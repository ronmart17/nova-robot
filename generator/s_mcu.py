"""Sheet 4 — ESP32-S3-WROOM-1-N16R8, reset/boot, series termination, TCA9535 expander, pull-ups, LED and UART."""
from sch import G
from helpers import place_part, vpart_between, cap_rail

def build(sh):
    sh.section('MICROCONTROLLER — ESP32-S3-WROOM-1-N16R8', (20.32, 25.4), (215.9, 254.0))
    sh.section('I/O EXPANDER — TCA9535 (I2C 0x20)', (220.98, 25.4), (401.32, 137.16))
    sh.section('PULL-UPS, STATUS LED AND DEBUG', (220.98, 142.24), (401.32, 248.92))

    # ------------------------------------------------------------------ ESP32-S3
    ux, uy = 116.84, 99.06
    u = place_part(sh, 'U_ESP32', 'U401', ux, uy, ref_at=(-12.7, 28.575, 'left'), val_at=(2.54, 28.575, 'left'))
    XL, XR = 76.2, 157.48
    # Pin assignment follows the board layout (Rev B): signals that run to the rear of the board (motor bridge,
    # encoders, charger, USB) sit on the module's right column and the right half of its bottom row; signals that
    # go to the front (display, servo) leave from the top row; the short Pi-link signals use the bottom-left pins.
    # LCD MOSI/SCLK stay on the FSPI IO_MUX pins (IO11/IO12) for full SPI speed.
    left_h = {'IO1': ('PI_PWR_OFF', 'output'), 'IO2': ('CLIFF_INT', 'input'), 'IO3': ('IRQ_N', 'input'),
              'IO6': ('PI_PWROFF', 'input'),
              'IO7': ('PI_SHDN_REQ', 'output'), 'IO8': ('I2C_SDA', 'bidirectional'), 'IO9': ('I2C_SCL', 'output'),
              'IO10': ('MOT_BIN1', 'output'), 'IO13': ('MOT_AIN2', 'output'), 'IO14': ('MOT_PWMA', 'output')}
    left_h.update({'EN': ('ESP_EN', 'bidirectional'), 'IO0': ('ESP_BOOT', 'bidirectional'),
                   'IO15': ('ENC_L_A', 'input'), 'IO16': ('ENC_L_B', 'input')})
    left_l = {'IO11': 'LCD_MOSI_MCU', 'IO12': 'LCD_SCLK_MCU', 'IO4': 'UART_TX', 'IO5': 'UART_RX'}   # UART1 → J401 (debug)
    for pin, (net, shape) in left_h.items():
        (px, py), _ = u.pin(pin)
        sh.wire((px, py), (XL, py)); sh.assign(u, pin, net)
        sh.hlabel(net, (XL, py), (-1, 0), shape)
    for pin, net in left_l.items():
        (px, py), _ = u.pin(pin)
        sh.wire((px, py), (XL + 10.16, py)); sh.assign(u, pin, net)
        sh.label(net, (XL + 10.16, py), (-1, 0))
    right_h = {'IO21': ('MOT_AIN1', 'output'), 'IO38': ('LCD_DC', 'output'), 'IO40': ('LCD_BL', 'output'),
               'IO41': ('SERVO_PWM', 'output'), 'IO42': ('LCD_CS', 'output'), 'IO45': ('MOT_STBY', 'output'),
               'IO47': ('MOT_BIN2', 'output'), 'IO17': ('ENC_R_A', 'input'), 'IO18': ('ENC_R_B', 'input'),
               'IO48': ('MOT_PWMB', 'output'),
               # UART0 to the Pi: the ROM serial bootloader only listens on UART0 (or USB), so the Pi can flash
               # the ESP32 with esptool after holding GPIO0 low and pulsing EN (Q702/Q703)
               'TXD0': ('UART_PI_TX', 'output'), 'RXD0': ('UART_PI_RX', 'input')}
    right_l = {}
    for pin, (net, shape) in right_h.items():
        (px, py), _ = u.pin(pin)
        sh.wire((px, py), (XR, py)); sh.assign(u, pin, net)
        sh.hlabel(net, (XR, py), (1, 0), shape)
    for pin, net in right_l.items():
        (px, py), _ = u.pin(pin)
        sh.wire((px, py), (XR - 10.16, py)); sh.assign(u, pin, net)
        sh.label(net, (XR - 10.16, py), (1, 0))
    for pin in ('IO35', 'IO36', 'IO37'):
        sh.pin_nc(u, pin)
    (px, py), _ = u.pin('IO36')
    sh.text('Octal PSRAM (do not use)', (px + 3.81, py + 0.635), size=1.27, italic=True)
    for pin in ('IO39', 'IO46'):                     # spare (GPIO46 is a strap: internal pull-down)
        sh.pin_nc(u, pin)
    # native USB (GPIO19/20) on bottom-side test pads under the module: development flashing / JTAG only. In the robot
    # the ESP32 is flashed by the Pi over UART0; the USB-C port is only the charging input (BC1.2 on its D+/D−).
    for pin, tp, net in (('13', 'TP401', 'ESP_USB_DM'), ('14', 'TP402', 'ESP_USB_DP')):
        (px, py), _ = u.pin(pin)
        sh.wire((px, py), (px + 7.62, py)); sh.assign(u, pin, net)
        t = place_part(sh, 'TP', tp, px + 7.62, py, rot=270, ref_at=(5.08, 0, 'left'), hide_value=True, val_at=(5.08, 0, 'left'))
        sh.assign(t, '1', net)
    tg = place_part(sh, 'TP', 'TP403', 190.5, 167.64, rot=0, ref_at=(1.27, -3.81, 'left'), hide_value=True, val_at=(1.27, -3.81, 'left'))
    sh.pin_power(tg, '1', 'GND', length=2.54)
    sh.text('TP401/TP402/TP403: native USB D−/D+/GND\n(bottom pads under U401, development only)', (180.34, 182.88), size=1.27, italic=True)
    # supply and decoupling next to pin 2
    (vx, vy), _ = u.pin('3V3'); sh.assign(u, '3V3', '+3V3')
    yr = vy - 12.7
    sh.wire((vx, vy), (vx, yr)); sh.power('+3V3', (vx, yr))
    sh.wire((vx, yr), (vx + 12.7, yr))
    cap_rail(sh, '+3V3', vx + 12.7, yr, [('C401', 'C_22u_10V'), ('C402', 'C_100n')], dx=12.7)
    sh.text('Next to the 3V3 pin', (vx + 12.7, yr - 3.81), size=1.27, italic=True)
    sh.pin_power(u, 'GND', 'GND', length=2.54)

    # ------------------------------------------------------------------ reset and boot
    sh.text('RESET AND BOOT', (25.4, 152.4), size=1.524, bold=True)
    y = 167.64
    sh.hlabel('ESP_EN', (33.02, y), (-1, 0), 'bidirectional'); sh.wire((33.02, y), (71.12, y))
    vpart_between(sh, 'R_10k', 'R401', 40.64, y - 7.62, '+3V3', ('net', 'ESP_EN'))
    vpart_between(sh, 'C_1u', 'C403', 55.88, y, ('net', 'ESP_EN'), 'GND')
    sw = place_part(sh, 'SW_PUSH', 'SW401', 71.12, y + 5.08, rot=270, ref_at=(3.81, -1.27, 'left'), val_at=(3.81, 1.27, 'left'))
    (s1x, s1y), _ = sw.pin('1'); (s2x, s2y), _ = sw.pin('2')
    top, bot = ('1', '2') if s1y < s2y else ('2', '1')
    sh.assign(sw, top, 'ESP_EN'); sh.pin_power(sw, bot, 'GND', length=0)
    sh.text('RESET', (74.93, y + 10.16), size=1.27, italic=True)
    xb = 91.44
    sh.hlabel('ESP_BOOT', (xb, y), (-1, 0), 'bidirectional'); sh.wire((xb, y), (106.68, y))
    sw2 = place_part(sh, 'SW_PUSH', 'SW402', 106.68, y + 5.08, rot=270, ref_at=(3.81, -1.27, 'left'), val_at=(3.81, 1.27, 'left'))
    (s1x, s1y), _ = sw2.pin('1'); (s2x, s2y), _ = sw2.pin('2')
    top, bot = ('1', '2') if s1y < s2y else ('2', '1')
    sh.assign(sw2, top, 'ESP_BOOT'); sh.pin_power(sw2, bot, 'GND', length=0)
    sh.text('BOOT (GPIO0)', (110.49, y + 10.16), size=1.27, italic=True)
    sh.text('EN: RC 10 kΩ / 1 µF (τ = 10 ms): the ESP32 starts\nonce 3V3 is already stable.\n'
            'GPIO0 has internal pull-up: BOOT + RESET = download.\nDevelopment: native USB (GPIO19/20) on test pads TP401–TP403;\nthe Pi can also reset/boot the ESP32 (sheet 7) and flash it over UART0\n(ROM bootloader, esptool on /dev/serial0).',
            (25.4, 190.5), size=1.27)

    # ------------------------------------------------------------------ series termination
    sh.text('33 Ω SERIES TERMINATION (place next to U401)', (132.08, 152.4), size=1.524, bold=True)
    series = (('R402', 'LCD_MOSI', 'output'), ('R403', 'LCD_SCLK', 'output'))
    for i, (ref, net, shape) in enumerate(series):
        yy = 162.56 + i * 10.16
        r = place_part(sh, 'R_33', ref, 160.02, yy, rot=90)
        (ax, ay), _ = r.pin('1'); (bx, by), _ = r.pin('2')
        lx, hx = (min(ax, bx) - 7.62, max(ax, bx) + 7.62)
        sh.wire((min(ax, bx), ay), (lx, ay)); sh.wire((max(ax, bx), ay), (hx, ay))
        left_pin = '1' if ax < bx else '2'; right_pin = '2' if left_pin == '1' else '1'
        sh.assign(r, left_pin, net + '_MCU'); sh.label(net + '_MCU', (lx, ay), (-1, 0))
        sh.assign(r, right_pin, net); sh.hlabel(net, (hx, ay), (1, 0), shape)

    notes = ('NOTES\n'
             '• Strapping: GPIO45 (VDD_SPI) only drives MOT_STBY with pull-down → 3.3 V flash. GPIO46: test point only (internal pull-down).\n'
             '• GPIO3 → IRQ_N (JTAG on GPIO3 only if the eFuse is burned). GPIO35–37: octal PSRAM, do not use.\n'
             '• GPIO1 (RTC GPIO, held in deep sleep) → PI_PWR_OFF (high = Pi rail off). UART0 (GPIO43/44) = link to the Pi (also ROM download);\n  GPIO4/5 = UART1 on the debug header J401. GPIO41 → servo PWM. Pin map chosen for the board layout (rear signals on the right column).\n'
             '• GPIO19/20: native USB on test pads only (short stubs). 33 Ω series on the display SPI: limits edge rates into the head cable.\n'
             '• Antenna at the left board edge: keep-out (no copper, all layers) under and around the antenna.')
    sh.text(notes, (25.4, 223.52), size=1.27)

    # ------------------------------------------------------------------ expander
    ex, ey = 309.88, 83.82
    e = place_part(sh, 'U_TCA9535', 'U402', ex, ey, ref_at=(-12.7, -24.765, 'left'), val_at=(1.27, 24.765, 'left'))
    for pin, net, shape in (('SDA', 'I2C_SDA', 'bidirectional'), ('SCL', 'I2C_SCL', 'input'), ('~{INT}', 'IRQ_N', 'output')):
        (px, py), _ = e.pin(pin)
        sh.wire((px, py), (271.78, py)); sh.assign(e, pin, net); sh.hlabel(net, (271.78, py), (-1, 0), shape)
    xa = 284.48
    pa = [e.pin(p)[0] for p in ('A2', 'A1', 'A0')]
    for (px, py), pn in zip(pa, ('A2', 'A1', 'A0')):
        sh.wire((px, py), (xa, py)); sh.assign(e, pn, 'GND')
    sh.wire((xa, pa[0][1]), (xa, pa[-1][1] + 2.54)); sh.power('GND', (xa, pa[-1][1] + 2.54))
    sh.text('A2..A0 = 0 → 0x20', (256.54, pa[0][1] - 3.81), size=1.27, italic=True)
    ports = {'P00': ('TOF_XSHUT', 'output'), 'P01': ('CLIFF_L_XSHUT', 'output'),
             'P04': ('IMU_INT1', 'input'), 'P05': ('TOF_INT', 'input'), 'P06': ('CLIFF_R_XSHUT', 'output'),
             'P07': ('PI_ON', 'input'), 'P10': ('TOUCH', 'input')}
    for pin, (net, shape) in ports.items():
        sh.pin_label(e, pin, net, length=17.78, kind='hier', shape=shape)
    sh.pin_power(e, 'P02', 'GND', length=7.62)             # spare input, tied low (configure as input only)
    sh.pin_label(e, 'P03', 'LED_STAT', length=48.26)
    sh.pin_label(e, 'P11', 'VBUS_DET', length=17.78, kind='hier', shape='input')
    sh.pin_label(e, 'P12', 'PI_5V_PG', length=17.78, kind='hier', shape='input')
    # P13–P17 unused: 10 kΩ to GND (TI: do not leave inputs floating); staircase fan-out without crossings
    pulls = [('P13', 'R414'), ('P14', 'R415'), ('P15', 'R416'), ('P16', 'R417'), ('P17', 'R418')]
    cols = [345.44 + i * 10.16 for i in range(5)]
    ytop = 111.76
    for i, (pin, ref) in enumerate(pulls):
        (px, py), _ = e.pin(pin); xc = cols[4 - i]
        sh.wire((px, py), (xc, py)); sh.wire((xc, py), (xc, ytop)); sh.assign(e, pin, f'EXP_{pin}')
        r = vpart_between(sh, 'R_10k', ref, xc, ytop, ('net', f'EXP_{pin}'), None)
        (bx, by), _ = r.pin('2'); sh.assign(r, '2', 'GND'); sh.wire((bx, by), (bx, by + 2.54))
    yb = ytop + 7.62 + 2.54
    sh.wire((cols[0], yb), (cols[-1], yb)); sh.power('GND', (cols[0] - 5.08, yb)); sh.wire((cols[0] - 5.08, yb), (cols[0], yb))
    sh.text('P13–P17 unused: 10 kΩ to GND', (345.44, 129.54), size=1.27, italic=True)
    (vx, vy), _ = e.pin('VCC'); sh.assign(e, 'VCC', '+3V3')
    yr = vy - 10.16
    sh.wire((vx, vy), (vx, yr)); sh.power('+3V3', (vx, yr))
    sh.wire((vx, yr), (vx + 12.7, yr))
    cap_rail(sh, '+3V3', vx + 12.7, yr, [('C404', 'C_100n')])
    sh.pin_power(e, 'GND', 'GND', length=2.54)
    sh.text('At power-up all ports are inputs (high impedance):\n'
            'P02 spare (tied to GND: keep it an input);\n'
            'CLIFF_x_XSHUT with pull-down → cliff ToFs off (address set one by one);\n'
            'TOF_XSHUT with pull-up on the head board → head ToF active.', (226.06, 119.38), size=1.27)

    # ------------------------------------------------------------------ pull-ups, LED, UART
    xs = [233.68, 246.38, 259.08, 271.78, 284.48]
    for x, (ref, key, net, shape) in zip(xs, (('R408', 'R_2k2', 'I2C_SDA', 'bidirectional'), ('R409', 'R_2k2', 'I2C_SCL', 'input'),
                                              ('R410', 'R_10k', 'IRQ_N', 'input'), ('R411', 'R_10k', 'CLIFF_INT', 'input'),
                                              ('R419', 'R_10k', 'TOF_INT', 'input'))):
        r = vpart_between(sh, key, ref, x, 162.56, '+3V3', None)
        (bx, by), _ = r.pin('2'); sh.assign(r, '2', net)
        sh.wire((bx, by), (bx, by + 7.62))
        sh.hlabel(net, (bx, by + 7.62), (0, 1), shape)
    sh.text('I2C pull-ups 2.2 kΩ: 400 kHz with ~150 pF\n(BQ25798, TCA9535, LSM6DSOX, 3× VL53Lx and cable).\n'
            'IRQ_N: BQ25798 and TCA9535 INT outputs, open-drain, wired-OR.\nCLIFF_INT: both VL53L4CD GPIO1 (open-drain), wired-OR.', (226.06, 203.2), size=1.27)
    rt = vpart_between(sh, 'R_100k', 'R420', 297.18, 170.18, None, 'GND')
    (tx, ty), _ = rt.pin('1'); sh.assign(rt, '1', 'TOUCH'); sh.wire((tx, ty), (tx, ty - 2.54)); sh.hlabel('TOUCH', (tx, ty - 2.54), (0, -1), 'input')
    rl = vpart_between(sh, 'R_1k', 'R412', 309.88, 162.56, '+3V3', None)
    d = place_part(sh, 'LED_G', 'D401', 309.88, 180.34, rot=90)
    sh.connect('LED_STAT_A', (rl, '2'), (d, '2'))
    sh.pin_label(d, '1', 'LED_STAT', length=5.08)
    sh.text('Status LED: active low,\ndriven from expander P03', (299.72, 203.2), size=1.27)
    j = place_part(sh, 'J_DBG', 'J401', 375.92, 175.26, mirror='x', dnp=True, ref_at=(-1.27, -8.89, 'left'), val_at=(-1.27, 8.89, 'left'))
    for pin, kind, dy in (('4', '+3V3', -5.08), ('1', 'GND', 5.08)):
        (px, py), _ = j.pin(pin)
        sh.wire((px, py), (px - 5.08, py)); sh.wire((px - 5.08, py), (px - 5.08, py + dy))
        sh.power(kind, (px - 5.08, py + dy)); sh.assign(j, pin, kind)
    sh.pin_label(j, '2', 'UART_TX', length=10.16)
    sh.pin_label(j, '3', 'UART_RX', length=10.16)
    sh.text('Debug UART1 (GPIO4/5, not fitted).\nTX/RX as seen from the ESP32.', (345.44, 203.2), size=1.27)
