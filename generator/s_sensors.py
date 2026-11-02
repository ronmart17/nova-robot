"""Sheet 6 — LSM6DSOX IMU, 2× VL53L4CD cliff ToF sensors (bottom side), head servo and connector to the head board."""
from sch import G
from helpers import place_part, vpart_between, cap_rail

def build(sh):
    sh.section('IMU — LSM6DSOX (I2C 0x6A)', (20.32, 25.4), (190.5, 111.76))
    sh.section('CLIFF SENSORS — VL53L4CD ToF ×2 (bottom side, facing down)', (20.32, 116.84), (190.5, 254.0))
    sh.section('HEAD SERVO (OPTIONAL TILT) — 5 V FROM THE PI RAIL', (200.66, 25.4), (401.32, 111.76))
    sh.section('HEAD BOARD CONNECTOR — JST SH 20p', (200.66, 116.84), (401.32, 248.92))

    # ------------------------------------------------------------------ IMU
    u = place_part(sh, 'U_LSM6DSO', 'U601', 101.6, 71.12, ref_at=(12.7, 6.985, 'left'), val_at=(12.7, 9.525, 'left'))
    # SA0, SDx, SCx to GND with a single symbol
    pts = [u.pin(p)[0] for p in ('SDO/SA0', 'SDx', 'SCx')]
    xb = pts[0][0] - 2.54
    for (px, py), pn in zip(pts, ('SDO/SA0', 'SDx', 'SCx')):
        sh.wire((px, py), (xb, py)); sh.assign(u, pn, 'GND')
    sh.wire((xb, pts[0][1]), (xb, pts[-1][1]))
    sh.wire((xb, pts[0][1]), (xb - 2.54, pts[0][1])); sh.power('GND', (xb - 2.54, pts[0][1]), rot=270)
    XL = 71.12
    for pin, net, shape in (('SDA', 'I2C_SDA', 'bidirectional'), ('SCL', 'I2C_SCL', 'input')):
        (px, py), _ = u.pin(pin)
        sh.wire((px, py), (XL, py)); sh.assign(u, pin, net); sh.hlabel(net, (XL, py), (-1, 0), shape)
    (cx, cy), _ = u.pin('CS'); sh.assign(u, 'CS', '+3V3')
    sh.wire((cx, cy), (cx - 2.54, cy)); sh.power('+3V3', (cx - 2.54, cy), rot=90)
    sh.pin_label(u, 'INT1', 'IMU_INT1', length=10.16, kind='hier', shape='output')
    for pin in ('INT2', 'OCS_Aux', 'SDO_Aux'):
        sh.pin_nc(u, pin)
    (ax, ay), _ = u.pin('VDDIO'); (bx, by), _ = u.pin('VDD')
    sh.assign(u, 'VDDIO', '+3V3'); sh.assign(u, 'VDD', '+3V3')
    top = ay - 10.16
    sh.wire((ax, ay), (ax, top)); sh.wire((bx, by), (bx, top)); sh.wire((ax, top), (bx, top))
    sh.power('+3V3', (ax, top))
    sh.wire((bx, top), (bx + 10.16, top))
    cap_rail(sh, '+3V3', bx + 10.16, top, [('C601', 'C_100n'), ('C602', 'C_100n')])
    sh.text('VDD / VDDIO', (bx + 10.16, top - 3.81), size=1.27, italic=True)
    sh.pin_power(u, 'GND', 'GND', length=2.54)
    sh.text('SA0 = GND → address 0x6A (0x6B is used by the BQ25798). CS = VDDIO → I2C mode.\n'
            'INT1 push-pull, active high → expander input (P04). SDx/SCx (auxiliary I2C) to GND.\n'
            'LSM6DSOX: same footprint and pinout as the LSM6DSO (enough stock at LCSC).', (25.4, 93.98), size=1.27)

    # ------------------------------------------------------------------ cliff ToF sensors
    for i, (side, U, C1, C2, C3, RX) in enumerate((('L', 'U602', 'C603', 'C604', 'C610', 'R601'),
                                                    ('R', 'U603', 'C607', 'C608', 'C611', 'R602'))):
        x0 = 25.4 + i * 83.82
        sh.text('Left (U602)' if side == 'L' else 'Right (U603)', (x0 + 2.54, 129.54), size=1.524, bold=True)
        t = place_part(sh, 'U_VL53L4CD', U, x0 + 38.1, 182.88, ref_at=(10.16, 6.35, 'left'), val_at=(10.16, 8.89, 'left'))
        sh.pin_label(t, 'SDA', 'I2C_SDA', length=10.16, kind='hier', shape='bidirectional')
        sh.pin_label(t, 'SCL', 'I2C_SCL', length=10.16, kind='hier', shape='input')
        sh.pin_label(t, 'GPIO1', 'CLIFF_INT', length=10.16, kind='hier', shape='output')
        xs_net = f'CLIFF_{side}_XSHUT'
        (xx, xy), _ = t.pin('XSHUT'); sh.assign(t, 'XSHUT', xs_net)
        sh.wire((xx, xy), (xx - 10.16, xy)); sh.hlabel(xs_net, (xx - 10.16, xy), (-1, 0), 'input')
        vpart_between(sh, 'R_100k', RX, xx - 5.08, xy, ('net', xs_net), 'GND')
        sh.assign(t, '8', f'__NC__{U}.8')
        (ax, ay), _ = t.pin('AVDD'); (vx, vy), _ = t.pin('AVDDVCSEL')
        sh.assign(t, 'AVDD', '+3V3'); sh.assign(t, 'AVDDVCSEL', '+3V3')
        top = ay - 10.16
        sh.wire((ax, ay), (ax, top)); sh.wire((vx, vy), (vx, top)); sh.wire((ax, top), (vx, top)); sh.wire((vx, top), (vx + 7.62, top))
        sh.power('+3V3', (ax, top))
        cap_rail(sh, '+3V3', vx + 7.62, top, [(C1, 'C_4u7'), (C2, 'C_100n')], dx=12.7)
        (tgx, tgy), _ = t.pin('GND'); (tax, tay), _ = t.pin('AVSSVCSEL')
        sh.wire((tgx, tgy), (tgx, tgy + 2.54)); sh.wire((tax, tay), (tax, tay + 2.54)); sh.wire((tax, tay + 2.54), (tgx, tgy + 2.54))
        sh.power('GND', (tgx, tgy + 2.54)); sh.assign(t, 'GND', 'GND'); sh.assign(t, 'AVSSVCSEL', 'GND')
    sh.text('VL53L4CD (1–1300 mm, 18° FoV) on the bottom side, ≈ 27 mm above the table, at the front corners.\n'
            'XSHUT pulled down: both start off; firmware enables one at a time and moves its address\n'
            '(0x29 → 0x30/0x31; the head VL53L1X keeps 0x29). GPIO1 (open-drain) → CLIFF_INT (pull-up on sheet 4).\n'
            'Measures the table distance; a jump of > 15 mm = edge. Works on dark and glossy tables.', (25.4, 233.68), size=1.27)

    # ------------------------------------------------------------------ servo
    js = place_part(sh, 'J_SERVO', 'J603', 340.36, 60.96, dnp=True, ref_at=(-1.27, -6.35, 'left'), val_at=(-1.27, 6.35, 'left'))
    sh.pin_power(js, '1', 'GND', length=2.54)
    (p2x, p2y), _ = js.pin('2'); sh.assign(js, '2', '+5V')
    sh.wire((p2x, p2y), (p2x - 12.7, p2y)); sh.power('+5V', (p2x - 12.7, p2y))
    rs = place_part(sh, 'R_100', 'R603', 299.72, 63.5, rot=90)
    (a, _), (b, _) = rs.pin('1'), rs.pin('2')
    lp, rp = ('1', '2') if a[0] < b[0] else ('2', '1')
    (lx, ly), _ = rs.pin(lp); (rx, ry), _ = rs.pin(rp)
    (p3x, p3y), _ = js.pin('3')
    sh.wire((rx, ry), (p3x, p3y)) if abs(ry - p3y) < 1e-6 else sh.wire((rx, ry), (rx + 5.08, ry), (rx + 5.08, p3y), (p3x, p3y))
    sh.assign(rs, rp, 'SERVO_SIG'); sh.assign(js, '3', 'SERVO_SIG')
    sh.wire((lx, ly), (lx - 12.7, ly)); sh.hlabel('SERVO_PWM', (lx - 12.7, ly), (-1, 0), 'input'); sh.assign(rs, lp, 'SERVO_PWM')
    vpart_between(sh, 'R_100k', 'R604', lx - 5.08, ly, ('net', 'SERVO_PWM'), 'GND')
    cp = place_part(sh, 'C_100u', 'C612', 271.78, 50.8 + 3.81, dnp=True)
    sh.assign(cp, '1', '+5V'); sh.assign(cp, '2', 'GND')
    (c1x, c1y), _ = cp.pin('1'); (c2x, c2y), _ = cp.pin('2')
    sh.wire((c1x, c1y), (c1x, c1y - 2.54)); sh.power('+5V', (c1x, c1y - 2.54)); sh.power('GND', (c2x, c2y))
    sh.text('Standard 3-pin servo plug (GND, +5 V, signal; e.g. SG90/MG90S for head tilt).\n'
            '+5 V comes from the Pi rail: the servo only moves while the Pi is on. C609 buffers the\n'
            'servo current peaks. R604 keeps the signal low while the ESP32 boots (no twitch). J603 not fitted by default.', (205.74, 93.98), size=1.27)

    # ------------------------------------------------------------------ head connector
    jh = place_part(sh, 'J_HEAD', 'J602', 330.2, 177.8, ref_at=(2.54, -24.13, 'left'), val_at=(2.54, 27.94, 'left'))
    head = {1: '+3V3', 2: '+3V3', 3: 'GND', 4: 'LCD_SCLK', 5: 'GND', 6: 'LCD_MOSI', 7: 'LCD_CS', 8: 'LCD_DC', 9: 'LCD_BL',
            10: 'GND', 11: 'I2C_SCL', 12: 'I2C_SDA', 13: 'TOF_XSHUT', 14: 'TOF_INT', 15: 'GND', 16: 'GND',
            17: None, 18: 'GND', 19: 'TOUCH', 20: 'GND'}
    shapes = {'TOF_INT': 'output', 'TOUCH': 'output', 'I2C_SDA': 'bidirectional'}
    for n, net in head.items():
        if net is None:
            sh.pin_nc(jh, str(n))
        elif net == 'GND':
            sh.pin_power(jh, str(n), 'GND', length=2.54)
        elif net == '+3V3':
            sh.stub(jh, str(n), 2.54); sh.assign(jh, str(n), '+3V3')
        else:
            sh.pin_label(jh, str(n), net, length=12.7, kind='hier', shape=shapes.get(net, 'input'))
    (p1x, p1y), _ = jh.pin('1'); (p2x, p2y), _ = jh.pin('2')
    xv = p1x - 2.54
    sh.wire((xv, p1y), (xv, p2y))
    yt = p1y - 7.62
    sh.wire((xv, p1y), (xv, yt)); sh.power('+3V3', (xv, yt))
    sh.wire((xv, yt), (xv - 12.7, yt))
    vpart_between(sh, 'C_10u_10V', 'C609', xv - 12.7, yt, ('net', '+3V3'), 'GND')
    (mx, my), _ = jh.pin('MP'); sh.assign(jh, 'MP', 'GND')
    sh.wire((mx, my), (mx, my + 2.54)); sh.power('GND', (mx, my + 2.54))
    sh.text('Head signals: LCD SPI (40 MHz), I2C (ToF), TOUCH (AT42QT1010). Pin 17 spare (NC).\n'
            'GND interleaved next to SCLK. Cable ≤ 12 cm. I2C pull-ups on the main board only.',
            (205.74, 228.6), size=1.27)
