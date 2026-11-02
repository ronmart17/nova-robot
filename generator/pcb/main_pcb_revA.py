"""Main board Rev A: Ø120 mm outline with wheel cutouts, mechanics, placement, tracks and zones.
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
SCR = '/tmp/claude-0/-home-claude/20eabc81-f669-53cb-a2b0-f93a4a522b2a/scratchpad/pcb'
CX, CY = 150.0, 100.0

# ------------------------------------------------------------------ mechanics (mm, local coordinates)
R = 60.0                       # board radius
WY, WX = 21.0, 46.5            # wheel cutout: |y| <= WY and |x| >= WX (34 mm wheel: 31.4 mm chord in the board plane)
FIL = 1.0                      # inner fillet of the cutout
BAT = (-35.0, -31.5, 35.0, 6.5)                 # 2S pack (2×18650 side by side, in parallel) on top
STRAP_X, STRAP_Y, STRAP_L, STRAP_W = 40.5, -18.5, 12.5, 2.5   # slots for the pack strap
BRK_X = (28.0, 40.75)          # N20 brackets (U clamp 25×11×11): on the motor can and on the gearbox
BRK_Y, BRK_SLOT = 9.65, 4.0    # ears at ±9.65 mm from the axle (M2), 4 mm slot along y
MOTOR = (14.5, 45.5)           # motor extent in |x| (encoder → gearbox face), |y| <= 6
CASTER = (0.0, -43.0)          # caster (bottom side)
CASTER_DX, CASTER_SLOT = 8.25, 8.2
HEAD_Y0, HEAD_Y1 = -47.6, -46.0   # vertical head board (front / rear face)
HEAD_W = 70.0

def A(x, y):
    return (r4(CX + x), r4(CY + y))

def L(p):
    return (p[0] - CX, p[1] - CY)

# ------------------------------------------------------------------ outline
def outline(b):
    segs = []
    xcut = math.sqrt(R * R - WY * WY)
    f = FIL
    for s in (1, -1):
        p1 = (s * xcut, -WY); p2 = (s * (WX + f), -WY)
        b.edge_line(A(*p1), A(*p2))
        m = (s * (WX + f) - s * f * 0.70710678, -WY + f - f * 0.70710678)
        b.edge_arc(A(*p2), A(*m), A(s * WX, -WY + f))
        p3 = (s * WX, -WY + f); p4 = (s * WX, WY - f)
        b.edge_line(A(*p3), A(*p4))
        m = (s * (WX + f) - s * f * 0.70710678, WY - f + f * 0.70710678)
        b.edge_arc(A(*p4), A(*m), A(s * (WX + f), WY))
        p5 = (s * (WX + f), WY); p6 = (s * xcut, WY)
        b.edge_line(A(*p5), A(*p6))
    b.edge_arc(A(xcut, WY), A(0, R), A(-xcut, WY))
    b.edge_arc(A(-xcut, -WY), A(0, -R), A(xcut, -WY))
    # polygon (absolute coordinates)
    disc = Point(CX, CY).buffer(R, 256)
    cut = unary_union([box(CX + WX, CY - WY, CX + R + 1, CY + WY), box(CX - R - 1, CY - WY, CX - WX, CY + WY)])
    poly = disc.difference(cut)
    for gg in getattr(poly, 'geoms', [poly]):
        segs.append(('poly', list(gg.exterior.coords)))
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

def mechanics(b):
    """Slots and mechanical zones. Returns (slots, footprint keepout zones)."""
    slots = []
    keep = []      # (name, polygon, sides, exempt refs)
    # motor brackets
    for s in (1, -1):
        for bx in BRK_X:
            for sy in (1, -1):
                slots.append(slot(b, (s * bx, sy * BRK_Y), BRK_SLOT, 2.2, 90))
                keep.append(('screw head M2 (motor bracket)', R_(s * bx - 2.9, sy * BRK_Y - 3.9, s * bx + 2.9, sy * BRK_Y + 3.9), 'F', ()))
        keep.append(('N20 motor and brackets', unary_union([R_(s * MOTOR[0], -6.5, s * MOTOR[1], 6.5)] +
                     [R_(s * (bx - 5.75), -12.8, s * (bx + 5.75), 12.8) for bx in BRK_X]), 'B', ()))
        # wheel cutout: the wheel protrudes ~9 mm above the board at |y| <= 15.7
        keep.append(('wheel', R_(s * (WX - 1.0), -17.0, s * (WX + 0.01), 17.0), 'FB', ()))
    # caster
    for s in (1, -1):
        slots.append(slot(b, (CASTER[0] + s * CASTER_DX, CASTER[1]), CASTER_SLOT, 2.2, 0))
        keep.append(('screw head M2 (caster)', R_(s * CASTER_DX - 6.6, CASTER[1] - 2.6, s * CASTER_DX + 6.6, CASTER[1] + 2.6), 'F', ()))
    keep.append(('caster', R_(-12.5, CASTER[1] - 8.0, 12.5, CASTER[1] + 8.0), 'B', ()))
    # pack strap
    for s in (1, -1):
        slots.append(slot(b, (s * STRAP_X, STRAP_Y), STRAP_L, STRAP_W, 90))
        keep.append(('pack strap', R_(s * 34.0, STRAP_Y - STRAP_L / 2 - 0.8, s * (STRAP_X + 2.2), STRAP_Y + STRAP_L / 2 + 0.8), 'F', ()))
    keep.append(('pack strap', R_(-STRAP_X - 2.2, STRAP_Y - STRAP_L / 2 - 0.8, STRAP_X + 2.2, STRAP_Y + STRAP_L / 2 + 0.8), 'B', ()))
    # 2S pack on top: no components underneath (tracks and tented vias are fine)
    keep.append(('2S pack', R_(*BAT), 'F', ()))
    # head board resting on the main board
    keep.append(('head board', R_(-HEAD_W / 2, HEAD_Y0, HEAD_W / 2, HEAD_Y1), 'F', ()))
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
    import blocks as BK
    pc = Placer(b); P = pc.P; T = pc.two
    # ===== holes: head board brackets (H1/H2) and front holes for cover/bumper (H3/H4)
    P('H1', -31.0, -41.0); P('H2', 31.0, -41.0); P('H3', -40.0, -33.0); P('H4', 40.0, -33.0)
    # ===== motors: TB6612 behind the pack, connectors (bottom side) behind the motors
    BK.put(pc, BK.motor_driver(), (0.0, 13.5))
    pc.centroid('J501', -9.5, 20.0, 0, 'B'); pc.centroid('J502', 9.5, 20.0, 0, 'B')
    for i, ref in enumerate(['R501', 'R502', 'C506', 'R503', 'R504', 'C507']):
        T(ref, (-15.4 + 1.25 * i, 16.8), 90)
    for i, ref in enumerate(['R505', 'R506', 'C508', 'R507', 'R508', 'C509']):
        T(ref, (8.4 + 1.25 * i, 16.8), 90)
    T('C510', (-17.4, 16.8), 90)
    # ===== IMU next to the turning axis
    P('U601', -10.0, 9.0, 0)
    T('C601', (-13.2, 8.6), 90); T('C602', (-13.2, 10.6), 90)
    # ===== regulators (centre-rear): 5 V on the left, 3V3 on the right
    BK.put(pc, BK.buck('U302', 'L301', 'C301', 'C302', 'C304', 'C303', 'R301', 'R302', 'C305', 'C306', 'C307'), (4.4, 28.4))
    BK.put(pc, BK.buck('U303', 'L302', 'C308', 'C309', 'C311', 'C310', 'R303', 'R304', 'C312', 'C313', 'C314'), (17.1, 28.4))
    T('R306', (9.4, 23.9), 0); T('R307', (12.0, 23.9), 0)
    # ===== charger (rear right)
    BK.put(pc, BK.charger(), (27.6, 35.2))
    P('J202', 28.0, 46.5, 0)
    # ===== battery: connector (pin 1 = BAT− at the front), switch, fuse and protector
    P('J301', 41.2, 16.2, 270)
    P('SW301', 48.05, 25.5, 90)
    T('F301', (41.2, 28.9), 270)
    P('Q301', 33.8, 16.4, 180); P('Q302', 33.8, 20.8, 180)
    P('U301', 29.4, 16.6, 0)
    T('C315', (25.8, 16.0), 90); T('C316', (25.8, 18.4), 90)
    T('R305', (24.4, 16.0), 90); T('R308', (24.4, 18.4), 90); T('R309', (29.4, 19.8), 0)
    P('TP307', 33.0, 12.4); P('TP302', 45.6, 32.4)
    P('TP306', 17.0, 21.6); P('TP301', 20.2, 22.0); P('TP303', -5.0, 24.6); P('TP304', 23.0, 22.0); P('TP305', 25.8, 22.0)
    # ===== rear USB-C and input protection
    P('J201', 0.0, 56.6, 0)
    P('U201', -3.4, 46.2, 90)
    T('R201', (-4.0, 49.9), 90); T('R202', (6.2, 52.4), 90)
    T('D201', (9.2, 53.2), 180)
    T('R213', (7.6, 49.8), 0); T('C214', (11.8, 49.8), 0)
    T('C201', (12.6, 43.65), 180)       # LM66200 VIN1 input (datasheet: input and output caps next to the IC)
    T('R215', (3.0, 44.6), 90); T('R216', (3.0, 41.8), 90)
    P('U202', 15.4, 43.4, 0)
    T('R205', (-0.8, 41.6), 0); T('R206', (-0.8, 40.6), 0)
    # charging dock: pogo pads on the bottom side
    P('TP201', 15.0, 49.6, 0, 'B'); P('TP202', 24.0, 49.6, 0, 'B')
    T('D202', (19.4, 46.8), 0); T('R214', (16.2, 53.2), 0); T('C215', (20.8, 53.0), 0)
    T('C203', (18.2, 43.65), 0); T('C202', (16.4, 41.3), 0);   # LM66200 VIN2 input and output
    T('R203', (22.6, 50.0), 90); T('R204', (23.9, 50.0), 90)
    # ===== ESP32-S3 (antenna towards the rear, left of the USB-C)
    P('U401', -30.0, 32.3, 180)
    T('C402', (-18.9, 36.9), 270); T('C401', (-17.0, 37.3), 270)
    T('R401', (-18.9, 35.0), 180); T('C403', (-14.4, 36.6), 270)
    T('R404', (-18.6, 28.67), 0); T('R405', (-18.6, 27.40), 0); T('R406', (-18.6, 26.13), 0); T('R407', (-18.6, 24.86), 0)
    T('R402', (-28.1, 17.4), 90); T('R403', (-29.4, 15.4), 90)
    P('SW402', -42.65, 17.0, 90); P('SW401', -42.65, 22.9, 90)
    P('J401', -45.3, 27.6, 0)
    P('TP401', -36.4, 15.6); P('TP402', -33.4, 15.6)
    T('R603', (-42.0, 36.4), 0); T('C603', (-42.0, 37.6), 0); T('R606', (-42.0, 34.0), 0); T('C604', (-42.0, 35.2), 0)
    # ===== TCA9535 expander and I2C/IRQ resistors
    P('U402', -12.4, 31.4, 0)
    for i, ref in enumerate(['R418', 'R417', 'R416', 'R415', 'R414', 'R413']):
        T(ref, (-6.6, 29.55 + 1.0 * i), 0)
    for i, ref in enumerate(['R408', 'R409', 'R410', 'R411', 'R419', 'R420']):
        T(ref, (-13.0 + 1.2 * i, 37.4), 90)
    T('C404', (-14.6, 26.0), 90)
    T('D401', (-9.0, 25.6), 180); T('R412', (-11.6, 25.6), 0)
    # ===== head board, audio and cliff sensors (in front of the pack)
    P('J602', 0.0, -35.0, 180)
    T('C609', (13.0, -33.6), 90)
    P('U604', -23.5, -37.6, 0)
    T('C605', (-25.6, -34.5), 0); T('C606', (-22.9, -34.5), 0); T('R609', (-26.95, -37.85), 180)
    T('FB601', (-19.0, -36.6), 0); T('FB602', (-19.0, -38.4), 0)
    P('J601', -15.3, -35.9, 90)
    pc.centroid('U602', -18.5, -51.6, 0, 'B'); pc.centroid('U603', 18.5, -51.6, 0, 'B')
    P('Q601', 21.0, -38.4, 0)
    T('R607', (17.8, -37.4), 90); T('R608', (17.8, -40.0), 90)
    T('R601', (-22.5, -43.5), 0); T('R604', (22.5, -43.5), 180)
    T('R602', (-19.0, -43.5), 0); T('R605', (19.0, -43.5), 180)
    # ===== fiducials
    P('FID1', -44.0, -26.0); P('FID2', 44.0, -27.0); P('FID3', -3.0, 38.4)

def build(preview_png=None, check=True):
    os.makedirs(SCR, exist_ok=True)
    xml = os.path.join(SCR, f'main_{os.getpid()}.xml')     # one file per process (variants run in parallel)
    subprocess.run([CLI, 'sch', 'export', 'netlist', '--format', 'kicadxml', '-o', xml, SCH], check=True, capture_output=True)
    comps, nets = read_netlist(xml)
    os.remove(xml)
    b = Board('nova-main', comps, nets, layers=4, title='NOVA — Main board (chassis)', rev='A',
              date='2026-10-25', company='ronmart · Caril Ronnie Martínez Vera')
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
        issues = geom.check_placement(b, usable, keep, allow_outside=('J201', 'U401'))
        body = geom.courtyard(b.placed['U401']).intersection(R_(-39.75, 18.85, -20.25, 45.6))
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
