"""Main board routing: fixed power routes, plane fan-outs, wide power nets and signals."""
import os, sys, time, math, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from shapely.geometry import Polygon, box, Point
from shapely.ops import unary_union
import main_pcb as M, rgrid, fixed, fixed_b
from router import LAYERS, Shape

def A(x, y): return (M.CX + x, M.CY + y)
def RA(x0, y0, x1, y1): return box(M.CX + min(x0, x1), M.CY + min(y0, y1), M.CX + max(x0, x1), M.CY + max(y0, y1))

def copper_keepouts(keep):
    """No-copper zones for the router: antenna (all layers), motors/brackets/caster (B.Cu), screw heads (F and B)."""
    hz = []
    for name, kp, sides, ex in keep:
        if name.startswith('antenna'):
            hz.append((kp, ('F.Cu', 'B.Cu', 'In1.Cu', 'In2.Cu')))
        elif name in ('N20 motor and brackets', 'caster'):
            hz.append((kp, ('B.Cu',)))
        elif name.startswith('screw head'):
            hz.append((kp, ('F.Cu', 'B.Cu')))
    return hz

def setup():
    b, usable, keep, issues = M.build(None, check=False)
    hz = copper_keepouts(keep)
    # fiducials: 1.6 mm copper-free around them (2 mm mask opening)
    for ref in ('FID1', 'FID2', 'FID3'):
        pl = b.placed[ref]
        hz.append((Point(pl.x, pl.y).buffer(1.6).difference(Point(pl.x, pl.y).buffer(0.0)), ('F.Cu',) if pl.side == 'F' else ('B.Cu',)))
    # under the ESP32 body: no F.Cu tracks and no vias (except the thermal pad vias, which belong to the footprint)
    u = b.placed['U401']
    body = box(u.x - 12.75, u.y - 9.0, u.x + 12.75, u.y + 9.0).buffer(-1.4, join_style=2)
    hz.append((body, ('F.Cu',)))
    R = rgrid.build_router(b, usable, hz)
    return b, usable, keep, R


if __name__ == '__main__':
    t = time.time()
    b, usable, keep, R = setup()
    print('grid', round(time.time() - t, 1), 's')
    F = fixed_b.route_fixed(R, b)
    print('fixed routes', sum(len(v) for v in R.routes.values()))
    import pickle
    pickle.dump({'routes': R.routes}, open(os.path.join(M.SCR, 'routes_fixed.pkl'), 'wb'))

def transfer(R, b):
    """Copy the router's routes to the board (tracks and vias)."""
    b.segments.clear(); b.vias.clear(); b.locked.clear()
    for net, items in R.routes.items():
        if net.startswith('__'): continue
        for it in items:
            if it[0] == 'seg':
                _, layer, a, c, w, tag = it
                b.track(net, [a, c], w, layer, locked=(tag == 'fixed'))
            else:
                _, p, d, tag = it
                b.via(net, p, d, 0.3)

def render(b, names, keep, prefix='r'):
    import views
    return views.views(b, names=names, keep=keep, prefix=prefix, rats=True)

# ------------------------------------------------------------------ planes
# In2 split: VSYS region (robot frame rectangles X0, Y0, X1, Y1), the rest of In2 is +3V3
VSYS_RECTS_ROBOT = [(-27.0, -64.0, 64.0, -31.0),     # rear band: charger, protector, 3.3 V buck input, TB6612 feed
                    (-11.0, -31.0, 11.0, -19.0),     # under the pack: TB6612 (bottom side)
                    (36.5, -31.0, 48.0, 30.6)]       # right strip up to the Pi buck input capacitors (via row at Y 29.15)
# the 3.3 V buck output (X < −27) and the Pi-buck EN/PG pull-ups (X < 36.5) stay on the +3V3 plane
def RB(X0, Y0, X1, Y1):
    return RA(X0, -Y0, X1, -Y1)

def planes_def(usable, keep, edge=0.35):
    ant = unary_union([kp for name, kp, s, ex in keep if name.startswith('antenna')])
    board = usable.buffer(-edge)
    gnd = board.difference(ant)
    vs = unary_union([RB(*r) for r in VSYS_RECTS_ROBOT]).intersection(board).difference(ant)
    p33 = board.difference(vs.buffer(0.5)).difference(ant)
    return {'GND': [('In1.Cu', gnd)], 'VSYS': [('In2.Cu', vs)], '+3V3': [('In2.Cu', p33)]}

def region_mask(R, poly, shrink=0.45):
    from shapely import vectorized
    X, Y = np.meshgrid(R.xs, R.ys)
    return vectorized.contains(poly.buffer(-shrink), X, Y).astype(np.uint8)

# ------------------------------------------------------------------ plane fan-outs
def fanout_net(R, b, net, planes, region, max_d=3.0, via_d=0.55, verbose=False, open_extra=0.45):
    import conn
    comps = conn.components(b, R, planes).get(net, [])
    poly = planes[net][0][1]
    n_ok = n_fail = 0
    fails = []
    for comp in comps:
        ids = set(comp)
        has_plane = any(i[0] == 'plane' for i in ids)
        if has_plane: continue
        pads = [i for i in ids if i[0] == 'pad']
        if not pads: continue
        # copper cells of the component: its pads
        src = []
        bx0 = by0 = 1e9; bx1 = by1 = -1e9
        for (_, ref, num, k) in pads:
            for sh, c in R.pads.get((ref, num), []):
                lays = [LAYERS.index(l) for l in sh.layers]
                bx0 = min(bx0, sh.bbox[0]); by0 = min(by0, sh.bbox[1]); bx1 = max(bx1, sh.bbox[2]); by1 = max(by1, sh.bbox[3])
                i0, i1, j0, j1 = R._window(sh.bbox, 0.0)
                X, Y = np.meshgrid(R.xs[j0:j1], R.ys[i0:i1])
                from router import dist_field
                m = dist_field(sh, X, Y) <= 1e-6
                ii, jj = np.nonzero(m)
                for L in lays:
                    src += [(L, int(a) + i0, int(c_) + j0) for a, c_ in zip(ii, jj)]
        if not src: continue
        lays_avail = sorted(set(L for L, _, _ in src))
        from scipy import ndimage as ndi
        def tmask(i0, i1, j0, j1, free, viaok, lays_avail=lays_avail, extra=open_extra):
            t = np.zeros_like(free)
            # prefer clear spots: the via with an extra free ring on both layers
            r = int(round(extra / R.P))
            yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
            dk = np.hypot(yy, xx) <= r + 1e-9
            both = (R.own[0, i0:i1, j0:j1] == 0) | (R.own[0, i0:i1, j0:j1] == R.nid(net))
            both &= (R.own[1, i0:i1, j0:j1] == 0) | (R.own[1, i0:i1, j0:j1] == R.nid(net))
            opn = ndi.binary_erosion(both, structure=dk, border_value=0)
            for L in lays_avail:
                t[L] = viaok & free[L] & opn
            if not t.any():
                for L in lays_avail:
                    t[L] = viaok & free[L]
            return t
        path, nexp = R.search(net, src, None, (bx0, by0, bx1, by1), pad=max_d, via_cost=1e6, t45=0.2, t90=0.6,
                              layers_allowed=tuple(lays_avail), tgt_mask=tmask, via_region=region, weight=1.0,
                              max_exp=400000)
        if not path:
            n_fail += 1; fails.append(pads[0][1:3]); continue
        end = path[-1]
        R.path_to_route(net, path, tag='fan')
        R.add_via(net, R.xy(end[1], end[2]), via_d, tag='fan')
        n_ok += 1
    if verbose or n_fail:
        print(f'  fan-out {net}: {n_ok} vias, {n_fail} without a spot {fails[:12]}')
    return fails

# ------------------------------------------------------------------ full flow
PLANE_NETS = ('GND', '+3V3', 'VSYS')
CH = '/USB-C + 12 V dock, BQ25798 charger/'
S3 = '/2S battery, protection, 3V3 and Pi 5 V bucks/'
WIDTHS = {
    # main 5 V / VBAT / B+ / B− / common-drain paths are fixed pours (fixed_b.py); these widths only apply to the
    # remaining branches (servo feed, FB sense, protector sense, test points)
    '+5V': 0.8, 'VBAT': 0.3, S3 + 'BAT-': 0.3,
    CH + 'VBUS_USB': 0.8, CH + 'VDOCK': 0.8, CH + 'CHG_VBUS': 1.0, CH + 'CHG_PMID': 1.0,
    'Net-(Q201-S-Pad1)': 0.8, 'Net-(Q203-S-Pad1)': 0.8, CH + 'CHG_SW1': 1.0, CH + 'CHG_SW2': 1.0,
    '/Motors and encoders/MOT_L+': 0.5, '/Motors and encoders/MOT_L-': 0.5,
    '/Motors and encoders/MOT_R+': 0.5, '/Motors and encoders/MOT_R-': 0.5,
    S3 + 'BAT_BM': 0.25, 'Net-(U303-SW)': 0.6, CH + 'CHG_REGN': 0.3, S3 + 'PWR_EN': 0.2,
}

# high-current paths (final reinforcement in power.py: parallel vias only along the source → sink path)
POWER_PATHS = {CH + 'VBUS_USB': (['J201'], ['Q201']), CH + 'VDOCK': (['J203'], ['Q203'])}

MINW = {'+5V': 0.5, CH + 'VBUS_USB': 0.6, CH + 'VDOCK': 0.6, CH + 'CHG_VBUS': 0.8}

ON_ITERS = None            # optional hook (nr, conflict) after the negotiation, for diagnostics
RESCUE_ROUNDS = None
ITERS = 32
CHECKPOINT = None          # e.g. '/path/ckpt_v{v}.pkl': negotiation state saved every iteration (resumable)

def run(save=True, verbose=True, variant=None, endgame_tries=4):
    """variant: integer that changes the signal routing order (seed) and saves to routes_v<n>.pkl."""
    import autoroute, conn, pickle, random
    t = time.time()
    b, usable, keep, R = setup()
    planes = planes_def(usable, keep)
    F = fixed_b.route_fixed(R, b)
    regions = {net: region_mask(R, planes[net][0][1]) for net in PLANE_NETS}
    if verbose: print(f'fixed routes: {time.time() - t:.0f} s')
    nets = [n for n in R.netpads if n not in PLANE_NETS]
    def hpwl(n):
        ps = [c for _, _, _, c in R.netpads[n]]
        return (max(p[0] for p in ps) - min(p[0] for p in ps)) + (max(p[1] for p in ps) - min(p[1] for p in ps))
    wide = [n for n in nets if n in WIDTHS and WIDTHS[n] >= 0.3]
    rest = [n for n in nets if n not in wide]
    rest = sorted(rest, key=hpwl)
    if variant:
        rng = random.Random(variant)
        rest = sorted(rest, key=lambda n: hpwl(n) * rng.uniform(0.6, 1.4))
    order = list(PLANE_NETS) + sorted(wide, key=lambda n: -WIDTHS[n]) + rest
    LAY = {}
    autoroute.THIN = {CH + 'VBUS_USB': {('U202', '9'), ('R203', '1'), ('U201', '5')},
                      CH + 'VDOCK': {('U202', '8')}}
    nr = autoroute.route_all(R, b, planes, order, WIDTHS, verbose=verbose, layers=LAY, regions=regions, minw={},
                             iters=ITERS, growth=1.3, endgame_tries=endgame_tries, on_iters=ON_ITERS,
                             rescue_rounds=RESCUE_ROUNDS, checkpoint=CHECKPOINT and CHECKPOINT.format(v=variant or 0))
    R, b = nr.R, nr.b
    conn.trim_stubs(b, R, planes, verbose=verbose)
    bad = conn.report(b, R, planes, verbose=verbose)
    if save:
        name = f'routes_v{variant}.pkl' if variant else 'routes.pkl'
        pickle.dump({'routes': R.routes, 'zones': F.zones, 'bad': sorted(bad)}, open(os.path.join(M.SCR, name), 'wb'))
    return b, usable, keep, R, planes, F, bad
