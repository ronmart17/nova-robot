"""Fabrication and documentation outputs for both boards (KiCad 10, kicad-cli):
Gerber + drill (JLCPCB), CPL (positions), assembly and 1:1 mechanical drawings as PDF, STEP and 3D views."""
import os, sys, csv, glob, shutil, subprocess, zipfile, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from export import CLI, CLIENV

BOARDS = {
    'nova-main': dict(dir='/home/claude/robot/kicad/nova-main', layers=4),
    'nova-head': dict(dir='/home/claude/robot/kicad/nova-head', layers=2),
    'nova-dock': dict(dir='/home/claude/robot/kicad/nova-dock', layers=2),
}

def run(cmd, check=True):
    r = subprocess.run(cmd, capture_output=True, text=True, env=CLIENV, timeout=1800)
    if check and r.returncode != 0:
        raise RuntimeError(' '.join(cmd) + '\n' + r.stdout[-2000:] + r.stderr[-2000:])
    return r

def gerbers(name, pcb, out, nlayers):
    g = os.path.join(out, 'gerbers')
    shutil.rmtree(g, ignore_errors=True); os.makedirs(g)
    cu = 'F.Cu,In1.Cu,In2.Cu,B.Cu' if nlayers == 4 else 'F.Cu,B.Cu'
    layers = cu + ',F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts'
    run([CLI, 'pcb', 'export', 'gerbers', '-o', g + '/', '-l', layers, '--no-x2', '--no-netlist',
         '--subtract-soldermask', pcb])
    run([CLI, 'pcb', 'export', 'drill', '-o', g + '/', '--format', 'excellon', '--drill-origin', 'absolute',
         '--excellon-units', 'mm', '--excellon-zeros-format', 'decimal', '--excellon-oval-format', 'alternate',
         '--excellon-separate-th', '--generate-map', '--map-format', 'gerberx2', pcb])
    z = os.path.join(out, f'{name}_gerbers_JLCPCB.zip')
    with zipfile.ZipFile(z, 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(os.listdir(g)):
            zf.write(os.path.join(g, f), f)
    return z, sorted(os.listdir(g))

def cpl(name, pcb, out):
    """JLCPCB CPL: Designator, Mid X, Mid Y, Layer, Rotation (no DNP; no parts excluded from the BOM)."""
    raw = os.path.join(out, f'{name}_pos_kicad.csv')
    run([CLI, 'pcb', 'export', 'pos', '-o', raw, '--side', 'both', '--format', 'csv', '--units', 'mm',
         '--exclude-dnp', pcb])
    bom = os.path.join(out, f'{name}_BOM_JLCPCB.csv')
    refs = set()
    if os.path.exists(bom):
        for row in csv.DictReader(open(bom, encoding='utf-8')):
            for r in row['Designator'].replace(' ', '').split(','):
                if r: refs.add(r)
    dst = os.path.join(out, f'{name}_CPL_JLCPCB.csv')
    n = 0
    with open(raw, encoding='utf-8') as f, open(dst, 'w', newline='', encoding='utf-8') as g:
        w = csv.writer(g); w.writerow(['Designator', 'Mid X', 'Mid Y', 'Layer', 'Rotation'])
        for row in csv.DictReader(f):
            ref = row['Ref']
            if refs and ref not in refs: continue
            side = 'Top' if row['Side'].lower().startswith('top') else 'Bottom'
            w.writerow([ref, f"{float(row['PosX']):.4f}mm", f"{float(row['PosY']):.4f}mm", side,
                        f"{float(row['Rot']):.1f}"])
            n += 1
    os.remove(raw)
    return dst, n

def pdfs(name, pcb, out):
    res = []
    for side, lay, mirror in (('top', 'F.Fab,Edge.Cuts', False), ('bottom', 'B.Fab,Edge.Cuts', True)):
        p = os.path.join(out, f'{name}_assembly_{side}.pdf')
        cmd = [CLI, 'pcb', 'export', 'pdf', '--mode-single', '-o', p, '-l', lay, '--include-border-title',
               '--black-and-white', '--crossout-DNP-footprints-on-fab-layers', '--sketch-pads-on-fab-layers',
               '--drill-shape-opt', '1']
        if mirror: cmd.append('--mirror')
        run(cmd + [pcb]); res.append(p)
    p = os.path.join(out, f'{name}_mechanical_1to1.pdf')
    run([CLI, 'pcb', 'export', 'pdf', '--mode-single', '-o', p, '-l', 'Edge.Cuts,User.Drawings,F.Fab',
         '--include-border-title', '--black-and-white', '--scale', '1', '--drill-shape-opt', '2', pcb])
    res.append(p)
    p = os.path.join(out, f'{name}_copper_layers.pdf')
    run([CLI, 'pcb', 'export', 'pdf', '--mode-multipage', '-o', p, '-l',
         ('F.Cu,In1.Cu,In2.Cu,B.Cu' if 'main' in name else 'F.Cu,B.Cu'), '--cl', 'Edge.Cuts',
         '--include-border-title', pcb])
    res.append(p)
    return res

def step(name, pcb, out):
    p = os.path.join(out, f'{name}.step')
    run([CLI, 'pcb', 'export', 'step', '-f', '-o', p, '--subst-models', '--no-dnp', pcb])
    return p

def renders(name, pcb, out):
    res = []
    for side, extra in (('top', []), ('bottom', []), ('iso', ['--rotate', '-35,0,30', '--perspective', '--zoom', '0.9'])):
        p = os.path.join(out, f'{name}_3d_{side}.png')
        cmd = [CLI, 'pcb', 'render', '-o', p, '--width', '1800', '--height', '1400', '--quality', 'high',
               '--background', 'opaque']
        cmd += ['--side', 'top' if side == 'iso' else side] + extra
        r = run(cmd + [pcb], check=False)
        if os.path.exists(p): res.append(p)
        else: print('render', side, 'failed:', r.stderr[-400:])
    return res

def all_outputs(names=('nova-main', 'nova-head'), do_step=True, do_render=True):
    rep = {}
    for name in names:
        d = BOARDS[name]['dir']; pcb = os.path.join(d, f'{name}.kicad_pcb'); out = os.path.join(d, 'fabrication')
        os.makedirs(out, exist_ok=True)
        z, files = gerbers(name, pcb, out, BOARDS[name]['layers'])
        c, n = cpl(name, pcb, out)
        p = pdfs(name, pcb, out)
        s = step(name, pcb, out) if do_step else None
        r = renders(name, pcb, out) if do_render else []
        rep[name] = dict(zip=z, gerbers=files, cpl=c, cpl_rows=n, pdf=p, step=s, renders=r)
        print(name, json.dumps({k: (v if not isinstance(v, list) else len(v)) for k, v in rep[name].items()}, ensure_ascii=False))
    return rep

if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    all_outputs(tuple(args) or ('nova-main', 'nova-head', 'nova-dock'), do_step='--no-step' not in sys.argv,
                do_render='--no-render' not in sys.argv)
