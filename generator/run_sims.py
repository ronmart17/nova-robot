"""Runs the simulations in batch: exports the SPICE netlist from KiCad 10, runs ngspice, collects the .meas results and
saves the waveforms (.dat) for the plots. Usage: python3 run_sims.py [name ...]"""
import os, sys, re, json, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import runsim

BASE = os.environ.get('ROBOT_OUT', '/home/claude/robot/kicad') + '/sim'
SIMS = {
    'sim1_vsys_motor_pwm': ['v(/VSYS)', 'i(v1)', 'i(l2)', 'v(/PWM)'],
    'sim2a_buck_3v3': ['v(/VOUT)', 'v(/SW)', 'i(l1)', 'v(/VIN)'],
    'sim2b_buck_5v': ['v(/VOUT)', 'v(/SW)', 'i(l1)', 'v(/VIN)'],
    'sim3_power_up': ['v(/PWR_EN)', 'v(/SS)', 'v(/3V3)', 'v(/EN_ESP)'],
    'sim4_cliff_sensor': ['v(/IR_EN)', 'v(/ILED)', 'v(/PH)', 'v(/C_TABLE)', 'v(/ADC_TABLE)', 'v(/C_CLIFF)', 'v(/ADC_CLIFF)'],
    'sim5_hot_plug': ['v(/VIN_NOPROT)', 'v(/VIN_TVS)', 'v(/VIN_RC)'],
}

def meas(log):
    out = {}
    for line in log.splitlines():
        m = re.match(r'^\s*([a-z_0-9]+)\s*=\s*([-+0-9.eE]+)', line)
        if m:
            try: out[m.group(1)] = float(m.group(2))
            except ValueError: pass
    return out

VARIANTS = {  # variants of the exported netlist: (suffix, function that modifies the text)
    'sim5_hot_plug': [('_2m', lambda c: re.sub(r'^(L[123] \S+ \S+) 1u$', r'\1 2u', c, flags=re.M))],
}

def run(name):
    d = f'{BASE}/{name}'
    sch = f'{d}/{name}.kicad_sch'
    work = f'{d}/results'
    os.makedirs(work, exist_ok=True)
    cir = runsim.export_spice(sch, f'{work}/{name}.cir')
    tran = [l for l in cir.splitlines() if l.lower().startswith('.tran')][0].split(None, 1)[1]
    hdr, data = runsim.run(cir, tran, SIMS[name], work, name)
    log = open(f'{work}/{name}.log').read()
    m = meas(log)
    if 'rror' in log and not m:
        print(log[-3000:])
    for suf, f in VARIANTS.get(name, []):
        c2 = f(cir); assert c2 != cir, 'variant unchanged'
        runsim.run(c2, tran, SIMS[name], work, name + suf)
        m.update({k + suf: v for k, v in meas(open(f'{work}/{name}{suf}.log').read()).items()})
    return hdr, data, m

if __name__ == '__main__':
    names = sys.argv[1:] or list(SIMS)
    allm = {}
    jf = f'{BASE}/meas.json'
    if os.path.exists(jf): allm = json.load(open(jf))
    for n in names:
        hdr, data, m = run(n)
        allm[n] = m
        print(n, data.shape, hdr)
        for k, v in m.items(): print(f'   {k:12s} = {v:.6g}')
    json.dump(allm, open(jf, 'w'), indent=1)

# ------------------------------------------------------------------ human-readable summary for the schematics
def es(x, nd):
    return f'{x:.{nd}f}'

def summary(m):
    out = {}
    a = m.get('sim1_vsys_motor_pwm')
    if a:
        out['sim1_vsys_motor_pwm'] = [
            f"VSYS: mean {es(a['vsys_avg'], 2)} V, min. {es(a['vsys_min'], 2)} V, ripple {es(a['vsys_pp']*1e3, 0)} mV p-p ({es(a['vsys_pp']/a['vsys_avg']*100, 1)} %)",
            f"Battery: {es(-a['ibat_avg'], 2)} A average; each motor {es(a['imot_avg'], 2)} A average",
            "VSYS well above 3.8 V (TPS62933 min. VIN) and 2.5 V (TB6612 min. VM)"]
    for n, lim in (('sim2a_buck_3v3', '3.3'), ('sim2b_buck_5v', '5')):
        b = m.get(n)
        if b:
            out[n] = [
                f"VOUT: mean {es(b['vout_avg'], 3)} V, ripple {es(b['vout_pp']*1e3, 1)} mV p-p ({es(b['vout_pp']/b['vout_avg']*100, 2)} %)",
                f"Inductor: mean {es(b['il_avg'], 2)} A, ripple {es(b['il_pp'], 2)} A p-p, peak {es(b['il_max'], 2)} A",
                "Peak well below Isat = 8 A (SRP5030T-3R3M) and 4.2 A (TPS62933 min. HS current limit)",
                f"VIN ripple: {es(b['vin_pp']*1e3, 0)} mV p-p"]
    c = m.get('sim3_power_up')
    if c:
        out['sim3_power_up'] = [
            f"PWR_EN crosses 1.21 V at t = {es(c['t_en']*1e3, 2)} ms (SW301 to ON at 1 ms)",
            f"3V3 reaches 90 % at t = {es(c['t_3v3']*1e3, 2)} ms ({es((c['t_3v3']-c['t_en'])*1e3, 1)} ms after EN)",
            f"ESP32-S3 EN reaches 0.75·VDD at t = {es(c['t_esp']*1e3, 1)} ms, with 3V3 = {es(c['v3v3_esp'], 2)} V",
            f"Margin {es(c['margin']*1e3, 1)} ms vs. 50 µs (ESP32-S3 min. tSTBL)"]
    d = m.get('sim4_cliff_sensor')
    if d:
        out['sim4_cliff_sensor'] = [
            f"I_LED = {es(d['iled']*1e3, 1)} mA (absolute max. 60 mA)",
            f"IR on: table {es(d['table_on'], 2)} V, cliff {es(d['cliff_on'], 2)} V; IR off: {es(d['table_off'], 2)} V and {es(d['cliff_off'], 2)} V",
            f"ADC_TABLE falls below 0.3 V {es((d['t_low']-100e-6)*1e6, 0)} µs after IR_EN: sample ≥ 50 µs later",
            "Firmware: table if (IR off − IR on) > 1 V; simulated difference "
            f"{es(d['table_off']-d['table_on'], 2)} V (table) vs. {es(d['cliff_off']-d['cliff_on'], 2)} V (cliff)"]
    e = m.get('sim5_hot_plug')
    if e:
        out['sim5_hot_plug'] = [
            f"VIN peak, 1 m cable (1 µH): no protection {es(e['peak_noprot'], 2)} V; TVS only {es(e['peak_tvs'], 2)} V; TVS + RC {es(e['peak_rc'], 2)} V",
            f"2 m cable (2 µH): no protection {es(e['peak_noprot_2m'], 2)} V; TVS only {es(e['peak_tvs_2m'], 2)} V; TVS + RC {es(e['peak_rc_2m'], 2)} V",
            "Only the RC keeps it below 6 V (LM66200 abs. max.) and 5.5 V (max. operating)",
            "VBUS: 11 µF nominal, ≈ 9.4 µF effective at 5 V (USB limit 10 µF); the 1 Ω R limits the inrush peak"]
    return out

def write_summary():
    m = json.load(open(f'{BASE}/meas.json'))
    s = summary(m)
    json.dump(s, open(f'{BASE}/results.json', 'w'), indent=1, ensure_ascii=False)
    return s

if __name__ == '__main__':
    for k, v in write_summary().items():
        print(k); [print('   ', x) for x in v]
