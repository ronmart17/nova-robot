"""Bridge between the board (Board + placed footprints) and the router: pads → analytic shapes, edges and keepout zones."""
import math
import numpy as np
from shapely.geometry import Polygon, Point
from shapely import vectorized
import geom
from router import Router, Shape, LAYERS, HARD
from board import rot

def pad_shape(pl, p, net_id):
    ly = -p['y'] if pl.side == 'B' else p['y']
    dx, dy = rot(p['x'], ly, pl.angle)
    cx, cy = pl.x + dx, pl.y + dy
    ang = (pl.angle + (-p['rot'] if pl.side == 'B' else p['rot'])) % 360
    w, h = p['w'], p['h']
    layers = []
    for l in p['layers']:
        if l == '*.Cu': layers += ['F.Cu', 'B.Cu']
        elif l in ('F.Cu', 'B.Cu'):
            layers.append(l if pl.side == 'F' else ('B.Cu' if l == 'F.Cu' else 'F.Cu'))
    layers = tuple(sorted(set(layers), key=LAYERS.index))
    if p['shape'] == 'circle':
        return Shape('circle', (cx, cy, w / 2), net_id, layers), (cx, cy)
    if p['shape'] == 'oval':
        r = min(w, h) / 2
        if w >= h: a, b = rot(-(w / 2 - r), 0, ang), rot(w / 2 - r, 0, ang)
        else: a, b = rot(0, -(h / 2 - r), ang), rot(0, h / 2 - r, ang)
        return Shape('seg', (cx + a[0], cy + a[1], cx + b[0], cy + b[1], 2 * r), net_id, layers), (cx, cy)
    if p.get('prims'):
        from geom import custom_abs
        return Shape('poly', custom_abs(pl, p), net_id, layers), (cx, cy)
    r = p.get('rratio', 0.0) * min(w, h)
    return Shape('rect', (cx, cy, w / 2, h / 2, ang, r), net_id, layers), (cx, cy)

def build_router(b, usable, hard_zones, pitch=0.1, clearance=0.15, width=0.15, edge_clear=0.35, hole_clear=0.25):
    """usable: board polygon (absolute, without slots). hard_zones: list of (polygon, layers) with no copper."""
    x0, y0, x1, y1 = usable.bounds
    R = Router(x0 - 1, y0 - 1, x1 + 1, y1 + 1, pitch, clearance, width)
    R.pads = {}       # (ref, num) -> list of (Shape, center)
    R.netpads = {}    # net -> list of (ref, num, Shape, center)
    # board edge: cells outside (board − edge clearance − half a track)
    inner = usable.buffer(-(edge_clear + width / 2 + R.margin))
    X, Y = np.meshgrid(R.xs, R.ys)
    inside = vectorized.contains(inner, X, Y)
    R.own[0][~inside] = HARD; R.own[1][~inside] = HARD
    R.novia[~vectorized.contains(usable.buffer(-(edge_clear + 0.3)), X, Y)] = 1
    # no-copper zones
    for poly, lays in hard_zones:
        m = vectorized.contains(poly.buffer(width / 2 + R.margin), X, Y)
        for L, ln in enumerate(LAYERS):
            if ln in lays: R.own[L][m] = HARD
        # a via goes through all layers: forbidden if its copper enters the zone on any layer
        mv = vectorized.contains(poly.buffer(R.via_d / 2 + 0.05), X, Y)
        R.novia[mv] = 1
    del X, Y, inside
    # pads
    for ref, pl in b.placed.items():
        for p in pl.pads:
            net = pl.comp.pins.get(p['num'], ('', '', ''))[0] if p['num'] else ''
            if p['kind'] == 'np_thru_hole':
                d = 0.0
                if p['drill'] is not None:
                    vals = [v for v in p['drill'][1:] if isinstance(v, (int, float))]
                    d = max(vals) if vals else p['w']
                sh = Shape('circle', (pl.x + rot(p['x'], -p['y'] if pl.side == 'B' else p['y'], pl.angle)[0],
                                      pl.y + rot(p['x'], -p['y'] if pl.side == 'B' else p['y'], pl.angle)[1],
                                      max(d, p['w']) / 2 + hole_clear - R.clear), 0, LAYERS)
                R.add_shape(sh, hard=True)
                R.add_novia(sh, 0.3)
                R.add_hole(sh.p[0], sh.p[1], max(d, 0.0) / 2)
                continue
            n = R.nid(net) if net and not net.startswith('unconnected') else R.nid(f'__nc_{ref}_{p["num"]}')
            sh, c = pad_shape(pl, p, n)
            if not sh.layers: continue
            R.add_shape(sh)
            if p['kind'] == 'thru_hole' and p['drill'] is not None:
                vals = [v for v in p['drill'][1:] if isinstance(v, (int, float))]
                if vals: R.add_hole(c[0], c[1], max(vals) / 2)
            if p['kind'] == 'smd':
                R.add_novia(sh, 0.15)          # no vias in pads or touching them
            R.pads.setdefault((ref, p['num']), []).append((sh, c))
            if net and not net.startswith('unconnected'):
                R.netpads.setdefault(net, []).append((ref, p['num'], sh, c))
    return R
