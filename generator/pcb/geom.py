"""Board geometry with shapely: courtyards and pads in board coordinates, placement checks."""
import math
from shapely.geometry import Polygon, Point, LineString, box
from shapely.ops import unary_union, polygonize
from shapely import affinity
import fpdb
from sx import kid, kids
from board import rot

def _arc_pts(s, m, e, n=16):
    (x1, y1), (x2, y2), (x3, y3) = s, m, e
    d = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
    if abs(d) < 1e-9: return [s, e]
    ux = ((x1 * x1 + y1 * y1) * (y2 - y3) + (x2 * x2 + y2 * y2) * (y3 - y1) + (x3 * x3 + y3 * y3) * (y1 - y2)) / d
    uy = ((x1 * x1 + y1 * y1) * (x3 - x2) + (x2 * x2 + y2 * y2) * (x1 - x3) + (x3 * x3 + y3 * y3) * (x2 - x1)) / d
    r = math.hypot(x1 - ux, y1 - uy)
    a1 = math.atan2(y1 - uy, x1 - ux); a2 = math.atan2(y2 - uy, x2 - ux); a3 = math.atan2(y3 - uy, x3 - ux)
    def norm(a): return a % (2 * math.pi)
    # direction that passes through the midpoint
    ccw = norm(a2 - a1) < norm(a3 - a1)
    span = norm(a3 - a1) if ccw else -norm(a1 - a3)
    return [(ux + r * math.cos(a1 + span * k / n), uy + r * math.sin(a1 + span * k / n)) for k in range(n + 1)]

def courtyard_local(fp):
    """Courtyard polygon in local coordinates (F side)."""
    lines = []
    polys = []
    for g in fp:
        if not isinstance(g, list) or not g or g[0] not in ('fp_line', 'fp_rect', 'fp_poly', 'fp_circle', 'fp_arc'): continue
        lay = kid(g, 'layer')
        if not lay or not str(lay[1]).endswith('CrtYd'): continue
        if g[0] == 'fp_line':
            s, e = kid(g, 'start'), kid(g, 'end'); lines.append(LineString([(float(s[1]), float(s[2])), (float(e[1]), float(e[2]))]))
        elif g[0] == 'fp_arc':
            s, m, e = kid(g, 'start'), kid(g, 'mid'), kid(g, 'end')
            lines.append(LineString(_arc_pts((float(s[1]), float(s[2])), (float(m[1]), float(m[2])), (float(e[1]), float(e[2])))))
        elif g[0] == 'fp_rect':
            s, e = kid(g, 'start'), kid(g, 'end'); polys.append(box(min(float(s[1]), float(e[1])), min(float(s[2]), float(e[2])),
                                                                     max(float(s[1]), float(e[1])), max(float(s[2]), float(e[2]))))
        elif g[0] == 'fp_poly':
            pts = [(float(xy[1]), float(xy[2])) for xy in kids(kid(g, 'pts'), 'xy')]
            polys.append(Polygon(pts))
        elif g[0] == 'fp_circle':
            c, e = kid(g, 'center'), kid(g, 'end'); r = math.hypot(float(e[1]) - float(c[1]), float(e[2]) - float(c[2]))
            polys.append(Point(float(c[1]), float(c[2])).buffer(r, 32))
    if lines:
        merged = unary_union(lines)
        ps = list(polygonize(merged))
        if ps: polys.append(unary_union(ps))
    if not polys:
        x0, y0, x1, y1 = fpdb.courtyard(fp)
        return box(x0, y0, x1, y1)
    return unary_union(polys)

_cy_cache = {}
def courtyard(pl):
    """Courtyard of a placed footprint, in board coordinates."""
    if pl.libid not in _cy_cache:
        _cy_cache[pl.libid] = courtyard_local(fpdb.load(pl.libid))
    g = _cy_cache[pl.libid]
    if pl.side == 'B':
        g = affinity.scale(g, 1, -1, origin=(0, 0))
    # KiCad rot(): (x c + y s, -x s + y c) = rotation by -ang in math axes with y pointing down → shapely rotate(-ang)
    g = affinity.rotate(g, -pl.angle, origin=(0, 0))
    return affinity.translate(g, pl.x, pl.y)

def custom_local(p, side='F'):
    """Custom pad (anchor rect + primitive polygons) in the pad's own frame, mirrored in y on the bottom side."""
    w, h = p['w'], p['h']
    parts = [box(-w / 2, -h / 2, w / 2, h / 2)] + [Polygon(q).buffer(0) for q in p['prims'] if len(q) >= 3]
    g = unary_union(parts)
    if side == 'B':
        g = affinity.scale(g, 1.0, -1.0, origin=(0, 0))
    return g

def custom_abs(pl, p):
    ly = -p['y'] if pl.side == 'B' else p['y']
    dx, dy = rot(p['x'], ly, pl.angle)
    ang = pl.angle + (-p['rot'] if pl.side == 'B' else p['rot'])
    g = affinity.rotate(custom_local(p, pl.side), -ang, origin=(0, 0))
    return affinity.translate(g, pl.x + dx, pl.y + dy)

def pad_shapes(pl, clearance=0.0):
    """List of (num, net, layers, polygon) of the pads in board coordinates."""
    out = []
    for p in pl.pads:
        ly = -p['y'] if pl.side == 'B' else p['y']
        dx, dy = rot(p['x'], ly, pl.angle)
        ang = pl.angle + (-p['rot'] if pl.side == 'B' else p['rot'])
        w, h = p['w'], p['h']
        if p['shape'] in ('circle',):
            g = Point(0, 0).buffer(w / 2, 16)
        elif p['shape'] in ('oval',):
            r = min(w, h) / 2
            if w >= h: g = LineString([(-(w / 2 - r), 0), (w / 2 - r, 0)]).buffer(r, 8)
            else: g = LineString([(0, -(h / 2 - r)), (0, h / 2 - r)]).buffer(r, 8)
        else:
            rr = p.get('rratio', 0.0) * min(w, h)
            if rr > 1e-6:
                g = box(-w / 2 + rr, -h / 2 + rr, w / 2 - rr, h / 2 - rr).buffer(rr, 8)
            else:
                g = box(-w / 2, -h / 2, w / 2, h / 2)
        if p.get('prims'):
            g = custom_local(p, pl.side)
        g = affinity.rotate(g, -ang, origin=(0, 0))
        g = affinity.translate(g, pl.x + dx, pl.y + dy)
        if clearance: g = g.buffer(clearance, 8)
        layers = []
        for l in p['layers']:
            if l == '*.Cu': layers += ['F.Cu', 'In1.Cu', 'In2.Cu', 'B.Cu']
            elif l in ('F.Cu', 'B.Cu'):
                layers.append(l if pl.side == 'F' else ('B.Cu' if l == 'F.Cu' else 'F.Cu'))
        net = pl.comp.pins.get(p['num'], ('', '', ''))[0] if p['num'] else ''
        drill = p['drill']
        dsz = 0.0
        if drill is not None:
            vals = [v for v in drill[1:] if isinstance(v, (int, float))]
            dsz = max(vals) if vals else 0.0
        out.append(dict(num=p['num'], net=net, layers=layers, poly=g, kind=p['kind'], drill=dsz,
                        center=(pl.x + dx, pl.y + dy)))
    return out

def is_tht(pl):
    return any(p['kind'] in ('thru_hole', 'np_thru_hole') for p in pl.pads)

def check_placement(board, board_poly, keepouts, allow_outside=(), verbose=True):
    """Check courtyard overlaps (per side), courtyards outside the board and keepout zones.
    keepouts: list of (name, polygon, sides('F','B','FB'), exempt refs)."""
    issues = []
    cys = {r: courtyard(pl) for r, pl in board.placed.items()}
    refs = sorted(cys)
    for i, a in enumerate(refs):
        pa = board.placed[a]
        for b in refs[i + 1:]:
            pb = board.placed[b]
            same = pa.side == pb.side
            tht_cross = (not same) and (is_tht(pa) or is_tht(pb))
            if not (same or tht_cross): continue
            ga, gb = cys[a], cys[b]
            if not tht_cross:
                inter = ga.intersection(gb).area
                if inter > 1e-3: issues.append(f'overlap {a}/{b}: {inter:.2f} mm²')
            else:
                # THT pins go through the board: only THT pads count against the other side's courtyard
                tht, other = (pa, b) if is_tht(pa) else (pb, a)
                g_other = cys[other]
                for ps in pad_shapes(tht):
                    if ps['kind'] in ('thru_hole', 'np_thru_hole') and ps['poly'].buffer(0.3).intersects(g_other):
                        issues.append(f'THT pin of {tht.comp.ref} under {other} (other side)'); break
    for r, g in cys.items():
        if r in allow_outside: continue
        out = g.difference(board_poly).area
        if out > 1e-3: issues.append(f'{r} outside the board: {out:.2f} mm²')
    for name, kp, sides, exempt in keepouts:
        for r, g in cys.items():
            if r in exempt: continue
            pl = board.placed[r]
            if pl.side in sides:
                a = g.intersection(kp).area
                if a > 1e-3: issues.append(f'{r} in keepout "{name}": {a:.2f} mm²')
            elif is_tht(pl):
                # THT part on the other side: its through-hole pads count (solder joints on the zone's side)
                for ps in pad_shapes(pl):
                    if ps['kind'] in ('thru_hole', 'np_thru_hole') and ps['poly'].buffer(0.5).intersects(kp):
                        issues.append(f'THT pin of {r} in keepout "{name}" (other side)'); break
    if verbose:
        print(f'{len(issues)} placement issues')
        for s in issues: print('  -', s)
    return issues
