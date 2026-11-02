"""Per-net autorouting (growing tree) with negotiated congestion (PathFinder):
each iteration reroutes the conflicting nets with an increasing present cost and an accumulated history cost."""
import math, os, time
import numpy as np
import conn
from router import LAYERS, dist_field, Shape

def item_cells(R, kind, data, lays):
    """Cells (L,i,j) covered by a copper item."""
    if kind == 'pad':
        shapes = [data]
    elif kind == 'zone':
        shapes = [Shape('poly', data, 0, tuple(lays))]
    elif kind == 'seg':
        # only cells on the track axis: a T branch must start on the axis (reliable connection in KiCad)
        _, layer, a, c, w, tag = data
        shapes = [Shape('seg', (a[0], a[1], c[0], c[1], 0.06), 0, (layer,))]
    else:
        _, p, d, tag = data
        shapes = [Shape('circle', (p[0], p[1], d / 2), 0, LAYERS)]
    out = []
    for sh in shapes:
        i0, i1, j0, j1 = R._window(sh.bbox, 0.0)
        if i0 >= i1 or j0 >= j1: continue
        X, Y = np.meshgrid(R.xs[j0:j1], R.ys[i0:i1])
        m = dist_field(sh.shrunk(0.02), X, Y) <= 1e-6
        ii, jj = np.nonzero(m)
        for L, ln in enumerate(LAYERS):
            if ln in sh.layers or ln in lays:
                out += [(L, int(a) + i0, int(c_) + j0) for a, c_ in zip(ii, jj)]
    return out

def pad_entries(R, byid, i):
    """Shapes of the specific pad of an item ('pad', ref, num, k): if several pads share the same number
    (mounting pads, shields), the one closest to the item is chosen."""
    ents = R.pads.get((i[1], i[2]), [])
    if len(ents) <= 1: return ents
    c = byid[i][2].centroid
    return [min(ents, key=lambda e: (e[1][0] - c.x) ** 2 + (e[1][1] - c.y) ** 2)]

THIN = {}        # net -> {(ref, pin)}: sense branches routed last and thin (e.g. VAC sense pins of wide input nets)
THIN_W = 0.3

class NetRouter:
    def __init__(self, R, b, planes, regions=None):
        self.R, self.b, self.planes = R, b, planes
        self.regions = regions or {}
        self.failed = {}       # net -> pads not reached
        self.paths = {}        # net -> [(path, w, classes)]
        self.fanrec = {}       # plane net -> [dict(path, shapes, entries)] per fan-out
        self.minw = {}         # net -> minimum allowed width (never go below it when searching for alternatives)
        self.reduced = {}      # net -> width used < requested

    def comps(self, net):
        its = conn.items_of_net(self.b, self.R, net)
        return conn.components_net(its, self.planes.get(net, []), self.b), its

    def ripup_fanouts(self, net, pred):
        """Rip up only the fan-outs of a plane net that satisfy pred(rec); returns how many."""
        keep, k = [], 0
        for rec in self.fanrec.get(net, []):
            if pred(rec):
                self.R.remove_route(net, rec['shapes'], rec['entries']); k += 1
            else:
                keep.append(rec)
        self.fanrec[net] = keep
        self.paths[net] = [rec['pe'] for rec in keep]
        return k

    def fanout_conflicts(self, net, rec):
        cells, vias = path_vias(rec['path'])
        R = self.R
        k = R.path_conflict(net, cells)
        for (vi, vj) in vias:
            if R.via_conflict(net, vi, vj) > 0: k += 4
        return k

    def fanout(self, net, region, soft=True, max_d=3.0, via_d=0.55, open_extra=0.45, tag='route'):
        """Connect each component of a plane net to a via inside the plane region. In hard mode, if
        there is no spot within ≤ max_d, retry with twice the radius."""
        R = self.R
        self.failed.pop(net, None)
        n = R.nid(net)
        if not any(self.paths.get(net, [])):
            self.fanrec[net] = []
        comps, its = self.comps(net)
        for comp in comps:
            if any(i[0] == 'plane' for i in comp): continue
            pads = [i for i in comp if i[0] == 'pad']
            if not pads: continue
            ok = False
            tries = [(max_d, None)] if soft else [(max_d, None), (2 * max_d, None)]
            if not soft:
                # last resort: join a via or pad already connected to the plane (e.g. a pull-up resistor)
                conn_items = [i for c in comps if any(x[0] == 'plane' for x in c) for i in c if i[0] in ('pad', 'via')]
                tries.append((2 * max_d, conn_items))
            for md, ci in tries:
                if self._fan_one(net, region, comp, its, soft, md, via_d, open_extra, tag, conn_items=ci):
                    ok = True; break
            if not ok:
                self.failed.setdefault(net, []).append(pads[0])
        return True

    def _fan_one(self, net, region, comp, its, soft, max_d, via_d, open_extra, tag, conn_items=None):
        """Fan-out of a component (joined pads) to a new via inside the plane region."""
        from scipy import ndimage as ndi
        R = self.R
        byid = {it[0]: it for it in its}
        src = []; bb = [1e9, 1e9, -1e9, -1e9]
        for i in comp:
            idd, lays, g, kind, info = byid[i]
            if kind == 'pad':
                for sh, c0 in pad_entries(R, byid, i):
                    src += item_cells(R, 'pad', sh, ())
                    b = sh.bbox; bb = [min(bb[0], b[0]), min(bb[1], b[1]), max(bb[2], b[2]), max(bb[3], b[3])]
            else:
                src += item_cells(R, kind, g if kind == 'zone' else info, lays)
        if not src: return False
        lays_avail = tuple(sorted(set(L for L, _, _ in src)))
        n = R.nid(net)
        joint = set()
        if conn_items:
            for i in conn_items:
                idd, lays, g, kind, info = byid[i]
                if kind == 'pad':
                    for sh, c0 in pad_entries(R, byid, i):
                        joint.update(c for c in item_cells(R, 'pad', sh, ()) if c[0] in lays_avail)
                else:
                    joint.update(c for c in item_cells(R, kind, g if kind == 'zone' else info, lays) if c[0] in lays_avail)
        def tmask(i0, i1, j0, j1, free, viaok, lays_avail=lays_avail):
            t = np.zeros_like(free)
            r = int(round(open_extra / R.P))
            yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
            dk = np.hypot(yy, xx) <= r + 1e-9
            ow = R.own[:, i0:i1, j0:j1]
            both = ((ow[0] == 0) | (ow[0] == n)) & ((ow[1] == 0) | (ow[1] == n))
            use = R.usage[:, i0:i1, j0:j1].max(axis=0) == 0
            opn = ndi.binary_erosion(both & use, structure=dk, border_value=0)
            for L in lays_avail:
                t[L] = viaok & free[L] & opn
            if not t.any():
                # no clear spot: at least no other nets' tracks within the via radius
                uo = R.vuse[:, i0:i1, j0:j1].astype(np.int32) - R.own_usage(n, i0, i1, j0, j1, via=True)
                ring_ok = uo.max(axis=0) <= 0
                for L in lays_avail:
                    t[L] = viaok & free[L] & ring_ok
            for (L, i, j) in joint:
                if i0 <= i < i1 and j0 <= j < j1: t[L, i - i0, j - j0] = 1
            return t
        path, nexp = R.search(net, src, None, tuple(bb), pad=max_d, via_cost=1e6, t45=0.2, t90=0.6,
                              layers_allowed=lays_avail, tgt_mask=tmask, via_region=region, weight=1.0,
                              max_exp=300000, soft=soft)
        if not path:
            return False
        end = path[-1]
        k0 = len(R.rshapes.get(n, [])); r0 = len(R.routes.get(net, []))
        R.path_to_route(net, path, tag=tag)
        if tuple(end) in joint:
            pe = (path, None, None)          # joined to already connected copper: no new via
        else:
            R.add_via(net, R.xy(end[1], end[2]), via_d, tag=tag)
            pe = (path + [(-1, end[1], end[2])], None, None)
        self.paths.setdefault(net, []).append(pe)
        self.fanrec.setdefault(net, []).append(dict(path=pe[0], pe=pe, shapes=R.rshapes[n][k0:],
                                                    entries=R.routes[net][r0:]))
        return True

    def route_net(self, net, w=None, pad=5.0, via_cost=30.0, max_tries=80, tag='route', bigpad=18.0, layers=(0, 1),
                  soft=True, soft_set=None):
        R = self.R
        if net in self.regions:
            return self.fanout(net, self.regions[net], soft=soft)
        self.failed.pop(net, None)
        for _ in range(max_tries):
            comps, its = self.comps(net)
            if len(comps) <= 1: break
            byid = {it[0]: it for it in its}
            def npads(c): return sum(1 for i in c if i[0] == 'pad')
            comps.sort(key=lambda c: -npads(c))
            tree = comps[0]
            tree_pts = [byid[i][2].centroid.coords[0] for i in tree if i[0] != 'plane']
            best = None
            thin_set = THIN.get(net, set())
            def is_thin(c):
                ps = [(i[1], i[2]) for i in c if i[0] == 'pad']
                return bool(ps) and all(x in thin_set for x in ps)
            cand = [c for c in comps[1:] if not is_thin(c)] or comps[1:]   # sense branches last
            for c in cand:
                for i in c:
                    if i[0] != 'pad': continue
                    p = byid[i][2].centroid.coords[0]
                    d = min(math.hypot(p[0] - q[0], p[1] - q[1]) for q in tree_pts) if tree_pts else 0
                    if best is None or d < best[0]: best = (d, c, i)
            if best is None: break
            _, comp_t, pid = best
            thin_branch = bool(thin_set) and is_thin(comp_t)
            src = []
            for i in tree:
                if i[0] == 'plane': continue
                idd, lays, g, kind, info = byid[i]
                if kind == 'pad':
                    for sh, c0 in pad_entries(R, byid, i):
                        src += item_cells(R, 'pad', sh, ())
                else:
                    src += item_cells(R, kind, g if kind == 'zone' else info, lays)
            tgts = []
            for i in comp_t:
                if i[0] != 'pad': continue
                for sh, c0 in pad_entries(R, byid, i):
                    tgts.append((sh, [LAYERS.index(l) for l in sh.layers]))
            tp = byid[pid][2].centroid.coords[0]
            near = sorted(tree_pts, key=lambda q: math.hypot(q[0] - tp[0], q[1] - tp[1]))[:6]
            bx = [q[0] for q in near] + [tp[0]]; by = [q[1] for q in near] + [tp[1]]
            bbox = (min(bx), min(by), max(bx), max(by))
            path = None; w_used = w
            mw = self.minw.get(net)
            wl = [w] if not w else ([w] + [x for x in (0.6, 0.4, 0.3, 0.25) if x < w and (mw is None or x >= mw - 1e-9)]
                                    + ([None] if mw is None else []))
            if thin_branch:
                wl = [THIN_W, None]
            for ww in wl:
                for padw in (pad, pad + 8.0, bigpad):
                    path, nexp = R.search(net, src, tgts, bbox, pad=padw, via_cost=via_cost, w=ww, layers_allowed=layers,
                                          soft=soft, soft_set=soft_set)
                    if path: break
                    if nexp >= 4_000_000:
                        # search budget exhausted (high congestion costs flatten the heuristic on long nets):
                        # retry greedier (weighted A*) instead of declaring the net unroutable
                        path, nexp = R.search(net, src, tgts, bbox, pad=padw, via_cost=via_cost, w=ww,
                                              layers_allowed=layers, soft=soft, soft_set=soft_set, weight=3.0)
                        if path: break
                if path:
                    w_used = ww; break
            if not path:
                self.failed.setdefault(net, []).append(pid)
                return False
            if w_used != w: self.reduced[net] = w_used or R.width
            R.path_to_route(net, path, w=w_used, tag=tag, cls=R.last_cls)
            self.paths.setdefault(net, []).append((path, w_used, R.last_cls))
        return True

def path_vias(path):
    cells = [p for p in path if p[0] >= 0]
    vias = [(p[1], p[2]) for p in path if p[0] < 0]
    for a, b2 in zip(cells, cells[1:]):
        if a[0] != b2[0]: vias.append((b2[1], b2[2]))
    return cells, vias

def victims(R, nr, net):
    """Autorouted nets that the current routes of 'net' collide with."""
    n = R.nid(net)
    out = set()
    for path, w, narrow in nr.paths.get(net, []):
        cells, vias = path_vias(path)
        D = R.infl() + ((w - R.width) / 2 + 0.15 if (w and w > R.width) else 0.0)
        for (L, i, j) in R.path_conflict(net, cells, w=w, cls=narrow, ret_cells=True):
            x, y = R.xy(i, j)
            out |= R.nets_near(L, x, y, D, exclude=n)
        for (vi, vj) in vias:
            if R.via_conflict(net, vi, vj) > 0:
                x, y = R.xy(vi, vj)
                out |= R.nets_near(0, x, y, R.vinfl(), exclude=n) | R.nets_near(1, x, y, R.vinfl(), exclude=n)
    return {R.netname[k] for k in out}

def net_conflicts(nr, R, net):
    c = 0
    for path, w, cl in nr.paths.get(net, []):
        cells, vias = path_vias(path)
        c += R.path_conflict(net, cells, w=w, cls=cl)
        for (vi, vj) in vias:
            if R.via_conflict(net, vi, vj) > 0: c += 4
    return c

def local_negotiate(nr, R, nets, widths, layers, iters=10, verbose=False):
    """PathFinder restricted to a group of signal nets: they negotiate among themselves (soft) and the rest of the copper
    is hard. Returns True if the group ends with no conflicts and no failures."""
    ids = {R.nid(n) for n in nets}
    hist0 = R.hist.copy()
    ok = False
    for it in range(iters):
        R.pres_fac = 0.5 * (1.45 ** it)
        for n in nets:
            R.ripup(n); nr.paths[n] = []; nr.failed.pop(n, None)
            nr.route_net(n, w=widths.get(n), layers=layers.get(n, (0, 1)), soft=True, soft_set=ids)
        conf = {n: net_conflicts(nr, R, n) for n in nets}
        failed = [n for n in nets if n in nr.failed]
        if verbose: print(f'    local {it + 1}: conflicts={sum(1 for v in conf.values() if v)} failed={failed}')
        if not failed and not any(conf.values()):
            ok = True; break
        score = sum(conf.values()) + 100 * len(failed)
        if it == 0 or score < best:
            best, stall = score, 0
        else:
            stall += 1
            if stall >= 3: break
        for n in nets:
            if conf[n]:
                for path, w, cl in nr.paths.get(n, []):
                    for (L, i, j) in path:
                        if L >= 0: R.hist[L, i, j] += 0.2
    R.hist[:] = np.maximum(R.hist, hist0)
    return ok

def repair(nr, R, widths, layers, rounds=24, pres=60.0, verbose=True):
    """Targeted rip-up and reroute: the failed net is routed in soft mode and the nets it collides with are
    rerouted in hard mode around it (plane fan-outs are only ripped up if they collide). If two nets keep
    alternating the failure, both are negotiated together (the rest of the copper stays fixed)."""
    queue = list(nr.failed)
    tries, blamed = {}, {}
    for rd in range(rounds):
        if not queue: break
        net = queue.pop(0)
        tries[net] = tries.get(net, 0) + 1
        if tries[net] > 4: continue
        R.pres_fac = pres
        nr.failed.pop(net, None)
        if net in nr.regions:
            nr.fanout(net, nr.regions[net], soft=True)
            if net in nr.failed:
                if verbose: print(f'  repair: {net} no fan-out even in soft mode: {nr.failed[net][:4]}')
                continue
        else:
            R.ripup(net); nr.paths[net] = []
            if not nr.route_net(net, w=widths.get(net), layers=layers.get(net, (0, 1)), soft=True):
                if verbose: print(f'  repair: {net} has no path even in soft mode')
                continue
        bad, vict_all = [], set()
        for sweep in range(3):
            vict = victims(R, nr, net)
            if not vict: break
            vict_all |= vict
            for v in vict:
                if v in nr.regions:
                    nr.ripup_fanouts(v, lambda rec, v=v: nr.fanout_conflicts(v, rec) > 0)
                else:
                    R.ripup(v); nr.paths[v] = []
            for v in sorted(vict, key=lambda x: x in nr.regions):
                if v in nr.regions:
                    nr.fanout(v, nr.regions[v], soft=False)
                    if v in nr.failed and v not in bad: bad.append(v)
                elif not nr.route_net(v, w=widths.get(v), layers=layers.get(v, (0, 1)), soft=False):
                    if v not in bad: bad.append(v)
        vict = vict_all
        if net_conflicts(nr, R, net):
            # still overlapping: better to rip it up and retry later than to leave a short circuit
            if net in nr.regions:
                nr.ripup_fanouts(net, lambda rec: nr.fanout_conflicts(net, rec) > 0)
            else:
                R.ripup(net); nr.paths[net] = []
            nr.failed.setdefault(net, []).append('solape')
            bad.append(net)
        # A↔B cycle: negotiate both at once
        for v in list(bad):
            if v != net and v not in nr.regions and net not in nr.regions and net in blamed.get(v, ()):
                ok = local_negotiate(nr, R, [net, v], widths, layers)
                if verbose: print(f'  repair: cycle {net} ↔ {v}: negotiation {"resolved" if ok else "unresolved"}')
                if ok: bad.remove(v)
        blamed[net] = set(bad)
        if verbose: print(f'  repair {rd + 1}: {net} → victims {sorted(vict)} → failing {bad}')
        for v in bad:
            if v not in queue: queue.append(v)
    # cleanup: no route may remain overlapping another net (better unrouted than shorted)
    while True:
        conf = {n: net_conflicts(nr, R, n) for n in list(nr.paths) if nr.paths.get(n)}
        conf = {n: c for n, c in conf.items() if c}
        if not conf: break
        n = max(conf, key=lambda k: conf[k])
        if n in nr.regions:
            nr.ripup_fanouts(n, lambda rec, n=n: nr.fanout_conflicts(n, rec) > 0)
        else:
            R.ripup(n); nr.paths[n] = []
        nr.failed.setdefault(n, []).append('solape')
        if verbose: print(f'  cleanup: {n} ripped up due to overlap')
    return nr

def _snapshot(R, nr):
    """Deep copy of the router state and the NetRouter (they share shapes, so they are copied together)."""
    import copy
    shared = {id(nr.b): nr.b, id(nr.planes): nr.planes, id(nr.regions): nr.regions}
    nd = {k: v for k, v in nr.__dict__.items() if k not in ('R', 'b', 'planes', 'regions')}
    return copy.deepcopy((dict(R.__dict__), nd), memo=shared)

def _restore(R, nr, snap):
    import copy
    rd, nd = copy.deepcopy(snap)
    R.__dict__.update(rd); nr.__dict__.update(nd)

def _endgame(nr, R, conflict, widths, layers, order_key, verbose):
    """Hard pass (conflicting nets are ripped up and routed without overlapping anything) and repair."""
    hard_order = sorted(conflict, key=order_key)
    sig = [n for n in hard_order if n not in nr.regions]
    pln = [n for n in hard_order if n in nr.regions]
    for net in sig:
        R.ripup(net); nr.paths[net] = []
    for net in pln:
        k = nr.ripup_fanouts(net, lambda rec, net=net: nr.fanout_conflicts(net, rec) > 0)
        if verbose: print(f'  hard pass: {net}: {k} fan-outs ripped up')
    for net in sig:
        nr.route_net(net, w=widths.get(net), layers=layers.get(net, (0, 1)), soft=False)
    for net in pln:
        nr.fanout(net, nr.regions[net], soft=False)
    if verbose:
        print(f'  hard pass: failed={len(nr.failed)} {list(nr.failed)[:12]}')
    if nr.failed:
        repair(nr, R, widths, layers, verbose=verbose)
        if verbose:
            print(f'  after repair: failed={len(nr.failed)} {list(nr.failed)[:12]}')

def rescue(nr, R, widths, layers, verbose=True, rounds=((2.0, 8, 12), (3.5, 14, 16), (5.0, 20, 20))):
    """Last resort for signal nets that are still incomplete: local negotiation (PathFinder) between the net and the
    nets whose autorouted copper passes near its pads, with the rest of the copper fixed. If unresolved, it is undone."""
    for net in list(nr.failed):
        if net in nr.regions: continue
        n = R.nid(net)
        pads = [c for (_, _, sh, c) in R.netpads.get(net, [])]
        for rad, maxn, iters in rounds:
            first = {}
            for r in [x * rad / 4 for x in range(1, 5)]:
                for (x, y) in pads:
                    for L in (0, 1):
                        for k in R.nets_near(L, x, y, r, exclude=n):
                            nm = R.netname[k]
                            if nm in nr.regions or nm.startswith('__') or nm in first: continue
                            first[nm] = r
            group = [net] + sorted(first, key=lambda k: first[k])[:maxn]
            snap = _snapshot(R, nr)
            ok = local_negotiate(nr, R, group, widths, layers, iters=iters)
            if ok:
                if verbose: print(f'  rescue: {net} resolved by negotiating with {len(group) - 1} neighbouring nets (r = {rad} mm)')
                break
            _restore(R, nr, snap)
            if verbose: print(f'  rescue: {net} unresolved (r = {rad} mm, {len(group) - 1} neighbouring nets)')
    return nr

def route_all(R, b, planes, order, widths, layers=None, iters=32, p0=0.5, growth=1.3, h_fac=0.8, verbose=True,
              regions=None, minw=None, endgame_tries=1, on_iters=None, rescue_rounds=None, checkpoint=None):
    layers = layers or {}
    nr = NetRouter(R, b, planes, regions)
    nr.minw = dict(minw or {})
    t0 = time.time()
    todo = list(order)
    conflict = {}
    it0 = 0
    stage = 'iters'
    if checkpoint and os.path.exists(checkpoint):
        import pickle
        st = pickle.load(open(checkpoint, 'rb'))
        nr, it0, conflict, todo, stage = st['nr'], st['it'] + 1, st['conflict'], st['todo'], st.get('stage', 'iters')
        R = nr.R
        if verbose: print(f'  resumed from checkpoint: stage {stage}, next iteration {it0 + 1}', flush=True)
    def save(it, stage):
        if not checkpoint: return
        import pickle
        tmp = checkpoint + '.tmp'
        pickle.dump(dict(nr=nr, it=it, conflict=conflict, todo=todo, stage=stage), open(tmp, 'wb'), protocol=5)
        os.replace(tmp, checkpoint)
    for it in range(it0 if stage == 'iters' else iters, iters):
        R.pres_fac = p0 * (growth ** it)
        for net in todo:
            R.ripup(net); nr.paths[net] = []
            nr.route_net(net, w=widths.get(net), layers=layers.get(net, (0, 1)))
        conflict = {}
        for net in order:
            c = 0
            for path, w, narrow in nr.paths.get(net, []):
                cells = [p for p in path if p[0] >= 0]
                vias = [(p[1], p[2]) for p in path if p[0] < 0]
                # vias at the path's layer changes
                for a, b2 in zip(cells, cells[1:]):
                    if a[0] != b2[0]: vias.append((b2[1], b2[2]))
                k = R.path_conflict(net, cells, w=w, cls=narrow)
                for (vi, vj) in vias:
                    if R.via_conflict(net, vi, vj) > 0: k += 4
                if k:
                    c += k
                    for (L, i, j) in cells:
                        R.hist[L, i, j] += h_fac * 0.25
            if c: conflict[net] = c
        failed = set(nr.failed)
        todo = [n for n in order if n in conflict or n in failed]
        if verbose:
            print(f'  iter {it + 1}: pres={R.pres_fac:.2f} conflicts={len(conflict)} '
                  f'(cells {sum(conflict.values())}) failed={len(failed)} ({time.time() - t0:.0f} s)', flush=True)
        save(it, 'iters' if (todo and it < iters - 1) else 'endgame')
        if not todo: break
    if on_iters is not None and stage != 'rescue':
        on_iters(nr, conflict)
    if not conflict and not nr.failed:
        return nr
    if stage == 'rescue':
        if nr.failed and rescue_rounds != ():
            rescue(nr, R, widths, layers, verbose=verbose, **({'rounds': rescue_rounds} if rescue_rounds else {}))
        return nr
    # endgame with several restarts: same negotiation, different hard-pass order; the best result is kept
    import random
    keys = [lambda n: conflict.get(n, 0), lambda n: -conflict.get(n, 0)]
    for k in range(2, endgame_tries):
        rng = random.Random(k)
        rk = {n: rng.random() for n in order}
        keys.append(lambda n, rk=rk: rk.get(n, 0.0))
    snap = _snapshot(R, nr) if endgame_tries > 1 else None
    best = None
    for k in range(max(1, endgame_tries)):
        if k > 0:
            _restore(R, nr, snap)
            if verbose: print(f'  endgame, attempt {k + 1}/{endgame_tries}')
        _endgame(nr, R, conflict, widths, layers, keys[k], verbose)
        nf = len(nr.failed)
        if best is None or nf < best[0]:
            best = (nf, k, _snapshot(R, nr) if (nf and k < endgame_tries - 1) else None)
        if nf == 0:
            break
    if best[0] < len(nr.failed) and best[2] is not None:
        _restore(R, nr, best[2])
        if verbose: print(f'  endgame: keeping attempt {best[1] + 1} ({best[0]} failed)')
    save(iters - 1, 'rescue')
    if nr.failed and rescue_rounds != ():
        rescue(nr, R, widths, layers, verbose=verbose, **({'rounds': rescue_rounds} if rescue_rounds else {}))
        if verbose: print(f'  after rescue: failed={len(nr.failed)} {list(nr.failed)[:12]}')
    return nr
