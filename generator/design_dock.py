import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from sch import Sheet, Project, add_junctions
from sexpr import fmt
import design_main, s_dock

def build(date=design_main.DATE):
    lib = design_main.library()
    prj = Project('nova-dock', lib, date, design_main.REV, design_main.COMPANY)
    sh = Sheet(prj, 'nova-dock.kicad_sch', 'NOVA — Charging dock', 1, path='/' + prj.root_uuid,
               comments=('Charging dock Rev B: 12 V input, protection, pogo pins + break-away robot contact plate',
                         'Robot side: J203 on the main board (BQ25798 VAC2)', 'Schematic generated and verified with KiCad 10.0.7 (ERC)', ''))
    sh.uuid = prj.root_uuid
    s_dock.build(sh)
    add_junctions(sh)
    return prj, sh

def write(prj, sh, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    node = sh.node(prj.lib.lib_symbols_node(sh.lib_ids), [['sheet_instances', ['path', '/', ['page', '1']]]])
    open(os.path.join(out_dir, sh.filename), 'w', encoding='utf-8').write(fmt(node) + '\n')

if __name__ == '__main__':
    prj, sh = build()
    out = sys.argv[1] if len(sys.argv) > 1 else '/home/claude/robot/kicad/nova-dock'
    write(prj, sh, out)
    print('ok', out)
