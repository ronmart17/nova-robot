"""NOVA Rev B — full 3D assembly: KiCad board STEPs (main, head, dock + contact plate), printed parts (parts.py) and
simplified purchased parts. Writes per-part STEP/STL, the assembly STEP/GLB and PNG renders.
Run:  xvfb-run -a python3 assembly.py [--parts-only]"""
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cadquery as cq
from dims import *
import parts as P

KICAD = '/home/claude/robot/kicad'
OUT = os.environ.get('MECH_OUT', '/home/claude/robot/mech/out')
PARTS_OUT = os.path.join(OUT, 'parts')

def C(r, g, b): return cq.Color(r, g, b)
GREEN, BLACK, ALU, GOLD, WHITE = C(0.10, 0.42, 0.20), C(0.08, 0.08, 0.09), C(0.80, 0.80, 0.82), C(0.85, 0.68, 0.25), C(0.95, 0.95, 0.95)

def loc(rot_rows, t):
    """cq.Location from a 3×3 rotation (rows) and a translation."""
    import OCP
    from OCP.gp import gp_Trsf, gp_Mat, gp_XYZ
    tr = gp_Trsf()
    r = rot_rows
    tr.SetValues(r[0][0], r[0][1], r[0][2], t[0], r[1][0], r[1][1], r[1][2], t[1], r[2][0], r[2][1], r[2][2], t[2])
    return cq.Location(tr)

def read_step_colored(path):
    """[(cq.Shape, cq.Color)] of a STEP file with its XCAF colours (KiCad STEP: one colour per solid or per face)."""
    from OCP.STEPCAFControl import STEPCAFControl_Reader
    from OCP.TDocStd import TDocStd_Document
    from OCP.XCAFDoc import XCAFDoc_DocumentTool, XCAFDoc_ColorSurf, XCAFDoc_ColorGen
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.TDF import TDF_LabelSequence
    from OCP.Quantity import Quantity_Color
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopAbs import TopAbs_SOLID, TopAbs_FACE
    from OCP.TopLoc import TopLoc_Location
    doc = TDocStd_Document(TCollection_ExtendedString('doc'))
    r = STEPCAFControl_Reader(); r.SetColorMode(True); r.SetNameMode(True)
    r.ReadFile(path); r.Transfer(doc)
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main()); ct = XCAFDoc_DocumentTool.ColorTool_s(doc.Main())
    out = []
    def colour_of(label, shape):
        c = Quantity_Color()
        for typ in (XCAFDoc_ColorSurf, XCAFDoc_ColorGen):
            if ct.GetColor_s(label, typ, c) or ct.GetColor(shape, typ, c):
                return cq.Color(c.Red(), c.Green(), c.Blue())
        ex = TopExp_Explorer(shape, TopAbs_FACE)
        if ex.More() and (ct.GetColor(ex.Current(), XCAFDoc_ColorSurf, c) or ct.GetColor(ex.Current(), XCAFDoc_ColorGen, c)):
            return cq.Color(c.Red(), c.Green(), c.Blue())
        return None
    def walk(label, loc):
        if st.IsAssembly_s(label):
            comps = TDF_LabelSequence(); st.GetComponents_s(label, comps)
            for i in range(1, comps.Length() + 1):
                cl = comps.Value(i)
                ref = cq.occ_impl.shapes.TDF_Label() if False else None
                from OCP.TDF import TDF_Label
                rl = TDF_Label()
                st.GetReferredShape_s(cl, rl)
                walk(rl, loc.Multiplied(st.GetLocation_s(cl)))
        else:
            shp = st.GetShape_s(label)
            col = colour_of(label, shp)
            ex = TopExp_Explorer(shp, TopAbs_SOLID)
            n = 0
            while ex.More():
                s = ex.Current(); c = colour_of(label, s) or col
                out.append((cq.Shape.cast(s.Moved(loc)), c)); n += 1; ex.Next()
            if n == 0:
                out.append((cq.Shape.cast(shp.Moved(loc)), col))
    labels = TDF_LabelSequence(); st.GetFreeShapes(labels)
    for i in range(1, labels.Length() + 1):
        walk(labels.Value(i), TopLoc_Location())
    return out

def board_step(name):
    p = f'{KICAD}/nova-{name}/fabrication/nova-{name}.step'
    if not os.path.exists(p):
        return None
    a = cq.Assembly(name=f'{name}_pcb')
    for i, (s, c) in enumerate(read_step_colored(p)):
        a.add(s, name=f'{name}_{i}', color=c if c is not None else GREEN)
    return a

# ------------------------------------------------------------------ purchased parts (simplified)
def drive():
    out = []
    for s in (-1, 1):
        w = cq.Workplane('YZ').circle(WHEEL_D / 2).extrude(WHEEL_W).translate((s * WHEEL_X - WHEEL_W / 2, 0, AXLE_Z))
        w = w.cut(cq.Workplane('YZ').circle(WHEEL_D / 2 - 4).extrude(WHEEL_W - 4).translate((s * WHEEL_X - WHEEL_W / 2 + 2 * (s > 0), 0, AXLE_Z)))
        hub = cq.Workplane('YZ').circle(WHEEL_D / 2 - 4).extrude(WHEEL_W - 6).translate((s * WHEEL_X - WHEEL_W / 2 + 3, 0, AXLE_Z))
        out += [(w, BLACK, f'wheel_{s}'), (hub, C(0.9, 0.9, 0.9), f'hub_{s}')]
        m = P.bx(min(s * MOTOR_X[0], s * MOTOR_X[1]), -MOTOR_W / 2, AXLE_Z - MOTOR_H / 2,
                 max(s * MOTOR_X[0], s * MOTOR_X[1]), MOTOR_W / 2, AXLE_Z + MOTOR_H / 2)
        out.append((m, ALU, f'n20_{s}'))
        sh = cq.Workplane('YZ').circle(1.5).extrude(WHEEL_X - MOTOR_X[1]).translate((min(s * MOTOR_X[1], s * WHEEL_X), 0, AXLE_Z))
        out.append((sh, ALU, f'shaft_{s}'))
        for bxx in BRK_X:
            br = P.bx(s * bxx - 5.5, -BRK_Y - 1.5, AXLE_Z - MOTOR_H / 2 - 1.0, s * bxx + 5.5, BRK_Y + 1.5, MB_Z0)
            br = br.cut(P.bx(s * bxx - 6, -MOTOR_W / 2 - 0.01, AXLE_Z - MOTOR_H / 2 - 0.01, s * bxx + 6, MOTOR_W / 2 + 0.01, MB_Z0 - 1.0))
            out.append((br, C(0.6, 0.6, 0.62), f'bracket_{s}_{bxx}'))
    return out

def caster():
    ball = cq.Workplane('XY').sphere(6.35).translate((0, CASTER_Y, 6.35))
    body = P.rrect(22, 12, MB_Z0 - 8.0, 3, 0, CASTER_Y, 8.0)
    return [(ball, ALU, 'caster_ball'), (body, BLACK, 'caster_body')]

def battery():
    out = []
    for i in (-1, 1):
        for k in (0, 1):
            c = (cq.Workplane('XZ').circle(CELL_D / 2).extrude(-CELL_L)
                 .translate((i * (CELL_D / 2 + 0.4), BAT_Y0 + 1.3, MB_Z1 + 0.5 + 0.8 + CELL_D / 2 + k * (CELL_D + 0.4))))
            out.append((c, C(0.12, 0.30, 0.70), f'cell_{i}_{k}'))
    return out

def pi_box(u0, u1, v0, v1, h, z):
    (xa, ya), (xb, yb) = pi_xy(u0, v0), pi_xy(u1, v1)
    return P.bx(min(xa, xb), min(ya, yb), z, max(xa, xb), max(ya, yb), z + h)

def pi5():
    z0 = PI_Z0; zt = z0 + PI_T
    board = P.rrect(PI_D, PI_W, PI_T, 3.0, PI_CX, PI_CY, z0)
    for u, v in PI_HOLES_UV:
        X, Y = pi_xy(u, v)
        board = board.cut(P.cyl(2.7, 5, X, Y, z0 - 1))
    out = [(board, GREEN, 'pi5_pcb')]
    out.append((pi_box(10, 52, 10, 52, COOLER_H - 3, zt + 3), ALU, 'pi5_cooler'))
    out.append((P.cyl(28, 3, *pi_xy(31, 31), zt + COOLER_H - 3).translate((0, 0, 0)), BLACK, 'pi5_fan'))
    out.append((pi_box(66, 87, 2, 20, 16, zt), ALU, 'pi5_rj45'))
    out.append((pi_box(66, 88, 21, 37, 16, zt), ALU, 'pi5_usb3'))
    out.append((pi_box(66, 88, 39, 54, 16, zt), ALU, 'pi5_usb2'))
    out.append((pi_box(7.1, 57.9, 49.9, 55.1, 8.5, zt), BLACK, 'pi5_gpio'))
    out.append((pi_box(7.6, 14.8, -1.2, 6.2, 3.2, zt), ALU, 'pi5_usbc'))
    for u in PI_HDMI_U:
        out.append((pi_box(u - 3.5, u + 3.5, -1.0, 6.5, 3.0, zt), ALU, f'pi5_hdmi_{u}'))
    for u, v in PI_HOLES_UV:
        X, Y = pi_xy(u, v)
        out.append((P.cyl(4.6, PI_STANDOFF, X, Y, MB_Z1), GOLD, f'standoff_{u}_{v}'))
        out.append((P.cyl(4.6, DECK_Z0 - zt, X, Y, zt), GOLD, f'standoff_top_{u}_{v}'))
    return out

def xvf3800():
    d = P.cyl(XVF_D, 1.2, 0.0, XVF_CY, XVF_Z0)
    out = [(d, BLACK, 'xvf3800_pcb')]
    for k in range(4):
        a = math.radians(45 + 90 * k)
        out.append((P.cyl(3.0, 1.0, P.XVF_MIC_R * math.cos(a), XVF_CY + P.XVF_MIC_R * math.sin(a), XVF_Z0 + 1.2), ALU, f'mic_{k}'))
    for k in range(12):
        a = math.radians(30 * k)
        out.append((P.bx(-1, -1, 0, 1, 1, 0.6).translate((40 * math.cos(a), XVF_CY + 40 * math.sin(a), XVF_Z0 + 1.2)),
                    WHITE, f'led_{k}'))
    return out

def speaker():
    X, Y, Z = SPEAKER
    yi = -SHELL_D / 2 + SHELL_WALL
    cone = P.cyl(40, 14, X, yi, Z, axis='Y')
    return [(cone, C(0.2, 0.2, 0.22), 'speaker')]

def head_modules():
    """Display module and Camera Module 3 on the front of the head board (head x = robot −X)."""
    yf = HEAD_Y0 + HEAD_T
    zl = HEAD_Z0 + HEAD_LCD_ZC
    out = []
    pcb = P.bx(-30.56, yf + 8.5, zl - 18.24, 30.56, yf + 10.1, zl + 18.24)
    out.append((pcb, C(0.10, 0.25, 0.55), 'lcd_pcb'))
    out.append((P.bx(-25.6, yf + 10.1, zl - 17.85, 25.6, yf + 12.3, zl + 17.85), BLACK, 'lcd_glass'))
    eyes = None
    for xx in (-11.0, 11.0):
        e = cq.Workplane('XZ').rect(11.0, 16.0).extrude(-0.1).edges('|Y').fillet(5.0).translate((xx, yf + 12.3, zl + 1.0))
        eyes = e if eyes is None else eyes.union(e)
    out.append((eyes, C(0.30, 0.85, 0.95), 'lcd_eyes'))
    for xx in (-28.0, ):
        out.append((P.bx(xx - 1.27, yf, zl - 10.16, xx + 1.27, yf + 8.5, zl + 10.16), BLACK, 'lcd_header'))
    zc = HEAD_Z0 + HEAD_CAM_TOP - 23.862 / 2
    cam = P.bx(-12.5, yf + 2.5, zc - 11.93, 12.5, yf + 3.5, zc + 11.93)
    out.append((cam, GREEN, 'cam_pcb'))
    zlz = HEAD_Z0 + HEAD_CAM_LENS_Z
    out.append((P.bx(-5.4, yf + 3.5, zlz - 5.4, 5.4, yf + 8.0, zlz + 5.4), BLACK, 'cam_block'))
    out.append((P.cyl(7.0, 6.5, 0, yf + 8.0, zlz, axis='Y'), BLACK, 'cam_lens'))
    out.append((P.cyl(4.0, 0.2, 0, yf + 14.5, zlz, axis='Y'), C(0.2, 0.3, 0.6), 'cam_glass'))
    for (x, z) in ((-10.5, HEAD_CAM_TOP - 2.0), (10.5, HEAD_CAM_TOP - 2.0), (-10.5, HEAD_CAM_TOP - 14.5), (10.5, HEAD_CAM_TOP - 14.5)):
        out.append((P.cyl(4.0, 2.5, -x, yf, HEAD_Z0 + z, axis='Y'), GOLD, f'cam_standoff_{x}_{z}'))
    return out

def placeholders():
    """Simple boards when the KiCad STEPs are not exported yet."""
    out = [(P.rrect(MB_W, MB_D, MB_T, MB_R, 0, 0, MB_Z0), GREEN, 'main_board')]
    out.append((P.bx(-HEAD_W / 2, HEAD_Y0, HEAD_Z0, HEAD_W / 2, HEAD_Y0 + HEAD_T, HEAD_Z1), GREEN, 'head_board'))
    return out

# ------------------------------------------------------------------ assembly
SHELL_PARTS = ('shell_upper', 'shell_skirt', 'visor', 'halo', 'top_cap')
def build(shell=True, explode=0.0):
    a = cq.Assembly(name='NOVA_RevB')
    main = board_step('main'); head = board_step('head'); dock = board_step('dock')
    ph = {nm: (sh, col) for sh, col, nm in placeholders()}
    if main is not None:
        a.add(main, name='main_board', loc=cq.Location((-150.0, 100.0, MB_Z0)))
    else:
        a.add(ph['main_board'][0], name='main_board', color=ph['main_board'][1])
    if head is not None:
        # head STEP (X_s, Y_s, Z_s) = (150 + x, z − 156, through the board) → robot (−x, HEAD_Y0 + Z_s, HEAD_Z0 + z)
        a.add(head, name='head_board', loc=loc(((-1, 0, 0), (0, 0, 1), (0, 1, 0)), (150.0, HEAD_Y0, HEAD_Z0 + 156.0)))
    else:
        a.add(ph['head_board'][0], name='head_board', color=ph['head_board'][1])
    for lst in (drive(), caster(), battery(), pi5(), xvf3800(), speaker(), head_modules()):
        for sh, col, nm in lst:
            a.add(sh, name=nm, color=col)
    for nm, (f, col) in P.PARTS.items():
        if nm.startswith('dock_') and nm != 'dock_plate_bar':
            continue
        if nm in SHELL_PARTS and not shell:
            continue
        z = (explode if nm in ('shell_upper', 'visor', 'halo', 'top_cap') else
             (-explode * 0.25 if nm == 'shell_skirt' else (explode * 0.45 if nm == 'top_deck' else 0.0)))
        a.add(f(), name=nm, color=cq.Color(*col), loc=cq.Location((0, 0, z)))
    plate, pads = P.dock_contact_plate()
    a.add(plate, name='contact_plate', color=GREEN); a.add(pads, name='contact_pads', color=GOLD)
    return a

def flatten(asm, parent=None, out=None, color=None):
    """[(Shape located in world, cq.Color or None, name)] of an assembly tree."""
    out = [] if out is None else out
    L = asm.loc if parent is None else parent * asm.loc
    col = asm.color if asm.color is not None else color
    if asm.obj is not None:
        objs = asm.obj.vals() if hasattr(asm.obj, 'vals') else [asm.obj]
        for o in objs:
            if hasattr(o, 'moved'):
                out.append((o.moved(L), col, asm.name))
    for ch in asm.children:
        flatten(ch, L, out, col)
    return out

def build_dock(with_robot=None):
    """Dock: base, tongue and the dock PCB (the break-away contact plate is removed: it lives under the robot)."""
    d = cq.Assembly(name='NOVA_dock_RevB')
    dock = board_step('dock')
    if dock is not None:
        # dock STEP (X_s, Y_s) = (150 + x, −100 − y) → robot (x, DOCK_PLATE_Y − y): translation only
        w = cq.Assembly(name='dock_board', loc=cq.Location((-150.0, 100.0 + DOCK_PLATE_Y, DOCK_PCB_Z)))
        w.add(dock, name='step')
        k = 0
        keep_box = cq.Solid.makeBox(200, 400, 100, cq.Vector(-29.6, -250, -10))
        for shp, col, nm in flatten(w):
            bb = shp.BoundingBox()
            if bb.xmax < -29.6:                        # contact plate parts and the tabs
                continue
            if bb.xmin < -29.6:                        # board body shared with the plate: keep the dock part only
                shp = shp.intersect(keep_box)
            d.add(shp, name=f'dock_pcb_{k}', color=col if col is not None else GREEN); k += 1
    for nm in ('dock_base', 'dock_tower', 'dock_tongue', 'dock_lightpipe', 'dock_tag_panel'):
        f, col = P.PARTS[nm]
        d.add(f(), name=nm, color=cq.Color(*col))
    tw, tb = P.dock_tag()
    d.add(tw, name='dock_tag_white', color=cq.Color(0.97, 0.97, 0.97))
    d.add(tb, name='dock_tag_black', color=cq.Color(0.02, 0.02, 0.02))
    return d

def export_parts():
    os.makedirs(PARTS_OUT, exist_ok=True)
    for nm, (f, col) in P.PARTS.items():
        s = f()
        cq.exporters.export(s, os.path.join(PARTS_OUT, f'NOVA_{nm}.step'))
        cq.exporters.export(s, os.path.join(PARTS_OUT, f'NOVA_{nm}.stl'), tolerance=0.05, angularTolerance=0.2)
        print('part', nm)

if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    if '--parts-only' in sys.argv:
        export_parts(); sys.exit(0)
    export_parts()
    a = build(shell=True)
    a.save(os.path.join(OUT, 'NOVA_RevB_assembly.step'), 'STEP')
    d = build_dock()
    d.save(os.path.join(OUT, 'NOVA_RevB_dock.step'), 'STEP')
    print('saved')
