"""Exports the schematic PDFs into kicad/docs/: one per board plus all simulation schematics merged into one file."""
import os, glob, subprocess, tempfile
from pypdf import PdfWriter

CLI = '/opt/kicad10/bin/kicad-cli'
BASE = os.environ.get('ROBOT_OUT', '/home/claude/robot/kicad')
DOCS = os.path.join(BASE, 'docs')


def sch_pdf(sch, out):
    r = subprocess.run([CLI, 'sch', 'export', 'pdf', '-o', out, sch], capture_output=True, text=True)
    assert r.returncode == 0 and os.path.exists(out), r.stderr
    return out


def main():
    os.makedirs(DOCS, exist_ok=True)
    for name in ('nova-main', 'nova-head'):
        print(sch_pdf(f'{BASE}/{name}/{name}.kicad_sch', f'{DOCS}/{name}_schematic.pdf'))
    w = PdfWriter()
    with tempfile.TemporaryDirectory() as td:
        for sch in sorted(glob.glob(f'{BASE}/sim/*/*.kicad_sch')):
            p = sch_pdf(sch, os.path.join(td, os.path.basename(sch) + '.pdf'))
            w.append(p)
        out = f'{DOCS}/simulation_schematics.pdf'
        with open(out, 'wb') as f:
            w.write(f)
    print(out)


if __name__ == '__main__':
    main()
