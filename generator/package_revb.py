"""Collects the Rev B deliverables into /home/claude/robot/deliver/NOVA_RevB (and zips the KiCad projects)."""
import os, shutil, zipfile, glob

ROOT = '/home/claude/robot'
OUT = f'{ROOT}/deliver/NOVA_RevB'

def zipdir(src, dst, arc_root, skip=('fabrication',)):
    with zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED) as z:
        for d, dirs, files in os.walk(src):
            dirs[:] = [x for x in dirs if x not in skip and not x.startswith('.') and x != '__pycache__']
            for f in files:
                if f.endswith(('-bak', '.lck')) or f.startswith('~'):
                    continue
                p = os.path.join(d, f)
                z.write(p, os.path.join(arc_root, os.path.relpath(p, src)))

def main():
    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT)
    # 1) KiCad projects (schematics, boards, project library) — one zip
    kz = f'{OUT}/NOVA_RevB_KiCad10.zip'
    with zipfile.ZipFile(kz, 'w', zipfile.ZIP_DEFLATED) as z:
        for name in ('nova-main', 'nova-head', 'nova-dock'):
            src = f'{ROOT}/kicad/{name}'
            for d, dirs, files in os.walk(src):
                dirs[:] = [x for x in dirs if x != 'fabrication']
                for f in files:
                    if f.endswith(('.kicad_pro', '.kicad_sch', '.kicad_pcb', '.kicad_prl', 'fp-lib-table', 'sym-lib-table', '.kicad_dru')):
                        p = os.path.join(d, f); z.write(p, os.path.join('NOVA_RevB_KiCad10', name, os.path.relpath(p, src)))
        for d, dirs, files in os.walk(f'{ROOT}/kicad/lib'):
            for f in files:
                p = os.path.join(d, f); z.write(p, os.path.join('NOVA_RevB_KiCad10', 'lib', os.path.relpath(p, f'{ROOT}/kicad/lib')))
    # 2) fabrication per board
    for name, label in (('nova-main', 'Main_board'), ('nova-head', 'Head_board'), ('nova-dock', 'Dock_board')):
        src = f'{ROOT}/kicad/{name}/fabrication'
        dst = f'{OUT}/{label}'
        os.makedirs(dst)
        for f in sorted(os.listdir(src)):
            p = os.path.join(src, f)
            if os.path.isfile(p) and not f.endswith('.xml'):
                shutil.copy2(p, dst)
    # 3) mechanics
    m = f'{OUT}/Mechanics_3D'; os.makedirs(f'{m}/printed_parts')
    for f in glob.glob(f'{ROOT}/mech/out/*.png') + glob.glob(f'{ROOT}/mech/out/*.glb'):
        if os.path.basename(f).startswith('NOVA_RevB'):
            shutil.copy2(f, m)
    with zipfile.ZipFile(f'{m}/NOVA_RevB_assembly_step.zip', 'w', zipfile.ZIP_DEFLATED) as z:
        for f in glob.glob(f'{ROOT}/mech/out/NOVA_RevB_*.step'):
            z.write(f, os.path.basename(f))
    for f in glob.glob(f'{ROOT}/mech/out/parts/*'):
        shutil.copy2(f, f'{m}/printed_parts')
    # 4) documentation
    for f in ('NOVA_RevB_design.md', 'NOVA_RevB_design.pdf', 'verification.json'):
        if os.path.exists(f'{ROOT}/docs/{f}'):
            shutil.copy2(f'{ROOT}/docs/{f}', OUT)
    # 4b) simulations: report, plots, scripts, netlists and results
    s = f'{OUT}/Simulations'; os.makedirs(f'{s}/plots')
    for f in ('NOVA_RevB_simulations.md', 'NOVA_RevB_simulations.pdf'):
        if os.path.exists(f'{ROOT}/docs/{f}'):
            shutil.copy2(f'{ROOT}/docs/{f}', s)
    for f in glob.glob(f'{ROOT}/sim/out/*.png'):
        shutil.copy2(f, f'{s}/plots')
    for f in glob.glob(f'{ROOT}/sim/out/*.json'):
        shutil.copy2(f, s)
    with zipfile.ZipFile(f'{s}/NOVA_RevB_sim_sources.zip', 'w', zipfile.ZIP_DEFLATED) as z:
        for f in glob.glob(f'{ROOT}/sim/*.py') + glob.glob(f'{ROOT}/sim/spice/*.cir'):
            z.write(f, os.path.join('sim', os.path.relpath(f, f'{ROOT}/sim')))
    # 5) generator sources (scripts) for reproducibility
    zipdir(f'{ROOT}/gen', f'{OUT}/NOVA_RevB_generator_scripts.zip', 'generator')
    with zipfile.ZipFile(f'{OUT}/NOVA_RevB_generator_scripts.zip', 'a', zipfile.ZIP_DEFLATED) as z:
        for f in glob.glob(f'{ROOT}/mech/*.py') + glob.glob(f'{ROOT}/gen3d/*.py'):
            z.write(f, os.path.join('mech' if '/mech/' in f else 'gen3d', os.path.basename(f)))
    for d, dirs, files in os.walk(OUT):
        for f in files:
            print(os.path.relpath(os.path.join(d, f), OUT), os.path.getsize(os.path.join(d, f)))

if __name__ == '__main__':
    main()
