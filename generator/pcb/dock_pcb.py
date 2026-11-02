"""Charging dock Rev B: one 2-layer PCB with two parts joined by two break-away tabs (MB1, MB2).

Dock board (58 × 34 mm + a 14.5 × 23.4 mm tail through the dock back wall, components on top): 12 V barrel jack J1 on the tail behind the wall, PTC F1,
reverse-polarity P-MOSFET Q1 (D2 clamps VGS, R1 pulls the gate down), TVS D1, bulk C1/C2, LED D3 at the front edge and two
pogo pairs (P1/P3 = +12 V, P2/P4 = GND; 16 mm between polarities, 5 mm within a pair).

Robot contact plate (42 × 18 mm, break-away): two 8 × 12 mm ENIG pads on F (facing the floor once mounted under the
robot) and J2 (JST XH, B side, facing the robot) for the 2-wire lead to J203 on the main board. Mounted face down, its
F side seen from above is mirrored, so the +12 V pad is at local x = +8 to land on the +12 V pogo pair (dock x = −8).

Local frame (both parts): x to the right, y towards the dock's back wall = robot rear when docked. KiCad absolute =
(150 + x, 100 + y). Same convention as the main board: (x, y) = (X, −Y) of the robot frame."""
import os, sys, math, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from board import Board, read_netlist, r4
from shapely.geometry import Polygon, Point, box, LineString
import geom
from head_pcb import rounded

CLI = '/opt/kicad10/bin/kicad-cli'
SCH = '/home/claude/robot/kicad/nova-dock/nova-dock.kicad_sch'
OUT = '/home/claude/robot/kicad/nova-dock/nova-dock.kicad_pcb'
SCR = '/tmp/claude-0/-home-claude/277a7080-1a17-5e2e-be8e-818ab51082a1/scratchpad/dock'
CX, CY = 150.0, 100.0
DW, DH = 58.0, 34.0                         # dock board
PX0, PX1, PH = -74.0, -32.0, 18.0           # contact plate x range and height (42 × 18 mm)
PC = ((PX0 + PX1) / 2, 0.0)                 # plate centre
TAB_Y = 5.0                                 # tab centres at y = ±5, 5 mm wide, 3 mm long
TAIL = (-7.0, 7.5, 40.4)                    # tail through the dock back wall carrying J1 behind it (x0, x1, y end)
POGO = [(-8.0, -2.5), (-8.0, 2.5), (8.0, -2.5), (8.0, 2.5)]     # P1, P3 (+12 V), P2, P4 (GND); centre = plate centre
PAD_DX = 8.0                                # plate pads at plate centre ± 8 (16 mm)

def A(x, y):
    return (r4(CX + x), r4(CY + y))

def outline(b):
    hw, hh, ph = DW / 2, DH / 2, PH / 2
    t0, t1 = TAB_Y - 2.5, TAB_Y + 2.5
    tx0, tx1, ty = TAIL
    pts = [(-hw, -hh), (hw, -hh), (hw, hh), (tx1, hh), (tx1, ty), (tx0, ty), (tx0, hh), (-hw, hh), (-hw, t1), (PX1, t1),
           (PX1, ph), (PX0, ph), (PX0, -ph), (PX1, -ph), (PX1, -t1), (-hw, -t1)]
    radii = [2.0, 2.0, 2.0, 1.0, 1.0, 1.0, 1.0, 2.0, 0.5, 0.5, 0.75, 1.5, 1.5, 0.75, 0.5, 0.5]
    prims, poly = rounded(pts, radii)
    for kind, p in prims:
        if kind == 'line': b.edge_line(A(*p[0]), A(*p[1]))
        else: b.edge_arc(A(*p[0]), A(*p[1]), A(*p[2]))
    # slot between the two tabs (3 × 5 mm)
    sl = [(PX1, -t0), (-hw, -t0), (-hw, t0), (PX1, t0)]
    sprims, spoly = rounded(sl, [0.5] * 4)
    for kind, p in sprims:
        if kind == 'line': b.edge_line(A(*p[0]), A(*p[1]))
        else: b.edge_arc(A(*p[0]), A(*p[1]), A(*p[2]))
    ab = Polygon([A(x, y) for x, y in poly.exterior.coords]).buffer(0)
    sab = Polygon([A(x, y) for x, y in spoly.exterior.coords]).buffer(0)
    return ab.difference(sab)

class Placer:
    def __init__(self, b): self.b = b
    def P(self, ref, x, y, a=0, side='F'):
        p = A(x, y)
        return self.b.place(ref, p[0], p[1], a % 360, side)

def place_all(b):
    pc = Placer(b); P = pc.P
    hw, hh = DW / 2, DH / 2
    # dock board: holes, pogo pins
    for ref, (x, y) in zip(('H1', 'H2', 'H3', 'H4'), ((-25.5, -13.0), (25.5, -13.0), (-25.5, 13.0), (25.5, 13.0))):
        P(ref, x, y)
    for ref, (x, y) in zip(('P1', 'P3', 'P2', 'P4'), POGO):
        P(ref, x, y)
    # 12 V jack on the tail behind the back wall (front face 0.6 mm inside the tail end); protection chain along y = 9.6 towards the left,
    # then up to the +12 V pogo pair; GND returns through the pours on both layers
    P('J1', 0.0, TAIL[2] - 0.6 - 13.6, 90)          # on the tail, behind the dock back wall (out of the robot's reach)
    P('F1', 3.0, 9.6, 180)
    P('Q1', -3.2, 9.6, 270)                     # drain (input) at the bottom, source (out) top left, gate top right
    P('D2', -3.2, 6.2, 0); P('R1', 0.7, 6.2, 0)  # VGS clamp across S–G above Q1, gate pull-down
    P('D1', -8.6, 9.6, 270)                     # VDOCK_OUT pads on top (towards the +12 V pogo pair), GND below
    P('C1', -12.4, 9.6, 270); P('C2', -14.8, 9.6, 270)
    # power LED at the front edge, centred (light pipe in the housing)
    P('D3', 0.0, -hh + 2.6, 0); P('R2', -2.6, -hh + 2.6, 180)
    # break-away tabs
    P('MB1', (PX1 - hw) / 2, -TAB_Y, 0); P('MB2', (PX1 - hw) / 2, TAB_Y, 0)
    # contact plate: +12 V pad at local +8 (mounted face down), GND at −8, J2 on the back, M3 at the ends
    cx, cy = PC
    P('TP1', cx + PAD_DX, cy, 0); P('TP2', cx - PAD_DX, cy, 0)
    P('J2', cx + 1.25, cy - 1.0, 180, 'B')
    P('H5', cx - 17.0, cy); P('H6', cx + 17.0, cy)

def mechanics():
    keep = []
    for ref, (x, y) in (('H1', (-25.5, -13.0)), ('H2', (25.5, -13.0)), ('H3', (-25.5, 13.0)), ('H4', (25.5, 13.0))):
        keep.append(('screw head M3', Point(*A(x, y)).buffer(3.0, 32), 'FB', (ref,)))
    cx, cy = PC
    for ref, x in (('H5', cx - 17.0), ('H6', cx + 17.0)):
        keep.append(('screw head M3', Point(*A(x, cy)).buffer(3.0, 32), 'FB', (ref,)))
    # pogo pins: housing guide bosses around each barrel (D5): no other parts
    for x, y in POGO:
        keep.append(('pogo guide', Point(*A(x, y)).buffer(2.5, 32), 'F', ('P1', 'P2', 'P3', 'P4')))
    return keep

def build(check=True):
    os.makedirs(SCR, exist_ok=True)
    xml = os.path.join(SCR, 'dock.xml')
    subprocess.run([CLI, 'sch', 'export', 'netlist', '--format', 'kicadxml', '-o', xml, SCH], check=True, capture_output=True)
    comps, nets = read_netlist(xml)
    b = Board('nova-dock', comps, nets, layers=2, title='NOVA — Charging dock and robot contact plate', rev='B',
              date='2026-10-28', company='ronmart · Caril Ronnie Martínez Vera', aux=(CX + PX0, CY + DH / 2))
    b.finish = 'ENIG'                           # flat, corrosion-resistant contact pads
    board_poly = outline(b)
    keep = mechanics()
    place_all(b)
    issues = []
    if check:
        issues = geom.check_placement(b, board_poly, keep, allow_outside=('J1',))
        unplaced = sorted(r for r, c in b.comps.items() if c.footprint and r not in b.placed)
        print('unplaced:', unplaced)
    return b, board_poly, keep, issues

if __name__ == '__main__':
    build()
