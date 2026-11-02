"""Head board (face) — JST SH 20p connector, ST7789 display with backlight, VL53L1X ToF, AT42QT1010 touch sensor and the
mounting for the Raspberry Pi Camera Module 3 (camera FPC goes straight to the Pi 5)."""
from sch import G
from helpers import place_part, vpart_between, cap_rail

HEAD = {1: '+3V3', 2: '+3V3', 3: 'GND', 4: 'LCD_SCLK', 5: 'GND', 6: 'LCD_MOSI', 7: 'LCD_CS', 8: 'LCD_DC', 9: 'LCD_BL',
        10: 'GND', 11: 'I2C_SCL', 12: 'I2C_SDA', 13: 'TOF_XSHUT', 14: 'TOF_INT', 15: 'GND', 16: 'GND',
        17: None, 18: 'GND', 19: 'TOUCH', 20: 'GND'}

def build(sh):
    sh.section('MAIN BOARD CONNECTOR — JST SH 20p (1:1 cable)', (20.32, 25.4), (124.46, 254.0))
    sh.section('ST7789 2.0" DISPLAY (8-PIN MODULE) AND BACKLIGHT', (129.54, 25.4), (401.32, 109.22))
    sh.section('DISTANCE — VL53L1X (I2C 0x29)', (129.54, 114.3), (259.08, 254.0))
    sh.section('CAMERA MODULE 3 — MECHANICAL ONLY', (264.16, 114.3), (401.32, 182.88))
    sh.section('TOUCH — AT42QT1010', (264.16, 187.96), (401.32, 248.92))

    # ------------------------------------------------------------------ connector
    j = place_part(sh, 'J_HEAD', 'J101', 50.8, 139.7, mirror='y', ref_at=(-2.54, -24.13, 'right'), val_at=(-2.54, 27.94, 'right'))
    for n, net in HEAD.items():
        if net is None:
            sh.pin_nc(j, str(n))
        elif net == 'GND':
            sh.pin_power(j, str(n), 'GND', length=2.54)
        elif net == '+3V3':
            sh.stub(j, str(n), 2.54); sh.assign(j, str(n), '+3V3')
        else:
            sh.pin_label(j, str(n), net, length=12.7)
    (p1x, p1y), _ = j.pin('1'); (p2x, p2y), _ = j.pin('2')
    xv = p1x + 2.54
    sh.wire((xv, p1y), (xv, p2y))
    yt = p1y - 7.62
    sh.wire((xv, p1y), (xv, yt)); sh.power('+3V3', (xv, yt))
    sh.wire((xv, yt), (xv + 12.7, yt))
    cap_rail(sh, '+3V3', xv + 12.7, yt, [('C101', 'C_10u_10V'), ('C102', 'C_100n')], dx=12.7)
    (mx, my), _ = j.pin('MP'); sh.assign(j, 'MP', 'GND')
    sh.wire((mx, my), (mx, my + 2.54)); sh.power('GND', (mx, my + 2.54))
    sh.text('C101/C102 next to the connector', (xv + 12.7, yt - 3.81), size=1.27, italic=True)
    for i, net in enumerate(('+3V3', 'GND')):
        xx = 33.02 + i * 17.78
        sh.power('PWR_FLAG', (xx, 218.44))
        sh.wire((xx, 218.44), (xx, 223.52))
        sh.power(net, (xx, 223.52), rot=180 if net != 'GND' else 0)
    sh.text('Pin n ↔ pin n with J602 on the main board.\nGND interleaved next to SCLK. Pin 17 spare (NC).\nJST SH 1.0 mm cable ≤ 12 cm.', (25.4, 238.76), size=1.27)

    # ------------------------------------------------------------------ display
    # J102 (right side, front view) and J103 (left side, unfitted alternative): same pin order from
    # top to bottom. Solder whichever one matches the orientation of the purchased module (see text).
    for ref, y0, dnp in (('J102', 63.5, False), ('J103', 93.98, True)):
        lcd = place_part(sh, 'J_LCD', ref, 378.46, y0, dnp=dnp, ref_at=(-1.27, -11.43, 'left'), val_at=(-1.27, 13.97, 'left'))
        sh.pin_power(lcd, '1', 'GND', length=2.54)
        (q2x, q2y), _ = lcd.pin('2'); sh.assign(lcd, '2', '+3V3')
        sh.wire((q2x, q2y), (q2x - 10.16, q2y)); sh.wire((q2x - 10.16, q2y), (q2x - 10.16, q2y - 10.16)); sh.power('+3V3', (q2x - 10.16, q2y - 10.16))
        for pin, net in (('3', 'LCD_SCLK'), ('4', 'LCD_MOSI'), ('5', 'LCD_RES'), ('6', 'LCD_DC'), ('7', 'LCD_CS'), ('8', 'BL_OUT')):
            sh.pin_label(lcd, pin, net, length=15.24)
    sh.text('Module pin order: GND VCC SCL SDA RES DC CS BLK.\nJ102 (right) or J103 (left, DNP): fit only one,\nmatching the module orientation; pin 1 = GND on top.', (271.78, 99.06), size=1.27, italic=True)
    # reset RC
    rr = vpart_between(sh, 'R_10k', 'R101', 309.88, 45.72, '+3V3', None)
    cr = vpart_between(sh, 'C_100n', 'C103', 309.88, 58.42, None, 'GND')
    sh.connect('LCD_RES', (rr, '2'), (cr, '1'))
    sh.wire((309.88, 55.88), (322.58, 55.88)); sh.label('LCD_RES', (322.58, 55.88), (1, 0))
    sh.text('Power-on reset (τ = 1 ms);\nfirmware adds a SWRESET.', (294.64, 76.2), size=1.27)
    # backlight switch (high side)
    qp = place_part(sh, 'Q_P_SOT23', 'Q101', 233.68, 58.42, mirror='x', ref_at=(5.08, -1.27, 'left'), val_at=(5.08, 1.27, 'left'))
    (sx, sy), _ = qp.pin('S'); (dx, dy), _ = qp.pin('D'); (gx, gy), _ = qp.pin('G')
    assert sy < dy
    sh.wire((sx, sy), (sx, sy - 5.08)); sh.power('+3V3', (sx, sy - 5.08)); sh.assign(qp, 'S', '+3V3')
    yb = dy + 5.08
    sh.wire((dx, dy), (dx, yb)); sh.assign(qp, 'D', 'BL_OUT')
    sh.wire((dx, yb), (dx + 7.62, yb)); sh.label('BL_OUT', (dx + 7.62, yb), (1, 0))
    vpart_between(sh, 'R_1k', 'R109', dx, yb, ('net', 'BL_OUT'), 'GND')
    rpu = vpart_between(sh, 'R_10k', 'R102', gx - 10.16, gy - 10.16, '+3V3', None)
    sh.connect('BL_G', (rpu, '2'), (gx - 10.16, gy), (qp, 'G'))
    qn = place_part(sh, 'Q_2N7002', 'Q102', gx - 12.7, gy + 17.78)
    (ndx, ndy), _ = qn.pin('D'); (ngx, ngy), _ = qn.pin('G')
    sh.connect('BL_G', (qn, 'D'), (ndx, gy))
    sh.pin_power(qn, 'S', 'GND', length=2.54)
    rg = place_part(sh, 'R_100', 'R103', ngx - 17.78, ngy, rot=90)
    sh.connect('BL_GN', (rg, '2'), (qn, 'G'))
    vpart_between(sh, 'R_100k', 'R104', ngx - 7.62, ngy, ('net', 'BL_GN'), 'GND')
    (r1x, r1y), _ = rg.pin('1'); sh.assign(rg, '1', 'LCD_BL')
    sh.wire((r1x, r1y), (r1x - 7.62, r1y)); sh.label('LCD_BL', (r1x - 7.62, r1y), (-1, 0))
    sh.text('LCD_BL = 1 → Q102 on → Q101 on → BLK = 3.3 V. R109 holds BLK at 0 V when off\n(modules with internal BLK pull-up). Suits logic BLK or a direct LED. PWM ≤ 5 kHz.', (134.62, 99.06), size=1.27)

    # ------------------------------------------------------------------ ToF
    t = place_part(sh, 'U_VL53L1X', 'U101', 190.5, 182.88, ref_at=(10.16, 6.35, 'left'), val_at=(10.16, 8.89, 'left'))
    sh.pin_label(t, 'SDA', 'I2C_SDA', length=15.24)
    sh.pin_label(t, 'SCL', 'I2C_SCL', length=15.24)
    sh.pin_label(t, 'GPIO1', 'TOF_INT', length=15.24)
    sh.pin_label(t, 'XSHUT', 'TOF_XSHUT', length=15.24)
    sh.assign(t, '8', '__NC__U101.8')
    (ax, ay), _ = t.pin('AVDD'); (vx, vy), _ = t.pin('AVDDVCSEL')
    sh.assign(t, 'AVDD', '+3V3'); sh.assign(t, 'AVDDVCSEL', '+3V3')
    top = ay - 10.16
    sh.wire((ax, ay), (ax, top)); sh.wire((vx, vy), (vx, top)); sh.wire((ax, top), (vx, top)); sh.wire((vx, top), (vx + 12.7, top))
    sh.power('+3V3', (ax, top))
    cap_rail(sh, '+3V3', vx + 12.7, top, [('C104', 'C_4u7'), ('C105', 'C_100n'), ('C106', 'C_100n')], dx=15.24)
    sh.text('C104 on AVDDVCSEL, C105/C106 on AVDD', (vx + 12.7, top - 3.81), size=1.27, italic=True)
    (tgx, tgy), _ = t.pin('GND'); (tax, tay), _ = t.pin('AVSSVCSEL')
    sh.wire((tgx, tgy), (tgx, tgy + 2.54)); sh.wire((tax, tay), (tax, tay + 2.54)); sh.wire((tax, tay + 2.54), (tgx, tgy + 2.54))
    sh.power('GND', (tgx, tgy + 2.54)); sh.assign(t, 'GND', 'GND'); sh.assign(t, 'AVSSVCSEL', 'GND')
    for x, (ref, net) in zip((149.86, 162.56), (('R105', 'TOF_INT'), ('R106', 'TOF_XSHUT'))):
        r = vpart_between(sh, 'R_10k', ref, x, 208.28, '+3V3', None)
        (bx, by), _ = r.pin('2'); sh.assign(r, '2', net)
        sh.wire((bx, by), (bx, by + 5.08)); sh.label(net, (bx, by + 5.08), (0, 1))
    sh.text('Optical window facing forward (vertical board).\nXSHUT pulled up: ToF active even if the expander\nis not configured yet. GPIO1 is open-drain.', (134.62, 236.22), size=1.27)

    # ------------------------------------------------------------------ camera (mechanical)
    for i, ref in enumerate(('H103', 'H104', 'H105', 'H106')):
        place_part(sh, 'MH_M2', ref, 279.4 + i * 15.24, 139.7, ref_at=(2.54, -2.54, 'left'), val_at=(2.54, 0, 'left'))
    sh.text('Raspberry Pi Camera Module 3 (standard) on 4× M2 holes, front side, lens through the face shell.\n'
            'Its 15-pin FPC passes through the slot under the module to the rear and on to the Pi 5\n'
            'CAM/DISP connector (22-pin, Pi 5 adapter cable). No electrical connection to this board.', (269.24, 157.48), size=1.27)

    # ------------------------------------------------------------------ touch
    q = place_part(sh, 'U_QT1010', 'U103', 322.58, 220.98, ref_at=(-7.62, -7.62, 'right'), val_at=(-7.62, 7.62, 'right'))
    (ox, oy), _ = q.pin('OUT'); sh.assign(q, 'OUT', 'TOUCH')
    sh.wire((ox, oy), (ox - 17.78, oy)); sh.label('TOUCH', (ox - 17.78, oy), (-1, 0))
    (syx, syy), _ = q.pin('SYNC'); sh.assign(q, 'SYNC', '+3V3')
    sh.wire((syx, syy), (syx - 5.08, syy)); sh.wire((syx - 5.08, syy), (syx - 5.08, syy - 10.16)); sh.power('+3V3', (syx - 5.08, syy - 10.16))
    (vx, vy), _ = q.pin('VDD'); sh.assign(q, 'VDD', '+3V3')
    yr = vy - 7.62
    sh.wire((vx, vy), (vx, yr)); sh.power('+3V3', (vx, yr)); sh.wire((vx, yr), (vx + 12.7, yr))
    vpart_between(sh, 'C_100n', 'C108', vx + 12.7, yr, ('net', '+3V3'), 'GND')
    sh.pin_power(q, 'VSS', 'GND', length=2.54)
    (kx, ky), _ = q.pin('SNSK'); (nx, ny), _ = q.pin('SNS')
    xc = kx + 7.62
    sh.wire((kx, ky), (xc, ky)); sh.assign(q, 'SNSK', 'TOUCH_SNSK')
    cs = vpart_between(sh, 'C_8n2', 'C109', xc, ky, ('net', 'TOUCH_SNSK'), None)
    (c2x, c2y), _ = cs.pin('2'); sh.assign(cs, '2', 'TOUCH_SNS')
    sh.wire((nx, ny), (nx + 2.54, ny)); sh.wire((nx + 2.54, ny), (nx + 2.54, c2y + 2.54)); sh.wire((nx + 2.54, c2y + 2.54), (xc, c2y + 2.54))
    sh.wire((xc, c2y + 2.54), (c2x, c2y)); sh.assign(q, 'SNS', 'TOUCH_SNS')
    rs = place_part(sh, 'R_4k7', 'R108', xc + 15.24, ky, rot=90)
    sh.connect('TOUCH_SNSK', (xc, ky), (rs, '1'))
    pad = place_part(sh, 'J_TOUCHPAD', 'TP101', xc + 30.48, ky, rot=270, ref_at=(5.08, -1.27, 'left'), val_at=(5.08, 1.27, 'left'))
    sh.connect('TOUCH_ELEC', (rs, '2'), (pad, '1'))
    sh.text('SYNC/MODE = VDD → fast mode. Cs 8.2 nF (sensitivity), Rs 4.7 kΩ (EMC).\nElectrode: copper tape on the top of the head.', (269.24, 241.3), size=1.27)
