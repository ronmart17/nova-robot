"""Head board Rev B: 76 × 74.9 mm, 2 layers, vertical at the front of the robot (rear face at Y = 52), standing on the
main board. All SMD on the F side (front). Local coordinates: x horizontal in front view, z upwards from the bottom edge.
KiCad absolute = (150 + x, 156 − z).

Front view, from the bottom:
- Central bottom notch (24 × 4 mm): the JST SH cable runs from J101 (F side, opening facing down) to the rear and on to
  J602 on the main board.
- H101/H102 (M3) at x = ±32, z = 10: angle brackets to the main board (HEAD_BRK, 4.5 mm behind the rear face).
- 2.0" ST7789 module (61.12 × 36.48 mm) in landscape, centred at z = 27, on an 8.5 mm female header: J102 (right) or
  J103 (left, DNP), pin 1 (GND) at the top in both.
- Raspberry Pi Camera Module 3 above the display, centred on x = 0, top edge at z = 72.4: 4 × M2 (21 × 12.5 mm),
  lens at z ≈ 58. Its 15-pin FPC leaves the module's bottom edge and passes to the rear through an 18 × 2 mm slot
  right below the module, then on to the Pi 5 CAM/DISP connector.
- VL53L1X ToF to the right of the camera at lens height; AT42QT1010 touch to the left, its electrode pad (TP101) near
  the top edge for the copper-tape electrode on top of the head."""
import os, sys, math, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from board import Board, read_netlist, rot, r4
from shapely.geometry import Polygon, Point, box, LineString
from shapely.ops import unary_union
import geom

CLI = '/opt/kicad10/bin/kicad-cli'
SCH = '/home/claude/robot/kicad/nova-head/nova-head.kicad_sch'
OUT = '/home/claude/robot/kicad/nova-head/nova-head.kicad_pcb'
SCR = '/tmp/claude-0/-home-claude/277a7080-1a17-5e2e-be8e-818ab51082a1/scratchpad/head'
CX, CZ = 150.0, 156.0
sys.path.insert(0, '/home/claude/robot/mech')
import dims as D
W, H = D.HEAD_W, round(D.HEAD_Z1 - D.HEAD_Z0, 2)          # 76 × 74.9
NOTCH_W, NOTCH_H = 24.0, 4.0
R_OUT, R_NOTCH_IN, R_NOTCH_OUT = 2.0, 1.0, 0.5
HOLE = (32.0, 10.0)                                        # M3 angle brackets (nut clears the main-board screw head)
LCD = (61.12, 36.48)
LCD_ZC = 27.0
HDR_X = 28.0
CAM_W, CAM_H, CAM_TOP = 25.0, 23.862, 72.4                 # Camera Module 3 PCB, top edge (opposite the FPC)
CAM_HOLES = [(-10.5, CAM_TOP - 2.0), (10.5, CAM_TOP - 2.0), (-10.5, CAM_TOP - 14.5), (10.5, CAM_TOP - 14.5)]
CAM_LENS_Z = CAM_TOP - 14.4
SLOT = (0.0, CAM_TOP - CAM_H - 1.55, 18.0, 2.0)            # FPC slot: centre x, centre z, length, width
TOF = (19.0, CAM_LENS_Z)
TOUCH = (-19.0, CAM_LENS_Z)

def A(x, z):
    return (r4(CX + x), r4(CZ - z))

def rounded(pts, radii):
    """Rectilinear polygon with rounded corners: returns [(type, points)] with 'line' (a, b) and 'arc' (a, m, b)
    in local coordinates, and the sampled polygon."""
    n = len(pts); prims = []; samp = []
    corners = []
    for k in range(n):
        P, V, N = pts[k - 1], pts[k], pts[(k + 1) % n]
        r = radii[k]
        din = ((V[0] - P[0]) / math.dist(P, V), (V[1] - P[1]) / math.dist(P, V))
        dout = ((N[0] - V[0]) / math.dist(V, N), (N[1] - V[1]) / math.dist(V, N))
        S = (V[0] - din[0] * r, V[1] - din[1] * r)
        E = (V[0] + dout[0] * r, V[1] + dout[1] * r)
        C = (S[0] + dout[0] * r, S[1] + dout[1] * r)
        d = math.dist(C, V)
        M = (C[0] + (V[0] - C[0]) * r / d, C[1] + (V[1] - C[1]) * r / d)
        corners.append((S, M, E, C, r))
    for k in range(n):
        S, M, E, C, r = corners[k]
        prims.append(('arc', (S, M, E)))
        a0 = math.atan2(S[1] - C[1], S[0] - C[0]); a1 = math.atan2(E[1] - C[1], E[0] - C[0])
        da = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
        for t in range(9):
            a = a0 + da * t / 8
            samp.append((C[0] + r * math.cos(a), C[1] + r * math.sin(a)))
        S2 = corners[(k + 1) % n][0]
        prims.append(('line', (E, S2)))
    return prims, Polygon(samp)

def outline(b):
    hw, nw = W / 2, NOTCH_W / 2
    pts = [(-hw, 0), (-nw, 0), (-nw, NOTCH_H), (nw, NOTCH_H), (nw, 0), (hw, 0), (hw, H), (-hw, H)]
    radii = [R_OUT, R_NOTCH_OUT, R_NOTCH_IN, R_NOTCH_IN, R_NOTCH_OUT, R_OUT, R_OUT, R_OUT]
    prims, poly = rounded(pts, radii)
    for kind, p in prims:
        if kind == 'line':
            b.edge_line(A(*p[0]), A(*p[1]))
        else:
            b.edge_arc(A(*p[0]), A(*p[1]), A(*p[2]))
    ab = Polygon([A(x, z) for x, z in poly.exterior.coords])
    sx, sz, sl, sw = SLOT
    r = sw / 2; h = sl / 2 - r
    b.edge_line(A(sx - h, sz + r), A(sx + h, sz + r)); b.edge_line(A(sx + h, sz - r), A(sx - h, sz - r))
    b.edge_arc(A(sx + h, sz + r), A(sx + h + r, sz), A(sx + h, sz - r))
    b.edge_arc(A(sx - h, sz - r), A(sx - h - r, sz), A(sx - h, sz + r))
    slot = LineString([A(sx - h, sz), A(sx + h, sz)]).buffer(r, 16)
    return ab.buffer(0).difference(slot)

class Placer:
    def __init__(self, b): self.b = b
    def P(self, ref, x, z, a=0, side='F'):
        p = A(x, z)
        return self.b.place(ref, p[0], p[1], a % 360, side)

def place_all(b):
    pc = Placer(b); P = pc.P
    # mechanics and connectors
    P('H101', -HOLE[0], HOLE[1]); P('H102', HOLE[0], HOLE[1])
    for ref, (x, z) in zip(('H103', 'H104', 'H105', 'H106'), CAM_HOLES):
        P(ref, x, z)
    P('J101', 0.0, 7.35, 0)
    z1 = LCD_ZC + 3.5 * 2.54
    P('J102', HDR_X, z1, 0); P('J103', -HDR_X, z1, 0)
    # connector decoupling
    P('C101', -9.6, 12.4, 90); P('C102', -7.6, 12.4, 90)
    # display reset (centre, under the module)
    P('R101', -1.2, 25.5, 90); P('C103', 1.2, 25.5, 90)
    # backlight (bottom right, under the module)
    P('Q102', 13.5, 13.5, 0); P('Q101', 20.5, 13.5, 0)
    P('R103', 10.0, 13.5, 0); P('R104', 13.5, 10.6, 0)
    P('R102', 20.5, 17.0, 0); P('R109', 23.6, 11.0, 90)
    # ToF to the right of the camera, at lens height
    tx, tz = TOF
    P('U101', tx, tz, 0)
    P('C104', tx - 4.4, tz + 1.2, 180); P('C105', tx - 4.2, tz - 0.4, 180); P('C106', tx - 4.2, tz - 1.6, 180)
    P('R106', tx + 4.2, tz + 1.0, 180); P('R105', tx + 4.2, tz - 1.0, 180)
    # touch controller to the left of the camera, electrode pad near the top edge
    ux, uz = TOUCH
    P('U103', ux, uz, 0)
    P('C108', ux + 3.4, uz, 0); P('C109', ux, uz - 2.6, 0); P('R108', ux, uz + 3.0, 0)
    P('TP101', ux, uz + 10.5, 0)

def mechanics():
    keep = []
    for s in (-1, 1):
        x, z = s * HOLE[0], HOLE[1]
        c = Point(*A(x, z))
        # M3 screw head (Ø5.5) at the front and angle bracket at the back
        keep.append(('screw head M3', c.buffer(3.0, 32), 'FB', ('H101', 'H102')))
    for x, z in CAM_HOLES:
        # M2 standoff (front, Ø4) and screw head (rear, Ø3.8)
        keep.append(('camera standoff M2', Point(*A(x, z)).buffer(2.2, 32), 'FB', ('H103', 'H104', 'H105', 'H106')))
    # camera module body (2.5 mm standoffs): nothing on the front side under the module
    x0, z0 = A(-CAM_W / 2, CAM_TOP); x1, z1 = A(CAM_W / 2, CAM_TOP - CAM_H)
    keep.append(('camera module', box(x0, z0, x1, z1), 'F', ('H103', 'H104', 'H105', 'H106')))
    # LCD module: no components taller than ~8 mm (the female header is 8.5 mm); marked on silkscreen only
    return keep

def build(check=True):
    os.makedirs(SCR, exist_ok=True)
    xml = os.path.join(SCR, 'head.xml')
    subprocess.run([CLI, 'sch', 'export', 'netlist', '--format', 'kicadxml', '-o', xml, SCH], check=True, capture_output=True)
    comps, nets = read_netlist(xml)
    b = Board('nova-head', comps, nets, layers=2, title='NOVA — Head board', rev='B',
              date='2026-10-28', company='ronmart · Caril Ronnie Martínez Vera', aux=(CX - W / 2, CZ))
    board_poly = outline(b)
    keep = mechanics()
    place_all(b)
    issues = []
    if check:
        issues = geom.check_placement(b, board_poly, keep)
        unplaced = sorted(r for r, c in b.comps.items() if c.footprint and r not in b.placed)
        print('unplaced:', unplaced)
    return b, board_poly, keep, issues

if __name__ == '__main__':
    build()
