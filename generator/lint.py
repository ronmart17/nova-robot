"""Geometric checker for generated KiCad 10 schematics: overlapping texts, symbol bodies and wires.
Usage: python3 lint.py file.kicad_sch [...]"""
import sys, os, math, re, collections
sys.path.insert(0, '/home/claude/robot'); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from symlib import parse
from sch import transform, tpt

CW = 0.92     # mean character width / size (newstroke font)
LINE = 1.61   # line spacing / size

def kids(n, head):
    return [c for c in n[1:] if isinstance(c, list) and c and c[0] == head]
def kid(n, head):
    k = kids(n, head); return k[0] if k else None
def num(v): return float(v)

class Box:
    __slots__ = ('x0', 'y0', 'x1', 'y1', 'what')
    def __init__(self, x0, y0, x1, y1, what=''):
        self.x0, self.x1 = min(x0, x1), max(x0, x1); self.y0, self.y1 = min(y0, y1), max(y0, y1); self.what = what
    def area_inter(self, o, shrink=0.0):
        w = min(self.x1, o.x1) - max(self.x0, o.x0) - shrink
        h = min(self.y1, o.y1) - max(self.y0, o.y0) - shrink
        return w * h if w > 0 and h > 0 else 0.0
    def seg_hits(self, a, b, shrink=0.15):
        # segment (orthogonal or not) crosses the interior of the box
        x0, y0, x1, y1 = self.x0 + shrink, self.y0 + shrink, self.x1 - shrink, self.y1 - shrink
        if x0 >= x1 or y0 >= y1: return False
        (ax, ay), (bx, by) = a, b
        if ax == bx:
            return x0 < ax < x1 and max(min(ay, by), y0) < min(max(ay, by), y1)
        if ay == by:
            return y0 < ay < y1 and max(min(ax, bx), x0) < min(max(ax, bx), x1)
        # general case: sampling
        for i in range(21):
            t = i / 20; px, py = ax + (bx - ax) * t, ay + (by - ay) * t
            if x0 < px < x1 and y0 < py < y1: return True
        return False
    def __repr__(self):
        return f'{self.what} [{self.x0:.2f},{self.y0:.2f}..{self.x1:.2f},{self.y1:.2f}]'

def font_size(n):
    e = kid(n, 'effects')
    if e is None: return 1.27
    f = kid(e, 'font'); s = kid(f, 'size') if f else None
    return num(s[1]) if s else 1.27
def justify(n):
    e = kid(n, 'effects')
    j = kid(e, 'justify') if e else None
    h, v = 'center', 'center'
    if j:
        for t in j[1:]:
            if t in ('left', 'right'): h = t
            if t in ('top', 'bottom'): v = t
    return h, v
def hidden(n):
    h = kid(n, 'hide')
    if h is not None and (len(h) == 1 or h[1] == 'yes'): return True
    e = kid(n, 'effects')
    if e is not None:
        h = kid(e, 'hide')
        if h is not None and (len(h) == 1 or h[1] == 'yes'): return True
        if 'hide' in e[1:]: return True
    return False

def text_box_local(tx, ty, txt, size, ang, h, v):
    lines = txt.split('\n')
    w = max(len(l) for l in lines) * size * CW
    hh = size + (len(lines) - 1) * size * LINE
    x0 = {'left': tx, 'center': tx - w / 2, 'right': tx - w}[h]
    y0 = {'top': ty, 'center': ty - hh / 2, 'bottom': ty - hh}[v]
    pts = [(x0, y0), (x0 + w, y0 + hh)]
    if int(ang) % 180 == 90:
        # RotatePoint 90° around (tx,ty): (dx,dy) -> (dy,-dx)
        pts = [(tx + (py - ty), ty - (px - tx)) for px, py in pts]
    return pts

def load(path):
    t = parse(open(path, encoding='utf-8').read())
    libs = {}
    ls = kid(t, 'lib_symbols')
    for s in kids(ls, 'symbol'):
        libs[s[1]] = s
    return t, libs

def lib_geom(sym):
    """-> dict unit -> (list of points of graphics, list of pins (x,y,ang,len)) in lib coords (Y up)."""
    name = sym[1].split(':')[-1]
    out = collections.defaultdict(lambda: ([], []))
    is_power = kid(sym, 'power') is not None
    for sub in kids(sym, 'symbol'):
        m = re.match(r'.*_(\d+)_(\d+)$', sub[1])
        unit, style = int(m.group(1)), int(m.group(2))
        if style not in (0, 1): continue
        pts, pins = out[unit]
        for g in sub[1:]:
            if not isinstance(g, list): continue
            if g[0] == 'rectangle':
                s, e = kid(g, 'start'), kid(g, 'end')
                pts += [(num(s[1]), num(s[2])), (num(e[1]), num(e[2]))]
            elif g[0] == 'polyline' or g[0] == 'bezier':
                for xy in kids(kid(g, 'pts'), 'xy'): pts.append((num(xy[1]), num(xy[2])))
            elif g[0] == 'circle':
                c, r = kid(g, 'center'), num(kid(g, 'radius')[1])
                pts += [(num(c[1]) - r, num(c[2]) - r), (num(c[1]) + r, num(c[2]) + r)]
            elif g[0] == 'arc':
                for k in ('start', 'mid', 'end'):
                    p = kid(g, k)
                    if p: pts.append((num(p[1]), num(p[2])))
            elif g[0] == 'pin':
                at = kid(g, 'at'); ln = kid(g, 'length')
                pins.append((num(at[1]), num(at[2]), num(at[3]) if len(at) > 3 else 0, num(ln[1]) if ln else 2.54))
    return out, is_power

def analyse(path):
    t, libs = load(path)
    geoms = {k: lib_geom(v) for k, v in libs.items()}
    bodies, texts, wires, pinsegs, pinpts = [], [], [], [], []
    juncs, ncs = set(), set()
    frames = []
    for n in t[1:]:
        if not isinstance(n, list): continue
        head = n[0]
        if head == 'symbol':
            lid = kid(n, 'lib_id')[1]; at = kid(n, 'at')
            x, y, rot = num(at[1]), num(at[2]), int(num(at[3])) if len(at) > 3 else 0
            mir = kid(n, 'mirror'); mir = mir[1] if mir else None
            unit = int(kid(n, 'unit')[1]) if kid(n, 'unit') else 1
            m = transform(rot, mir)
            refp = [p for p in kids(n, 'property') if p[1] == 'Reference']
            ref = refp[0][2] if refp else '?'
            (g, is_power) = geoms[lid]
            pts = g[0][0] + g[unit][0]
            if pts:
                tp = [tpt(m, px, -py) for px, py in pts]
                xs = [x + a for a, b in tp]; ys = [y + b for a, b in tp]
                bodies.append((Box(min(xs), min(ys), max(xs), max(ys), f'body {ref}'), ref, is_power or lid.endswith(':LED')))
            for (px, py, pa, pl) in g[0][1] + g[unit][1]:
                cx, cy = tpt(m, px, -py)
                d = {0: (1, 0), 90: (0, 1), 180: (-1, 0), 270: (0, -1)}[int(pa) % 360]
                ex, ey = tpt(m, px + d[0] * pl, -(py + d[1] * pl))
                pinpts.append((round(x + cx, 3), round(y + cy, 3), ref))
                pinsegs.append(((x + cx, y + cy), (x + ex, y + ey), ref))
            det = m[0] * m[3] - m[1] * m[2]
            minv = (m[3] / det, -m[1] / det, -m[2] / det, m[0] / det)
            for p in kids(n, 'property'):
                if hidden(p) or p[2] == '': continue
                pat = kid(p, 'at'); ax, ay, aang = num(pat[1]), num(pat[2]), num(pat[3]) if len(pat) > 3 else 0
                rx, ry = tpt(minv, ax - x, ay - y)
                h, v = justify(p)
                loc = text_box_local(x + rx, y + ry, p[2], font_size(p), aang, h, v)
                q = [tpt(m, px - x, py - y) for px, py in loc]
                texts.append((Box(x + q[0][0], y + q[0][1], x + q[1][0], y + q[1][1], f'{p[1]} {ref}="{p[2]}"'), ref, 'field'))
        elif head == 'wire':
            xy = kids(kid(n, 'pts'), 'xy')
            wires.append(((num(xy[0][1]), num(xy[0][2])), (num(xy[1][1]), num(xy[1][2]))))
        elif head == 'junction':
            at = kid(n, 'at'); juncs.add((round(num(at[1]), 3), round(num(at[2]), 3)))
        elif head == 'no_connect':
            at = kid(n, 'at'); ncs.add((round(num(at[1]), 3), round(num(at[2]), 3)))
        elif head in ('label', 'hierarchical_label', 'global_label'):
            at = kid(n, 'at'); x, y, a = num(at[1]), num(at[2]), int(num(at[3]))
            s = font_size(n); L = len(n[1]) * s * CW
            if head == 'label':
                d = {0: (1, 0), 180: (-1, 0), 90: (0, -1), 270: (0, 1)}[a]
                if d[1] == 0:
                    b = Box(x, y - 0.25, x + d[0] * (L + 0.3), y - s - 0.4)
                else:
                    b = Box(x - 0.25, y, x - s - 0.4, y + d[1] * (L + 0.3))
            else:
                extra = s * 1.2 + (s * 0.6 if head == 'global_label' else 0.3)
                d = {0: (1, 0), 180: (-1, 0), 90: (0, -1), 270: (0, 1)}[a]
                if head == 'hierarchical_label':
                    d = {0: (-1, 0), 180: (1, 0), 90: (0, 1), 270: (0, -1)}[a] if False else d
                if d[1] == 0:
                    b = Box(x, y - s * 0.65, x + d[0] * (L + extra), y + s * 0.65)
                else:
                    b = Box(x - s * 0.65, y, x + s * 0.65, y + d[1] * (L + extra))
            b.what = f'{head} "{n[1]}"'
            texts.append((b, None, head))
        elif head == 'text':
            at = kid(n, 'at'); x, y, a = num(at[1]), num(at[2]), num(at[3]) if len(at) > 3 else 0
            h, v = justify(n)
            loc = text_box_local(x, y, n[1], font_size(n), a, h, v)
            texts.append((Box(loc[0][0], loc[0][1], loc[1][0], loc[1][1], 'text "' + n[1].split('\n')[0][:30] + '"'), None, 'text'))
        elif head == 'rectangle':
            s, e = kid(n, 'start'), kid(n, 'end')
            frames.append(Box(num(s[1]), num(s[2]), num(e[1]), num(e[2]), 'frame'))
        elif head == 'sheet':
            at = kid(n, 'at'); sz = kid(n, 'size')
            bodies.append((Box(num(at[1]), num(at[2]), num(at[1]) + num(sz[1]), num(at[2]) + num(sz[2]), 'sheet ' + n[1] if isinstance(n[1], str) else 'sheet'), 'sheet', False))
            for p in kids(n, 'pin'):
                pa = kid(p, 'at'); pinpts.append((round(num(pa[1]), 3), round(num(pa[2]), 3), 'sheetpin'))
    return dict(bodies=bodies, texts=texts, wires=wires, pinsegs=pinsegs, pinpts=pinpts, juncs=juncs, ncs=ncs, frames=frames)

def on_seg(p, a, b):
    if a[0] == b[0] == p[0]: return min(a[1], b[1]) < p[1] < max(a[1], b[1])
    if a[1] == b[1] == p[1]: return min(a[0], b[0]) < p[0] < max(a[0], b[0])
    return False

def check(path, min_area=0.25):
    G = analyse(path)
    out = []
    B = G['bodies']; T = G['texts']; W = G['wires']
    # 1 overlapping bodies
    for i in range(len(B)):
        for j in range(i + 1, len(B)):
            (bi, ri, pi), (bj, rj, pj) = B[i], B[j]
            if pi or pj: continue
            if bi.area_inter(bj, 0.2) > 0: out.append(('BODY-BODY', bi, bj))
    # 2 overlapping texts
    for i in range(len(T)):
        for j in range(i + 1, len(T)):
            if T[i][0].area_inter(T[j][0]) > min_area: out.append(('TEXT-TEXT', T[i][0], T[j][0]))
    # 3 text over a body (except power symbols)
    for tb, tref, kind in T:
        for bb, bref, isp in B:
            if isp and kind == 'field' and tref == bref: continue
            if bb.area_inter(tb) > min_area: out.append(('TEXT-BODY', tb, bb))
    # 4 wire crosses text
    for tb, tref, kind in T:
        for a, b in W:
            if tb.seg_hits(a, b, 0.2): out.append(('WIRE-TEXT', tb, f'wire {a}->{b}'))
    # 5 wire crosses a body
    for bb, bref, isp in B:
        if isp: continue
        for a, b in W:
            if bb.seg_hits(a, b, 0.3): out.append(('WIRE-BODY', bb, f'wire {a}->{b}'))
    # 6 overlapping collinear wires
    for i in range(len(W)):
        for j in range(i + 1, len(W)):
            (a, b), (c, d) = W[i], W[j]
            if a[0] == b[0] == c[0] == d[0]:
                lo = max(min(a[1], b[1]), min(c[1], d[1])); hi = min(max(a[1], b[1]), max(c[1], d[1]))
                if hi - lo > 0.01: out.append(('WIRE-OVERLAP', f'{W[i]}', f'{W[j]}'))
            elif a[1] == b[1] == c[1] == d[1]:
                lo = max(min(a[0], b[0]), min(c[0], d[0])); hi = min(max(a[0], b[0]), max(c[0], d[0]))
                if hi - lo > 0.01: out.append(('WIRE-OVERLAP', f'{W[i]}', f'{W[j]}'))
    # 7 dangling wire ends
    anchors = collections.Counter()
    for a, b in W:
        anchors[(round(a[0], 3), round(a[1], 3))] += 1; anchors[(round(b[0], 3), round(b[1], 3))] += 1
    pins = {(x, y) for x, y, _ in G['pinpts']}
    labels_at = set()
    for n in parse(open(path, encoding='utf-8').read())[1:]:
        if isinstance(n, list) and n[0] in ('label', 'hierarchical_label', 'global_label'):
            at = kid(n, 'at'); labels_at.add((round(num(at[1]), 3), round(num(at[2]), 3)))
    for (p, cnt) in anchors.items():
        if cnt > 1 or p in pins or p in labels_at or p in G['juncs'] or p in G['ncs']: continue
        if any(on_seg(p, a, b) for a, b in W): continue
        out.append(('WIRE-DANGLING', f'end {p}', ''))
    # 8 items crossing section frames
    for fr in G['frames']:
        for tb, tref, kind in T + [(b, r, 'body') for b, r, isp in B]:
            inside = fr.area_inter(tb)
            if 0 < inside < (tb.x1 - tb.x0) * (tb.y1 - tb.y0) - 0.05 and (tb.x1 - tb.x0) * (tb.y1 - tb.y0) < (fr.x1 - fr.x0) * (fr.y1 - fr.y0):
                out.append(('CROSSES-FRAME', tb, fr))
    # 9 T without junction / 4-way junction
    deg = collections.Counter()
    for a, b in W:
        for p in (a, b): deg[(round(p[0], 3), round(p[1], 3))] += 1
    for j in G['juncs']:
        d = deg[j] + sum(1 for a, b in W if on_seg(j, a, b)) * 2 + sum(1 for x, y, _ in G['pinpts'] if (x, y) == j)
        if d >= 4: out.append(('JUNCTION-4', f'junction {j}', ''))
    return out

if __name__ == '__main__':
    tot = 0
    for p in sys.argv[1:]:
        res = check(p)
        cnt = collections.Counter(r[0] for r in res)
        print(f'## {os.path.basename(p)}: {dict(cnt) if cnt else "no issues"}')
        for r in res:
            print('  ', r[0], '|', r[1], '|', r[2])
        tot += len(res)
    print('TOTAL', tot)
