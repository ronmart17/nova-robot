"""Sheet 3 — 2S battery with fuse and R5460 protector, power switch/UVLO, TPS566238 5.15 V / 5 A Pi rail and TPS62933 3.3 V rail."""
from sch import G
from helpers import place_part, vpart_between, cap_rail

def battery(sh):
    # ---- connector and fuse
    j = place_part(sh, 'J_BAT', 'J301', 33.02, 60.96, rot=180, ref_at=(-1.27, -6.35, 'left'), val_at=(-1.27, 6.35, 'left'))
    (bpx, bpy), _ = j.pin('3'); (bmx, bmy), _ = j.pin('2'); (bnx, bny), _ = j.pin('1')
    yb = 50.8
    sh.wire((bpx, bpy), (bpx + 5.08, bpy)); sh.wire((bpx + 5.08, bpy), (bpx + 5.08, yb)); sh.assign(j, '3', 'BAT+')
    f = place_part(sh, 'F_10A', 'F301', 55.88, yb, rot=90)
    (f1x, f1y), _ = f.pin('1'); (f2x, f2y), _ = f.pin('2')
    fl, fr = ('1', '2') if f1x < f2x else ('2', '1')
    (flx, fly), _ = f.pin(fl); (frx, fry), _ = f.pin(fr)
    sh.wire((bpx + 5.08, yb), (flx, yb)); sh.assign(f, fl, 'BAT+'); sh.assign(f, fr, 'VBAT')
    xv = 106.68
    sh.wire((frx, yb), (xv, yb)); sh.power('VBAT', (73.66, yb))
    sh.wire((bmx, bmy), (bmx + 12.7, bmy)); sh.label('BAT_BM', (bmx + 12.7, bmy), (1, 0)); sh.assign(j, '2', 'BAT_BM')
    sh.wire((bnx, bny), (bnx + 12.7, bny)); sh.label('BAT-', (bnx + 12.7, bny), (1, 0)); sh.assign(j, '1', 'BAT-')
    sh.text('2S2P Li-ion pack (JST VH, 10 A):\n1 = B−, 2 = midpoint, 3 = B+', (25.4, 73.66), size=1.27, italic=True)

    # ---- R5460N212AF protector
    u = place_part(sh, 'U_R5460', 'U301', xv, 76.2, ref_at=(10.16, -10.16, 'left'), val_at=(10.16, -7.62, 'left'))
    (vdx, vdy), _ = u.pin('VDD'); (vcx, vcy), _ = u.pin('VC'); (vsx, vsy), _ = u.pin('VSS')
    (cox, coy), _ = u.pin('COUT'); (dox, doy), _ = u.pin('DOUT'); (vmx, vmy), _ = u.pin('V-')
    # VDD = VBAT through R305, C315 to BAT−
    r1 = vpart_between(sh, 'R_330', 'R305', xv, yb, ('net', 'VBAT'), ('net', 'PROT_VDD'))
    (r1bx, r1by), _ = r1.pin('2')
    sh.wire((r1bx, r1by), (vdx, vdy)); sh.assign(u, 'VDD', 'PROT_VDD')
    yc = r1by + 2.54
    sh.wire((xv, yc), (xv - 7.62, yc))
    c1 = place_part(sh, 'C_100n', 'C315', xv - 7.62, yc + 3.81, fpos='left'); sh.assign(c1, '1', 'PROT_VDD')
    (c1bx, c1by), _ = c1.pin('2'); sh.assign(c1, '2', 'BAT-')
    sh.wire((c1bx, c1by), (c1bx - 5.08, c1by)); sh.label('BAT-', (c1bx - 5.08, c1by), (-1, 0))
    sh.wire((xv, yc + 2.54), (xv + 7.62, yc + 2.54)); sh.power('PWR_FLAG', (xv + 7.62, yc + 2.54))
    # VC from the midpoint
    r2 = place_part(sh, 'R_330', 'R308', vcx - 10.16, vcy, rot=90)
    (a2x, a2y), _ = r2.pin('1'); (b2x, b2y), _ = r2.pin('2')
    l2, rr2 = ('1', '2') if a2x < b2x else ('2', '1')
    (l2x, l2y), _ = r2.pin(l2); (rr2x, rr2y), _ = r2.pin(rr2)
    sh.wire((l2x, l2y), (l2x - 5.08, l2y)); sh.label('BAT_BM', (l2x - 5.08, l2y), (-1, 0)); sh.assign(r2, l2, 'BAT_BM')
    sh.wire((rr2x, rr2y), (vcx, vcy)); sh.assign(r2, rr2, 'PROT_VC'); sh.assign(u, 'VC', 'PROT_VC')
    xc2 = vcx - 2.54
    sh.wire((xc2, vcy), (xc2, vcy + 5.08))
    c2 = place_part(sh, 'C_100n', 'C316', xc2, vcy + 5.08 + 3.81, fpos='left'); sh.assign(c2, '1', 'PROT_VC')
    (c2bx, c2by), _ = c2.pin('2'); sh.assign(c2, '2', 'BAT-')
    ybus = 101.6
    sh.wire((c2bx, c2by), (c2bx, ybus))
    sh.wire((vsx, vsy), (vsx, ybus)); sh.assign(u, 'VSS', 'BAT-')
    sh.label('BAT-', (c2bx - 7.62, ybus), (-1, 0)); sh.wire((c2bx - 7.62, ybus), (c2bx, ybus)); sh.wire((c2bx, ybus), (vsx, ybus))
    # discharge FET (Q301, S on BAT−) and charge FET (Q302, S on P− = GND), common drains
    q1 = place_part(sh, 'Q_PROT', 'Q301', 134.62, ybus - 2.54, rot=270, ref_at=(2.54, -8.89, 'left'), val_at=(2.54, -6.35, 'left'))
    q2 = place_part(sh, 'Q_PROT', 'Q302', 157.48, ybus - 2.54, rot=270, mirror='y', ref_at=(1.27, -8.89, 'left'), val_at=(1.27, -6.35, 'left'))
    (s1x, s1y), _ = q1.pin('S'); (d1x, d1y), _ = q1.pin('D'); (g1x, g1y), _ = q1.pin('G')
    (s2x, s2y), _ = q2.pin('S'); (d2x, d2y), _ = q2.pin('D'); (g2x, g2y), _ = q2.pin('G')
    assert abs(s1y - ybus) < 1e-6 and abs(d2y - ybus) < 1e-6
    sh.wire((vsx, ybus), (s1x, s1y)); sh.assign(q1, 'S', 'BAT-')
    sh.wire((d1x, d1y), (d2x, d2y)); sh.assign(q1, 'D', 'PROT_MID'); sh.assign(q2, 'D', 'PROT_MID')
    sh.wire((s2x, s2y), (s2x + 7.62, s2y)); sh.power('GND', (s2x + 7.62, s2y)); sh.assign(q2, 'S', 'GND')
    sh.wire((dox, doy), (g1x, doy)); sh.wire((g1x, doy), (g1x, g1y)); sh.assign(u, 'DOUT', 'PROT_DOUT'); sh.assign(q1, 'G', 'PROT_DOUT')
    sh.wire((cox, coy), (g2x, coy)); sh.wire((g2x, coy), (g2x, g2y)); sh.assign(u, 'COUT', 'PROT_COUT'); sh.assign(q2, 'G', 'PROT_COUT')
    # V− to P− (GND) through R309
    xm = vmx + 7.62
    sh.wire((vmx, vmy), (xm, vmy)); sh.assign(u, 'V-', 'PROT_VM')
    vpart_between(sh, 'R_1k', 'R309', xm, vmy, ('net', 'PROT_VM'), 'GND')
    # PWR_FLAG on BAT−
    sh.power('PWR_FLAG', (s1x - 5.08, ybus));
    sh.text('Q301 discharge (S on B−) · Q302 charge (S on P− = board GND)', (99.06, 111.76), size=1.27, italic=True)
    sh.text('R5460N212AF: overcharge 4.29 V/cell (release 4.05 V), overdischarge 3.00 V (3.20 V), discharge overcurrent\n'
            '0.2 V / (2·RDS(on)): CSD17579Q3A (8.7 mΩ typ @ 10 V) → ≈ 10 A cold, ≈ 7 A hot (12 ms delay); short circuit 1.1 V (300 µs).\n'
            'R305/R308 330 Ω (< 1 kΩ) + C315/C316 100 nF filter VDD and VC; R309 1 kΩ (R305 + R309 ≥ 1 kΩ, R309 ≤ 3 kΩ).\n'
            'F301 10 A very fast (NANO2) next to the connector: protects the wiring if the protector fails.', (25.4, 120.65), size=1.27)

def buck(sh, y0, refs, rfb_top, vout_kind, title):
    """TPS62933 at 1.2 MHz (RT to GND). y0 = row of the SW pin."""
    U, CIN1, CIN2, CSS, CBST, L, CO1, CO2, CO3, RT, RB = refs
    if title:
        sh.text(title, (210.82, y0 - 27.94), size=1.524, bold=True)
    ux = 259.08
    u = place_part(sh, 'U_TPS62933', U, ux, y0, ref_at=(-5.08, -12.065, 'left'), val_at=(-2.54, 15.875, 'right'))
    (vx, vy), _ = u.pin('VIN'); sh.assign(u, 'VIN', 'VSYS')
    yr = y0 - 20.32; xr = vx - 7.62
    sh.wire((vx, vy), (xr, vy)); sh.wire((xr, vy), (xr, yr)); sh.wire((xr, yr), (231.14, yr))
    sh.power('VSYS', (xr, yr))
    cap_rail(sh, 'VSYS', 218.44, yr, [(CIN1, 'C_22u_25V'), (CIN2, 'C_100n')], dx=12.7)
    sh.pin_label(u, 'EN', 'PWR_EN', length=12.7)
    (sx, sy), _ = u.pin('SS'); sh.assign(u, 'SS', f'{U}_SS')
    sh.wire((sx, sy), (sx - 15.24, sy))
    vpart_between(sh, 'C_33n', CSS, sx - 15.24, sy, ('net', f'{U}_SS'), 'GND')
    (rx, ry), _ = u.pin('RT'); sh.assign(u, 'RT', 'GND')
    sh.wire((rx, ry), (rx - 2.54, ry)); sh.power('GND', (rx - 2.54, ry))
    sh.pin_power(u, 'GND', 'GND', length=2.54)
    (bx, by), _ = u.pin('BST'); sh.assign(u, 'BST', f'{U}_BST')
    (swx, swy), _ = u.pin('SW'); sh.assign(u, 'SW', f'{U}_SW')
    xb = bx + 5.08
    sh.wire((bx, by), (xb, by))
    vpart_between(sh, 'C_100n', CBST, xb, by, ('net', f'{U}_BST'), ('net', f'{U}_SW'))
    l = place_part(sh, 'L_3u3', L, swx + 25.4, swy, rot=90)
    (la, lay), _ = l.pin('1'); (lb, lby), _ = l.pin('2')
    lin, lout = ('1', '2') if la < lb else ('2', '1')
    (lix, liy), _ = l.pin(lin); (lox, loy), _ = l.pin(lout)
    sh.wire((swx, swy), (lix, liy)); sh.assign(l, lin, f'{U}_SW'); sh.assign(l, lout, vout_kind)
    xv = lox + 7.62
    sh.wire((lox, loy), (xv + 20.32, loy)); sh.power(vout_kind, (xv, loy))
    cap_rail(sh, vout_kind, xv + 20.32, loy, [(CO1, 'C_22u_10V'), (CO2, 'C_22u_10V'), (CO3, 'C_100n')], dx=12.7)
    (fx, fy), _ = u.pin('FB'); sh.assign(u, 'FB', f'{U}_FB')
    xf = xv + 7.62
    vpart_between(sh, rfb_top, RT, xf, loy, ('net', vout_kind), ('net', f'{U}_FB'))
    vpart_between(sh, 'R_10k', RB, xf, fy, ('net', f'{U}_FB'), 'GND')
    sh.wire((fx, fy), (xf, fy))
    return u

def pi_buck(sh):
    """TPS566238P: VSYS (6.0-8.4 V) -> 5.15 V / 5 A for the Raspberry Pi 5 (USB-C output on sheet 7)."""
    ux, uy = 279.4, 116.84
    u = place_part(sh, 'U_TPS566238', 'U302', ux, uy, ref_at=(-7.62, -12.7, 'left'), val_at=(-7.62, 13.97, 'left'))
    # VIN from VSYS with the input capacitors
    (vx, vy), _ = u.pin('VIN'); sh.assign(u, 'VIN', 'VSYS')
    yr, xr = 91.44, vx - 7.62
    sh.wire((vx, vy), (xr, vy)); sh.wire((xr, vy), (xr, yr)); sh.power('VSYS', (xr, yr))
    sh.wire((256.54, yr), (xr, yr))
    cap_rail(sh, 'VSYS', 218.44, yr, [('C301', 'C_10u_25V_0805'), ('C302', 'C_10u_25V_0805'), ('C303', 'C_10u_25V_0805'), ('C304', 'C_100n')], dx=12.7)
    sh.text('Input: 3×10 µF + 100 nF (C304 at the VIN/PGND pins)', (213.36, 81.28), size=1.27, italic=True)
    # VCC
    (cx, cy), _ = u.pin('VCC'); sh.assign(u, 'VCC', 'U302_VCC')
    sh.wire((cx, cy), (cx - 5.08, cy))
    vpart_between(sh, 'C_1u', 'C305', cx - 5.08, cy, ('net', 'U302_VCC'), 'GND')
    sh.pin_power(u, 'PGND', 'GND', length=2.54)
    # EN: pull-up to +3V3 (alive only while the 3.3 V buck runs) and Q303 driven by the ESP32
    (ex, ey), _ = u.pin('EN'); sh.assign(u, 'EN', 'PI_EN')
    xn = 236.22
    sh.wire((xn, ey), (ex, ey)); sh.label('PI_EN', (251.46, ey), (0, -1))
    rpu = vpart_between(sh, 'R_100k', 'R310', xn, ey - 10.16, '+3V3', None)
    (rpx, rpy), _ = rpu.pin('2'); sh.assign(rpu, '2', 'PI_EN'); sh.wire((rpx, rpy), (rpx, ey))
    vpart_between(sh, 'C_1n', 'C312', xn + 10.16, ey, ('net', 'PI_EN'), 'GND')
    q = place_part(sh, 'Q_2N7002', 'Q303', xn - 2.54, ey + 10.16)
    (qdx, qdy), _ = q.pin('D'); (qgx, qgy), _ = q.pin('G')
    sh.wire((qdx, qdy), (qdx, ey)); sh.assign(q, 'D', 'PI_EN')
    sh.pin_power(q, 'S', 'GND', length=2.54)
    sh.wire((qgx, qgy), (qgx - 10.16, qgy)); sh.assign(q, 'G', 'PI_PWR_OFF')
    sh.hlabel('PI_PWR_OFF', (qgx - 10.16, qgy), (-1, 0), 'input')
    vpart_between(sh, 'R_100k', 'R312', qgx - 5.08, qgy, ('net', 'PI_PWR_OFF'), 'GND')
    # BST and SW
    (bx, by), _ = u.pin('BST'); sh.assign(u, 'BST', 'U302_BST')
    (swx, swy), _ = u.pin('SW'); sh.assign(u, 'SW', 'U302_SW')
    xb = bx + 7.62
    sh.wire((bx, by), (xb, by))
    cb = vpart_between(sh, 'C_100n', 'C306', xb, by - 7.62, ('net', 'U302_SW'), ('net', 'U302_BST'))
    (c1x, c1y), _ = cb.pin('1')
    sh.wire((c1x, c1y), (c1x, c1y - 2.54), (xb + 10.16, c1y - 2.54), (xb + 10.16, swy))
    l = place_part(sh, 'L_2u2', 'L301', swx + 25.4, swy, rot=90, ref_at=(-2.54, -3.81, 'left'), val_at=(-2.54, 3.81, 'left'))
    (la, _), (lb, _) = l.pin('1'), l.pin('2')
    lin, lout = ('1', '2') if la[0] < lb[0] else ('2', '1')
    (lix, liy), _ = l.pin(lin); (lox, loy), _ = l.pin(lout)
    sh.wire((swx, swy), (lix, liy)); sh.assign(l, lin, 'U302_SW'); sh.assign(l, lout, '+5V')
    # output rail with the capacitors and the feedback divider at its end
    xo = lox + 7.62
    sh.wire((lox, loy), (xo, loy)); sh.power('+5V', (xo, loy))
    sh.wire((xo, loy), (xo + 7.62, loy))
    xs, _ = cap_rail(sh, '+5V', xo + 7.62, loy, [('C307', 'C_47u_10V'), ('C308', 'C_47u_10V'), ('C309', 'C_47u_10V'), ('C310', 'C_100n')], dx=12.7)
    xf = xs[-1] + 12.7
    sh.wire((xs[-1], loy), (xf, loy))
    rt = vpart_between(sh, 'R_182k', 'R301', xf, loy, ('net', '+5V'), None)
    rbt = vpart_between(sh, 'R_24k', 'R302', xf, loy + 10.16, None, 'GND')
    sh.connect('U302_FB', (rt, '2'), (rbt, '1'))
    sh.wire((xf, loy + 8.89), (xf - 5.08, loy + 8.89)); sh.label('U302_FB', (xf - 5.08, loy + 8.89), (-1, 0))
    sh.wire((xf, loy), (xf + 7.62, loy))
    cff = vpart_between(sh, 'C_33p', 'C311', xf + 7.62, loy, ('net', '+5V'), None)
    (c3x, c3y), _ = cff.pin('2'); sh.assign(cff, '2', 'U302_FB')
    sh.wire((c3x, c3y), (c3x, loy + 8.89)); sh.wire((c3x, loy + 8.89), (xf, loy + 8.89))
    (fx, fy), _ = u.pin('FB'); sh.assign(u, 'FB', 'U302_FB')
    sh.wire((fx, fy), (fx + 7.62, fy)); sh.label('U302_FB', (fx + 7.62, fy), (1, 0))
    # PG → expander, pull-up to +3V3
    (gx, gy), _ = u.pin('PG'); sh.assign(u, 'PG', 'PI_5V_PG')
    yp = gy + 10.16
    sh.wire((gx, gy), (gx + 5.08, gy)); sh.wire((gx + 5.08, gy), (gx + 5.08, yp)); sh.wire((gx + 5.08, yp), (gx + 25.4, yp))
    rpg = vpart_between(sh, 'R_10k', 'R313', gx + 15.24, yp - 7.62, '+3V3', ('net', 'PI_5V_PG'))
    sh.hlabel('PI_5V_PG', (gx + 25.4, yp), (1, 0), 'output')
    sh.text('Vout = 0.6 V × (1 + 182k/24.0k) = 5.15 V (Pi 5 input 5.0–5.25 V). D-CAP3 at 600 kHz; 98 % max duty (frequency\n'
            'foldback): regulates 5.15 V at 5 A down to ≈ 5.5 V in. L301 2.2 µH (Isat 11 A); valley limit ≥ 6.1 A. Cout 3×47 µF\n'
            '(≈ 75 µF effective at 5 V, limit 220 µF incl. C701). EN: pulled to +3V3 (off with the 3.3 V rail = power switch);\n'
            'PI_PWR_OFF high (ESP32 GPIO1, held in deep sleep) turns the Pi rail off after the shutdown handshake. PG → U402 P12.',
            (210.82, 152.4), size=1.27)

def build(sh):
    sh.section('2S BATTERY, FUSE AND PROTECTION (R5460)', (20.32, 25.4), (200.66, 137.16))
    sh.section('POWER SWITCH AND UVLO', (205.74, 25.4), (401.32, 68.58))
    sh.section('PI 5 V RAIL — TPS566238P, 5.15 V / 5 A (TO THE PI USB-C OUTPUT, SHEET 7)', (205.74, 73.66), (401.32, 167.64))
    sh.section('ALWAYS-ON 3.3 V RAIL — TPS62933 at 1.2 MHz', (205.74, 172.72), (401.32, 254.0))
    sh.section('TEST POINTS, FLAGS AND NOTES', (20.32, 142.24), (200.66, 254.0))

    battery(sh)

    # ------------------------------------------------------------------ power switch + UVLO
    y = 45.72
    sh.power('VSYS', (215.9, y), rot=0)
    r1 = place_part(sh, 'R_86k6', 'R306', 226.06, y, rot=90)
    (a1x, a1y), _ = r1.pin('1'); (b1x, b1y), _ = r1.pin('2')
    lp, rp = ('1', '2') if a1x < b1x else ('2', '1')
    (lpx, lpy), _ = r1.pin(lp); (rpx, rpy), _ = r1.pin(rp)
    sh.wire((215.9, y), (lpx, y)); sh.assign(r1, lp, 'VSYS'); sh.assign(r1, rp, 'PWR_EN')
    xn = 241.3
    sh.wire((rpx, y), (xn, y))
    vpart_between(sh, 'R_23k2', 'R307', xn, y, ('net', 'PWR_EN'), 'GND')
    sw = place_part(sh, 'SW_SLIDE', 'SW301', 266.7, y, ref_at=(-2.54, -6.35, 'left'), val_at=(-2.54, 6.35, 'left'))
    (sbx, sby), _ = sw.pin('B'); (sax, say), _ = sw.pin('A'); (scx, scy), _ = sw.pin('C')
    sh.wire((xn, y), (sbx, sby)); sh.assign(sw, 'B', 'PWR_EN')
    sh.label('PWR_EN', (251.46, y), (1, 0))
    sh.wire((sax, say), (sax + 5.08, say)); sh.wire((sax + 5.08, say), (sax + 5.08, say + 7.62))
    sh.power('GND', (sax + 5.08, say + 7.62)); sh.assign(sw, 'A', 'GND')
    sh.pin_nc(sw, 'C')
    sh.text('OFF', (sax + 1.27, say - 1.27), size=1.0, italic=True)
    sh.text('ON', (scx + 2.54, scy + 1.27), size=1.0, italic=True)
    sh.text('SW301 in OFF ties PWR_EN to GND: 3.3 V buck off, and with it\n'
            'the Pi rail (PI_EN pull-up) — the contact sees ≤ 1.8 V.\n'
            'ON: 86.6k/23.2k divider → start-up ≈ 5.6 V (< 6.0 V protector cut-off\n'
            'and < VSYSMIN 7.0 V). Charging works with the robot switched off.', (288.29, 38.1), size=1.27)

    # ------------------------------------------------------------------ regulators
    pi_buck(sh)
    buck(sh, 215.9, ('U303', 'C320', 'C321', 'C322', 'C323', 'L302', 'C324', 'C325', 'C326', 'R320', 'R321'),
         'R_31k6', '+3V3', '')
    sh.text('Vout = 0.8 V × (1 + 31.6k/10k) = 3.33 V. RT to GND → 1.2 MHz. Css 33 nF → 4.8 ms.\n'
            'L302 3.3 µH (Isat 8 A); Cout 2×22 µF X5R. ESP32-S3, expander, sensors, head board.',
            (210.82, 243.84), size=1.27)

    # ------------------------------------------------------------------ test points and PWR_FLAG
    for i, (ref, net) in enumerate((('TP301', 'VSYS'), ('TP302', 'VBAT'), ('TP303', '+5V'), ('TP304', '+3V3'),
                                    ('TP305', 'GND'), ('TP306', 'GND'), ('TP307', 'BAT-'))):
        xx = 33.02 + i * 17.78
        t = place_part(sh, 'TP', ref, xx, 162.56, ref_at=(1.27, -5.715, 'left'), hide_value=True, val_at=(1.27, -3.175, 'left'))
        sh.assign(t, '1', net)
        if net == 'GND':
            sh.wire((xx, 162.56), (xx, 165.1)); sh.power('GND', (xx, 165.1))
        elif net == 'BAT-':
            sh.wire((xx, 162.56), (xx, 167.64)); sh.label('BAT-', (xx, 167.64), (0, 1))
        else:
            sh.wire((xx, 162.56), (xx, 167.64)); sh.power(net, (xx, 167.64), rot=180)
    for i, net in enumerate(('GND', '+5V', '+3V3')):
        xx = 33.02 + i * 22.86
        sh.power('PWR_FLAG', (xx, 190.5))
        if net == 'GND':
            sh.wire((xx, 190.5), (xx, 195.58)); sh.power('GND', (xx, 195.58))
        else:
            sh.wire((xx, 190.5), (xx, 195.58)); sh.power(net, (xx, 195.58), rot=180)
    notes = ('NOTES\n'
             '• VSYS: BQ25798 power-path output (6.0–8.4 V; ≥ 7.0 V with input). Feeds the TB6612 and both bucks.\n'
             '• Board GND = pack P− (after Q302). Never tie BAT− to GND except through Q301/Q302.\n'
             '• Off-state draw: bucks in shutdown, protector (≈ 4 µA) and BQ25798 battery-only (≈ 17 µA, ADC off).\n'
             '• Capacitors with no voltage rating: X7R 50 V.')
    sh.text(notes, (25.4, 210.82), size=1.27)
