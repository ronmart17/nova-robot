"""Simulation plots (PNG) from the ngspice .dat files. Restrained style: 2 px traces,
fine grid, one scale per panel, legend with 2+ series and selective direct labels."""
import os, json, numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

BASE = os.environ.get('ROBOT_OUT', '/home/claude/robot/kicad') + '/sim'
OUT = BASE + '/plots'
SURF, INK, INK2, MUTED, GRID, AXIS = '#fcfcfb', '#0b0b0b', '#52514e', '#898781', '#e1e0d9', '#c3c2b7'
S = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100']      # fixed categorical order
LW = 1.5                                              # ≈ 2 px at 96 dpi

plt.rcParams.update({
    'figure.facecolor': SURF, 'axes.facecolor': SURF, 'savefig.facecolor': SURF,
    'font.family': 'DejaVu Sans', 'font.size': 9, 'axes.titlesize': 10, 'axes.titleweight': 'bold',
    'axes.edgecolor': AXIS, 'axes.labelcolor': INK2, 'xtick.color': MUTED, 'ytick.color': MUTED,
    'xtick.labelcolor': INK2, 'ytick.labelcolor': INK2, 'axes.grid': True, 'grid.color': GRID, 'grid.linewidth': 0.6,
    'axes.spines.top': False, 'axes.spines.right': False, 'legend.frameon': False, 'legend.fontsize': 8.5,
    'lines.solid_capstyle': 'round', 'lines.solid_joinstyle': 'round', 'axes.titlelocation': 'left',
    'axes.titlecolor': INK, 'axes.formatter.use_locale': False,
})

def load(name):
    p = f'{BASE}/{name}/results/{name}.dat'
    hdr = open(p).readline().split()
    d = np.loadtxt(p, skiprows=1)
    return {h: d[:, i] for i, h in enumerate(hdr)}

def es(x, nd):
    return f'{x:.{nd}f}'

def comma_axis(ax, nd_x=None, nd_y=None):
    from matplotlib.ticker import FuncFormatter
    if nd_x is not None: ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: es(v, nd_x)))
    if nd_y is not None: ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: es(v, nd_y)))

def note(ax, x, y, s, **kw):
    ax.annotate(s, (x, y), fontsize=8.5, color=INK2, **kw)

def fig1():
    d = load('sim1_vsys_motor_pwm'); t = d['time'] * 1e3
    w = (t >= 5.0) & (t <= 5.5)
    fig, (a, b) = plt.subplots(2, 1, figsize=(7.2, 5.0), sharex=True, gridspec_kw={'hspace': 0.35})
    m = json.load(open(f'{BASE}/meas.json'))['sim1_vsys_motor_pwm']
    a.plot(t[w], d['v(/VSYS)'][w], color=S[0], lw=LW)
    a.set_title(f"VSYS with both motors at PWM 20 kHz / 70 %: ripple {es(m['vsys_pp']*1e3, 0)} mV p-p, mean {es(m['vsys_avg'], 2)} V")
    a.set_ylabel('V'); comma_axis(a, nd_y=2)
    b.plot(t[w], -d['i(v1)'][w], color=S[0], lw=LW, label='Battery')
    b.plot(t[w], d['i(l2)'][w], color=S[1], lw=LW, label='Left motor')
    b.set_title('Currents', pad=20); b.set_ylabel('A'); b.set_xlabel('Time (ms)')
    b.legend(loc='lower left', bbox_to_anchor=(0, 1.0), ncol=2, borderaxespad=0.2); comma_axis(b, nd_x=1, nd_y=1)
    b.set_ylim(bottom=0)
    fig.savefig(f'{OUT}/sim1_vsys_pwm.png', dpi=160, bbox_inches='tight'); plt.close(fig)

def fig2():
    fig, ax = plt.subplots(2, 2, figsize=(8.4, 5.2), sharex=True, gridspec_kw={'hspace': 0.38, 'wspace': 0.28})
    for j, (name, title) in enumerate((('sim2a_buck_3v3', 'Buck 3.3 V · 1 A'), ('sim2b_buck_5v', 'Buck 5 V · 1.4 A'))):
        d = load(name); t = d['time']; t0 = t[-1] - 2.5e-6
        w = t >= t0; tu = (t[w] - t0) * 1e6
        vo = d['v(/VOUT)']; m = vo[t >= 0.95e-3].mean()
        ax[0, j].plot(tu, (vo[w] - m) * 1e3, color=S[0], lw=LW)
        mm = json.load(open(f'{BASE}/meas.json'))[name]
        ax[0, j].set_title(f"{title}: VOUT ripple {es(mm['vout_pp']*1e3, 1)} mV p-p")
        ax[0, j].set_ylabel(f"mV relative to {es(mm['vout_avg'], 3)} V")
        il = d['i(l1)']
        ax[1, j].plot(tu, il[w], color=S[1], lw=LW)
        ax[1, j].set_title(f"3.3 µH inductor: {es(mm['il_pp'], 2)} A p-p, peak {es(mm['il_max'], 2)} A"); ax[1, j].set_ylabel('A')
        ax[1, j].set_xlabel('Time (µs)')
        comma_axis(ax[0, j], nd_y=1); comma_axis(ax[1, j], nd_x=1, nd_y=2)
    fig.savefig(f'{OUT}/sim2_buck.png', dpi=160, bbox_inches='tight'); plt.close(fig)

def fig3():
    d = load('sim3_power_up'); t = d['time'] * 1e3
    fig, a = plt.subplots(figsize=(7.2, 4.0))
    ser = [('v(/3V3)', '3V3'), ('v(/EN_ESP)', 'ESP32-S3 EN'), ('v(/PWR_EN)', 'PWR_EN'), ('v(/SS)', 'SS (up to 1 V)')]
    for k, (v, lab) in enumerate(ser):
        y = d[v] if v != 'v(/SS)' else np.where(d[v] <= 1.0, d[v], np.nan)
        a.plot(t, y, color=S[k], lw=LW, label=lab)
    for y, lab in ((2.475, '0.75·VDD = 2.475 V'), (1.21, 'EN threshold 1.21 V')):
        a.axhline(y, color=MUTED, lw=0.8)
        a.annotate(lab, (29.5, y), xytext=(0, 3), textcoords='offset points', ha='right', fontsize=8, color=INK2)
    m = json.load(open(f'{BASE}/meas.json'))['sim3_power_up']
    a.plot([m['t_esp'] * 1e3], [2.475], 'o', ms=6, color=S[1], mec=SURF, mew=1.5)
    a.annotate(f"EN at {es(m['t_esp']*1e3, 1)} ms", (m['t_esp'] * 1e3, 2.475), xytext=(6, -14), textcoords='offset points', fontsize=8.5, color=INK2)
    a.set_title('Power-up: SW301 to ON at t = 1 ms', pad=22); a.set_xlabel('Time (ms)'); a.set_ylabel('V')
    a.set_xlim(0, 30); a.set_ylim(0, 3.6); a.legend(loc='lower left', bbox_to_anchor=(0, 1.0), ncol=4, borderaxespad=0.2)
    comma_axis(a, nd_y=1)
    fig.savefig(f'{OUT}/sim3_power_up.png', dpi=160, bbox_inches='tight'); plt.close(fig)

def fig4():
    d = load('sim4_cliff_sensor'); t = d['time'] * 1e3
    fig, (a, b) = plt.subplots(2, 1, figsize=(7.2, 5.0), sharex=True, gridspec_kw={'hspace': 0.35, 'height_ratios': [1, 1.6]})
    a.plot(t, d['v(/ILED)'] * 1e3, color=S[0], lw=LW)
    a.set_title('IR LED current (300 µs pulse)'); a.set_ylabel('mA')
    b.plot(t, d['v(/ADC_TABLE)'], color=S[0], lw=LW, label='Over the table (CTR 5 %)')
    b.plot(t, d['v(/ADC_CLIFF)'], color=S[1], lw=LW, label='Over the cliff (CTR 0.05 %)')
    b.axvline(0.35, color=MUTED, lw=0.8)
    b.annotate('sampling at 350 µs', (0.35, 1.5), xytext=(4, 0), textcoords='offset points', fontsize=8, color=INK2)
    b.set_title('ADC input voltage', pad=20); b.set_ylabel('V'); b.set_xlabel('Time (ms)')
    b.set_ylim(0, 3.3); b.legend(loc='lower left', bbox_to_anchor=(0, 1.0), ncol=2, borderaxespad=0.2)
    comma_axis(a, nd_y=0); comma_axis(b, nd_x=1, nd_y=1)
    fig.savefig(f'{OUT}/sim4_cliff_sensor.png', dpi=160, bbox_inches='tight'); plt.close(fig)

def fig5():
    d = load('sim5_hot_plug'); t = d['time'] * 1e6
    m = json.load(open(f'{BASE}/meas.json'))['sim5_hot_plug']
    fig, a = plt.subplots(figsize=(7.2, 4.0))
    for k, (v, lab, key) in enumerate((('v(/VIN_NOPROT)', 'No protection', 'peak_noprot'), ('v(/VIN_TVS)', 'TVS SMF5.0A only', 'peak_tvs'),
                                      ('v(/VIN_RC)', 'TVS + RC 1 Ω / 10 µF (design)', 'peak_rc'))):
        a.plot(t, d[v], color=S[k], lw=LW, label=f"{lab}: peak {es(m[key], 2)} V")
    for y, lab in ((6.0, 'LM66200 VIN abs. max. = 6 V'), (5.5, 'VIN max. operating = 5.5 V')):
        a.axhline(y, color=MUTED, lw=0.8)
        a.annotate(lab, (59, y), xytext=(0, 3), textcoords='offset points', ha='right', fontsize=8, color=INK2)
    a.set_title('Hot plug, 1 m USB-C cable (1 µH)', pad=36); a.set_xlabel('Time (µs)'); a.set_ylabel('V')
    a.set_xlim(5, 60); a.set_ylim(0, 10)
    a.legend(loc='lower left', bbox_to_anchor=(0, 1.0), ncol=2, borderaxespad=0.2)
    comma_axis(a, nd_y=0)
    fig.savefig(f'{OUT}/sim5_hot_plug.png', dpi=160, bbox_inches='tight'); plt.close(fig)

if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    for f in (fig1, fig2, fig3, fig4, fig5): f()
    print(sorted(os.listdir(OUT)))
