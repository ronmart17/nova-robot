"""Sheet 7 — Raspberry Pi 5: GPIO link (2x6 IDC ribbon to header pins 1-12) and the USB-C 5 V power output."""
from sch import G
from helpers import place_part, vpart_between, cap_rail, place_vertical_k_top

# Pi header pins 1-12 as seen on the 2x6 box header (straight IDC ribbon: pin n <-> pin n)
PI_PINS = {1: 'PI_3V3', 2: None, 3: None, 4: None, 5: 'PI_SHDN_N', 6: 'GND', 7: 'PI_GPIO4', 8: 'PI_TXD',
           9: 'GND', 10: 'PI_RXD', 11: 'PI_GPIO17', 12: 'PI_GPIO18'}

def hfet(sh, ref, rg, rpd, x, y, gate_net, drain_net, src_label, src_shape='input'):
    """2N7002 with series gate resistor and gate pull-down. (x, y) = transistor anchor.
    gate_net: name of the net at the far side of the gate resistor (hier/local label).
    drain_net: (label, kind) of the drain."""
    q = place_part(sh, 'Q_2N7002', ref, x, y)
    (dx, dy), _ = q.pin('D'); (gx, gy), _ = q.pin('G')
    sh.pin_power(q, 'S', 'GND', length=2.54)
    gn = f'{ref}_G'
    r = place_part(sh, 'R_100', rg, gx - 15.24, gy, rot=90)
    sh.connect(gn, (r, '2'), (q, 'G'))
    vpart_between(sh, 'R_100k', rpd, gx - 5.08, gy, ('net', gn), 'GND')
    (r1x, r1y), _ = r.pin('1')
    sh.wire((r1x, r1y), (r1x - 7.62, r1y)); sh.assign(r, '1', gate_net)
    if src_label == 'hier':
        sh.hlabel(gate_net, (r1x - 7.62, r1y), (-1, 0), src_shape)
    else:
        sh.label(gate_net, (r1x - 7.62, r1y), (-1, 0))
    net, kind = drain_net
    sh.wire((dx, dy), (dx, dy - 5.08)); sh.assign(q, 'D', net)
    if kind == 'hier':
        sh.hlabel(net, (dx, dy - 5.08), (0, -1), 'output')
    else:
        sh.label(net, (dx, dy - 5.08), (0, -1))
    return q

def build(sh):
    sh.section('RASPBERRY PI 5 GPIO LINK — 2×6 IDC RIBBON TO HEADER PINS 1–12', (20.32, 25.4), (243.84, 254.0))
    sh.section('PI POWER OUTPUT — USB-C SOURCE, 5.15 V / 5 A', (248.92, 25.4), (401.32, 137.16))
    sh.section('NOTES', (248.92, 142.24), (401.32, 248.92))

    # ------------------------------------------------------------------ 2x6 box header
    j = place_part(sh, 'J_PI', 'J701', 129.54, 88.9, ref_at=(-2.54, -10.16, 'left'), val_at=(-2.54, 12.7, 'left'))
    for n, net in PI_PINS.items():
        if net is None:
            sh.pin_nc(j, str(n))
        elif net == 'GND':
            (px, py), (ddx, _) = j.pin(str(n))
            sh.pin_power(j, str(n), 'GND', length=2.54)
        else:
            sh.pin_label(j, str(n), net, length=12.7)
    sh.text('Pins 2/4 = Pi 5 V and pin 3 = GPIO2:\nnot connected (the Pi is powered by USB-C)', (99.06, 116.84), size=1.27, italic=True)

    # ------------------------------------------------------------------ PI_3V3 -> PI_ON (expander)
    sh.text('PI ALIVE (Pi 3.3 V rail)', (25.4, 38.1), size=1.524, bold=True)
    r = vpart_between(sh, 'R_10k', 'R709', 50.8, 55.88, ('label', 'PI_3V3', 2.54), None)
    r2 = vpart_between(sh, 'R_100k', 'R710', 50.8, 68.58, None, 'GND')
    sh.connect('PI_ON', (r, '2'), (r2, '1'))
    sh.wire((50.8, 66.04), (66.04, 66.04)); sh.hlabel('PI_ON', (66.04, 66.04), (1, 0), 'output')
    sh.text('PI_ON = 1 while the Pi 3.3 V rail is up\n(→ expander P07). 100k keeps it at 0 V when off.', (25.4, 86.36), size=1.27)
    sh.power('PWR_FLAG', (81.28, 50.8)); sh.wire((81.28, 50.8), (81.28, 55.88)); sh.label('PI_3V3', (81.28, 55.88), (0, 1))
    sh.text('PI_3V3 comes from the Pi (J701 pin 1)', (73.66, 45.72), size=1.27, italic=True)

    # ------------------------------------------------------------------ UART: Pi TXD -> ESP32 RX (1k), ESP32 TX -> buffer -> Pi RXD
    sh.text('UART (ESP32 UART0 ↔ Pi UART0, GPIO14/15)', (25.4, 132.08), size=1.524, bold=True)
    rt = place_part(sh, 'R_1k', 'R701', 55.88, 144.78, rot=90)
    (a, _), (b, _) = rt.pin('1'), rt.pin('2')
    lp, rp = ('1', '2') if a[0] < b[0] else ('2', '1')
    (lx, ly), _ = rt.pin(lp); (rx, ry), _ = rt.pin(rp)
    sh.wire((lx, ly), (lx - 7.62, ly)); sh.label('PI_TXD', (lx - 7.62, ly), (-1, 0)); sh.assign(rt, lp, 'PI_TXD')
    sh.wire((rx, ry), (rx + 10.16, ry)); sh.hlabel('UART_PI_RX', (rx + 10.16, ry), (1, 0), 'output'); sh.assign(rt, rp, 'UART_PI_RX')
    sh.text('1 kΩ: limits current if only one side is powered', (25.4, 152.4), size=1.27, italic=True)
    u = place_part(sh, 'U_LVC1G125', 'U701', 63.5, 182.88, ref_at=(5.08, -10.16, 'left'), val_at=(5.08, -7.62, 'left'))
    (ax, ay), _ = u.pin('2'); sh.assign(u, '2', 'UART_PI_TX')
    sh.wire((ax, ay), (ax - 10.16, ay)); sh.hlabel('UART_PI_TX', (ax - 10.16, ay), (-1, 0), 'input')
    sh.pin_label(u, '4', 'PI_RXD', length=10.16)
    (ox, oy), _ = u.pin('1'); sh.assign(u, '1', 'GND')
    sh.wire((ox, oy), (ox, oy - 5.08)); sh.power('GND', (ox, oy - 5.08), rot=180)
    (vx, vy), _ = u.pin('5'); sh.assign(u, '5', 'PI_3V3')
    sh.wire((vx, vy), (vx, vy - 7.62)); sh.wire((vx, vy - 7.62), (vx - 15.24, vy - 7.62)); sh.label('PI_3V3', (vx - 15.24, vy - 7.62), (-1, 0))
    vpart_between(sh, 'C_100n', 'C703', vx - 7.62, vy - 7.62, ('net', 'PI_3V3'), 'GND')
    sh.pin_power(u, '3', 'GND', length=2.54)
    sh.text('U701 runs from the Pi 3.3 V rail: with the Pi off its\noutput is high-Z (Ioff), so the ESP32 TX cannot back-power\nthe Pi through GPIO15. OE tied low = always enabled.',
            (25.4, 210.82), size=1.27)

    # ------------------------------------------------------------------ Pi GPIO4 (gpio-poweroff) -> ESP32
    sh.text('POWER-OFF HANDSHAKE AND REMOTE RESET', (162.56, 132.08), size=1.524, bold=True)
    rp4 = place_part(sh, 'R_1k', 'R702', 175.26, 144.78, rot=90)
    (a, _), (b, _) = rp4.pin('1'), rp4.pin('2')
    lp, rpn = ('1', '2') if a[0] < b[0] else ('2', '1')
    (lx, ly), _ = rp4.pin(lp); (rx, ry), _ = rp4.pin(rpn)
    sh.wire((lx, ly), (lx - 7.62, ly)); sh.label('PI_GPIO4', (lx - 7.62, ly), (-1, 0)); sh.assign(rp4, lp, 'PI_GPIO4')
    sh.wire((rx, ry), (rx + 15.24, ry)); sh.hlabel('PI_PWROFF', (rx + 15.24, ry), (1, 0), 'output'); sh.assign(rp4, rpn, 'PI_PWROFF')
    vpart_between(sh, 'R_100k', 'R703', rx + 7.62, ry, ('net', 'PI_PWROFF'), 'GND')
    # shutdown request: ESP32 -> Q701 -> Pi GPIO3 (open drain, 1.8k pull-up on the Pi)
    hfet(sh, 'Q701', 'R704', 'R705', 205.74, 187.96, 'PI_SHDN_REQ', ('PI_SHDN_N', 'local'), 'hier', 'input')
    # remote reset / boot of the ESP32 from the Pi (firmware update over UART)
    hfet(sh, 'Q702', 'R706', 'R707', 132.08, 187.96, 'PI_GPIO17', ('ESP_EN', 'hier'), 'local')
    hfet(sh, 'Q703', 'R708', 'R711', 132.08, 228.6, 'PI_GPIO18', ('ESP_BOOT', 'hier'), 'local')
    sh.text('Q701: ESP32 → GPIO3 low = shutdown request\n(dtoverlay=gpio-shutdown, default GPIO3).', (162.56, 210.82), size=1.27)
    sh.text('Q702/Q703: Pi GPIO17/18 hold ESP32 EN / GPIO0\nlow → the Pi can flash the ESP32 over UART.\nGPIO17/18 default to pull-down: no effect at boot.',
            (162.56, 228.6), size=1.27)

    # ------------------------------------------------------------------ USB-C power output
    jc = place_part(sh, 'J_USBC', 'J702', 279.4, 76.2, ref_at=(-10.16, -20.955, 'left'), val_at=(-10.16, -18.415, 'left'))
    (vx, vy), _ = jc.pin('A4'); sh.assign(jc, 'A4', '+5V')
    xj, yr = vx + 5.08, vy - 10.16                      # VBUS rises to a rail above the CC resistors
    sh.wire((vx, vy), (xj, vy), (xj, yr))
    sh.wire((xj, yr), (xj + 7.62, yr)); sh.power('+5V', (xj + 7.62, yr))
    xs = 353.06
    sh.wire((xj + 7.62, yr), (xs + 25.4, yr))
    for pin, ref, xr in (('A5', 'R712', 309.88), ('B5', 'R713', 322.58)):
        (cx, cy), _ = jc.pin(pin)
        net = f'PI_CC{pin[0] == "A" and 1 or 2}'
        sh.wire((cx, cy), (xr, cy)); sh.assign(jc, pin, net)
        r = vpart_between(sh, 'R_10k', ref, xr, yr, ('net', '+5V'), ('net', net))
        (r2x, r2y), _ = r.pin('2')
        sh.wire((r2x, r2y), (xr, cy))
    for p in ('A7', 'B7', 'A6', 'B6', 'A8', 'B8'):
        sh.pin_nc(jc, p)
    sh.pin_power(jc, 'A1', 'GND', length=2.54)
    sh.pin_power(jc, 'SHIELD', 'GND', length=2.54)
    cap_rail(sh, '+5V', xs, yr, [('C701', 'C_22u_10V'), ('C702', 'C_100n')], dx=12.7)
    tv = place_vertical_k_top(sh, 'D_TVS_6V', 'D701', xs + 25.4, yr + 7.62, fpos='right')
    (kx, ky), _ = tv.pin('1'); (ax2, ay2), _ = tv.pin('2')
    sh.assign(tv, '1', '+5V'); sh.assign(tv, '2', 'GND')
    sh.wire((kx, ky), (kx, yr)); sh.power('GND', (ax2, ay2))
    sh.text('Rp = 10 kΩ on CC1/CC2: USB-C source advertising 3 A.\nThe Pi 5 runs at full power with PSU_MAX_CURRENT=5000\n(EEPROM) and usb_max_current_enable=1 (config.txt).\n'
            'Short USB-C ↔ USB-C cable (≈ 15 cm); right-angle plug into J702\n(the main board has a notch under the plug overmold).', (254.0, 109.22), size=1.27)

    notes = ('NOTES\n'
             '• J701: 2×6 shrouded box header, straight 12-way IDC ribbon\n'
             '  (2×6 female IDC on both ends) to Pi header pins 1–12.\n'
             '• Pi config.txt:\n'
             '    dtparam=uart0=on                  (GPIO14/15)\n'
             '    dtoverlay=gpio-shutdown           (GPIO3, active low)\n'
             '    dtoverlay=gpio-poweroff,gpiopin=4,timeout_ms=5000\n'
             '    usb_max_current_enable=1\n'
             '• Pi EEPROM: PSU_MAX_CURRENT=5000.\n'
             '• gpio-poweroff on the Pi 5 pulses (active 100 ms, inactive\n'
             '  100 ms, active): the ESP32 latches the FIRST rising edge.\n'
             '• Power sequence: ESP32 sends SHUTDOWN over UART (or pulls\n'
             '  GPIO3 low through Q701), waits for PI_PWROFF, waits 300 ms\n'
             '  and then switches the 5 V buck off (PI_PWR_OFF, sheet 3).')
    sh.text(notes, (254.0, 152.4), size=1.27)
