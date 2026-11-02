"""Generate PNG views (full and zoomed) of the current placement."""
import sys, os
import main_pcb as M
import preview
SCR = M.SCR
def views(b, segs_extra=None, names=None, rats=True, prefix='v', keep=None):
    _, segs = M.outline_segs_cache
    def deco(ax):
        from matplotlib.patches import Polygon as MP
        for name, kp, sides, ex in (keep or []):
            for g in getattr(kp, 'geoms', [kp]):
                col = '#2a9d2a' if 'pack' in name else ('#d1491f' if sides == 'B' else ('#7a3db8' if 'head' in name else '#888888'))
                ax.add_patch(MP(list(g.exterior.coords), closed=True, fill=False, ec=col, lw=0.6, ls=':'))
    V = {
        'full': None,
        'rear_c': M.A(-22, 5)[0:2] + M.A(22, 45)[0:2],
        'rear_r': M.A(14, 8)[0:2] + M.A(52, 46)[0:2],
        'usb': M.A(-10, 36)[0:2] + M.A(30, 61)[0:2],
        'esp': M.A(-50, 5)[0:2] + M.A(-10, 45)[0:2],
        'front': M.A(-42, -60)[0:2] + M.A(42, -26)[0:2],
    }
    out = []
    for k, v in V.items():
        if names and k not in names: continue
        p = os.path.join(SCR, f'{prefix}_{k}.png')
        preview.draw(b, p, segs, extra=[deco], view=v, nets=(v is not None), rats=rats, title=f'nova-main — {k}', size=13 if v is None else 12,
                     dpi=110 if v is None else 120)
        out.append(p)
    return out
if __name__ == '__main__':
    b, usable, keep, issues = M.build(None, check=False)
    print('\n'.join(views(b, names=sys.argv[1:] or None, keep=keep)))
