"""Generates the KiCad 10 projects (main, head, dock), runs ERC and compares netlists."""
import os, sys, shutil, tempfile, collections, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import design_main, design_head, design_dock, project_files, verify
from sch import uid

BASE = os.environ.get('ROBOT_OUT', '/home/claude/robot/kicad')

def gen_main():
    out = f'{BASE}/nova-main'
    prj, root, subs = design_main.build()
    design_main.write(prj, root, subs, out)
    sheets = [(prj.root_uuid, 'Root')] + [(uid(prj.name, 'sheetsym', s.filename), s.title) for s in subs]
    project_files.kicad_pro(f'{out}/nova-main.kicad_pro', 'nova-main', sheets, board=True)
    project_files.lib_tables(out)
    return prj, [root] + subs, f'{out}/nova-main.kicad_sch'

def gen_head():
    out = f'{BASE}/nova-head'
    prj, sh = design_head.build()
    design_head.write(prj, sh, out)
    project_files.kicad_pro(f'{out}/nova-head.kicad_pro', 'nova-head', [(prj.root_uuid, 'Root')], board=True)
    project_files.lib_tables(out)
    return prj, [sh], f'{out}/nova-head.kicad_sch'

def gen_dock():
    out = f'{BASE}/nova-dock'
    prj, sh = design_dock.build()
    design_dock.write(prj, sh, out)
    project_files.kicad_pro(f'{out}/nova-dock.kicad_pro', 'nova-dock', [(prj.root_uuid, 'Root')], board=True)
    project_files.lib_tables(out)
    return prj, [sh], f'{out}/nova-dock.kicad_sch'

def gen_sims():
    import design_sims
    res = []
    for f in design_sims.SIMS:
        prj, sh = f()
        out = f'{BASE}/sim/{prj.name}'
        design_sims.write(prj, sh, out)
        project_files.kicad_pro(f'{out}/{prj.name}.kicad_pro', prj.name, [(prj.root_uuid, 'Root')], netclasses=False)
        project_files.lib_tables(out, rel='../../lib')
        res.append((prj, [sh], f'{out}/{prj.name}.kicad_sch'))
    return res

EXCL = [  # intentional violations: (type, patterns that must appear in the items, comment)
    ('pin_to_pin', [r'U601 Pin [123] '], 'LSM6DSOX: SA0/SDx/SCx tied to GND on purpose (address 0x6A, auxiliary I2C unused)'),
    ('pin_to_pin', [r'U402 Pin 6 '], 'TCA9535 P02 spare, tied to GND on purpose (keep it configured as an input)'),
]

def erc_exclusions(sch_dir, erc_json, sheet_paths):
    """Builds ERC exclusions (SCH_MARKER::SerializeToString format) for the intentional violations."""
    import re, glob
    d = json.load(open(erc_json))
    files = {f: open(f, encoding='utf-8').read() for f in glob.glob(os.path.join(sch_dir, '*.kicad_sch'))}
    def path_of(u):
        for f, t in files.items():
            if f'"{u}"' in t: return sheet_paths[os.path.basename(f)]
        return ''
    out = []
    for sh in d['sheets']:
        for v in sh['violations']:
            descs = [i['description'] for i in v['items']]
            for typ, pats, comment in EXCL:
                if v['type'] != typ or not all(any(re.search(p, x) for x in descs) for p in pats):
                    continue
                m = v['items'][0]; a = v['items'][1] if len(v['items']) > 1 else None
                ser = '|'.join([typ, str(round(m['pos']['x'] * 10000)), str(round(m['pos']['y'] * 10000)), m['uuid'],
                                a['uuid'] if a else '00000000-0000-0000-0000-000000000000',
                                sh['uuid_path'], path_of(m['uuid']), path_of(a['uuid']) if a else ''])
                out.append([ser, comment])
                break
    return out

def check(prj, sheets, root_sch, netcheck=True):
    tmp = tempfile.mkdtemp()
    items = verify.erc(root_sch, tmp)
    c = collections.Counter((s, t) for s, t, *_ in items)
    print(f'== {os.path.basename(root_sch)}: ERC', dict(c) if c else 'clean')
    for s, t, path, d, its in items:
        print(f'   [{s}] {t} {path}: {d} :: {its}')
    if netcheck:
        problems, unassigned, nets, comps = verify.compare(prj, sheets, root_sch, tmp)
        print(f'   netlist: {len(nets)} nets, {len(comps)} components, {len(problems)} mismatches, {len(unassigned)} unassigned pins')
        for p in problems[:40]: print('   ', p)
        for p in unassigned[:20]: print('    unassigned', p)
    return items

if __name__ == '__main__':
    what = sys.argv[1:] or ['main', 'head', 'dock']
    if 'main' in what:
        prj, sheets, sch = gen_main()
        tmp = tempfile.mkdtemp(); verify.erc(sch, tmp)
        paths = {sh.filename: sh.path for sh in sheets}
        ex = erc_exclusions(os.path.dirname(sch), os.path.join(tmp, 'erc.json'), paths)
        pro = os.path.splitext(sch)[0] + '.kicad_pro'
        js = json.load(open(pro)); js.setdefault('erc', {})['erc_exclusions'] = ex; json.dump(js, open(pro, 'w'), indent=2)
        print(f'   documented ERC exclusions: {len(ex)}')
        check(prj, sheets, sch)
    if 'head' in what:
        check(*gen_head())
    if 'dock' in what:
        check(*gen_dock())
    if 'sims' in what:
        for prj, sheets, sch in gen_sims():
            check(prj, sheets, sch, netcheck=False)
