"""Mechanical dimensions and notes on User.Drawings (runs inside pcbnew). Used for the 1:1 PDF drawing."""
import pcbnew

MM = pcbnew.FromMM
LAYER = pcbnew.Dwgs_User

def V(x, y):
    return pcbnew.VECTOR2I(MM(x), MM(y))

def _style(d, size=1.0):
    d.SetLayer(LAYER)
    d.SetUnitsMode(pcbnew.DIM_UNITS_MODE_MM)
    d.SetUnitsFormat(pcbnew.DIM_UNITS_FORMAT_NO_SUFFIX)
    d.SetPrecision(pcbnew.DIM_PRECISION_X_XX)
    d.SetSuppressZeroes(True)
    d.SetLineThickness(MM(0.1))
    d.SetTextSize(pcbnew.VECTOR2I(MM(size), MM(size)))
    d.SetTextThickness(MM(0.15))
    d.SetArrowLength(MM(1.0))

def aligned(b, p1, p2, height, prefix='', size=1.5):
    d = pcbnew.PCB_DIM_ALIGNED(b, pcbnew.PCB_DIM_ALIGNED_T)
    _style(d, size)
    d.SetStart(V(*p1)); d.SetEnd(V(*p2)); d.SetHeight(MM(height))
    if prefix: d.SetPrefix(prefix)
    d.Update()
    b.Add(d)
    return d

def text(b, s, p, size=1.2, left=True):
    t = pcbnew.PCB_TEXT(b)
    t.SetText(s); t.SetLayer(LAYER)
    t.SetTextSize(pcbnew.VECTOR2I(MM(size), MM(size))); t.SetTextThickness(MM(0.15))
    t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT if left else pcbnew.GR_TEXT_H_ALIGN_CENTER)
    t.SetPosition(V(*p))
    b.Add(t)
    return t

def cross(b, p, r=1.5):
    for a, c in (((p[0] - r, p[1]), (p[0] + r, p[1])), ((p[0], p[1] - r), (p[0], p[1] + r))):
        s = pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(V(*a)); s.SetEnd(V(*c)); s.SetLayer(LAYER); s.SetWidth(MM(0.1)); b.Add(s)

def _dims():
    import sys
    sys.path.insert(0, '/home/claude/robot/mech')
    import dims as D
    return D

def main_board(b):
    """Main board Rev B: local origin at the centre (150, 100); local (x, y) = robot (X, −Y), front = −y."""
    D = _dims()
    X, Y = 150.0, 100.0
    A = lambda x, y: (X + x, Y + y)
    hw = D.MB_W / 2
    cross(b, A(0, 0), 3.0)
    aligned(b, A(-hw, -hw), A(hw, -hw), -8.0)                                    # width
    aligned(b, A(hw, -hw), A(hw, hw), 8.0)                                       # depth
    aligned(b, A(-D.WCUT_X, D.WCUT_Y), A(D.WCUT_X, D.WCUT_Y), 34.0)             # between the wheel cut-outs
    aligned(b, A(-hw, -D.WCUT_Y), A(-hw, D.WCUT_Y), -6.0)                       # cut-out height
    (sx, sy) = D.SHELL_HOLES[3]
    aligned(b, A(-sx, -sy), A(sx, -sy), -18.0)                                   # shell holes
    aligned(b, A(sx, -sy), A(sx, sy), 18.0)
    ph = [D.pi_xy(u, v) for u, v in D.PI_HOLES_UV]
    xs = sorted({round(p[0], 2) for p in ph}); ys = sorted({round(p[1], 2) for p in ph})
    aligned(b, A(xs[0], -ys[-1]), A(xs[-1], -ys[-1]), -6.0)                     # Pi standoffs
    aligned(b, A(xs[-1], -ys[-1]), A(xs[-1], -ys[0]), 6.0)
    (hx, hy) = D.HEAD_BRK[1]
    aligned(b, A(-hx, -hy), A(hx, -hy), -10.0)                                   # head brackets
    aligned(b, A(-D.CASTER_DX, -D.CASTER_Y), A(D.CASTER_DX, -D.CASTER_Y), 6.0)   # caster slots
    for p in [A(x, -y) for x, y in D.SHELL_HOLES] + [A(x, -y) for x, y in ph] + [A(x, -y) for x, y in D.HEAD_BRK]:
        cross(b, p, 1.5)
    lines = [
        'MAIN BOARD REV B — MECHANICAL DRAWING 1:1 (mm)',
        "Origin: board centre = wheel axle. +x to the robot's right, +y towards the rear (front = −y).",
        f'{D.MB_W:g} × {D.MB_D:g} rounded square (R{D.MB_R:g}); wheel cut-outs |x| ≥ {D.WCUT_X:g} for |y| ≤ {D.WCUT_Y:g}; '
        'J702 plug notch on the right edge (x ≥ 55.6, y −37.5…−23.5).',
        'M3 (ring to GND): H1–H4 shell bosses (±55, ±55); H9/H10 head angle brackets (±32, −47.5). '
        'M2.5 (ring to GND): H5–H8 Raspberry Pi 5 standoffs (45 mm: 25 + 20).',
        f'N20 bracket slots (2.2 × 4, M2): x = ±{D.BRK_X[0]:g} and ±{D.BRK_X[1]:g}; y = ±{D.BRK_Y:g}. '
        f'Caster slots (2.2 × 8.2): (±{D.CASTER_DX:g}, −{D.CASTER_Y:g}).',
        f'2S2P pack on top in its cage: x ±{D.BAT_X:g}, y {-D.BAT_Y1:g}…{-D.BAT_Y0:g}. '
        f'Head board: y −{D.HEAD_Y0 + D.HEAD_T:g}…−{D.HEAD_Y0:g}, {D.HEAD_W:g} wide (vertical).',
        'Bottom side: N20 motors, TB6612, IMU at the axle, VL53L4CD cliff sensors (±34, −62), J203 dock lead.',
        'Check against the real parts before fabrication: N20 brackets, caster, pack cage, Pi standoffs and angle brackets.',
    ]
    for k, s in enumerate(lines):
        text(b, s, (60.0, 178.0 + k * 2.2), 1.2 if k else 1.6)

def head_board(b):
    """Head board Rev B: x horizontal (front view), z upwards; KiCad = (150 + x, 156 − z)."""
    import head_pcb as H
    X, Z = 150.0, 156.0
    A = lambda x, z: (X + x, Z - z)
    hw = H.W / 2
    aligned(b, A(-hw, H.H), A(hw, H.H), -6.0)                    # width
    aligned(b, A(hw, 0), A(hw, H.H), 6.0)                        # height
    aligned(b, A(-12, 0), A(12, 0), 6.0)                         # notch
    aligned(b, A(-H.HOLE[0], H.HOLE[1]), A(H.HOLE[0], H.HOLE[1]), 14.0)
    aligned(b, A(-hw, 0), A(-hw, H.HOLE[1]), -6.0)
    (x0, z0), (x1, _), (_, z2) = H.CAM_HOLES[0], H.CAM_HOLES[1], H.CAM_HOLES[2]
    aligned(b, A(x0, z0), A(x1, z0), 4.0)                        # camera holes 21 mm
    aligned(b, A(x1, z2), A(x1, z0), -14.0)                      # 12.5 mm
    aligned(b, A(0, 0), A(0, H.CAM_LENS_Z), 0.0)                 # lens height
    aligned(b, A(0, 0), A(0, H.LCD_ZC), 8.0)                     # LCD centre
    for p in (A(-H.HOLE[0], H.HOLE[1]), A(H.HOLE[0], H.HOLE[1]), A(0, H.CAM_LENS_Z), A(0, H.LCD_ZC), A(*H.TOF)):
        cross(b, p, 1.5)
    lines = [
        'HEAD BOARD REV B — MECHANICAL DRAWING 1:1 (mm). Front view (F side = display and camera).',
        f'{H.W:g} × {H.H:g}, 2 layers, 1.6 mm. Bottom notch 24 × 4 for the J101 JST SH cable (opening facing down).',
        f'H101/H102 M3 at x = ±{H.HOLE[0]:g}, z = {H.HOLE[1]:g}: angle brackets to H9/H10 on the main board (4.5 mm behind the rear face).',
        f'2.0" LCD module (61.12 × 36.48) centred at z = {H.LCD_ZC:g}; J102 (x = +{H.HDR_X:g}) or J103 (x = −{H.HDR_X:g}), pin 1 = GND at top.',
        f'Camera Module 3 on M2 standoffs (2.5 mm): holes 21 × 12.5, top edge z = {H.CAM_TOP:g}, lens z ≈ {H.CAM_LENS_Z:.1f}. '
        f'FPC slot 18 × 2 at z = {H.SLOT[1]:.2f}.',
        f'ToF VL53L1X at ({H.TOF[0]:g}, {H.TOF[1]:.1f}): clear window facing forward. Touch electrode pad TP101 near the top edge.',
    ]
    for k, s in enumerate(lines):
        text(b, s, (95.0, 165.0 + k * 2.2), 1.2 if k else 1.5)

def dock_board(b):
    """Dock board + break-away robot contact plate; KiCad = (150 + x, 100 + y)."""
    import dock_pcb as DK
    X, Y = 150.0, 100.0
    A = lambda x, y: (X + x, Y + y)
    hw, hh = DK.DW / 2, DK.DH / 2
    aligned(b, A(-hw, -hh), A(hw, -hh), -6.0)
    aligned(b, A(hw, -hh), A(hw, hh), 6.0)
    aligned(b, A(DK.PX0, -DK.PH / 2), A(DK.PX1, -DK.PH / 2), -8.0)
    aligned(b, A(DK.PX0, -DK.PH / 2), A(DK.PX0, DK.PH / 2), -6.0)
    (p1, p3, p2, p4) = DK.POGO
    aligned(b, A(*p3), A(*p4), 8.0)                               # 16 mm between polarities
    aligned(b, A(*p2), A(*p4), -4.0)                              # 5 mm within a pair
    for x, y in DK.POGO:
        cross(b, A(x, y), 1.2)
    lines = [
        'NOVA DOCK REV B — MECHANICAL DRAWING 1:1 (mm). Top view of the dock board; the plate (left) is mounted face down.',
        f'Dock board {DK.DW:g} × {DK.DH:g}, 4 × M3 at (±25.5, ±13). Pogo pins YTC1P-8020: 9.0 mm working height above the board, '
        '1.0 mm stroke, 100 g each.',
        'P1/P3 = +12 V (x = −8), P2/P4 = GND (x = +8). Robot plate pads 8 × 12 (ENIG): +12 V pad at plate x = +8 because '
        'the plate is mounted face down (mirrored).',
        f'Contact plate {DK.PX1 - DK.PX0:g} × {DK.PH:g}, 2 × M3 (countersunk) at plate x = ±17. Break off at MB1/MB2 and '
        'sand the tab remains flush.',
        'J1 on the tail that passes through the dock back wall (jack behind the wall, out of the robot reach). D3 at the front edge under a light pipe.',
    ]
    for k, s in enumerate(lines):
        text(b, s, (75.0, 126.0 + k * 2.2), 1.2 if k else 1.5)
