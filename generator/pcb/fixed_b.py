"""Main board Rev B — hand-drawn power routes (relative to the pads), tagged 'fixed' so that the autorouter keeps them.
TI layout guides followed: BQ25798 (SLUSDV2 §8.4), TPS566238 and TPS62933 data sheets."""
from shapely.geometry import Polygon, box
from shapely.ops import unary_union
from fixed import FX, off, shape_geom
import fixed

CH = '/USB-C + 12 V dock, BQ25798 charger/'
S3 = '/2S battery, protection, 3V3 and Pi 5 V bucks/'

def net_of(F, ref, num):
    return F.b.placed[ref].comp.pins[str(num)][0]

def pads_bbox(F, ref, num):
    """Absolute bounding box of a pad (from the router's pad shapes)."""
    lst = F.R.pads[(ref, str(num))]
    x0 = min(s.bbox[0] for s, c in lst); y0 = min(s.bbox[1] for s, c in lst)
    x1 = max(s.bbox[2] for s, c in lst); y1 = max(s.bbox[3] for s, c in lst)
    return x0, y0, x1, y1

def zone_clear(F, net, layer, region, seed, clear=0.3):
    """F.Cu/B.Cu zone = region minus other nets' copper (+clear); keeps the part that contains the seed."""
    from shapely.geometry import Point
    n = F.R.nid(net)
    others = []
    for sh, hard in F.R.shapes:
        if sh.net != n and layer in sh.layers and box(*sh.bbox).intersects(region.buffer(1.0)):
            others.append(shape_geom(sh))
    for (ref, num), lst in F.R.pads.items():
        for sh, cc in lst:
            if sh.net != n and layer in sh.layers and region.buffer(1.0).intersects(box(*sh.bbox)):
                others.append(shape_geom(sh))
    z = region.difference(unary_union(others).buffer(clear, 8)) if others else region
    z = z.buffer(-0.12, 8).buffer(0.12, 8)
    parts = list(getattr(z, 'geoms', [z]))
    z = min(parts, key=lambda g: g.distance(Point(*seed)))
    F.zone(net, layer, list(z.exterior.coords), prio=2)
    return z

# ------------------------------------------------------------------ BQ25798
def charger(F):
    U = 'U202'
    c = F.b.placed[U]; cx, cy = c.x, c.y
    L = lambda x, y: (cx + x, cy + y)                       # IC frame (KiCad: y down; top row of the IC at y = −1.7)
    PMID, SW1, SW2, SYS = CH + 'CHG_PMID', CH + 'CHG_SW1', CH + 'CHG_SW2', 'VSYS'
    VB = CH + 'CHG_VBUS'
    # --- SW1 / SW2: two vias each in the empty centre of the package → B.Cu → vias between the inductor pads
    sw_v = {SW1: [L(-0.5, -0.7), L(-0.5, 0.0)], SW2: [L(0.5, -0.7), L(0.5, 0.0)]}
    for net, pin in ((SW1, '28'), (SW2, '26')):
        p = F.p(U, pin)
        vx = sw_v[net][0][0]
        F.t(net, 'F.Cu', [p, (p[0], cy - 1.15), (vx, cy - 1.15), sw_v[net][0]], 0.2)
        F.t(net, 'F.Cu', [sw_v[net][0], sw_v[net][1]], 0.3)
        for v in sw_v[net]:
            F.v(net, v, 0.5)
    l1 = pads_bbox(F, 'L201', '1'); l2 = pads_bbox(F, 'L201', '2')
    ym = (l1[1] + l1[3]) / 2
    lv = {SW1: [(l1[2] + 0.55, ym + d) for d in (-1.0, 0.0, 1.0)], SW2: [(l2[0] - 0.55, ym + d) for d in (-1.0, 0.0, 1.0)]}
    for net in (SW1, SW2):
        for v in lv[net]:
            F.v(net, v, 0.55)
        x = lv[net][0][0]
        F.t(net, 'F.Cu', [(x, lv[net][0][1]), (x, lv[net][-1][1])], 0.55)
        edge = l1[2] if net == SW1 else l2[0]
        for v in lv[net]:
            F.t(net, 'F.Cu', [v, (edge, v[1])], 0.55)
        # B.Cu band from the package vias up to the inductor vias
        # leaves the package centre at 45° towards the inductor-side via column right away, so the GND vias of the
        # PMID/SYS 100 nF capacitors (above pin 27) stay clear of the band
        a = sw_v[net][0]; b = lv[net][-1]
        y1 = a[1] - 0.4
        F.t(net, 'B.Cu', [sw_v[net][1], a, (a[0], y1), (b[0], y1 - abs(a[0] - b[0])), b], 0.8)
        F.t(net, 'B.Cu', [lv[net][0], lv[net][-1]], 0.8)
    # --- BAT caps GND (top pads): bar + one via each, placed before the SYS pour is cleared around them
    ga, gb = F.p('C216', '2'), F.p('C217', '2')
    F.t('GND', 'F.Cu', [ga, gb], 0.6)
    for q in (ga, gb):
        F.t('GND', 'F.Cu', [q, (q[0], q[1] - 0.95)], 0.4); F.v('GND', (q[0], q[1] - 0.95), 0.6)
    # --- PMID / SYS 100 nF on the IC layer + GND bar between them over the SW pins
    pm = F.p(U, '29'); sy = F.p(U, '25'); g = F.p(U, '27')
    c209 = (F.p('C209', '1'), F.p('C209', '2')); c215 = (F.p('C215', '1'), F.p('C215', '2'))
    ytop = cy - 2.2
    F.t(PMID, 'F.Cu', [pm, (pm[0], ytop), c209[0]], 0.25)
    F.t(SYS, 'F.Cu', [sy, (sy[0], ytop), c215[0]], 0.25)
    F.t('GND', 'F.Cu', [g, (g[0], c209[1][1])], 0.25)
    F.t('GND', 'F.Cu', [c209[1], c215[1]], 0.35)
    # --- PMID and SYS corridors under the inductor (F.Cu zones), bulk caps on them, GND vias at the caps
    pmc = [F.p(r, '1') for r in ('C206', 'C207', 'C208')]
    syc = [F.p(r, '1') for r in ('C210', 'C211', 'C212', 'C213', 'C214')]
    yc = pmc[0][1]
    lb = l1[3]                                           # inductor pads bottom
    reg_pm = unary_union([box(min(p[0] for p in pmc) - 0.7, lb + 0.45, l1[2] + 0.2, yc + 0.75),
                          box(c209[0][0] - 0.45, lb + 0.45, c209[0][0] + 0.3, c209[0][1] + 0.35)])
    reg_sy = unary_union([box(l2[0] - 0.2, lb + 0.45, max(p[0] for p in syc) + 0.7, yc + 0.75),
                          box(c215[0][0] - 0.3, lb + 0.45, c215[0][0] + 0.45, c215[0][1] + 0.35)])
    zone_clear(F, PMID, 'F.Cu', reg_pm, (pmc[0][0], yc))
    zone_clear(F, SYS, 'F.Cu', reg_sy, (syc[0][0], yc))
    F.t(PMID, 'F.Cu', [c209[0], (c209[0][0], yc)], 0.5)
    F.t(SYS, 'F.Cu', [c215[0], (c215[0][0], yc)], 0.5)
    # SYS to the In2 VSYS plane: a row of vias under the SYS caps' corridor
    for p in syc:
        F.v(SYS, (p[0] + 1.0, yc + 0.15), 0.55)
    for ref in ('C206', 'C207', 'C208', 'C210', 'C211', 'C212', 'C213', 'C214'):
        q = F.p(ref, '2')
        F.t('GND', 'F.Cu', [q, (q[0], q[1] - 1.0)], 0.5); F.v('GND', (q[0], q[1] - 1.0), 0.55)
    # 100 nF GND: vias above the GND bar
    for x in (c209[1][0], c215[1][0]):
        F.v('GND', (x, c209[1][1] - 0.75), 0.5)
        F.t('GND', 'F.Cu', [(x, c209[1][1]), (x, c209[1][1] - 0.75)], 0.3)
    # --- BAT: pins 22/23 → stub → BAT pour under the VBAT pads of C216/C217 → F301 (pour created in battery())
    b1, b2 = F.p(U, '23'), F.p(U, '22')
    xb = b1[0] + 0.5
    F.t('VBAT', 'F.Cu', [b2, b1, (xb, b1[1])], 0.25)
    F.t('VBAT', 'F.Cu', [(xb, b2[1]), (xb, b1[1])], 0.4)
    # --- VBUS: pins 2/3 → C205 (100 nF) → C203/C204
    v2, v3 = F.p(U, '2'), F.p(U, '3')
    c205 = F.p('C205', '1')
    F.t(VB, 'F.Cu', [v2, v3], 0.25)
    F.t(VB, 'F.Cu', [((v2[0] + v3[0]) / 2 - 0.1, (v2[1] + v3[1]) / 2), (c205[0], (v2[1] + v3[1]) / 2), c205], 0.3)
    gv = []
    for ref in ('C203', 'C204'):
        q = F.p(ref, '2'); v = (q[0] + 1.0, q[1])
        F.t('GND', 'F.Cu', [q, v], 0.5); F.v('GND', v, 0.55); gv.append(v)
    # C205 GND: shares the C203 via (above) and has its own via below (two vias, TI)
    q = F.p('C205', '2')
    F.t('GND', 'F.Cu', [q, gv[0]], 0.3)
    F.t('GND', 'F.Cu', [q, (q[0], q[1] + 0.8)], 0.3); F.v('GND', (q[0], q[1] + 0.8), 0.5)
    # --- REGN cap: two GND vias (TI)
    q = F.p('C218', '2')
    for dx in (-0.35, 0.45):
        v = (q[0] + dx, q[1] + 0.85); F.t('GND', 'F.Cu', [q, v], 0.35); F.v('GND', v, 0.5)
    # --- GND of the IC: pin 27 is joined on top (bar); extra vias next to the bar
    return F

# ------------------------------------------------------------------ input FET pairs
def fet_pairs(F):
    for qa, qb in (('Q201', 'Q202'), ('Q203', 'Q204')):
        net_s = net_of(F, qa, '1')                       # common source of the back-to-back pair
        sa = [F.p(qa, n) for n in ('1', '2', '3')]; sb = [F.p(qb, n) for n in ('1', '2', '3')]
        ya = sorted(p[1] for p in sa); yb = sorted(p[1] for p in sb)
        F.t(net_s, 'F.Cu', [(sa[0][0], ya[0]), (sa[0][0], ya[-1])], 0.4)
        F.t(net_s, 'F.Cu', [(sb[0][0], yb[0]), (sb[0][0], yb[-1])], 0.4)
        common = [y for y in ya if any(abs(y - y2) < 0.05 for y2 in yb)]
        for y in common:
            F.t(net_s, 'F.Cu', [(sa[0][0], y), (sb[0][0], y)], 0.45)
    return F

# ------------------------------------------------------------------ TPS566238 Pi 5 V buck + J702
def pi_buck(F):
    """Hot loop VIN–C304–PGND under the IC, SW straight up into L301 through the BST cap's SW pad, VCC/FB/EN/PG out
    to the left. Absolute coordinates are derived from the pads, so the block can move as a whole."""
    U = 'U302'
    SW = net_of(F, U, '8'); BST = net_of(F, U, '7'); VCC = net_of(F, U, '1'); FB = net_of(F, U, '2')
    EN = net_of(F, U, '3'); PG = net_of(F, U, '9')
    p = {n: F.p(U, n) for n in '123456789'}
    # --- SW: pin 8 → C306 SW pad → L301 pad 1 (F.Cu polygon, 0.8 mm)
    l1 = pads_bbox(F, 'L301', '1')
    x8 = p['8'][0]
    sw_poly = box(x8 - 0.15, l1[3] - 0.3, x8 + 0.6, p['8'][1] - 0.4)
    F.zone(SW, 'F.Cu', list(sw_poly.exterior.coords), prio=3)
    F.t(SW, 'F.Cu', [p['8'], (x8, p['8'][1] - 0.6)], 0.25)
    # --- BST: pin 7 → right → up to the C306 BST pad
    cb = F.p('C306', '2')
    F.t(BST, 'F.Cu', [p['7'], (cb[0] + 0.05, p['7'][1]), (cb[0] + 0.05, cb[1])], 0.25)
    # --- VIN: pins 6/5 → C301..C303 VSYS bar (F.Cu polygon) and down to the C304 VSYS pad
    c1 = pads_bbox(F, 'C301', '1'); c3 = pads_bbox(F, 'C303', '1'); c4 = pads_bbox(F, 'C304', '1')
    vin = unary_union([box(p['6'][0] - 0.25, p['6'][1] - 0.125, c1[0] + 0.1, p['5'][1] + 0.0),
                       box(c4[0] + 0.05, p['5'][1] - 0.1, c4[2] - 0.05, c4[1] + 0.1),
                       box(c1[0], c1[1], c3[2], c1[3]),
                       box(c1[0] + 0.3, c1[1] - 0.95, c3[2], c1[1] + 0.1)])
    F.zone('VSYS', 'F.Cu', list(vin.exterior.coords), prio=3)
    # VSYS stitching vias to the In2 VSYS plane, one row above the bar
    for i in range(5):
        F.v('VSYS', (c1[0] + 0.75 + i * (c3[2] - c1[0] - 1.5) / 4, c1[1] - 0.6), 0.6)
    # --- PGND: pin 4 → C304 GND pad; GND pour under C304 and C301..C303 with vias to In1
    g4 = F.p('C304', '2')
    F.t('GND', 'F.Cu', [p['4'], (p['4'][0], p['4'][1] + 0.35), g4], 0.25)
    cg1 = pads_bbox(F, 'C301', '2'); cg3 = pads_bbox(F, 'C303', '2')
    yv = cg1[3] + 0.75
    vias = [(g4[0], yv)] + [(cg1[0] + 0.2 + i * (cg3[2] - cg1[0] - 0.4) / 4, yv) for i in range(5)]
    for v in vias:
        F.v('GND', v, 0.6)
    reg = box(g4[0] - 0.35, cg1[1], cg3[2] + 0.2, yv + 0.65)
    zone_clear(F, 'GND', 'F.Cu', reg, (g4[0], yv), clear=0.3)
    # --- VCC: pin 1 → C305 (left), GND pad → via
    cv = F.p('C305', '1'); cgv = F.p('C305', '2')
    xv = cv[0] + 0.25
    F.t(VCC, 'F.Cu', [p['1'], (xv, p['1'][1]), (xv, cv[1]), cv], 0.25)
    F.t('GND', 'F.Cu', [cgv, (cgv[0] - 0.65, cgv[1])], 0.3); F.v('GND', (cgv[0] - 0.65, cgv[1]), 0.6)
    # --- FB: pin 2 straight left across R302 / R301 / C311; R302 GND → via; R301 + C311 +5V pads joined
    cf = F.p('C311', '2')
    F.t(FB, 'F.Cu', [p['2'], (cf[0], p['2'][1])], 0.2)
    rg = F.p('R302', '2'); F.t('GND', 'F.Cu', [rg, (rg[0], rg[1] + 0.85)], 0.3); F.v('GND', (rg[0], rg[1] + 0.85), 0.6)
    F.t('+5V', 'F.Cu', [F.p('R301', '1'), F.p('C311', '1')], 0.3)
    # --- PG: pin 9 up between pin 1 and SW, then left above the VCC cap to R313
    rp = F.p('R313', '2')
    yp = cv[1] - 0.7
    F.t(PG, 'F.Cu', [p['9'], (p['9'][0], yp), (rp[0], yp), rp], 0.2)
    # --- EN: pin 3 → left → down to C312 / R310 / Q303 drain
    ce = F.p('C312', '1'); re_ = F.p('R310', '2'); qd = F.p('Q303', '3')
    xe = ce[0]
    F.t(EN, 'F.Cu', [p['3'], (xe, p['3'][1]), ce], 0.2)
    F.t(EN, 'F.Cu', [ce, re_], 0.2)
    F.t(EN, 'F.Cu', [re_, (re_[0] - 0.55, re_[1]), (qd[0] + 0.3, qd[1])], 0.2)
    q = F.p('C312', '2'); F.t('GND', 'F.Cu', [q, (q[0], q[1] + 0.8)], 0.3); F.v('GND', (q[0], q[1] + 0.8), 0.6)
    qs = F.p('Q303', '2'); rs = F.p('R312', '2')
    F.t('GND', 'F.Cu', [qs, (rs[0], qs[1]), rs], 0.3); F.v('GND', ((qs[0] + rs[0]) / 2, qs[1] + 0.85), 0.6)
    F.t('GND', 'F.Cu', [((qs[0] + rs[0]) / 2, qs[1]), ((qs[0] + rs[0]) / 2, qs[1] + 0.85)], 0.3)
    F.t(net_of(F, 'Q303', '1'), 'F.Cu', [F.p('Q303', '1'), (F.p('R312', '1')[0], F.p('Q303', '1')[1]), F.p('R312', '1')], 0.2)
    return F

def j702(F):
    """+5V band from L301 over the COUT stack to the J702 VBUS pads; J702 decoupling above the receptacle;
    CC1/CC2 to the Rp resistors on the bottom side."""
    J = 'J702'
    l2 = pads_bbox(F, 'L301', '2')
    co = [pads_bbox(F, r, '1') for r in ('C307', 'C308', 'C309')]
    vb = [pads_bbox(F, J, n) for n in ('A4', 'B4')]
    vtop, vbot = sorted(vb, key=lambda b: b[1])
    cc = [pads_bbox(F, J, n) for n in ('A5', 'B5')]
    xj = min(b[0] for b in vb + cc) - 0.3                       # 0.3 mm short of the J702 rear pad row
    k2 = pads_bbox(F, 'C702', '1'); k1 = pads_bbox(F, 'C701', '1'); kd = pads_bbox(F, 'D701', '1')
    tp = F.p('TP303', '1'); c10 = pads_bbox(F, 'C310', '1')
    ytop = min(c10[1], tp[1]) + 0.05
    band = unary_union([
        box(l2[0], ytop, xj, l2[3]),                             # band over L301 pad 2
        box(min(b[0] for b in co) - 0.1, l2[1], xj, vbot[3]),    # strip over the COUT +5V pads down to VBUS
        box(xj - 0.1, vtop[1], vtop[0] + 0.3, vtop[3]),          # stubs into the VBUS pads
        box(xj - 0.1, vbot[1], vbot[0] + 0.3, vbot[3]),
        box(xj - 0.1, ytop, kd[2], kd[3] - 0.25),                # extension over C702 / C701 / D701 cathode
    ])
    # COUT GND: pour on the left of the stack with vias to In1 (placed before the +5V zone is cleared)
    cg = [pads_bbox(F, r, '2') for r in ('C307', 'C308', 'C309')]
    xg = cg[0][0] - 0.7
    for b in cg:
        for dy in (-0.45, 0.45):
            F.v('GND', (xg, (b[1] + b[3]) / 2 + dy), 0.6)
    zone_clear(F, 'GND', 'F.Cu', box(xg - 0.6, cg[0][1], cg[0][2], cg[2][3]), (xg, (cg[0][1] + cg[0][3]) / 2))
    # C310 GND via above its pad
    g = F.p('C310', '2'); F.t('GND', 'F.Cu', [g, (g[0], g[1] - 0.85)], 0.3); F.v('GND', (g[0], g[1] - 0.85), 0.6)
    # CC1 / CC2: F.Cu stub towards the inside of the receptacle, via, bottom-side trace to R712 / R713
    for pad, r in (('A5', 'R712'), ('B5', 'R713')):
        b = pads_bbox(F, J, pad); y = (b[1] + b[3]) / 2
        v = (b[2] + 0.55, y)
        n = net_of(F, J, pad)
        F.t(n, 'F.Cu', [((b[0] + b[2]) / 2, y), v], 0.2); F.v(n, v, 0.6)
        rp = F.p(r, '2')
        F.t(n, 'B.Cu', [v, (rp[0], y), rp], 0.25)
    # Rp +5V pads (bottom) → one via into the +5V strip
    a, c = F.p('R713', '1'), F.p('R712', '1')
    vv = (xj - 0.55, (a[1] + c[1]) / 2)
    F.v('+5V', vv, 0.6)
    F.t('+5V', 'B.Cu', [a, c], 0.3); F.t('+5V', 'B.Cu', [(a[0], vv[1]), vv], 0.3)
    # J702 GND pads → shell tabs (THT, into the In1 plane)
    for pad, dy in (('A1', 0), ('B1', 0)):
        b = pads_bbox(F, J, pad); y = (b[1] + b[3]) / 2; x = (b[0] + b[2]) / 2 + 0.25
        ys = 1.0 if y > F.b.placed[J].y else -1.0
        F.t('GND', 'F.Cu', [(x, y), (x, y + ys * 1.05)], 0.5)
    # GND pour above the receptacle (C702 / C701 / D701 anode) with vias, joined to the upper shell tab
    gd = pads_bbox(F, 'D701', '2'); g1 = pads_bbox(F, 'C701', '2'); g2 = pads_bbox(F, 'C702', '2')
    jy0 = vtop[1] - 0.8                                          # just above the upper GND pad row
    reg = unary_union([box(g2[0] - 0.1, g2[1] - 0.05, gd[2] - 0.55, jy0 - 0.05), box(gd[0], gd[1], gd[2], g2[1] + 0.3)])
    for x in (g1[2] + 1.0, g1[2] + 2.4, g1[2] + 3.8):
        F.v('GND', (x, g1[1] + 0.65), 0.6)
    zone_clear(F, 'GND', 'F.Cu', reg, ((g1[0] + g1[2]) / 2, (g1[1] + g1[3]) / 2))
    # +5V vias in the strip (B.Cu Rp feed already above); then the +5V zone, cleared around everything else
    zone_clear(F, '+5V', 'F.Cu', band, ((l2[0] + l2[2]) / 2, (l2[1] + l2[3]) / 2), clear=0.3)
    return F

# ------------------------------------------------------------------ 2S pack: J301 → F301 → VBAT, B− → Q301/Q302 → GND
def battery(F):
    # VBAT pour: BAT pin stub → under the C216/C217 VBAT pads → F301 pad 2 (taller between the caps and the fuse)
    U = 'U202'
    xb = F.p(U, '23')[0] + 0.5
    a1 = pads_bbox(F, 'C216', '1'); a2 = pads_bbox(F, 'C217', '1'); g2 = pads_bbox(F, 'C217', '2')
    f2 = pads_bbox(F, 'F301', '2'); f1 = pads_bbox(F, 'F301', '1')
    yb = (F.p(U, '23')[1] + F.p(U, '22')[1]) / 2
    reg = unary_union([box(xb - 0.2, min(a1[1], yb - 0.3), f2[2], max(a1[3] + 0.4, yb + 0.3)),
                       box(g2[2] + 0.3, f2[1], f2[2], f2[3])])
    tp = F.p('TP302', '1')
    F.t('VBAT', 'F.Cu', [((f2[0] + f2[2]) / 2, f2[3] - 0.3), tp], 0.6)
    zone_clear(F, 'VBAT', 'F.Cu', reg, ((a1[0] + a1[2]) / 2, (a1[1] + a1[3]) / 2))
    # BAT+ pour: F301 pad 1 → J301 pin 3
    J = 'J301'
    j3 = pads_bbox(F, J, '3'); j2 = pads_bbox(F, J, '2'); j1 = pads_bbox(F, J, '1')
    bp = net_of(F, J, '3')
    reg = unary_union([box(f1[0], min(f1[1], j3[1]), j3[2] + 0.3, f1[3]), box(j3[0], j3[1], j3[2], j3[3])])
    zone_clear(F, bp, 'F.Cu', reg, ((f1[0] + f1[2]) / 2, (f1[1] + f1[3]) / 2))
    # B−: J301 pin 1 → Q301 sources (pins 1..3)
    bm = net_of(F, J, '1')
    s1 = [pads_bbox(F, 'Q301', n) for n in ('1', '2', '3')]; g1 = pads_bbox(F, 'Q301', '4')
    reg = unary_union([box(j1[0], min(b[1] for b in s1) - 0.15, max(b[2] for b in s1), g1[1] - 0.3),
                       box(j1[0], j1[1], j1[2], j1[3])])
    zone_clear(F, bm, 'F.Cu', reg, ((j1[0] + j1[2]) / 2, (j1[1] + j1[3]) / 2))
    tp7 = F.p('TP307', '1'); F.t(bm, 'F.Cu', [((j1[0] + j1[2]) / 2, j1[1] + 0.3), tp7], 0.8)
    # common drain Q301/Q302 (pads 5, facing +X)
    d1 = pads_bbox(F, 'Q301', '5'); d2 = pads_bbox(F, 'Q302', '5')
    dn = net_of(F, 'Q301', '5')
    reg = box(min(d1[0], d2[0]) + 0.45, d1[1], max(d1[2], d2[2]), d2[3])
    zone_clear(F, dn, 'F.Cu', reg, ((d1[0] + d1[2]) / 2, (d1[1] + d1[3]) / 2))
    # Q302 sources → GND pour with vias towards J301
    s2 = [pads_bbox(F, 'Q302', n) for n in ('1', '2', '3')]; gq2 = pads_bbox(F, 'Q302', '4')
    y0 = min(b[1] for b in s2) - 0.15; y1 = gq2[1] - 0.3
    x0 = j2[2] + 0.35
    for i in range(3):
        F.v('GND', (x0 + 0.6 + i * 1.2, (y0 + y1) / 2), 0.6)
    zone_clear(F, 'GND', 'F.Cu', box(x0, y0, max(b[2] for b in s2), y1), ((s2[0][0] + s2[0][2]) / 2, (s2[0][1] + s2[0][3]) / 2))
    return F

def tb6612(F):
    """TB6612 VCC (pin 20) sits inside the VSYS island of In2: tie it on B.Cu straight to its 3V3 decoupling capacitor
    C501, which fans out to the +3V3 plane just outside the island."""
    F.t('+3V3', 'B.Cu', [F.p('U501', '20'), F.p('C501', '1')], 0.3)
    return F

def esp_usb_pads(F):
    """TP403 (GND pad of the native-USB test pads, bottom side under the module, where vias are not allowed): tie it on
    B.Cu to the module's thermal-pad vias."""
    tp = F.p('TP403', '1')
    th = min(F.b.placed['U401'].pad_xy('41'), key=lambda q: (q[0] - tp[0]) ** 2 + (q[1] - tp[1]) ** 2)
    F.t('GND', 'B.Cu', [tp, th], 0.4)
    return F

def route_fixed(R, b):
    F = FX(R, b)
    fixed.buck(F, 'U303', 'L302', 'C321', 'C320', 'C323', 'C322', 'R320', 'R321', 'C324', 'C325', 'C326', '+3V3')
    charger(F)
    fet_pairs(F)
    battery(F)
    pi_buck(F)
    j702(F)
    tb6612(F)
    esp_usb_pads(F)
    return F
