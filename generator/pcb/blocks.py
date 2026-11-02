"""Placement blocks in a local frame (mm). Each item: (ref, x, y, rot[, side]).
2-pad convention (R/C/L/D): rot 0 → pad 1 on the left; 180 → right; 90 → down (+y); 270 → up (−y).
The block is rotated like a KiCad footprint (rot(lx, ly, θ)) and then translated."""
from board import rot, r4

def put(pc, items, origin, brot=0, side='F'):
    """Place a block. origin in local board coordinates."""
    ox, oy = origin
    for it in items:
        ref, lx, ly, lr = it[:4]
        s = it[4] if len(it) > 4 else side
        dx, dy = rot(lx, ly, brot)
        pc.P(ref, ox + dx, oy + dy, (lr + brot) % 360, s)

# ------------------------------------------------------------------ TPS62933 buck (IC rotated 270 in the frame)
# IC: 4 GND(−0.75, −0.74) 3 VIN(−0.25, −0.74) 2 EN(0.25, −0.74) 1 RT(0.75, −0.74) | 5 SW(−0.75, 0.74) 6 BST 7 SS 8 FB(0.75, 0.74)
def buck(u, l, cin, chf, cbst, css, rtop, rbot, co1, co2, cohf):
    return [
        (u, 0.0, 0.0, 270),
        (chf, -0.48, -2.05, 180),          # 100 nF: pad 1 (VSYS) on the right, next to VIN
        (cin, -0.5, -4.05, 180),           # 22 µF input
        (l, -5.15, 1.85, 180),             # pad 1 (SW) on the right
        (cbst, -0.25, 2.25, 270),          # pad 1 (BST) at the top
        (css, 1.35, 2.35, 270),            # pad 1 (SS) at the top
        (rbot, 3.05, 0.74, 0),             # pad 1 (FB) on the left
        (rtop, 3.05, -0.55, 180),          # pad 2 (FB) on the left, pad 1 (VOUT) on the right
        (co1, -7.45, 6.45, 270),           # pad 1 (VOUT) at the top
        (co2, -5.2, 6.45, 270),
        (cohf, -3.3, 5.75, 270),
    ]

# ------------------------------------------------------------------ BQ25883 charger (IC at 0°, as in the datasheet)
# top (y=−1.96): 24 DP(−1.25) 23 VBUS 22 PMID 21 PMID 20 GND 19 GND(1.25)
# right (x=1.96): 18 SW(−1.25) 17 SW 16 SYS 15 SYS 14 BAT 13 BAT(1.25)
# bottom (y=1.96): 7 TS(−1.25) 8 ILIM 9 PG 10 NC 11 REGN 12 BTST(1.25)
# left (x=−1.96): 1 DM(−1.25) 2 STAT 3 CE 4 SDA 5 SCL 6 INT(1.25)
# TI guide (SLUSDL3A §11.1 and the BQ2588x checklist): 1) SYS capacitor as close as possible to SYS and GND
# (the small one first); 2) PMID capacitor next to PMID/PGND; 3) inductor next to SW; BAT with its capacitor close by.
# Wedge layout to the right of the IC: SW rises diagonally towards the inductor, BAT drops diagonally towards C211, and
# between them there is a VSYS zone on F.Cu with C210 (100 nF) 0.5 mm from the SYS pins, C208 (22 µF) at 3 mm and 8 vias to In2.
def charger():
    return [
        ('U204', 0.0, 0.0, 0),
        ('C207', 0.65, -4.95, 90),         # PMID 22 µF: pad 1 (PMID) at the bottom, over PMID pins 21/22
        ('L201', 5.4, -4.1, 270),          # pad 2 (SW) at the bottom, right of the SW pins; pad 1 (PMID) at the top
        ('C210', 3.6, 0.0, 0),             # SYS 100 nF: pad 1 (SYS) 0.5 mm from the SYS pins, pad 2 to GND with a via
        ('C208', 7.4, -0.45, 0),           # SYS 22 µF: pad 1 (SYS) on the left, inside the VSYS zone
        ('C206', -1.6, -4.2, 90),          # VBUS 1 µF (as close as possible)
        ('C205', -5.0, -4.95, 90),         # VBUS 22 µF
        ('C211', 3.85, 3.6, 270),          # BAT 22 µF: pad 1 (VBAT) at the top, at the end of the BAT diagonal
        ('C212', 1.75, 3.65, 270),         # BTST 47 nF: pad 1 (BTST) at the top
        ('C213', 0.5, 4.25, 270),          # REGN 4.7 µF: pad 1 (REGN) at the top
        ('R210', -1.3, 4.0, 270),          # ILIM 1k ∥ 1k = 500 Ω → 2.2 A
        ('R212', -2.4, 4.0, 270),
        ('R207', -4.6, 0.9, 180),          # TS: REGN–TS
        ('R208', -4.6, 2.1, 180),          # TS–GND
        ('R209', -4.6, 3.3, 180),          # TS–GND
        ('R211', -0.9, 6.9, 0),            # charge LED
        ('D203', 1.9, 6.9, 180),
        # SYS bulk caps under the VBAT trunk (over the In2 VSYS island, with vias)
        ('C209', 6.2, 5.6, 270),
        ('C216', 8.65, 5.6, 270),
        ('C217', 11.1, 5.6, 270),
    ]

# ------------------------------------------------------------------ TB6612FNG (IC rotated 90: outputs towards +y)
# front row (y=−3.5): 24 VM1(−3.58) 23 PWMA 22 AIN2 21 AIN1 20 VCC 19 STBY 18 GND 17 BIN1 16 BIN2 15 PWMB 14 VM3 13 VM2(3.58)
# rear row (y=+3.5): 1,2 AO1 | 3,4 PGND1 | 5,6 AO2 | 7,8 BO2 | 9,10 PGND2 | 11,12 BO1
def motor_driver():
    return [
        ('U501', 0.0, 0.0, 90),
        ('C505', -4.25, -5.9, 90),         # VM1 100 nF: pad 1 (VSYS) at the bottom, towards VM1
        ('C501', -0.97, -5.9, 90),         # VCC 100 nF in the gap between AIN1 and STBY
        ('C503', -6.4, -2.0, 270),         # VM 22 µF: pad 1 at the top
        ('C504', 6.4, -2.0, 270),
        ('C502', 12.4, -2.9, 0),           # VM 100 µF electrolytic (pad 1 = + on the left)
    ]
