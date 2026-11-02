"""NOVA Rev B — system-level analyses (Python): stability, drive, power budget and runtime, charging, pogo contacts,
battery protector and fuse margins, thermal, docking Monte Carlo, AprilTag range. Every input is listed in the code
with its source (datasheet, CAD, or 'est.' = engineering estimate). Results → out/system_results.json + plots."""
import os, sys, json, math
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from spice_sims import style, save, limit, C, OUT

G = 9.81
RNG = np.random.default_rng(20261029)
MP = json.load(open(os.path.join(OUT, 'mass_props.json')))
M = MP['mass_g'] / 1000.0                          # kg
CG = MP['cg_mm']                                   # (x, y, z) mm, robot frame (origin on the floor under the axle)
WHEEL_R, WHEEL_X, CASTER_Y = 21.5, 59.5, 50.0      # mm (mech/dims.py)
R = {}

# ======================================================================== A. static stability / tipping
def a_stability():
    x, y, z = CG
    caster_frac = y / CASTER_Y
    a_tip = G * y / z                               # forward accel (or braking while reversing) that lifts the caster
    # lateral: distance from the CoG to the wheel–caster line
    px, py = WHEEL_X, 0.0; qx, qy = 0.0, CASTER_Y
    d_lat = abs((qy - py) * (x - px) - (qx - px) * (y - py)) / math.hypot(qx - px, qy - py)
    a_lat = G * d_lat / z
    # rock-back angle until the rear skirt edge (Y −70.5, Z 8) touches the floor (rotation about the axle)
    r = math.hypot(70.5, WHEEL_R - 8.0); a0 = math.atan2(WHEEL_R - 8.0, 70.5)
    rock = math.degrees(math.asin(WHEEL_R / r) - a0)
    # finger force on the top at Y = −40 mm that tips it back
    f_touch = M * G * y / 40.0
    # Monte Carlo on the CoG: estimated / typical masses ±25 %, positions ±5 mm; CAD parts ±12 % (infill)
    n = 20000; ys = np.zeros(n); zs = np.zeros(n)
    items = MP['items']
    m0 = np.array([it['mass_g'] for it in items]); p0 = np.array([it['pos_mm'] for it in items])
    est = np.array([('CAD' not in it['src']) for it in items])
    dm = np.where(est, 0.25, 0.12)
    for k in range(n):
        m = m0 * (1 + RNG.uniform(-1, 1, len(m0)) * dm)
        p = p0 + np.where(est[:, None], RNG.uniform(-5, 5, p0.shape), 0.0)
        ys[k] = (m * p[:, 1]).sum() / m.sum(); zs[k] = (m * p[:, 2]).sum() / m.sum()
    # fixes: 100 g front ballast (Y 58, Z 14, under the board next to the caster) / rear anti-tip glides
    def with_ballast(mb, yb, zb):
        mt = MP['mass_g'] + mb
        return (MP['mass_g'] * y + mb * yb) / mt, (MP['mass_g'] * z + mb * zb) / mt
    yb100, zb100 = with_ballast(100, 58.0, 14.0)
    res = dict(mass_g=MP['mass_g'], cg_mm=CG, caster_load_g=MP['mass_g'] * caster_frac, a_tip_ms2=a_tip,
               a_lat_ms2=a_lat, rock_back_deg=rock, touch_tip_N=f_touch, cg_y_p05=float(np.percentile(ys, 5)),
               cg_y_p95=float(np.percentile(ys, 95)), p_cg_behind_axle=float((ys < 0).mean()),
               ballast100=dict(cg_y=yb100, cg_z=zb100, a_tip=G * yb100 / zb100))
    # plot: side view + histogram
    fig, ax = plt.subplots(1, 2, figsize=(10, 4.2), gridspec_kw=dict(width_ratios=[1.35, 1]))
    a = ax[0]
    a.add_patch(plt.Rectangle((-70.5, 8), 141, 98, fill=False, ec=C['grey'], lw=1))
    a.add_patch(plt.Circle((0, WHEEL_R), WHEEL_R, fill=False, ec='k', lw=1.4))
    a.add_patch(plt.Circle((CASTER_Y, 6.35), 6.35, fill=False, ec='k', lw=1.2))
    a.plot([-75, 80], [0, 0], color='k', lw=1)
    a.plot(y, z, 'o', color=C['red'], ms=8); a.annotate(f'CoG ({y:.1f}, {z:.1f}) mm', (y, z), (12, 62), fontsize=8,
                                                        arrowprops=dict(arrowstyle='->', lw=0.8))
    a.plot(yb100, zb100, 'o', color=C['green'], ms=6)
    a.annotate(f'with 100 g front ballast: Y {yb100:.1f}', (yb100, zb100), (20, 30), fontsize=7.5, color=C['green'],
               arrowprops=dict(arrowstyle='->', lw=0.7, color=C['green']))
    a.plot([0, y], [0, z], color=C['red'], lw=0.8, ls=':')
    a.text(-66, 96, 'rear', fontsize=8, color=C['grey']); a.text(52, 96, 'front', fontsize=8, color=C['grey'])
    a.text(-60, -9, f'tips back at a ≥ {a_tip:.2f} m/s² (forward acceleration or braking in reverse)', fontsize=7.5, color=C['red'])
    a.set_aspect('equal'); a.set_xlim(-78, 82); a.set_ylim(-14, 112)
    style(a, 'Side view: wheels at Y 0, caster at Y 50', 'Y (mm)', 'Z (mm)')
    b = ax[1]
    b.hist(ys, bins=60, color=C['blue'], alpha=0.8)
    b.axvline(0, color=C['red'], lw=1.2); b.text(0.3, b.get_ylim()[1] * 0.9, 'axle', color=C['red'], fontsize=8)
    style(b, f'CoG Y, mass/position uncertainty (5–95 %: {res["cg_y_p05"]:.1f}–{res["cg_y_p95"]:.1f} mm)', 'CoG Y (mm)', 'samples')
    res['plot'] = save(fig, 'sys_a_stability')
    return res

# ======================================================================== B. drive (N20 options)
N20 = dict(R=9.0, I0=0.04, n0_rpm=15000, V=6.0)     # generic GA12-N20 6 V base motor: stall 0.67 A, 15 000 rpm (est., vendor tables)
KE = (N20['V'] - N20['I0'] * N20['R']) / (N20['n0_rpm'] * 2 * math.pi / 60)   # V·s/rad = N·m/A

def b_drive():
    r = WHEEL_R / 1000
    ratios = {30: 0.65, 50: 0.62, 100: 0.55, 150: 0.52, 298: 0.48}  # gearbox efficiency (est.)
    res = {}
    fig, ax = plt.subplots(1, 1, figsize=(9, 4.2))
    a_tip = G * CG[1] / CG[2]
    for ratio, eta in ratios.items():
        V = 6.0
        w0 = (V - N20['I0'] * N20['R']) / KE / ratio            # wheel no-load rad/s
        Ts = KE * (V / N20['R'] - N20['I0']) * ratio * eta        # wheel stall torque (one motor)
        vmax = w0 * r; Fs = 2 * Ts / r                            # robot: two motors
        res[ratio] = dict(rpm=w0 * 60 / 2 / math.pi, v_max_ms=vmax, stall_torque_kgcm=Ts / 0.0981, F_stall_N=Fs,
                          a_max_ms2=Fs / M, counts_per_mm=28 * ratio / (2 * math.pi * WHEEL_R),
                          v_min_ctrl_ms=0.08 * vmax)
        if ratio in (50, 100, 150):
            v = np.linspace(0, vmax, 50)
            ax.plot(v, Fs * (1 - v / vmax), lw=1.6, label=f'1:{ratio} ({res[ratio]["rpm"]:.0f} rpm): v max {vmax:.2f} m/s, F stall {Fs:.1f} N')
    for crr, lab in ((0.015, 'rolling, hard floor'), (0.05, 'rolling, carpet')):
        ax.axhline(M * G * crr, color=C['grey'], lw=0.9, ls='--'); ax.text(0.72, M * G * crr * 1.08, lab, fontsize=7.5, color=C['grey'])
    ft = M * a_tip + M * G * 0.015
    ax.axhline(ft, color=C['red'], lw=1.2); ax.text(0.40, ft * 1.12, f'tip-back limit: a = {a_tip:.2f} m/s² ({ft:.2f} N)', fontsize=8, color=C['red'])
    ax.set_yscale('log'); ax.set_ylim(0.05, 30); ax.set_xlim(0, 0.95)
    style(ax, f'Traction force vs speed, two N20 6 V motors, Ø43 wheels, robot {M * 1000:.0f} g', 'speed (m/s)', 'force at the floor (N)')
    ax.legend(fontsize=7.5, frameon=False, loc='upper right')
    res['plot'] = save(fig, 'sys_b_drive')
    # motor current for a 0.4 m/s² ramp to 0.25 m/s on a hard floor (1:100)
    Tw = (M * 0.4 + M * G * 0.015) * r / 2
    res['ramp_current_A'] = Tw / (KE * 100 * 0.55) + N20['I0']
    res['stall_current_8V4_A'] = 8.4 / (N20['R'] + 1.0)        # + TB6612 Ron (≈ 0.5 + 0.5 Ω)
    return res

# ======================================================================== C. power budget and runtime
CELL = dict(cap_ah=3.05, soc=[0, 5, 10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 100],
            ocv=[3.00, 3.30, 3.45, 3.57, 3.63, 3.68, 3.73, 3.80, 3.88, 3.97, 4.07, 4.13, 4.20])   # NMC 18650 (typ.)
R1P, TAU1 = 0.060, 900.0                          # pack polarisation branch (diffusion) for the CV tail (est.)
RPACK = 0.030 + 2 * 0.0105 + 0.0056 + 0.010      # 2S2P cells + CSD17579 ×2 (VGS ≈ 7 V) + NANO2 fuse + wiring (Ω)
CAP = 2 * CELL['cap_ah']                          # 2P

def ocv(soc):
    return 2 * np.interp(soc, CELL['soc'], CELL['ocv'])

LOADS = {   # W at the load (est. — Pi 5 figures from published measurements; Camera Module 3 and XVF3800 powered by the Pi)
    'Pi off (standby)':      dict(pi=0.0,  xvf=0.0, lcd=0.0,  esp=0.10, tof=0.0,  mot=0.0),
    'Idle, listening':       dict(pi=3.0,  xvf=0.5, lcd=0.15, esp=0.20, tof=0.10, mot=0.0),
    'Conversation (cloud AI)': dict(pi=4.5, xvf=0.8, lcd=0.15, esp=0.20, tof=0.10, mot=0.1),
    'Vision + driving':      dict(pi=6.5,  xvf=0.6, lcd=0.15, esp=0.25, tof=0.15, mot=0.5),
    'Full load (local AI)':  dict(pi=7.5,  xvf=0.8, lcd=0.15, esp=0.25, tof=0.15, mot=0.5),
}

def sys_power(l):
    p5 = l['pi'] + l['xvf']
    eta5 = 0.0 if p5 == 0 else (0.90 if p5 < 2.5 else 0.93)
    p3 = l['lcd'] + l['esp'] + l['tof'] + 0.03
    return (p5 / eta5 if p5 else 0.0) + p3 / 0.86 + l['mot'] / 0.85 + 0.01

def c_runtime():
    res = {}
    for name, l in LOADS.items():
        P = sys_power(l)
        soc, t, dt = 100.0, 0.0, 30.0
        while True:
            v = ocv(soc); i = P / v; v -= i * RPACK
            if v / 2 < 3.25 or soc <= 0.5:                      # firmware cut-off 3.25 V/cell under load
                break
            soc -= i * dt / 3600 / CAP * 100; t += dt
        res[name] = dict(P_bat_W=P, runtime_h=t / 3600, I_bat_A=P / 7.4)
    fig, ax = plt.subplots(1, 1, figsize=(9, 3.4))
    names = list(res)
    ax.barh(names, [res[n]['runtime_h'] for n in names], color=C['blue'])
    for k, n in enumerate(names):
        ax.text(res[n]['runtime_h'] + 1, k, f'{res[n]["runtime_h"]:.1f} h  ({res[n]["P_bat_W"]:.1f} W from the battery)', va='center', fontsize=8)
    ax.set_xscale('log'); ax.set_xlim(1, 2000); ax.invert_yaxis()
    style(ax, f'Runtime on the 2S2P pack ({2 * 3.6 * CAP:.0f} Wh nominal, cut-off 3.25 V/cell)', 'hours (log scale)')
    res['plot'] = save(fig, 'sys_c_runtime')
    return res

# ======================================================================== D. charging (BQ25798)
def charge(src, iindpm, psys, ichg=3.0, vreg=8.4, iterm=0.2, soc0=10.0):
    """src 'dock' (12 V adapter: cable 0.12 Ω, PTC + Q1 0.08 Ω, pogo loop ≤ 0.1 Ω, ACFETs 0.02 Ω; buck η 0.94)
    or 'usb' (5 V: 1 m cable 0.12 Ω + ACFETs 0.02 Ω; boost η 0.91)."""
    v0, rin, eta = (12.0, 0.32, 0.94) if src == 'dock' else (5.0, 0.14, 0.91)
    soc, t, dt, vp = soc0, 0.0, 10.0, 0.0
    T, S, I = [], [], []
    while t < 12 * 3600:
        pin = (v0 - rin * iindpm) * iindpm * eta - psys
        vo = ocv(soc)
        icc = min(ichg, pin / (vo + vp + ichg * RPACK)) if pin > 0 else pin / vo
        icv = (vreg - vo - vp) / RPACK
        ib = min(icc, icv)
        if icv < icc and ib < iterm:
            break
        vp += (ib * R1P - vp) * dt / TAU1
        soc = min(100.0, soc + ib * dt / 3600 / CAP * 100); t += dt
        T.append(t); S.append(soc); I.append(ib)
    T = np.array(T); S = np.array(S)
    t80 = float(T[np.argmax(S >= 80)] / 3600) if (S >= 80).any() else None
    return dict(t_full_h=t / 3600, t_10_80_h=t80, I_max=float(max(I)), P_in_W=(v0 - rin * iindpm) * iindpm), T, S, np.array(I)

def d_charging():
    p_idle = sys_power(LOADS['Idle, listening']); p_off = sys_power(LOADS['Pi off (standby)'])
    cases = [('Dock, IINDPM 2.5 A, Pi idle', 'dock', 2.5, p_idle, C['blue']),
             ('Dock, IINDPM 1.8 A, Pi idle', 'dock', 1.8, p_idle, C['cyan']),
             ('Dock, IINDPM 1.8 A, Pi off', 'dock', 1.8, p_off, C['green']),
             ('USB-C 5 V 3 A source, Pi idle', 'usb', 3.0, p_idle, C['orange']),
             ('USB 5 V 1.5 A source, Pi idle', 'usb', 1.5, p_idle, C['red'])]
    res = {}
    fig, ax = plt.subplots(2, 1, figsize=(9, 5.8), sharex=True)
    for lab, src, ii, ps, col in cases:
        m, T, S, I = charge(src, ii, ps)
        res[lab] = m
        ax[0].plot(T / 3600, S, color=col, lw=1.4, label=lab + (f': full in {m["t_full_h"]:.1f} h' if m['t_full_h'] < 11.9 else ': > 12 h'))
        ax[1].plot(T / 3600, I, color=col, lw=1.2)
    style(ax[0], 'Charging from 10 % (BQ25798, ICHG 3 A, 8.4 V, termination 0.2 A)', yl='state of charge (%)')
    ax[0].legend(fontsize=7.3, frameon=False, loc='lower right')
    style(ax[1], 'Battery current', 'hours', 'A')
    res['plot'] = save(fig, 'sys_d_charging')
    return res

# ======================================================================== E. pogo pins: current sharing
def e_pogo():
    """YTC1P-8020-01 datasheet: 1.5 A max, contact resistance ≤ 100 mΩ, 12 V DC, 10 000 cycles. Two pins per polarity:
    the pair with the larger mismatch decides. R per contact ~ U(20, 100) mΩ (new ≈ 20–40, worn/dirty up to 100)."""
    n = 50000
    res = {}
    fig, ax = plt.subplots(1, 1, figsize=(9, 3.4))
    for k, (ii, col) in enumerate(((2.5, C['red']), (2.0, C['orange']), (1.8, C['green']))):
        imax = np.zeros(n)
        for pol in range(2):
            r1 = RNG.uniform(0.02, 0.10, n); r2 = RNG.uniform(0.02, 0.10, n)
            i1 = ii * r2 / (r1 + r2)
            imax = np.maximum(imax, np.maximum(i1, ii - i1))
        res[f'{ii}A'] = dict(p_over_1A5=float((imax > 1.5).mean()), i_worst=float(imax.max()),
                             drop_V=ii * 0.05 * 2, p_contact_W=(ii / 2) ** 2 * 0.1)
        ax.hist(imax, bins=80, histtype='step', color=col, lw=1.5,
                label=f'IINDPM {ii} A: P(one pin > 1.5 A) = {res[f"{ii}A"]["p_over_1A5"] * 100:.0f} %')
    ax.set_ylim(0, ax.get_ylim()[1] * 1.55)
    ax.axvline(1.5, color='k', lw=1); ax.text(1.51, ax.get_ylim()[1] * 0.6, 'pin rating 1.5 A', fontsize=8)
    style(ax, 'Highest pogo-pin current (2 pins per polarity, contact resistance 20–100 mΩ each)', 'A', 'samples')
    ax.legend(fontsize=7.5, frameon=False, loc='upper left', ncol=2)
    res['plot'] = save(fig, 'sys_e_pogo')
    return res

# ======================================================================== F. protector and fuse margins
def f_protection():
    """R5460N212AF: VDET3 0.200 V ±15 mV (12 ms), VSHORT 1.1 V (0.7–1.5 V, 300 µs), charge VDET4 −0.2 V (−0.17…−0.23 V);
    CSD17579Q3A ×2 in series: RDS(on) max 10.2 mΩ at 10 V, 14.2 mΩ at 4.5 V (TI) → at VGS 6–8 V ≈ 8.5 (typ, 25 °C) …
    12.6 mΩ (max) ×1.15 at 60 °C. NANO2 0451010 10 A."""
    r_min, r_typ, r_max = 2 * 0.0085, 2 * 0.0100, 2 * 0.0126 * 1.15
    oc = dict(min=0.185 / r_max, typ=0.200 / r_typ, max=0.215 / r_min)
    sc = dict(min=0.7 / r_max, typ=1.1 / r_typ, max=1.5 / r_min)
    coc = dict(min=0.17 / r_max, typ=0.2 / r_typ)
    v_low = 6.4
    loads = {'Pi realistic peak (3 A at 5.15 V)': 3 * 5.15 / 0.93 / v_low,
             'Pi absolute max (5 A at 5.15 V)': 5 * 5.15 / 0.92 / v_low,
             'both motors stalled (6.4 V / 10 Ω each)': 2 * 0.64,
             '3.3 V rail + rest': 0.35}
    worst = loads['Pi absolute max (5 A at 5.15 V)'] + loads['both motors stalled (6.4 V / 10 Ω each)'] + loads['3.3 V rail + rest']
    real = loads['Pi realistic peak (3 A at 5.15 V)'] + loads['both motors stalled (6.4 V / 10 Ω each)'] + loads['3.3 V rail + rest']
    res = dict(oc_trip_A=oc, short_trip_A=sc, charge_oc_trip_A=coc, loads_A=loads, worst_A=worst, realistic_A=real,
               fuse_A=10, cell_ocv_max=4.29)
    fig, ax = plt.subplots(1, 1, figsize=(9, 2.8))
    ax.barh(['discharge over-current trip (12 ms)'], [oc['max'] - oc['min']], left=[oc['min']], color=C['orange'], alpha=0.6)
    ax.plot([oc['typ']], [0], 'k|', ms=18)
    ax.barh(['battery current'], [worst - real], left=[real], color=C['blue'], alpha=0.6)
    ax.plot([real], [1], 'k|', ms=18)
    ax.axvline(10, color=C['red'], lw=1); ax.text(10.1, 1.25, 'NANO2 fuse 10 A', fontsize=8, color=C['red'])
    ax.text(real, 1.32, f'realistic peak {real:.1f} A', fontsize=7.5); ax.text(worst + 0.1, 0.9, f'worst {worst:.1f} A', fontsize=7.5)
    ax.text(oc['min'], -0.42, f'{oc["min"]:.1f} A (min) … {oc["typ"]:.1f} (typ) … {oc["max"]:.1f} A (max)', fontsize=7.5)
    ax.set_xlim(0, 16)
    style(ax, 'Battery protector (R5460N212AF + 2 × CSD17579Q3A) vs. load current at 6.4 V', 'A')
    res['plot'] = save(fig, 'sys_f_protection')
    return res

# ======================================================================== G. thermal
def g_thermal():
    """Lumped network. Shell 141 × 141 × 98 mm PETG 2 mm: A ≈ 0.075 m², h_in 7, h_out 10.5 (5 conv. + 5.5 rad., ε 0.9)
    → G_wall ≈ 0.30 W/K; board underside to the ventilated floor gap ≈ 0.08 W/K; stack-effect flow through the wheel
    cut-outs (in) and the gills 528 mm² + halo holes 108 mm² (out), height 55 mm, Cd 0.6; Active Cooler blower
    ≈ 0.6 L/s with 10–30 % exchanged through the gills. Pi 5 SoC: θ(SoC → cooler air) ≈ 8.5 K/W at full fan
    (≈ 62 °C at ≈ 4.5 W SoC in a 22 °C room, published measurements), SoC ≈ 65 % of the Pi board power."""
    def t_int(p, tamb, fan_f=0.15, gw=0.30, aeff=537e-6):
        dT = 5.0
        for _ in range(50):
            q_stack = 0.6 * aeff * math.sqrt(2 * G * 0.055 * max(dT, 0.1) / 300)
            gv = 1.2 * 1005 * (q_stack + 0.6e-3 * fan_f)
            dT = p / (gw + 0.08 + gv)
        return tamb + dT
    def internal_power(pi, charging):
        p = pi + 0.5 + pi * (1 / 0.93 - 1) + 0.5 + 0.1
        if charging:
            p += 25 * 0.06 + 0.3
        return p
    res = {}
    fig, ax = plt.subplots(1, 1, figsize=(9, 4))
    pis = np.linspace(2, 9, 30)
    for tamb, col in ((25, C['blue']), (30, C['orange']), (35, C['red'])):
        lo = [t_int(internal_power(p, False), tamb, 0.30, 0.36) + 0.65 * p * 8.5 for p in pis]
        mid = [t_int(internal_power(p, False), tamb) + 0.65 * p * 8.5 for p in pis]
        hi = [t_int(internal_power(p, False), tamb, 0.10, 0.25) + 0.65 * p * 8.5 for p in pis]
        ax.fill_between(pis, lo, hi, color=col, alpha=0.15)
        ax.plot(pis, mid, color=col, lw=1.6, label=f'ambient {tamb} °C')
        if tamb == 25:
            imp = [t_int(internal_power(p, False), tamb, 0.40, 0.30, 1000e-6) + 0.65 * p * 8.5 for p in pis]
            ax.plot(pis, imp, color=col, lw=1.0, ls='--', label='25 °C, gills ×2 + low inlet (option)')
            opn = [tamb + 0.65 * p * 8.5 for p in pis]
            ax.plot(pis, opn, color=C['grey'], lw=1.0, ls=':', label='25 °C, Pi 5 in open air (reference)')
    limit(ax, 80, 'Pi 5 soft throttling 80 °C'); limit(ax, 85, 'hard limit 85 °C')
    style(ax, 'Pi 5 SoC temperature inside the shell (band: venting / wall-coefficient uncertainty)', 'Pi 5 board power (W)', '°C')
    ax.legend(fontsize=7.5, frameon=False, loc='lower right'); ax.set_ylim(30, 95)
    res['plot'] = save(fig, 'sys_g_thermal')
    for name, pi, ch in (('idle', 3.0, False), ('conversation', 4.5, False), ('full load', 7.5, False),
                         ('docked + charging, idle', 3.0, True), ('docked + charging, full load', 7.5, True)):
        for tamb in (25, 35):
            ti = t_int(internal_power(pi, ch), tamb)
            res[f'{name} @ {tamb} °C'] = dict(T_internal=ti, T_soc=ti + 0.65 * pi * 8.5, P_internal=internal_power(pi, ch),
                                              T_soc_improved=t_int(internal_power(pi, ch), tamb, 0.40, 0.30, 1000e-6) + 0.65 * pi * 8.5)
    return res

# ======================================================================== H. docking Monte Carlo
def h_docking():
    """Dock frame: back wall at y = 0; robot centre (axle) at 71.5 mm when docked; rear face 70.5 mm behind the centre;
    tongue front 37.5 mm from the wall → the rear opening engages when the centre is at 109 mm. Swept radius of the shell
    86.2 mm → the closest in-place turn that clears the tongue (+10 mm) is at 134 mm. Camera lens 68 mm ahead of the
    centre; the tag (40 mm) fits the 41° vertical FOV and the 10 cm focus limit from 0.10 m.
    Lateral error at the opening = x_turn + (D_turn − 38.5 mm)·sin(ψ). Capture if |e| ≤ 2 + chamfer (4.5) mm and |ψ| ≤ 6°.
    Tag pose (per fix, averaged): σ_lat = 0.3 + 0.005·d, σ_ψ = 0.3° + 2.5°/m·d (est., 40 mm tag36h11, 1536 px wide).
    Camera-yaw calibration residual 0.3° (calibrated) / 1.5° (not). Gyro (LSM6DSOX) 180° turn: scale error σ 0.2 %
    (calibrated) / 0.58 % (±1 % uniform), + 0.1°; turn-centre drift σ 1.5 mm; heading drift 0.1°/100 mm driven."""
    n = 40000
    def run(d_fix, d_turn, cal=True, chamfer=4.5):
        sl = 0.3 + 0.005 * d_fix; sp = 0.3 + 2.5 * d_fix / 1000
        x = RNG.normal(0, sl, n)
        psi = RNG.normal(0, sp, n) + RNG.normal(0, 0.3 if cal else 1.5, n)
        s1 = abs(d_fix + 68 - d_turn)
        x = x + s1 * np.sin(np.radians(psi)) + RNG.normal(0, 0.3, n)
        psi = psi + RNG.normal(0, 0.1 * s1 / 100, n)
        psi = psi + 180 * RNG.normal(0, 0.002 if cal else 0.0058, n) + RNG.normal(0, 0.1, n)
        x = x + RNG.normal(0, 1.5, n)
        e = x + (d_turn - 38.5) * np.sin(np.radians(psi))
        ok = (np.abs(e) <= 2 + chamfer) & (np.abs(psi) <= 6)
        return e, psi, float(ok.mean())
    strategies = {
        'A: align at 0.40 m, turn there, reverse 0.40 m': (400, 468, True, 4.5, C['red']),
        'B: last fix at 0.12 m, turn at 134 mm, reverse 62 mm': (120, 134, True, 4.5, C['green']),
        'B without gyro/camera calibration': (120, 134, False, 4.5, C['orange']),
        'A with an 8 mm tongue chamfer': (400, 468, True, 8.0, C['purple']),
    }
    res = {}
    fig, ax = plt.subplots(1, 2, figsize=(10.5, 3.9))
    for lab, (df, dt, cal, ch, col) in strategies.items():
        e, psi, p = run(df, dt, cal, ch)
        res[lab] = dict(success=p, sigma_e_mm=float(e.std()), p_retry3=1 - (1 - p) ** 3)
        if ch == 4.5:
            ax[0].hist(e, bins=120, range=(-40, 40), histtype='step', lw=1.4, color=col, density=True, label=f'{lab}: {p * 100:.1f} %')
    ax[0].axvspan(-6.5, 6.5, color=C['green'], alpha=0.08); ax[0].text(-6, ax[0].get_ylim()[1] * 0.92, 'capture ±6.5 mm', fontsize=7.5)
    style(ax[0], 'Lateral error at the rear opening', 'mm', 'density'); ax[0].legend(fontsize=6.8, frameon=False, loc='upper left', bbox_to_anchor=(0, 0.85))
    dts = np.linspace(134, 500, 24)
    for cal, col, lab in ((True, C['green'], 'calibrated gyro + camera'), (False, C['orange'], 'not calibrated')):
        ps = [run(max(100, d - 68) if d > 188 else 120, d, cal)[2] for d in dts]
        ax[1].plot(dts, np.array(ps) * 100, color=col, lw=1.6, label=lab)
    style(ax[1], 'First-try success vs. turn point', 'robot centre to the dock wall at the 180° turn (mm)', '%')
    ax[1].legend(fontsize=7.5, frameon=False); ax[1].set_ylim(0, 102)
    res['plot'] = save(fig, 'sys_h_docking')
    return res

# ======================================================================== I. AprilTag detection range
def i_apriltag():
    """Camera Module 3 (standard lens): HFOV 66°, VFOV 41°, focus from 10 cm. tag36h11: 8 cells across the black square
    (40 mm → 5 mm/cell). Reliable decoding ≈ ≥ 3 px/cell (24 px), pose for docking ≥ 8 px/cell."""
    d = np.linspace(0.08, 3.0, 300)
    res = {}
    fig, ax = plt.subplots(1, 1, figsize=(9, 3.4))
    for w, col in ((1536, C['blue']), (2304, C['purple']), (640, C['orange'])):
        px = w * 40 / (2 * d * 1000 * math.tan(math.radians(33)))
        ax.plot(d, px, color=col, lw=1.5, label=f'{w} px wide stream')
        res[f'{w}px'] = dict(d_max_detect_m=float(w * 40 / (24 * 2 * math.tan(math.radians(33))) / 1000),
                             d_max_pose_m=float(w * 40 / (64 * 2 * math.tan(math.radians(33))) / 1000))
    ax.axhline(24, color=C['red'], lw=1, ls='--'); ax.text(2.2, 26, 'detection ≈ 24 px', fontsize=7.5, color=C['red'])
    ax.axhline(64, color=C['green'], lw=1, ls='--'); ax.text(2.2, 67, 'good pose ≈ 64 px', fontsize=7.5, color=C['green'])
    ax.axvline(0.10, color=C['grey'], lw=1, ls=':'); ax.text(0.11, 600, 'focus limit 0.1 m', fontsize=7.5, color=C['grey'])
    ax.set_yscale('log'); ax.set_ylim(8, 2000)
    style(ax, 'AprilTag (40 mm) size in the image vs. distance — Camera Module 3', 'camera–tag distance (m)', 'tag width (px)')
    ax.legend(fontsize=7.5, frameon=False)
    res['min_distance_fov_m'] = 0.05 * 1.2 / (2 * math.tan(math.radians(20.5)))
    res['plot'] = save(fig, 'sys_i_apriltag')
    return res

if __name__ == '__main__':
    R = dict(A_stability=a_stability(), B_drive=b_drive(), C_runtime=c_runtime(), D_charging=d_charging(),
             E_pogo=e_pogo(), F_protection=f_protection(), G_thermal=g_thermal(), H_docking=h_docking(),
             I_apriltag=i_apriltag())
    json.dump(R, open(os.path.join(OUT, 'system_results.json'), 'w'), indent=1, default=float)
    print(json.dumps(R, indent=1, default=lambda o: round(float(o), 3))[:12000])
