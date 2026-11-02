"""Straightening pass (pcbnew, before power reinforcement and zone fill).

The grid router leaves staircase jogs (0.1 mm grid, A* with congestion). For every chain of track segments of one net
on one layer between two anchors (pad, via, junction, width change or a hand-routed locked track), this pass searches
the octilinear polyline with the fewest segments that reproduces the connection: each hop between two chain points is
either one straight 0/45/90° segment or a diagonal + straight pair. Every new segment is checked with the exact
geometry of power.Geo (clearance 0.15, copper-edge 0.3, hole clearance 0.25, keep-outs). Turns are limited to 90°
and 90° turns cost extra, so 45° bends are preferred. Several passes: a track freed by its neighbour can straighten
in the next pass. KiCad DRC validates the result."""
import math
import pcbnew
from power import Geo, MM, _xy

NM = 1000          # node key resolution: 1 µm


def _key(p):
    return (int(round(p[0] * NM)), int(round(p[1] * NM)))


def _dir(a, c):
    """Octilinear direction index 0..7 of a→c, or None if not octilinear."""
    dx, dy = c[0] - a[0], c[1] - a[1]
    if abs(dx) < 1e-4 and abs(dy) < 1e-4:
        return None
    ang = math.degrees(math.atan2(dy, dx)) % 360
    k = round(ang / 45) % 8
    if abs(((ang - k * 45 + 180) % 360) - 180) > 0.5:
        return None
    return k


def _turn(d1, d2):
    if d1 is None or d2 is None:
        return 0
    t = abs(d1 - d2) % 8
    return min(t, 8 - t)          # in 45° steps


def _candidates(a, c):
    """Octilinear connections a→c: [(points, [dirs])]."""
    dx, dy = c[0] - a[0], c[1] - a[1]
    d = _dir(a, c)
    if d is not None:
        return [([a, c], [d])]
    sx, sy = math.copysign(1, dx), math.copysign(1, dy)
    m = min(abs(dx), abs(dy))
    out = []
    for mid in ((a[0] + sx * m, a[1] + sy * m), (c[0] - sx * m, c[1] - sy * m)):
        d1, d2 = _dir(a, mid), _dir(mid, c)
        if d1 is None or d2 is None:
            continue
        out.append(([a, mid, c], [d1, d2]))
    return out


def _chains(b, G):
    """Chains of unlocked tracks per (net, layer). Returns list of (net, layer, width, [points], [tracks])."""
    tracks = [t for t in b.GetTracks() if t.GetClass() == 'PCB_TRACK' and t.GetLayer() in G.layers]
    by = {}
    for t in tracks:
        by.setdefault((t.GetNetname(), t.GetLayer()), []).append(t)
    vias = {}
    for t in b.GetTracks():
        if t.GetClass() == 'PCB_VIA':
            vias.setdefault(t.GetNetname(), set()).add(_key(_xy(t.GetPosition())))
    pads = {}
    for fp in b.GetFootprints():
        for pad in fp.Pads():
            pads.setdefault(pad.GetNetname(), []).append(pad)
    out = []
    for (net, L), ts in by.items():
        adj = {}
        anchors = set(vias.get(net, ()))
        for t in ts:
            a, c = _key(_xy(t.GetStart())), _key(_xy(t.GetEnd()))
            if t.IsLocked():
                anchors.add(a); anchors.add(c)
                continue
            adj.setdefault(a, []).append((c, t)); adj.setdefault(c, []).append((a, t))
        # pads of the net on this layer
        for pad in pads.get(net, ()):
            if not pad.IsOnLayer(L):
                continue
            for k in adj:
                if pad.HitTest(pcbnew.VECTOR2I(int(k[0] * MM / NM), int(k[1] * MM / NM))):
                    anchors.add(k)
        # endpoints lying in the interior of another segment (T junction) → anchor, and freeze that segment
        frozen = set()
        for t in ts:
            for k in (_key(_xy(t.GetStart())), _key(_xy(t.GetEnd()))):
                for u in ts:
                    if u is t:
                        continue
                    ua, uc = _xy(u.GetStart()), _xy(u.GetEnd())
                    p = (k[0] / NM, k[1] / NM)
                    if _key(ua) == k or _key(uc) == k:
                        continue
                    if _dist_seg(p, ua, uc) < 0.002:
                        anchors.add(k); frozen.add(id(u))
        seen = set()
        for start in list(adj):
            deg = len(adj[start])
            if not (deg != 2 or start in anchors):
                continue
            for nxt, t in adj[start]:
                if id(t) in seen:
                    continue
                pts, trk = [start], []
                cur, tt = start, t
                w = t.GetWidth()
                while True:
                    seen.add(id(tt)); trk.append(tt)
                    a, c = _key(_xy(tt.GetStart())), _key(_xy(tt.GetEnd()))
                    cur = c if a == cur else a
                    pts.append(cur)
                    if len(adj[cur]) != 2 or cur in anchors:
                        break
                    (n1, t1), (n2, t2) = adj[cur]
                    tt = t2 if t1 is tt else t1
                    if id(tt) in seen or tt.GetWidth() != w:
                        break
                ok = all(x.GetWidth() == w for x in trk) and not any(id(x) in frozen for x in trk)
                if len(trk) >= 2 and ok:
                    out.append((net, L, w / MM, [(k[0] / NM, k[1] / NM) for k in pts], trk))
    return out


def _dist_seg(p, a, c):
    ax, ay = a; cx, cy = c
    dx, dy = cx - ax, cy - ay
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return math.dist(p, a)
    t = max(0, min(1, ((p[0] - ax) * dx + (p[1] - ay) * dy) / L2))
    return math.dist(p, (ax + t * dx, ay + t * dy))


def _solve(G, net, L, w, pts):
    """Fewest-segment octilinear polyline through a subsequence of pts (DP with incoming direction state)."""
    n = len(pts)
    cache = {}

    def feasible(i, j):
        if (i, j) not in cache:
            res = []
            for poly, dirs in _candidates(pts[i], pts[j]):
                if all(G.track_ok(L, poly[k], poly[k + 1], w, net) for k in range(len(poly) - 1)):
                    res.append((poly, dirs))
            cache[(i, j)] = res
        return cache[(i, j)]

    INF = float('inf')
    best = {(0, None): (0.0, None)}          # (index, incoming dir) → (cost, back pointer)
    for i in range(n):
        states = [(k, v) for k, v in best.items() if k[0] == i]
        for (ii, din), (cost, _) in states:
            for j in range(n - 1, i, -1):
                if j - i > 60:
                    continue
                for poly, dirs in feasible(i, j):
                    t0 = _turn(din, dirs[0])
                    if t0 > 2:
                        continue
                    tt = [t0] + [_turn(dirs[k], dirs[k + 1]) for k in range(len(dirs) - 1)]
                    c = cost + len(dirs) + 0.35 * sum(1 for x in tt if x == 2) \
                        + 0.001 * sum(math.dist(poly[k], poly[k + 1]) for k in range(len(poly) - 1))
                    key = (j, dirs[-1])
                    if c < best.get(key, (INF,))[0]:
                        best[key] = (c, ((ii, din), poly))
    ends = [(v[0], k) for k, v in best.items() if k[0] == n - 1]
    if not ends:
        return None
    cost, k = min(ends)
    polys = []
    while best[k][1] is not None:
        prev, poly = best[k][1]
        polys.append(poly)
        k = prev
    out = [pts[0]]
    for poly in reversed(polys):
        out += poly[1:]
    # merge collinear runs
    m = [out[0]]
    for p in out[1:]:
        if len(m) >= 2 and _dir(m[-2], m[-1]) == _dir(m[-1], p):
            m[-1] = p
        else:
            m.append(p)
    return m


def _segcount_cost(pts):
    """Same cost metric applied to the existing chain (non-octilinear segments count double)."""
    c = 0.0
    dirs = [_dir(a, b) for a, b in zip(pts, pts[1:])]
    for d in dirs:
        c += 1 if d is not None else 2
    for d1, d2 in zip(dirs, dirs[1:]):
        if _turn(d1, d2) >= 2:
            c += 0.35
    return c


def straighten(b, passes=4, verbose=True):
    total_before = sum(1 for t in b.GetTracks() if t.GetClass() == 'PCB_TRACK')
    for p in range(passes):
        G = Geo(b)
        chains = _chains(b, G)
        changed = 0
        removed = added = 0
        for net, L, w, pts, trk in chains:
            new = _solve(G, net, L, w, pts)
            if new is None or len(new) - 1 >= len(trk):
                continue
            if _segcount_cost(new) >= _segcount_cost(pts) - 1e-9:
                continue
            # reuse existing track objects (fewer new segments than old ones), delete the rest
            for t, (a, c) in zip(trk, zip(new, new[1:])):
                t.SetStart(pcbnew.VECTOR2I(int(round(a[0] * MM)), int(round(a[1] * MM))))
                t.SetEnd(pcbnew.VECTOR2I(int(round(c[0] * MM)), int(round(c[1] * MM))))
                G.add_track_geom(L, a, c, w, net)
            for t in trk[len(new) - 1:]:
                b.Delete(t)
            changed += 1; removed += len(trk); added += len(new) - 1
        if verbose:
            print(f'  straighten pass {p + 1}: {changed} chains, {removed} → {added} segments')
        if not changed:
            break
    total_after = sum(1 for t in b.GetTracks() if t.GetClass() == 'PCB_TRACK')
    if verbose:
        print(f'  straighten: {total_before} → {total_after} track segments')
