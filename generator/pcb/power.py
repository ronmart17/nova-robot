"""Power reinforcement on the already routed board (pcbnew, before zone fill):
1) widens the power-net segments that the router left below their nominal width (necks next to
   fine-pitch pads or narrow passages) to the largest width that fits;
2) adds parallel vias next to the vias of the high-current nets (and, if needed, a short segment on the other
   layer to join them), so as not to trust 2 A to a single 0.3 mm via.
Exact geometric check with shapely on KiCad's polygons (clearance 0.15, copper–edge 0.3, hole–copper
0.25, hole–hole 0.25, keepout areas, no vias inside SMD pads). Pours and planes are filled afterwards,
so they do not count as obstacles. KiCad's DRC validates the result."""
import math
import pcbnew
from shapely.geometry import Polygon, Point, LineString
from shapely.ops import unary_union
from shapely.strtree import STRtree

MM = 1e6
CLR, EDGE, HOLE_CLR, HOLE_HOLE = 0.15, 0.3, 0.25, 0.25
EPS = 0.012
VIA_D, VIA_DRILL = 0.55, 0.3

def _sps_to_shapely(sps):
    polys = []
    for i in range(sps.OutlineCount()):
        o = sps.COutline(i)
        pts = [(o.CPoint(k).x / MM, o.CPoint(k).y / MM) for k in range(o.PointCount())]
        holes = []
        for h in range(sps.HoleCount(i)):
            hh = sps.CHole(i, h)
            holes.append([(hh.CPoint(k).x / MM, hh.CPoint(k).y / MM) for k in range(hh.PointCount())])
        if len(pts) >= 3:
            polys.append(Polygon(pts, holes).buffer(0))
    return unary_union(polys) if polys else Polygon()

def _xy(p):
    return (p.x / MM, p.y / MM)

def _norm(net):
    """Net name as used by the router (KiCad escapes the '/' in sheet names as {slash})."""
    return net.replace('{slash}', '/')

class Geo:
    """Copper per outer layer (pads, tracks, vias) with its net, drill holes and keepout areas."""
    def __init__(self, b):
        self.b = b
        self.layers = {pcbnew.F_Cu: 'F', pcbnew.B_Cu: 'B'}
        self.items = {L: [] for L in self.layers}        # (geom, net, kind)
        self.holes = []                                  # (geom, net)
        self.smd = []                                    # SMD pad polygons (any outer layer)
        for fp in b.GetFootprints():
            for pad in fp.Pads():
                net = pad.GetNetname()
                for L in self.layers:
                    if pad.IsOnLayer(L):
                        sps = pcbnew.SHAPE_POLY_SET()
                        pad.TransformShapeToPolygon(sps, L, 0, 5000, pcbnew.ERROR_INSIDE)
                        g = _sps_to_shapely(sps)
                        self.items[L].append((g, net, 'pad'))
                        if pad.GetAttribute() == pcbnew.PAD_ATTRIB_SMD:
                            self.smd.append(g)
                if pad.HasHole():
                    ds = pad.GetDrillSize()
                    c = _xy(pad.GetPosition())
                    if ds.x == ds.y:
                        hg = Point(c).buffer(ds.x / MM / 2, 24)
                    else:
                        sps = pcbnew.SHAPE_POLY_SET()
                        pad.TransformHoleToPolygon(sps, 0, 5000, pcbnew.ERROR_INSIDE)
                        hg = _sps_to_shapely(sps)
                    self.holes.append((hg, net))
        for t in b.GetTracks():
            net = t.GetNetname()
            if t.GetClass() == 'PCB_VIA':
                c = _xy(t.GetPosition())
                g = Point(c).buffer(t.GetWidth(pcbnew.F_Cu) / MM / 2, 24)
                for L in self.layers:
                    self.items[L].append((g, net, 'via'))
                self.holes.append((Point(c).buffer(t.GetDrillValue() / MM / 2, 24), net))
            elif t.GetClass() == 'PCB_TRACK' and t.GetLayer() in self.layers:
                g = LineString([_xy(t.GetStart()), _xy(t.GetEnd())]).buffer(t.GetWidth() / MM / 2, 12)
                self.items[t.GetLayer()].append((g, net, 'track'))
        sps = pcbnew.SHAPE_POLY_SET()
        b.GetBoardPolygonOutlines(sps, False)
        self.board = _sps_to_shapely(sps)
        self.inner_track = self.board.buffer(-(EDGE + EPS))
        self.inner_via = self.board.buffer(-(EDGE + EPS + VIA_D / 2))
        self.keep_tracks = {L: [] for L in self.layers}
        self.keep_vias = []
        zones = list(b.Zones())
        for fp in b.GetFootprints():
            zones += list(fp.Zones())
        for z in zones:
            if not z.GetIsRuleArea(): continue
            g = _sps_to_shapely(z.Outline())
            if z.GetDoNotAllowVias() and any(z.IsOnLayer(L) for L in (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu)):
                self.keep_vias.append(g)
            for L in self.layers:
                if z.GetDoNotAllowTracks() and z.IsOnLayer(L):
                    self.keep_tracks[L].append(g)
        self.trees = {L: STRtree([g for g, n, k in self.items[L]]) for L in self.layers}
        self.htree = STRtree([g for g, n in self.holes])
        self.extra = {L: [] for L in self.layers}
        self.extra_holes = []

    def same_net(self, L, net):
        return unary_union([g for g, n, k in self.items[L] + self.extra[L] if n == net])

    def clear_on(self, L, g, net, d=CLR):
        for i in self.trees[L].query(g, predicate='dwithin', distance=d + EPS):
            if self.items[L][i][1] != net:
                return False
        for gg, n, k in self.extra[L]:
            if n != net and g.distance(gg) < d + EPS:
                return False
        return True

    def holes_clear(self, g, net, d=HOLE_CLR):
        """Copper g against drill holes of other nets."""
        for i in self.htree.query(g, predicate='dwithin', distance=d + EPS):
            if self.holes[i][1] != net:
                return False
        for gg, n in self.extra_holes:
            if n != net and g.distance(gg) < d + EPS:
                return False
        return True

    def track_ok(self, L, a, c, w, net):
        g = LineString([a, c]).buffer(w / 2, 12)
        if not g.within(self.inner_track): return False
        if any(g.intersects(k) for k in self.keep_tracks[L]): return False
        return self.clear_on(L, g, net) and self.holes_clear(g, net)

    def add_track_geom(self, L, a, c, w, net):
        self.extra[L].append((LineString([a, c]).buffer(w / 2, 12), net, 'track'))

    def via_ok(self, q, net, d=VIA_D, drill=VIA_DRILL, ignore=None):
        """Does a via (d/drill) fit at q? ignore: own drill geometry that does not count (when enlarging a via)."""
        pad = Point(q).buffer(d / 2, 24)
        hole = Point(q).buffer(drill / 2, 24)
        if not Point(q).within(self.board.buffer(-(EDGE + EPS + d / 2))): return False
        if any(pad.intersects(k) for k in self.keep_vias): return False
        if any(hole.intersection(s).area > 1e-4 for s in self.smd): return False      # never drill inside an SMD pad
        for L in self.layers:
            if not self.clear_on(L, pad, net): return False
        # drill: against other nets' copper on outer layers and against all drill holes
        for L in self.layers:
            if not self.clear_on(L, hole, net, HOLE_CLR): return False
        for i in self.htree.query(hole, predicate='dwithin', distance=HOLE_HOLE + EPS):
            if ignore is not None and self.holes[i][0].equals(ignore): continue
            return False
        for gg, n in self.extra_holes:
            if hole.distance(gg) < HOLE_HOLE + EPS: return False
        return True

    def add_via_geom(self, q, net, d=VIA_D, drill=VIA_DRILL):
        pad = Point(q).buffer(d / 2, 24)
        for L in self.layers:
            self.extra[L].append((pad, net, 'via'))
        self.extra_holes.append((Point(q).buffer(drill / 2, 24), net))

def widen(b, G, widths, verbose=True):
    """Widen the segments of the 'widths' nets that are below nominal. Returns the widened length in mm."""
    steps = (1.5, 1.2, 1.0, 0.8, 0.6, 0.5, 0.4, 0.3, 0.25, 0.2)
    total = 0.0; nseg = 0
    rep = {}
    tracks = [t for t in b.GetTracks() if t.GetClass() == 'PCB_TRACK']
    for t in tracks:
        net = t.GetNetname()
        if _norm(net) not in widths: continue
        w0 = t.GetWidth() / MM; wn = widths[_norm(net)]
        if w0 >= wn - 1e-6: continue
        L = t.GetLayer()
        if L not in G.layers: continue
        a, c = _xy(t.GetStart()), _xy(t.GetEnd())
        for w in [x for x in steps if w0 + 1e-6 < x <= wn + 1e-6]:
            if G.track_ok(L, a, c, w, net):
                t.SetWidth(int(round(w * MM)))
                G.add_track_geom(L, a, c, w, net)
                ln = math.dist(a, c)
                total += ln; nseg += 1
                r = rep.setdefault(_norm(net), [0, 0.0, 9.9]); r[0] += 1; r[1] += ln; r[2] = min(r[2], w)
                break
    if verbose:
        print(f'  widened {nseg} segments ({total:.1f} mm)')
        for net, (k, ln, wmin) in sorted(rep.items()):
            print(f'    {net.split("/")[-1]}: {k} segments, {ln:.1f} mm')
    return total

def _new_track(b, G, L, a, c, w, netinfo, net):
    tr = pcbnew.PCB_TRACK(b)
    tr.SetStart(pcbnew.VECTOR2I(int(round(a[0] * MM)), int(round(a[1] * MM))))
    tr.SetEnd(pcbnew.VECTOR2I(int(round(c[0] * MM)), int(round(c[1] * MM))))
    tr.SetWidth(int(round(w * MM))); tr.SetLayer(L); tr.SetNet(netinfo)
    b.Add(tr)
    G.add_track_geom(L, a, c, w, net)

def _new_via(b, G, q, netinfo, net):
    nv = pcbnew.PCB_VIA(b)
    nv.SetPosition(pcbnew.VECTOR2I(int(round(q[0] * MM)), int(round(q[1] * MM))))
    nv.SetViaType(pcbnew.VIATYPE_THROUGH)
    nv.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    nv.SetWidth(int(round(VIA_D * MM))); nv.SetDrill(int(round(VIA_DRILL * MM)))
    nv.SetNet(netinfo)
    b.Add(nv)
    G.add_via_geom(q, net)

def _seg_points(a, c, step=0.05):
    L = math.dist(a, c)
    n = max(1, int(L / step))
    return [(a[0] + (c[0] - a[0]) * k / n, a[1] + (c[1] - a[1]) * k / n) for k in range(n + 1)]

def _stub_width(G, L, a, c, net, wn):
    for ws in sorted({min(wn, 0.8), 0.6, 0.5, 0.4}, reverse=True):
        if ws <= wn + 1e-6 and G.track_ok(L, a, c, ws, net):
            return ws
    return None

def add_parallel_vias(b, G, nets, widths, per_via=2, verbose=True, only=None):
    """For each via of 'nets', try to add 'per_via' more vias at 0.6–1.3 mm along the net's tracks that touch it;
    if there is no copper of the net at that point on the other layer, add a short segment from the original via."""
    vias = [t for t in b.GetTracks() if t.GetClass() == 'PCB_VIA' and _norm(t.GetNetname()) in nets]
    if only is not None:
        vias = [v for v in vias if (round(_xy(v.GetPosition())[0], 3), round(_xy(v.GetPosition())[1], 3)) in only]
    tracks = [t for t in b.GetTracks() if t.GetClass() == 'PCB_TRACK' and _norm(t.GetNetname()) in nets]
    added = {}
    for v in vias:
        net = v.GetNetname(); p = _xy(v.GetPosition()); wn = widths.get(_norm(net), 0.6)
        cands = []
        for t in tracks:
            if t.GetNetname() != net or t.GetLayer() not in G.layers: continue
            a, c = _xy(t.GetStart()), _xy(t.GetEnd())
            if LineString([a, c]).distance(Point(p)) > 0.35: continue
            for q in _seg_points(a, c):
                d = math.dist(q, p)
                if 0.6 <= d <= 1.3:
                    cands.append((d, t.GetLayer(), q))
        k = 0
        done = [p]
        for d, Ls, q in sorted(cands):
            if k >= per_via: break
            if any(math.dist(q, o) < 0.6 for o in done): continue
            if not G.via_ok(q, net): continue
            Lo = pcbnew.B_Cu if Ls == pcbnew.F_Cu else pcbnew.F_Cu
            disk = Point(q).buffer(VIA_D / 2, 24)
            stub = None
            if disk.intersection(G.same_net(Lo, net)).area < 0.05:
                stub = _stub_width(G, Lo, p, q, net, wn)
                if stub is None: continue
                _new_track(b, G, Lo, p, q, stub, v.GetNet(), net)
            _new_via(b, G, q, v.GetNet(), net)
            done.append(q); k += 1
        added.setdefault(_norm(net), []).append((p, k))
    if verbose:
        for net, lst in sorted(added.items()):
            s = ', '.join(f'({x:.1f},{y:.1f})+{k}' for (x, y), k in lst)
            print(f'  parallel vias {net.split("/")[-1]}: {s}')
    return added

def bridge_vias(b, G, vias, widths, reach=4.0, verbose=True):
    """For vias with no room for another one beside them: search the same net's tracks (≤ reach mm) for a point where
    a new via fits and join it with a straight segment to the net's copper on the other layer → parallel path."""
    out = []
    for v in vias:
        net = v.GetNetname(); p = _xy(v.GetPosition()); wn = widths.get(_norm(net), 0.6)
        ok = False
        for La in G.layers:
            Lb = pcbnew.B_Cu if La == pcbnew.F_Cu else pcbnew.F_Cu
            other = [t for t in b.GetTracks() if t.GetClass() == 'PCB_TRACK' and t.GetNetname() == net
                     and t.GetLayer() == Lb]
            if not other: continue
            ogeom = unary_union([LineString([_xy(t.GetStart()), _xy(t.GetEnd())]) for t in other])
            cands = []
            for t in b.GetTracks():
                if t.GetClass() != 'PCB_TRACK' or t.GetNetname() != net or t.GetLayer() != La: continue
                if t.GetWidth() / MM < 0.39: continue
                a, c = _xy(t.GetStart()), _xy(t.GetEnd())
                for q in _seg_points(a, c, 0.1):
                    d = math.dist(q, p)
                    if 0.6 <= d <= reach:
                        cands.append((ogeom.distance(Point(q)), d, q))
            for dist_o, d, q in sorted(cands):
                if dist_o > reach: break
                if not G.via_ok(q, net): continue
                from shapely.ops import nearest_points
                r = nearest_points(ogeom, Point(q))[0]
                r = (r.x, r.y)
                if math.dist(q, r) < 0.05:
                    _new_via(b, G, q, v.GetNet(), net); ok = True
                else:
                    w = _stub_width(G, Lb, q, r, net, wn)
                    if w is None: continue
                    _new_via(b, G, q, v.GetNet(), net)
                    _new_track(b, G, Lb, q, r, w, v.GetNet(), net); ok = True
                out.append((p, q, round(math.dist(q, r), 2)))
                break
            if ok: break
    if verbose and out:
        print('  parallel bridges: ' + ', '.join(f'({p[0]:.1f},{p[1]:.1f})→via ({q[0]:.1f},{q[1]:.1f}) + segment {l} mm'
                                                    for p, q, l in out))
    return out

def upsize_vias(b, G, vias, sizes=((0.8, 0.5), (0.7, 0.4), (0.65, 0.35)), verbose=True):
    """Enlarge the given vias (those with no room for a parallel one) if the larger size fits."""
    out = []
    for v in vias:
        net = v.GetNetname(); q = _xy(v.GetPosition())
        own = Point(q).buffer(v.GetDrillValue() / MM / 2, 24)
        for d, dr in sizes:
            if G.via_ok(q, net, d, dr, ignore=own):
                v.SetWidth(int(round(d * MM))); v.SetDrill(int(round(dr * MM)))
                G.add_via_geom(q, net, d, dr)
                out.append((q, d, dr)); break
    if verbose and out:
        print('  enlarged vias: ' + ', '.join(f'({x:.1f},{y:.1f}) {d}/{dr}' for (x, y), d, dr in out))
    return out

def main_vias(b, net, srcs, snks):
    """Vias of 'net' on the main current path (shortest path in the net's copper graph
    between the pads of the srcs parts and those of the snks parts)."""
    from collections import deque
    items = []                                      # (type, object, {layer: geometry})
    for fp in b.GetFootprints():
        for pad in fp.Pads():
            if _norm(pad.GetNetname()) != net: continue
            g = {}
            for L in (pcbnew.F_Cu, pcbnew.B_Cu):
                if pad.IsOnLayer(L):
                    sps = pcbnew.SHAPE_POLY_SET(); pad.TransformShapeToPolygon(sps, L, 0, 5000, pcbnew.ERROR_INSIDE)
                    g[L] = _sps_to_shapely(sps).buffer(0.005)
            items.append(('pad', fp.GetReference(), g))
    for t in b.GetTracks():
        if _norm(t.GetNetname()) != net: continue
        if t.GetClass() == 'PCB_VIA':
            d = Point(_xy(t.GetPosition())).buffer(t.GetWidth(pcbnew.F_Cu) / MM / 2, 16)
            items.append(('via', t, {pcbnew.F_Cu: d, pcbnew.B_Cu: d}))
        elif t.GetClass() == 'PCB_TRACK':
            g = LineString([_xy(t.GetStart()), _xy(t.GetEnd())]).buffer(t.GetWidth() / MM / 2 + 0.005, 8)
            items.append(('track', t, {t.GetLayer(): g}))
    n = len(items)
    adj = [[] for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            gi, gj = items[i][2], items[j][2]
            if any(L in gj and gi[L].intersects(gj[L]) for L in gi):
                adj[i].append(j); adj[j].append(i)
    def bfs(src):
        prev = {src: None}; dq = deque([src])
        while dq:
            u = dq.popleft()
            for v in adj[u]:
                if v not in prev:
                    prev[v] = u; dq.append(v)
        return prev
    out = set()
    S = [i for i, it in enumerate(items) if it[0] == 'pad' and it[1] in srcs]
    T = [i for i, it in enumerate(items) if it[0] == 'pad' and it[1] in snks]
    for s in S:
        prev = bfs(s)
        for t in T:
            if t not in prev: continue
            u = t
            while u is not None:
                if items[u][0] == 'via':
                    out.add(id(items[u][1]))
                    out.add((round(_xy(items[u][1].GetPosition())[0], 3), round(_xy(items[u][1].GetPosition())[1], 3)))
                u = prev[u]
    return out

def reinforce(b, widths, paths, verbose=True):
    """paths: {net: (source refs, sink refs)} of the high-current nets; only the vias on their main path are
    reinforced (not the sense or protection branches, which carry almost no current)."""
    G = Geo(b)
    widen(b, G, widths, verbose)
    keys = set()
    for net, (srcs, snks) in paths.items():
        keys |= {k for k in main_vias(b, net, set(srcs), set(snks)) if isinstance(k, tuple)}
    added = add_parallel_vias(b, G, set(paths), widths, verbose=verbose, only=keys)
    lonely = {(round(p[0], 3), round(p[1], 3)) for lst in added.values() for p, k in lst if k == 0}
    vias = [t for t in b.GetTracks() if t.GetClass() == 'PCB_VIA'
            and (round(_xy(t.GetPosition())[0], 3), round(_xy(t.GetPosition())[1], 3)) in lonely]
    bridged = bridge_vias(b, G, vias, widths, verbose=verbose)
    done = {(round(p[0], 3), round(p[1], 3)) for p, q, l in bridged}
    upsize_vias(b, G, [v for v in vias if (round(_xy(v.GetPosition())[0], 3), round(_xy(v.GetPosition())[1], 3)) not in done],
                verbose=verbose)
    # second widening pass: the new segments may have changed the surroundings
    widen(b, Geo(b), widths, verbose=False)
