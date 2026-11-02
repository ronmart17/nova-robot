"""Critical power routes, drawn by hand (relative to the pads): charger, regulators, motor bridge and protector.
All tagged 'fixed' so that the autorouter keeps them."""
from router import Shape, LAYERS
from shapely.geometry import Polygon, box

class FX:
    def __init__(self, R, b):
        self.R, self.b = R, b
        self.zones = []          # (net, layer, absolute polygon, priority)

    def p(self, ref, num, k=0):
        return self.b.placed[ref].pad_xy(num)[k]

    def t(self, net, layer, pts, w):
        for a, c in zip(pts, pts[1:]):
            self.R.add_track(net, layer, a, c, w, tag='fixed')

    def v(self, net, xy, d=0.6):
        self.R.add_via(net, xy, d, tag='fixed')

    def zone(self, net, layer, pts, prio=2):
        poly = pts if hasattr(pts, 'exterior') else Polygon(pts)
        self.zones.append((net, layer, poly, prio))
        n = self.R.nid(net)
        self.R.add_shape(Shape('poly', poly, n, (layer,), 'fixed'))

def off(p, dx=0.0, dy=0.0):
    return (p[0] + dx, p[1] + dy)

# ------------------------------------------------------------------ BQ25883 charger
def shape_geom(sh):
    """Router shape → shapely geometry."""
    from shapely.geometry import Point, LineString, Polygon
    from shapely import affinity
    k, p = sh.kind, sh.p
    if k == 'circle': return Point(p[0], p[1]).buffer(p[2], 24)
    if k == 'seg': return LineString([(p[0], p[1]), (p[2], p[3])]).buffer(p[4] / 2, 12)
    if k == 'rect':
        cx, cy, hw, hh, a = p[:5]
        r = min(p[5], hw, hh) if len(p) > 5 else 0.0
        g = box(cx - hw + r, cy - hh + r, cx + hw - r, cy + hh - r).buffer(r, 8) if r > 0 else box(cx - hw, cy - hh, cx + hw, cy + hh)
        # KiCad rot() turns counter-clockwise on screen (y pointing down) → −a in shapely (y pointing up)
        return affinity.rotate(g, -a, origin=(cx, cy)) if a else g
    return p

def charger(F):
    """BQ25883 (TI guide SLUSDL3A §11.1): SYS cap as close as possible to SYS/GND, PMID cap next to PMID/PGND, inductor
    next to SW, BAT with its capacitor close by and enough vias on every current path. Wedge layout to the
    right of the IC: SW rises diagonally to the inductor, BAT drops diagonally to C211 and between them a VSYS zone on F.Cu
    with C210 (100 nF) 0.5 mm from the SYS pins, C208 (22 µF) at 3 mm and 8 vias to the In2 VSYS island."""
    from shapely.geometry import Point
    from shapely.ops import unary_union
    U = 'U204'
    c = F.b.placed[U]; cx, cy = c.x, c.y
    Lc = lambda x, y: (cx + x, cy + y)                 # IC frame: x to the right, y downwards
    SW, SYS, VBAT = '/USB-C and dock input, 2S charger/CHG_SW', 'VSYS', 'VBAT'
    PMID = 'Net-(C207-Pad1)'
    xl = F.p(U, '17')[0] - cx                          # 1.9625: centre of the right-hand pads
    # SW: pins 17/18 → to the right and diagonally up to pad 2 of L201
    F.t(SW, 'F.Cu', [Lc(xl, -1.0), Lc(2.75, -1.0), Lc(3.95, -2.2), Lc(4.6, -2.2)], 0.7)
    # PMID: pins 21/22 → C207 (above) → pad 1 of L201 (diagonal above the SW node)
    pm = [F.p(U, '21'), F.p(U, '22')]; xm = (pm[0][0] + pm[1][0]) / 2; ytop = pm[0][1]
    c207 = F.p('C207', '1')
    F.t(PMID, 'F.Cu', [(xm, ytop), (xm, c207[1])], 0.75)
    F.t(PMID, 'F.Cu', [Lc(0.9, -3.6), Lc(2.3, -3.6), Lc(3.9, -5.2), Lc(4.4, -5.6)], 0.7)
    # GND 19/20 → exposed pad
    g = [F.p(U, '19'), F.p(U, '20')]; xg = (g[0][0] + g[1][0]) / 2
    F.t('GND', 'F.Cu', [(xg, ytop), (xg, ytop + 0.95)], 0.75)
    # BTST: C212 next to BTST; its SW side returns to the SW node on B.Cu
    c212 = F.p('C212', '2')
    v1 = (c212[0], c212[1] + 0.85)
    v2 = Lc(xl + 0.75, -1.85)
    F.t(SW, 'F.Cu', [c212, v1], 0.4); F.v(SW, v1, 0.55)
    F.t(SW, 'B.Cu', [v1, (v1[0] + 0.0, v2[1] + 1.2), (v2[0], v2[1])], 0.4); F.v(SW, v2, 0.55)
    F.t(SW, 'F.Cu', [v2, (v2[0], cy - 1.0)], 0.4)
    bt = F.p(U, '12'); c212b = F.p('C212', '1')
    F.t('/USB-C and dock input, 2S charger/CHG_BTST', 'F.Cu', [bt, (bt[0], bt[1] + 0.45), c212b], 0.25)
    # REGN → C213
    rg = F.p(U, '11'); c213 = F.p('C213', '1')
    F.t('/USB-C and dock input, 2S charger/CHG_REGN', 'F.Cu', [rg, (rg[0], rg[1] + 0.35), c213], 0.3)
    # VBUS (pin 23) goes straight up and turns left towards C206; D+ (pin 24) turns earlier, below it
    vb = F.p(U, '23'); c206 = F.p('C206', '1')
    VIN = '/USB-C and dock input, 2S charger/VIN_CHG'
    c205 = F.p('C205', '1')
    yr = F.p('C206', '1')[1] + 0.2         # VIN rail over the pads 1 (never over the GND pads 2)
    F.t(VIN, 'F.Cu', [vb, (vb[0], yr), (c206[0], yr)], 0.4)
    F.t(VIN, 'F.Cu', [(c206[0], yr), (c205[0], yr), c205], 0.6)
    # BAT: pins 13/14 → diagonal down → C211; 1.2 mm VBAT trunk below the SYS zone up to F301
    F.t(VBAT, 'F.Cu', [Lc(xl, 1.0), Lc(2.55, 1.0), Lc(3.3, 1.75)], 0.8)
    c211 = F.p('C211', '1'); f2 = F.p('F301', '2')
    F.t(VBAT, 'F.Cu', [c211, Lc(4.4, 2.3), Lc(11.0, 2.3), (f2[0], cy + 2.3 - (f2[0] - (cx + 11.0))), f2], 1.2)
    # SYS: pins → C210 (100 nF) with its GND through a via; C208 (22 µF) with two GND vias; 8 vias to the VSYS island
    F.t(SYS, 'F.Cu', [Lc(xl, 0.0), F.p('C210', '1')], 0.6)
    c210g = F.p('C210', '2'); vg = (c210g[0] + 0.68, c210g[1])
    F.t('GND', 'F.Cu', [c210g, vg], 0.45); F.v('GND', vg, 0.55)
    c208g = F.p('C208', '2')
    for dy in (-0.4, 0.4):
        a = (c208g[0], c208g[1] + dy); v = (c208g[0] + 1.17, c208g[1] + dy)
        F.t('GND', 'F.Cu', [a, v], 0.45); F.v('GND', v, 0.55)
    vias = [Lc(x, 0.95) for x in (5.0, 5.65, 6.3, 6.95, 7.6, 8.25, 8.9, 9.55)]
    for v in vias:
        F.v(SYS, v, 0.55)
    F.t(SYS, 'F.Cu', [vias[0], vias[-1]], 0.45)
    F.t(SYS, 'F.Cu', [F.p('C208', '1'), (F.p('C208', '1')[0], vias[0][1])], 0.6)
    # VSYS zone on F.Cu: the wedge minus other nets' copper (+0.3 mm); KiCad fills it with 0.2 mm clearance
    n = F.R.nid(SYS)
    region = box(cx + 2.0, cy - 2.0, cx + 10.5, cy + 1.45)
    others = [shape_geom(sh) for sh, hard in F.R.shapes
              if sh.net != n and 'F.Cu' in sh.layers and sh.bbox[2] > region.bounds[0] - 1 and sh.bbox[0] < region.bounds[2] + 1
              and sh.bbox[3] > region.bounds[1] - 1 and sh.bbox[1] < region.bounds[3] + 1]
    for (ref, num), lst in F.R.pads.items():
        for sh, cc in lst:
            if sh.net != n and 'F.Cu' in sh.layers and region.buffer(1.0).intersects(box(*sh.bbox)):
                others.append(shape_geom(sh))
    z = region.difference(unary_union(others).buffer(0.3, 8))
    z = z.buffer(-0.12, 8).buffer(0.12, 8)           # no slivers narrower than 0.24 mm
    seed = Point(cx + 2.5, cy)
    parts = list(getattr(z, 'geoms', [z]))
    z = min(parts, key=lambda gg: gg.distance(seed))
    F.zone(SYS, 'F.Cu', list(z.exterior.coords), prio=2)

# ------------------------------------------------------------------ TPS62933 regulators
def buck(F, U, L, CHF, CIN, CBST, CSS, RTOP, RBOT, CO1, CO2, COHF, OUT, out_w=1.0):
    pin = lambda n: F.p(U, n)
    VS = 'VSYS'
    swn = F.b.placed[U].comp.pins['5'][0]; bstn = F.b.placed[U].comp.pins['6'][0]
    ssn = F.b.placed[U].comp.pins['7'][0]; fbn = F.b.placed[U].comp.pins['8'][0]
    # VIN / GND to the input capacitors
    F.t(VS, 'F.Cu', [pin('3'), off(pin('3'), 0, -0.5), F.p(CHF, '1')], 0.3)
    F.t('GND', 'F.Cu', [pin('4'), off(pin('4'), 0, -0.5), F.p(CHF, '2')], 0.3)
    F.t(VS, 'F.Cu', [F.p(CHF, '1'), F.p(CIN, '1')], 0.5)
    F.t('GND', 'F.Cu', [F.p(CHF, '2'), F.p(CIN, '2')], 0.5)
    # SW → inductor; bootstrap capacitor
    l1 = F.p(L, '1')
    F.t(swn, 'F.Cu', [pin('5'), (pin('5')[0], l1[1] - 0.6)], 0.3)
    F.t(swn, 'F.Cu', [(pin('5')[0] - 0.35, l1[1] - 0.6), (l1[0], l1[1] - 0.6)], 0.6)
    F.t(swn, 'F.Cu', [F.p(CBST, '2'), (l1[0] + 0.5, F.p(CBST, '2')[1])], 0.35)
    F.t(bstn, 'F.Cu', [pin('6'), F.p(CBST, '1')], 0.25)
    F.t(ssn, 'F.Cu', [pin('7'), off(pin('7'), 0, 0.45), F.p(CSS, '1')], 0.2)
    # FB
    F.t(fbn, 'F.Cu', [pin('8'), F.p(RBOT, '1')], 0.2)
    F.t(fbn, 'F.Cu', [F.p(RBOT, '1'), F.p(RTOP, '2')], 0.2)
    # RT (pin 1) to GND with a via
    r1 = pin('1'); vr = (r1[0] + 0.85, r1[1])
    F.t('GND', 'F.Cu', [r1, vr], 0.25); F.v('GND', vr, 0.55)
    # EN: escapes upwards between C_HF and RT
    en = pin('2')
    enn = F.b.placed[U].comp.pins['2'][0]
    F.t(enn, 'F.Cu', [en, (en[0], en[1] - 0.62), (en[0] + 1.5, en[1] - 0.62)], 0.2)
    # output: inductor → capacitors
    l2 = F.p(L, '2'); o1 = F.p(CO1, '1'); o2 = F.p(CO2, '1'); oh = F.p(COHF, '1')
    F.t(OUT, 'F.Cu', [(l2[0], l2[1] + 0.5), (o1[0], o1[1])], out_w)
    F.t(OUT, 'F.Cu', [(o1[0], o1[1] - 0.15), (o2[0], o1[1] - 0.15), (oh[0], oh[1])], 0.6)

# ------------------------------------------------------------------ TB6612FNG
def motor_driver(F):
    U = 'U501'
    VS = 'VSYS'
    p24 = F.p(U, '24'); p13 = F.p(U, '13'); p14 = F.p(U, '14')
    c503 = F.p('C503', '1'); c504 = F.p('C504', '1'); c505 = F.p('C505', '1'); c502 = F.p('C502', '1')
    yv = p24[1] - 0.55
    F.t(VS, 'F.Cu', [p24, (p24[0], yv), (c503[0], yv), c503], 0.5)
    F.t(VS, 'F.Cu', [(p24[0], yv), c505], 0.4)
    F.t(VS, 'F.Cu', [p14, (p14[0], yv), (p13[0], yv), p13], 0.5)
    F.t(VS, 'F.Cu', [(p13[0], yv), (c504[0], yv), c504], 0.5)
    F.t(VS, 'F.Cu', [c504, (c502[0], c504[1] + 0.25)], 0.6)
    # VM to the In2 VSYS island: 2 vias on the VM1 bridge (next to C503) and 3 on the C504 → C502 link
    for x in (c503[0] + 1.35, c503[0] + 1.95):
        F.v(VS, (x, yv), 0.55)
    import math
    e = (c502[0], c504[1] + 0.25); L = math.dist(c504, e); u = ((e[0] - c504[0]) / L, (e[1] - c504[1]) / L)
    for d in (1.25, 1.85, 2.45):
        F.v(VS, (c504[0] + u[0] * d, c504[1] + u[1] * d), 0.55)
    # power GND: 3 vias in a column behind each PGND pair (3-4 and 9-10)
    for a, bb in (('3', '4'), ('9', '10')):
        pa, pb = F.p(U, a), F.p(U, bb)
        xm = (pa[0] + pb[0]) / 2
        F.t('GND', 'F.Cu', [pa, pb], 0.5)
        F.t('GND', 'F.Cu', [(xm, pa[1]), (xm, pa[1] + 3.05)], 0.6)
        for dy in (1.75, 2.4, 3.05):
            F.v('GND', (xm, pa[1] + dy), 0.6)
    # VCC (3V3): pin 20 → C501
    F.t('+3V3', 'F.Cu', [F.p(U, '20'), F.p('C501', '1')], 0.3)

def motor_outputs(F):
    """TB6612 outputs to the motor connectors (THT, body on the bottom side), all on F.Cu at 0.5 mm and with no vias.
    The near terminal of each connector goes straight down (J501.6 ← AO1, J502.1 ← BO1). The far one (J501.1 ← AO2,
    J502.6 ← BO2) goes down between the two channels and wraps around its connector from behind (y = connector + 1.6).
    To keep them from crossing, J501 has M+/M− swapped in the schematic (mirrored motors). This leaves free: on F.Cu,
    the strip between the encoder RCs and the connectors; on B.Cu, the central passage between J501 and J502 (under the TB6612)."""
    U = 'U501'
    ML, MLm = '/Motors and encoders/MOT_L+', '/Motors and encoders/MOT_L-'
    MR, MRm = '/Motors and encoders/MOT_R+', '/Motors and encoders/MOT_R-'
    w = 0.5
    p = {k: F.p(U, k) for k in ('1', '2', '5', '6', '7', '8', '11', '12')}
    yb = p['1'][1] + 0.7                     # inside the pads (1.9 mm long)
    def bar(a, c, net):
        F.t(net, 'F.Cu', [(p[a][0], yb), (p[c][0], yb)], 0.4)     # inside the pads (0.4 wide)
        return (p[a][0] + p[c][0]) / 2
    xa1, xa2, xb2, xb1 = bar('1', '2', ML), bar('5', '6', MLm), bar('7', '8', MRm), bar('11', '12', MR)
    j1, j6 = F.p('J501', '1'), F.p('J501', '6')
    k1, k6 = F.p('J502', '1'), F.p('J502', '6')
    y45 = yb + 0.8                           # start of the 45° segment of the near terminals
    # near: AO1 → J501.6 and BO1 → J502.1 (down, then 45° to the pad axis)
    F.t(ML, 'F.Cu', [(xa1, yb), (xa1, y45), (j6[0], y45 + abs(xa1 - j6[0])), j6], w)
    F.t(MR, 'F.Cu', [(xb1, yb), (xb1, y45), (k1[0], y45 + abs(xb1 - k1[0])), k1], w)
    # far: AO2 → J501.1 and BO2 → J502.6 behind their connector
    yB = j1[1] + 1.6
    F.t(MLm, 'F.Cu', [(xa2, yb), (xa2, yB), (j1[0], yB), j1], w)
    F.t(MRm, 'F.Cu', [(xb2, yb), (xb2, yB), (k6[0], yB), k6], w)

# ------------------------------------------------------------------ battery protector (low side)
def protection(F):
    BATM = '/2S battery, protection and regulators/BAT-'
    j1 = F.p('J301', '1'); qs = F.p('Q301', '2'); u6 = F.p('U301', '6')
    F.t(BATM, 'F.Cu', [j1, (qs[0] + 0.6, j1[1]), (qs[0] + 0.6, qs[1]), qs], 1.2)
    F.t(BATM, 'F.Cu', [qs, (u6[0], qs[1]), u6], 0.4)
    # common drains Q301–Q302
    d1 = F.p('Q301', '3'); d2 = F.p('Q302', '3')
    F.t('Net-(Q301-D)', 'F.Cu', [d1, d2], 1.2)
    # Q302 source to GND with vias
    s2 = F.p('Q302', '2')
    vy = s2[1] - 0.9
    F.t('GND', 'F.Cu', [s2, (s2[0] + 1.4, s2[1]), (s2[0] + 1.4, vy), (s2[0] + 2.9, vy)], 0.8)
    for k in range(3):
        F.v('GND', (s2[0] + 1.4 + 0.75 * k, vy), 0.6)
    # J301 pin 3 → fuse
    j3 = F.p('J301', '3'); f1 = F.p('F301', '1')
    F.t('Net-(J301-Pin_3)', 'F.Cu', [j3, f1], 1.5)

def ep_stubs(F, U, pins, ep='17', w=0.25):
    """Join a QFN's GND pins to its exposed pad with a straight inward stub."""
    c = F.b.placed[U]
    ex, ey = c.x, c.y
    for n in pins:
        p = F.p(U, n)
        q = (p[0] + (ex - p[0]) * 0.55, p[1] + (ey - p[1]) * 0.55)
        F.t('GND', 'F.Cu', [p, q], w)

def extra(F):
    """Fixed fan-outs where autorouting gets stuck: R401 (ESP32 EN pull-up) is boxed in between the
    module, U402 and the EN track; its +3V3 drops to the plane through a fixed via just above the pad."""
    p = F.p('R401', '1')
    via = (p[0], p[1] - 1.05)
    F.t('+3V3', 'F.Cu', [p, via], 0.3)
    F.v('+3V3', via, 0.55)

def ideal_diode(F):
    """LM66200 output (VIN_CHG, up to 2.2 A) to the charger: joins VOUT (pins 2 and 7) under the body, exits between
    pins 1 and 8 at 0.4 mm and continues at 0.8 mm to pad 1 of C205, where the charger's fixed rail starts."""
    U = 'U202'
    VIN = '/USB-C and dock input, 2S charger/VIN_CHG'
    p2, p7 = F.p(U, '2'), F.p(U, '7')
    xc, yc = (p2[0] + p7[0]) / 2, p2[1]
    F.t(VIN, 'F.Cu', [p2, p7], 0.3)
    y0 = yc - 1.3
    F.t(VIN, 'F.Cu', [(xc, yc), (xc, y0)], 0.4)
    c205 = F.p('C205', '1')
    ya = c205[1] + 0.68                      # 45° diagonal arrival at the C205 pad
    xa = c205[0] - 1.2
    yb = ya + (xa - xc)                      # start of the diagonal
    F.t(VIN, 'F.Cu', [(xc, y0), (xc, yb), (xa, ya), c205], 0.8)
    # inputs: IN1 (pin 3) → C201 on the left and IN2 (pin 6) → C203 on the right (0.3 mm between pins, then 0.6)
    for pin, cref, sgn, net in (('3', 'C201', -1, '/USB-C and dock input, 2S charger/VBUS_USB'),
                                ('6', 'C203', 1, '/USB-C and dock input, 2S charger/VDOCK')):
        pp = F.p(U, pin); cp = F.p(cref, '1'); xm = pp[0] + sgn * 0.76
        F.t(net, 'F.Cu', [pp, (xm, pp[1])], 0.3)
        F.t(net, 'F.Cu', [(xm, pp[1]), cp], 0.6)

def route_fixed(R, b):
    F = FX(R, b)
    extra(F)
    ep_stubs(F, 'U604', ['3', '11', '15'])
    F.v('GND', F.p('U604', '17'), 0.55)        # MAX98357A exposed pad to the GND plane (datasheet)
    charger(F)
    ideal_diode(F)
    buck(F, 'U302', 'L301', 'C302', 'C301', 'C304', 'C303', 'R301', 'R302', 'C305', 'C306', 'C307', '+5V')
    buck(F, 'U303', 'L302', 'C309', 'C308', 'C311', 'C310', 'R303', 'R304', 'C312', 'C313', 'C314', '+3V3')
    motor_driver(F)
    motor_outputs(F)
    protection(F)
    return F
