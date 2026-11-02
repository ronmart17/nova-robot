import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from sch import Sheet, Project, uid, add_junctions
from sexpr import fmt
import design_main, s_head
from helpers import place_part

def build(date=design_main.DATE):
    lib = design_main.library()
    prj = Project('nova-head', lib, date, design_main.REV, design_main.COMPANY)
    sh = Sheet(prj, 'nova-head.kicad_sch', 'NOVA — Head board', 1,
               path='/' + prj.root_uuid, comments=('Head board Rev B: display, ToF, touch and Camera Module 3 mount', 'Connects to J602 on the main board (JST SH 20p, 1:1 cable)', 'Schematic generated and verified with KiCad 10.0.7 (ERC)', ''))
    sh.uuid = prj.root_uuid
    s_head.build(sh)
    for i in range(2):   # M3 angle brackets to the main board (H9/H10 there)
        place_part(sh, 'MH_M3', f'H{i+101}', 30.48 + i * 15.24, 40.64, ref_at=(2.54, -1.27, 'left'), val_at=(2.54, 1.27, 'left'))
    add_junctions(sh)
    return prj, sh

def write(prj, sh, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    node = sh.node(prj.lib.lib_symbols_node(sh.lib_ids), [['sheet_instances', ['path', '/', ['page', '1']]]])
    open(os.path.join(out_dir, sh.filename), 'w', encoding='utf-8').write(fmt(node) + '\n')

if __name__ == '__main__':
    prj, sh = build()
    out = sys.argv[1] if len(sys.argv) > 1 else '/home/claude/robot/kicad/nova-head'
    write(prj, sh, out)
    print('ok', out)
