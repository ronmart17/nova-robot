import subprocess, os, re, sys, numpy as np
CLI = os.environ.get('KICAD_CLI', '/opt/kicad10/bin/kicad-cli')

def export_spice(sch, out_cir):
    r = subprocess.run([CLI, 'sch', 'export', 'netlist', '--format', 'spice', '-o', out_cir, sch], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stdout + r.stderr)
    return open(out_cir).read()

def node(netlist, name):
    """find the exact node token used for a label name"""
    toks = set(re.findall(r'[^\s()]+', netlist))
    for cand in (name, '/' + name, name.upper(), '/' + name.upper()):
        if cand in toks: return cand
    raise KeyError(name)

def run(cir_text, tran, vectors, workdir, tag):
    os.makedirs(workdir, exist_ok=True)
    body = []
    for line in cir_text.splitlines():
        l = line.strip().lower()
        if l.startswith('.tran') or l.startswith('.end') and not l.startswith('.ends') or l.startswith('.control') or l.startswith('.endc'):
            continue
        body.append(line)
    out = os.path.join(workdir, tag + '.dat')
    vec = ' '.join(vectors)
    ctl = ['.control', 'set filetype=ascii', 'set wr_vecnames', 'set wr_singlescale', f'tran {tran}', f'wrdata {out} {vec}', 'quit', '.endc', '.end']
    cir = os.path.join(workdir, tag + '.cir')
    open(cir, 'w').write('\n'.join(body + ctl) + '\n')
    r = subprocess.run(['ngspice', '-b', cir], capture_output=True, text=True, timeout=1200)
    open(os.path.join(workdir, tag + '.log'), 'w').write(r.stdout + r.stderr)
    data = np.loadtxt(out, skiprows=1)
    hdr = open(out).readline().split()
    return hdr, data
