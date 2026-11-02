"""Builds docs/NOVA_RevB_simulations.md and .pdf from out/spice_results.json, out/system_results.json and the plots."""
import os, json, subprocess, tempfile
ROOT = '/home/claude/robot'
SIM = f'{ROOT}/sim'
O = f'{SIM}/out'
MD = f'{ROOT}/docs/NOVA_RevB_simulations.md'
PDF = f'{ROOT}/docs/NOVA_RevB_simulations.pdf'
S = json.load(open(f'{O}/spice_results.json'))
Y = json.load(open(f'{O}/system_results.json'))
A, B, Cr, D, E, F, Gt, H, I = (Y[k] for k in ('A_stability', 'B_drive', 'C_runtime', 'D_charging', 'E_pogo', 'F_protection',
                                               'G_thermal', 'H_docking', 'I_apriltag'))
s1, s2, s3, s4, s5, s6, s7, s8 = (S[k] for k in ('s1', 's2', 's3', 's4', 's5', 's6', 's7', 's8'))
f1 = lambda v: f'{v:.1f}'; f2 = lambda v: f'{v:.2f}'; f0 = lambda v: f'{v:.0f}'
pct = lambda v: f'{v * 100:.0f} %'

def img(name, cap):
    return f'\n<figure><img src="plots/{name}.png"><figcaption>{cap}</figcaption></figure>\n'

hb = H['B: last fix at 0.12 m, turn at 134 mm, reverse 62 mm']; ha = H['A: align at 0.40 m, turn there, reverse 0.40 m']
hu = H['B without gyro/camera calibration']; hc = H['A with an 8 mm tongue chamfer']
th = lambda k: Gt[k]
md = f'''# NOVA — Rev B: simulations and system analyses

Date: 2026-10-29 · ngspice 42 (batch) · Python 3 (numpy) · CadQuery mass properties · ronmart · Caril Ronnie Martínez Vera

Everything in Rev B that can be checked without hardware was simulated: power rails, transients at the connectors,
signal edges, and the robot as a system (stability, drive, energy, charging, heat, docking). Every model lists its
inputs and their source in the scripts (`sim/spice_sims.py`, `sim/system_sims.py`, `sim/mass_props.py`): datasheet values
where they exist, CAD for geometry and masses of printed parts, and marked estimates (“est.”) for the rest.

## 1. Summary

| # | Check | Result | Limit | Verdict |
|---|---|---|---|---|
| S1 | VSYS ripple, both motors PWM + Pi 3 A | {f0(s1['a']['vpp'] * 1e3)} mV p-p driving, {f0(s1['a']['vpp_st'] * 1e3)} mV at stall; min {f2(s1['low']['vmin'])} V at 6.6 V battery | TPS566238 / TPS62933 inputs ≥ 3 V | OK |
| S2 | +5V (Pi 5) load step 1 → 3 A | min {f2(s2['a']['vpimin'])} V at the Pi, {f2(s2['a']['vpi1'])} V steady at 3 A; ripple {f1(s2['a']['vpp1'] * 1e3)} mV p-p | Pi 5 under-voltage ≈ 4.63 V | OK (270 mV margin) |
| S2 | +5V extreme step 0.5 → 5 A, 2 A/µs, battery 6.6 V | min {f2(s2['d']['vpimin'])} V for ≈ 10 µs; {f2(s2['d']['vpi1'])} V steady; overshoot {f2(s2['d']['vmax'])} V; L301 peak {f1(s2['d']['ilmax'])} A | 4.63 V; Isat 11 A; valley limit ≥ 6.1 A | Marginal (option: 5.22 V) |
| S3 | +3V3 step 0.1 → 0.6 A | {f2(s3['vmin'])} … {f2(s3['vmax'])} V, ripple {f1(s3['vpp'] * 1e3)} mV | 3.0–3.6 V | OK |
| S4 | Power-up sequence | +3V3 at {f1(s4['t33'] * 1e3)} ms, +5V at {f1(s4['t5'] * 1e3)} ms, ESP32 EN at {f1(s4['tpu'] * 1e3)} ms | EN after the supply is stable | OK |
| S5 | Dock: adapter plug-in / robot docks on a live dock / reversed adapter | VAC2 peak {f1(s5['plug']['vmax'])} V / {f1(s5['dock']['vmax'])} V / blocked (0 V) | VAC2 abs. max 30 V | OK |
| S6 | USB-C hot plug | VBUS peak {f1(s6['with_U201']['vmax'])} V (U201 clamps {f2(s6['with_U201']['iu'])} A); VBUS_DET {f2(s6['with_U201']['vdet'])} V | BQ25798 30 V; TCA9535 6 V | OK (option: RC damper → {f1(s6['damper']['vmax'])} V) |
| S7 | I2C rise time (2.2 kΩ, {f0(s7['cbus_pF'])} pF estimated from the layout) | {f0(s7['2.2k_111p']['tr_ns'])} ns; {f0(s7['2.2k_166p']['tr_ns'])} ns at +50 % C | ≤ 300 ns (400 kHz) | OK, measure at bring-up |
| S8 | Display SCLK 40 MHz over the head cable | {f2(s8['33R_drv2']['vmax'])} V / {f2(s8['33R_drv2']['vmin'])} V (drive 2); {f2(s8['33R_drv1']['vmax'])} / {f2(s8['33R_drv1']['vmin'])} V (drive 1) | ±0.3 V beyond the rails | Firmware: drive strength 1 |
| A | Static stability (CAD mass {f0(A['mass_g'])} g) | CoG {f1(A['cg_mm'][1])} mm ahead of the axle at {f0(A['cg_mm'][2])} mm height → tips back at {f2(A['a_tip_ms2'])} m/s² | — | **Action** |
| B | Drive (N20 6 V, Ø43 wheels) | 1:100 → {f2(B['100']['v_max_ms'])} m/s, stall force {f1(B['100']['F_stall_N'])} N (≫ tip limit) | TB6612 1.2 A cont. | OK with acceleration limit |
| C | Runtime (44 Wh) | idle {f1(Cr['Idle, listening']['runtime_h'])} h · conversation {f1(Cr['Conversation (cloud AI)']['runtime_h'])} h · vision + drive {f1(Cr['Vision + driving']['runtime_h'])} h · full {f1(Cr['Full load (local AI)']['runtime_h'])} h · standby {f0(Cr['Pi off (standby)']['runtime_h'] / 24)} days | — | — |
| D | Charging 10 → 80 % | dock 2.5 A: {f1(D['Dock, IINDPM 2.5 A, Pi idle']['t_10_80_h'])} h · dock 1.8 A: {f1(D['Dock, IINDPM 1.8 A, Pi idle']['t_10_80_h'])} h · USB-C 5 V 3 A: {f1(D['USB-C 5 V 3 A source, Pi idle']['t_10_80_h'])} h (Pi idle) | — | USB-C is a backup input |
| E | Pogo-pin current sharing | at 2.5 A: P(one pin > 1.5 A) = {pct(E['2.5A']['p_over_1A5'])}; at 1.8 A: {pct(E['1.8A']['p_over_1A5'])} | 1.5 A per pin (datasheet) | **Action: IINDPM ≤ 1.8 A** |
| F | Battery protector / fuse | worst load {f1(F['worst_A'])} A, realistic {f1(F['realistic_A'])} A vs. trip ≥ {f1(F['oc_trip_A']['min'])} A (12 ms) | fuse 10 A | OK |
| G | Thermal (Pi 5 SoC inside the shell, 25 °C room) | conversation {f0(th('conversation @ 25 °C')['T_soc'])} °C · full load {f0(th('full load @ 25 °C')['T_soc'])} °C | soft throttling 80 °C | Marginal at sustained full load |
| H | Docking first-try success | as written in the design: {pct(ha['success'])} · recommended procedure: {pct(hb['success'])} | capture ±6.5 mm | **Action: procedure** |
| I | AprilTag (40 mm) range, 1536 px stream | detection ≈ {f1(I['1536px']['d_max_detect_m'])} m, good pose ≤ {f2(I['1536px']['d_max_pose_m'])} m, closest 0.10 m | — | OK |

### Findings that need a decision

The design files were not changed, except the pogo-pin text in the dock BOM (finding 2).

1. **Tip-back margin is small (A).** The centre of gravity is only {f1(A['cg_mm'][1])} mm in front of the wheel axle
   (5–95 % range with the mass estimates: {f1(A['cg_y_p05'])}–{f1(A['cg_y_p95'])} mm) and {f0(A['cg_mm'][2])} mm high. The
   caster carries ≈ {f0(A['caster_load_g'])} g. Any acceleration above **{f2(A['a_tip_ms2'])} m/s²** forwards (or braking
   while reversing onto the dock) lifts the caster and rocks the robot back {f1(A['rock_back_deg'])}° onto the rear skirt; a
   {f1(A['touch_tip_N'])} N push on the rear of the top does the same. Options: (a) firmware only — limit acceleration and
   braking to ≤ 0.4 m/s² with a jerk-limited ramp (enough for a desk robot: 0.25 m/s in 0.6 s); (b) **100 g of ballast**
   under the front of the main board (next to the caster) → CoG {f1(A['ballast100']['cg_y'])} mm, limit
   {f2(A['ballast100']['a_tip'])} m/s²; (c) two small rear glides on the skirt at |X| ≈ 55 mm (outside the dock base),
   1–1.5 mm above the floor, which cap the rock at ≈ 1.4°. Recommended: (a) always, plus (b) or (c). Check at the first
   assembly by weighing the caster load (≈ {f0(A['caster_load_g'])} g expected).
2. **Pogo pins (E).** The YTC1P-8020 datasheet gives 1.5 A max and ≤ 100 mΩ per pin. With two pins per polarity and
   2.5 A, unequal contact resistance puts more than 1.5 A on one pin in {pct(E['2.5A']['p_over_1A5'])} of the cases (worst
   {f2(E['2.5A']['i_worst'])} A). **Set the BQ25798 VAC2 input current limit to 1.8 A** (worst {f2(E['1.8A']['i_worst'])} A per
   pin): dock charging 10 → 80 % takes {f1(D['Dock, IINDPM 1.8 A, Pi idle']['t_10_80_h'])} h with the Pi idle
   ({f1(D['Dock, IINDPM 1.8 A, Pi off']['t_10_80_h'])} h with the Pi off) instead of {f1(D['Dock, IINDPM 2.5 A, Pi idle']['t_10_80_h'])} h.
   A hardware alternative for a later revision: three pins per polarity or 3 A pins. The BOM description of the pogo pins
   was corrected to 1.5 A / 100 mΩ.
3. **Docking procedure (H).** “See the tag, turn 180°, reverse” from 0.40 m succeeds at the first try in
   {pct(ha['success'])} of the runs (σ {f0(ha['sigma_e_mm'])} mm at the opening): the heading error is multiplied by the
   reverse distance. Recommended procedure: track the tag until the camera is 0.12 m from it, drive on to a turn point
   134 mm from the dock wall (the closest point where the shell clears the tongue while turning), turn 180° with the gyro,
   reverse 62 mm until VAC2 is detected. First try {pct(hb['success'])}; without gyro scale and camera-yaw calibration
   {pct(hu['success'])}. Retry automatically when VAC2 is not detected (three tries: > 99.9 %). A larger tongue chamfer
   (8 mm) alone only brings the 0.40 m procedure to {pct(hc['success'])}.
4. **Heat at sustained full load (G).** With ≈ 7.5 W on the Pi 5 (all cores busy, camera on) the SoC reaches
   ≈ {f0(th('full load @ 25 °C')['T_soc'])} °C in a 25 °C room (soft throttling starts at 80 °C) because the air inside the shell
   sits ≈ {f0(th('full load @ 25 °C')['T_internal'] - 25)} K above the room. Conversation with a cloud AI (≈ 4.5 W) stays at
   ≈ {f0(th('conversation @ 25 °C')['T_soc'])} °C. Doubling the gills and adding a low inlet gains only ≈
   {f0(th('full load @ 25 °C')['T_soc'] - th('full load @ 25 °C')['T_soc_improved'])} K, since most of the rise is the
   Active Cooler itself. Practical rule: heavy AI in the cloud, or accept throttling during long local inference. Docked
   and charging in a 35 °C room the air inside reaches ≈ {f0(th('docked + charging, idle @ 35 °C')['T_internal'])} °C: the
   BQ25798 JEITA “warm” range will reduce the charge (NTC on TS).
5. **Pi 5 rail at extreme load (S2).** At a realistic 1 → 3 A step the Pi sees ≥ {f2(s2['a']['vpimin'])} V. Only a
   0.5 → 5 A step at 2 A/µs with a nearly empty battery touches the 4.63 V warning level ({f2(s2['d']['vpimin'])} V for
   ≈ 10 µs, mostly the USB-C cable's inductance). Optional: R301 182 k → 187 k and R302 24 k → 24.3 k sets 5.22 V
   ({f2(s2['e']['vpimin'])} V minimum, {f2(s2['e']['vpi1'])} V steady at 5 A, overshoot {f2(s2['e']['vmax'])} V < 5.5 V).
6. **USB-C charging (D).** The BQ25798 reads only D+/D− (BC1.2), not the Type-C CC advertisement; a DCP sets 3.25 A
   with VINDPM protecting the source. From a 5 V 3 A charger the robot charges in {f1(D['USB-C 5 V 3 A source, Pi idle']['t_full_h'])} h with the
   Pi idle; from a 1.5 A source only {f2(D['USB 5 V 1.5 A source, Pi idle']['I_max'])} A reach the battery. The dock is the main
   charging path; firmware: VINDPM ≈ 4.5 V and ICO enabled for USB-C.
7. **Firmware settings that come out of the simulations:** ESP32-S3 drive strength 1 on GPIO11/12 (S8); acceleration
   limit (A/B); VAC2 IINDPM 1.8 A (E); motor PWM limited to a 6 V average (B); docking procedure and retries (H).

## 2. Circuit simulations (ngspice)

### S1 — VSYS with the motors under PWM
TB6612 (≈ 0.5 Ω per switch), both N20 channels in phase at 20 kHz / 75 % (worst case), motor 9 Ω / 0.6 mH, start from
standstill at 2 ms; Pi 5 buck input as 3 A pulses at 600 kHz; 3.3 V buck 0.25 A. Battery 2S2P ≈ 90 mΩ + 0.3 µH;
VSYS bank 72 µF ceramic (derated) + 100 µF electrolytic.
Result: {f0(s1['a']['vpp'] * 1e3)} mV p-p while driving, {f0(s1['a']['vpp_st'] * 1e3)} mV p-p with both motors stalled,
battery current {f1(-s1['a']['ibat'])} A / {f1(-s1['a']['ibat_st'])} A.
{img('s1_vsys_motors_7.4V', 'S1 — battery 7.4 V')}

### S2 — +5V rail for the Pi 5 (TPS566238, behavioural D-CAP3 model)
Constant-on-time model (on-time Vout/(Vin·fsw), 100 ns minimum off-time, Rds(on) 20.8/10.6 mΩ, VFB 0.6 V), validated
at {f0(s2['a']['vavg'] * 1000)} mV DC, ≈ 600 kHz and {f1(s2['a']['vpp1'] * 1e3)} mV p-p ripple. Load: USB-C cable to the Pi
(2 × 25 mΩ, 0.15 µH) and ≈ 20 µF at the Pi input. Cases: a) 7.4 V, 1 → 3 A at 1 A/µs; b) same at 6.6 V; c/d) 0.5 → 5 A at
2 A/µs at 8.4 V / 6.6 V; e) case d with the output set to 5.22 V.

| Case | Vout min / max | Pi min | Pi steady (high load) | L301 peak |
|---|---|---|---|---|
''' + ''.join(f"| {k} | {f2(v['vmin'])} / {f2(v['vmax'])} V | {f2(v['vpimin'])} V | {f2(v['vpi1'])} V | {f1(v['ilmax'])} A |\n"
              for k, v in s2.items()) + f'''
{img('s2_pi_rail_a', 'S2a — realistic Pi 5 load step')}
{img('s2_pi_rail_d', 'S2d — extreme step at a low battery')}
{img('s2_pi_ripple', 'S2 — output ripple at 3 A')}

### S3 — +3V3 always-on rail (TPS62933)
The TPS62933 is peak-current-mode; the COT model at 1.2 MHz gives ripple and the size of the response to a
0.1 → 0.6 A step (Wi-Fi burst + backlight): {f2(s3['vmin'])}–{f2(s3['vmax'])} V, {f1(s3['vpp'] * 1e3)} mV p-p.
{img('s3_3v3', 'S3 — +3V3 load step')}

### S4 — power-up sequence
Switch on at 1 ms → TPS62933 soft start (Css 33 nF ≈ 4.8 ms) → PI_EN (R310 100 k from +3V3) crosses the EN
threshold at {f1(s4['tpien'] * 1e3)} ms → +5V soft start 1.9 ms (in regulation at {f1(s4['t5'] * 1e3)} ms) → ESP32 CHIP_PU
(10 k / 1 µF) reaches 0.75 × VDD at {f1(s4['tpu'] * 1e3)} ms, ≈ 11 ms after +3V3 is stable.
{img('s4_power_up', 'S4 — sequence')}

### S5 — dock transients
12 V adapter with 1.5 m cable → PTC → AO3401A reverse-polarity FET → 10 µF + SMF15A → pogo pins → robot lead →
C202 1 µF + SMF15A → VAC2. Plugging the adapter in gives {f1(s5['plug']['vmax'])} V at VAC2; docking on a live dock rings to
{f1(s5['dock']['vmax'])} V (clamped by D202, {f1(s5['dock']['itvs'])} A peak) with a {f0(s5['dock']['ipog'])} A sub-µs inrush
into C202 (12 µC, below the 50 µC that USB allows for a hot plug); a reversed adapter is blocked by Q1.
{img('s5_dock', 'S5 — dock cases')}

### S6 — USB-C hot plug
1 m cable (0.12 Ω, 0.8 µH) into C201 1 µF: the LC rings to {f1(s6['D201_only']['vmax'])} V; U201's VBUS zener (≥ 6 V)
limits it to {f1(s6['with_U201']['vmax'])} V and conducts {f2(s6['with_U201']['iu'])} A for ≈ 1 µs. VBUS_DET peaks at
{f2(s6['with_U201']['vdet'])} V (TCA9535 abs. max 6 V, inputs 5 V tolerant). Option for a later revision: 1 Ω + 4.7 µF
damper at J201 → {f1(s6['damper']['vmax'])} V and no zener current.
{img('s6_usb_plug', 'S6 — USB-C hot plug')}

### S7 — I2C edges
Bus capacitance from the routed boards: 298 mm of trace per line (main 244 mm + head 54 mm), 120 mm of head cable,
≈ 15 vias and 7 devices (ESP32-S3, BQ25798, TCA9535 9.5 pF max, LSM6DSOX, 2 × VL53L4CD, VL53L1X) → {f0(s7['cbus_pF'])} pF.
2.2 kΩ: {f0(s7['2.2k_111p']['tr_ns'])} ns (limit 300 ns); with 50 % more capacitance {f0(s7['2.2k_166p']['tr_ns'])} ns; 1.5 kΩ
would give {f0(s7['1.5k_166p']['tr_ns'])} ns (3 mA sink limit still met). Measure tr at bring-up.
{img('s7_i2c', 'S7 — SDA rising edges')}

### S8 — display SPI over the head cable
33 Ω series (R403) → 48 mm on the main board → 120 mm cable → 73 mm on the head board → module with ESD diodes.
At the default drive strength the edge rings to {f2(s8['33R_drv2']['vmax'])} V / {f2(s8['33R_drv2']['vmin'])} V (diode current
< 1 mA, harmless but outside the ±0.3 V rating); with drive strength 1 the edge is clean
({f2(s8['33R_drv1']['vmax'])} V / {f2(s8['33R_drv1']['vmin'])} V). Without R403 it would reach {f2(s8['0R_drv2']['vmax'])} V.
{img('s8_spi', 'S8 — SCLK at the display')}

## 3. System analyses (Python)

### A — mass properties and stability
Printed parts from the CAD solids (PETG 1.27 g/cm³ × solid fraction), bought parts from catalogue masses at their CAD
positions: **{f0(A['mass_g'])} g**, CoG ({f1(A['cg_mm'][0])}, {f1(A['cg_mm'][1])}, {f1(A['cg_mm'][2])}) mm. Lateral tipping in a turn needs
{f1(A['a_lat_ms2'])} m/s² (not a concern); tipping back needs only {f2(A['a_tip_ms2'])} m/s² (see finding 1).
{img('sys_a_stability', 'A — CoG and its uncertainty')}

### B — drive
Generic GA12-N20 6 V motor (9 Ω, 15 000 rpm base, est.), gearbox efficiency 0.48–0.65:

| Gear | Wheel rpm (6 V) | Max speed | Stall force (2 motors) | Encoder counts / mm |
|---|---|---|---|---|
''' + ''.join(f"| 1:{k} | {f0(v['rpm'])} | {f2(v['v_max_ms'])} m/s | {f1(v['F_stall_N'])} N | {f1(v['counts_per_mm'])} |\n"
              for k, v in B.items() if k.isdigit()) + f'''
Recommended **1:100 (150 rpm at 6 V)**: 0.34 m/s top speed, fine control down to ≈ 3 cm/s for docking, 20.7 counts/mm.
A 0.4 m/s² ramp needs only {f2(B['ramp_current_A'])} A per motor; stall at 8.4 V is {f2(B['stall_current_8V4_A'])} A (TB6612 1.2 A
continuous). Every option can exceed the tip-back limit, so acceleration must be limited in firmware; keep the motor PWM
at a 6 V average (duty ≤ 6 V / VSYS).
{img('sys_b_drive', 'B — force vs speed')}

### C — power budget and runtime
Loads (est., Pi 5 figures from published measurements; camera and XVF3800 powered from the Pi): +5V buck 90–93 %,
+3V3 86 %, pack resistance {f0((0.030 + 2 * 0.0105 + 0.0056 + 0.010) * 1000)} mΩ, cut-off 3.25 V/cell under load.

| Mode | Battery power | Runtime |
|---|---|---|
''' + ''.join(f"| {k} | {f1(v['P_bat_W'])} W | {f1(v['runtime_h'])} h |\n" for k, v in Cr.items() if k != 'plot') + f'''
{img('sys_c_runtime', 'C — runtime')}

### D — charging
BQ25798 with ICHG 3 A, 8.4 V, termination 0.2 A; dock path 12 V − 0.32 Ω × I (cable, PTC, Q1, pogo, input FETs), buck
94 %; USB-C 5 V − 0.14 Ω × I, boost 91 %; battery model with OCV curve, pack resistance and a polarisation branch.

| Case | Input power | 10 → 80 % | Full |
|---|---|---|---|
''' + ''.join(f"| {k} | {f1(v['P_in_W'])} W | {(f1(v['t_10_80_h']) + ' h') if v['t_10_80_h'] else '—'} | {(f1(v['t_full_h']) + ' h') if v['t_full_h'] < 11.9 else '> 12 h'} |\n"
              for k, v in D.items() if k != 'plot') + f'''
{img('sys_d_charging', 'D — charging')}

### E — pogo pins
Contact resistance per pin uniformly 20–100 mΩ (datasheet max 100 mΩ), the worse of the two polarity pairs counts.
Loop drop at 1.8 A ≤ {f2(E['1.8A']['drop_V'])} V; ≤ {f0(E['1.8A']['p_contact_W'] * 1000)} mW per contact.
{img('sys_e_pogo', 'E — highest pin current')}

### F — battery protector and fuse
R5460N212AF: discharge over-current 0.200 V ± 15 mV (12 ms), short circuit 1.1 V (0.7–1.5 V, 300 µs), charge
over-current −0.2 V; 2 × CSD17579Q3A (10.2 mΩ max at 10 V, 14.2 mΩ max at 4.5 V; gate drive ≈ VDD). Trip range
{f1(F['oc_trip_A']['min'])}–{f1(F['oc_trip_A']['max'])} A (typ. {f1(F['oc_trip_A']['typ'])} A); short {f0(F['short_trip_A']['min'])}–{f0(F['short_trip_A']['max'])} A; charge
over-current ≥ {f1(F['charge_oc_trip_A']['min'])} A vs. ICHG 3 A. Over-charge detection 4.29 V/cell vs. 4.20 V charge: the
pack has no balancing, so use matched cells from one batch.
{img('sys_f_protection', 'F — protector margin')}

### G — thermal
Lumped model: shell walls ≈ 0.30 W/K, board underside 0.08 W/K, stack-effect flow through the wheel cut-outs and the
gills/halo holes, part of the Active Cooler flow exchanged through the gills; SoC ≈ 8.5 K/W above the cooler intake.

| Case | Internal air | SoC | SoC with more venting |
|---|---|---|---|
''' + ''.join(f"| {k} | {f0(v['T_internal'])} °C | {f0(v['T_soc'])} °C | {f0(v['T_soc_improved'])} °C |\n" for k, v in Gt.items() if k != 'plot') + f'''
{img('sys_g_thermal', 'G — Pi 5 SoC temperature')}

### H — docking Monte Carlo (40 000 runs per case)
Error sources: tag pose (lateral and yaw, growing with distance), camera-yaw calibration, the blind drive to the turn
point, gyro scale error over 180°, turn-centre drift, then the reverse. Capture when the rear opening meets the tongue
within ±6.5 mm (2 mm clearance + 4.5 mm chamfer) and ±6°.

| Procedure | First try | σ at the opening | Within 3 tries |
|---|---|---|---|
''' + ''.join(f"| {k} | {pct(v['success'])} | {f1(v['sigma_e_mm'])} mm | {v['p_retry3'] * 100:.1f} % |\n" for k, v in H.items() if k != 'plot') + f'''
{img('sys_h_docking', 'H — docking')}

### I — AprilTag range (Camera Module 3, HFOV 66°)
{img('sys_i_apriltag', 'I — tag size in the image')}

## 4. What was not simulated (and how to check it)

| Item | Why | Check at bring-up |
|---|---|---|
| BQ25798 internal loops, power-path hand-over, ICO | no public model | scope VSYS while plugging/unplugging the dock and USB-C under load |
| Wi-Fi / BLE (ESP32-S3 antenna in the shell), Pi 5 Wi-Fi | RF/EM tools and the real enclosure needed | RSSI at 1/5/10 m with the shell on and off |
| EMC / ESD | needs a lab | ESD gun on the dock contacts, USB-C and the touch spot |
| Acoustics (XVF3800 AEC, speaker in the shell) | room and enclosure dependent | XVF3800 tuning tools, echo-return loss with music |
| Board-level thermal (TPS566238, BQ25798 hot spots) | no FEA here | thermal camera at 3 A / 5 A and while charging |
| Printed-part strength, drops | no FEA | 0.5 m drop on the skirt corners |
| Firmware timing (motor loop, PCNT, I2C traffic) | software | logic analyser |

## 5. Files

`sim/spice_sims.py` (S1–S8), `sim/cot.py` (behavioural COT buck), `sim/spice_lib.py` (ngspice runner),
`sim/mass_props.py` (CAD mass properties), `sim/system_sims.py` (A–I), `sim/build_sim_report.py` (this report);
netlists in `sim/spice/`, results in `sim/out/spice_results.json` and `sim/out/system_results.json`.
'''
open(MD, 'w', encoding='utf-8').write(md)
css = '''body{font-family:"DejaVu Sans",Arial,sans-serif;font-size:10pt;line-height:1.42;color:#1d2430;margin:0 6mm}
h1{font-size:21pt;color:#0b1a2e;border-bottom:3px solid #20c2d8;padding-bottom:4px}
h2{font-size:15pt;color:#0b1a2e;margin-top:22px;border-bottom:1px solid #cfd8e3;page-break-after:avoid}
h3{font-size:12pt;color:#13385e;page-break-after:avoid}
table{border-collapse:collapse;width:100%;font-size:8.6pt;margin:8px 0;page-break-inside:avoid}
th,td{border:1px solid #c9d3df;padding:3px 5px;vertical-align:top}
th{background:#eaf3f8}
code{background:#f1f4f8;padding:1px 3px;border-radius:3px;font-size:8.6pt}
figure{margin:6px 0 12px 0;page-break-inside:avoid}
figure img{width:100%}
figcaption{font-size:8pt;color:#556}
'''
d = tempfile.mkdtemp()
open(f'{d}/doc.md', 'w', encoding='utf-8').write(md.replace('src="plots/', f'src="file://{O}/'))
open(f'{d}/style.css', 'w').write(css)
subprocess.run(['pandoc', f'{d}/doc.md', '-f', 'gfm', '-t', 'html5', '-s', '--metadata', 'pagetitle=NOVA Rev B simulations',
                '-c', f'{d}/style.css', '-o', f'{d}/doc.html'], check=True)
subprocess.run(['wkhtmltopdf', '--enable-local-file-access', '-q', '--page-size', 'A4', '--margin-top', '14mm',
                '--margin-bottom', '14mm', '--footer-center', 'NOVA Rev B — simulations and system analyses · [page]/[topage]',
                '--footer-font-size', '7', f'{d}/doc.html', PDF], check=False)
print(MD, PDF, os.path.getsize(PDF) if os.path.exists(PDF) else 'missing')
