from sch import G
from helpers import place_part, vpart_between, cap_rail

def build(sh):
    # ---------------- section frames ----------------
    sh.section('MOTOR DRIVER — TB6612FNG', (20.32, 25.4), (213.36, 180.34))
    sh.section('MOTOR + ENCODER CONNECTORS (JST PH 6p)', (223.52, 25.4), (401.32, 124.46))
    sh.section('ENCODER CONDITIONING', (223.52, 129.54), (401.32, 254.0))
    sh.section('NOTES', (20.32, 185.42), (213.36, 254.0))

    u = place_part(sh, 'U_TB6612', 'U501', 101.6, 109.22, ref_at=(12.7, 13.97, 'left'), val_at=(12.7, 16.51, 'left'))
    # control inputs from the MCU (hierarchical)
    for pin, net in (('STBY', 'MOT_STBY'), ('PWMA', 'MOT_PWMA'), ('PWMB', 'MOT_PWMB'), ('AIN1', 'MOT_AIN1'),
                     ('AIN2', 'MOT_AIN2'), ('BIN1', 'MOT_BIN1'), ('BIN2', 'MOT_BIN2')):
        sh.pin_label(u, pin, net, length=10.16, kind='hier', shape='input')
    # logic supply with its decoupling on the left
    (vx, vy), _ = u.pin('VCC'); sh.assign(u, 'VCC', '+3V3')
    yl = vy - 12.7
    sh.wire((vx, vy), (vx, yl)); sh.power('+3V3', (vx, yl))
    sh.wire((vx, yl), (vx - 25.4, yl))
    vpart_between(sh, 'C_100n', 'C501', vx - 12.7, yl, ('net', '+3V3'), 'GND')
    vpart_between(sh, 'C_10u_10V', 'C510', vx - 25.4, yl, ('net', '+3V3'), 'GND')
    # VM1..VM3 → VSYS with bulk decoupling
    xs = []
    for pin in ('VM1', 'VM2', 'VM3'):
        (px, py), _ = u.pin(pin); xs.append(px); sh.assign(u, pin, 'VSYS')
    yb = vy - 2.54
    for px in xs: sh.wire((px, vy), (px, yb))
    sh.wire((xs[0], yb), (xs[1], yb)); sh.wire((xs[1], yb), (xs[2], yb))
    rail_y = vy - 22.86
    sh.wire((xs[0], yb), (xs[0], rail_y)); sh.power('VSYS', (xs[0], rail_y))
    sh.wire((xs[0], rail_y), (127.0, rail_y))
    cap_rail(sh, 'VSYS', 127.0, rail_y, [('C502', 'C_100u'), ('C503', 'C_22u_25V'), ('C504', 'C_22u_25V'), ('C505', 'C_100n')], dx=15.24)
    sh.text('Next to VM1–VM3', (127.0, rail_y - 3.81), size=1.27, italic=True)
    for pin in ('GND', 'PGND1', 'PGND2'):
        sh.pin_power(u, pin, 'GND', length=2.54)
    # outputs
    for pin, net in (('AO1', 'MOT_L+'), ('AO2', 'MOT_L-'), ('BO1', 'MOT_R+'), ('BO2', 'MOT_R-')):
        sh.pin_label(u, pin, net, length=10.16)
    (ax, ay), _ = u.pin('AO1'); (bx, by), _ = u.pin('BO1')
    sh.text('← left motor (channel A)', (ax + 22.86, ay + 3.175), size=1.27, italic=True)
    sh.text('← right motor (channel B)', (bx + 22.86, by + 3.175), size=1.27, italic=True)

    # ---------------- connectors ----------------
    for j, (ref, side, y0) in enumerate((('J501', 'L', 60.96), ('J502', 'R', 99.06))):
        conn = place_part(sh, 'J_MOTOR', ref, 287.02, y0, ref_at=(-1.27, -8.89, 'left'), val_at=(-1.27, 11.43, 'left'))
        # mirrored motors: the left one has M+/M− swapped at the connector (J501.1 = MOT_L−, J501.6 = MOT_L+)
        m1, m6 = (f'MOT_{side}-', f'MOT_{side}+') if side == 'L' else (f'MOT_{side}+', f'MOT_{side}-')
        sh.pin_label(conn, '1', m1, length=12.7)
        sh.pin_power(conn, '2', 'GND', length=2.54)
        sh.pin_label(conn, '3', f'ENC_{side}_A_RAW', length=12.7)
        sh.pin_label(conn, '4', f'ENC_{side}_B_RAW', length=12.7)
        sh.pin_power(conn, '5', '+3V3', length=2.54)
        sh.pin_label(conn, '6', m6, length=12.7)
        (mx, my), _ = conn.pin('MP'); sh.assign(conn, 'MP', 'GND')
        sh.wire((mx, my), (mx, my + 2.54)); sh.power('GND', (mx, my + 2.54))
        sh.text(('Left motor' if side == 'L' else 'Right motor') + ' — N20 6 V with Hall encoder', (294.64, y0 - 1.27), size=1.27)
    sh.text('GA12-N20 pinout (verify wire colours):\n1 M+  2 GND  3 Enc A  4 Enc B  5 VCC (3V3)  6 M-\n'
            'J501 (left) has M+/M− swapped: the motors are mirrored, so the same logical\n'
            'direction drives both wheels forward and the TB6612 outputs route without crossings.',
            (236.22, 111.76), size=1.27)

    # ---------------- encoder conditioning ----------------
    rows = (('ENC_L_A', 'R501', 'R502', 'C506'), ('ENC_L_B', 'R503', 'R504', 'C507'),
            ('ENC_R_A', 'R505', 'R506', 'C508'), ('ENC_R_B', 'R507', 'R508', 'C509'))
    for i, (net, rpu, rs, cf) in enumerate(rows):
        y = 152.4 + i * 25.4
        x_in, x_node, x_out = 238.76, 251.46, 271.78
        sh.label(net + '_RAW', (x_in, y), (-1, 0))
        sh.wire((x_in, y), (x_node, y))
        pu = vpart_between(sh, 'R_10k', rpu, x_node, y - 7.62, '+3V3', None)
        sh.assign(pu, '2', net + '_RAW')
        r = place_part(sh, 'R_1k', rs, x_node + 10.16, y, rot=90)
        (p1x, p1y), _ = r.pin('1'); (p2x, p2y), _ = r.pin('2')
        sh.wire((x_node, y), (p1x, p1y)); sh.assign(r, '1', net + '_RAW')
        sh.wire((p2x, p2y), (x_out, y)); sh.assign(r, '2', net)
        cc = vpart_between(sh, 'C_1n', cf, x_out, y, None, 'GND')
        sh.assign(cc, '1', net)
        sh.wire((x_out, y), (x_out + 10.16, y))
        sh.hlabel(net, (x_out + 10.16, y), (1, 0), shape='output')
    sh.text('10 kΩ pull-up (open-collector Hall outputs)\nRC filter 1 kΩ / 1 nF: τ = 1 µs, passes >100 kHz', (238.76, 246.38), size=1.27)

    notes = ('• 20 kHz PWM (LEDC) on PWMA/PWMB. Duty-cycle cap = 6.0 V / VSYS (6 V motors; 71 % at 8.4 V).\n'
             '• STBY has an internal 200 kΩ pull-down: the motors stay in standby while the ESP32-S3 boots.\n'
             '• VM straight from VSYS (6.2–8.4 V; TB6612 rated 15 V abs., 13.5 V operating). 1.2 A avg / 3.2 A peak per channel.\n'
             '• VM decoupling: 100 µF electrolytic (its ESR damps) + 2×22 µF + 100 nF tight to VM1–VM3 (see SIM1).\n'
             '• Stall: firmware cuts the channel if PWM > 50 % and the encoder does not count for 300 ms.')
    sh.text(notes, (24.13, 195.58), size=1.27)
