"""NOVA charging dock — 12 V barrel jack, PTC, reverse-polarity P-MOSFET, TVS, LED and two pogo pins.
The same PCB panel carries a break-away robot contact plate (two ENIG pads wired to J203 on the main board)."""
from sch import G
from helpers import place_part, vpart_between, cap_rail, place_vertical_k_top

def hpart(sh, key, ref, x, y, left_net, right_net):
    """Horizontal 2-pin part centred at (x, y); returns (inst, left_point, right_point)."""
    p = place_part(sh, key, ref, x, y, rot=90)
    (a, _), (b, _) = p.pin('1'), p.pin('2')
    lp, rp = ('1', '2') if a[0] < b[0] else ('2', '1')
    (lx, ly), _ = p.pin(lp); (rx, ry), _ = p.pin(rp)
    sh.assign(p, lp, left_net); sh.assign(p, rp, right_net)
    return p, (lx, ly), (rx, ry)

def build(sh):
    sh.section('12 V INPUT AND PROTECTION', (20.32, 25.4), (269.24, 137.16))
    sh.section('POGO PINS (TO THE ROBOT)', (274.32, 25.4), (401.32, 137.16))
    sh.section('ROBOT CONTACT PLATE (BREAK-AWAY PART, MOUNTED UNDER THE ROBOT)', (20.32, 142.24), (269.24, 254.0))
    sh.section('NOTES', (274.32, 142.24), (401.32, 254.0))

    yl = 66.04                                     # main 12 V line
    j = place_part(sh, 'J_DCJACK', 'J1', 33.02, yl + 2.54, ref_at=(-5.08, -6.35, 'left'), val_at=(-5.08, 7.62, 'left'))
    (p1x, p1y), _ = j.pin('1'); (p2x, p2y), _ = j.pin('2')
    assert abs(p1y - yl) < 1e-6, p1y
    sh.assign(j, '1', 'VIN_RAW')
    sh.pin_nc(j, '3')
    sh.assign(j, '2', 'GND'); sh.wire((p2x, p2y), (p2x + 5.08, p2y)); sh.wire((p2x + 5.08, p2y), (p2x + 5.08, p2y + 7.62))
    sh.power('GND', (p2x + 5.08, p2y + 7.62))
    sh.power('PWR_FLAG', (p2x + 12.7, p2y)); sh.wire((p2x + 5.08, p2y), (p2x + 12.7, p2y))
    f, fl, fr = hpart(sh, 'F_PTC', 'F1', 60.96, yl, 'VIN_RAW', 'VIN_F')
    sh.wire((p1x, yl), fl)
    sh.power('PWR_FLAG', (48.26, yl))
    # reverse-polarity P-MOSFET: drain = input side, source = output side, gate to GND through R1, D2 clamps VGS
    q = place_part(sh, 'Q_P_SOT23', 'Q1', 96.52, yl + 2.54, rot=90, ref_at=(-2.54, -8.89, 'left'), val_at=(-2.54, -6.35, 'left'))
    (dx, dy), _ = q.pin('D'); (sx, sy), _ = q.pin('S'); (gx, gy), _ = q.pin('G')
    assert abs(dy - yl) < 1e-6 and abs(sy - yl) < 1e-6 and dx < sx, (dx, dy, sx, sy)
    sh.wire(fr, (dx, dy)); sh.assign(q, 'D', 'VIN_F'); sh.assign(q, 'S', 'VDOCK_OUT')
    xo = 254.0
    sh.wire((sx, sy), (xo, yl)); sh.label('VDOCK_OUT', (xo, yl), (1, 0))
    sh.assign(q, 'G', 'Q1_G')
    yg = gy + 7.62
    sh.wire((gx, gy), (gx, yg))
    z = place_part(sh, 'D_ZENER_10V', 'D2', gx + 10.16, yg, rot=180, ref_at=(-3.81, 3.81, 'left'), val_at=(-3.81, 6.35, 'left'))
    (zkx, zky), _ = z.pin('K'); (zax, zay), _ = z.pin('A')
    assert zax < zkx and abs(zay - yg) < 1e-6
    sh.wire((gx, yg), (zax, zay)); sh.assign(z, 'A', 'Q1_G')
    sh.wire((zkx, zky), (zkx, yl)); sh.assign(z, 'K', 'VDOCK_OUT')
    vpart_between(sh, 'R_10k', 'R1', gx, yg, ('net', 'Q1_G'), 'GND')
    # TVS, bulk, LED
    xs = 142.24
    tv = place_vertical_k_top(sh, 'D_TVS_15V', 'D1', xs, yl + 7.62, fpos='right')
    (k1, _), (a1, _) = tv.pin('1'), tv.pin('2')
    sh.assign(tv, '1', 'VDOCK_OUT'); sh.assign(tv, '2', 'GND')
    sh.wire(k1, (k1[0], yl)); sh.power('GND', a1)
    cap_rail(sh, 'VDOCK_OUT', xs + 15.24, yl, [('C1', 'C_22u_25V'), ('C2', 'C_100n')], dx=12.7, start_net='VDOCK_OUT')
    rl = vpart_between(sh, 'R_4k7', 'R2', xs + 45.72, yl, ('net', 'VDOCK_OUT'), None)
    dl = place_part(sh, 'LED_G', 'D3', xs + 45.72, yl + 17.78, rot=90)
    sh.connect('LED_A', (rl, '2'), (dl, '2'))
    sh.pin_power(dl, '1', 'GND', length=2.54)
    sh.power('PWR_FLAG', (xs + 60.96, yl))
    sh.text('D3: 12 V present (≈ 2 mA)', (xs + 38.1, yl + 30.48), size=1.27, italic=True)
    sh.text('F1 (PTC 3 A hold / 6 A trip) opens on a short across the exposed pogo pins.\n'
            'Q1 (AO3401A, 44 mΩ) blocks a reversed adapter; D2 (10 V) clamps its VGS (±12 V max).\n'
            'D1 SMF15A: 15 V stand-off, clamps hot-plug ringing on the output.', (25.4, 116.84), size=1.27)

    # pogo pins: two per polarity (YTC1P is rated 1.5 A each), 5 mm apart along the 12 mm side of each plate pad
    for i, (ref, net) in enumerate((('P1', 'VDOCK_OUT'), ('P3', 'VDOCK_OUT'), ('P2', 'GND'), ('P4', 'GND'))):
        x = 297.18 + i * 25.4
        pp = place_part(sh, 'POGO', ref, x, 73.66, rot=270, ref_at=(2.54, -6.35, 'left'), val_at=(2.54, -3.81, 'left'))
        (qx, qy), _ = pp.pin('1'); sh.assign(pp, '1', net)
        sh.wire((qx, qy), (qx, qy + 5.08))
        if net == 'GND':
            sh.power('GND', (qx, qy + 5.08))
        else:
            sh.label(net, (qx, qy + 5.08), (0, 1))
    sh.text('P1/P3 = +12 V, P2/P4 = GND: 16 mm between polarities, 5 mm between the two pins\n'
            'of a pair (YTC1P-8020: 1.5 A max each, 9.0 mm working height, 100 g).', (279.4, 116.84), size=1.27)

    # robot contact plate
    for i, (ref, net) in enumerate((('TP1', 'PLATE_POS'), ('TP2', 'PLATE_GND'))):
        x = 55.88 + i * 38.1
        t = place_part(sh, 'TP_PLATE', ref, x, 175.26, ref_at=(2.54, -7.62, 'left'), val_at=(2.54, -5.08, 'left'))
        (qx, qy), _ = t.pin('1'); sh.assign(t, '1', net)
        sh.wire((qx, qy), (qx, qy + 10.16)); sh.label(net, (qx, qy + 10.16), (0, 1))
    jw = place_part(sh, 'J_PLATE', 'J2', 177.8, 187.96, mirror='y', ref_at=(-6.35, -5.08, 'left'), val_at=(-6.35, 7.62, 'left'))
    sh.pin_label(jw, '1', 'PLATE_POS', length=12.7)
    sh.pin_label(jw, '2', 'PLATE_GND', length=12.7)
    for i, net in enumerate(('PLATE_POS', 'PLATE_GND')):
        xx = 218.44 + i * 22.86
        sh.power('PWR_FLAG', (xx, 165.1)); sh.wire((xx, 165.1), (xx, 172.72)); sh.label(net, (xx, 172.72), (0, 1))
    sh.text('Two 8×12 mm ENIG pads on the bottom of the plate; a 2-wire lead from J2 (JST XH) goes\n'
            'to J203 on the robot main board (pin 1 = +12 V, pin 2 = GND). The plate is not wired to the\n'
            'dock circuit: it is a separate break-away part of the same panel.', (25.4, 226.06), size=1.27)

    notes = ('NOTES\n'
             '• Adapter: 12 V, ≥ 2.5 A, 5.5×2.1 mm barrel, centre positive.\n'
             '• The robot reverses onto the dock: the pogo pins press on the\n'
             '  contact plate from below (working height 9 mm).\n'
             '• Robot side: BQ25798 VAC2 behind a back-to-back FET pair;\n'
             '  the charger connects it only once 12 V is valid.\n'
             '• Firmware: IINDPM ≤ 2.5 A on VAC2 (two pogo pairs).\n'
             '• Finish: ENIG (flat, corrosion-resistant contact pads).\n'
             '• Docking alignment: AprilTag on the dock back wall (Pi camera).')
    sh.text(notes, (279.4, 152.4), size=1.27)
    for i in range(4):
        place_part(sh, 'MH_M3', f'H{i+1}', 289.56 + i * 12.7, 210.82, ref_at=(2.54, -2.54, 'left'), val_at=(2.54, 0, 'left'))
    for i in range(2):
        place_part(sh, 'MH_M3', f'H{i+5}', 289.56 + i * 12.7, 231.14, ref_at=(2.54, -2.54, 'left'), val_at=(2.54, 0, 'left'))
    sh.text('H1–H4: dock base · H5–H6: contact plate', (279.4, 243.84), size=1.27, italic=True)
    for i in range(2):
        place_part(sh, 'MB_TAB', f'MB{i+1}', 365.76 + i * 12.7, 210.82, ref_at=(2.54, -2.54, 'left'), val_at=(2.54, 0, 'left'))
    sh.text('MB1–MB2: break-away tabs', (355.6, 223.52), size=1.27, italic=True)
