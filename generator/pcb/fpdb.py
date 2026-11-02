"""Footprint loading (.kicad_mod) from the project library (robot:) and the official KiCad 10 libraries."""
import os, copy, functools
from sx import parse, kids, kid
F10 = '/opt/kicad10libs/root/usr/share/kicad/footprints'
ROBOT = '/home/claude/robot/kicad/lib/robot.pretty'

@functools.lru_cache(maxsize=None)
def _load(libid):
    lib, name = libid.split(':')
    p = f'{ROBOT}/{name}.kicad_mod' if lib == 'robot' else f'{F10}/{lib}.pretty/{name}.kicad_mod'
    return parse(open(p, encoding='utf-8').read())

def load(libid):
    return copy.deepcopy(_load(libid))

def _custom_equiv(p, at):
    """'custom' pad: equivalent circle enclosing its primitive (e.g. a ring around a microphone
    port). Returns (x, y, diameter) in footprint coordinates, or None."""
    import math
    pr = kid(p, 'primitives')
    if not pr: return None
    a = float(at[3]) if len(at) > 3 else 0.0
    c, s_ = math.cos(math.radians(a)), math.sin(math.radians(a))
    for g in pr[1:]:
        if isinstance(g, list) and g and g[0] == 'gr_circle':
            ce = kid(g, 'center'); en = kid(g, 'end'); wd = kid(g, 'width')
            cx, cy = float(ce[1]), float(ce[2])
            r = math.hypot(float(en[1]) - cx, float(en[2]) - cy) + (float(wd[1]) / 2 if wd else 0.0)
            # KiCad rotation: (x c + y s, −x s + y c)
            dx, dy = cx * c + cy * s_, -cx * s_ + cy * c
            return float(at[1]) + dx, float(at[2]) + dy, 2 * r
    return None

def pads(fp):
    out = []
    for p in kids(fp, 'pad'):
        at = kid(p, 'at'); sz = kid(p, 'size')
        if str(p[3]) == 'custom':
            eq = _custom_equiv(p, at)
            if eq:
                x, y, d = eq
                out.append(dict(num=str(p[1]), kind=str(p[2]), shape='circle', x=x, y=y, rot=0.0, w=d, h=d,
                                layers=[str(l) for l in kid(p, 'layers')[1:]], drill=kid(p, 'drill'), rratio=0.0))
                continue
        prims = []
        if str(p[3]) == 'custom':
            pr = kid(p, 'primitives')
            for g in (pr[1:] if pr else []):
                if isinstance(g, list) and g and g[0] == 'gr_poly':
                    prims.append([(float(xy[1]), float(xy[2])) for xy in kids(kid(g, 'pts'), 'xy')])
                elif isinstance(g, list) and g and g[0] == 'gr_rect':
                    s, e = kid(g, 'start'), kid(g, 'end')
                    x0, y0, x1, y1 = float(s[1]), float(s[2]), float(e[1]), float(e[2])
                    prims.append([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
        out.append(dict(num=str(p[1]), kind=str(p[2]), shape=str(p[3]), x=float(at[1]), y=float(at[2]), prims=prims,
                        rot=float(at[3]) if len(at) > 3 else 0.0, w=float(sz[1]), h=float(sz[2]),
                        layers=[str(l) for l in kid(p, 'layers')[1:]], drill=kid(p, 'drill'),
                        rratio=float(kid(p, 'roundrect_rratio')[1]) if (str(p[3]) == 'roundrect' and kid(p, 'roundrect_rratio')) else 0.0))
    return out

def courtyard(fp, side='F'):
    xs, ys = [], []
    for g in fp:
        if not isinstance(g, list) or g[0] not in ('fp_line', 'fp_rect', 'fp_poly', 'fp_circle', 'fp_arc'): continue
        lay = kid(g, 'layer')
        if not lay or not str(lay[1]).endswith('CrtYd'): continue
        for k in ('start', 'end', 'mid', 'center'):
            e = kid(g, k)
            if e: xs.append(float(e[1])); ys.append(float(e[2]))
        pts = kid(g, 'pts')
        if pts:
            for xy in kids(pts, 'xy'): xs.append(float(xy[1])); ys.append(float(xy[2]))
        if g[0] == 'fp_circle':
            c = kid(g, 'center'); e = kid(g, 'end'); r = ((float(e[1]) - float(c[1])) ** 2 + (float(e[2]) - float(c[2])) ** 2) ** 0.5
            xs += [float(c[1]) - r, float(c[1]) + r]; ys += [float(c[2]) - r, float(c[2]) + r]
    if not xs:
        ps = pads(fp)
        xs = [p['x'] - p['w'] / 2 for p in ps] + [p['x'] + p['w'] / 2 for p in ps]
        ys = [p['y'] - p['h'] / 2 for p in ps] + [p['y'] + p['h'] / 2 for p in ps]
    return min(xs), min(ys), max(xs), max(ys)
