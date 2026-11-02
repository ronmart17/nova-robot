"""Exports the kicadxml netlist of each project and generates the full BOM and the JLCPCB BOM (CSV)."""
import os, sys, subprocess, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bom
CLI = '/opt/kicad10/bin/kicad-cli'
BASE = os.environ.get('ROBOT_OUT', '/home/claude/robot/kicad')
for name in ('nova-main', 'nova-head', 'nova-dock'):
    d = f'{BASE}/{name}'; out = f'{d}/fabrication'; os.makedirs(out, exist_ok=True)
    xml = f'{out}/{name}.xml'
    r = subprocess.run([CLI, 'sch', 'export', 'netlist', '--format', 'kicadxml', '-o', xml, f'{d}/{name}.kicad_sch'], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    full, jlc, groups = bom.write_boms(xml, out, name)
    os.remove(xml)
    n_parts = sum(len(cs) for k, cs in groups.items() if not k[3])
    miss = [(k[0], [c['ref'] for c in cs]) for k, cs in groups.items() if not k[3] and not cs[0].get('LCSC')]
    print(f'{name}: {len(groups)} lines, {n_parts} fitted parts; without LCSC: {miss}')
    print('   ', full); print('   ', jlc)
