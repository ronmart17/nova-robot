"""NOVA Rev B — 3D-printed parts (CadQuery). Robot frame: X right, Y forward, Z up, origin on the floor under the axle.
Every dimension comes from dims.py; print notes are in the docstrings (PETG, 0.2 mm layers unless stated)."""
import math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cadquery as cq
from dims import *

# ------------------------------------------------------------------ helpers
def bx(x0, y0, z0, x1, y1, z1):
    return cq.Workplane('XY').box(x1 - x0, y1 - y0, z1 - z0, centered=False).translate((x0, y0, z0))

def rrect(w, d, h, r, x=0.0, y=0.0, z=0.0):
    s = cq.Workplane('XY').rect(w, d).extrude(h)
    if r > 0:
        s = s.edges('|Z').fillet(r)
    return s.translate((x, y, z))

def cyl(d, h, x=0.0, y=0.0, z=0.0, axis='Z'):
    c = cq.Workplane('XY').circle(d / 2).extrude(h)
    if axis == 'X':
        c = c.rotate((0, 0, 0), (0, 1, 0), 90)
    elif axis == 'Y':
        c = c.rotate((0, 0, 0), (1, 0, 0), -90)
    return c.translate((x, y, z))

def slot_y(w, h, r, x, y0, y1, z):
    """Rounded rectangular hole through a wall normal to Y (w along X, h along Z), centred at (x, z)."""
    return cq.Workplane('XZ').center(x, z).rect(w, h).extrude(-(y1 - y0)).edges('|Y').fillet(r).translate((0, y0, 0))

def slot_x(w, h, r, y, z, x0, x1):
    """Rounded rectangular hole through a wall normal to X (w along Y, h along Z)."""
    return cq.Workplane('YZ').center(y, z).rect(w, h).extrude(x1 - x0).edges('|X').fillet(r).translate((x0, 0, 0))

def try_fillet(s, sel, r):
    try:
        return s.edges(sel).fillet(r)
    except Exception:
        return s

PI_STANDOFFS = [pi_xy(u, v) for u, v in PI_HOLES_UV]
BOSS_Z1 = MB_Z1 + 16.0                      # top of the shell corner bosses

# ------------------------------------------------------------------ enclosure (industrial design)
# Upper body (matte white) + lower skirt (graphite) split along a plane rising from the front (Z 32.5) to the rear
# (Z 39.5) with a 0.6 mm shadow gap; graphite fender bands rise around the wheels; large smoked visor over the face;
# light-diffusing halo ring on the top over the XVF3800 LED ring and microphones.
ZS_FRONT, ZS_REAR = 32.5, 39.5
Z_SPLIT = ZS_FRONT                              # lowest point of the parting line
TOP_Z = SHELL_Z1 + TOP_T                        # 108
R_TOP = 12.0                                    # top edge radius
VISOR = (36.0, 36.5, 95.5, 12.0)                # half width, z0, z1, corner radius (the whole flat front face)
VIS_OPEN = (33.0, 39.5, 92.5, 10.0)             # through opening behind the visor
HALO = (28.0, 49.0)                             # halo ring radii (centre on the XVF3800; mics at r 46.7)
XVF_MIC_R = 46.7                                # XVF3800 AEC_MIC_ARRAY_GEO (±0.033, ±0.033) m → r 46.7 mm at 45°
ARCH_R = WHEEL_D / 2 + 3.0                      # wheel arch radius (24.5) around the axle
FENDER_R = ARCH_R + 6.0                         # graphite fender band outer radius (30.5): rises into the white body
REVEAL = 0.6                                    # shadow gap between the white body and the graphite parts

def split_z(y):
    """Parting-line height at Y (plane, rising towards the rear)."""
    return ZS_FRONT + (ZS_REAR - ZS_FRONT) * (SHELL_D / 2 - y) / SHELL_D

def half_space(below, dz=0.0):
    """Big box bounded by the parting plane shifted by dz (below=True keeps Z < plane + dz)."""
    k = (ZS_REAR - ZS_FRONT) / SHELL_D
    th = -math.degrees(math.atan(k))
    b = bx(-300, -300, -600, 300, 300, 0) if below else bx(-300, -300, 0, 300, 300, 600)
    return b.rotate((0, 0, 0), (1, 0, 0), th).translate((0, 0, split_z(0.0) + dz))

def _rr_y(hw, z0, z1, r, y0, y1):
    """Rounded rectangle in the XZ plane (|X| <= hw, z0..z1) extruded along Y from y0 to y1."""
    return (cq.Workplane('XZ').center(0, (z0 + z1) / 2).rect(2 * hw, z1 - z0).extrude(-(y1 - y0))
            .edges('|Y').fillet(r).translate((0, y0, 0)))

def shell_upper():
    """Upper body, printed upside down, 2 mm walls, R12 top edges, bottom edge on the rising parting plane. Fixed with
    four M3 from under the main board (front M3 × 8, rear M3 × 10 through the dock plate bar) through the skirt ears into heat-set inserts in the corner bosses. Front:
    pocket and frame for the 2 mm smoked visor (the whole flat face); top: seat for the halo; sides: forward-leaning gills
    over the Pi; rear: hexagonal speaker grille and the NOVA mark."""
    zb = ZS_FRONT - 2.0
    outer = rrect(SHELL_W, SHELL_D, TOP_Z - zb, SHELL_R, z=zb)
    outer = try_fillet(outer, '>Z', R_TOP)
    inner = rrect(SHELL_W - 2 * SHELL_WALL, SHELL_D - 2 * SHELL_WALL, TOP_Z - SHELL_WALL - zb + 1, SHELL_R - SHELL_WALL,
                  z=zb - 1)
    inner = try_fillet(inner, '>Z', R_TOP - SHELL_WALL)
    s = outer.cut(inner).intersect(half_space(False, REVEAL / 2))
    yo, yi = SHELL_D / 2, SHELL_D / 2 - SHELL_WALL
    xo = SHELL_W / 2
    # visor: frame behind the wall, 2 mm pocket in front of it, through opening
    hw, z0, z1, r = VISOR
    ohw, oz0, oz1, orr = VIS_OPEN
    frame = _rr_y(hw + 1.5, z0 - 1.0, z1 + 1.0, r + 1.0, yi - 2.0, yi + 0.1).cut(_rr_y(ohw, oz0, oz1, orr, yi - 3, yi + 1))
    s = s.union(frame)
    s = s.cut(_rr_y(hw + 0.3, z0 - 0.3, z1 + 0.3, r + 0.3, yo - 2.0, yo + 1))
    s = s.cut(_rr_y(ohw, oz0, oz1, orr, yi - 3, yo + 1))
    # halo seat: annular opening r 28..47 in the top
    r0, r1 = HALO
    ring = cyl(2 * r1 + 0.4, 10, 0.0, XVF_CY, TOP_Z - 5).cut(cyl(2 * r0 - 0.4, 12, 0.0, XVF_CY, TOP_Z - 6))
    s = s.cut(ring)
    # touch spot (engraved ring with a dot) between the halo and the front edge
    ty = (XVF_CY + r1 + SHELL_D / 2 - R_TOP) / 2              # centred on the flat between the halo and the top edge
    s = s.cut(cyl(11.0, 0.5, 0.0, ty, TOP_Z - 0.5).cut(cyl(9.8, 1, 0.0, ty, TOP_Z - 0.7)))
    s = s.cut(cyl(2.0, 0.5, 0.0, ty, TOP_Z - 0.5))
    # gills over the Pi on both sides: four 2.2 × 30 mm slots, each one 2.5 mm further back (forward-leaning stack)
    for sx in (-1, 1):
        for k, z in enumerate((72.0, 77.0, 82.0, 87.0)):
            cut = slot_x(30.0, 2.2, 1.05, -4.0 - 2.5 * k, z, xo - 4 if sx > 0 else -xo - 1, xo + 1 if sx > 0 else -xo + 4)
            s = s.cut(cut)
    # rear: hexagonal speaker grille (Ø2.2 on a 3.6 mm hex grid inside Ø34)
    sx_, sy_, sz_ = SPEAKER
    pitch = 3.6
    holes = None
    for i in range(-6, 7):
        for j in range(-6, 7):
            x = sx_ + pitch * (i + 0.5 * (j % 2)); z = sz_ + pitch * math.sqrt(3) / 2 * j
            if math.hypot(x - sx_, z - sz_) <= 17.0:
                hcyl = cyl(2.2, 6, x, -yo - 2, z, axis='Y')
                holes = hcyl if holes is None else holes.union(hcyl)
    s = s.cut(holes)
    s = s.cut(cyl(40.0, 0.5, sx_, -yo - 0.01, sz_, axis='Y').cut(cyl(38.6, 1, sx_, -yo - 0.5, sz_, axis='Y')))
    # NOVA mark on the rear, engraved 0.5 mm
    try:
        txt = (cq.Workplane('XZ').text('NOVA', 9.0, -0.5, kind='bold', halign='center', valign='center')
               .translate((-22.0, -yo + 0.0, 90.0)))
        s = s.cut(txt)
    except Exception:
        pass
    # corner bosses (from the board top) with ribs, heat-set inserts Ø4.0 × 6
    for (X, Y) in SHELL_HOLES:
        boss = cyl(8.0, TOP_Z - SHELL_WALL - MB_Z1 - R_TOP * 0.6, X, Y, MB_Z1)
        L = 16.0
        rib = (cq.Workplane('XY').rect(L, 2.0).extrude(TOP_Z - SHELL_WALL - MB_Z1 - R_TOP * 0.6)
               .rotate((0, 0, 0), (0, 0, 1), 45 if X * Y > 0 else -45)
               .translate((X + math.copysign(L / 2 * 0.707, X), Y + math.copysign(L / 2 * 0.707, Y), MB_Z1)))
        rib = rib.intersect(rrect(SHELL_W - 1.0, SHELL_D - 1.0, TOP_Z - MB_Z1, SHELL_R - 0.5, z=MB_Z1))
        # below the parting plane the rib stays inside the skirt's inner face
        rib = (rib.intersect(rrect(SHELL_W - 2 * SHELL_WALL - 0.4, SHELL_D - 2 * SHELL_WALL - 0.4, TOP_Z - MB_Z1,
                                   SHELL_R - SHELL_WALL - 0.2, z=MB_Z1))
               .union(rib.intersect(half_space(False, REVEAL / 2))))
        s = s.union(boss).union(rib)
        s = s.cut(cyl(4.0, 6.5, X, Y, MB_Z1 - 0.01))
    # speaker cup on the inner rear wall
    s = s.union(cyl(46.0, 4.0, sx_, -yi, sz_, axis='Y').cut(cyl(41.0, 6, sx_, -yi - 1, sz_, axis='Y')))
    # graphite fender bands come up from the skirt: matching cut-outs with the reveal
    for sx in (-1, 1):
        s = s.cut(cq.Workplane('YZ').center(0, AXLE_Z).circle(FENDER_R + REVEAL).extrude(10).translate((sx * xo - 5, 0, 0)))
    # the disc inside the halo is a separate part (top_cap): keep the main body only
    sol = max(s.solids().vals(), key=lambda v: v.Volume())
    return cq.Workplane('XY').add(sol)

def top_cap():
    """White disc inside the halo ring (r 27.8, 2 mm), glued onto the halo's inner flange; 0.3 mm dished centre ring."""
    r0 = HALO[0] - 0.2
    c = cyl(2 * r0, SHELL_WALL, 0.0, XVF_CY, TOP_Z - SHELL_WALL)
    c = try_fillet(c, '>Z', 0.5)
    c = c.cut(cyl(30.0, 0.3, 0.0, XVF_CY, TOP_Z - 0.3).cut(cyl(28.8, 1, 0.0, XVF_CY, TOP_Z - 0.5)))
    return c

def shell_skirt():
    """Lower skirt (graphite), Z 8 up to the parting plane: wraps the main board edge, wheel arches with 1.5 mm fender flares, rear
    port bay (USB-C, power switch) and the dock opening. Four ears under the board corners take the shell screws."""
    z0, z1 = SHELL_Z0, ZS_REAR + 2.0
    outer = rrect(SHELL_W, SHELL_D, z1 - z0, SHELL_R, z=z0)
    try:
        outer = outer.edges('<Z').chamfer(4.0, 1.6)            # tucked-under lower edge: the body looks lighter
    except Exception:
        outer = try_fillet(outer, '<Z', 2.0)
    inner = rrect(SHELL_W - 2 * SHELL_WALL, SHELL_D - 2 * SHELL_WALL, z1 - z0 + 2, SHELL_R - SHELL_WALL, z=z0 - 1)
    s = outer.cut(inner).intersect(half_space(True, -REVEAL / 2))
    yo, yi = SHELL_D / 2, SHELL_D / 2 - SHELL_WALL
    xo = SHELL_W / 2
    ra = ARCH_R
    for sx in (-1, 1):
        band = (cq.Workplane('YZ').center(0, AXLE_Z).circle(FENDER_R).circle(ra).extrude(SHELL_WALL)
                .translate((sx * xo - (SHELL_WALL if sx > 0 else 0), 0, 0)))
        s = s.union(band.intersect(bx(-xo - 1, -FENDER_R - 1, z0, xo + 1, FENDER_R + 1, AXLE_Z + FENDER_R + 1)))
        flare = (cq.Workplane('YZ').center(0, AXLE_Z).circle(ra + 3.5).circle(ra).extrude(1.5)
                 .translate((sx * xo - (0 if sx > 0 else 1.5), 0, 0)))
        flare = flare.intersect(bx(-xo - 3, -ra - 4, z0, xo + 3, ra + 4, AXLE_Z + ra + 4))
        try:
            flare = flare.faces('>X' if sx > 0 else '<X').edges().fillet(0.6)
        except Exception:
            pass
        s = s.union(flare)
        arch = (cq.Workplane('YZ').center(0, AXLE_Z).circle(ra).extrude(12).translate((sx * xo - 6, 0, 0))
                .union(bx(sx * xo - 6, -ra, 0, sx * xo + 6, ra, AXLE_Z)))
        s = s.cut(arch)
    # rear port bay: 1.0 mm recess around the USB-C and the power switch
    s = s.cut(_rr_y(14.0, MB_Z1 - 3.6, MB_Z1 + 6.6, 3.0, -yo - 1, -yo + 1.0).translate((-6.5, 0, 0)))
    s = s.cut(slot_y(11.5, 6.0, 2.0, 0.0, -yo - 1, -yi + 1, MB_Z1 + 1.6))
    s = s.cut(slot_y(8.0, 4.0, 1.2, -15.6, -yo - 1, -yi + 1, MB_Z1 + 1.2))
    # dock opening (the dock tongue enters here)
    ox, oz = DOCK_OPENING
    s = s.cut(slot_y(2 * ox, 2 * (oz - z0), 3.0, 0.0, -yo - 1, -yi + 1, z0))
    # ears under the board corners (2 mm), joined to the wall
    for (X, Y) in SHELL_HOLES:
        ear = rrect(12.0, 12.0, 2.0, 3.0, X + math.copysign(3.0, X), Y + math.copysign(3.0, Y), MB_Z0 - 2.0)
        ear = ear.intersect(rrect(SHELL_W - 1.0, SHELL_D - 1.0, 10, SHELL_R - 0.5, z=MB_Z0 - 3))
        s = s.union(ear).cut(cyl(3.4, 10, X, Y, MB_Z0 - 5))
    return s

def visor():
    """Face visor: 2 mm smoked acrylic (laser cut), glued into the front pocket. The display shows through the tint;
    clear cut-outs for the camera lens and the ToF."""
    hw, z0, z1, r = VISOR
    yo = SHELL_D / 2
    v = _rr_y(hw, z0, z1, r, yo - 2.0, yo)
    v = try_fillet(v, '>Y', 0.6)
    v = v.cut(cyl(8.0, 4, 0.0, yo - 3, HEAD_Z0 + HEAD_CAM_LENS_Z, axis='Y'))
    v = v.cut(slot_y(6.0, 4.0, 1.0, -HEAD_TOF[0], yo - 3, yo + 1, HEAD_Z0 + HEAD_TOF[1]))
    return v

def halo():
    """Halo: translucent PETG ring over the XVF3800 LEDs and microphones; 0.8 mm proud of the top with chamfered edges, a
    flange under the top skin, two rings of 48 × Ø1.2 holes: r 46.7 (four of them exactly over the microphones at
    45° + k·90°) and r 38."""
    r0, r1 = HALO
    zt = TOP_Z
    top = cyl(2 * r1, SHELL_WALL + 0.8, 0.0, XVF_CY, zt - SHELL_WALL).cut(cyl(2 * r0, 5, 0.0, XVF_CY, zt - 3))
    try:
        top = top.faces('>Z').edges().chamfer(0.6)
    except Exception:
        pass
    flange = cyl(2 * r1 + 5, 1.2, 0.0, XVF_CY, zt - SHELL_WALL - 1.2).cut(cyl(2 * r0 - 5, 3, 0.0, XVF_CY, zt - 5))
    h = top.union(flange)
    for rr, ph in ((XVF_MIC_R, 0.0), (38.0, 0.5)):              # over the four mics (45° + k·90°), decorative ring
        for k in range(48):
            a = 2 * math.pi * (k + ph) / 48
            h = h.cut(cyl(1.2, 6, rr * math.cos(a), XVF_CY + rr * math.sin(a), zt - 4))
    return h

# ------------------------------------------------------------------ head board angle brackets
def head_bracket(side=1):
    """Angle bracket (×2, mirrored), 2.5 mm PETG/PLA or 1.5 mm bent aluminium. Horizontal leg: M3 from under the main
    board (H9/H10) with a nut on top; vertical leg: M3 through H101/H102 of the head board (z = 10), nut at the back."""
    X, Y = HEAD_BRK[0 if side < 0 else 1]
    t = 2.5
    yb = HEAD_Y0                                     # head board rear face
    zh = HEAD_Z0 + HEAD_HOLE[1]
    w = 9.0
    hor = bx(X - w / 2, Y - 5.0, MB_Z1, X + w / 2, yb, MB_Z1 + t)
    ver = bx(X - w / 2, yb - t, MB_Z1, X + w / 2, yb, zh + 5.5)
    br = hor.union(ver)
    # triangular gussets at both sides
    for sx in (-1, 1):
        g = (cq.Workplane('YZ').polyline([(yb - t, MB_Z1 + t), (yb - t - 4.0, MB_Z1 + t), (yb - t, MB_Z1 + t + 4.0)]).close()
             .extrude(1.2).translate((X + sx * (w / 2 - 0.6) - 0.6, 0, 0)))
        br = br.union(g)
    br = br.cut(cyl(3.3, 10, X, Y, MB_Z1 - 1))
    br = br.cut(cyl(3.3, 10, X, yb - t - 1, zh, axis='Y'))
    # relief for the nut on the horizontal leg (AF 5.5)
    br = br.cut(cyl(7.0, 4.0, X, Y, MB_Z1 + t).intersect(bx(X - 4, yb - t - 1.2, MB_Z1 + t, X + 4, yb, MB_Z1 + t + 4)))
    return try_fillet(br, '|X', 0.4)

# ------------------------------------------------------------------ battery cage
def battery_cage():
    """Cage for the 2S2P 18650 block: slides down over the four Pi standoffs (Ø4.6 hex, holes Ø5.4) and presses the
    pack onto a 1 mm foam pad on the main board. Open top under the Pi, lead exit at the rear (towards J301)."""
    w, d, h = BAT_W + 2 * 0.4, BAT_L + 2 * 0.4, BAT_H + 0.4      # inner
    t = 1.8
    z0 = MB_Z1 + 0.5                                             # 0.5 mm foam under the pack
    yc = (BAT_Y0 + BAT_Y1) / 2
    outer = rrect(w + 2 * t, d + 2 * t, h + t, 3.0, 0, yc, z0)
    inner = rrect(w, d, h + 0.01, 1.5, 0, yc, z0 - 0.01)
    cage = outer.cut(inner)
    # top window (the Pi bottom is 1.2 mm above): keep a 6 mm rim
    cage = cage.cut(rrect(w - 12, d - 12, 5, 4.0, 0, yc, z0 + h - 1))
    # side windows (cooling, lighter)
    for sx in (-1, 1):
        for k in (-1, 1):
            cage = cage.cut(slot_x(22.0, 22.0, 4.0, yc + k * 17.0, z0 + h / 2, sx * (w / 2) - 3 if sx > 0 else -w / 2 - t - 1,
                                   sx * (w / 2 + t) + 1 if sx > 0 else -w / 2 + 3))
    # lead exit at the rear end
    cage = cage.cut(slot_y(16.0, 10.0, 2.0, 8.0, yc - d / 2 - t - 1, yc - d / 2 + 1, z0 + 6.0))
    # ears over the Pi standoffs
    for (X, Y) in PI_STANDOFFS:
        ear = rrect(8.5, 8.5, 4.0, 2.0, X, Y, z0 + h + t - 4.0)
        arm = bx(min(X, math.copysign(w / 2 + t - 0.5, X)), Y - 3.0, z0 + h + t - 4.0,
                 max(X, math.copysign(w / 2 + t - 0.5, X)), Y + 3.0, z0 + h + t)
        if abs(Y - yc) > d / 2:                    # standoffs in front of the pack: arm along Y
            arm = bx(X - 3.0, min(Y, yc + d / 2 + t - 0.5), z0 + h + t - 4.0, X + 3.0, max(Y, yc + d / 2 + t - 0.5), z0 + h + t)
        cage = cage.union(ear).union(arm)
    for (X, Y) in PI_STANDOFFS:
        cage = cage.cut(cyl(5.4, 80, X, Y, z0 - 1))             # through the ears
    # notch in the left wall for the Pi-link header J701 (2 × 6 IDC box header and its cable socket)
    cage = cage.cut(bx(-24.0, 13.4, z0 - 1, -19.9, 37.9, z0 + 18.0))
    return cage

# ------------------------------------------------------------------ top deck for the XVF3800
def top_deck():
    """Ø106 deck, 2 mm, on four M2.5 × 20 standoffs from the Pi. The XVF3800 board (Ø100) sits in a 0.6 mm pocket
    and is held by three snap tabs; central slot for its USB cable down to the Pi."""
    z0 = DECK_Z0
    d = cyl(XVF_D + 6, 2.0, 0.0, XVF_CY, z0)
    for (X, Y) in PI_STANDOFFS:                                     # ears over the standoffs at the rim
        d = d.union(rrect(9.0, 9.0, 2.0, 3.0, X, Y, z0))
    d = d.cut(cyl(XVF_D + 0.6, 1.0, 0.0, XVF_CY, z0 + 1.4))
    d = d.cut(rrect(26, 10, 5, 3, 0.0, XVF_CY - 25.0, z0 - 1))           # cable slot
    for (X, Y) in PI_STANDOFFS:
        d = d.cut(cyl(2.8, 5, X, Y, z0 - 1))
    for k in range(3):
        a = math.radians(90 + 120 * k)
        x, y = (XVF_D / 2 + 1.6) * math.cos(a), XVF_CY + (XVF_D / 2 + 1.6) * math.sin(a)
        tab = (cq.Workplane('XY').rect(2.0, 8.0).extrude(4.2).rotate((0, 0, 0), (0, 0, 1), math.degrees(a))
               .translate((x, y, z0 + 2.0)))
        lip = (cq.Workplane('XY').rect(1.6, 8.0).extrude(0.8).rotate((0, 0, 0), (0, 0, 1), math.degrees(a))
               .translate((x - 0.9 * math.cos(a), y - 0.9 * math.sin(a), z0 + 2.0 + 3.4)))
        d = d.union(tab).union(lip)
    # lightening windows
    for k in range(4):
        a = math.radians(45 + 90 * k)
        d = d.cut(cyl(16.0, 5, 30 * math.cos(a), XVF_CY + 30 * math.sin(a), z0 - 1))
    return d

# ------------------------------------------------------------------ rear bar carrying the dock contact plate
PLATE_W, PLATE_H = 42.0, 18.0

def dock_plate_bar():
    """Bar under the rear of the main board, fixed with the two rear shell screws (H1/H2, M3 × 10 from below; the bar's
    end bosses are the spacers). Its underside carries the 42 × 18 contact plate face down in a 1.6 mm recess, flush with
    the bar at Z = DOCK_PLATE_Z, with 20° ramps on both sides so the pogo tips are pressed down before they reach the
    pads (entering and leaving). J2 sits in the central pocket; 2 × M3 countersunk into heat-set inserts at x = ±17."""
    X1, Y1 = SHELL_HOLES[0][0], SHELL_HOLES[0][1]             # (−55, −55)
    yc, zf = DOCK_PLATE_Y, DOCK_PLATE_Z
    zb = MB_Z0 - 2.5                                          # beam top (2.5 mm under the board's bottom parts)
    ramp = 6.0
    # the rear ramp ends 0.3 mm inside the skirt wall (4.2 mm long: still lifts the 1 mm pogo pre-travel)
    y0, y1 = max(yc - PLATE_H / 2 - ramp, -SHELL_D / 2 + SHELL_WALL + 0.3), yc + PLATE_H / 2 + ramp
    rr = (yc - PLATE_H / 2) - y0
    # plate carrier: flat underside at zf between the ramps, 26 mm wide in X around the pads
    prof = [(y0, zf + rr * math.tan(math.radians(20))), (yc - PLATE_H / 2, zf), (yc + PLATE_H / 2, zf),
            (y1, zf + ramp * math.tan(math.radians(20))), (y1, zb), (y0, zb)]
    carrier = cq.Workplane('YZ').polyline(prof).close().extrude(PLATE_W + 6).translate((-(PLATE_W + 6) / 2, 0, 0))
    beam = bx(X1 - 5, Y1 - 4, zb - 4.5, -X1 + 5, Y1 + 4, zb)
    bar = carrier.union(beam)
    for sx in (-1, 1):
        bar = bar.union(cyl(10.0, (MB_Z0 - 2.0) - (zb - 4.5), sx * X1, Y1, zb - 4.5))   # up to the skirt ear
        bar = bar.cut(cyl(3.4, 40, sx * X1, Y1, zb - 10))
        bar = bar.cut(cyl(6.2, 3.0, sx * X1, Y1, zb - 4.51))          # screw head counterbore
    bar = bar.cut(bx(-PLATE_W / 2 - 0.2, yc - PLATE_H / 2 - 0.2, zf - 0.01, PLATE_W / 2 + 0.2, yc + PLATE_H / 2 + 0.2, zf + 1.6))
    bar = bar.cut(bx(-6.0, yc - 4.5, zf, 4.0, yc + 4.5, zf + 9.0))       # J2 (XH, 7 mm) pocket
    bar = bar.cut(bx(-2.0, yc - 4.5, zf + 6.0, 2.0, Y1 - 4.0 + 0.01, zb + 0.01).union(
        bx(-2.0, yc - 15.0, zb - 3.0, 2.0, yc - 4.5, zb + 0.01)))          # lead channel towards J203
    for sx in (-1, 1):
        bar = bar.cut(cyl(4.0, 6.0, sx * 17.0, yc, zf + 1.59))
    # pocket for the dock lead connector J203 (bottom side of the main board)
    bar = bar.cut(bx(8.0, -66.1, 19.8, 16.5, -59.3, zb + 0.01))
    bar = bar.cut(bx(-2.0, -64.0, zb - 3.0, 8.5, -61.0, zb + 0.01))          # lead groove: channel → J203
    return bar

def dock_contact_plate():
    """The break-away contact plate itself (from the dock PCB panel), for the assembly view."""
    yc, zf = DOCK_PLATE_Y, DOCK_PLATE_Z
    p = rrect(PLATE_W, PLATE_H, 1.6, 1.5, 0, yc, zf)
    for sx in (-1, 1):
        p = p.cut(cyl(3.2, 3, sx * 17.0, yc, zf - 1))
    pads = None
    for sx in (-1, 1):
        q = rrect(8.0, 12.0, 0.05, 0.8, sx * 8.0, yc, zf - 0.04)
        pads = q if pads is None else pads.union(q)
    return p, pads

# ------------------------------------------------------------------ dock
# Graphite base + tongue, white sculpted tower (flat front for the robot's rear, curved back), AprilTag on the tower
# front at the camera height, DC jack hidden inside the tower foot (plug enters from the back), light pipe over D3.
DOCK_BASE = (-48.0, 48.0, -98.0, -30.0)                        # x0, x1, y0, y1 of the base plate
TONGUE = (-32.0, 32.0, -34.0, DOCK_WALL_Y)                     # x0, x1, y_front, y_back
BASE_T = 3.0
TOWER = (42.0, 126.0)                                          # half width, top z
TOWER_BACK = [(-97.0, BASE_T), (-97.0, 22.0), (-93.5, 55.0), (-87.5, 95.0), (-81.0, 126.0)]   # (y, z) of the back
TAG = (50.0, 40.0)                                             # sticker edge, tag (black square) edge — tag36h11 id 0
TAG_PANEL = (60.0, 6.0)                                        # graphite panel edge, corner radius
JACK_Z = DOCK_PCB_Z + 1.6 + 6.5                                # DC-005 bore axis
TOWER_SCREWS = [(-30.0, -88.0), (30.0, -88.0)]

def dock_xy(x, y):
    """Dock PCB local (x, y) → robot frame when docked (pogo centre under the plate centre)."""
    return x, DOCK_PLATE_Y - y

def dock_base():
    """Dock base (graphite PETG, 3 mm): rounded plan 96 × 68 mm with soft top edges, PCB bosses (M3 heat-set inserts),
    rest for the PCB tail end, two countersunk M3 holes for the tower and four Ø10 rubber-foot recesses."""
    x0, x1, y0, y1 = DOCK_BASE
    b = rrect(x1 - x0, y1 - y0, BASE_T, 14.0, (x0 + x1) / 2, (y0 + y1) / 2, 0)
    b = try_fillet(b, '>Z', 1.2)
    b = b.union(cyl(5.0, DOCK_PCB_Z - BASE_T, -3.0, DOCK_PLATE_Y - 37.0, BASE_T - 0.01))         # tail-end rest
    for (x, y) in ((-25.5, -13), (25.5, -13), (-25.5, 13), (25.5, 13)):
        X, Y = dock_xy(x, y)
        b = b.union(cyl(6.5, DOCK_PCB_Z - BASE_T, X, Y, BASE_T - 0.01)).cut(cyl(4.0, 5.5, X, Y, 0.5))   # M3 × 4 insert
    for (x, y) in TOWER_SCREWS:
        b = b.cut(cyl(3.4, 10, x, y, -1)).cut(cq.Workplane('XY').circle(3.2).workplane(offset=1.8).circle(1.7).loft()
                                              .translate((x, y, -0.01)))
    for (x, y) in ((x0 + 10, y0 + 10), (x1 - 10, y0 + 10), (x0 + 10, y1 - 10), (x1 - 10, y1 - 10)):
        b = b.cut(cyl(10.2, 1.0, x, y, -0.01))
    return b

def dock_tower():
    """Tower (white PETG, printed on its side): intersection of a tapered front silhouette (88 mm at the foot, 64 mm at
    the top, R16 shoulders) and a side profile with a flat front (the robot's rear stops 1 mm from it) and a curved back.
    Front: 1.2 mm recess for the graphite tag panel at the camera height, engraved NOVA mark under it. Foot: open-bottom
    channel for the PCB tail and the DC jack, Ø11 plug opening in the back; two M3 heat-set inserts."""
    hw, zt = TOWER
    yf = DOCK_WALL_Y
    side = (cq.Workplane('YZ').moveTo(yf, BASE_T).lineTo(*TOWER_BACK[0]).lineTo(*TOWER_BACK[1])
            .spline(TOWER_BACK[2:], includeCurrent=True).lineTo(yf, zt).close()
            .extrude(2 * hw + 20).translate((-hw - 10, 0, 0)))
    sk = (cq.Sketch().polygon([(-hw - 2, BASE_T), (hw + 2, BASE_T), (hw - 10, zt), (-hw + 10, zt), (-hw - 2, BASE_T)])
          .vertices('>Y').fillet(16.0))
    front = cq.Workplane('XZ').placeSketch(sk).extrude(-60).translate((0, yf - 40, 0))
    w = side.intersect(front)
    try:
        w = w.faces('>Y').edges().fillet(1.5)
    except Exception:
        pass
    zc = HEAD_Z0 + HEAD_CAM_LENS_Z
    pw, pr = TAG_PANEL
    w = w.cut(_rr_y(pw / 2 + 0.2, zc - pw / 2 - 0.2, zc + pw / 2 + 0.2, pr + 0.2, yf - 1.2, yf + 0.1))
    try:
        txt = (cq.Workplane('XZ').text('NOVA', 6.0, -0.4, kind='bold', halign='center', valign='center')
               .translate((0.0, yf, 38.0)).mirror('YZ'))                 # reads from the front (+Y)
        w = w.cut(txt.translate((0, -0.4, 0)).union(txt))
    except Exception:
        pass
    # foot channel (open bottom): PCB tail and DC jack; plug opening in the back
    w = w.cut(bx(-30.0, yf - 1.2, BASE_T - 1, 30.0, yf + 0.1, DOCK_PCB_Z + 1.6 + 0.4))         # PCB rear edge
    w = w.cut(bx(-7.6, -96.0, BASE_T - 1, 8.1, yf + 1, DOCK_PCB_Z + 1.6 + 0.6))
    w = w.cut(bx(-5.9, DOCK_PLATE_Y - 40.0, BASE_T - 1, 5.9, DOCK_PLATE_Y - 26.2 + 2.0, DOCK_PCB_Z + 1.6 + 13.0))
    w = w.cut(cyl(11.0, 10, 0.0, -100.0, JACK_Z, axis='Y'))
    for (x, y) in TOWER_SCREWS:
        w = w.cut(cyl(4.0, 6.0, x, y, BASE_T - 0.01))
    return w

def dock_tag_panel():
    """Graphite tag panel (60 × 60 × 1.2 mm, R6), glued into the tower recess; carries the AprilTag sticker."""
    zc = HEAD_Z0 + HEAD_CAM_LENS_Z
    pw, pr = TAG_PANEL
    return _rr_y(pw / 2, zc - pw / 2, zc + pw / 2, pr, DOCK_WALL_Y - 1.2, DOCK_WALL_Y)

def dock_tag():
    """AprilTag sticker (tag36h11, id 0; 50 mm white square, 40 mm black square = detector tag size 0.040 m)."""
    from moms_apriltag import TagGenerator2
    bits = TagGenerator2('tag36h11').generate(0, scale=1)
    zc = HEAD_Z0 + HEAD_CAM_LENS_Z
    yf = DOCK_WALL_Y
    cell = TAG[1] / 8
    white = bx(-TAG[0] / 2, yf, zc - TAG[0] / 2, TAG[0] / 2, yf + 0.1, zc + TAG[0] / 2)
    black = None
    for r in range(8):
        for c in range(8):
            if bits[r][c] == 0:
                x0 = TAG[1] / 2 - (c + 1) * cell; z1 = zc + TAG[1] / 2 - r * cell     # seen from +Y: image left = +X
                q = bx(x0, yf, z1 - cell, x0 + cell, yf + 0.1, z1)
                black = q if black is None else black.union(q)
    return white.cut(black), black

def dock_lightpipe():
    """Ø3 clear acrylic rod over the status LED D3 (dock PCB top → 0.6 mm above the tongue)."""
    X, Y = dock_xy(0.0, -14.4)
    return cyl(3.0, DOCK_TONGUE_H + 0.6 - (DOCK_PCB_Z + 1.6 + 0.6), X, Y, DOCK_PCB_Z + 1.6 + 0.6)

def dock_tongue():
    """Cover over the dock PCB (2 mm walls, top at 13 mm, 5 mm under the robot's rear opening): chamfered front corners
    in plan so the opening (±34) self-centres on it (±2 mm), rounded top edges, Ø1.9 guides for the four pogo barrels,
    Ø3.2 light pipe over D3, rear end open against the wall; fixed by the four PCB screws (M3 × 10 into M3 × 4 inserts
    in the base bosses)."""
    x0, x1, yf, yb = TONGUE
    h = DOCK_TONGUE_H
    pts = [(x0, yb), (x1, yb), (x1, yf - 4.5), (x1 - 4.5, yf), (x0 + 4.5, yf), (x0, yf - 4.5)]
    outer = cq.Workplane('XY').polyline(pts).close().extrude(h - 3.0).translate((0, 0, 3.0))
    outer = try_fillet(outer, '>Z', 2.5)
    inner = cq.Workplane('XY').polyline(pts).close().offset2D(-2.0).extrude(h - 3.0 - 2.0).translate((0, 0, 2.99))
    inner = inner.union(bx(x0 + 2, yb - 3, 2.99, x1 - 2, yb + 2.5, h - 2.0))      # rear end fully open
    t = outer.cut(inner)
    for (x, y) in ((-8.0, -2.5), (-8.0, 2.5), (8.0, -2.5), (8.0, 2.5)):
        X, Y = dock_xy(x, y)
        t = t.cut(cyl(1.9, 12, X, Y, DOCK_PCB_Z))
    X, Y = dock_xy(0.0, -14.4)
    t = t.cut(cyl(3.2, 12, X, Y, DOCK_PCB_Z))
    for (x, y) in ((-25.5, -13), (25.5, -13), (-25.5, 13), (25.5, 13)):
        X, Y = dock_xy(x, y)
        col = cyl(6.0, h - 2.0 - (DOCK_PCB_Z + 1.6) + 0.01, X, Y, DOCK_PCB_Z + 1.6)
        t = t.union(col).cut(cyl(3.4, 20, X, Y, 0)).cut(cyl(6.0, 2.0, X, Y, h - 1.99))
    return t

PARTS = {
    'shell_upper': (shell_upper, (0.93, 0.93, 0.92)),
    'shell_skirt': (shell_skirt, (0.17, 0.18, 0.20)),
    'top_cap': (top_cap, (0.93, 0.93, 0.92)),
    'visor': (visor, (0.04, 0.05, 0.07)),
    'halo': (halo, (0.70, 0.93, 1.00)),
    'head_bracket_L': (lambda: head_bracket(-1), (0.25, 0.25, 0.27)),
    'head_bracket_R': (lambda: head_bracket(1), (0.25, 0.25, 0.27)),
    'battery_cage': (battery_cage, (0.25, 0.25, 0.27)),
    'top_deck': (top_deck, (0.85, 0.85, 0.87)),
    'dock_plate_bar': (dock_plate_bar, (0.25, 0.25, 0.27)),
    'dock_base': (dock_base, (0.17, 0.18, 0.20)),
    'dock_tower': (dock_tower, (0.93, 0.93, 0.92)),
    'dock_tongue': (dock_tongue, (0.22, 0.23, 0.25)),
    'dock_tag_panel': (dock_tag_panel, (0.17, 0.18, 0.20)),
    'dock_lightpipe': (dock_lightpipe, (0.55, 0.95, 1.00)),
}
