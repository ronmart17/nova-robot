"""Preview (PNG): outline, zones, real courtyards, pads (with net names in zoomed views), tracks, vias and ratsnest."""
import math, re
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MPoly, Circle
import geom

def short(net):
    if not net: return ''
    n = net.split('/')[-1]
    n = re.sub(r'^Net-\((.*)\)$', r'\1', n)
    return n.replace('unconnected-', 'nc')

def ratsnest(board, skip=('GND',)):
    """Minimum spanning tree edges per net between pad centres (copper pads only)."""
    pts = {}
    for ref, pl in board.placed.items():
        for ps in geom.pad_shapes(pl):
            n = ps['net']
            if not n or n.startswith('unconnected') or n in skip: continue
            pts.setdefault(n, []).append(ps['center'])
    edges = []
    for n, P in pts.items():
        if len(P) < 2: continue
        inside = [0]; rest = list(range(1, len(P)))
        while rest:
            best = None
            for i in inside:
                for j in rest:
                    d = (P[i][0] - P[j][0]) ** 2 + (P[i][1] - P[j][1]) ** 2
                    if best is None or d < best[0]: best = (d, i, j)
            _, i, j = best
            edges.append((n, P[i], P[j])); inside.append(j); rest.remove(j)
    return edges

def draw(board, path, outline_segments, extra=None, view=None, labels=True, title='', side='both', dpi=110,
         tracks=True, nets=False, rats=False, rat_skip=('GND',), size=13):
    fig, ax = plt.subplots(figsize=(size, size))
    ax.set_aspect('equal')
    if view is None: view = (150 - 62, 100 - 62, 150 + 62, 100 + 62)
    x0, y0, x1, y1 = view
    ax.set_xlim(x0, x1); ax.set_ylim(y1, y0)
    zoom = 124.0 / max(x1 - x0, y1 - y0)
    for kind, data in outline_segments:
        if kind == 'line':
            (a, b) = data; ax.plot([a[0], b[0]], [a[1], b[1]], color='#c8a200', lw=1.2)
        elif kind == 'poly':
            ax.add_patch(MPoly(data, closed=True, fill=False, ec='#c8a200', lw=1.2))
    if extra:
        for e in extra: e(ax)
    if tracks:
        cols = {'F.Cu': '#c83434', 'B.Cu': '#3a5fcd', 'In1.Cu': '#c2a33a', 'In2.Cu': '#2f9e5b'}
        for (net, a, b, w, layer) in board.segments:
            ax.plot([a[0], b[0]], [a[1], b[1]], color=cols.get(layer, 'k'), lw=max(0.3, w * 2.9 * zoom), alpha=0.7,
                    solid_capstyle='round')
        for (net, p, size_, drill) in board.vias:
            ax.add_patch(Circle(p, size_ / 2, color='#666', alpha=0.9)); ax.add_patch(Circle(p, drill / 2, color='w'))
    for ref, pl in board.placed.items():
        if side != 'both' and pl.side != side: continue
        cy = geom.courtyard(pl)
        col = '#1f6fd1' if pl.side == 'F' else '#d1491f'
        for g in getattr(cy, 'geoms', [cy]):
            ax.add_patch(MPoly(list(g.exterior.coords), closed=True, fill=True, fc=col, alpha=0.06, ec=col, lw=0.5,
                               ls='-' if pl.side == 'F' else '--'))
        for ps in geom.pad_shapes(pl):
            g = ps['poly']
            pc = '#b33' if 'F.Cu' in ps['layers'] else '#36b'
            if ps['kind'] in ('thru_hole',): pc = '#a07000'
            if ps['kind'].startswith('np'): pc = '#555'
            ax.add_patch(MPoly(list(g.exterior.coords), closed=True, fc=pc, ec='none', alpha=0.6))
            if nets and ps['net'] and zoom > 2.5:
                c = ps['center']
                if x0 <= c[0] <= x1 and y0 <= c[1] <= y1:
                    ax.text(c[0], c[1], short(ps['net'])[:12], fontsize=max(2.6, 1.1 * zoom ** 0.75), ha='center', va='center',
                            color='k', alpha=0.9, clip_on=True)
        if labels:
            b = cy.bounds
            if b[2] < x0 or b[0] > x1 or b[3] < y0 or b[1] > y1: continue
            ax.text((b[0] + b[2]) / 2, (b[1] + b[3]) / 2 if zoom <= 3 else b[1] - 0.3, ref,
                    fontsize=min(7, 3.6 * zoom ** 0.5), ha='center', va='center' if zoom <= 3 else 'bottom',
                    color='#102040' if pl.side == 'F' else '#702010', clip_on=True)
    if rats:
        rl = rats if isinstance(rats, list) else ratsnest(board, rat_skip)
        for (n, a, b) in rl:
            ax.plot([a[0], b[0]], [a[1], b[1]], color='#00a0a0', lw=0.5 if isinstance(rats, list) else 0.35, alpha=0.8)
    ax.set_title(title, fontsize=11)
    ax.grid(True, lw=0.2, alpha=0.4)
    fig.savefig(path, dpi=dpi, bbox_inches='tight'); plt.close(fig)
