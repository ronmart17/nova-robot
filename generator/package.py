"""Packs the deliverables into a ZIP: KiCad projects (schematics and PCB), library, simulations, fabrication
(Gerber/BOM/CPL/PDF/STEP/3D views), documentation and generator scripts."""
import os, zipfile, glob
BASE = '/home/claude/robot/kicad'
OUT = '/home/claude/robot/entrega/NOVA_KiCad10_RevA.zip'
ROOT = 'NOVA_RevA'
SKIP_DIRS = {'__pycache__', 'gerbers'}          # the Gerbers go inside <board>_gerbers_JLCPCB.zip
SKIP_EXT = {'.bak', '.lck', '.kicad_prl'}
os.makedirs(os.path.dirname(OUT), exist_ok=True)
n = 0
with zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED) as z:
    for root, dirs, files in os.walk(BASE):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.endswith('-backups')]
        for f in files:
            if os.path.splitext(f)[1] in SKIP_EXT or f.startswith('~') or f.startswith('_autosave') or f == 'fp-info-cache':
                continue
            p = os.path.join(root, f)
            z.write(p, os.path.join(ROOT, os.path.relpath(p, BASE))); n += 1
    for p in sorted(glob.glob('/home/claude/robot/entrega/*.md')):
        z.write(p, os.path.join(ROOT, os.path.basename(p))); n += 1
    for pat, sub in (('/home/claude/robot/gen/*.py', 'gen'), ('/home/claude/robot/gen/pcb/*.py', 'pcb'),
                     ('/home/claude/robot/gen3d/*.py', 'gen3d')):
        for p in sorted(glob.glob(pat)):
            if os.path.basename(p).endswith('_v1.py'): continue
            z.write(p, os.path.join(ROOT, 'generator', sub, os.path.basename(p))); n += 1
print(OUT, n, 'files', round(os.path.getsize(OUT) / 1e6, 2), 'MB')
