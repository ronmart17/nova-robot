"""Top view of the robot layout (robot frame) with all the mechanical items: quick check of fits and clearances."""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, FancyBboxPatch, Polygon
from dims import *

def rr(ax, cx, cy, w, h, r, **kw):
    ax.add_patch(FancyBboxPatch((cx - w / 2 + r, cy - h / 2 + r), w - 2 * r, h - 2 * r, boxstyle=f'round,pad={r}', **kw))

def rect(ax, x0, y0, x1, y1, **kw):
    ax.add_patch(Rectangle((min(x0, x1), min(y0, y1)), abs(x1 - x0), abs(y1 - y0), **kw))

def draw(path, extra=None):
    fig, ax = plt.subplots(figsize=(11, 11))
    rr(ax, 0, 0, SHELL_W, SHELL_D, SHELL_R, fill=False, ec='#999999', lw=1.2, ls='--')
    ax.text(0, SHELL_D / 2 + 2, 'shell 140 × 140', ha='center', color='#888', fontsize=8)
    rr(ax, 0, 0, MB_W, MB_D, MB_R, fill=True, fc='#dfeedd', ec='#2d6a2d', lw=1.5)
    for s in (-1, 1):
        rect(ax, s * WCUT_X, -WCUT_Y, s * (MB_W / 2 + 1), WCUT_Y, fc='white', ec='#2d6a2d', lw=1.2)
        rect(ax, s * (WHEEL_X - WHEEL_W / 2), -WHEEL_D / 2, s * (WHEEL_X + WHEEL_W / 2), WHEEL_D / 2, fc='#333333', alpha=0.6)
        rect(ax, s * MOTOR_X[0], -MOTOR_W / 2, s * MOTOR_X[1], MOTOR_W / 2, fc='none', ec='#c0392b', ls=':', lw=1.2)
        for bx in BRK_X:
            rect(ax, s * (bx - 5.75), -12.8, s * (bx + 5.75), 12.8, fc='none', ec='#c0392b', ls=':', lw=0.6)
    ax.text(-30, -2, 'N20 (bottom)', color='#c0392b', fontsize=7, ha='center')
    ax.add_patch(Circle((0, CASTER_Y), 8, fc='none', ec='#c0392b', ls=':'))
    ax.text(0, CASTER_Y - 11, 'caster (bottom)', color='#c0392b', fontsize=7, ha='center')
    for x, y in CLIFF:
        rect(ax, x - 2.2, y - 1.2, x + 2.2, y + 1.2, fc='#c0392b')
    ax.text(0, CLIFF[0][1] + 3, 'cliff ToF ×2 (bottom)', color='#c0392b', fontsize=7, ha='center')
    rect(ax, -BAT_X, BAT_Y0, BAT_X, BAT_Y1, fc='#3b6fb6', alpha=0.35, ec='#3b6fb6')
    ax.text(0, (BAT_Y0 + BAT_Y1) / 2, '2S2P 18650\n(on the board)', ha='center', va='center', color='#1d4f91', fontsize=9)
    # Pi
    (x0, y0), (x1, y1) = pi_xy(0, 0), pi_xy(PI_W, PI_D)
    rect(ax, x0, y0, x1, y1, fc='none', ec='#0b6623', lw=2)
    (ux0, uy0), (ux1, uy1) = pi_xy(66, 2), pi_xy(87, 54)
    rect(ax, ux0, uy0, ux1, uy1, fc='#aaaaaa', alpha=0.4)
    ax.text((ux0 + ux1) / 2, (uy0 + uy1) / 2, 'USB/RJ45', ha='center', va='center', fontsize=7)
    (hx0, hy0), (hx1, hy1) = pi_xy(7.1, 49.9), pi_xy(57.9, 55.1)
    rect(ax, hx0, hy0, hx1, hy1, fc='#222222', alpha=0.6)
    p1 = pi_xy(*PI_PIN1_UV)
    ax.plot(*p1, 'o', color='yellow', ms=4)
    ax.text(p1[0] - 2, p1[1] + 3, 'pin 1', fontsize=7)
    uc = pi_xy(PI_USBC_U, 0)
    rect(ax, uc[0] - 3, uc[1] - 4.5, uc[0] + 1.5, uc[1] + 4.5, fc='#aaaaaa')
    ax.text(uc[0] + 2, uc[1], 'USB-C', fontsize=7, va='center')
    for u, v in PI_HOLES_UV:
        ax.add_patch(Circle(pi_xy(u, v), 2.6, fc='#c9a227'))
    ax.text(PI_CX, PI_CY + 30, 'Raspberry Pi 5 (z = 71)', ha='center', color='#0b6623', fontsize=9)
    ax.add_patch(Circle((0, PI_CY), XVF_D / 2, fc='none', ec='#555555', ls='-.'))
    ax.text(0, PI_CY - XVF_D / 2 + 3, 'XVF3800 Ø100 (top)', ha='center', fontsize=8, color='#555')
    rect(ax, -HEAD_W / 2, HEAD_Y0, HEAD_W / 2, HEAD_Y0 + HEAD_T, fc='#6c3483')
    ax.text(0, HEAD_Y0 + 5, 'head board (face)', ha='center', color='#6c3483', fontsize=8)
    ax.add_patch(Circle(SPEAKER[:2], 3, fc='#555'))
    ax.text(SPEAKER[0], SPEAKER[1] + 3, 'speaker (rear wall)', ha='center', fontsize=7)
    for X, Y in SHELL_HOLES:
        ax.add_patch(Circle((X, Y), 1.6, fc='white', ec='k'))
    for X, Y in HEAD_BRK:
        ax.add_patch(Circle((X, Y), 1.6, fc='white', ec='#6c3483'))
    if extra:
        extra(ax)
    ax.set_aspect('equal'); ax.set_xlim(-75, 75); ax.set_ylim(-75, 75)
    ax.grid(True, lw=0.3, alpha=0.5)
    ax.set_xlabel('X (mm) → right'); ax.set_ylabel('Y (mm) → front')
    ax.set_title('NOVA Rev B — layout, top view (robot frame)')
    fig.tight_layout(); fig.savefig(path, dpi=110); plt.close(fig)

if __name__ == '__main__':
    draw(sys.argv[1] if len(sys.argv) > 1 else '/home/claude/robot/mech/out/layout_top.png')
