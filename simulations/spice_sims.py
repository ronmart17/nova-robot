"""NOVA Rev B — circuit simulations (ngspice 42, batch). Each sim writes its netlist to spice/, runs it, returns
measurements and saves a plot to out/. Values come from the Rev B schematics / BOM (see the notes in each function).
Run: python3 spice_sims.py [names...]"""
import os, sys, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import spice_lib as S
import cot

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
os.makedirs(OUT, exist_ok=True)
C = dict(blue='#1f6fb5', red='#c8423b', green='#2e8b57', orange='#e08a1e', grey='#6b7280', purple='#7a4fb5', cyan='#1aa6b7')

def style(ax, title=None, xl=None, yl=None):
    ax.grid(True, color='#e3e7ee', lw=0.8)
    for s in ('top', 'right'):
        ax.spines[s].set_visible(False)
    if title: ax.set_title(title, fontsize=10.5, loc='left', color='#1d2430')
    if xl: ax.set_xlabel(xl, fontsize=9)
    if yl: ax.set_ylabel(yl, fontsize=9)
    ax.tick_params(labelsize=8.5)

def save(fig, name):
    fig.tight_layout()
    p = os.path.join(OUT, name + '.png')
    fig.savefig(p, dpi=140)
    plt.close(fig)
    return p

def limit(ax, y, text, color=C['red']):
    ax.axhline(y, color=color, lw=1, ls='--')
    ax.text(ax.get_xlim()[1], y, ' ' + text, va='center', ha='left', fontsize=7.5, color=color, clip_on=False)

# ------------------------------------------------------------------ battery / VSYS model shared by several sims
BAT = dict(r=0.09, l='0.3u')     # 2S2P 18650 (≈ 2 × 17 mΩ) + 2 × CSD17579 (≈ 2 × 10 mΩ) + fuse 5.6 mΩ + BATFET + wiring

def vsys_bank(node='vsys'):
    """Lumped VSYS capacitance: ceramics derated for DC bias at ≈ 7.4 V and the 100 µF electrolytic (C502)."""
    return [f'* VSYS bank: C210–C214 5×10 µF, C503/C504 2×22 µF, C301–C303 3×10 µF (25 V X5R, ≈ 55 % at 7.4 V) + C502',
            f'Ccer {node} ncer 72u', 'Rcer ncer 0 2m',
            f'Cel {node} nel 100u', 'Rel nel 0 0.34']

# ------------------------------------------------------------------ S1: VSYS with the motors under PWM
def s1_vsys_motors(vbat=7.4):
    """TB6612 (Ron ≈ 0.5 Ω high + low side), both channels in phase at 20 kHz / 75 % (worst case), N20 motor
    R 9 Ω / L 0.6 mH / back-EMF (running 4.0 V; stall at start = 0 V). Pi 5 buck input = pulsed current (3 A, D ≈ 0.7,
    600 kHz), 3.3 V buck 0.25 A average. Start-up of both motors from standstill at t = 2 ms."""
    net = [f'* S1 VSYS + motors', f'Vbat bat 0 {vbat}', f'Rb bat b1 {BAT["r"]}', f'Lb b1 vsys {BAT["l"]}'] + vsys_bank()
    net += ['Vpwm pwm 0 PULSE(0 1 0 20n 20n 37.5u 50u)']
    for k in (1, 2):
        net += [f'S{k} vsys m{k} pwm 0 SWM', f'D{k} 0 m{k} DF', f'Rm{k} m{k} ma{k} 9.5', f'Lm{k} ma{k} mb{k} 0.6m',
                f'Bemf{k} mb{k} 0 V = time < 2m ? 4.0 : 0']
    net += ['.model SWM SW(Ron=0.5 Roff=1Meg Vt=0.5 Vh=0.1)', '.model DF D(Is=1e-9 N=1.5 Rs=0.05)',
            'Vpi pis 0 PULSE(0 1 0 5n 5n 1.15u 1.667u)', 'Bpi vsys 0 I = 3*v(pis)', 'I33 vsys 0 0.25',
            '.tran 20n 4m 0 20n',
            '.meas tran vavg AVG v(vsys) from=1m to=2m', '.meas tran vpp PP v(vsys) from=1m to=2m',
            '.meas tran vmin MIN v(vsys) from=1m to=4m', '.meas tran ibat AVG i(Vbat) from=1m to=2m',
            '.meas tran imot AVG i(Lm1) from=1m to=2m', '.meas tran imot_st AVG i(Lm1) from=3.5m to=4m',
            '.meas tran vpp_st PP v(vsys) from=3.5m to=4m', '.meas tran ibat_st AVG i(Vbat) from=3.5m to=4m']
    t, d, m = S.run('s1_vsys_motors', '\n'.join(net), ['v(vsys)', 'i(Lm1)', 'i(Vbat)'])
    fig, ax = plt.subplots(2, 1, figsize=(9, 5.6), sharex=True)
    ax[0].plot(t * 1e3, d['v(vsys)'], color=C['blue'], lw=0.6)
    style(ax[0], f'VSYS — battery {vbat} V, both motors PWM 20 kHz 75 % + Pi 5 buck 3 A + 3.3 V buck', yl='V')
    ax[1].plot(t * 1e3, d['i(Lm1)'], color=C['orange'], lw=0.8, label='motor current (each)')
    ax[1].plot(t * 1e3, -d['i(Vbat)'], color=C['grey'], lw=0.5, alpha=0.7, label='battery current')
    ax[1].axvline(2, color=C['red'], lw=0.8, ls=':'); ax[1].text(2.03, ax[1].get_ylim()[1] * 0.85, 'motors stalled / start', fontsize=7.5, color=C['red'])
    style(ax[1], None, 'ms', 'A'); ax[1].legend(fontsize=7.5, loc='upper left', frameon=False)
    m['plot'] = save(fig, f's1_vsys_motors_{vbat:.1f}V')
    return m

# ------------------------------------------------------------------ S2: Pi 5 V rail (TPS566238 behavioural COT)
PI = dict(fsw=600e3, vout=5.15, vref=0.6, rtop='182k', rbot='24k', cff='33p', L='2.2u', dcr='12.5m', rhs='0.0208',
          rls='0.0106', kinj=0.1, tau_inj=10 / 600e3, toff_min=100e-9)

def s2_pi_rail(vin=7.4, i0=1.0, i1=3.0, slew=1.0, tag='a', **over):
    """Datasheet values: VFB 0.6 V, 600 kHz FCCM, toff(min) 100 ns, Rds(on) 20.8/10.6 mΩ, valley limit ≥ 6.1 A.
    Cout C307–C309 3×47 µF/10 V 1206 X5R ≈ 3×20 µF at 5 V (+ C310), C701/C702 at J702. USB-C cable to the Pi:
    VBUS + GND ≈ 2 × 25 mΩ incl. contacts, 0.15 µH; Pi 5 input ≈ 20 µF. Load step i0 → i1 at `slew` A/µs at the Pi."""
    p = dict(PI, il0=i0, tau_int=300e-6, **over)
    vo = p['vout']
    tr = (i1 - i0) / slew * 1e-6
    T0, T1, TE = 2.0e-3, 2.5e-3, 3.0e-3
    net = [f'* S2 Pi rail', f'Vin vin0 0 {vin}', 'Rin vin0 vin 15m', 'Cin vin 0 18u'] + cot.cot_buck(p, 'vin', 'vout')
    net += [f'Cout vout co 60u ic={vo}', 'Rco co 0 1m', 'C310 vout 0 100n',
            'Rpcb vout j702 4m', f'C701 j702 0 8u ic={vo}',
            'Rcab j702 c1 50m', f'Lcab c1 pi 0.15u ic={i0}', f'Cpi pi cpi 20u ic={vo - 0.054 * i0:.4f}', 'Rcpi cpi 0 10m',
            f'Ipi pi 0 PWL(0 {i0} {T0} {i0} {T0 + tr} {i1} {T1} {i1} {T1 + tr} {i0})',
            '.option method=gear reltol=1e-3', f'.tran 2n {TE} 0 2n uic',
            f'.meas tran vavg AVG v(vout) from=1.8m to={T0}', f'.meas tran vpp PP v(vout) from=1.8m to={T0}',
            f'.meas tran vpi0 AVG v(pi) from=1.8m to={T0}', f'.meas tran vpi1 AVG v(pi) from=2.4m to={T1}',
            f'.meas tran vmin MIN v(vout) from={T0} to=2.4m', f'.meas tran vpimin MIN v(pi) from={T0} to=2.4m',
            f'.meas tran vmax MAX v(vout) from={T1} to={TE}', f'.meas tran vpp1 PP v(vout) from=2.4m to={T1}',
            f'.meas tran ilmax MAX i(LX1) from={T0} to={T1}', f'.meas tran ilmin MIN i(LX1) from=2.4m to={T1}']
    t, d, m = S.run(f's2_pi_rail_{tag}', '\n'.join(net), ['v(vout)', 'v(pi)', 'i(LX1)'])
    sel = t > 1.7e-3
    t, d = t[sel], {k: v[sel] for k, v in d.items()}
    fig, ax = plt.subplots(2, 1, figsize=(9, 5.6), sharex=True)
    ax[0].plot(t * 1e3, d['v(vout)'], color=C['blue'], lw=0.6, label='buck output (J702)')
    ax[0].plot(t * 1e3, d['v(pi)'], color=C['purple'], lw=0.6, label='at the Pi 5 (after the USB-C cable)')
    ax[0].set_ylim(min(4.5, d['v(pi)'].min() - 0.05), 5.6)
    limit(ax[0], 5.5, 'USB-C sink max 5.5 V', C['orange'])
    style(ax[0], f'+5V set to {vo:.2f} V — VIN {vin} V, load step {i0:g} → {i1:g} A at {slew:g} A/µs (and back)', yl='V')
    limit(ax[0], 4.63, 'Pi 5 under-voltage ≈ 4.63 V')
    ax[0].legend(fontsize=7.5, loc='lower left', frameon=False)
    ax[1].plot(t * 1e3, d['i(LX1)'], color=C['orange'], lw=0.5)
    style(ax[1], 'Inductor current (L301, Isat 11 A; valley limit ≥ 6.1 A)', 'ms', 'A')
    m['plot'] = save(fig, f's2_pi_rail_{tag}')
    if tag == 'a':
        s2 = (t > 2.45e-3) & (t < 2.4565e-3)
        fig, ax = plt.subplots(1, 1, figsize=(9, 2.8))
        ax.plot((t[s2] - t[s2][0]) * 1e6, (d['v(vout)'][s2] - d['v(vout)'][s2].mean()) * 1e3, color=C['blue'], lw=1)
        style(ax, f'Output ripple at {i1:g} A (AC part)', 'µs', 'mV')
        m['plot_ripple'] = save(fig, 's2_pi_ripple')
    return m

# ------------------------------------------------------------------ S3: 3.3 V always-on rail (TPS62933)
def s3_3v3(vin=7.4):
    """TPS62933 at 1.2 MHz (RT to GND), L302 3.3 µH (38 mΩ), Cout C324/C325 2×22 µF/10 V 0805 ≈ 2×13 µF at 3.3 V.
    The part is peak-current-mode; a behavioural COT model at 1.2 MHz is used for ripple and the order of magnitude
    of the load-step response (ESP32 Wi-Fi/BLE burst + display backlight): 0.10 → 0.60 A."""
    p = dict(fsw=1.2e6, vout=3.33, vref=0.8, rtop='31.6k', rbot='10k', cff='10p', L='3.3u', dcr='38m', rhs='0.09',
             rls='0.04', kinj=0.08, tau_inj=10 / 1.2e6, toff_min=140e-9, il0=0.1)
    net = ['* S3 3V3', f'Vin vin 0 {vin}'] + cot.cot_buck(p, 'vin', 'v33', pre='Y')
    net += ['Co v33 co 26u ic=3.33', 'Rco co 0 2m', 'C326 v33 0 100n',
            'Il v33 0 PWL(0 0.1 2.0m 0.1 2.001m 0.6 2.3m 0.6 2.301m 0.1)',
            '.option method=gear reltol=1e-3', '.tran 1n 2.6m 0 1n uic',
            '.meas tran vavg AVG v(v33) from=1.9m to=2.0m', '.meas tran vpp PP v(v33) from=2.2m to=2.3m',
            '.meas tran vpp0 PP v(v33) from=1.9m to=2.0m',
            '.meas tran vmin MIN v(v33) from=2.0m to=2.2m', '.meas tran vmax MAX v(v33) from=2.3m to=2.5m',
            '.meas tran ilmax MAX i(LY1) from=2.0m to=2.3m']
    t, d, m = S.run('s3_3v3', '\n'.join(net), ['v(v33)', 'i(LY1)'])
    sel = t > 1.8e-3
    t, d = t[sel], {k: v[sel] for k, v in d.items()}
    fig, ax = plt.subplots(2, 1, figsize=(9, 5), sharex=True)
    ax[0].plot(t * 1e3, d['v(v33)'], color=C['blue'], lw=0.6)
    style(ax[0], f'+3V3 (always-on) — VIN {vin} V, load step 0.1 → 0.6 A', yl='V')
    limit(ax[0], 3.0, 'ESP32-S3 min. 3.0 V'); limit(ax[0], 3.6, 'abs. max 3.6 V')
    ax[0].set_ylim(2.9, 3.7)
    ax[1].plot(t * 1e3, d['i(LY1)'], color=C['orange'], lw=0.5)
    style(ax[1], 'Inductor current (L302, Isat 8 A)', 'ms', 'A')
    m['plot'] = save(fig, 's3_3v3')
    return m

# ------------------------------------------------------------------ S4: power-up sequence
def s4_power_up():
    """SW301 released at 1 ms → PWR_EN (VSYS through R) → TPS62933 soft-start Css 33 nF (≈ 4.8 ms) → +3V3.
    PI_EN: R310 100k to +3V3, C312 1 nF; TPS566238P EN threshold ≈ 1.2 V, internal soft-start 1.9 ms → +5V.
    ESP32 CHIP_PU: R401 10k / C403 1 µF from +3V3 (Espressif: CHIP_PU after the supply is stable)."""
    net = ['* S4 power-up', 'Vsw en 0 PWL(0 0 1m 0 1.01m 7.4)',
           'B33 v33 0 V = 3.33*min(1, max(0, (time-1.3m)/4.8m))',
           'R310 v33 pien 100k', 'C312 pien 0 1n',
           'B5 v5 0 V = 5.15*min(1, max(0, (time - {tpien})/1.9m))',
           'R401 v33 chpu 10k', 'C403 chpu 0 1u',
           '.param tpien=0', '.tran 2u 25m 0 2u',
           '.meas tran t33 WHEN v(v33)=3.15 RISE=1', '.meas tran tpien WHEN v(pien)=1.2 RISE=1',
           '.meas tran tpu WHEN v(chpu)=2.475 RISE=1']
    # first pass to get the PI_EN time
    t, d, m = S.run('s4_power_up_a', '\n'.join(net), ['v(v33)', 'v(pien)', 'v(chpu)'])
    net2 = [l.replace('.param tpien=0', f'.param tpien={m["tpien"]:.6g}') for l in net]
    net2.append('.meas tran t5 WHEN v(v5)=4.9 RISE=1')
    t, d, m = S.run('s4_power_up', '\n'.join(net2), ['v(en)', 'v(v33)', 'v(pien)', 'v(v5)', 'v(chpu)'])
    fig, ax = plt.subplots(1, 1, figsize=(9, 3.8))
    ax.plot(t * 1e3, d['v(en)'], color=C['grey'], lw=1, label='PWR_EN (switch ON at 1 ms)')
    ax.plot(t * 1e3, d['v(v33)'], color=C['blue'], lw=1.4, label='+3V3')
    ax.plot(t * 1e3, d['v(v5)'], color=C['purple'], lw=1.4, label='+5V (Pi)')
    ax.plot(t * 1e3, d['v(chpu)'], color=C['green'], lw=1.4, label='ESP32 CHIP_PU (EN)')
    ax.axhline(2.475, color=C['green'], lw=0.6, ls=':')
    style(ax, 'Power-up sequence', 'ms', 'V'); ax.legend(fontsize=7.5, frameon=False, loc='center right'); ax.set_ylim(-0.2, 8)
    m['plot'] = save(fig, 's4_power_up')
    return m

# ------------------------------------------------------------------ S5: dock — 12 V hot plug, docking, reverse polarity
TVS15 = '.model TVS15 D(Is=1e-12 N=1 Rs=0.8 BV=17.6 IBV=1m Cjo=150p)'
TVS12 = '.model TVS12 D(Is=1e-12 N=1 Rs=0.9 BV=14.0 IBV=1m Cjo=170p)'

def dock_net(case):
    """Adapter 12 V with 1.5 m cable (0.12 Ω, 1.2 µH) → J1 → F1 PTC (≈ 25 mΩ cold) → Q1 AO3401A (body diode + switch,
    ON when the gate is pulled low: |VGS| clamp D2 10 V) → C1 22 µF/25 V (≈ 10 µF at 12 V) + C2 100 nF + D1 SMF15A →
    2 pogo pins in parallel (≈ 15 mΩ, 10 nH) → contact plate → J2 lead (20 mΩ, 80 nH) → robot J203 →
    C202 1 µF + D202 SMF15A → VAC2 pin of the BQ25798 (abs. max 30 V)."""
    v = '-12' if case == 'reverse' else '12'
    if case == 'plug':           # adapter plugged into the dock with the robot already docked
        src = [f'Vad ad 0 PWL(0 0 10u 0 10.05u {v})']
        contact = 'Rpog d2 rob 15m'
    elif case == 'dock':         # dock live, robot rolls onto the pogo pins at 10 µs
        src = [f'Vad ad 0 {v}']
        contact = 'Spog d2 rob ctl 0 SWP'
    else:
        src = [f'Vad ad 0 PWL(0 0 10u 0 10.05u {v})']
        contact = 'Rpog d2 rob 15m'
    net = ['* S5 dock'] + src + ['Rcab ad a1 0.12', 'Lcab a1 jack 1.2u', 'Rptc jack f1 25m',
            'Dbody f1 q1 DB', 'Sq1 f1 q1 q1 0 SWQ', 'C1 q1 c1n 10u', 'Rc1 c1n 0 3m', 'C2 q1 0 100n', 'D1 0 q1 TVS15',
            'Lpog q1 d2 10n', contact, 'Vctl ctl 0 PWL(0 0 10u 0 10.01u 1)',
            'Rlead rob r1 20m', 'Llead r1 vac2 80n', 'C202 vac2 c202n 1u', 'Rc202 c202n 0 5m', 'Vmd vac2 dk 0', 'D202 0 dk TVS15',
            'Rvac vac2 0 200k',
            '.model DB D(Is=1e-11 N=1.05 Rs=0.05)', '.model SWQ SW(Ron=0.06 Roff=1G Vt=2.5 Vh=0.3)',
            '.model SWP SW(Ron=15m Roff=1G Vt=0.5 Vh=0.1)', TVS15]
    if case == 'dock':
        net += ['.ic v(q1)=12 v(f1)=12 v(jack)=12']
    net += ['.tran 2n 60u 0 2n' + (' uic' if case == 'dock' else ''),
            '.meas tran vmax MAX v(vac2) from=0 to=60u', '.meas tran vmaxd MAX v(q1) from=0 to=60u',
            '.meas tran vmin MIN v(vac2) from=0 to=60u', '.meas tran vfin AVG v(vac2) from=50u to=60u',
            '.meas tran ipog MAX i(Lpog) from=0 to=60u', '.meas tran itvs MAX i(Vmd) from=0 to=60u',
            '.meas tran vjack MIN v(jack) from=0 to=60u']
    return '\n'.join(net)

def s5_dock():
    res = {}
    fig, ax = plt.subplots(3, 1, figsize=(9, 7.4), sharex=True)
    for k, (case, title) in enumerate((('plug', 'Adapter plugged into the dock (robot docked)'),
                                       ('dock', 'Robot docks on a live dock (pogo contact closes)'),
                                       ('reverse', 'Adapter with reversed polarity'))):
        t, d, m = S.run(f's5_dock_{case}', dock_net(case), ['v(q1)', 'v(vac2)', 'v(jack)', 'i(Lpog)'])
        res[case] = m
        if case == 'reverse':
            ax[k].plot(t * 1e6, d['v(jack)'], color=C['red'], lw=1.0, ls='--', label='adapter at J1 (reversed)')
        ax[k].plot(t * 1e6, d['v(q1)'], color=C['grey'], lw=0.9, label='dock side (after Q1)')
        ax[k].plot(t * 1e6, d['v(vac2)'], color=C['blue'], lw=1.1, label='robot VAC2 (BQ25798)')
        style(ax[k], title, 'µs' if k == 2 else None, 'V')
        if k < 2:
            limit(ax[k], 30, 'VAC2 abs. max 30 V'); ax[k].set_ylim(-2, 33)
        else:
            ax[k].set_ylim(-14, 3)
        ax[k].legend(fontsize=7.5, frameon=False, loc='lower right')
    res['plot'] = save(fig, 's5_dock')
    return res

# ------------------------------------------------------------------ S6: USB-C plug-in
def s6_usb_plug():
    """5 V source, 1 m cable (VBUS + GND 0.12 Ω, 0.8 µH) → J201 → C201 1 µF/25 V + D201 SMF12A + U201 USBLC6-2SC6
    (pin 5 on VBUS: internal zener to GND, VBR ≥ 6 V at 1 mA; modelled BV 6.5 V, 2.2 Ω — from its 12 V @ 1 A /
    17 V @ 5 A clamping) + R203/R204 divider → VBUS_DET (90 mm trace + TCA9535 P11 ≈ 15 pF; abs. max 6 V, VIH ≤ 5.5 V).
    The BQ25798 input FETs are still off when the cable is plugged in. Also run without U201 (D201 alone)."""
    res = {}
    fig, ax = plt.subplots(1, 1, figsize=(9, 3.6))
    for k, (u201, damp, col) in enumerate(((False, False, C['grey']), (True, False, C['blue']), (True, True, C['purple']))):
        net = ['* S6 USB-C', 'Vs s 0 PWL(0 0 5u 0 5.05u 5)', 'Rc s c1 0.12', 'Lc c1 vbus 0.8u',
               'C201 vbus cn 1u', 'Rc201 cn 0 5m', 'D201 0 vbus TVS12', 'R203 vbus det 100k', 'R204 det 0 200k',
               'Cdet det 0 15p', TVS12, '.model ZLC6 D(Is=1e-12 N=1 Rs=2.2 BV=6.5 IBV=1m Cjo=50p)']
        if u201:
            net += ['Vmu vbus u5 0', 'DU201 0 u5 ZLC6']
        if damp:      # option: RC damper next to J201, R ≈ Z0 = √(Lcable / C201), C ≈ 3.5 × C201 (4.7 µF/25 V 0805 at 5 V)
            net += ['Rdmp vbus dmp 1', 'Cdmp dmp 0 3.5u']
        net += ['.tran 1n 25u 0 1n', '.meas tran vmax MAX v(vbus)', '.meas tran vdet MAX v(det)',
                '.meas tran vfin AVG v(vbus) from=22u to=25u']
        if u201:
            net += ['.meas tran iu MAX i(Vmu)', '.meas tran qu INTEG i(Vmu) from=5u to=25u']
        if damp:
            net += ['.meas tran iin MAX i(Lc)']
        t, d, m = S.run(f's6_usb_plug_{k}', '\n'.join(net), ['v(vbus)', 'v(det)'])
        res[('damper' if damp else 'with_U201') if u201 else 'D201_only'] = m
        lab = ('+ RC damper 1 Ω / 4.7 µF (option)' if damp else 'as designed (D201 + U201)') if u201 else 'without U201 (D201 only)'
        ax.plot(t * 1e6, d['v(vbus)'], color=col, lw=1.2, label=f'VBUS at J201 — {lab}: peak {m["vmax"]:.1f} V')
        if u201 and not damp:
            ax.plot(t * 1e6, d['v(det)'], color=C['green'], lw=1.0, label=f'VBUS_DET (TCA9535 P11): peak {m["vdet"]:.2f} V')
    style(ax, 'USB-C hot plug (5 V source, 1 m cable, BQ25798 input still off)', 'µs', 'V')
    ax.legend(fontsize=7.5, frameon=False, loc='lower right')
    limit(ax, 6.0, 'TCA9535 abs. max 6 V', C['orange'])
    res['plot'] = save(fig, 's6_usb_plug')
    return res

# ------------------------------------------------------------------ S7: I2C bus edges
I2C_BUS = dict(trace_mm=244 + 54, cable_mm=120, vias=15,
               pins=dict(ESP32_S3_module=5, BQ25798=10, TCA9535=9.5, LSM6DSOX=10, VL53L4CD_L=10, VL53L4CD_R=10,
                         VL53L1X_head=10, connectors=3))

def i2c_cbus(b=I2C_BUS):
    """Trace length from the routed boards (main 244 mm + head 54 mm per line); 1.1 pF/cm for a 0.2 mm trace over the
    plane (Z0 ≈ 55 Ω, εeff ≈ 3.3), 0.5 pF/cm for the head cable, 0.3 pF/via; pin capacitance from the datasheets where
    given (TCA9535 Cio max 9.5 pF), otherwise 10 pF assumed (pessimistic)."""
    c = b['trace_mm'] * 0.11 + b['cable_mm'] * 0.05 + b['vias'] * 0.3 + sum(b['pins'].values())
    return c

def s7_i2c():
    """Pull-ups R408/R409 2.2 kΩ to 3.3 V. Bus capacitance estimated from the layout (i2c_cbus) and +50 % margin.
    Open-drain driver Ron ≈ 40 Ω, 400 kHz fast mode: tr(30→70 %) ≤ 300 ns; Rp ≥ (3.3 − 0.4) / 3 mA = 0.97 kΩ."""
    res = {}
    cb0 = i2c_cbus(); res['cbus_pF'] = cb0
    fig, ax = plt.subplots(1, 1, figsize=(9, 3.6))
    for k, (rp, cb, col) in enumerate((('2.2k', cb0, C['blue']), ('2.2k', 1.5 * cb0, C['orange']), ('1.5k', 1.5 * cb0, C['green']))):
        net = ['* S7 I2C', 'Vdd vdd 0 3.3', f'Rp vdd sda {rp}', f'Cb sda 0 {cb:.1f}p', 'Vg g 0 PULSE(1 0 0.5u 10n 10n 1.25u 2.5u)',
               'Sd sda 0 g 0 SWD', '.model SWD SW(Ron=40 Roff=100Meg Vt=0.5 Vh=0.05)', '.tran 2n 6u',
               '.meas tran t30 WHEN v(sda)=0.99 RISE=1 from=1.7u', '.meas tran t70 WHEN v(sda)=2.31 RISE=1 from=1.7u',
               '.meas tran vol MIN v(sda)']
        t, d, m = S.run(f's7_i2c_{k}', '\n'.join(net), ['v(sda)'])
        m['tr_ns'] = (m['t70'] - m['t30']) * 1e9
        res[f'{rp}_{cb:.0f}p'] = m
        ax.plot(t * 1e6, d['v(sda)'], color=col, lw=1.2, label=f'Rp {rp}Ω, Cbus {cb:.0f} pF: tr = {m["tr_ns"]:.0f} ns')
    style(ax, 'I2C (400 kHz fast mode): rise time 30–70 % must be ≤ 300 ns', 'µs', 'V')
    ax.legend(fontsize=7.5, frameon=False, loc='center right')
    res['plot'] = save(fig, 's7_i2c')
    return res

# ------------------------------------------------------------------ S8: display SPI over the head cable
def s8_spi():
    """ESP32-S3 GPIO → R402/R403 33 Ω → main board trace 48 mm (Z0 55 Ω, from the layout) → JST SH 20-pin cable
    120 mm (≈ 100 Ω, signal next to GND) → head board 73 mm (55 Ω, from the layout) → ST7789 module header + FPC +
    input (≈ 6 pF) with its ESD diodes to VDDI (3.3 V) and GND. SCLK 40 MHz.
    ESP32-S3 drive strength: level 2 (default, '20 mA') ≈ 25 Ω / 1.5 ns edges; level 1 ('10 mA') ≈ 50 Ω / 3 ns."""
    res = {}
    fig, ax = plt.subplots(1, 1, figsize=(9, 3.9))
    cases = (('0R_drv2', '0.01', 25, 1.5, C['red'], 'no series R, drive 2'),
             ('33R_drv2', '33', 25, 1.5, C['blue'], 'R403 33 Ω, drive 2 (default)'),
             ('33R_drv1', '33', 50, 3.0, C['green'], 'R403 33 Ω, drive 1'))
    for k, (key, rs, ro, tr, col, lab) in enumerate(cases):
        net = ['* S8 SPI', f'Vd d 0 PULSE(0 3.3 2n {tr}n {tr}n {12.5 - tr}n 25n)', f'Ro d o {ro}', f'Rs o s {rs}',
               'T1 s 0 a 0 Z0=55 TD=0.30n', 'T2 a 0 b 0 Z0=100 TD=0.58n', 'T3 b 0 r 0 Z0=55 TD=0.45n', 'Cr r 0 6p',
               'Vdi vddi 0 3.3', 'Vmh r rh 0', 'Dh rh vddi DESD', 'Vml rl r 0', 'Dl 0 rl DESD',
               '.model DESD D(Is=1e-14 N=1 Rs=10 Cjo=0.5p)',
               '.tran 5p 60n', '.meas tran vmax MAX v(r) from=25n to=40n', '.meas tran vmin MIN v(r) from=36n to=52n',
               '.meas tran ih MAX i(Vmh) from=25n to=60n', '.meas tran il MAX i(Vml) from=25n to=60n',
               '.meas tran t50 WHEN v(r)=1.65 RISE=2', '.meas tran tlast WHEN v(r)=1.65 CROSS=LAST from=27n to=37n']
        t, d, m = S.run(f's8_spi_{k}', '\n'.join(net), ['v(r)'])
        res[key] = m
        ax.plot(t * 1e9, d['v(r)'], color=col, lw=1.2, label=f'{lab}: peak {m["vmax"]:.2f} V / {m["vmin"]:+.2f} V, '
                                                            f'ESD-diode current ≤ {max(m["ih"], m["il"]) * 1e3:.0f} mA')
    style(ax, 'Display SCLK at the ST7789 module input (40 MHz, through the head cable)', 'ns', 'V')
    limit(ax, 3.6, 'VDDI + 0.3 V', C['orange']); limit(ax, -0.3, '−0.3 V', C['orange'])
    ax.set_ylim(-1.6, 5.0)
    ax.legend(fontsize=7.2, frameon=False, loc='lower center')
    res['plot'] = save(fig, 's8_spi')
    return res

SIMS = dict(s1=lambda: dict(a=s1_vsys_motors(7.4), low=s1_vsys_motors(6.6)),
            s2=lambda: dict(a=s2_pi_rail(7.4, 1.0, 3.0, 1.0, 'a'), b=s2_pi_rail(6.6, 1.0, 3.0, 1.0, 'b'),
                            c=s2_pi_rail(8.4, 0.5, 5.0, 2.0, 'c'), d=s2_pi_rail(6.6, 0.5, 5.0, 2.0, 'd'),
                            e=s2_pi_rail(6.6, 0.5, 5.0, 2.0, 'e', vout=5.217, rtop='187k', rbot='24.3k')),
            s3=lambda: s3_3v3(7.4), s4=s4_power_up, s5=s5_dock, s6=s6_usb_plug, s7=s7_i2c, s8=s8_spi)

if __name__ == '__main__':
    names = sys.argv[1:] or list(SIMS)
    jf = os.path.join(OUT, 'spice_results.json')
    allr = json.load(open(jf)) if os.path.exists(jf) else {}
    for n in names:
        r = SIMS[n]()
        allr[n] = r
        print(n, json.dumps(r, indent=None, default=str)[:900])
        json.dump(allr, open(jf, 'w'), indent=1, default=str)
