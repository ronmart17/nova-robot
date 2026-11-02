"""NOVA Rev B — mass properties from the CAD model (CadQuery exact solids) + catalogue masses for bought parts.
Printed parts: volume × PETG density 1.27 g/cm³ × solid fraction (walls/infill). Writes out/mass_props.json."""
import os, sys, json, math
sys.path.insert(0, '/home/claude/robot/mech')
import cadquery as cq
import parts as P
import assembly as A
from dims import *

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
PETG = 1.27e-3          # g/mm³
FILL = dict(shell_upper=0.85, shell_skirt=0.85, top_cap=0.9, halo=1.0, head_bracket_L=0.7, head_bracket_R=0.7,
            battery_cage=0.6, top_deck=0.6, dock_plate_bar=0.7)
ACRYLIC = 1.19e-3

def vc(shape):
    s = shape.val() if hasattr(shape, 'val') else shape
    return s.Volume(), s.Center()

items = []   # (name, mass g, (x, y, z), source)
for nm, (f, _) in P.PARTS.items():
    if nm.startswith('dock_') and nm != 'dock_plate_bar':
        continue
    v, c = vc(f())
    rho = ACRYLIC if nm == 'visor' else PETG * FILL[nm]
    items.append((nm, v * rho, (c.x, c.y, c.z), f'CAD volume {v / 1000:.1f} cm³'))

# bought parts: catalogue / typical masses, positions from the CAD model
def cen(lst, key):
    sh = [s for s, _, n in lst if n.startswith(key)]
    vs = [vc(s) for s in sh]
    V = sum(v for v, _ in vs)
    return tuple(sum(v * getattr(c, a) for v, c in vs) / V for a in 'xyz')
cells = A.battery(); pi = A.pi5(); dr = A.drive(); hm = A.head_modules()
items += [
    ('battery 2S2P 18650 (4 × 46 g + strips/wrap 12 g)', 196, cen(cells, 'cell'), 'typ. 3.0–3.5 Ah cell 45–48 g'),
    ('Raspberry Pi 5', 46, cen(pi, 'pi5_pcb')[:2] + (PI_Z0 + 4.0,), 'typ.'),
    ('Pi 5 Active Cooler', 20, cen(pi, 'pi5_cooler'), 'typ.'),
    ('standoffs M2.5 (4 × 45 + 4 × 20 mm, brass)', 16, (PI_CX, PI_CY, (MB_Z1 + DECK_Z0) / 2), 'est.'),
    ('ReSpeaker XVF3800 board', 22, (0.0, XVF_CY, XVF_Z0 + 2), 'est. (Ø99 PCB)'),
    ('main board, assembled', 85, (0.0, 0.0, MB_Z0 + 2.5), 'FR-4 136×136×1.6 ≈ 52 g + parts'),
    ('head board, assembled', 22, (0.0, HEAD_Y0 + 1, (HEAD_Z0 + HEAD_Z1) / 2), 'est.'),
    ('display module 2.0"', 18, cen(hm, 'lcd'), 'typ.'),
    ('Camera Module 3', 4, cen(hm, 'cam'), 'datasheet 4 g'),
    ('N20 motors with encoders (2 × 12 g)', 24, (0.0, 0.0, AXLE_Z), 'typ.'),
    ('wheels Ø43 (2 × 10 g)', 20, (0.0, 0.0, AXLE_Z), 'typ.'),
    ('motor brackets (4)', 10, (0.0, 0.0, AXLE_Z + 3), 'est.'),
    ('ball caster (Ø12.7 steel ball + body)', 12, (0.0, CASTER_Y, 8.0), 'typ.'),
    ('speaker 40 mm 3 W', 18, (SPEAKER[0], SPEAKER[1] + 6, SPEAKER[2]), 'typ.'),
    ('cables (USB-C to Pi, J701 ribbon, head, motors, FPC)', 25, (5.0, 0.0, 60.0), 'est.'),
    ('screws, inserts, contact plate', 12, (0.0, -30.0, 30.0), 'est.'),
]
M = sum(m for _, m, _, _ in items)
cg = tuple(sum(m * p[k] for _, m, p, _ in items) / M for k in range(3))
res = dict(mass_g=M, cg_mm=cg, items=[dict(name=n, mass_g=m, pos_mm=p, src=s) for n, m, p, s in items])
json.dump(res, open(os.path.join(OUT, 'mass_props.json'), 'w'), indent=1)
for n, m, p, s in items:
    print(f'{n:52s} {m:6.1f} g  ({p[0]:6.1f}, {p[1]:6.1f}, {p[2]:6.1f})  {s}')
print(f'TOTAL {M:.0f} g, CoG = ({cg[0]:.1f}, {cg[1]:.1f}, {cg[2]:.1f}) mm')
