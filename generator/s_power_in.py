"""Sheet 2 — power inputs (USB-C on VAC1, 12 V dock on VAC2), back-to-back ACFET/RBFET input selector and the BQ25798
buck-boost 2S charger with NVDC power path (I2C 0x6B)."""
from sch import G
from helpers import place_part, vpart_between, cap_rail, place_vertical_k_top

def fet_pair(sh, xa, y0, qa, qb, vin, acdrv, title):
    """Back-to-back common-source N-MOSFET pair: ACFET drain on the connector side (vin), RBFET drain on CHG_VBUS.
    (xa, y0) = ACFET anchor; the drain/source line runs at y0 - 2.54 and the gates at y0 + 5.08."""
    sh.text(title, (xa - 30.48, y0 - 15.24), size=1.27, bold=True)
    a = place_part(sh, 'Q_ACFET', qa, xa, y0, rot=90, ref_at=(-7.62, -10.16, 'left'), val_at=(-7.62, -7.62, 'left'))
    b = place_part(sh, 'Q_ACFET', qb, xa + 20.32, y0, rot=90, mirror='y', ref_at=(2.54, -10.16, 'left'), val_at=(2.54, -7.62, 'left'))
    (adx, ady), _ = a.pin('D'); (asx, asy), _ = a.pin('S'); (agx, agy), _ = a.pin('G')
    (bdx, bdy), _ = b.pin('D'); (bsx, bsy), _ = b.pin('S'); (bgx, bgy), _ = b.pin('G')
    src = f'{acdrv}_S'
    sh.wire((asx, asy), (bsx, bsy)); sh.assign(a, 'S', src); sh.assign(b, 'S', src)
    sh.wire((adx, ady), (adx - 15.24, ady)); sh.label(vin, (adx - 15.24, ady), (-1, 0)); sh.assign(a, 'D', vin)
    sh.wire((bdx, bdy), (bdx + 15.24, bdy)); sh.label('CHG_VBUS', (bdx + 15.24, bdy), (1, 0)); sh.assign(b, 'D', 'CHG_VBUS')
    yg = agy + 5.08
    sh.wire((agx, agy), (agx, yg)); sh.wire((bgx, bgy), (bgx, yg)); sh.wire((agx, yg), (bgx, yg))
    xm = (agx + bgx) / 2
    sh.wire((xm, yg), (xm, yg + 5.08)); sh.label(acdrv, (xm, yg + 5.08), (0, 1))
    sh.assign(a, 'G', acdrv); sh.assign(b, 'G', acdrv)
    return a, b

def build(sh):
    sh.section('USB-C INPUT (VAC1) — 5 V, ESD AND TVS', (20.32, 25.4), (134.62, 137.16))
    sh.section('CHARGING DOCK INPUT (VAC2) — 12 V', (20.32, 142.24), (134.62, 193.04))
    sh.section('NOTES', (20.32, 198.12), (134.62, 254.0))
    sh.section('INPUT SELECTOR — BACK-TO-BACK ACFET/RBFET PAIRS', (139.7, 25.4), (254.0, 129.54))
    sh.section('CHARGER POWER CAPACITORS (TIGHT TO U202)', (139.7, 134.62), (254.0, 254.0))
    sh.section('2S BUCK-BOOST CHARGER, NVDC POWER PATH — BQ25798 (I2C 0x6B)', (259.08, 25.4), (401.32, 248.92))

    # ------------------------------------------------------------------ USB-C
    j = place_part(sh, 'J_USBC', 'J201', 43.18, 76.2, ref_at=(-10.16, -20.955, 'left'), val_at=(-10.16, -18.415, 'left'))
    (vx, vy), _ = j.pin('A4'); sh.assign(j, 'A4', 'VBUS_USB')
    sh.wire((vx, vy), (vx + 12.7, vy)); sh.label('VBUS_USB', (vx + 12.7, vy), (1, 0))
    for pin, net in (('A5', 'CC1'), ('B5', 'CC2')):
        sh.pin_label(j, pin, net, length=12.7)
    for (pa, pb, net, xj) in (('A7', 'B7', 'USB_DM', 60.96), ('A6', 'B6', 'USB_DP', 63.5)):
        (ax, ay), _ = j.pin(pa); (bx, by), _ = j.pin(pb)
        sh.wire((ax, ay), (xj, ay)); sh.wire((bx, by), (xj, by)); sh.wire((xj, ay), (xj, by))
        sh.wire((xj, ay), (ax + 12.7, ay)); sh.label(net, (ax + 12.7, ay), (1, 0))
        sh.assign(j, pa, net); sh.assign(j, pb, net)
    sh.pin_nc(j, 'A8'); sh.pin_nc(j, 'B8')
    sh.pin_power(j, 'A1', 'GND', length=2.54)
    sh.pin_power(j, 'SHIELD', 'GND', length=2.54)
    for x, net, ref in ((93.98, 'CC1', 'R201'), (106.68, 'CC2', 'R202')):
        vpart_between(sh, 'R_5k1', ref, x, 50.8, ('label', net, 2.54), 'GND')
    sh.text('Rd = 5.1 kΩ on CC1/CC2:\nUSB-C sink at 5 V', (91.44, 69.85), size=1.27)
    # ESD on D+/D- (and VBUS)
    e = place_part(sh, 'U_USBLC6', 'U201', 101.6, 104.14, ref_at=(5.08, -6.35, 'left'), val_at=(5.08, -3.81, 'left'))
    (p1x, p1y), _ = e.pin('1'); (p3x, p3y), _ = e.pin('3')
    sh.wire((p1x, p1y), (p1x - 10.16, p1y)); sh.label('USB_DM', (p1x - 10.16, p1y), (-1, 0)); sh.assign(e, '1', 'USB_DM')
    sh.wire((p3x, p3y), (p3x - 10.16, p3y)); sh.label('USB_DP', (p3x - 10.16, p3y), (-1, 0)); sh.assign(e, '3', 'USB_DP')
    sh.pin_label(e, '6', 'USB_DM', length=12.7)          # D+/D− of the USB-C input: BC1.2 detection only (R205/R206)
    sh.pin_label(e, '4', 'USB_DP', length=12.7)
    sh.pin_label(e, '5', 'VBUS_USB', length=5.08)
    sh.pin_power(e, '2', 'GND', length=2.54)
    # VBUS TVS + local capacitor
    tv = place_vertical_k_top(sh, 'D_TVS_12V', 'D201', 30.48, 116.84, fpos='right')
    (k1, _), (a1, _) = tv.pin('1'), tv.pin('2')
    sh.assign(tv, '1', 'VBUS_USB'); sh.assign(tv, '2', 'GND')
    sh.wire(k1, (k1[0], k1[1] - 5.08)); sh.label('VBUS_USB', (k1[0], k1[1] - 5.08), (0, -1)); sh.power('GND', a1)
    vpart_between(sh, 'C_1u_25V', 'C201', 53.34, 109.22, ('label', 'VBUS_USB', 2.54), 'GND')
    # VBUS detection for the ESP32 USB device (→ expander P11)
    r3 = vpart_between(sh, 'R_100k', 'R203', 66.04, 106.68, ('label', 'VBUS_USB', 2.54), None)
    r4 = vpart_between(sh, 'R_200k', 'R204', 66.04, 114.3, None, 'GND')
    sh.assign(r3, '2', 'VBUS_DET'); sh.assign(r4, '1', 'VBUS_DET')
    sh.wire((66.04, 114.3), (78.74, 114.3)); sh.hlabel('VBUS_DET', (78.74, 114.3), (1, 0), 'output')
    sh.text('VBUS_DET: 5 V → 3.33 V', (63.5, 133.35), size=1.27, italic=True)
    sh.text('D201 SMF12A + C201\nat the connector', (25.4, 133.35), size=1.27, italic=True)

    # ------------------------------------------------------------------ dock input
    jd = place_part(sh, 'J_DOCK', 'J203', 35.56, 165.1, mirror='y', ref_at=(-6.35, -5.08, 'left'), val_at=(-6.35, 7.62, 'left'))
    (d1x, d1y), _ = jd.pin('1'); (d2x, d2y), _ = jd.pin('2')
    sh.wire((d1x, d1y), (114.3, d1y)); sh.assign(jd, '1', 'VDOCK'); sh.label('VDOCK', (114.3, d1y), (1, 0))
    sh.wire((d2x, d2y), (d2x + 5.08, d2y)); sh.wire((d2x + 5.08, d2y), (d2x + 5.08, d2y + 7.62)); sh.power('GND', (d2x + 5.08, d2y + 7.62))
    sh.assign(jd, '2', 'GND')
    td = place_vertical_k_top(sh, 'D_TVS_15V', 'D202', 71.12, d1y + 7.62, fpos='right')
    (k2, _), (a2, _) = td.pin('1'), td.pin('2')
    sh.assign(td, '1', 'VDOCK'); sh.assign(td, '2', 'GND')
    sh.wire(k2, (k2[0], d1y)); sh.power('GND', a2)
    vpart_between(sh, 'C_1u_25V', 'C202', 86.36, d1y, ('net', 'VDOCK'), 'GND')
    sh.power('PWR_FLAG', (101.6, d1y))
    sh.text('J203 (bottom side): wires from the dock contact plate.\n1 = +12 V, 2 = GND. D202 SMF15A clamps hot-plug\nringing below the 30 V abs. max of VAC2.',
            (25.4, 182.88), size=1.27)
    sh.power('PWR_FLAG', (121.92, 60.96)); sh.wire((121.92, 60.96), (121.92, 66.04)); sh.label('VBUS_USB', (121.92, 66.04), (0, 1))

    # ------------------------------------------------------------------ input selector
    fet_pair(sh, 175.26, 60.96, 'Q201', 'Q202', 'VBUS_USB', 'ACDRV1', 'PAIR 1 — USB-C (VAC1, BC1.2 detection)')
    fet_pair(sh, 175.26, 93.98, 'Q203', 'Q204', 'VDOCK', 'ACDRV2', 'PAIR 2 — 12 V DOCK (VAC2)')
    sh.text('ACDRVx drives both gates ≈ 5 V above the common source. The first valid input is connected;\n'
            'with both present VAC1 wins. The host swaps inputs with EN_ACDRV1/2. A missing or reversed input\n'
            'is blocked in both directions (no back-feed into the USB port or onto the dock contacts).',
            (144.78, 121.92), size=1.27)

    # ------------------------------------------------------------------ charger capacitors
    rows = (('CHG_VBUS', [('C203', 'C_10u_25V_0805'), ('C204', 'C_10u_25V_0805'), ('C205', 'C_100n')], 'VBUS: 2×10 µF + 0.1 µF'),
            ('CHG_PMID', [('C206', 'C_10u_25V_0805'), ('C207', 'C_10u_25V_0805'), ('C208', 'C_10u_25V_0805'), ('C209', 'C_100n')],
             'PMID: 3×10 µF + 0.1 µF'),
            ('VSYS', [('C210', 'C_10u_25V_0805'), ('C211', 'C_10u_25V_0805'), ('C212', 'C_10u_25V_0805'), ('C213', 'C_10u_25V_0805'),
                      ('C214', 'C_10u_25V_0805'), ('C215', 'C_100n')], 'SYS: 5×10 µF + 0.1 µF'),
            ('VBAT', [('C216', 'C_10u_25V_0805'), ('C217', 'C_10u_25V_0805')], 'BAT: 2×10 µF'))
    for i, (net, caps, txt) in enumerate(rows):
        y = 147.32 + i * 26.67
        sh.text(txt, (144.78, y - 3.81), size=1.27, italic=True)
        x0 = 165.1
        if net in ('VSYS', 'VBAT'):
            sh.power(net, (x0 - 10.16, y)); sh.wire((x0 - 10.16, y), (x0, y))
            cap_rail(sh, net, x0, y, caps, dx=12.7)
        else:
            sh.label(net, (x0 - 10.16, y), (-1, 0)); sh.wire((x0 - 10.16, y), (x0, y))
            cap_rail(sh, net, x0, y, caps, dx=12.7, start_net=net)

    # ------------------------------------------------------------------ BQ25798
    ux, uy = 330.2, 96.52
    u = place_part(sh, 'U_BQ25798', 'U202', ux, uy, ref_at=(-10.16, -35.56, 'left'), val_at=(-10.16, -33.02, 'left'))
    L = {'VBUS': 'CHG_VBUS', 'VAC1': 'VBUS_USB', 'ACDRV1': 'ACDRV1', 'VAC2': 'VDOCK', 'ACDRV2': 'ACDRV2', 'D-': 'CHG_DM',
         'D+': 'CHG_DP', '~{QON}': 'CHG_QON', 'ILIM_HIZ': 'CHG_ILIM', 'PROG': 'CHG_PROG', 'TS': 'CHG_TS'}
    for pin, net in L.items():
        sh.pin_label(u, pin, net, length=7.62)
    for pin, net, shape in (('SCL', 'I2C_SCL', 'input'), ('SDA', 'I2C_SDA', 'bidirectional'), ('~{INT}', 'IRQ_N', 'output')):
        (px, py), _ = u.pin(pin)
        sh.wire((px, py), (px - 20.32, py)); sh.assign(u, pin, net); sh.hlabel(net, (px - 20.32, py), (-1, 0), shape)
    # ~CE held low by R214: charging enabled in hardware; firmware switches charging with EN_CHG (REG0x0F) over I2C
    (px, py), _ = u.pin('~{CE}')
    sh.wire((px, py), (px - 20.32, py)); sh.assign(u, '~{CE}', 'CHG_CE'); sh.label('CHG_CE', (px - 20.32, py), (-1, 0))
    R = {'PMID': 'CHG_PMID', 'BTST1': 'CHG_BTST1', 'SW1': 'CHG_SW1', 'SW2': 'CHG_SW2', 'BTST2': 'CHG_BTST2',
         'REGN': 'CHG_REGN', 'SDRV': 'CHG_SDRV', 'BATP': 'CHG_BATP'}
    for pin, net in R.items():
        sh.pin_label(u, pin, net, length=7.62)
    for pin, net, dx in (('SYS', 'VSYS', 12.7), ('BAT', 'VBAT', 22.86)):
        (px, py), _ = u.pin(pin); sh.assign(u, pin, net)
        sh.wire((px, py), (px + dx, py)); sh.power(net, (px + dx, py))
    sh.pin_power(u, 'GND', 'GND', length=2.54)
    sh.power('PWR_FLAG', (285.75, 63.5)); sh.wire((285.75, 63.5), (285.75, 68.58)); sh.label('CHG_VBUS', (285.75, 68.58), (0, 1))
    sh.text('U202 pins 2/3 (VBUS) and 22/23 (BAT) are\ndoubled in the package.', (264.16, 142.24), size=1.27, italic=True)

    # inductor and bootstraps
    sh.text('POWER STAGE (750 kHz)', (264.16, 152.4), size=1.524, bold=True)
    l = place_part(sh, 'L_2u2', 'L201', 284.48, 165.1, rot=90, ref_at=(-2.54, -3.81, 'left'), val_at=(-2.54, 3.81, 'left'))
    (la, _), (lb, _) = l.pin('1'), l.pin('2')
    lp, rp = ('1', '2') if la[0] < lb[0] else ('2', '1')
    (lx, ly), _ = l.pin(lp); (rx, ry), _ = l.pin(rp)
    sh.wire((lx, ly), (lx - 7.62, ly)); sh.label('CHG_SW1', (lx - 7.62, ly), (-1, 0)); sh.assign(l, lp, 'CHG_SW1')
    sh.wire((rx, ry), (rx + 7.62, ry)); sh.label('CHG_SW2', (rx + 7.62, ry), (1, 0)); sh.assign(l, rp, 'CHG_SW2')
    vpart_between(sh, 'C_47n', 'C219', 312.42, 157.48, ('label', 'CHG_BTST1', 2.54), ('label', 'CHG_SW1', 2.54))
    vpart_between(sh, 'C_47n', 'C220', 327.66, 157.48, ('label', 'CHG_BTST2', 2.54), ('label', 'CHG_SW2', 2.54))
    vpart_between(sh, 'C_4u7', 'C218', 342.9, 157.48, ('label', 'CHG_REGN', 2.54), 'GND')
    vpart_between(sh, 'C_1n', 'C221', 358.14, 157.48, ('label', 'CHG_SDRV', 2.54), 'GND')
    rb = vpart_between(sh, 'R_100', 'R215', 373.38, 157.48, ('label', 'CHG_BATP', 2.54), None)
    (bx2, by2), _ = rb.pin('2'); sh.assign(rb, '2', 'VBAT'); sh.wire((bx2, by2), (bx2, by2 + 2.54)); sh.power('VBAT', (bx2, by2 + 2.54), rot=180)
    sh.text('L201 2.2 µH (Isat 11 A) between SW1 and SW2: one inductor for buck and boost.\n'
            'C219/C220 47 nF bootstraps. C218 REGN. C221: SDRV with no ship FET.\nR215: BATP sense, 100 Ω to the pack.',
            (264.16, 182.88), size=1.27)

    # configuration network
    sh.text('CONFIGURATION, TS (NTC), STATUS', (264.16, 195.58), size=1.524, bold=True)
    yr = 208.28
    r = vpart_between(sh, 'R_4k7', 'R210', 269.24, yr, ('label', 'CHG_REGN', 2.54), None)
    r2 = vpart_between(sh, 'R_10k', 'R212', 269.24, yr + 10.16, None, 'GND')
    sh.connect('CHG_ILIM', (r, '2'), (r2, '1'))
    sh.wire((269.24, yr + 10.16), (276.86, yr + 10.16)); sh.label('CHG_ILIM', (276.86, yr + 10.16), (1, 0))
    vpart_between(sh, 'R_8k2', 'R213', 292.1, yr, ('label', 'CHG_PROG', 2.54), 'GND')
    rt1 = vpart_between(sh, 'R_5k23', 'R207', 307.34, yr, ('label', 'CHG_REGN', 2.54), None)
    rt2 = vpart_between(sh, 'R_30k1', 'R208', 307.34, yr + 10.16, None, 'GND')
    sh.connect('CHG_TS', (rt1, '2'), (rt2, '1'))
    sh.wire((307.34, yr + 10.16), (325.12, yr + 10.16)); sh.label('CHG_TS', (314.96, yr + 10.16), (1, 0))
    vpart_between(sh, 'R_10k', 'R209', 325.12, yr + 10.16, ('net', 'CHG_TS'), 'GND', dnp=True)
    jn = place_part(sh, 'J_NTC', 'J202', 345.44, yr + 10.16, ref_at=(-1.27, -3.81, 'left'), val_at=(-1.27, 6.35, 'left'))
    (n1x, n1y), _ = jn.pin('1'); (n2x, n2y), _ = jn.pin('2')
    sh.wire((325.12, yr + 10.16), (n1x, n1y)); sh.assign(jn, '1', 'CHG_TS')
    sh.wire((n2x, n2y), (n2x - 5.08, n2y)); sh.wire((n2x - 5.08, n2y), (n2x - 5.08, n2y + 5.08))
    sh.power('GND', (n2x - 5.08, n2y + 5.08)); sh.assign(jn, '2', 'GND')
    # STAT (open drain) not used: the charge LED would be hidden inside the enclosure; the charge state is read over
    # I2C and shown on the face display. Firmware sets DIS_STAT = 1.
    sh.pin_nc(u, 'STAT')
    rc = vpart_between(sh, 'R_100k', 'R214', 373.38, yr, ('label', 'CHG_CE', 2.54), 'GND')
    t = place_part(sh, 'TP', 'TP201', 388.62, yr + 2.54, ref_at=(1.27, -5.715, 'left'), hide_value=True, val_at=(1.27, -3.175, 'left'))
    (tx, ty), _ = t.pin('1'); sh.assign(t, '1', 'CHG_QON'); sh.wire((tx, ty), (tx, ty + 5.08)); sh.label('CHG_QON', (tx, ty + 5.08), (0, 1))
    for i, (ref, a, b) in enumerate((('R205', 'CHG_DP', 'USB_DP'), ('R206', 'CHG_DM', 'USB_DM'))):
        yy = 233.68 + i * 7.62
        rr = place_part(sh, 'R_0', ref, 279.4, yy, rot=90)
        (ax, ay), _ = rr.pin('1'); (bx3, by3), _ = rr.pin('2')
        lpin, rpin = ('1', '2') if ax < bx3 else ('2', '1')
        (lx2, ly2), _ = rr.pin(lpin); (rx2, ry2), _ = rr.pin(rpin)
        sh.wire((lx2, ly2), (lx2 - 7.62, ly2)); sh.label(a, (lx2 - 7.62, ly2), (-1, 0)); sh.assign(rr, lpin, a)
        sh.wire((rx2, ry2), (rx2 + 7.62, ry2)); sh.label(b, (rx2 + 7.62, ry2), (1, 0)); sh.assign(rr, rpin, b)
    sh.text('R205/R206 (0 Ω): BC1.2 on the\nshared USB D+/D− pair.', (299.72, 236.22), size=1.27)

    notes = ('• BQ25798: 2S buck-boost charger, 3.6–24 V inputs.\n'
             '  USB-C 5 V (VAC1, BC1.2) and 12 V dock (VAC2);\n'
             '  NVDC power path: SYS ≥ VSYSMIN 7.0 V with input.\n'
             '• Firmware at boot: watchdog kick or disable;\n'
             '  VAC_OVP = 18 V (reg 0x10); ICHG 2.0 A; VREG 8.40 V;\n'
             '  IINDPM from CC (USB) or 2.5 A (dock); HVDCP off.\n'
             '• IBAT discharge 6 A RMS / 10 A for 1 s (BATFET).\n'
             '• ILIM_HIZ = REGN·10/14.7: hardware input limit\n'
             '  ≈ 2.8–3.0 A (the lower of pin and IINDPM wins).\n'
             '• PROG 8.2 kΩ → 2S, 750 kHz. TS 5.23k/30.1k + 10 kΩ\n'
             '  NTC (103AT): JEITA 0–60 °C. R209 only without NTC.\n'
             '• R214 holds ~CE low: charging enabled in hardware;\n'
             '  EN_CHG over I2C. STAT unused (DIS_STAT = 1): state over\n'
             '  I2C, shown on the face display. TP201: QON.\n'
             '• Capacitors with no voltage rating: X7R 50 V.')
    sh.text(notes, (25.4, 205.74), size=1.27)
