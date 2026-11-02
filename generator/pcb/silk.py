"""Board silkscreen (runs inside pcbnew, after the board is written):
1) mechanical outlines (battery, motors, caster, head board) clipped around pads and other silkscreen;
2) functional labels (connectors, buttons, polarity, test points, title);
3) automatic reference placement: around each footprint, without overlapping pads, other components' bodies,
   other silkscreen or the board edge; if it does not fit, the reference is hidden (it stays on F.Fab/B.Fab for the
   assembly drawing).
JLCPCB rules (Character Design Specifications): height ≥ 0.8 mm (≥ 1.0 mm recommended), stroke ≥ 0.15 mm,
silkscreen ≥ 0.15 mm from pads."""
import math
import pcbnew
from shapely.geometry import Polygon, LineString, MultiLineString, box, Point
from shapely.ops import unary_union
from shapely.strtree import STRtree
from shapely import affinity

MM, TM = pcbnew.FromMM, pcbnew.ToMM
LAY = {'F': (pcbnew.F_SilkS, pcbnew.F_Cu, pcbnew.F_CrtYd), 'B': (pcbnew.B_SilkS, pcbnew.B_Cu, pcbnew.B_CrtYd)}
PAD_CLR = 0.25      # silkscreen to pad copper (includes 0.05 mask expansion + 0.2)
EDGE_CLR = 0.5      # silkscreen to board edge
TXT_GAP = 0.2       # between texts
LINE_W = 0.15
X0, Y0 = 150.0, 100.0   # local origin (board centre)

def A(x, y):
    return (X0 + x, Y0 + y)

# ------------------------------------------------------------------ geometry
def ps_to_shapely(ps):
    out = []
    for i in range(ps.OutlineCount()):
        o = ps.Outline(i)
        ext = [(TM(o.CPoint(k).x), TM(o.CPoint(k).y)) for k in range(o.PointCount())]
        holes = []
        for h in range(ps.HoleCount(i)):
            hh = ps.Hole(i, h)
            hp = [(TM(hh.CPoint(k).x), TM(hh.CPoint(k).y)) for k in range(hh.PointCount())]
            if len(hp) >= 3: holes.append(hp)
        if len(ext) >= 3:
            g = Polygon(ext, holes).buffer(0)
            if not g.is_empty: out.append(g)
    return out

def item_geom(it, layer, clr=0.0):
    ps = pcbnew.SHAPE_POLY_SET()
    it.TransformShapeToPolygon(ps, layer, MM(clr), MM(0.005), pcbnew.ERROR_OUTSIDE)
    g = ps_to_shapely(ps)
    return unary_union(g) if g else None

def courtyard(fp, crt):
    fp.BuildCourtyardCaches()
    g = ps_to_shapely(fp.GetCourtyard(crt))
    return unary_union(g) if g else None

def side_of(fp):
    return 'B' if fp.GetLayer() == pcbnew.B_Cu else 'F'

class Grid:
    """Simple spatial index for the texts already placed."""
    def __init__(self, cell=4.0):
        self.c = cell; self.d = {}
    def _keys(self, g):
        x0, y0, x1, y1 = g.bounds
        for i in range(int(math.floor(x0 / self.c)), int(math.floor(x1 / self.c)) + 1):
            for j in range(int(math.floor(y0 / self.c)), int(math.floor(y1 / self.c)) + 1):
                yield (i, j)
    def add(self, g):
        for k in self._keys(g): self.d.setdefault(k, []).append(g)
    def hits(self, g):
        seen = set()
        for k in self._keys(g):
            for h in self.d.get(k, ()):
                if id(h) in seen: continue
                seen.add(id(h))
                if h.intersects(g): return True
        return False

# ------------------------------------------------------------------ context
class Ctx:
    def __init__(self, b):
        self.b = b
        ps = pcbnew.SHAPE_POLY_SET()
        b.GetBoardPolygonOutlines(ps, False)
        self.board = unary_union(ps_to_shapely(ps))
        self.inner = self.board.buffer(-EDGE_CLR)
        self.obs = {'F': [], 'B': []}       # fixed obstacles (pads, footprint silkscreen, bodies)
        self.copper = {'F': [], 'B': []}    # pads (for clipping lines)
        self.body = {}                      # ref -> (side, courtyard polygon)
        for fp in b.GetFootprints():
            s = side_of(fp)
            crt = LAY[s][2]
            cy = courtyard(fp, crt)
            if cy is not None:
                self.body[fp.GetReference()] = (s, cy)
                g = cy.buffer(-0.2)
                if not g.is_empty: self.obs[s].append(g)
            for it in fp.GraphicalItems():
                for S in 'FB':
                    if it.GetLayer() == LAY[S][0]:
                        g = item_geom(it, LAY[S][0])
                        if g is not None: self.obs[S].append(g)
            for pad in fp.Pads():
                if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                    q = pad.GetPosition(); d = pad.GetDrillSize()
                    g = Point(TM(q.x), TM(q.y)).buffer(max(TM(d.x), TM(d.y)) / 2 + 0.3, 24)
                    for S in 'FB':
                        self.obs[S].append(g); self.copper[S].append(g)
                    continue
                for S in 'FB':
                    if pad.IsOnLayer(LAY[S][1]):
                        g = item_geom(pad, LAY[S][1], PAD_CLR)
                        if g is not None:
                            self.obs[S].append(g); self.copper[S].append(g)
        self.dyn = {'F': Grid(), 'B': Grid()}
        self.tree = {}
        self.rebuild()

    def rebuild(self):
        for S in 'FB':
            self.tree[S] = STRtree(self.obs[S])

    def free(self, S, g):
        if not self.inner.contains(g): return False
        if self.tree[S].query(g, predicate='intersects').size: return False
        return not self.dyn[S].hits(g.buffer(TXT_GAP))

    def static_free(self, S, g):
        if not self.inner.contains(g): return False
        return not self.tree[S].query(g, predicate='intersects').size

    def add_dyn(self, S, g):
        self.dyn[S].add(g)

# ------------------------------------------------------------------ drawing
def add_segment(b, a, c, layer, w=LINE_W):
    s = pcbnew.PCB_SHAPE(b)
    s.SetShape(pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(pcbnew.VECTOR2I(MM(a[0]), MM(a[1])))
    s.SetEnd(pcbnew.VECTOR2I(MM(c[0]), MM(c[1])))
    s.SetLayer(layer)
    s.SetWidth(MM(w))
    b.Add(s)
    return s

def draw_clipped(ctx, S, line, w=LINE_W, min_len=0.6):
    """Draw a silkscreen polyline, clipped around pads, other silkscreen and outside the board edge."""
    layer = LAY[S][0]
    cut = unary_union(ctx.obs[S]).buffer(w / 2 + 0.1)
    g = line.intersection(ctx.inner.buffer(-w / 2)).difference(cut)
    parts = [g] if g.geom_type == 'LineString' else [p for p in getattr(g, 'geoms', []) if p.geom_type == 'LineString']
    drawn = []
    for p in parts:
        if p.length < min_len: continue
        cs = list(p.coords)
        for a, c in zip(cs, cs[1:]):
            add_segment(ctx.b, a, c, layer, w)
        drawn.append(p.buffer(w / 2))
    for d in drawn:
        ctx.obs[S].append(d)
    ctx.rebuild()
    return drawn

def new_text(b, s, S, size=1.0, thick=0.15):
    t = pcbnew.PCB_TEXT(b)
    t.SetText(s)
    t.SetLayer(LAY[S][0])
    t.SetTextSize(pcbnew.VECTOR2I(MM(size), MM(size)))
    t.SetTextThickness(MM(thick))
    t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER)
    if S == 'B': t.SetMirrored(True)
    b.Add(t)
    return t

# ------------------------------------------------------------------ text placement
def text_box(item, angle, size, thick):
    """Text polygon (box) centred on the origin, and the anchor→centre offset."""
    item.SetTextSize(pcbnew.VECTOR2I(MM(size), MM(size)))
    item.SetTextThickness(MM(thick))
    item.SetTextAngle(pcbnew.EDA_ANGLE(angle, pcbnew.DEGREES_T))
    item.SetPosition(pcbnew.VECTOR2I(0, 0))
    ps = pcbnew.SHAPE_POLY_SET()
    item.TransformShapeToPolygon(ps, item.GetLayer(), 0, MM(0.005), pcbnew.ERROR_OUTSIDE)
    g = unary_union(ps_to_shapely(ps))
    c = g.centroid
    return affinity.translate(g, -c.x, -c.y), (c.x, c.y)

def candidates(spec, ctx):
    """Generate feasible (score, polygon, anchor, angle, size, stroke) candidates against the fixed obstacles."""
    item, S = spec['item'], spec['side']
    out = []
    for si, (size, thick) in enumerate(spec.get('sizes', [(1.0, 0.15), (0.8, 0.15)])):
        for angle in spec.get('angles', (0, 90)):
            g0, off = text_box(item, angle, size, thick)
            x0, y0, x1, y1 = g0.bounds
            bw, bh = x1 - x0, y1 - y0
            pts = []
            if spec['mode'] == 'around':
                ax0, ay0, ax1, ay1 = spec['bbox']
                cx, cy = (ax0 + ax1) / 2, (ay0 + ay1) / 2
                pref = spec.get('prefer', ('top', 'bottom', 'left', 'right'))
                for gi, gap in enumerate((0.15, 0.4, 0.8, 1.3, 2.0)):
                    for sh in (0, 0.5, -0.5, 1.0, -1.0, 1.6, -1.6, 2.4, -2.4):
                        for k, sd in enumerate(pref):
                            if sd == 'top': p = (cx + sh, ay0 - gap - bh / 2)
                            elif sd == 'bottom': p = (cx + sh, ay1 + gap + bh / 2)
                            elif sd == 'left': p = (ax0 - gap - bw / 2, cy + sh)
                            else: p = (ax1 + gap + bw / 2, cy + sh)
                            sc = gi * 1.0 + abs(sh) * 0.5 + k * 0.35
                            pts.append((sc, p))
            else:   # 'at': spiral around a point
                px, py = spec['point']
                pts.append((0.0, (px, py)))
                rmax = spec.get('rmax', 3.0)
                r = 0.4
                while r <= rmax + 1e-9:
                    n = max(8, int(2 * math.pi * r / 0.4))
                    for k in range(n):
                        a = 2 * math.pi * k / n
                        pts.append((r * 1.2, (px + r * math.cos(a), py + r * math.sin(a))))
                    r += 0.4
            for sc, p in pts:
                g = affinity.translate(g0, p[0], p[1])
                if ctx.static_free(S, g):
                    out.append((sc + (0.8 if angle else 0.0) + si * 3.0, g, (p[0] - off[0], p[1] - off[1]), angle, size,
                                thick))
    out.sort(key=lambda t: t[0])
    return out

def place_texts(ctx, specs):
    cands = {}
    for k, sp in enumerate(specs):
        cands[k] = candidates(sp, ctx)
    order = sorted(cands, key=lambda k: (-specs[k].get('prio', 0), len(cands[k]) if cands[k] else 1e9))
    placed, hidden = 0, []
    for k in order:
        sp = specs[k]; item, S = sp['item'], sp['side']
        ok = None
        for c in cands[k]:
            if not ctx.dyn[S].hits(c[1].buffer(TXT_GAP)):
                ok = c; break
        if ok is None:
            if sp.get('kind') == 'ref':
                item.SetVisible(False)
            else:
                ctx.b.Remove(item)
            hidden.append(sp['name'])
            continue
        sc, g, pos, angle, size, thick = ok
        item.SetTextSize(pcbnew.VECTOR2I(MM(size), MM(size)))
        item.SetTextThickness(MM(thick))
        item.SetTextAngle(pcbnew.EDA_ANGLE(angle, pcbnew.DEGREES_T))
        item.SetPosition(pcbnew.VECTOR2I(MM(pos[0]), MM(pos[1])))
        if sp.get('kind') == 'ref': item.SetVisible(True)
        ctx.add_dyn(S, g)
        placed += 1
    return placed, hidden


# ------------------------------------------------------------------ logo (ronmart)
import os
LOGO_PNG = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'kicad', 'lib', 'logo', 'ronmart_logo_silk.png')

def _logo_mask():
    from PIL import Image
    im = Image.open(LOGO_PNG).convert('RGBA')
    W, H = im.size
    a = im.getchannel('A').load()
    rows = [[a[x, y] > 127 for x in range(W)] for y in range(H)]
    ys = [y for y in range(H) if any(rows[y])]
    xs = [x for x in range(W) if any(rows[y][x] for y in ys)]
    return [r[min(xs):max(xs) + 1] for r in rows[min(ys):max(ys) + 1]]

def _logo_runs(height, mirror):
    """Row runs of the logo as rectangles (mm, centred on the origin)."""
    m = _logo_mask()
    H, W = len(m), len(m[0])
    px = height / H
    out = []
    for y, row in enumerate(m):
        x = 0
        while x < W:
            if row[x]:
                x2 = x
                while x2 < W and row[x2]: x2 += 1
                xa, xb = (x - W / 2) * px, (x2 - W / 2) * px
                if mirror: xa, xb = -xb, -xa
                out.append((xa, (y - H / 2) * px, xb, (y + 1 - H / 2) * px))
                x = x2
            else:
                x += 1
    return out, W * px

def place_logo(ctx, S, prefer, heights=(8.0, 7.0, 6.0), rmax=8.0, keep=0.4):
    """Logo as filled silkscreen polygons on side S, as close to `prefer` as it fits (pads, silk, vias, edge).
    Strokes ≥ 0.15 mm (JLCPCB) need ≥ 5.5 mm of height (thinnest stroke ≈ 6 px of 204)."""
    vias = [Point(TM(t.GetPosition().x), TM(t.GetPosition().y)).buffer(TM(t.GetWidth(pcbnew.F_Cu)) / 2 + 0.1, 12)
            for t in ctx.b.GetTracks() if t.GetClass() == 'PCB_VIA']
    vtree = STRtree(vias) if vias else None
    for h in heights:
        runs, w = _logo_runs(h, S == 'B')
        r = 0.0
        while r <= rmax + 1e-9:
            n = 1 if r == 0 else max(8, int(2 * math.pi * r / 0.5))
            for k in range(n):
                cx = prefer[0] + r * math.cos(2 * math.pi * k / n); cy = prefer[1] + r * math.sin(2 * math.pi * k / n)
                g = box(cx - w / 2 - keep, cy - h / 2 - keep, cx + w / 2 + keep, cy + h / 2 + keep)
                if not ctx.free(S, g): continue
                if vtree is not None and vtree.query(g, predicate='intersects').size: continue
                ps = pcbnew.SHAPE_POLY_SET()
                for xa, ya, xb, yb in runs:
                    ps.NewOutline()
                    for qx, qy in ((xa, ya), (xb, ya), (xb, yb), (xa, yb)):
                        ps.Append(MM(cx + qx), MM(cy + qy))
                ps.Simplify()
                ps.Fracture()
                for i in range(ps.OutlineCount()):
                    one = pcbnew.SHAPE_POLY_SET(); one.AddOutline(ps.Outline(i))
                    sh = pcbnew.PCB_SHAPE(ctx.b)
                    sh.SetShape(pcbnew.SHAPE_T_POLY); sh.SetPolyShape(one); sh.SetFilled(True); sh.SetWidth(0)
                    sh.SetLayer(LAY[S][0]); ctx.b.Add(sh)
                ctx.add_dyn(S, g)
                return (round(cx, 2), round(cy, 2), round(w, 2), h)
            r += 0.5
    return None

# ------------------------------------------------------------------ content
TP_LABEL = {'TP301': 'VSYS', 'TP302': 'VBAT', 'TP303': '5V', 'TP304': '3V3', 'TP305': 'GND', 'TP306': 'GND',
            'TP307': 'BAT-', 'TP401': 'D-', 'TP402': 'D+', 'TP403': 'GND', 'TP201': 'QON'}
FUNC_LABEL = {'J201': 'USB-C IN', 'J202': 'NTC', 'J203': 'DOCK 12V', 'J301': 'BAT 2S', 'SW301': 'PWR', 'SW401': 'RST',
              'SW402': 'BOOT', 'J401': 'UART', 'J501': 'MOTOR L', 'J502': 'MOTOR R', 'J602': 'HEAD', 'J603': 'SERVO',
              'J701': 'PI GPIO', 'J702': 'PI 5V'}
NO_REF = ('FID', 'H')       # no silkscreen reference (fiducials, mounting holes)

def fp_bbox(ctx, fp):
    ref = fp.GetReference()
    if ref in ctx.body: return ctx.body[ref][1].bounds
    bb = fp.GetBoundingBox(False)
    return (TM(bb.GetLeft()), TM(bb.GetTop()), TM(bb.GetRight()), TM(bb.GetBottom()))

def pad_center(fp, num):
    for p in fp.Pads():
        if p.GetNumber() == num:
            q = p.GetPosition(); return (TM(q.x), TM(q.y))
    return None

def mech_outlines(ctx):
    b = ctx.b
    import sys
    sys.path.insert(0, '/home/claude/robot/mech')
    import dims as D
    # 2S2P pack (on top, in its cage): X ±BAT_X, Y BAT_Y0..BAT_Y1 → local (X, −Y)
    x0, y0 = A(-D.BAT_X, -D.BAT_Y1); x1, y1 = A(D.BAT_X, -D.BAT_Y0)
    draw_clipped(ctx, 'F', LineString([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]))
    # head board (vertical at the front): Y HEAD_Y0..HEAD_Y0 + HEAD_T, HEAD_W wide
    hw = D.HEAD_W / 2
    hx0, hy0 = A(-hw, -(D.HEAD_Y0 + D.HEAD_T)); hx1, hy1 = A(hw, -D.HEAD_Y0)
    draw_clipped(ctx, 'F', LineString([(hx0, hy0), (hx1, hy0), (hx1, hy1), (hx0, hy1), (hx0, hy0)]))
    # motors and caster (bottom side): outline of their no-copper areas
    for z in b.Zones():
        if not z.GetIsRuleArea(): continue
        nm = z.GetZoneName()
        if 'motor' in nm or 'caster' in nm:
            for g in ps_to_shapely(z.Outline()):
                draw_clipped(ctx, 'B', LineString(list(g.exterior.coords)))

def common_specs(ctx, func_label, tp_label):
    """Functional/test-point labels and the references of all footprints."""
    b = ctx.b
    specs = []
    fps = {fp.GetReference(): fp for fp in b.GetFootprints()}
    for ref, s in list(func_label.items()) + list(tp_label.items()):
        fp = fps.get(ref)
        if fp is None: continue
        S = side_of(fp)
        t = new_text(b, s, S, 1.0, 0.15)
        specs.append(dict(item=t, side=S, mode='around', bbox=fp_bbox(ctx, fp), sizes=[(1.0, 0.15), (0.8, 0.15)],
                          prio=2, name=f'{ref}:{s}', kind='label'))
    for ref, fp in fps.items():
        f = fp.Reference()
        if hasattr(f, 'SetKeepUpright'): f.SetKeepUpright(True)
        # the value only clutters the assembly drawing (F.Fab): it stays in the BOM
        fp.Value().SetVisible(False)
        if ref.startswith(NO_REF) and ref.rstrip('0123456789') in NO_REF:
            f.SetVisible(False); continue
        S = side_of(fp)
        specs.append(dict(item=f, side=S, mode='around', bbox=fp_bbox(ctx, fp), prio=0, name=ref, kind='ref'))
    return specs

def label_at(ctx, specs, s, S, p, sz, rmax=6.0, prio=5, angles=(0,), name=None):
    th = 0.25 if sz >= 2 else (0.18 if sz > 1.0 else 0.15)
    t = new_text(ctx.b, s, S, sz, th)
    specs.append(dict(item=t, side=S, mode='at', point=p, rmax=rmax, sizes=[(sz, th)], angles=angles, prio=prio,
                      name=name or s, kind='label'))

def pin_labels(ctx, specs, fp, labels, S, sz=0.8, rmax=3.0, prio=3, offset=(0.0, 0.0)):
    for num, s in labels:
        c = pad_center(fp, num)
        if c is None: continue
        t = new_text(ctx.b, s, S, sz, 0.15)
        specs.append(dict(item=t, side=S, mode='at', point=(c[0] + offset[0], c[1] + offset[1]), rmax=rmax,
                          sizes=[(sz, 0.15)], angles=(0,), prio=prio, name=f'{fp.GetReference()}.{num}{S}', kind='label'))

# ------------------------------------------------------------------ main board
def main_content(ctx):
    b = ctx.b
    mech_outlines(ctx)
    specs = []
    label_at(ctx, specs, '2S2P PACK', 'F', A(0, -4.0), 2.0, rmax=8.0)
    label_at(ctx, specs, 'HEAD BOARD', 'F', A(-26.0, -50.5), 1.2, rmax=8.0)
    for z in b.Zones():
        if not z.GetIsRuleArea(): continue
        nm = z.GetZoneName()
        if 'motor' in nm or 'caster' in nm:
            g = unary_union(ps_to_shapely(z.Outline()))
            c = g.representative_point()
            lab = 'CASTER' if 'caster' in nm else ('N20 LEFT' if c.x < X0 else 'N20 RIGHT')
            label_at(ctx, specs, lab, 'B', (c.x, c.y), 1.2, angles=(0, 90))
    # title on the bottom side (between the IMU and the caster), revision on the top side
    ctx.logo = place_logo(ctx, 'B', A(-12.0, -33.0), heights=(7.5, 7.0, 6.0), rmax=8.0)
    if ctx.logo:
        label_at(ctx, specs, 'ronmart', 'B', (ctx.logo[0], ctx.logo[1] + ctx.logo[3] / 2 + 1.3), 1.2, rmax=2.0, prio=6)
    label_at(ctx, specs, 'NOVA', 'B', A(6.0, -36.0), 3.0, rmax=8.0, prio=6)
    label_at(ctx, specs, 'MAIN BOARD · REV B · 2026-10', 'B', A(6.0, -32.3), 1.2, rmax=8.0, prio=5)
    label_at(ctx, specs, '4 layers · 1.6 mm · JLC04161H-7628', 'B', A(6.0, -29.8), 1.0, rmax=8.0, prio=5)
    label_at(ctx, specs, 'NOVA · REV B', 'F', A(-24.0, 56.0), 1.2, rmax=10.0, prio=4)
    fps = {fp.GetReference(): fp for fp in b.GetFootprints()}
    # battery polarity (J301: 1 = BAT−, 2 = midpoint, 3 = BAT+): on both sides next to each pin
    if 'J301' in fps:
        for S in ('F', 'B'):
            for num, s in (('1', '−'), ('2', 'BM'), ('3', '+')):
                c = pad_center(fps['J301'], num)
                label_at(ctx, specs, s, S, c, 1.5 if s in '+−' else 1.0, rmax=4.0, prio=4, name=f'J301.{num}{S}')
    # dock input polarity (J203, bottom side)
    if 'J203' in fps:
        S = side_of(fps['J203'])
        for num, s in (('1', '+12V'), ('2', 'GND')):
            label_at(ctx, specs, s, S, pad_center(fps['J203'], num), 0.8, rmax=3.0, prio=4, name=f'J203.{num}')
    # UART pins (1 GND, 2 TX, 3 RX, 4 3V3)
    if 'J401' in fps:
        pin_labels(ctx, specs, fps['J401'], (('1', 'G'), ('2', 'TX'), ('3', 'RX'), ('4', '3V3')), 'F', rmax=3.6)
    return specs + common_specs(ctx, FUNC_LABEL, TP_LABEL)

# ------------------------------------------------------------------ head board
HX0, HZ0 = 150.0, 156.0
def AH(x, z):
    return (HX0 + x, HZ0 - z)

HEAD_FUNC = {'U101': 'ToF', 'U103': 'TOUCH', 'TP101': 'ELECTRODE', 'J101': 'TO J602'}
LCD_PINS = (('1', 'GND'), ('2', '3V3'), ('3', 'SCL'), ('4', 'SDA'), ('5', 'RES'), ('6', 'DC'), ('7', 'CS'), ('8', 'BL'))

def head_content(ctx):
    b = ctx.b
    import head_pcb as H
    fps = {fp.GetReference(): fp for fp in b.GetFootprints()}
    # 2.0" LCD module outline (61.12 × 36.48 mm) and Camera Module 3 outline (25 × 23.86 mm)
    w, h, zc = H.LCD[0], H.LCD[1], H.LCD_ZC
    x0, y0 = AH(-w / 2, zc + h / 2); x1, y1 = AH(w / 2, zc - h / 2)
    draw_clipped(ctx, 'F', LineString([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]))
    cx0, cy0 = AH(-H.CAM_W / 2, H.CAM_TOP); cx1, cy1 = AH(H.CAM_W / 2, H.CAM_TOP - H.CAM_H)
    draw_clipped(ctx, 'F', LineString([(cx0, cy0), (cx1, cy0), (cx1, cy1), (cx0, cy1), (cx0, cy0)]))
    lx, lz = AH(0, H.CAM_LENS_Z)
    draw_clipped(ctx, 'F', Point(lx, lz).buffer(2.9, 24).exterior)
    specs = []
    label_at(ctx, specs, '2.0" LCD MODULE  61 × 36.5 mm', 'F', AH(0, 38.0), 1.2)
    label_at(ctx, specs, 'J102 or J103: fit only one', 'F', AH(0, 34.5), 1.0)
    label_at(ctx, specs, 'CAMERA MODULE 3', 'F', AH(0, H.CAM_TOP - 4.5), 1.2, rmax=4.0)
    label_at(ctx, specs, 'FPC ↓ (to the rear)', 'F', AH(0, H.SLOT[1] + 2.4), 1.0, rmax=3.0)
    # display header pin labels, on the inside and on the back
    for ref, dx in (('J102', -2.7), ('J103', 2.7)):
        if ref in fps:
            pin_labels(ctx, specs, fps[ref], LCD_PINS, 'F', offset=(dx, 0.0), rmax=1.5)
            pin_labels(ctx, specs, fps[ref], LCD_PINS, 'B', offset=(dx, 0.0), rmax=1.5)
    # back side: title, notes and cable
    ctx.logo = place_logo(ctx, 'B', AH(-14.0, 31.5), heights=(7.5, 7.0, 6.0), rmax=6.0)
    if ctx.logo:
        label_at(ctx, specs, 'ronmart', 'B', (ctx.logo[0], ctx.logo[1] + ctx.logo[3] / 2 + 1.3), 1.2, rmax=2.0, prio=6)
    label_at(ctx, specs, 'NOVA', 'B', AH(4.0, 33.0), 3.0, rmax=6.0, prio=6)
    label_at(ctx, specs, 'HEAD BOARD · REV B · 2026-10', 'B', AH(4.0, 29.3), 1.2, rmax=6.0, prio=5)
    label_at(ctx, specs, 'Display: solder J102 or J103 (pin 1 = GND at top)', 'B', AH(0, 23.5), 1.0, rmax=8.0, prio=4)
    label_at(ctx, specs, 'JST SH 20-pin 1:1 cable → J602', 'B', AH(0, 11.5), 1.0, rmax=6.0, prio=4)
    label_at(ctx, specs, 'Camera FPC → Pi 5 CAM/DISP (15→22-pin cable)', 'B', AH(0, H.SLOT[1] - 2.6), 1.0, rmax=6.0, prio=4)
    return specs + common_specs(ctx, HEAD_FUNC, {})

# ------------------------------------------------------------------ dock board + contact plate
DOCK_FUNC = {'J1': '12V IN', 'D3': 'PWR'}

def dock_content(ctx):
    b = ctx.b
    import dock_pcb as DK
    fps = {fp.GetReference(): fp for fp in b.GetFootprints()}
    specs = []
    # pogo pairs: polarity on the top side
    for ref, s in (('P1', '+12V'), ('P2', 'GND')):
        if ref in fps:
            q = fps[ref].GetPosition()
            label_at(ctx, specs, s, 'F', (TM(q.x), TM(q.y) - 2.6), 1.2, rmax=3.0, prio=5, name=f'{ref}:{s}')
    # plate: the F side faces the floor (pogo side); labels read correctly with the robot upside down
    for ref, s in (('TP1', '+12V'), ('TP2', 'GND')):
        if ref in fps:
            q = fps[ref].GetPosition()
            label_at(ctx, specs, s, 'F', (TM(q.x), TM(q.y) + 7.6), 1.2, rmax=2.0, prio=5, name=f'{ref}:{s}')
    cx, cy = DK.PC
    label_at(ctx, specs, 'ROBOT CONTACT PLATE · pads face down', 'F', A(cx, cy - 7.6), 1.0, rmax=2.0, prio=4)
    label_at(ctx, specs, '← ROBOT FRONT', 'B', A(cx, cy + 7.6), 1.0, rmax=2.0, prio=4)
    if 'J2' in fps:
        S = side_of(fps['J2'])
        for num, s in (('1', '+'), ('2', '−')):
            label_at(ctx, specs, s, S, pad_center(fps['J2'], num), 1.2, rmax=3.0, prio=5, name=f'J2.{num}')
        label_at(ctx, specs, 'TO J203', S, A(cx, cy - 4.2), 1.0, rmax=3.0, prio=4)
    # dock: title on the back, revision and adapter on the top
    ctx.logo = place_logo(ctx, 'B', A(-12.0, 5.0), heights=(7.0, 6.0), rmax=6.0)
    label_at(ctx, specs, 'NOVA DOCK', 'B', A(6.0, 4.0), 2.0, rmax=6.0, prio=6)
    label_at(ctx, specs, 'REV B · 2026-10', 'B', A(6.0, 7.4), 1.0, rmax=6.0, prio=5)
    label_at(ctx, specs, '12 V ≥ 2.5 A · 5.5×2.1 · centre +', 'F', A(10.0, -1.5), 1.0, rmax=6.0, prio=4)
    label_at(ctx, specs, 'NOVA DOCK · REV B', 'F', A(0.0, -10.5), 1.0, rmax=6.0, prio=3)
    return specs + common_specs(ctx, DOCK_FUNC, {})

def run(b, profile='main', verbose=True):
    ctx = Ctx(b)
    specs = {'main': main_content, 'head': head_content, 'dock': dock_content}[profile](ctx)
    placed, hidden = place_texts(ctx, specs)
    if verbose:
        print(f'silkscreen ({profile}): {placed} texts placed, {len(hidden)} hidden: {", ".join(hidden)}; logo {getattr(ctx, "logo", None)}')
    return placed, hidden
