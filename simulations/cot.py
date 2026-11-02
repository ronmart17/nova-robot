"""Behavioural constant-on-time (D-CAP-like) synchronous buck for ngspice (XSPICE one-shots).
Comparator on V(FB) + injected ramp (RC replica of the switch node, AC part) + slow integrator vs Vref;
on-time one-shot with width Vout/(Vin·fsw) controlled by Vin; minimum off-time blanking one-shot; ideal synchronous
switch with Rds(on); input current drawn from VIN while the high side is on."""

def cot_buck(p, vin_node='vin', out_node='vout', pre='X'):
    P = lambda k: p[k]
    n = lambda x: f'{pre}{x}'
    vins = [3, 4, 5, 6, 7, 8, 9, 10, 12, 15, 18, 24]
    pws = [p['vout'] / (max(v, p['vout'] / 0.98) * p['fsw']) for v in vins]   # max duty ~98 %
    ca = ' '.join(str(v) for v in vins); pa = ' '.join(f'{w:.6g}' for w in pws)
    s = [f'* --- COT buck {pre}']
    # power stage
    s.append(f'B{pre}sw {n("sw")} 0 V = v({n("on")})*v({vin_node})')
    s.append(f'R{pre}sw {n("sw")} {n("swr")} {{({P("rhs")}+{P("rls")})/2}}')
    s.append(f'L{pre}1 {n("swr")} {n("lx")} {P("L")} ic={p.get("il0", 0)}')
    s.append(f'R{pre}dcr {n("lx")} {out_node} {P("dcr")}')
    s.append(f'B{pre}iin {vin_node} 0 I = v({n("on")})*i(L{pre}1)')
    # feedback
    s.append(f'R{pre}t {out_node} {n("fb")} {P("rtop")}')
    s.append(f'R{pre}b {n("fb")} 0 {P("rbot")}')
    s.append(f'C{pre}ff {out_node} {n("fb")} {P("cff")}')
    s.append(f'R{pre}inj {n("sw")} {n("rp")} 1k')
    s.append(f'C{pre}inj {n("rp")} 0 {{{P("tau_inj")}/1k}} ic={P("vout")}')
    s.append(f'B{pre}int 0 {n("x")} I = {1e-9 / p.get("tau_int", 300e-6):.4g}*(v({n("fb")})-{P("vref")})')
    s.append(f'C{pre}int {n("x")} 0 1n ic={p.get("x0", 0)}')
    # injected ramp: AC part of the RC replica of SW (high-pass via a slow replica, so the I·R offset is not injected)
    # and clamped to ±1.5 × its steady-state half-amplitude, like a bounded internal ramp generator — otherwise a long
    # off-time after a load release produces a large fake "go on" signal that a real D-CAP3 ramp does not.
    vn = p.get('vin_nom', 7.4)
    a = 1.5 * p['kinj'] * (vn - p['vout']) * p['vout'] / (vn * p['fsw'] * p['tau_inj']) / 2
    s.append(f'R{pre}hp {n("rp")} {n("rpf")} 1k')
    s.append(f'C{pre}hp {n("rpf")} 0 {{{p.get("tau_hp", 20 / p["fsw"])}/1k}} ic={P("vout")}')
    s.append(f'B{pre}fbm {n("fbm")} 0 V = v({n("fb")}) + max(-{a:.4g}, min({a:.4g}, {P("kinj")}*(v({n("rp")})-v({n("rpf")})))) + v({n("x")})')
    # comparator (smooth), trigger = comp AND NOT on AND NOT blank
    s.append(f'B{pre}cmp {n("cmp")} 0 V = 0.5*(1+tanh(({P("vref")}-v({n("fbm")}))*4000))')
    s.append(f'B{pre}trg {n("trg")} 0 V = v({n("cmp")})*(1-v({n("on")}))*(1-v({n("blk")}))')
    s.append(f'B{pre}nof {n("nof")} 0 V = 1-v({n("on")})')
    s.append(f'V{pre}clr {n("clr")} 0 0')
    s.append(f'A{pre}on {n("trg")} {vin_node} {n("clr")} {n("on")} {pre}ON')
    s.append(f'.model {pre}ON oneshot(cntl_array=[{ca}] pw_array=[{pa}] clk_trig=0.5 pos_edge_trig=true '
             f'out_low=0 out_high=1 rise_delay=2n fall_delay=2n retrig=false)')
    s.append(f'A{pre}bk {n("nof")} {vin_node} {n("clr")} {n("blk")} {pre}BK')
    s.append(f'.model {pre}BK oneshot(cntl_array=[0 30] pw_array=[{p.get("toff_min", 220e-9)} {p.get("toff_min", 220e-9)}] '
             f'clk_trig=0.5 pos_edge_trig=true out_low=0 out_high=1 rise_delay=1n fall_delay=1n retrig=false)')
    return s
