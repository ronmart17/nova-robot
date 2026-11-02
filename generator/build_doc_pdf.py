"""Builds docs/NOVA_RevB_design.pdf from the Markdown (pandoc → HTML → wkhtmltopdf) with the key renders."""
import os, subprocess, tempfile
ROOT = '/home/claude/robot'
MD = f'{ROOT}/docs/NOVA_RevB_design.md'
OUT = f'{ROOT}/docs/NOVA_RevB_design.pdf'
M = f'{ROOT}/mech/out'
K = f'{ROOT}/kicad'
imgs = [(f'{M}/NOVA_RevB_hero_front.png', 'NOVA Rev B'), (f'{M}/NOVA_RevB_hero_docked.png', 'On its charging dock'),
        (f'{M}/NOVA_RevB_hero_rear.png', 'Rear: speaker grille, port bay, dock opening'), (f'{M}/NOVA_RevB_explode.png', 'Enclosure exploded'),
        (f'{M}/NOVA_RevB_core.png', 'Without the enclosure'), (f'{K}/nova-main/fabrication/nova-main_3d_top.png', 'Main board (top)'),
        (f'{K}/nova-head/fabrication/nova-head_3d_top.png', 'Head board'), (f'{K}/nova-dock/fabrication/nova-dock_3d_top.png', 'Dock board')]
css = '''body{font-family:"DejaVu Sans",Arial,sans-serif;font-size:10.5pt;line-height:1.45;color:#1d2430;margin:0 6mm}
h1{font-size:22pt;color:#0b1a2e;border-bottom:3px solid #20c2d8;padding-bottom:4px}
h2{font-size:15pt;color:#0b1a2e;margin-top:22px;border-bottom:1px solid #cfd8e3}
h3{font-size:12pt;color:#13385e}
table{border-collapse:collapse;width:100%;font-size:9pt;margin:8px 0}
th,td{border:1px solid #c9d3df;padding:4px 6px;vertical-align:top}
th{background:#eaf3f8}
code{background:#f1f4f8;padding:1px 3px;border-radius:3px;font-size:9pt}
.gal{display:block}
.gal figure{display:inline-block;width:48%;margin:0 1% 10px 0;vertical-align:top}
.gal img{width:100%;border-radius:6px}
.gal figcaption{font-size:8.5pt;color:#556}
'''
gal = '<div class="gal">' + ''.join(f'<figure><img src="file://{p}"><figcaption>{c}</figcaption></figure>'
                                   for p, c in imgs if os.path.exists(p)) + '</div>\n\n'
md = open(MD, encoding='utf-8').read()
i = md.index('\n## 1.')
md = md[:i] + '\n\n' + gal + md[i:]
d = tempfile.mkdtemp()
open(f'{d}/doc.md', 'w', encoding='utf-8').write(md)
open(f'{d}/style.css', 'w').write(css)
subprocess.run(['pandoc', f'{d}/doc.md', '-f', 'gfm', '-t', 'html5', '-s', '--metadata', 'pagetitle=NOVA Rev B',
                '-c', f'{d}/style.css', '-o', f'{d}/doc.html'], check=True)
subprocess.run(['wkhtmltopdf', '--enable-local-file-access', '-q', '--page-size', 'A4', '--margin-top', '14mm',
                '--margin-bottom', '14mm', '--footer-center', 'NOVA Rev B — design, layout and mechanics · [page]/[topage]',
                '--footer-font-size', '7', f'{d}/doc.html', OUT], check=False)
print(OUT, os.path.getsize(OUT) if os.path.exists(OUT) else 'missing')
