"""Per-net connectivity check (pads, tracks, vias and planes), in the style of KiCad's ratsnest."""
from shapely.geometry import LineString, Point
from shapely.strtree import STRtree
import geom

class UF:
    def __init__(self): self.p = {}
    def f(self, a):
        self.p.setdefault(a, a)
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]; a = self.p[a]
        return a
    def u(self, a, b):
        ra, rb = self.f(a), self.f(b)
        if ra != rb: self.p[ra] = rb

def items_of(b, R):
    """Returns dict net -> list of (id, layers(set), geom, kind, info)."""
    out = {}
    for ref, pl in b.placed.items():
        for k, ps in enumerate(geom.pad_shapes(pl)):
            n = ps['net']
            if not n or n.startswith('unconnected') or not ps['layers']: continue
            lays = set(ps['layers'])
            out.setdefault(n, []).append((('pad', ref, ps['num'], k), lays, ps['poly'], 'pad', (ref, ps['num'])))
    for net, its in R.routes.items():
        if net.startswith('__'): continue
        for k, it in enumerate(its):
            if it[0] == 'seg':
                _, layer, a, c, w, tag = it
                g = LineString([a, c]).buffer(w / 2, 8) if (a != c) else Point(a).buffer(w / 2, 8)
                out.setdefault(net, []).append((('seg', net, k), {layer}, g, 'seg', it))
            else:
                _, p, d, tag = it
                out.setdefault(net, []).append((('via', net, k), {'F.Cu', 'B.Cu', 'In1.Cu', 'In2.Cu'}, Point(p).buffer(d / 2, 12), 'via', it))
    for k, (sh, hard) in enumerate(R.shapes):          # fixed copper zones (e.g. VSYS next to the charger)
        if sh.kind == 'poly' and sh.tag == 'fixed' and sh.net in R.netname:
            net = R.netname[sh.net]
            out.setdefault(net, []).append((('zone', net, k), set(sh.layers), sh.p, 'zone', None))
    return out

def components(b, R, planes):
    """planes: dict net -> list of (layer, polygon). Returns dict net -> list of components (each a list of ids)."""
    res = {}
    for net, its in items_of(b, R).items():
        uf = UF()
        geoms = [g for _, _, g, _, _ in its]
        tree = STRtree(geoms)
        for i, (idd, lays, g, kind, info) in enumerate(its):
            uf.f(idd)
            for j in tree.query(g):
                j = int(j)
                if j <= i: continue
                idd2, lays2, g2, k2, _ = its[j]
                if not (lays & lays2): continue
                # two items on common layers are connected if they touch
                if g.intersects(g2): uf.u(idd, idd2)
        for layer, poly in planes.get(net, []):
            node = ('plane', net, layer)
            for idd, lays, g, kind, info in its:
                if layer in lays and kind in ('via', 'pad') and poly.intersects(g):
                    uf.u(idd, node)
        comps = {}
        for idd, lays, g, kind, info in its:
            comps.setdefault(uf.f(idd), []).append(idd)
        res[net] = list(comps.values())
    return res

def report(b, R, planes, verbose=True):
    comps = {}
    nets = set(pad_items(b)) | set(n for n in R.routes if not n.startswith('__'))
    for n in nets:
        comps[n] = components_net(items_of_net(b, R, n), planes.get(n, []), b)
    bad = {n: c for n, c in comps.items() if len(c) > 1}
    if verbose:
        print(f'nets: {len(comps)}, incomplete: {len(bad)}')
        for n, c in sorted(bad.items()):
            pads = [[f'{i[1]}.{i[2]}' for i in comp if i[0] == 'pad'] for comp in c]
            print(f'  {n}: {len(c)} groups → {pads[:6]}')
    return bad

_PADCACHE = {}
def pad_items(b):
    key = id(b)
    if key not in _PADCACHE:
        d = {}
        for ref, pl in b.placed.items():
            for k, ps in enumerate(geom.pad_shapes(pl)):
                n = ps['net']
                if not n or n.startswith('unconnected') or not ps['layers']: continue
                d.setdefault(n, []).append((('pad', ref, ps['num'], k), set(ps['layers']), ps['poly'], 'pad', (ref, ps['num'])))
        _PADCACHE[key] = d
    return _PADCACHE[key]

def items_of_net(b, R, net):
    out = list(pad_items(b).get(net, []))
    for k, it in enumerate(R.routes.get(net, [])):
        if it[0] == 'seg':
            _, layer, a, c, w, tag = it
            g = LineString([a, c]).buffer(w / 2, 8) if (a != c) else Point(a).buffer(w / 2, 8)
            out.append((('seg', net, k), {layer}, g, 'seg', it))
        else:
            _, p, d, tag = it
            out.append((('via', net, k), {'F.Cu', 'B.Cu', 'In1.Cu', 'In2.Cu'}, Point(p).buffer(d / 2, 12), 'via', it))
    n = R.netid.get(net)
    for k, (sh, hard) in enumerate(R.shapes):          # fixed copper zones
        if sh.kind == 'poly' and sh.tag == 'fixed' and sh.net == n:
            out.append((('zone', net, k), set(sh.layers), sh.p, 'zone', None))
    return out

JUMPER_FPS = ('robot:SW_SPST_PTS810',)

def components_net(its, net_planes, b=None):
    uf = UF()
    if not its: return []
    # repeated pads joined internally (push buttons)
    seen = {}
    for idd, lays, g, kind, info in its:
        if kind == 'pad' and b is not None and b.placed[idd[1]].libid in JUMPER_FPS:
            key = (idd[1], idd[2])
            if key in seen: uf.u(seen[key], idd)
            else: seen[key] = idd
    geoms = [g for _, _, g, _, _ in its]
    tree = STRtree(geoms)
    for i, (idd, lays, g, kind, info) in enumerate(its):
        uf.f(idd)
        for j in tree.query(g):
            j = int(j)
            if j <= i: continue
            idd2, lays2, g2, k2, _ = its[j]
            if not (lays & lays2): continue
            if g.intersects(g2): uf.u(idd, idd2)
    for layer, poly in net_planes:
        node = ('plane', layer)
        uf.f(node)
        for idd, lays, g, kind, info in its:
            if layer in lays and kind in ('via', 'pad') and poly.intersects(g):
                uf.u(idd, node)
    comps = {}
    for idd, lays, g, kind, info in its:
        comps.setdefault(uf.f(idd), []).append(idd)
    for layer, poly in net_planes:
        r = uf.f(('plane', layer))
        if r in comps and ('plane', layer) not in comps[r]: comps[r].append(('plane', layer))
    return list(comps.values())

def missing_rats(b, R, planes):
    """Edges (net, a, b) between disconnected components of each net (for the preview)."""
    out = []
    nets = set(pad_items(b)) | set(n for n in R.routes if not n.startswith('__'))
    for n in nets:
        its = items_of_net(b, R, n)
        comps = components_net(its, planes.get(n, []), b)
        if len(comps) < 2: continue
        byid = {i[0]: i for i in its}
        cents = []
        for c in comps:
            pts = [byid[i][2].centroid.coords[0] for i in c if i in byid and i[0] == 'pad']
            if pts: cents.append(pts)
        for k in range(1, len(cents)):
            best = None
            for p in cents[k]:
                for q in cents[0]:
                    d = (p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2
                    if best is None or d < best[0]: best = (d, p, q)
            out.append((n, best[1], best[2]))
    return out

def trim_stubs(b, R, planes, verbose=True):
    """Remove track segments with a dangling end (like KiCad's 'track_dangling' DRC: an end is attached if
    other copper of the net is within ≤ half a width) as long as the net stays equally connected."""
    removed = 0
    for net in [n for n in R.routes if not n.startswith('__')]:
        keep = set()
        while True:
            its = items_of_net(b, R, net)
            base = len(components_net(its, planes.get(net, []), b))
            cand = None
            for k, it in enumerate(R.routes[net]):
                if it[0] != 'seg' or id(it) in keep: continue
                _, layer, a, c, w, tag = it
                for E in (a, c):
                    pE = Point(E)
                    att = False
                    for idd, lays, g, kind, info in its:
                        if kind == 'seg' and info is it: continue
                        if layer not in lays: continue
                        if g.distance(pE) <= w / 2 + 1e-6:
                            att = True; break
                    if not att:
                        cand = (k, it); break
                if cand: break
            if not cand: break
            R.routes[net].pop(cand[0])
            if len(components_net(items_of_net(b, R, net), planes.get(net, []), b)) > base:
                R.routes[net].insert(cand[0], cand[1]); keep.add(id(cand[1]))
            else:
                removed += 1
    if verbose: print(f'dangling segments removed: {removed}')
    return removed
