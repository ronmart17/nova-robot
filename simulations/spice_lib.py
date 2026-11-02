"""Tiny ngspice batch runner: writes the netlist, runs ngspice -b, reads wrdata output and .meas results."""
import os, re, subprocess
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
SP = os.path.join(HERE, 'spice')

def run(name, netlist, vectors, tran=None):
    """netlist: SPICE text without .control/.end; vectors: names for wrdata. Returns (t, {vec: array}, meas dict)."""
    cir = os.path.join(SP, name + '.cir')
    dat = os.path.join(SP, name + '.dat')
    log = os.path.join(SP, name + '.log')
    ctl = ['.control', 'set noaskquit', 'set wr_singlescale', 'set wr_vecnames', 'run',
           'wrdata ' + dat + ' ' + ' '.join(vectors), '.endc', '.end']
    open(cir, 'w').write(netlist.strip() + '\n' + '\n'.join(ctl) + '\n')
    r = subprocess.run(['ngspice', '-b', '-o', log, cir], capture_output=True, text=True, timeout=1800)
    txt = open(log).read() if os.path.exists(log) else r.stdout + r.stderr
    meas = {}
    for line in txt.splitlines():
        m = re.match(r'^\s*([a-z_0-9]+)\s*=\s*([-+0-9.eE]+)', line)
        if m:
            try: meas[m.group(1)] = float(m.group(2))
            except ValueError: pass
    if not os.path.exists(dat):
        raise RuntimeError(f'{name}: ngspice failed\n' + txt[-3000:])
    a = np.loadtxt(dat, skiprows=1)
    t = a[:, 0]
    data = {v: a[:, k + 1] for k, v in enumerate(vectors)}
    return t, data, meas
