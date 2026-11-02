from sch import G, snap
from parts import P

def part(key):
    d = P[key]
    return d['value'], d['footprint'], dict(d.get('fields', {}))

def lib_of(key):
    return P[key].get('lib', 'Device:R')

TWO_PIN = ('Device:R', 'Device:C', 'Device:C_Polarized', 'Device:L', 'Device:Fuse', 'Device:Thermistor_NTC',
           'Device:FerriteBead_Small', 'Device:LED', 'Device:D', 'Diode:SMAJ6.5A')

def place_part(sh, key, ref, x, y, rot=0, mirror=None, dnp=False, **kw):
    """Place a part from the database. Fields: explicit ref_at/val_at (screen coordinates) or automatic fpos."""
    value, fp, fields = part(key)
    lib = P[key].get('lib')
    lab = dict(kw)
    if 'ref_at' not in lab and 'fpos' not in lab:
        if lib in TWO_PIN or lib.startswith('Diode:'):
            from sch import transform, tpt
            sdef = sh.project.lib.get(lib); m = transform(rot, mirror)
            xs = {round(tpt(m, p_['x'], -p_['y'])[0], 3) for p_ in sdef.pins}
            lab['fpos'] = 'right' if len(xs) == 1 else 'tb'
        elif lib.startswith('Transistor_FET:') or lib.startswith('Device:Q_'):
            lab['fpos'] = 'right'
    if P[key].get('in_bom') is False and 'in_bom' not in lab:
        lab['in_bom'] = False   # pads, holes and fiducials: on the board, not in the BOM
    return sh.place(lib, ref, value, x, y, rot=rot, mirror=mirror, footprint=fp, fields=fields, dnp=dnp, **lab)

def vpart_between(sh, key, ref, x, y_top, top, bottom='GND', dnp=False, top_kind='net'):
    """Vertical 2-pin part whose pin1 is at (x, y_top). top/bottom: power kind names or ('label', net) or None (caller wires)."""
    inst = place_part(sh, key, ref, x, y_top + 3.81, rot=0, dnp=dnp)
    for pin, n in (('1', top), ('2', bottom)):
        if n is None: continue
        if isinstance(n, tuple) and n[0] == 'label':
            sh.pin_label(inst, pin, n[1], length=0 if len(n) < 3 else n[2])
        elif isinstance(n, tuple) and n[0] == 'net':
            sh.assign(inst, pin, n[1])
        else:
            sh.pin_power(inst, pin, n, length=0)
    return inst

def cap_rail(sh, kind, x0, y, caps, dx=None, power_side='left', label=None, start_net=None):
    """Horizontal rail at y starting at x0; caps hang below (pin1 on rail), GND at bottom.
    caps: list of (ref, partkey[, dnp]). Returns (x_end, insts)."""
    insts = []
    xs = []
    x = x0
    if dx is None:
        dx = 10.16 if max(len(P[c[1]]['value']) for c in caps) <= 5 else 12.7
    for c in caps:
        ref, key = c[0], c[1]
        dnp = len(c) > 2 and c[2]
        inst = place_part(sh, key, ref, x, y + 3.81, rot=0, dnp=dnp)
        sh.assign(inst, '1', kind if start_net is None else start_net)
        sh.pin_power(inst, '2', 'GND', length=0)
        insts.append(inst); xs.append(x)
        x += dx
    if len(xs) > 1:
        sh.wire((xs[0], y), (xs[-1], y))
        # split into segments at each cap so connections are at endpoints
        sh.items.pop()
        for a, b in zip(xs, xs[1:]):
            sh.wire((a, y), (b, y))
    return xs, insts

def place_vertical_k_top(sh, key, ref, x, y, **kw):
    """Place a 2-pin diode vertically with pin 1 (cathode) at the top, whatever the library graphics."""
    from sch import transform, tpt
    lib = P[key].get('lib')
    sdef = sh.project.lib.get(lib)
    pins = {p_['num']: p_ for p_ in sdef.pins}
    for r in (90, 270):
        m = transform(r)
        y1 = tpt(m, pins['1']['x'], -pins['1']['y'])[1]
        y2 = tpt(m, pins['2']['x'], -pins['2']['y'])[1]
        if y1 < y2:
            return place_part(sh, key, ref, x, y, rot=r, **kw)
    raise RuntimeError(ref)
