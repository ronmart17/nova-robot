"""Board output: router tracks/vias, planes and pours, rule areas, zone fill (pcbnew) and DRC."""
import os, sys, json, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union
import main_pcb as M

CLI = '/opt/kicad10/bin/kicad-cli'
LIBENV = dict(KICAD10_FOOTPRINT_DIR='/opt/kicad10libs/root/usr/share/kicad/footprints',
              KICAD10_SYMBOL_DIR='/opt/kicad10libs/root/usr/share/kicad/symbols',
              KICAD10_3DMODEL_DIR='/usr/share/kicad/3dmodels')
CLIENV = dict(os.environ, **LIBENV)
PYENV = dict(os.environ, KICAD_RUN_FROM_BUILD_DIR='1', PYTHONPATH='/opt/src/kicad/build/pcbnew', **LIBENV)
HERE = os.path.dirname(os.path.abspath(__file__))

def ring(poly):
    g = poly if poly.geom_type == 'Polygon' else max(poly.geoms, key=lambda q: q.area)
    return [(round(x, 4), round(y, 4)) for x, y in list(g.exterior.coords)[:-1]]

def zones(b, usable, keep, planes, F):
    outline = ring(usable.buffer(0))
    # inner planes
    b.zone('GND', 'In1.Cu', outline, priority=0, clearance=0.25, min_w=0.2, connect='tht', name='GND (In1)')
    vs = planes['VSYS'][0][1]
    for g in getattr(vs, 'geoms', [vs]):
        b.zone('VSYS', 'In2.Cu', ring(g.buffer(0.2, join_style=2)), priority=2, clearance=0.25, min_w=0.2, connect='tht', name='VSYS (In2)')
    b.zone('+3V3', 'In2.Cu', outline, priority=1, clearance=0.25, min_w=0.2, connect='tht', name='+3V3 (In2)')
    # GND pours on the outer layers (THT with thermal relief, SMD solid connection)
    b.zone('GND', 'F.Cu', outline, priority=0, clearance=0.25, min_w=0.2, connect='tht', name='GND (F)')
    b.zone('GND', 'B.Cu', outline, priority=0, clearance=0.25, min_w=0.2, connect='tht', name='GND (B)')
    for net, layer, poly, prio in F.zones:
        b.zone(net, layer, ring(poly), priority=3 + prio, clearance=0.2, min_w=0.2, connect='solid')
    # rule areas
    for name, kp, sides, ex in keep:
        if name in ('N20 motor and brackets', 'caster'):
            for g in getattr(kp, 'geoms', [kp]):
                b.keepout(['B.Cu'], ring(g), tracks=False, vias=False, pads=True, pour=False, fps=True, name=f'No copper: {name}')
        elif name.startswith('screw head'):
            for g in getattr(kp, 'geoms', [kp]):
                b.keepout(['F.Cu', 'B.Cu'], ring(g), tracks=False, vias=False, pads=True, pour=False, fps=True,
                          name='No copper: screw head')
    for ref in ('FID1', 'FID2', 'FID3'):
        pl = b.placed[ref]
        c = Point(pl.x, pl.y).buffer(1.6, 32)
        b.keepout(['F.Cu'], ring(c), tracks=False, vias=False, pads=True, pour=False, fps=True, name=f'Fiducial {ref}')

def fill_and_save(path, silk=True, profile='main', power=None, straight=True):
    """power: dict(widths={net: nominal width}, paths={net: (sources, sinks)}) → power reinforcement (power.py)
    before silkscreen and zone fill."""
    pj = json.dumps(power or {})
    code = f'''
import sys, json
sys.path.insert(0, {HERE!r})
import pcbnew
b = pcbnew.LoadBoard({path!r})
P = json.loads({pj!r})
if {straight!r}:
    import straighten
    straighten.straighten(b)
if P:
    import power
    power.reinforce(b, P['widths'], {{k: tuple(v) for k, v in P['paths'].items()}})
if {silk!r}:
    import silk, mech
    silk.run(b, {profile!r})
    dict(main=mech.main_board, head=mech.head_board, dock=mech.dock_board)[{profile!r}](b)
f = pcbnew.ZONE_FILLER(b)
f.Fill(b.Zones())
pcbnew.SaveBoard({path!r}, b)
print('zones', len(b.Zones()))
'''
    r = subprocess.run([sys.executable, '-c', code], env=PYENV, capture_output=True, text=True, timeout=900)
    print(r.stdout.strip()[-3000:], r.stderr.strip()[-1500:])

def cleanup(path, drc_json):
    """Post-DRC cosmetic cleanup: deletes dangling track stubs / single-layer vias and the footprint silkscreen items
    that DRC flags (clipped by the board edge or a pad, overlapping silk), then refills the zones."""
    code = f'''
import json, re
import pcbnew
b = pcbnew.LoadBoard({path!r})
d = json.load(open({drc_json!r}))
mm = pcbnew.FromMM
def P(it): return pcbnew.VECTOR2I(mm(it['pos']['x']), mm(it['pos']['y']))
n_tr = n_si = 0
want = {{}}
for v in d['violations']:
    t = v['type']; its = v['items']
    if t in ('track_dangling', 'via_dangling'):
        want[its[0]['uuid']] = 'track'
    elif t in ('silk_edge_clearance', 'silk_over_copper', 'silk_overlap'):
        it = its[0] if 'Silkscreen' in its[0]['description'] else its[1]
        want[it['uuid']] = 'silk'
for tr in list(b.GetTracks()):
    if tr.m_Uuid.AsString() in want:
        b.Delete(tr); n_tr += 1
for fp in b.GetFootprints():
    for g in list(fp.GraphicalItems()):
        if g.m_Uuid.AsString() in want:
            fp.Delete(g); n_si += 1
f = pcbnew.ZONE_FILLER(b)
f.Fill(b.Zones())
pcbnew.SaveBoard({path!r}, b)
print('cleanup: removed', n_tr, 'dangling items,', n_si, 'silk items')
'''
    r = subprocess.run([sys.executable, '-c', code], env=PYENV, capture_output=True, text=True, timeout=900)
    print(r.stdout.strip()[-2000:], r.stderr.strip()[-1500:])

def drc(path, out_json):
    r = subprocess.run([CLI, 'pcb', 'drc', '--format', 'json', '--severity-all', '--schematic-parity', '--units', 'mm',
                        '-o', out_json, path], capture_output=True, text=True, timeout=900, env=CLIENV)
    d = json.load(open(out_json))
    return d

def summarize(d, maxn=40):
    from collections import Counter
    v = d.get('violations', [])
    u = d.get('unconnected_items', [])
    p = d.get('schematic_parity', [])
    c = Counter((x['type'], x['severity']) for x in v)
    print(f'DRC: {len(v)} violations, {len(u)} unconnected, {len(p)} parity')
    for (t, s), n in c.most_common():
        print(f'  {s:8s} {t}: {n}')
    return v, u, p
