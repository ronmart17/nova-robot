"""Concept assembly of NOVA Rev B (simplified solids) -> STEP + PNG views. Run with xvfb-run."""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cadquery as cq
from dims import *

OUT = os.environ.get('MECH_OUT', '/home/claude/robot/mech/out')
os.makedirs(OUT, exist_ok=True)

def rbox(w, d, h, r, x=0, y=0, z=0):
    return cq.Workplane('XY').box(w, d, h, centered=(True, True, False)).edges('|Z').fillet(r).translate((x, y, z))

def bx(w, d, h, x=0, y=0, z=0):
    return cq.Workplane('XY').box(w, d, h, centered=(True, True, False)).translate((x, y, z))

def cyl(d, h, x=0, y=0, z=0, axis='Z'):
    c = cq.Workplane('XY').circle(d / 2).extrude(h)
    if axis == 'X':
        c = c.rotate((0, 0, 0), (0, 1, 0), 90)
    elif axis == 'Y':
        c = c.rotate((0, 0, 0), (1, 0, 0), -90)
    return c.translate((x, y, z))

def main_board():
    b = rbox(MB_W, MB_D, MB_T, MB_R, z=MB_Z0)
    for s in (-1, 1):
        cut = bx(40, 2 * WCUT_Y, 10, x=s * (WCUT_X + 20), z=MB_Z0 - 2)
        b = b.cut(cut)
    return b

def wheels():
    out = []
    for s in (-1, 1):
        w = cq.Workplane('YZ').circle(WHEEL_D / 2).extrude(WHEEL_W).translate((s * WHEEL_X - WHEEL_W / 2, 0, AXLE_Z))
        hub = cq.Workplane('YZ').circle(8).extrude(WHEEL_W + 0.4).translate((s * WHEEL_X - WHEEL_W / 2 - 0.2, 0, AXLE_Z))
        out.append((w, (0.12, 0.12, 0.12)))
        out.append((hub, (0.85, 0.85, 0.85)))
        m = bx(MOTOR_X[1] - MOTOR_X[0], MOTOR_W, MOTOR_H, x=s * (MOTOR_X[0] + MOTOR_X[1]) / 2, z=AXLE_Z - MOTOR_H / 2)
        out.append((m, (0.75, 0.75, 0.78)))
    return out

def caster():
    ball = cq.Workplane('XY').sphere(6.35).translate((0, CASTER_Y, 6.35))
    body = cyl(18, MB_Z0 - 9, 0, CASTER_Y, 9)
    return [(ball, (0.8, 0.8, 0.82)), (body, (0.2, 0.2, 0.2))]

def battery():
    out = []
    for i in (-1, 1):
        for k in (0, 1):
            c = cq.Workplane('XZ').circle(CELL_D / 2).extrude(-CELL_L).translate((i * CELL_D / 2, BAT_Y0 + 1.3, MB_Z1 + 0.8 + CELL_D / 2 + k * CELL_D))
            out.append((c, (0.15, 0.35, 0.75) if k == 0 else (0.15, 0.55, 0.35)))
    return out

def pi_box(u0, u1, v0, v1, h, z):
    (xa, ya), (xb, yb) = pi_xy(u0, v0), pi_xy(u1, v1)
    return bx(abs(xb - xa), abs(yb - ya), h, (xa + xb) / 2, (ya + yb) / 2, z)

def pi5():
    z0 = PI_Z0; zt = z0 + PI_T
    p = []
    board = rbox(PI_D, PI_W, PI_T, 3.0, PI_CX, PI_CY, z0)
    for u, v in PI_HOLES_UV:
        X, Y = pi_xy(u, v)
        board = board.cut(cyl(2.7, 5, X, Y, z0 - 1))
    p.append((board, (0.1, 0.45, 0.2)))
    p.append((pi_box(10, 50, 12, 50, COOLER_H, zt), (0.75, 0.75, 0.78)))           # Active Cooler
    p.append((pi_box(66, 87, 2, 54, 16, zt), (0.8, 0.8, 0.8)))                      # USB-A / RJ45 stack (rear)
    p.append((pi_box(7.1, 57.9, 49.9, 55.1, 8.5, zt), (0.15, 0.15, 0.15)))          # 40-pin header (left)
    p.append((pi_box(7.6, 14.8, -1.2, 6.2, 3.2, zt), (0.8, 0.8, 0.8)))              # USB-C (right, front)
    for u in PI_HDMI_U:
        p.append((pi_box(u - 3.5, u + 3.5, -1.0, 6.5, 3.0, zt), (0.8, 0.8, 0.8)))
    for u, v in PI_HOLES_UV:
        X, Y = pi_xy(u, v)
        p.append((cyl(4.6, PI_STANDOFF, X, Y, MB_Z1), (0.85, 0.7, 0.3)))
        p.append((cyl(4.6, DECK_Z0 - zt, X, Y, zt), (0.85, 0.7, 0.3)))
    return p

def top_deck():
    deck = cyl(XVF_D + 6, 2.0, 0, PI_CY, DECK_Z0).cut(cyl(XVF_D - 20, 3, 0, PI_CY, DECK_Z0 - 0.5))
    xvf = cyl(XVF_D, 1.2, 0, PI_CY, XVF_Z0)
    return [(deck, (0.9, 0.9, 0.9)), (xvf, (0.05, 0.05, 0.05))]

def head():
    out = []
    out.append((bx(HEAD_W, HEAD_T, HEAD_Z1 - HEAD_Z0, 0, HEAD_Y0 + HEAD_T / 2, HEAD_Z0), (0.1, 0.45, 0.2)))
    yf = HEAD_Y0 + HEAD_T
    # display module (landscape 61.12 x 36.48) on an 8.5 mm female header
    zc = 70.0
    out.append((bx(61.12, 1.6, 36.48, 0, yf + 8.5 + 0.8, zc - 18.24), (0.1, 0.3, 0.6)))
    out.append((bx(47.0, 2.4, 35.0, 0, yf + 8.5 + 1.6 + 1.2, zc - 17.5), (0.02, 0.02, 0.02)))
    # camera module 3 above (25 x 24) on 4 mm standoffs, lens forward
    zc_cam = 94.0
    out.append((bx(25, 1.0, 24, 0, yf + 4.5, zc_cam - 12), (0.1, 0.45, 0.2)))
    out.append((cyl(8.5, 11.5 - 1.0, 0, yf + 5.0, zc_cam + 2.5, axis='Y'), (0.05, 0.05, 0.05)))
    # ToF below the display
    out.append((bx(4.9, 1.6, 2.5, 0, yf + 0.8, 44.0), (0.05, 0.05, 0.05)))
    return out

def speaker():
    X, Y, Z = SPEAKER
    return [(cyl(40, 14, X, Y, Z, axis='Y'), (0.3, 0.3, 0.3))]

def shell():
    outer = rbox(SHELL_W, SHELL_D, SHELL_Z1 - SHELL_Z0, SHELL_R, z=SHELL_Z0)
    inner = rbox(SHELL_W - 2 * SHELL_WALL, SHELL_D - 2 * SHELL_WALL, SHELL_Z1 - SHELL_Z0 + 2, SHELL_R - SHELL_WALL, z=SHELL_Z0 - 1)
    s = outer.cut(inner)
    for sx in (-1, 1):
        s = s.cut(bx(30, 2 * (WHEEL_D / 2 + 3), 2 * AXLE_Z + 4, x=sx * SHELL_W / 2, z=0))
    # face openings
    s = s.cut(bx(49, 10, 37, 0, SHELL_D / 2, 70 - 18.5))         # display window
    s = s.cut(cyl(10, 10, 0, SHELL_D / 2 - 5, 94, axis='Y'))       # camera
    s = s.cut(bx(10, 10, 6, 0, SHELL_D / 2, 42))                    # ToF
    top = rbox(SHELL_W, SHELL_D, TOP_T, SHELL_R, z=SHELL_Z1)
    for hx in (-1, 1):
        for hy in (-1, 1):
            top = top.cut(cyl(3, 4, hx * 33, PI_CY + hy * 33, SHELL_Z1 - 1))
    return [(s, (0.93, 0.92, 0.88)), (top, (0.93, 0.92, 0.88))]

def assembly(with_shell=True):
    a = cq.Assembly(name='NOVA_RevB')
    def add(lst, name):
        for i, (sh, col) in enumerate(lst):
            a.add(sh, name=f'{name}_{i}', color=cq.Color(*col))
    add([(main_board(), (0.1, 0.45, 0.2))], 'main_board')
    add(wheels(), 'drive'); add(caster(), 'caster'); add(battery(), 'battery'); add(pi5(), 'pi5')
    add(top_deck(), 'deck'); add(head(), 'head'); add(speaker(), 'speaker')
    if with_shell:
        add(shell(), 'shell')
    return a

if __name__ == '__main__':
    a = assembly(with_shell=False)
    a.save(os.path.join(OUT, 'NOVA_RevB_concept_core.step'), 'STEP')
    b = assembly(with_shell=True)
    b.save(os.path.join(OUT, 'NOVA_RevB_concept.step'), 'STEP')
    print('saved')
