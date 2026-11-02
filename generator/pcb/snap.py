"""Board snapshots with kicad-cli (per-layer SVG) rasterised with Chromium (Playwright).
Usage: python3 snap.py PCB OUTPUT.png LAYERS [x0 y0 x1 y1 (mm, absolute)] [--mirror] [--px N]"""
import os, sys, subprocess, tempfile, re
CLI = '/opt/kicad10/bin/kicad-cli'
ENV = dict(os.environ, KICAD10_FOOTPRINT_DIR='/opt/kicad10libs/root/usr/share/kicad/footprints',
           KICAD10_3DMODEL_DIR='/usr/share/kicad/3dmodels')

def snap(pcb, out_png, layers, crop=None, mirror=False, px=1600, theme=None):
    tmp = tempfile.mkdtemp()
    svg = os.path.join(tmp, 'b.svg')
    # with a crop: full page (absolute KiCad coordinates); without a crop: board area only
    cmd = [CLI, 'pcb', 'export', 'svg', '--mode-single', '-o', svg, '-l', layers, '--page-size-mode', '0' if crop else '2',
           '--exclude-drawing-sheet', '--drill-shape-opt', '2']
    if mirror: cmd.append('--mirror')
    if theme: cmd += ['--theme', theme]
    r = subprocess.run(cmd + [pcb], capture_output=True, text=True, env=ENV)
    if not os.path.exists(svg):
        raise RuntimeError(r.stdout + r.stderr)
    s = open(svg, encoding='utf-8').read()
    # viewBox in SVG units (mm)
    m = re.search(r'viewBox="([-\d.]+) ([-\d.]+) ([-\d.]+) ([-\d.]+)"', s)
    vx, vy, vw, vh = map(float, m.groups())
    if crop:
        x0, y0, x1, y1 = crop
        if mirror:
            # mirroring flips X around the view centre
            cx = vx + vw / 2
            x0, x1 = 2 * cx - x1, 2 * cx - x0
        s = s.replace(m.group(0), f'viewBox="{x0} {y0} {x1 - x0} {y1 - y0}"', 1)
        vw, vh = x1 - x0, y1 - y0
    s = re.sub(r'width="[^"]*mm" height="[^"]*mm"', f'width="{px}" height="{px * vh / vw:.0f}"', s, count=1)
    open(svg, 'w', encoding='utf-8').write(s)
    html = os.path.join(tmp, 'p.html')
    open(html, 'w').write(f'<html><body style="margin:0;background:#101418"><img src="b.svg" style="display:block;width:{px}px"></body></html>')
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        br = p.chromium.launch()
        pg = br.new_page(viewport={'width': px, 'height': int(px * vh / vw)})
        pg.goto('file://' + html)
        pg.wait_for_timeout(300)
        pg.screenshot(path=out_png, full_page=True)
        br.close()
    return out_png

if __name__ == '__main__':
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    mirror = '--mirror' in sys.argv
    px = 1600
    for x in sys.argv:
        if x.startswith('--px='): px = int(x[5:])
    crop = tuple(map(float, a[3:7])) if len(a) >= 7 else None
    print(snap(a[0], a[1], a[2], crop, mirror, px))
