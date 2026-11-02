"""Main board Rev B: 136 × 136 mm rounded square (R30) with wheel cut-outs, mechanics, placement, tracks and zones.
Local coordinates: origin at the board centre, +y towards the rear (front = −y). KiCad absolute = (150 + x, 100 + y)."""
import os, sys, math, subprocess, tempfile, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from board import Board, read_netlist, rot, r4
from shapely.geometry import Polygon, Point, box, LineString
from shapely.ops import unary_union
import geom, preview

CLI = '/opt/kicad10/bin/kicad-cli'
SCH = '/home/claude/robot/kicad/nova-main/nova-main.kicad_sch'
OUT = '/home/claude/robot/kicad/nova-main/nova-main.kicad_pcb'
SCR = '/tmp/claude-0/-home-claude/277a7080-1a17-5e2e-be8e-818ab51082a1/scratchpad/pcb'
CX, CY = 150.0, 100.0

# ------------------------------------------------------------------ mechanics (mm, local coordinates)
sys.path.insert(0, '/home/claude/robot/mech')
import dims as D
# KiCad local frame: (x, y) = (X, -Y) of the robot frame (front of the robot = -y)
def RB(X, Y): return (X, -Y)
HW = D.MB_W / 2                # half width of the rounded-square outline
RC = D.MB_R                    # corner radius
WX, WY = D.WCUT_X, D.WCUT_Y    # wheel cut-out: |x| >= WX and |y| <= WY
FIL = 1.0                      # inner fillet of the cut-out
NOTCH = (55.6, 37.5)           # J702 plug notch (robot frame): X >= 55.6 for Y from the wheel cut-out (WCUT_Y) to 37.5;
                               # the edge sits 0.65 mm past the front shell tabs, the receptacle overhangs it by 1.05 mm
BAT = (-D.BAT_X - 0.6, -D.BAT_Y1 - 0.6, D.BAT_X + 0.6, -D.BAT_Y0 + 0.6)   # pack footprint (local), + 0.6 mm margin
BRK_X, BRK_Y, BRK_SLOT = D.BRK_X, D.BRK_Y, D.BRK_SLOT
MOTOR = D.MOTOR_X
CASTER = RB(0.0, D.CASTER_Y)
CASTER_DX, CASTER_SLOT = D.CASTER_DX, 8.2
HEAD_Y0, HEAD_Y1 = -(D.HEAD_Y0 + D.HEAD_T), -D.HEAD_Y0      # vertical head board (front / rear face)
HEAD_W = D.HEAD_W

def A(x, y):
    return (r4(CX + x), r4(CY + y))

def L(p):
    return (p[0] - CX, p[1] - CY)

# ------------------------------------------------------------------ outline
def outline(b):
    """Rounded square HW x HW with the two wheel cut-outs (filleted inner corners)."""
    segs = []
    f = FIL
    k = 0.70710678
    def arc_corner(cx, cy, r, a0):
        a1 = a0 + math.pi / 2; am = a0 + math.pi / 4
        return ((cx + r * math.cos(a0), cy + r * math.sin(a0)), (cx + r * math.cos(am), cy + r * math.sin(am)),
                (cx + r * math.cos(a1), cy + r * math.sin(a1)))
    c = HW - RC
    # corners (local coords, y down): top-left (-c,-c) ... go clockwise on screen
    corners = {'tl': arc_corner(-c, -c, RC, math.pi), 'tr': arc_corner(c, -c, RC, -math.pi / 2),
               'br': arc_corner(c, c, RC, 0.0), 'bl': arc_corner(-c, c, RC, math.pi / 2)}
    for key in ('tl', 'tr', 'br', 'bl'):
        s_, m_, e_ = corners[key]
        b.edge_arc(A(*s_), A(*m_), A(*e_))
    b.edge_line(A(-c, -HW), A(c, -HW))            # front edge
    b.edge_line(A(c, HW), A(-c, HW))              # rear edge
    for s in (1, -1):
        # side edge with the wheel cut-out: from the front corner down to the cut-out, around it, to the rear corner
        p_top = (s * HW, -c); p_cut0 = (s * HW, -WY)
        if s == 1:
            # notch for the right-angle USB-C plug into J702 (the plug overmold drops below the board top)
            n0, nx, fr, fo = -NOTCH[1], NOTCH[0], 1.0, 1.0
            b.edge_line(A(HW, -c), A(HW, n0))
            b.edge_line(A(HW, n0), A(nx + fr, n0))
            b.edge_arc(A(nx + fr, n0), A(nx + fr - fr * k, n0 + fr - fr * k), A(nx, n0 + fr))
            b.edge_line(A(nx, n0 + fr), A(nx, -WY - fo))
            # convex corner where the notch meets the wheel cut-out
            b.edge_arc(A(nx, -WY - fo), A(nx - fo + fo * k, -WY - fo + fo * k), A(nx - fo, -WY))
            b.edge_line(A(nx - fo, -WY), A(WX + f, -WY))
        else:
            b.edge_line(A(*p_top), A(*p_cut0))
        p1 = (s * HW, -WY); p2 = (s * (WX + f), -WY)
        if s == -1:
            b.edge_line(A(*p1), A(*p2))
        m = (s * (WX + f) - s * f * k, -WY + f - f * k)
        b.edge_arc(A(*p2), A(*m), A(s * WX, -WY + f))
        p3 = (s * WX, -WY + f); p4 = (s * WX, WY - f)
        b.edge_line(A(*p3), A(*p4))
        m = (s * (WX + f) - s * f * k, WY - f + f * k)
        b.edge_arc(A(*p4), A(*m), A(s * (WX + f), WY))
        p5 = (s * (WX + f), WY); p6 = (s * HW, WY)
        b.edge_line(A(*p5), A(*p6))
        b.edge_line(A(s * HW, WY), A(s * HW, c))
    sq = box(CX - HW, CY - HW, CX + HW, CY + HW)
    rr = box(CX - c, CY - c, CX + c, CY + c).buffer(RC, 64, join_style=1)
    poly = rr.intersection(sq)
    nx, n0, fo = NOTCH[0], -NOTCH[1], 1.0
    notch = box(CX + nx, CY + n0, CX + HW + 1, CY - WY + 0.01)
    corner = box(CX + nx - fo, CY - WY - fo, CX + nx, CY - WY + 0.01).difference(Point(CX + nx - fo, CY - WY - fo).buffer(fo, 32))
    notch = notch.union(corner)
    cut = unary_union([box(CX + WX, CY - WY, CX + HW + 1, CY + WY), box(CX - HW - 1, CY - WY, CX - WX, CY + WY), notch])
    poly = poly.difference(cut)
    segs.append(('poly', list(poly.exterior.coords)))
    return poly, segs

def slot(b, c, length, width, angle=0):
    """Internal slot on Edge.Cuts. angle=0: long axis along X. Returns the absolute polygon."""
    r = width / 2; h = length / 2 - r
    ca, sa = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    def T(x, y):
        return A(c[0] + x * ca - y * sa, c[1] + x * sa + y * ca)
    b.edge_line(T(-h, -r), T(h, -r)); b.edge_line(T(h, r), T(-h, r))
    b.edge_arc(T(h, -r), T(h + r, 0), T(h, r)); b.edge_arc(T(-h, r), T(-h - r, 0), T(-h, -r))
    return LineString([T(-h, 0), T(h, 0)]).buffer(r, 16)

def R_(x0, y0, x1, y1):
    """Local rectangle → absolute polygon."""
    return box(CX + min(x0, x1), CY + min(y0, y1), CX + max(x0, x1), CY + max(y0, y1))

def C_(x, y, r):
    return Point(CX + x, CY + y).buffer(r, 32)

def mechanics(b):
    """Slots and mechanical zones. Returns (slots, footprint keepout zones)."""
    slots = []
    keep = []      # (name, polygon, sides, exempt refs)
    # motor brackets (bottom side)
    for s in (1, -1):
        for bx in BRK_X:
            for sy in (1, -1):
                slots.append(slot(b, (s * bx, sy * BRK_Y), BRK_SLOT, 2.2, 90))
                keep.append(('screw head M2 (motor bracket)', R_(s * bx - 2.9, sy * BRK_Y - 3.9, s * bx + 2.9, sy * BRK_Y + 3.9), 'F', ()))
        keep.append(('N20 motor and brackets', unary_union([R_(s * MOTOR[0], -6.5, s * MOTOR[1], 6.5)] +
                     [R_(s * (bx - 5.75), -12.8, s * (bx + 5.75), 12.8) for bx in BRK_X]), 'B', ()))
        # wheel: protrudes ~14 mm above the board at |y| <= ~16
        keep.append(('wheel', R_(s * (WX - 1.0), -18.0, s * (WX + 0.01), 18.0), 'FB', ()))
    # caster (bottom)
    for s in (1, -1):
        slots.append(slot(b, (CASTER[0] + s * CASTER_DX, CASTER[1]), CASTER_SLOT, 2.2, 0))
        keep.append(('screw head M2 (caster)', R_(s * CASTER_DX - 6.6, CASTER[1] - 2.6, s * CASTER_DX + 6.6, CASTER[1] + 2.6), 'F', ()))
    keep.append(('caster', R_(-12.5, CASTER[1] - 8.0, 12.5, CASTER[1] + 8.0), 'B', ()))
    # 2S pack on top: no components underneath (tracks and tented vias are fine)
    keep.append(('2S pack', R_(*BAT), 'F', ()))
    # head board resting on the main board
    keep.append(('head board', R_(-HEAD_W / 2, HEAD_Y0, HEAD_W / 2, HEAD_Y1), 'F', ()))
    # Pi standoffs (M2.5 hex, Ø 5.2 across corners) and their nuts/washers underneath
    for u, v in D.PI_HOLES_UV:
        X, Y = D.pi_xy(u, v)
        keep.append(('Pi standoff', C_(X, -Y, 3.4), 'FB', ('H5', 'H6', 'H7', 'H8')))
    # shell screws (M3 from below) and head brackets
    for X, Y in D.SHELL_HOLES:
        keep.append(('shell screw', C_(X, -Y, 3.6), 'FB', ('H1', 'H2', 'H3', 'H4')))
    for X, Y in D.HEAD_BRK:
        keep.append(('head bracket', R_(X - 4.5, -Y - 4.5, X + 4.5, -Y + 4.5), 'F', ('H9', 'H10')))
    # right-angle USB-C plug into J702 (towards +X) and its cable rising to the Pi
    return slots, keep

# ------------------------------------------------------------------ placement
class Placer:
    def __init__(self, b):
        self.b = b

    def P(self, ref, x, y, a=0, side='F'):
        return self.b.place(ref, r4(CX + x), r4(CY + y), a % 360, side)

    def pad(self, ref, num):
        x, y = self.b.placed[ref].pad(num)
        return (x - CX, y - CY)

    def two(self, ref, c, a=0, side='F'):
        """2-pad part centred at c (the origin of 2-pad footprints is at their centre)."""
        return self.P(ref, c[0], c[1], a, side)

    def centroid(self, ref, x, y, a=0, side='F'):
        """Place so that the centre of the numbered pads lands at (x, y)."""
        pl = self.P(ref, 0, 0, a, side)
        ps = [p for p in pl.pads if p['num']]
        xs, ys = [], []
        for p in ps:
            ly = -p['y'] if side == 'B' else p['y']
            dx, dy = rot(p['x'], ly, a); xs.append(dx); ys.append(dy)
        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        return self.P(ref, x - mx, y - my, a, side)

def place_all(b):
    import main_place
    main_place.place_all(b, Placer, D)

def build(preview_png=None, check=True):
    os.makedirs(SCR, exist_ok=True)
    xml = os.path.join(SCR, f'main_{os.getpid()}.xml')     # one file per process (variants run in parallel)
    subprocess.run([CLI, 'sch', 'export', 'netlist', '--format', 'kicadxml', '-o', xml, SCH], check=True, capture_output=True)
    comps, nets = read_netlist(xml)
    os.remove(xml)
    b = Board('nova-main', comps, nets, layers=4, title='NOVA — Main board (chassis)', rev='B',
              date='2026-10-28', company='ronmart · Caril Ronnie Martínez Vera')
    board_poly, segs = outline(b)
    slots, keep = mechanics(b)
    for s in slots: segs.append(('poly', list(s.exterior.coords)))
    global outline_segs_cache
    outline_segs_cache = (board_poly, segs)
    place_all(b)
    usable = board_poly.difference(unary_union(slots))
    issues = []
    # keepout zones defined inside the footprints (ESP32 antenna): all layers, both sides
    from sx import kids, kid
    for ref, pl in b.placed.items():
        for z in kids(pl.node, 'zone'):
            pts = [(float(xy[1]), float(xy[2])) for xy in kids(kid(kid(z, 'polygon'), 'pts'), 'xy')]
            keep.append((f'antenna {ref}', Polygon(pts), 'FB', (ref,)))
    if check:
        issues = geom.check_placement(b, usable, keep, allow_outside=('J201', 'U401', 'SW301', 'J702'))
        if 'U401' in b.placed:
            body = geom.courtyard(b.placed['U401']).intersection(R_(-66.6, -45.1, -40.9, -26.9))
            print('ESP32 body outside the board: %.2f mm²' % body.difference(usable).area)
        unplaced = sorted(r for r, c in b.comps.items() if c.footprint and r not in b.placed)
        print('unplaced:', unplaced)
    if preview_png:
        def deco(ax):
            from matplotlib.patches import Rectangle, Polygon as MP
            for name, kp, sides, ex in keep:
                for g in getattr(kp, 'geoms', [kp]):
                    col = '#2a9d2a' if 'pack' in name else ('#d1491f' if sides == 'B' else '#999999')
                    ax.add_patch(MP(list(g.exterior.coords), closed=True, fill=False, ec=col, lw=0.6, ls=':'))
            x0, y0, x1, y1 = BAT
            ax.text(*A((x0 + x1) / 2, (y0 + y1) / 2), '2S PACK (on top)', color='#2a9d2a', ha='center', fontsize=9)
            ax.add_patch(Rectangle(A(-HEAD_W / 2, HEAD_Y0), HEAD_W, HEAD_Y1 - HEAD_Y0, fc='#7a3db8', alpha=0.25, ec='#7a3db8'))
        preview.draw(b, preview_png, segs, extra=[deco], title='nova-main — placement')
    return b, usable, keep, issues

if __name__ == '__main__':
    png = sys.argv[1] if len(sys.argv) > 1 else os.path.join(SCR, 'place.png')
    build(png)
