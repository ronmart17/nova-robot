import cadquery as cq
OUT = '/home/claude/robot/kicad/lib/robot.3dshapes/'
BLACK = cq.Color(0.12, 0.12, 0.12); METAL = cq.Color(0.82, 0.82, 0.80); GREY = cq.Color(0.35, 0.35, 0.37)
BEIGE = cq.Color(0.93, 0.90, 0.80); BLUE = cq.Color(0.15, 0.20, 0.45); TIN = cq.Color(0.75, 0.75, 0.72)

def box(x, y, z, cx=0, cy=0, z0=0, fillet=0):
    b = cq.Workplane('XY').box(x, y, z, centered=(True, True, False)).translate((cx, cy, z0))
    if fillet:
        try: b = b.edges('|Z').fillet(fillet)
        except Exception: pass
    return b

def save(name, parts):
    a = cq.Assembly(name=name)
    for i, (shape, color) in enumerate(parts):
        a.add(shape, name=f'{name}_{i}', color=color)
    a.save(OUT + name + '.step', 'STEP')
    print('saved', name)

def mirror_y(v):  # KiCad footprint Y is down; 3D model Y is up
    return -v

# SOT-583-8 (TI DRL): body 2.1 x 1.2? use 1.6 x 2.1 footprint fab: pins at x=+-0.74, pitch 0.5
def sot583():
    parts = [(box(1.2, 2.1, 0.55, z0=0.05), BLACK)]
    for i, y in enumerate((-0.75, -0.25, 0.25, 0.75)):
        for x in (-0.74, 0.74):
            parts.append((box(0.35, 0.2, 0.15, cx=x * 1.0, cy=mirror_y(y)), TIN))
    save('SOT-583-8', parts)

def tqfn16():
    parts = [(box(3.0, 3.0, 0.75, z0=0.0), BLACK)]
    for k in range(4):
        y = -0.75 + 0.5 * k
        for x in (-1.45, 1.45):
            parts.append((box(0.4, 0.25, 0.2, cx=x, cy=mirror_y(y)), TIN))
        for yy in (-1.45, 1.45):
            parts.append((box(0.25, 0.4, 0.2, cx=y, cy=yy), TIN))
    parts.append((box(1.23, 1.23, 0.02, z0=-0.0), TIN))
    save('TQFN-16-1EP_3x3mm_P0.5mm_EP1.23x1.23mm', parts)

def ihlp2525():
    parts = [(box(6.47, 6.86, 3.0, z0=0.0, fillet=0.4), GREY)]
    for x in (-2.921, 2.921):
        parts.append((box(1.6, 3.0, 0.3, cx=x * 1.05), TIN))
    save('L_Vishay_IHLP-2525', parts)

def srp5030():
    parts = [(box(5.4, 5.2, 3.0, z0=0.0, fillet=0.3), GREY)]
    for x in (-2.25, 2.25):
        parts.append((box(1.5, 1.6, 0.3, cx=x * 1.08), TIN))
    save('L_Bourns_SRP5030T', parts)

def pa4332():
    """Pulse PA4332 (4.2 × 4.2 × 2.0 mm), bottom terminals at x = ±1.5 mm."""
    parts = [(box(4.2, 4.2, 2.0, z0=0.0, fillet=0.25), GREY)]
    for x in (-1.5, 1.5):
        parts.append((box(0.9, 3.4, 0.2, cx=x, z0=-0.05), TIN))
    save('L_Pulse_PA4332', parts)

def pts810():
    body = box(4.2, 3.2, 1.6, z0=0.0)
    cap = cq.Workplane('XY').circle(0.9).extrude(0.9).translate((0, 0, 1.6))
    parts = [(body, BLACK), (cap, BEIGE)]
    for x in (-2.075, 2.075):
        for y in (-1.075, 1.075):
            parts.append((box(0.8, 0.5, 0.2, cx=x * 1.02, cy=mirror_y(y)), TIN))
    save('SW_SPST_PTS810', parts)

def jst_sh20():
    n = 20; w = (n - 1) * 1.0 + 4.0
    housing = box(w, 4.25, 2.9, cy=mirror_y(0.6), z0=0.0)
    cavity = box(w - 1.2, 3.0, 1.9, cy=mirror_y(1.4), z0=0.5)
    housing = housing.cut(cavity)
    parts = [(housing, BEIGE)]
    for k in range(n):
        x = -9.5 + k
        parts.append((box(0.3, 1.2, 0.2, cx=x, cy=mirror_y(-2.1)), TIN))
    for x in (-10.8, 10.8):
        parts.append((box(1.0, 1.6, 0.25, cx=x, cy=mirror_y(1.875)), TIN))
    save('JST_SH_SM20B-SRSS-TB_1x20-1MP_P1.00mm_Horizontal', parts)

def tcrt5000():
    """Vishay TCRT5000 aligned with OptoDevice:Vishay_TCRT5000 (KiCad 10): pad 1 at the origin,
    pads 1-2 at x=0 (IR emitter, blue), 3-4 at x=5.5 (phototransistor, black), clips at x=2.75."""
    cx, cy = 2.75, mirror_y(1.27)
    emi = box(5.1, 5.8, 7.0, cx=cx - 2.55, cy=cy, z0=0.0)
    det = box(5.1, 5.8, 7.0, cx=cx + 2.55, cy=cy, z0=0.0)
    lens_e = cq.Workplane('XY').circle(1.3).extrude(0.2).translate((cx - 2.55, cy, 7.0))
    lens_d = cq.Workplane('XY').circle(1.3).extrude(0.2).translate((cx + 2.55, cy, 7.0))
    parts = [(det, BLACK), (emi, BLUE), (lens_e, cq.Color(0.6, 0.6, 0.9)), (lens_d, cq.Color(0.25, 0.25, 0.25))]
    for x, y in ((0, 0), (0, 2.54), (5.5, 2.54), (5.5, 0)):
        parts.append((box(0.5, 0.5, 3.5 + 1.0, cx=x, cy=mirror_y(y), z0=-3.5), METAL))
    for x, y in ((2.75, -0.63), (2.75, 3.17)):   # mounting clips
        parts.append((cq.Workplane('XY').circle(1.1).extrude(2.6).translate((x, mirror_y(y), -2.6)), BLACK))
    save('Vishay_TCRT5000', parts)

def rqm0029():
    """TI RQM0029A VQFN-HR 4 x 4 x 1.0 mm (BQ25798); terminals per KiCad footprint (KiCad Y down -> model Y up)."""
    parts = [(box(4.0, 4.0, 0.9, z0=0.05), BLACK)]
    marker = cq.Workplane('XY').circle(0.18).extrude(0.02).translate((-1.5, 1.5, 0.95))
    parts.append((marker, GREY))
    for i in range(7):
        y = -1.2 + 0.4 * i
        for x in (-1.9, 1.9):
            parts.append((box(0.3, 0.18, 0.12, cx=x, cy=mirror_y(y)), TIN))
    for x in (-1.0, -0.6, -0.2, 0.2, 0.6, 1.0):
        parts.append((box(0.18, 0.3, 0.12, cx=x, cy=mirror_y(1.9)), TIN))
    for x in (-0.9, -0.45, 0.0, 0.45, 0.9):
        parts.append((box(0.18, 0.8, 0.12, cx=x, cy=mirror_y(-1.6)), TIN))
    save('Texas_RQM0029A_VQFN-29_4x4mm_P0.4mm', parts)

def rqf0009():
    """TI RQF0009A VQFN-HR 1.5 x 2.0 x 1.0 mm (TPS566238)."""
    parts = [(box(1.5, 2.0, 0.9, z0=0.05), BLACK)]
    parts.append((cq.Workplane('XY').circle(0.1).extrude(0.02).translate((-0.45, 0.7, 0.95)), GREY))
    for x, y, w, h in ((-0.6, -0.5, 0.3, 0.2), (-0.6, 0, 0.3, 0.2), (-0.6, 0.5, 0.3, 0.2), (0.6, -0.5, 0.3, 0.2),
                       (0.6, 0, 0.3, 0.2), (0.6, 0.5, 0.3, 0.2), (-0.25, -0.675, 0.2, 0.5), (0.25, -0.3, 0.2, 1.25), (-0.25, 0.45, 0.2, 0.95)):
        parts.append((box(w, h, 0.1, cx=x, cy=mirror_y(y)), TIN))
    save('Texas_RQF0009A_VQFN-HR-9_1.5x2mm_P0.5mm', parts)

def vl53l4cd():
    """ST VL53L4CD optical LGA12 4.4 x 2.4 x 1.0 mm with the emitter/receiver windows."""
    parts = [(box(4.4, 2.4, 1.0, z0=0.0), BLACK)]
    for x, c in ((-1.2, cq.Color(0.55, 0.35, 0.10)), (1.2, cq.Color(0.20, 0.20, 0.25))):
        parts.append((cq.Workplane('XY').circle(0.45).extrude(0.02).translate((x, 0, 1.0)), c))
    save('ST_VL53L4CD', parts)

def fuse1812():
    parts = [(box(2.9, 3.2, 1.1, z0=0.0), cq.Color(0.15, 0.35, 0.20))]
    for x in (-1.95, 1.95):
        parts.append((box(0.6, 3.2, 1.15, cx=x), TIN))
    save('Fuse_1812_4532Metric', parts)

def nano2():
    """Littelfuse NANO2 451/453 (2410): 6.1 x 2.69 x 2.69 mm, end caps 1.4 mm."""
    parts = [(box(3.3, 2.69, 2.69, z0=0.0), cq.Color(0.85, 0.85, 0.80))]
    for x in (-2.35, 2.35):
        parts.append((box(1.4, 2.69, 2.69, cx=x), TIN))
    save('Fuse_Littelfuse-NANO2-451_453', parts)

def pogo_ytc1p():
    """YIYUAN YTC1P-8020-01 (datasheet table, type 8020): flange D2.0, barrel D1.5 to 8.5 mm, plunger D0.9, 10.0 mm free."""
    base = cq.Workplane('XY').circle(1.0).extrude(0.4)
    barrel = cq.Workplane('XY').circle(0.75).extrude(8.1).translate((0, 0, 0.4))
    plunger = cq.Workplane('XY').circle(0.45).extrude(1.05).translate((0, 0, 8.5))
    tip = cq.Workplane('XY').sphere(0.45).translate((0, 0, 9.55))
    gold = cq.Color(0.85, 0.68, 0.25)
    save('Pogo_YTC1P-8020_D2.0mm', [(base, gold), (barrel, gold), (plunger, gold), (tip, gold)])

def dc005():
    """XKB DC-005-5A-2.0: body 14.0 x 9.0 x 11 mm, front face 13.6 mm in front of the centre pin (-x), bore D6.2 on 6.5 mm."""
    body = cq.Workplane('XY').box(14.0, 9.0, 11.0, centered=(True, True, False)).translate((-6.6, 0, 0))
    bore = cq.Workplane('YZ').circle(3.1).extrude(9.0).translate((-13.61, 0, 6.5))
    body = body.cut(bore)
    pin = cq.Workplane('YZ').circle(1.0).extrude(8.0).translate((-12.5, 0, 6.5))
    parts = [(body, BLACK), (pin, METAL)]
    for x, y, w, l in ((0.0, 0.0, 0.35, 3.0), (-5.9, 0.0, 0.35, 3.0), (-3.0, -4.7, 3.0, 0.35)):
        parts.append((box(w, l, 3.5, cx=x, cy=y, z0=-3.5), TIN))
    save('DC_Jack_XKB_DC-005-5A-2.0_Horizontal', parts)

import sys as _s
for f in ([globals()[n] for n in _s.argv[1:]] or (sot583, srp5030, pts810, jst_sh20, rqm0029, rqf0009, vl53l4cd, fuse1812, nano2, pogo_ytc1p, dc005)):
    f()
