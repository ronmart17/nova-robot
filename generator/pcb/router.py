"""Custom grid router (A* with numba): 2 signal layers (F.Cu, B.Cu), 8 directions, vias, bend penalties,
per-net occupancy maps with exact distance to each copper shape, per-net Steiner tree and rip-up/reroute."""
import math, time, heapq
import numpy as np
from numba import njit
from scipy import ndimage

LAYERS = ('F.Cu', 'B.Cu')
FREE, HARD, MULTI = 0, -1, -2

# ------------------------------------------------------------------ analytic shapes
class Shape:
    __slots__ = ('kind', 'p', 'net', 'layers', 'bbox', 'tag')
    def __init__(self, kind, p, net, layers, tag=''):
        self.kind, self.p, self.net, self.layers, self.tag = kind, p, net, layers, tag
        if kind == 'circle':
            cx, cy, r = p; self.bbox = (cx - r, cy - r, cx + r, cy + r)
        elif kind == 'seg':
            x1, y1, x2, y2, w = p; h = w / 2
            self.bbox = (min(x1, x2) - h, min(y1, y2) - h, max(x1, x2) + h, max(y1, y2) + h)
        elif kind == 'rect':       # centre, half-width, half-height, angle (degrees, KiCad direction)[, corner radius]
            cx, cy, hw, hh, a = p[:5]
            ca, sa = abs(math.cos(math.radians(a))), abs(math.sin(math.radians(a)))
            ex, ey = hw * ca + hh * sa, hw * sa + hh * ca
            self.bbox = (cx - ex, cy - ey, cx + ex, cy + ey)
        elif kind == 'poly':       # shapely
            self.bbox = p.bounds
        else:
            raise ValueError(kind)

    def shrunk(self, e):
        """Copy shrunk inwards by e (mm): start/target cells clearly inside the copper."""
        k, p = self.kind, self.p
        if k == 'circle': q = (p[0], p[1], max(p[2] - e, 0.01))
        elif k == 'seg': q = (p[0], p[1], p[2], p[3], max(p[4] - 2 * e, 0.02))
        elif k == 'rect':
            r = p[5] if len(p) > 5 else 0.0
            q = (p[0], p[1], max(p[2] - e, 0.01), max(p[3] - e, 0.01), p[4], max(r - e, 0.0))
        else:
            g = p.buffer(-e)
            q = g if not g.is_empty else p
        return Shape(k, q, self.net, self.layers, self.tag)

def dist_field(shape, X, Y):
    """Distance (mm) from the points X,Y (arrays) to the outer edge of the shape (0 inside)."""
    k, p = shape.kind, shape.p
    if k == 'circle':
        cx, cy, r = p
        return np.maximum(np.hypot(X - cx, Y - cy) - r, 0.0)
    if k == 'seg':
        x1, y1, x2, y2, w = p
        dx, dy = x2 - x1, y2 - y1
        L2 = dx * dx + dy * dy
        if L2 < 1e-12:
            t = np.zeros_like(X)
        else:
            t = np.clip(((X - x1) * dx + (Y - y1) * dy) / L2, 0.0, 1.0)
        return np.maximum(np.hypot(X - (x1 + t * dx), Y - (y1 + t * dy)) - w / 2, 0.0)
    if k == 'rect':
        cx, cy, hw, hh, a = p[:5]
        r = min(p[5], hw, hh) if len(p) > 5 else 0.0
        ar = math.radians(a); c, s = math.cos(ar), math.sin(ar)
        # inverse of KiCad rot(): local = (dx c − dy s, dx s + dy c)
        dx, dy = X - cx, Y - cy
        lx, ly = dx * c - dy * s, dx * s + dy * c
        qx, qy = np.maximum(np.abs(lx) - (hw - r), 0.0), np.maximum(np.abs(ly) - (hh - r), 0.0)
        return np.maximum(np.hypot(qx, qy) - r, 0.0)
    if k == 'poly':
        from shapely import vectorized
        from shapely.geometry import Point
        poly = p
        inside = vectorized.contains(poly, X, Y)
        b = poly.boundary
        import shapely
        d = shapely.distance(shapely.points(X.ravel(), Y.ravel()), b).reshape(X.shape)
        return np.where(inside, 0.0, d)
    raise ValueError(k)

# ------------------------------------------------------------------ A*
DX = np.array([1, 1, 0, -1, -1, -1, 0, 1], np.int64)
DY = np.array([0, 1, 1, 1, 0, -1, -1, -1], np.int64)

@njit(cache=True)
def _astar(cost, viac, src, tgt, ty, tx, via_cost, t45, t90, weight, max_exp):
    """cost: float32[2,H,W] cost of entering the cell (>=1e9 = blocked); viac: float32[H,W] extra via cost
    (>=1e9 = forbidden); src/tgt: uint8[2,H,W]. Returns a list of (layer,i,j) and the number of expansions."""
    H, W = cost.shape[1], cost.shape[2]
    NS = 2 * H * W * 9
    g = np.full(NS, 1e30, np.float32)
    par = np.full(NS, -1, np.int64)
    closed = np.zeros(NS, np.uint8)
    heap = [(0.0, np.int64(0))]
    heap.pop()
    SQ2 = 1.41421356
    BIG = 1e9
    for L in range(2):
        for i in range(H):
            for j in range(W):
                if src[L, i, j] and cost[L, i, j] < BIG:
                    s = ((L * H + i) * W + j) * 9 + 8
                    g[s] = 0.0
                    ddy = abs(i - ty); ddx = abs(j - tx)
                    h = (max(ddx, ddy) - min(ddx, ddy)) + SQ2 * min(ddx, ddy)
                    heapq.heappush(heap, (weight * h, s))
    nexp = 0
    goal = -1
    while len(heap) > 0:
        f, s = heapq.heappop(heap)
        if closed[s]:
            continue
        closed[s] = 1
        nexp += 1
        if nexp > max_exp:
            break
        d = s % 9; c = s // 9
        j = c % W; c2 = c // W; i = c2 % H; L = c2 // H
        if tgt[L, i, j]:
            goal = s
            break
        gs = g[s]
        for k in range(8):
            if d != 8:
                diff = abs(k - d)
                if diff > 4:
                    diff = 8 - diff
                if diff >= 3:
                    continue
                tp = 0.0 if diff == 0 else (t45 if diff == 1 else t90)
            else:
                tp = 0.0
            ni = i + DY[k]; nj = j + DX[k]
            if ni < 0 or nj < 0 or ni >= H or nj >= W:
                continue
            cc = cost[L, ni, nj]
            if cc >= BIG:
                continue
            if k % 2 == 1:
                if cost[L, i, nj] >= BIG or cost[L, ni, j] >= BIG:
                    continue
                step = SQ2
            else:
                step = 1.0
            ns = ((L * H + ni) * W + nj) * 9 + k
            ng = gs + step * cc + tp
            if ng < g[ns]:
                g[ns] = ng; par[ns] = s
                ddy = abs(ni - ty); ddx = abs(nj - tx)
                h = (max(ddx, ddy) - min(ddx, ddy)) + SQ2 * min(ddx, ddy)
                heapq.heappush(heap, (ng + weight * h, ns))
        vc = viac[i, j]
        if vc < BIG:
            L2 = 1 - L
            if cost[L2, i, j] < BIG:
                ns = ((L2 * H + i) * W + j) * 9 + 8
                ng = gs + via_cost + vc
                if ng < g[ns]:
                    g[ns] = ng; par[ns] = s
                    ddy = abs(i - ty); ddx = abs(j - tx)
                    h = (max(ddx, ddy) - min(ddx, ddy)) + SQ2 * min(ddx, ddy)
                    heapq.heappush(heap, (ng + weight * h, ns))
    out = []
    if goal < 0:
        return out, nexp
    s = goal
    while s >= 0:
        c = s // 9
        j = c % W; c2 = c // W; i = c2 % H; L = c2 // H
        out.append((L, i, j))
        s = par[s]
    out.reverse()
    return out, nexp

# ------------------------------------------------------------------ grid
class Router:
    def __init__(self, x0, y0, x1, y1, pitch=0.1, clearance=0.15, width=0.15, via_d=0.55, via_drill=0.3, margin=0.05):
        self.P = pitch
        self.x0, self.y0 = x0, y0
        self.W = int(math.ceil((x1 - x0) / pitch)) + 1
        self.H = int(math.ceil((y1 - y0) / pitch)) + 1
        self.clear, self.width, self.via_d, self.via_drill, self.margin = clearance, width, via_d, via_drill, margin
        self.own = np.zeros((2, self.H, self.W), np.int32)
        self.usage = np.zeros((2, self.H, self.W), np.int16)   # number of autorouted (inflated) tracks per cell
        # maps for via centres: copper inflated by via radius + clearance (exact at the cell centre)
        self.vmargin = 0.02
        self.vown = np.zeros((2, self.H, self.W), np.int32)
        self.vuse = np.zeros((2, self.H, self.W), np.int16)
        # necking of wide tracks next to their pads: base width within ≤ r1, neck (≤ neck_w) within ≤ r2
        self.neck_w, self.neck_r1, self.neck_r2 = 0.4, 0.6, 1.5
        self.lcost = (1.0, 1.15)    # relative cost per layer (F, B)
        self.rshapes = {}          # net id -> autorouted shapes (tag 'route')
        # hole-to-hole spacing (hole_to_hole 0.25 mm): via centres forbidden near other drill holes
        self.hole_clear = 0.25
        self.vhole_fix = np.zeros((self.H, self.W), np.uint8)
        self.vhole = np.zeros((self.H, self.W), np.int16)
        self.hist = np.zeros((2, self.H, self.W), np.float32)  # historical congestion cost
        self.pres_fac = 0.5
        self.novia = np.zeros((self.H, self.W), np.uint8)    # 1 = no via allowed (SMD pads, zones)
        self.shapes = []           # (Shape)
        self.netid = {}; self.netname = {}
        self.routes = {}           # net -> list of ('seg', layer, (x1,y1), (x2,y2), w) / ('via', (x,y))
        self.xs = x0 + np.arange(self.W) * pitch
        self.ys = y0 + np.arange(self.H) * pitch

    # ---------------- utilities
    def nid(self, net):
        if net not in self.netid:
            k = len(self.netid) + 1
            self.netid[net] = k; self.netname[k] = net
        return self.netid[net]

    def cell(self, x, y):
        return int(round((y - self.y0) / self.P)), int(round((x - self.x0) / self.P))

    def xy(self, i, j):
        return (self.x0 + j * self.P, self.y0 + i * self.P)

    def _window(self, bbox, pad):
        x0, y0, x1, y1 = bbox
        j0 = max(0, int(math.floor((x0 - pad - self.x0) / self.P))); j1 = min(self.W, int(math.ceil((x1 + pad - self.x0) / self.P)) + 1)
        i0 = max(0, int(math.floor((y0 - pad - self.y0) / self.P))); i1 = min(self.H, int(math.ceil((y1 + pad - self.y0) / self.P)) + 1)
        return i0, i1, j0, j1

    def infl(self, extra=0.0):
        """Inflation distance for a track of the default width."""
        return self.clear + self.width / 2 + self.margin + extra

    def vinfl(self):
        """Minimum distance from a via centre to another net's copper."""
        return self.via_d / 2 + self.clear + self.vmargin

    def _hole_mask(self, cx, cy, rh):
        r = rh + self.hole_clear + self.via_drill / 2 + 0.02
        i0, i1, j0, j1 = self._window((cx, cy, cx, cy), r + self.P)
        X, Y = np.meshgrid(self.xs[j0:j1], self.ys[i0:i1])
        return (i0, i1, j0, j1), np.hypot(X - cx, Y - cy) <= r

    def add_hole(self, cx, cy, rh, delta=None):
        """Drill hole (of a pad or via) that imposes spacing on new via centres. delta=None → fixed."""
        (i0, i1, j0, j1), m = self._hole_mask(cx, cy, rh)
        if delta is None:
            self.vhole_fix[i0:i1, j0:j1][m] = 1
        else:
            self.vhole[i0:i1, j0:j1][m] += delta

    def wide_extra(self, w):
        """Extra erosion (mm) for a track of width w > base: a safe bound given the grid discretisation
        (real distance ≥ EDT distance + inflation − P·√2) and the loss on diagonal segments."""
        return (w - self.width) / 2 + self.P * math.sqrt(2) - self.margin + 0.012

    # ---------------- shape stamping
    def _stamp(self, shape, D, hard=False):
        Dv = self.vinfl()
        i0, i1, j0, j1 = self._window(shape.bbox, max(D, Dv) + self.P)
        if i0 >= i1 or j0 >= j1: return
        X, Y = np.meshgrid(self.xs[j0:j1], self.ys[i0:i1])
        d = dist_field(shape, X, Y)
        for arr, DD in ((self.own, D), (self.vown, Dv)):
            m = d <= DD
            if not m.any(): continue
            for L, ln in enumerate(LAYERS):
                if ln not in shape.layers: continue
                sub = arr[L, i0:i1, j0:j1]
                if hard:
                    sub[m] = HARD; continue
                cur = sub[m]
                n = shape.net
                sub[m] = np.where(cur == FREE, n, np.where(cur == n, n, np.where(cur == HARD, HARD, MULTI)))

    def _usage_stamp(self, shape, D, delta):
        Dv = self.vinfl()
        i0, i1, j0, j1 = self._window(shape.bbox, max(D, Dv) + self.P)
        if i0 >= i1 or j0 >= j1: return
        X, Y = np.meshgrid(self.xs[j0:j1], self.ys[i0:i1])
        d = dist_field(shape, X, Y)
        m = d <= D; mv = d <= Dv
        for L, ln in enumerate(LAYERS):
            if ln in shape.layers:
                self.usage[L, i0:i1, j0:j1][m] += delta
                self.vuse[L, i0:i1, j0:j1][mv] += delta

    def add_shape(self, shape, hard=False):
        self.shapes.append((shape, hard))
        self._stamp(shape, self.infl(), hard)

    def add_novia(self, shape, D):
        i0, i1, j0, j1 = self._window(shape.bbox, D + self.P)
        X, Y = np.meshgrid(self.xs[j0:j1], self.ys[i0:i1])
        m = dist_field(shape, X, Y) <= D
        self.novia[i0:i1, j0:j1][m] = 1

    def restamp(self, bbox):
        """Recompute the occupancy in a window from all shapes (not used in the normal flow:
        only 'route' routes are ripped up, and they live in usage/vuse)."""
        raise NotImplementedError('restamp: fixed routes are never ripped up')
        D = self.infl()
        i0, i1, j0, j1 = self._window(bbox, D + 2 * self.P)
        self.own[:, i0:i1, j0:j1] = FREE
        wx0, wy0 = self.x0 + j0 * self.P, self.y0 + i0 * self.P
        wx1, wy1 = self.x0 + (j1 - 1) * self.P, self.y0 + (i1 - 1) * self.P
        for sh, hard in self.shapes:
            if sh.tag == 'route': continue
            b = sh.bbox
            if b[2] + D < wx0 or b[0] - D > wx1 or b[3] + D < wy0 or b[1] - D > wy1: continue
            # stamp only inside the window
            ii0, ii1, jj0, jj1 = self._window(sh.bbox, D + self.P)
            ii0, ii1, jj0, jj1 = max(ii0, i0), min(ii1, i1), max(jj0, j0), min(jj1, j1)
            if ii0 >= ii1 or jj0 >= jj1: continue
            X, Y = np.meshgrid(self.xs[jj0:jj1], self.ys[ii0:ii1])
            m = dist_field(sh, X, Y) <= D
            for L, ln in enumerate(LAYERS):
                if ln not in sh.layers: continue
                sub = self.own[L, ii0:ii1, jj0:jj1]
                if hard:
                    sub[m] = HARD; continue
                cur = sub[m]; n = sh.net
                sub[m] = np.where(cur == FREE, n, np.where(cur == n, n, np.where(cur == HARD, HARD, MULTI)))

    def _core_mask(self, n, L, i0, i1, j0, j1):
        """Cells covered by real copper of net n on layer L (pads and tracks), inside the window."""
        m = np.zeros((i1 - i0, j1 - j0), bool)
        X = Y = None
        for sh, hard in self.shapes:
            if hard or sh.net != n or LAYERS[L] not in sh.layers: continue
            b = sh.bbox
            if b[2] < self.xs[j0] or b[0] > self.xs[j1 - 1] or b[3] < self.ys[i0] or b[1] > self.ys[i1 - 1]: continue
            if X is None: X, Y = np.meshgrid(self.xs[j0:j1], self.ys[i0:i1])
            m |= dist_field(sh, X, Y) <= 1e-6
        return m

    def net_cells(self, net, bbox, pad=1.0):
        """List (L,i,j) of cells with real copper of the net (to start a tree from)."""
        n = self.nid(net)
        i0, i1, j0, j1 = self._window(bbox, pad)
        out = []
        for L in (0, 1):
            m = self._core_mask(n, L, i0, i1, j0, j1) & ((self.own[L, i0:i1, j0:j1] == n))
            ii, jj = np.nonzero(m)
            out += [(L, int(a) + i0, int(c) + j0) for a, c in zip(ii, jj)]
        return out

    # ---------------- routes
    def add_track(self, net, layer, a, b, w=None, tag='route'):
        w = w or self.width
        n = self.nid(net)
        sh = Shape('seg', (a[0], a[1], b[0], b[1], w), n, (layer,), tag)
        self.shapes.append((sh, False))
        if tag == 'route':
            self._usage_stamp(sh, self.infl(), +1)
            self.rshapes.setdefault(n, []).append(sh)
        else:
            self._stamp(sh, self.infl())
        self.routes.setdefault(net, []).append(('seg', layer, a, b, w, tag))

    def add_via(self, net, p, d=None, tag='route'):
        d = d or self.via_d
        n = self.nid(net)
        sh = Shape('circle', (p[0], p[1], d / 2), n, LAYERS, tag)
        self.shapes.append((sh, False))
        if tag == 'route':
            self._usage_stamp(sh, self.infl(), +1)
            self.rshapes.setdefault(n, []).append(sh)
            self.add_hole(p[0], p[1], self.via_drill / 2, +1)
        else:
            self._stamp(sh, self.infl())
            self.add_hole(p[0], p[1], self.via_drill / 2)
        self.routes.setdefault(net, []).append(('via', p, d, tag))

    def ripup(self, net, tag='route'):
        n = self.netid.get(net)
        if n is None: return
        removed = [sh for sh, hard in self.shapes if sh.net == n and sh.tag == tag]
        if not removed: return
        self.shapes = [(sh, hard) for sh, hard in self.shapes if not (sh.net == n and sh.tag == tag)]
        self.routes[net] = [r for r in self.routes.get(net, []) if r[-1] != tag]
        if tag == 'route':
            for sh in removed:
                self._usage_stamp(sh, self.infl(), -1)
                if sh.kind == 'circle' and len(sh.layers) == len(LAYERS):
                    self.add_hole(sh.p[0], sh.p[1], self.via_drill / 2, -1)
            self.rshapes.pop(n, None)
            return
        xs0 = min(s.bbox[0] for s in removed); ys0 = min(s.bbox[1] for s in removed)
        xs1 = max(s.bbox[2] for s in removed); ys1 = max(s.bbox[3] for s in removed)
        self.restamp((xs0, ys0, xs1, ys1))

    def remove_route(self, net, shapes, entries):
        """Remove specific autorouted shapes of a net (partial rip-up, e.g. a fan-out)."""
        n = self.nid(net)
        ids = {id(sh) for sh in shapes}
        for sh in shapes:
            self._usage_stamp(sh, self.infl(), -1)
            if sh.kind == 'circle' and len(sh.layers) == len(LAYERS):
                self.add_hole(sh.p[0], sh.p[1], self.via_drill / 2, -1)
        self.shapes = [(sh, h) for sh, h in self.shapes if id(sh) not in ids]
        self.rshapes[n] = [sh for sh in self.rshapes.get(n, []) if id(sh) not in ids]
        eids = {id(e) for e in entries}
        self.routes[net] = [e for e in self.routes.get(net, []) if id(e) not in eids]

    def own_usage(self, n, i0, i1, j0, j1, via=False):
        """Contribution of net n's autorouted tracks to 'usage' (or to 'vuse' if via) in the window."""
        u = np.zeros((2, i1 - i0, j1 - j0), np.int16)
        D = self.vinfl() if via else self.infl()
        X = Y = None
        for sh in self.rshapes.get(n, ()):
            b = sh.bbox
            if b[2] + D < self.xs[j0] or b[0] - D > self.xs[j1 - 1] or b[3] + D < self.ys[i0] or b[1] - D > self.ys[i1 - 1]: continue
            if X is None: X, Y = np.meshgrid(self.xs[j0:j1], self.ys[i0:i1])
            m = dist_field(sh, X, Y) <= D
            for L, ln in enumerate(LAYERS):
                if ln in sh.layers: u[L][m] += 1
        return u

    # ---------------- search
    def search(self, net, src_cells, tgt_shapes, bbox, pad=6.0, via_cost=30.0, t45=0.4, t90=2.0, lcost=None,
               weight=1.25, max_exp=4_000_000, layers_allowed=(0, 1), w=None, tgt_mask=None, via_region=None,
               soft=True, soft_set=None):
        """A* with costs. Hard: other nets' pads/fixed routes, edges and zones. Soft (soft=True): other nets'
        autorouted tracks with cost pres_fac·usage + history (PathFinder); soft=False treats them as hard."""
        n = self.nid(net)
        w = w or self.width
        lcost = lcost or self.lcost
        i0, i1, j0, j1 = self._window(bbox, pad)
        H, W = i1 - i0, j1 - j0
        own = self.own[:, i0:i1, j0:j1]
        free = ((own == FREE) | (own == n)).astype(np.uint8)
        use = self.usage[:, i0:i1, j0:j1].astype(np.int32) - self.own_usage(n, i0, i1, j0, j1)
        use = np.maximum(use, 0)
        # local negotiation: only the soft_set nets are soft; all other autorouted tracks are hard
        use_hard = None
        if soft_set:
            us = np.zeros_like(use)
            for m in soft_set:
                if m != n: us += self.own_usage(m, i0, i1, j0, j1)
            use_hard = np.maximum(use - us, 0)
            use = np.minimum(use, us)
        self.last_cls = None
        if w > self.width + 1e-6:
            # per-cell classes: 2 = requested width; 1 = neck (wn) within ≤ r2 of own copper; 0 = base width within ≤ r1
            wn = min(w, self.neck_w)
            core = np.zeros((2, H, W), bool)
            for L in (0, 1):
                core[L] = self._core_mask(n, L, i0, i1, j0, j1)
            def disk(r):
                rr = int(math.ceil(r / self.P))
                yy, xx = np.mgrid[-rr:rr + 1, -rr:rr + 1]
                return np.hypot(yy, xx) * self.P <= r + 1e-9
            d1, d2 = disk(self.neck_r1), disk(self.neck_r2)
            fb = free.astype(bool)
            ew = self.wide_extra(w); dkw = disk(ew)
            cls = np.full((2, H, W), -1, np.int8)
            use_c = use.copy()
            uh_c = use_hard.copy() if use_hard is not None else None
            for L in (0, 1):
                near1 = ndimage.binary_dilation(core[L], structure=d1)
                near2 = ndimage.binary_dilation(core[L], structure=d2)
                er_w = ndimage.binary_erosion(fb[L], structure=dkw, border_value=0)
                use_w = ndimage.maximum_filter(use[L], footprint=dkw)
                uh_w = ndimage.maximum_filter(use_hard[L], footprint=dkw) if use_hard is not None else None
                if wn > self.width + 1e-6:
                    dkn = disk(self.wide_extra(wn))
                    er_n = ndimage.binary_erosion(fb[L], structure=dkn, border_value=0)
                    use_n = ndimage.maximum_filter(use[L], footprint=dkn)
                    uh_n = ndimage.maximum_filter(use_hard[L], footprint=dkn) if use_hard is not None else None
                else:
                    er_n, use_n = fb[L], use[L]
                    uh_n = use_hard[L] if use_hard is not None else None
                c = cls[L]
                c[near1 & fb[L]] = 0
                c[near2 & er_n] = 1
                c[er_w] = 2
                use_c[L] = np.where(c == 2, use_w, np.where(c == 1, use_n, use[L]))
                if uh_c is not None:
                    uh_c[L] = np.where(c == 2, uh_w, np.where(c == 1, uh_n, use_hard[L]))
                free[L] = (c >= 0).astype(np.uint8)
            use = use_c
            use_hard = uh_c
            self.last_cls = (i0, j0, cls, wn)
        free_all = free.copy()
        for L in (0, 1):
            if L not in layers_allowed: free[L] = 0
        BIG = np.float32(1e9)
        cost = np.full((2, H, W), BIG, np.float32)
        for L in (0, 1):
            if soft:
                c = lcost[L] * (1.0 + self.hist[L, i0:i1, j0:j1] + self.pres_fac * use[L])
                if use_hard is not None:
                    c = np.where(use_hard[L] > 0, BIG, c)
            else:
                c = np.where(use[L] > 0, BIG, np.float32(lcost[L]) * (1.0 + self.hist[L, i0:i1, j0:j1]))
            cost[L] = np.where(free[L] == 1, c, BIG)
        # vias: exact distance (EDT) to hard obstacles using the base map (independent of track width)
        viaok = self.via_ok(n, i0, i1, j0, j1)
        if via_region is not None:
            viaok &= via_region[i0:i1, j0:j1]
        viaok_t = viaok.copy()
        if not (0 in layers_allowed and 1 in layers_allowed): viaok[:] = 0
        vu = np.maximum(self.vuse[:, i0:i1, j0:j1].astype(np.int32) - self.own_usage(n, i0, i1, j0, j1, via=True), 0)
        vu_hard = None
        if soft_set:
            vs = np.zeros_like(vu)
            for m in soft_set:
                if m != n: vs += self.own_usage(m, i0, i1, j0, j1, via=True)
            vu_hard = np.maximum(vu - vs, 0).max(axis=0)
            vu = np.minimum(vu, vs)
        vu = vu.max(axis=0)
        if soft:
            viac = np.where(viaok == 1, (self.pres_fac * vu * 3.0).astype(np.float32), BIG).astype(np.float32)
            if vu_hard is not None:
                viac = np.where(vu_hard > 0, BIG, viac).astype(np.float32)
        else:
            viac = np.where((viaok == 1) & (vu == 0), np.float32(0.0), BIG).astype(np.float32)
        src = np.zeros((2, H, W), np.uint8)
        for (L, i, j) in src_cells:
            if i0 <= i < i1 and j0 <= j < j1: src[L, i - i0, j - j0] = 1
        X, Y = np.meshgrid(self.xs[j0:j1], self.ys[i0:i1])
        if tgt_mask is not None:
            tgt = tgt_mask(i0, i1, j0, j1, free, viaok_t)
            ys_, xs_ = np.nonzero(tgt.max(axis=0))
            if len(ys_) == 0 or not src.any(): return None, 0
            ti, tj = int(ys_.mean()) + i0, int(xs_.mean()) + j0
        else:
            tgt = np.zeros((2, H, W), np.uint8)
            cx = cy = 0.0; cnt = 0
            for sh, lays in tgt_shapes:
                m = dist_field(sh.shrunk(0.02), X, Y) <= 1e-6
                for L in lays:
                    tgt[L][m & (free[L] == 1)] = 1
                bx = (sh.bbox[0] + sh.bbox[2]) / 2; by = (sh.bbox[1] + sh.bbox[3]) / 2
                cx += bx; cy += by; cnt += 1
            if not tgt.any() or not src.any():
                return None, 0
            ti, tj = self.cell(cx / cnt, cy / cnt)
        path, nexp = _astar(cost, viac, src, tgt, ti - i0, tj - j0, via_cost, t45, t90, weight, max_exp)
        if not path:
            return None, nexp
        return [(L, i + i0, j + j0) for (L, i, j) in path], nexp

    def via_ok(self, n, i0, i1, j0, j1):
        """1 where a via centre of net n keeps clearance to all fixed copper (exact)."""
        v = self.vown[:, i0:i1, j0:j1]
        base = ((v == FREE) | (v == n)).all(axis=0)
        return (base & (self.novia[i0:i1, j0:j1] == 0) & (self.vhole_fix[i0:i1, j0:j1] == 0)
                & (self.vhole[i0:i1, j0:j1] == 0)).astype(np.uint8)

    def via_conflict(self, net, i, j):
        """>0 if a via of 'net' at (i,j) violates the clearance of other nets' autorouted tracks/vias."""
        n = self.nid(net)
        u = self.vuse[:, i:i + 1, j:j + 1].astype(np.int32) - self.own_usage(n, i, i + 1, j, j + 1, via=True)
        return int(u.max())

    def nets_near(self, L, x, y, D, exclude=None):
        """Ids of nets whose autorouted shapes on layer L are within ≤ D (mm) of the point."""
        out = set()
        Xa, Ya = np.array([[x]]), np.array([[y]])
        for n, shs in self.rshapes.items():
            if n == exclude: continue
            for sh in shs:
                if LAYERS[L] not in sh.layers: continue
                b = sh.bbox
                if x < b[0] - D or x > b[2] + D or y < b[1] - D or y > b[3] + D: continue
                if dist_field(sh, Xa, Ya)[0, 0] <= D:
                    out.add(n); break
        return out

    def path_conflict(self, net, path, w=None, cls=None, ret_cells=False):
        """Path cells in conflict with other nets' autorouted tracks (using each cell's width-class radius
        for wide tracks)."""
        if not path: return [] if ret_cells else 0
        n = self.nid(net)
        ii = [p[1] for p in path]; jj = [p[2] for p in path]
        wide = bool(w and w > self.width + 1e-6)
        ex = self.wide_extra(w) if wide else 0.0
        g = int(math.ceil(ex / self.P)) + 2
        i0, i1, j0, j1 = max(0, min(ii) - g), min(self.H, max(ii) + g + 1), max(0, min(jj) - g), min(self.W, max(jj) + g + 1)
        use = np.maximum(self.usage[:, i0:i1, j0:j1].astype(np.int32) - self.own_usage(n, i0, i1, j0, j1), 0)
        maps = {0: use}
        if wide:
            def mf(r):
                rr = int(math.ceil(r / self.P))
                yy, xx = np.mgrid[-rr:rr + 1, -rr:rr + 1]
                dk = (np.hypot(yy, xx) * self.P <= r + 1e-9)
                return np.stack([ndimage.maximum_filter(use[L], footprint=dk) for L in (0, 1)])
            maps[2] = mf(ex)
            wn = cls[3] if cls is not None else w
            maps[1] = mf(self.wide_extra(wn)) if wn > self.width + 1e-6 else use
        cnt = 0; bad = []
        for (L, i, j) in path:
            c = self.cell_cls(cls, (L, i, j)) if wide else 0
            u = maps[c][L, i - i0, j - j0]
            if u > 0:
                cnt += 1
                if ret_cells: bad.append((L, i, j))
        return bad if ret_cells else cnt

    def cell_cls(self, cls, p):
        """Width class of a path cell (2 if there is no map)."""
        if cls is None: return 2
        i0, j0, cm, wn = cls
        L, i, j = p
        a, b = i - i0, j - j0
        if 0 <= a < cm.shape[1] and 0 <= b < cm.shape[2]:
            c = int(cm[L, a, b])
            return c if c >= 0 else 0
        return 2

    def path_to_route(self, net, path, w=None, tag='route', cls=None):
        """Convert a list of cells into tracks (merging collinear segments) and vias. With a wide track, each segment
        between two cells uses the width of the smaller class of its ends (base / neck / requested)."""
        if not path: return
        wide = bool(w and w > self.width + 1e-6 and cls is not None)
        wmap = {0: self.width, 1: (cls[3] if wide else w), 2: w}
        runs = []      # [layer, class, cells]
        for k in range(1, len(path)):
            a, b = path[k - 1], path[k]
            if a[0] != b[0]:
                self.add_via(net, self.xy(b[1], b[2]), tag=tag)
                continue
            c = min(self.cell_cls(cls, a), self.cell_cls(cls, b)) if wide else 2
            if runs and runs[-1][0] == a[0] and runs[-1][1] == c and runs[-1][2][-1] == a:
                runs[-1][2].append(b)
            else:
                runs.append([a[0], c, [a, b]])
        for L, c, cells in runs:
            pts = [cells[0]]
            for k in range(1, len(cells) - 1):
                p0, p1, p2 = pts[-1], cells[k], cells[k + 1]
                d1 = (p1[1] - p0[1], p1[2] - p0[2]); d2 = (p2[1] - p1[1], p2[2] - p1[2])
                if d1[0] * d2[1] - d1[1] * d2[0] != 0 or (d1[0] * d2[0] + d1[1] * d2[1]) < 0:
                    pts.append(p1)
            pts.append(cells[-1])
            ww = wmap[c] if wide else w
            for p, q in zip(pts, pts[1:]):
                self.add_track(net, LAYERS[L], self.xy(p[1], p[2]), self.xy(q[1], q[2]), ww, tag)
