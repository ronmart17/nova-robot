"""Simulation schematics (KiCad 10 + ngspice). Each one is a single-sheet A4 project that runs from the KiCad
simulator (Inspect → Simulator) or in batch with runsim.py. The .tran/.meas directives live in the schematic itself."""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
from sch import Project, Sheet, uid, add_junctions, prop_node, Sym, _on_seg
from sexpr import fmt
import design_main

PF = 1.0          # font size of the visible simulation parameters
RESULTS = os.environ.get('SIM_RESULTS', '/home/claude/robot/kicad/sim/results.json')

def rp(p):
    return (round(p[0], 4), round(p[1], 4))

# ------------------------------------------------------------------ drawing utilities
def new(name, title, c1, c2=''):
    prj = Project(name, design_main.library(), '2026-10-24', 'A', 'ronmart · Caril Ronnie Martínez Vera')
    sh = Sheet(prj, name + '.kicad_sch', title, 1, paper='A4', path='/' + prj.root_uuid,
               comments=(c1, c2, 'ngspice simulation from KiCad 10 (Inspect → Simulator)', ''))
    sh.uuid = prj.root_uuid
    return prj, sh

def _just(prop):
    e = [it for it in prop if isinstance(it, list) and it and it[0] == 'effects'][0]
    j = [it for it in e if isinstance(it, list) and it and it[0] == 'justify']
    return ' '.join(str(s) for s in j[0][1:]) if j else None

def place(sh, lib, ref, value, x, y, rot=0, mirror=None, fields=None, fpos='right', show_params=False):
    inst = sh.place(lib, ref, value, x, y, rot=rot, mirror=mirror, footprint='', fields=fields or {},
                    in_bom=False, on_board=False, fpos=fpos)
    if show_params:
        node = sh.items[-1]
        vprop = [it for it in node if isinstance(it, list) and it[:2] == ['property', 'Value']][0]
        vx, vy = vprop[3][1], vprop[3][2]
        for i, it in enumerate(node):
            if isinstance(it, list) and it[:2] == ['property', 'Sim.Params']:
                node[i] = prop_node('Sim.Params', it[2], vx, round(vy + 2.54, 4), vprop[3][3], hide=False, justify=_just(vprop), size=PF)
    return inst

def pin(inst, p):
    return inst.pin(p)[0]

def R(sh, ref, val, x, y, rot=0):
    return place(sh, 'Device:R', ref, val, x, y, rot=rot, fpos='right' if rot in (0, 180) else 'tb')
def C(sh, ref, val, x, y, rot=0):
    return place(sh, 'Device:C', ref, val, x, y, rot=rot, fpos='right' if rot in (0, 180) else 'tb')
def L(sh, ref, val, x, y, rot=0):
    return place(sh, 'Device:L', ref, val, x, y, rot=rot, fpos='right' if rot in (0, 180) else 'tb')

def source(sh, kind, ref, value, x, y, params, rot=0, fpos='right'):
    """Simulation_SPICE sources: VDC, VPULSE, IDC (pin 1 = +) and BSOURCE (pin 1 = N+). Parameters shown on the sheet."""
    if kind == 'BSOURCE':
        f = {'Sim.Device': 'SPICE', 'Sim.Params': params}
    else:
        dev, typ = {'VDC': ('V', 'DC'), 'VPULSE': ('V', 'PULSE'), 'IDC': ('I', 'DC')}[kind]
        f = {'Sim.Device': dev, 'Sim.Type': typ, 'Sim.Pins': '1=+ 2=-', 'Sim.Params': params}
    return place(sh, 'Simulation_SPICE:' + kind, ref, value, x, y, rot=rot, fields=f, fpos=fpos, show_params=True)

def switch(sh, ref, value, x, y, params, mirror=None, fpos='right'):
    """Voltage-controlled switch: N+ at the top, N− at the bottom; control (C+ top, C− bottom) on the left,
    or on the right with mirror='y'."""
    f = {'Sim.Device': 'SW', 'Sim.Type': 'V', 'Sim.Pins': '1=no+ 2=no- 3=ctrl+ 4=ctrl-', 'Sim.Params': params}
    return place(sh, 'Simulation_SPICE:SWITCH', ref, value, x, y, mirror=mirror, fields=f, fpos=fpos, show_params=True)

def diode(sh, ref, value, x, y, params, k_top=True, lib='Device:D'):
    f = {'Sim.Device': 'D', 'Sim.Pins': '1=K 2=A', 'Sim.Params': params}
    return place(sh, lib, ref, value, x, y, rot=270 if k_top else 90, fields=f, fpos='right', show_params=True)

def gnd(sh, inst, p):
    sh.power('GND', pin(inst, p))

def ctl_label(sh, inst, net, side):
    """Switch C+ pin: 2.54 stub upwards with the label facing outwards; C− to GND."""
    c = pin(inst, '3')
    top = rp((c[0], c[1] - 2.54))
    sh.wire(c, top)
    sh.label(net, top, (-1, 0) if side == 'left' else (1, 0))
    gnd(sh, inst, '4')

def label_up(sh, inst, p, net, length=2.54):
    a = pin(inst, p); b = rp((a[0], a[1] - length))
    sh.wire(a, b); sh.label(net, b, (1, 0))

def pwr_flag(sh, x, y):
    sh.power('PWR_FLAG', (x, y)); sh.wire((x, y), (x, y + 2.54)); sh.power('GND', (x, y + 2.54))

def directives(sh, lines, p):
    sh.text('\n'.join(lines), p, size=1.27)

def notes(sh, text, p):
    sh.text(text, p, size=1.27)

def results(sh, name, p):
    try:
        res = json.load(open(RESULTS)).get(name)
    except Exception:
        res = None
    if res:
        sh.text('RESULTS (ngspice-42, batch run)\n' + '\n'.join(res), p, size=1.27)

def split_wires(sh):
    """Split every wire at the points where another wire ends or a pin or label sits, so that all connections
    are at wire endpoints (as the KiCad editor does)."""
    pts = set()
    for it in sh.items:
        if it[0] == 'wire':
            pts.add(rp((it[1][1][1], it[1][1][2]))); pts.add(rp((it[1][2][1], it[1][2][2])))
        elif it[0] == 'label':
            pts.add(rp((it[2][1], it[2][2])))
    pts |= {rp(p) for p in sh.pin_points}
    out = []
    for it in sh.items:
        if it[0] != 'wire':
            out.append(it); continue
        a = rp((it[1][1][1], it[1][1][2])); b = rp((it[1][2][1], it[1][2][2]))
        inner = sorted((p for p in pts if _on_seg(p, a, b)), key=lambda p: abs(p[0] - a[0]) + abs(p[1] - a[1]))
        if not inner:
            out.append(it); continue
        chain = [a] + inner + [b]
        for u, v in zip(chain, chain[1:]):
            out.append(['wire', ['pts', ['xy', u[0], u[1]], ['xy', v[0], v[1]]], ['stroke', ['width', 0], ['type', Sym('default')]],
                        ['uuid', uid(sh.uuid, 'w', u, v)]])
    sh.items = out

def finish(sh):
    split_wires(sh)
    add_junctions(sh)

# ------------------------------------------------------------------ SIM1: VSYS ripple with motor PWM
def sim1():
    name = 'sim1_vsys_motor_pwm'
    prj, sh = new(name, 'SIM1 — VSYS ripple with motor PWM (20 kHz, 70 %)',
                  '2S battery, VSYS bank and two motors with in-phase PWM (worst case)')
    sh.section('CIRCUIT MODEL', (15.24, 25.4), (205.74, 101.6))
    yr = 43.18
    v1 = source(sh, 'VDC', 'V1', 'BAT 2S', 25.4, 55.88, 'dc=7.4'); gnd(sh, v1, '2')
    r1 = R(sh, 'R1', '0.15', 36.83, yr, rot=90)
    l1 = L(sh, 'L1', '300n', 46.99, yr, rot=90)
    sh.wire(pin(v1, '1'), (25.4, yr), pin(r1, '1'))
    sh.wire(pin(r1, '2'), pin(l1, '1'))
    xm = (129.54, 172.72)
    sh.wire(pin(l1, '2'), (xm[1], yr))
    sh.label('VSYS', (55.88, yr))
    for x, re, ce, esr, cv in ((63.5, 'R2', 'C1', '0.34', '100u'), (76.2, 'R3', 'C2', '3m', '26u'), (88.9, 'R4', 'C3', '10m', '100n')):
        R(sh, re, esr, x, yr + 3.81)
        c = C(sh, ce, cv, x, yr + 11.43); gnd(sh, c, '2')
    i1 = source(sh, 'IDC', 'I1', 'LOGIC', 101.6, yr + 5.08, 'dc=0.35'); gnd(sh, i1, '2')
    for k, xs in enumerate(xm):
        sw = switch(sh, f'S{k+1}', 'TB6612', xs, 55.88, 'thr=1.65 ron=0.5 roff=10Meg')
        sh.wire((xs, yr), pin(sw, '1'))
        ctl_label(sh, sw, 'PWM', 'left')
        n = pin(sw, '2'); ym = round(n[1] + 2.54, 4)
        R(sh, f'R{5+k}', '5', xs, ym + 3.81)
        L(sh, f'L{2+k}', '1.5m', xs, ym + 11.43)
        em = source(sh, 'VDC', f'V{3+k}', 'BEMF', xs, ym + 20.32, 'dc=3'); gnd(sh, em, '2')
        d = diode(sh, f'D{k+1}', 'D', xs + 10.16, ym + 3.81, 'is=1e-9 n=1.5 rs=0.05'); gnd(sh, d, '2')
        sh.wire(n, (xs, ym), pin(d, '1'))
        sh.label('M_LEFT' if k == 0 else 'M_RIGHT', (xs + 1.27, ym))
        sh.text('Left motor' if k == 0 else 'Right motor', (xs - 7.62, 97.79), size=1.27, italic=True)
    sh.text('Battery and wiring', (21.59, 97.79), size=1.27, italic=True)
    sh.text('VSYS bank (Motors sheet)', (60.96, 97.79), size=1.27, italic=True)
    sh.text('Logic (2 bucks)', (97.79, 97.79), size=1.27, italic=True)
    # stimuli
    sh.section('STIMULI', (15.24, 106.68), (101.6, 152.4))
    v2 = source(sh, 'VPULSE', 'V2', 'PWM 20 kHz 70 %', 25.4, 124.46, 'y1=0 y2=3.3 td=0 tr=50n tf=50n tw=35u per=50u')
    label_up(sh, v2, '1', 'PWM'); gnd(sh, v2, '2')
    pwr_flag(sh, 91.44, 121.92)
    # analysis
    sh.section('ANALYSIS', (106.68, 106.68), (281.94, 162.56))
    directives(sh, ['.tran 0.1u 6m 4m 0.1u',
                    '.meas tran vsys_pp PP v(/VSYS) from=4m to=6m',
                    '.meas tran vsys_min MIN v(/VSYS) from=4m to=6m',
                    '.meas tran vsys_avg AVG v(/VSYS) from=4m to=6m',
                    '.meas tran ibat_avg AVG i(V1) from=4m to=6m',
                    '.meas tran imot_avg AVG i(L2) from=4m to=6m'], (109.22, 114.3))
    notes(sh, 'TB6612 modelled as a switch (Ron 0.5 Ω, high + low side) with freewheeling diode; PWM 20 kHz at 70 %,\n'
              'both motors in phase (worst case). R1 = cells + 2×RDS(on) of the protector + fuse + wires; L1 = wiring.\n'
              'C1: 100 µF/50 V electrolytic (ESR 0.34 Ω); C2: 2×22 µF X5R 25 V, ≈ 26 µF under DC bias. Only the bank on\n'
              'the Motors sheet (without the charger and buck capacitors): conservative case.', (109.22, 133.35))
    results(sh, name, (177.8, 114.3))
    finish(sh)
    return prj, sh

# ------------------------------------------------------------------ SIM2: TPS62933 buck (open-loop switching model)
def sim_buck(name, title, vout, cout, rload, duty, iout):
    prj, sh = new(name, title, f'TPS62933 power stage at 1.2 MHz, open loop ({vout} V / {iout} A)')
    sh.section('CIRCUIT MODEL', (15.24, 25.4), (157.48, 101.6))
    yr, xh, ysw = 43.18, 73.66, 66.04
    v1 = source(sh, 'VDC', 'V1', 'VSYS', 25.4, 55.88, 'dc=7.4'); gnd(sh, v1, '2')
    r1 = R(sh, 'R1', '0.05', 36.83, yr, rot=90)
    sh.wire(pin(v1, '1'), (25.4, yr), pin(r1, '1'))
    sh.wire(pin(r1, '2'), (xh, yr))
    sh.label('VIN', (43.18, yr))
    R(sh, 'R2', '3m', 50.8, yr + 3.81)
    c1 = C(sh, 'C1', '13u', 50.8, yr + 11.43); gnd(sh, c1, '2')
    hs = switch(sh, 'S1', 'HS 76 mΩ', xh, 55.88, 'thr=2.5 ron=0.076 roff=1Meg')
    ls = switch(sh, 'S2', 'LS 32 mΩ', xh, 78.74, 'thr=2.5 ron=0.032 roff=1Meg')
    sh.wire((xh, yr), pin(hs, '1'))
    ctl_label(sh, hs, 'GH', 'left'); ctl_label(sh, ls, 'GL', 'left')
    gnd(sh, ls, '2')
    sh.wire(pin(hs, '2'), pin(ls, '1'))
    d1 = diode(sh, 'D1', 'D_LS', 83.82, ysw + 3.81, 'is=1e-9 n=1.5 rs=0.05'); gnd(sh, d1, '2')
    l1 = L(sh, 'L1', '3.3u', 97.79, ysw, rot=90)
    sh.wire((xh, ysw), pin(l1, '1'))
    sh.label('SW', (76.2, ysw))
    r3 = R(sh, 'R3', '0.038', 110.49, ysw, rot=90)
    sh.wire(pin(l1, '2'), pin(r3, '1'))
    sh.wire(pin(r3, '2'), (142.24, ysw))
    sh.label('VOUT', (116.84, ysw))
    R(sh, 'R4', '3m', 127.0, ysw + 3.81)
    c2 = C(sh, 'C2', cout, 127.0, ysw + 11.43); gnd(sh, c2, '2')
    r5 = R(sh, 'R5', rload, 142.24, ysw + 3.81); gnd(sh, r5, '2')
    sh.text('Input (VSYS)', (21.59, 97.79), size=1.27, italic=True)
    sh.text('TPS62933 power stage', (60.96, 97.79), size=1.27, italic=True)
    sh.text('Output and load', (119.38, 97.79), size=1.27, italic=True)
    # stimuli: gate drives with 20 ns dead time
    per = 1 / 1.2e6; ton = duty * per
    sh.section('STIMULI', (15.24, 106.68), (101.6, 162.56))
    g1 = source(sh, 'VPULSE', 'V2', 'GH 1.2 MHz', 25.4, 124.46, f'y1=0 y2=5 td=0 tr=5n tf=5n tw={ton*1e9:.0f}n per={per*1e9:.1f}n')
    label_up(sh, g1, '1', 'GH'); gnd(sh, g1, '2')
    g2 = source(sh, 'VPULSE', 'V3', 'GL 1.2 MHz', 25.4, 147.32,
                f'y1=0 y2=5 td={ton*1e9+20:.0f}n tr=5n tf=5n tw={(per-ton)*1e9-40:.0f}n per={per*1e9:.1f}n')
    label_up(sh, g2, '1', 'GL'); gnd(sh, g2, '2')
    pwr_flag(sh, 91.44, 121.92)
    sh.section('ANALYSIS', (106.68, 106.68), (281.94, 162.56))
    directives(sh, ['.tran 2n 1m 0.95m 2n',
                    '.meas tran vout_avg AVG v(/VOUT) from=0.95m to=1m',
                    '.meas tran vout_pp PP v(/VOUT) from=0.95m to=1m',
                    '.meas tran il_avg AVG i(L1) from=0.95m to=1m',
                    '.meas tran il_pp PP i(L1) from=0.95m to=1m',
                    '.meas tran il_max MAX i(L1) from=0.95m to=1m',
                    '.meas tran vin_pp PP v(/VIN) from=0.95m to=1m'], (109.22, 114.3))
    dc = f'{duty*100:.1f}'
    rl = rload
    notes(sh, f'TPS62933 with RT to GND (1.2 MHz): RDS(on) 76 mΩ / 32 mΩ, 20 ns dead time with the low-side MOSFET\n'
              f'body diode. L1 = SRP5030T-3R3M (3.3 µH, DCR 38 mΩ). C2 = 2×22 µF X5R 10 V, ≈ {cout[:-1]} µF under DC bias, ESR 3 mΩ.\n'
              f'Load {rl} Ω ({iout} A). Open loop with a fixed {dc} % duty cycle: shows ripple and inductor current,\n'
              f'not the control-loop response.', (109.22, 135.89))
    results(sh, name, (177.8, 114.3))
    finish(sh)
    return prj, sh

# ------------------------------------------------------------------ SIM3: power-up sequence
def sim3():
    name = 'sim3_power_up'
    prj, sh = new(name, 'SIM3 — Power-up: UVLO, soft start and ESP32-S3 EN',
                  'VSYS = 7.4 V present; SW301 releases PWR_EN at t = 1 ms')
    sh.section('CIRCUIT MODEL', (15.24, 25.4), (184.15, 104.14))
    yr = 43.18
    v1 = source(sh, 'VDC', 'V1', 'VSYS', 25.4, 55.88, 'dc=7.4'); gnd(sh, v1, '2')
    r1 = R(sh, 'R1', '86.6k', 45.72, yr + 3.81)
    r2 = R(sh, 'R2', '23.2k', 45.72, 59.69); gnd(sh, r2, '2')
    sh.wire(pin(v1, '1'), (25.4, yr), pin(r1, '1'))
    sh.label('VSYS', (30.48, yr))
    sw = switch(sh, 'S1', 'SW301', 66.04, 58.42, 'thr=1.65 ron=0.1 roff=100Meg', mirror='y')
    sh.wire(pin(r1, '2'), pin(r2, '1'))
    sh.wire((45.72, 53.34), pin(sw, '1'))
    sh.label('PWR_EN', (48.26, 53.34))
    gnd(sh, sw, '2')
    ctl_label(sh, sw, 'SW301', 'right')
    sh.text('UVLO divider + SW301 (OFF = PWR_EN to GND)', (21.59, 72.39), size=1.27, italic=True)
    # soft start
    yss = 78.74
    c1 = C(sh, 'C1', '33n', 25.4, yss + 3.81); gnd(sh, c1, '2')
    b1 = source(sh, 'BSOURCE', 'B1', 'ISS 5.5 µA', 38.1, yss + 5.08, 'type="B" model="I=V(/PWR_EN)>1.21 ? 5.5u : 0"', rot=180)
    sh.wire(pin(c1, '1'), pin(b1, '2'))
    gnd(sh, b1, '1')
    sh.label('SS', (27.94, yss))
    # 3.3 V buck (controlled source) + load + ESP32-S3 EN RC
    xe, xl, xb = 104.14, 116.84, 127.0
    b2 = source(sh, 'BSOURCE', 'B2', 'BUCK 3V3', xb, yss + 5.08, 'type="B" model="V=3.328*min(V(/SS)/0.8,1)"')
    gnd(sh, b2, '2')
    r4 = R(sh, 'R4', '10k', xe, yss + 3.81)
    c2 = C(sh, 'C2', '1u', xe, yss + 11.43); gnd(sh, c2, '2')
    r3 = R(sh, 'R3', '33', xl, yss + 3.81); gnd(sh, r3, '2')
    sh.wire(pin(b2, '1'), (xe, yss))
    sh.label('3V3', (106.68, yss))
    en = pin(r4, '2')
    sh.wire(en, (xe - 7.62, en[1]))
    sh.label('EN_ESP', (xe - 7.62, en[1]), (-1, 0))
    sh.text('TPS62933 soft start', (21.59, 100.33), size=1.27, italic=True)
    sh.text('3.3 V buck, 100 mA load and ESP32-S3 EN RC', (97.79, 100.33), size=1.27, italic=True)
    sh.section('STIMULI', (15.24, 109.22), (101.6, 152.4))
    v2 = source(sh, 'VPULSE', 'V2', 'SW301 → ON', 25.4, 127.0, 'y1=3.3 y2=0 td=1m tr=1u tf=1u tw=1 per=2')
    label_up(sh, v2, '1', 'SW301'); gnd(sh, v2, '2')
    pwr_flag(sh, 91.44, 124.46)
    sh.section('ANALYSIS', (106.68, 109.22), (281.94, 162.56))
    directives(sh, ['.tran 10u 30m',
                    '.meas tran t_en WHEN v(/PWR_EN)=1.21 RISE=1',
                    '.meas tran t_3v3 WHEN v(/3V3)=2.97 RISE=1',
                    '.meas tran t_esp WHEN v(/EN_ESP)=2.475 RISE=1',
                    '.meas tran v3v3_esp FIND v(/3V3) WHEN v(/EN_ESP)=2.475 RISE=1',
                    ".meas tran margin param='t_esp-t_3v3'"], (109.22, 116.84))
    notes(sh, 'UVLO 86.6k/23.2k: PWR_EN = 1.56 V at VSYS = 7.4 V (EN rises at 1.21 V → start-up at VSYS ≈ 5.6 V, max. 5.94 V).\n'
              'Soft start: ISS 5.5 µA into Css 33 nF → 4.8 ms to VREF = 0.8 V. The buck is modelled as a source that follows\n'
              'V(SS)/0.8 (100 mA load). ESP32-S3 EN: RC 10 kΩ / 1 µF; it must cross 0.75·VDD with 3V3 already stable.', (109.22, 135.89))
    results(sh, name, (190.5, 116.84))
    finish(sh)
    return prj, sh

# ------------------------------------------------------------------ SIM4: cliff sensor
def sim4():
    name = 'sim4_cliff_sensor'
    prj, sh = new(name, 'SIM4 — TCRT5000L cliff sensor: IR pulse and ADC reading',
                  'Table (CTR 5 %) vs. cliff (CTR 0.05 %); 50 µA ambient light (worst case)')
    sh.section('CIRCUIT MODEL', (15.24, 25.4), (281.94, 101.6))
    # IR LED with its resistor and Q601
    r1 = R(sh, 'R1', '180', 25.4, 46.99)
    label_up(sh, r1, '1', '5V')
    d1 = diode(sh, 'D1', 'IR LED', 25.4, 58.42, 'is=2.5p n=1.8 rs=5', k_top=False, lib='Device:LED')
    sh.wire(pin(r1, '2'), pin(d1, '2'))
    sh.label('LED_A', (25.4, 52.07))
    s1 = switch(sh, 'S1', 'Q601', 25.4, 74.93, 'thr=1.65 ron=0.05 roff=10Meg', mirror='y')
    sh.wire(pin(d1, '1'), pin(s1, '1'))
    gnd(sh, s1, '2')
    ctl_label(sh, s1, 'IR_EN', 'right')
    sh.text('IR emitter and Q601', (19.05, 97.79), size=1.27, italic=True)
    # optical model: I_LED (1 V/A) → 15 µs delay → PH
    b1 = source(sh, 'BSOURCE', 'B1', 'I_LED (1 V/A)', 55.88, 58.42, 'type="B" model="V=(V(/5V)-V(/LED_A))/180"')
    gnd(sh, b1, '2')
    r2 = R(sh, 'R2', '1k', 64.77, 45.72, rot=90)
    sh.wire(pin(b1, '1'), (55.88, 45.72), pin(r2, '1'))
    sh.label('ILED', (55.88, 45.72))
    c1 = C(sh, 'C1', '15n', 76.2, 49.53); gnd(sh, c1, '2')
    sh.wire(pin(r2, '2'), pin(c1, '1'))
    sh.label('PH', (69.85, 45.72))
    sh.text('Optical coupling (τ = 15 µs)', (50.8, 97.79), size=1.27, italic=True)
    x0 = 185.42
    for k, (ctr, tag, yc, title) in enumerate(((0.05, 'TABLE', 48.26, 'Over the table (CTR 5 %)'),
                                              (0.0005, 'CLIFF', 76.2, 'Over the cliff (CTR 0.05 %)'))):
        rp_ = place(sh, 'Device:R', f'R{3+2*k}', '10k', x0, yc - 3.81, fpos='left')
        label_up(sh, rp_, '1', '3V3')
        b = source(sh, 'BSOURCE', f'B{2+k}', 'PHOTOTRANSISTOR', x0, yc + 5.08,
                   f'type="B" model="I=min({ctr}*V(/PH)+50u,V(/C_{tag})/100)"', fpos='left')
        gnd(sh, b, '2')
        rs = R(sh, f'R{4+2*k}', '1k', x0 + 16.51, yc, rot=90)
        sh.wire(pin(b, '1'), pin(rs, '1'))
        sh.label(f'C_{tag}', (x0 + 2.54, yc))
        ca = C(sh, f'C{2+k}', '2.2n', x0 + 25.4, yc + 3.81); gnd(sh, ca, '2')
        sh.wire(pin(rs, '2'), (x0 + 27.94, yc))
        sh.label(f'ADC_{tag}', (x0 + 27.94, yc))
        sh.text(title, (x0 + 43.18, yc), size=1.27, italic=True)
    sh.section('STIMULI', (15.24, 106.68), (149.86, 152.4))
    for ref, val, x, params, net in (('V1', '5V', 25.4, 'dc=5', '5V'), ('V2', '3V3', 55.88, 'dc=3.3', '3V3')):
        v = source(sh, 'VDC', ref, val, x, 124.46, params); label_up(sh, v, '1', net); gnd(sh, v, '2')
    v3 = source(sh, 'VPULSE', 'V3', 'IR_EN', 86.36, 124.46, 'y1=0 y2=3.3 td=100u tr=100n tf=100n tw=300u per=1m')
    label_up(sh, v3, '1', 'IR_EN'); gnd(sh, v3, '2')
    pwr_flag(sh, 139.7, 137.16)
    sh.section('ANALYSIS', (154.94, 106.68), (281.94, 162.56))
    directives(sh, ['.tran 0.2u 1.2m',
                    '.meas tran iled MAX v(/ILED)',
                    '.meas tran table_on FIND v(/ADC_TABLE) AT=350u',
                    '.meas tran cliff_on FIND v(/ADC_CLIFF) AT=350u',
                    '.meas tran table_off FIND v(/ADC_TABLE) AT=950u',
                    '.meas tran cliff_off FIND v(/ADC_CLIFF) AT=950u',
                    '.meas tran t_low WHEN v(/ADC_TABLE)=0.3 FALL=1'], (157.48, 114.3))
    notes(sh, 'Phototransistor: I = CTR·I_LED (τ = 15 µs) + 50 µA ambient\n'
              'light; saturation modelled with 100 Ω. 10 kΩ pull-up to\n'
              '3.3 V and 1 kΩ / 2.2 nF filter into the ESP32-S3 ADC1.', (157.48, 137.16))
    results(sh, name, (157.48, 146.05))
    finish(sh)
    return prj, sh

# ------------------------------------------------------------------ SIM5: USB-C / dock hot plug
def sim5():
    name = 'sim5_hot_plug'
    prj, sh = new(name, 'SIM5 — Hot plug: LM66200 VIN',
                  '1 m USB-C cable (0.15 Ω, 1 µH); LM66200 VIN abs. max. = 6 V')
    sh.section('CIRCUIT MODEL', (15.24, 25.4), (254.0, 104.14))
    yn = 68.58
    chans = ((30.48, 'NOPROT', 'No protection'), (81.28, 'TVS', 'TVS SMF5.0A only'), (165.1, 'RC', 'TVS + RC 1 Ω / 10 µF (design)'))
    for k, (x0, tag, title) in enumerate(chans):
        n = k + 1
        sw = switch(sh, f'S{n}', 'PLUG-IN', x0, 48.26, 'thr=1.65 ron=0.01 roff=100Meg')
        label_up(sh, sw, '1', 'VCHARGER')
        ctl_label(sh, sw, 'PLUG', 'left')
        rc_ = R(sh, f'R{n}', '0.15', x0, 57.15)
        lc_ = place(sh, 'Device:L', f'L{n}', '1u', x0, 64.77, fpos='left')
        x_end = x0 + {0: 20.32, 1: 30.48, 2: 40.64}[k]
        sh.wire(pin(lc_, '2'), (x_end, yn))
        sh.label(f'VIN_{tag}', (x0 + 1.27, yn))
        c = C(sh, f'C{n}', '0.85u', x0 + 10.16, yn + 3.81); gnd(sh, c, '2')
        rq = R(sh, f'R{10+n}', '100k', x0 + 20.32, yn + 3.81); gnd(sh, rq, '2')
        if k >= 1:
            d = diode(sh, f'D{n}', 'SMF5.0A', x0 + (30.48 if k == 1 else 40.64), yn + 3.81, 'is=1e-12 n=1 rs=0.1 bv=7.07 ibv=10m',
                      lib='Device:D_Zener')
            gnd(sh, d, '2')
        if k == 2:
            R(sh, 'R20', '1', x0 + 30.48, yn + 3.81)
            cs = C(sh, 'C20', '8.5u', x0 + 30.48, yn + 11.43); gnd(sh, cs, '2')
        sh.text(title, (x0 - 7.62, 97.79), size=1.27, italic=True)
    sh.text('Cable: R1–R3 and L1–L3. C1–C3 = C201 (1 µF/25 V,\n≈ 0.85 µF under DC bias). R11–R13: quiescent load.\n'
            'D2, D3: SMF5.0A at max. VBR (7.07 V, worst case).\nC20: CL31A106KAHNNNE at 5 V ≈ 8.5 µF.', (21.59, 85.09), size=1.27)
    sh.section('STIMULI', (15.24, 109.22), (101.6, 152.4))
    v1 = source(sh, 'VDC', 'V1', 'CHARGER 5 V', 25.4, 127.0, 'dc=5'); label_up(sh, v1, '1', 'VCHARGER'); gnd(sh, v1, '2')
    v2 = source(sh, 'VPULSE', 'V2', 'PLUG', 55.88, 127.0, 'y1=0 y2=3.3 td=10u tr=1n tf=1n tw=1 per=2')
    label_up(sh, v2, '1', 'PLUG'); gnd(sh, v2, '2')
    pwr_flag(sh, 91.44, 142.24)
    sh.section('ANALYSIS', (106.68, 109.22), (281.94, 162.56))
    directives(sh, ['.tran 2n 60u',
                    '.meas tran peak_noprot MAX v(/VIN_NOPROT)',
                    '.meas tran peak_tvs MAX v(/VIN_TVS)',
                    '.meas tran peak_rc MAX v(/VIN_RC)',
                    '.meas tran final_rc FIND v(/VIN_RC) AT=58u'], (109.22, 116.84))
    notes(sh, 'On plug-in, the cable inductance and the ceramic input capacitor resonate and the voltage can almost\n'
              'double. The TVS only clamps above its VBR (6.4–7.07 V): not enough for the 6 V limit of the LM66200.\n'
              'The 1 Ω + 10 µF RC damps the resonance (Q < 1) and keeps VIN below 5.5 V.', (109.22, 135.89))
    results(sh, name, (109.22, 146.05))
    finish(sh)
    return prj, sh

def write(prj, sh, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    node = sh.node(prj.lib.lib_symbols_node(sh.lib_ids), [['sheet_instances', ['path', '/', ['page', '1']]]])
    open(os.path.join(out_dir, sh.filename), 'w', encoding='utf-8').write(fmt(node) + '\n')

SIMS = [sim1,
        lambda: sim_buck('sim2a_buck_3v3', 'SIM2a — 3.3 V / 1 A buck: ripple and inductor current', '3.3', '24u', '3.3', 0.457, '1'),
        lambda: sim_buck('sim2b_buck_5v', 'SIM2b — 5 V / 1.4 A buck: ripple and inductor current', '5', '18u', '3.6', 0.698, '1.4'),
        sim3, sim4, sim5]

if __name__ == '__main__':
    base = sys.argv[1] if len(sys.argv) > 1 else '/home/claude/robot/kicad/sim'
    for f in SIMS:
        prj, sh = f()
        write(prj, sh, os.path.join(base, prj.name))
        print('ok', prj.name)
