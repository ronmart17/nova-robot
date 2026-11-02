"""Main board Rev B — component placement in the ROBOT frame (X to the right, Y forward, mm from the axle centre).
KiCad local = (X, −Y); a 2-pad part at angle 0 has pad 1 towards −X, 180 → +X, 90 → rear (−Y), 270 → front (+Y).

Zoning (see mech/out/layout_zoning.png):
  rear centre ... USB-C input (J201), power switch (SW301), dock lead (J203, bottom)
  rear right .... BQ25798 charger with the two input FET pairs, 2S battery connector, fuse and protector
  rear left ..... always-on 3.3 V buck
  under the pack  TB6612 motor bridge + motor connectors and the IMU (bottom side, near the turning axis)
  front left .... ESP32-S3 (antenna at the left edge), IO expander, Pi GPIO link (J701) and its buffers
  front right ... 5.15 V / 5 A Pi buck and the Pi USB-C output (J702)
  front centre .. head connector (J602) and servo header; cliff ToF sensors (bottom) at the front corners
"""
import math

def put(pc, ref, X, Y, a=0, side='F'):
    return pc.P(ref, X, -Y, a % 360, side)

def block(pc, origin, items, side='F', mirror=False):
    """Items (ref, dX, dY, a[, side]) relative to origin (robot frame). mirror=True mirrors X (for bottom-side
    copies of a top-side arrangement): dX → −dX and the angle → 180 − a."""
    ox, oy = origin
    for it in items:
        ref, dx, dy, a = it[:4]
        sd = it[4] if len(it) > 4 else side
        if mirror:
            dx, a = -dx, (180 - a)
        put(pc, ref, ox + dx, oy + dy, a, sd)

def place_all(b, Placer, D):
    pc = Placer(b)
    P = lambda ref, X, Y, a=0, side='F': put(pc, ref, X, Y, a, side)

    # ================================================================ mechanics
    for i, (X, Y) in enumerate(D.SHELL_HOLES):                     # H1..H4 shell (corners)
        P(f'H{i + 1}', X, Y)
    ph = [D.pi_xy(u, v) for u, v in D.PI_HOLES_UV]                 # H5..H8 Pi standoffs
    for i, (X, Y) in enumerate(sorted(ph, key=lambda p: (-p[1], p[0]))):
        P(f'H{i + 5}', X, Y)
    P('H9', D.HEAD_BRK[0][0], D.HEAD_BRK[0][1]); P('H10', D.HEAD_BRK[1][0], D.HEAD_BRK[1][1])
    P('FID1', -20.0, 49.5); P('FID2', 60.0, 44.0); P('FID3', -40.0, -58.0)

    # ================================================================ rear centre: USB-C input, ESD, switch
    P('J201', 0.0, -64.8, 0)
    P('U201', 0.0, -56.4, 90)
    P('R201', -3.4, -58.6, 90); P('R202', 3.4, -58.6, 90)
    P('D201', -8.8, -62.4, 180); P('C201', -8.8, -59.4, 180)
    P('R203', -6.4, -55.4, 90); P('R204', -7.6, -55.4, 90)
    P('R205', 3.6, -53.2, 0); P('R206', 3.6, -52.0, 0)
    P('SW301', -15.6, -65.75, 0)   # mounting tabs 0.4 mm inside the rear edge; actuator slightly recessed in the skirt
    P('R306', -15.0, -60.2, 0); P('R307', -15.0, -59.0, 0)
    # dock lead (bottom side) with its TVS / capacitor on top
    P('J203', 11.0, -63.2, 0, 'B')
    P('D202', 12.2, -58.0, 180); P('C202', 12.2, -55.4, 180)

    # ================================================================ charger BQ25798 (rear right) + input FET pairs
    UX, UY = 32.0, -47.0
    P('U202', UX, UY, 0)
    P('Q201', 18.2, -48.0, 180); P('Q202', 22.2, -48.0, 0)          # pair 1: USB-C (VAC1)
    P('Q203', 18.2, -53.6, 180); P('Q204', 22.2, -53.6, 0)          # pair 2: dock (VAC2)
    block(pc, (UX, UY), [
        ('C209', -0.95, 2.95, 0),         # PMID 100 nF (pad 1 PMID, pad 2 GND) on the IC layer
        ('C215', 0.95, 2.95, 180),        # SYS 100 nF
        ('L201', 0.0, 8.6, 0),          # pad 1 SW1, pad 2 SW2 — SW nodes on B.Cu (vias under the IC)
        # bulk caps with the power pad at the bottom (rear) on a corridor under the inductor, GND at the top
        ('C206', -6.6, 6.6, 90), ('C207', -8.6, 6.6, 90), ('C208', -10.6, 6.6, 90),          # PMID 3×10 µF
        ('C210', 6.6, 6.6, 90), ('C211', 8.6, 6.6, 90), ('C212', 10.6, 6.6, 90),             # SYS 5×10 µF
        ('C213', 12.6, 6.6, 90), ('C214', 14.6, 6.6, 90),
        ('C216', 4.0, 2.4, 90), ('C217', 6.0, 2.4, 90),           # BAT 2×10 µF: VBAT pads down on the BAT pour, GND pads up
        ('C205', -3.4, 1.0, 180),                                  # VBUS 100 nF (pad 1 right)
        ('C203', -6.1, 1.9, 0), ('C204', -6.1, 3.9, 0),           # VBUS 2×10 µF
        ('C218', -6.3, 0.0, 180),                                  # REGN 4.7 µF
        ('C221', 2.4, 0.95, 0, 'B'),                               # SDRV 1 nF (bottom, via next to pin 24)
        ('C219', -1.9, 0.1, 0, 'B'), ('C220', 1.9, -0.1, 180, 'B'),  # bootstraps (bottom, TI layout guide)
        ('R213', 4.4, -0.0, 0),         # PROG 8.2k
        ('R215', 4.4, -1.2, 0),         # BATP 100 R
        ('R210', 6.8, -1.6, 90), ('R212', 8.0, -1.6, 90),          # ILIM divider
        ('R207', 6.8, -4.4, 90), ('R208', 8.0, -4.4, 90), ('R209', 9.2, -4.4, 90),   # TS
        ('R214', 0.2, -4.0, 90),        # CE pull-down
        ('TP201', -3.0, -6.6, 0, 'B'),  # QON test pad on the bottom: keeps the IC's lower-left escape free
    ])
    P('J202', 45.0, -54.6, 0)                                     # pack NTC
    P('TP301', 40.0, -36.0); P('TP306', 40.0, -60.0)

    # ================================================================ 2S battery connector, fuse, protector (right)
    P('J301', 54.0, -33.0, 270)        # pins along −Y: 1 B− (Y −33), 2 BM (−37.0), 3 B+ (−40.9)
    P('F301', 46.6, -45.6, 180)         # pad 1 (B+) right, pad 2 (VBAT) left towards the BAT caps
    P('Q301', 61.8, -33.8, 0); P('Q302', 61.8, -38.6, 0)       # discharge / charge FETs (common drain)
    P('U301', 60.6, -43.6, 0)
    P('C315', 64.4, -42.6, 90); P('C316', 65.6, -42.6, 90)
    P('R305', 64.4, -45.4, 90); P('R308', 65.6, -45.4, 90); P('R309', 60.6, -46.6, 0)
    P('TP302', 42.6, -48.9); P('TP307', 58.0, -29.0)

    # ================================================================ always-on 3.3 V buck (rear left)
    import blocks as BK
    BK.put(pc, BK.buck('U303', 'L302', 'C320', 'C321', 'C323', 'C322', 'R320', 'R321', 'C324', 'C325', 'C326'), (-30.0, 46.0))
    P('TP304', -36.0, -34.0); P('TP305', -40.0, -34.0)

    # ================================================================ Pi 5 V buck TPS566238 + USB-C output (front right)
    PX, PY = 36.0, 28.0
    P('U302', PX, PY, 0)
    # KiCad view (y down): SW exits the top of the IC into L301 (vertical), VIN on the right with the 100 nF under
    # VIN/PGND, VCC/FB/EN on the left, +5V band along the top of L301, COUT stacked down to the J702 VBUS pads.
    block(pc, (PX, PY), [
        ('L301', 0.25, 7.1, 90),        # pad 1 (SW) at the bottom, right above the SW pin; pad 2 (+5V) at the top
        ('C306', 0.9, 1.8, 0),          # BST 100 nF: SW pad on the SW path, BST pad above BST (pin 7)
        ('C304', 0.42, -1.75, 180),     # VIN 100 nF right under VIN (pin 5) / PGND (pin 4)
        ('C301', 2.7, -0.9, 270), ('C302', 4.7, -0.9, 270), ('C303', 6.7, -0.9, 270),   # VIN 3×10 µF, VSYS row level with pin 6
        ('C305', -2.4, 1.0, 180),       # VCC 1 µF
        ('R302', -2.4, -0.5, 270),      # FB bottom 24k   } FB pads in one row level with FB (pin 2)
        ('R301', -3.4, -0.5, 90),       # FB top 182k     }
        ('C311', -4.4, -0.5, 90),       # CFF 33 pF       }
        ('R313', -5.4, -0.5, 90),       # PG pull-up
        ('C312', -1.5, -3.9, 270),      # EN 1 nF         } EN row
        ('R310', -2.5, -3.9, 90),       # EN pull-up      }
        ('Q303', -5.0, -3.9, 0),        # EN pull-down    }
        ('R312', -7.4, -3.9, 270),      # gate pull-down  }
        ('C307', 7.6, 7.6, 180), ('C308', 7.6, 5.3, 180), ('C309', 7.6, 3.0, 180),      # COUT 3×47 µF, +5V pads on the J702 side
        ('C310', 4.6, 12.1, 0),         # COUT 100 nF on the +5V band
        ('TP303', 11.0, 13.1, 0),
        # J702 decoupling and protection above the receptacle, Rp resistors under it (bottom side)
        ('C702', 12.5, 9.9, 270), ('C701', 14.1, 10.1, 270), ('D701', 17.45, 10.8, 0),
        ('R713', 12.8, 4.75, 0, 'B'), ('R712', 12.8, 1.75, 0, 'B'),   # level with CC2 / CC1, CC pad towards the via
    ])
    P('J702', 53.0, 31.0, 90)                                      # opening towards +X (notch in the board)

    # ================================================================ under the pack, bottom side: motor bridge, connectors
    MX, MY = 0.0, -25.6
    block(pc, (MX, MY), [
        ('U501', 0.0, 0.0, 90, 'B'),
        ('C505', 4.25, 5.9, 270, 'B'), ('C501', 0.97, 5.9, 90, 'B'),        # C501 pin 1 (+3V3) faces U501 pin 20
        ('C503', 6.4, 2.0, 90, 'B'), ('C504', -6.4, 2.0, 90, 'B'),
        ('C502', 0.0, -8.6, 0, 'B'),
    ])
    P('J501', -9.0, -13.0, 0, 'B'); P('J502', 9.0, -13.0, 0, 'B')
    for i, ref in enumerate(['R501', 'R502', 'C506', 'R503', 'R504', 'C507']):
        P(ref, -15.5 + 1.25 * i, -20.4, 90, 'B')
    for i, ref in enumerate(['R505', 'R506', 'C508', 'R507', 'R508', 'C509']):
        P(ref, 9.25 + 1.25 * i, -20.4, 90, 'B')
    P('C510', -17.0, -20.4, 90, 'B')
    # IMU at the turning axis (bottom)
    P('U601', 0.0, -2.0, 0, 'B'); P('C601', -2.9, -1.0, 90, 'B'); P('C602', -2.9, -3.0, 90, 'B')

    # ================================================================ front corners, bottom: cliff ToF sensors
    for ref, X, caps, r in (('U602', -34.0, ('C603', 'C604'), 'R601'), ('U603', 34.0, ('C607', 'C608'), 'R602')):
        s = -1 if X < 0 else 1
        P(ref, X, 62.0, 0, 'B')
        P(caps[0], X - s * 4.2, 63.25, 90, 'B'); P(caps[1], X - s * 4.2, 60.8, 90, 'B')
        P(r, X + s * 4.0, 61.0, 90, 'B')

    # ================================================================ front centre: head connector, servo
    P('J602', 0.0, 42.9, 180)
    P('C609', -13.6, 42.0, 90)
    # head tilt servo (optional): right strip, next to the Pi 5 V rail
    P('J603', 24.0, 19.0, 90); P('R603', 24.0, 15.6, 0); P('R604', 26.6, 15.6, 90)
    P('C612', 40.5, 18.6, 90)

    # ================================================================ front left: ESP32-S3, IO expander, Pi link
    EX, EY = -53.75, 36.0
    P('U401', EX, EY, 90)                                          # antenna towards −X (board edge)
    P('C401', -57.6, 25.0, 0); P('C402', -54.8, 25.0, 0)          # 3V3 (pin 2) decoupling, rear of the module
    P('R401', -52.4, 25.0, 0); P('C403', -50.2, 25.0, 0)          # EN RC
    P('SW401', -45.0, -19.0, 90); P('SW402', -39.0, -19.0, 90)   # RESET / BOOT (rear left, clear of the motor brackets)
    P('J401', -49.0, 49.5, 90)                                    # debug UART (DNP), next to TXD0/RXD0
    # ESP32 native USB pads (D−, D+, GND) on the bottom under the module, next to pins 13/14
    P('TP401', -46.4, 30.4, 0, 'B'); P('TP402', -43.8, 30.4, 0, 'B'); P('TP403', -46.4, 33.0, 0, 'B')
    P('R402', -39.4, 44.0, 90); P('R403', -38.2, 44.0, 90)          # 33 R LCD SPI series (towards J602)
    # IO expander in the left strip, under the ESP32 (P13..P17 pull-downs in front of it)
    TX, TY = -41.0, 17.6
    P('U402', TX, TY, 90)
    block(pc, (TX, TY), [
        ('C404', -5.0, 4.2, 0),
        ('R414', 1.6, 5.2, 90), ('R415', 0.4, 5.2, 90), ('R416', -0.8, 5.2, 90), ('R417', -2.0, 5.2, 90), ('R418', 2.8, 5.2, 90),
        ('D401', -5.6, -4.8, 90), ('R412', -5.6, -1.8, 90),
    ])
    for i, ref in enumerate(['R408', 'R409', 'R410', 'R411', 'R419', 'R420']):
        P(ref, -38.0 + 1.2 * i, 26.0, 90)                          # I2C / IRQ pull-ups, between the ESP32 and J701
    # Pi GPIO link: J701 under the Pi header pins 1-12 (pin 1 at the front)
    P('J701', -26.6, 32.0, 0)
    P('U701', -35.4, 34.0, 0); P('C703', -35.4, 37.4, 0)
    P('R701', -31.6, 38.2, 0); P('R702', -31.6, 37.0, 0); P('R703', -31.6, 35.8, 0)
    P('R709', -31.6, 32.2, 0); P('R710', -31.6, 31.0, 0)
    # shutdown / reset / boot transistors: rear left, outside the motor and bracket no-via zone (B.Cu keep-out)
    for i, (q, rg, rp) in enumerate((('Q701', 'R704', 'R705'), ('Q702', 'R706', 'R707'), ('Q703', 'R708', 'R711'))):
        x = -35.8 - i * 4.6
        P(q, x, -25.0, 0); P(rg, x - 0.8, -28.4, 0); P(rp, x - 0.8, -29.6, 0)
    return pc
