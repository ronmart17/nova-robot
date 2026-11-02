"""KiCad 10 schematic writer with geometric helpers and intended-netlist tracking."""
import uuid, re, os, math, copy
from sexpr import Sym, fmt, q
import kilib

NS = uuid.UUID('6f1c7a52-3b0e-4d6a-9d2b-5e1f0a7c9b11')
def uid(*parts):
    return str(uuid.uuid5(NS, '/'.join(str(p) for p in parts)))

G = 2.54
def snap(v, g=1.27):
    return round(round(v / g) * g, 4)

def eff(size=1.27, justify=None, hide=False, bold=False, italic=False):
    font = ['font', ['size', size, size]]
    if bold: font.append(['bold', Sym('yes')])
    if italic: font.append(['italic', Sym('yes')])
    e = ['effects', font]
    if justify: e.append(['justify'] + [Sym(j) for j in justify.split()])
    if hide: e.append(['hide', Sym('yes')])
    return e

def prop_node(name, value, x, y, ang=0, hide=False, justify=None, size=1.27):
    n = ['property', name, value, ['at', x, y, ang]]
    if hide: n.append(['hide', Sym('yes')])
    n += [['show_name', Sym('no')], ['do_not_autoplace', Sym('no')], eff(size, justify)]
    return n

# ---------------- orientation math (mirrors SCH_SYMBOL::SetOrientation) ----------------
def _compose(m, t):
    return (m[0]*t[0] + m[2]*t[1], m[1]*t[0] + m[3]*t[1], m[0]*t[2] + m[2]*t[3], m[1]*t[2] + m[3]*t[3])
CCW = (0, 1, -1, 0); CW = (0, -1, 1, 0); MX = (1, 0, 0, -1); MY = (-1, 0, 0, 1); ID = (1, 0, 0, 1)
def transform(rot, mirror=None):
    m = ID
    if rot == 90: m = _compose(m, CCW)
    elif rot == 180: m = _compose(_compose(m, CCW), CCW)
    elif rot == 270: m = _compose(m, CW)
    if mirror == 'x': m = _compose(m, MX)
    if mirror == 'y': m = _compose(m, MY)
    return m
def tpt(m, x, y):
    return (m[0]*x + m[1]*y, m[2]*x + m[3]*y)

DIRS = {0: (1, 0), 90: (0, 1), 180: (-1, 0), 270: (0, -1)}  # lib pin angle -> vector toward body, lib coords (Y up)

class Inst:
    def __init__(self, sheet, sdef, ref, x, y, rot, mirror, unit):
        self.sheet, self.sdef, self.ref, self.x, self.y, self.rot, self.mirror, self.unit = sheet, sdef, ref, x, y, rot, mirror, unit
        self.m = transform(rot, mirror)
    def _pin(self, key):
        cands = [p for p in self.sdef.pins if (p['unit'] in (0, self.unit)) and (p['num'] == str(key))]
        if not cands:
            cands = [p for p in self.sdef.pins if (p['unit'] in (0, self.unit)) and p['name'] == str(key) and not p['hidden']]
        if not cands:
            cands = [p for p in self.sdef.pins if (p['unit'] in (0, self.unit)) and p['name'] == str(key)]
        if not cands:
            raise KeyError(f'{self.ref}: pin {key} not found in {self.sdef.lib_id}')
        return cands[0]
    def pin(self, key):
        """Absolute connection point (schematic coords, Y down) and outward unit vector."""
        p = self._pin(key)
        dx, dy = tpt(self.m, p['x'], -p['y'])
        bx, by = DIRS[int(p['ang']) % 360]
        ox, oy = tpt(self.m, -bx, by)  # outward = opposite of toward-body; lib Y up -> internal Y down
        return (round(self.x + dx, 4), round(self.y + dy, 4)), (int(round(ox)), int(round(oy)))
    def pins_same_position(self, key):
        p = self._pin(key)
        return [q2['num'] for q2 in self.sdef.pins if q2['unit'] in (0, self.unit) and q2['x'] == p['x'] and q2['y'] == p['y']]

class Sheet:
    def __init__(self, project, filename, title, page, paper='A3', path=None, sheet_uuid=None, comments=()):
        self.project, self.filename, self.title, self.page, self.paper = project, filename, title, page, paper
        self.uuid = uid(project.name, filename)
        self.path = path  # instance path string, e.g. '/root' or '/root/sheetuuid'
        self.items = []
        self.lib_ids = set()
        self.comments = comments
        self.net = {}       # (ref, pinnum) -> net name (intended)
        self.refs = {}
        self.power_count = 0
        self.children = []  # (sheet object, x, y, w, h, pins)
        self.pwr_ref_base = page * 100
        self.pin_points = []
        self.insts = []
    # ----- intended netlist -----
    def assign(self, inst, pin, net):
        for num in inst.pins_same_position(pin):
            k = (inst.ref, num)
            if k in self.net and self.net[k] != net:
                raise ValueError(f'{inst.ref}.{num} assigned {self.net[k]} and {net}')
            self.net[k] = net
    # ----- primitives -----
    def wire(self, *pts):
        pts = [(round(p[0], 4), round(p[1], 4)) for p in pts]
        for a, b in zip(pts, pts[1:]):
            if abs(a[0] - b[0]) < 1e-3 and abs(a[1] - b[1]) < 1e-3: continue
            self.items.append(['wire', ['pts', ['xy', a[0], a[1]], ['xy', b[0], b[1]]],
                               ['stroke', ['width', 0], ['type', Sym('default')]], ['uuid', uid(self.uuid, 'w', a, b)]])
    def junction(self, p):
        self.items.append(['junction', ['at', p[0], p[1]], ['diameter', 0], ['color', 0, 0, 0, 0], ['uuid', uid(self.uuid, 'j', p)]])
    def nc(self, p):
        self.items.append(['no_connect', ['at', p[0], p[1]], ['uuid', uid(self.uuid, 'nc', p)]])
    def _label_angle(self, d):
        # d: direction in which the label text should extend from the connection point
        return {(1, 0): (0, 'left'), (-1, 0): (180, 'right'), (0, -1): (90, 'left'), (0, 1): (270, 'right')}[d]
    def label(self, net, p, d=(1, 0), size=1.27):
        ang, j = self._label_angle(d)
        self.items.append(['label', net, ['at', p[0], p[1], ang], eff(size, j + ' bottom'), ['uuid', uid(self.uuid, 'l', net, p)]])
    def glabel(self, net, p, d=(1, 0), shape='bidirectional'):
        ang, j = self._label_angle(d)
        self.items.append(['global_label', net, ['shape', Sym(shape)], ['at', p[0], p[1], ang], ['fields_autoplaced', Sym('yes')],
                           eff(1.27, j), ['uuid', uid(self.uuid, 'g', net, p)],
                           ['property', 'Intersheetrefs', '${INTERSHEET_REFS}', ['at', p[0], p[1], 0], ['hide', Sym('yes')],
                            ['show_name', Sym('no')], ['do_not_autoplace', Sym('no')], eff(1.27, j)]])
    def hlabel(self, net, p, d=(1, 0), shape='bidirectional'):
        ang, j = self._label_angle(d)
        reg = self.project.hier_shape.setdefault(self.filename, {})
        shape = reg.setdefault(net, shape)
        self.items.append(['hierarchical_label', net, ['shape', Sym(shape)], ['at', p[0], p[1], ang], eff(1.27, j),
                           ['uuid', uid(self.uuid, 'h', net, p)]])
        self.project.hier.setdefault(self.filename, []).append((net, shape))
    def text(self, s, p, size=1.27, bold=False, justify=None, ang=0, italic=False):
        if justify is None:
            justify = 'left top' if '\n' in s else 'left bottom'
        self.items.append(['text', s, ['exclude_from_sim', Sym('no')], ['at', p[0], p[1], ang], eff(size, justify, bold=bold, italic=italic),
                           ['uuid', uid(self.uuid, 't', s, p)]])
    def textbox(self, s, p, w, h, size=1.27, bold=False, border=True, fill=None):
        node = ['text_box', s, ['exclude_from_sim', Sym('no')], ['at', p[0], p[1], 0], ['size', w, h],
                ['margins', 0.9525, 0.9525, 0.9525, 0.9525],
                ['stroke', ['width', 0 if border else -0.0001], ['type', Sym('solid' if border else 'default')]],
                ['fill', ['type', Sym('none')]] if not fill else ['fill', ['type', Sym('color')], ['color'] + list(fill)],
                eff(size, 'left top', bold=bold), ['uuid', uid(self.uuid, 'tb', s[:40], p)]]
        self.items.append(node)
    def rect(self, p1, p2, dash=True, width=0.2, color=None):
        st = ['stroke', ['width', width], ['type', Sym('dash' if dash else 'solid')]]
        if color: st.append(['color'] + list(color))
        self.items.append(['rectangle', ['start', p1[0], p1[1]], ['end', p2[0], p2[1]], st,
                           ['fill', ['type', Sym('none')]], ['uuid', uid(self.uuid, 'r', p1, p2)]])
    def section(self, title, p1, p2, color=(0, 72, 72, 1)):
        """Dashed frame with a title in the top-left corner."""
        self.rect(p1, p2, dash=True, width=0.25, color=color)
        self.text(title, (p1[0] + 1.27, p1[1] + 3.81), size=2.0, bold=True)
    # ----- symbols -----
    def body_bbox(self, sdef, unit, m):
        pts = sdef.graphics.get(0, []) + sdef.graphics.get(unit, [])
        if not pts: return (-1.27, -1.27, 1.27, 1.27)
        tp = [tpt(m, px, -py) for px, py in pts]
        return (min(a for a, b in tp), min(b for a, b in tp), max(a for a, b in tp), max(b for a, b in tp))
    def auto_fields(self, bb, fpos, gap=1.27):
        x0, y0, x1, y1 = bb; cx, cy = (x0 + x1) / 2, (y0 + y1) / 2; h = 0.635
        if fpos == 'right':  return (x1 + gap, cy - 1.27, 'left'), (x1 + gap, cy + 1.27, 'left')
        if fpos == 'left':   return (x0 - gap, cy - 1.27, 'right'), (x0 - gap, cy + 1.27, 'right')
        if fpos == 'tb':     return (cx, y0 - gap - h, None), (cx, y1 + gap + h, None)
        if fpos == 'above':  return (cx, y0 - gap - h - 2.54, None), (cx, y0 - gap - h, None)
        if fpos == 'below':  return (cx, y1 + gap + h, None), (cx, y1 + gap + h + 2.54, None)
        if fpos == 'ic':     return (x0, y0 - gap - h, 'left'), (x1, y0 - gap - h, 'right')
        if fpos == 'ic_below': return (x0, y1 + gap + h, 'left'), (x1, y1 + gap + h, 'right')
        if fpos == 'ic_above2': return (x0, y0 - gap - h - 2.54, 'left'), (x0, y0 - gap - h, 'left')
        if fpos == 'ic_below2': return (x0, y1 + gap + h, 'left'), (x0, y1 + gap + h + 2.54, 'left')
        raise ValueError(fpos)
    def place(self, lib_id, ref, value, x, y, rot=0, mirror=None, unit=1, footprint=None, fields=None, dnp=False,
              in_bom=True, on_board=True, ref_at=None, val_at=None, hide_value=False, hide_ref=False, exclude_from_sim=False,
              fpos=None):
        sdef = self.project.lib.get(lib_id)
        self.lib_ids.add(lib_id)
        x, y = snap(x), snap(y)
        inst = Inst(self, sdef, ref, x, y, rot, mirror, unit)
        if not sdef.is_power:
            if ref in self.project.refs and self.project.refs[ref] != (self.filename, unit):
                if self.project.refs[ref][0] != self.filename or self.project.refs[ref][1] == unit:
                    raise ValueError(f'duplicate ref {ref}')
            self.project.refs[ref] = (self.filename, unit)
        m = inst.m
        node = ['symbol', ['lib_id', lib_id], ['at', x, y, rot]]
        if mirror: node.append(['mirror', Sym(mirror)])
        node += [['unit', unit], ['body_style', 1], ['exclude_from_sim', Sym('yes' if exclude_from_sim else 'no')],
                 ['in_bom', Sym('yes' if in_bom else 'no')], ['on_board', Sym('yes' if on_board else 'no')],
                 ['in_pos_files', Sym('yes' if on_board else 'no')], ['dnp', Sym('yes' if dnp else 'no')],
                 ['fields_autoplaced', Sym('yes')], ['uuid', uid(self.uuid, 'sym', ref, unit)]]
        # ---- field positions: given in screen coordinates (dx, dy, just) ----
        rotated = abs(m[1]) > 0.5
        fang = 90 if rotated else 0
        def stored_just(j):
            if j in (None, 'center'): return None
            u = (1, 0) if fang == 0 else (0, -1)
            d = tpt(m, *u)
            plus = d[0] > 0.5
            if j == 'left': return 'left' if plus else 'right'
            return 'right' if plus else 'left'
        if ref_at is None and val_at is None and fpos:
            ref_at, val_at = self.auto_fields(self.body_bbox(sdef, unit, m), fpos)
        def lib_field(name):
            f = sdef.fields.get(name)
            if not f: return (x, y, 0, None)
            fx, fy = tpt(m, f['x'], -f['y'])
            return (x + fx, y + fy, f.get('ang', 0), f.get('justify'))
        if ref_at is not None:
            rx, ry, ra, rj = x + ref_at[0], y + ref_at[1], fang, stored_just(ref_at[2] if len(ref_at) > 2 else 'left')
        else:
            rx, ry, ra, rj = lib_field('Reference')
        if val_at is not None:
            vx, vy, va, vj = x + val_at[0], y + val_at[1], fang, stored_just(val_at[2] if len(val_at) > 2 else 'left')
        else:
            vx, vy, va, vj = lib_field('Value')
        props = [prop_node('Reference', ref, round(rx, 4), round(ry, 4), ra, hide=hide_ref or sdef.is_power, justify=rj)]
        props.append(prop_node('Value', value, round(vx, 4), round(vy, 4), va, hide=hide_value, justify=vj))
        fp = footprint if footprint is not None else sdef.fields.get('Footprint', {}).get('value', '')
        props.append(prop_node('Footprint', fp, x, y, 0, hide=True))
        props.append(prop_node('Datasheet', (fields or {}).get('Datasheet', sdef.fields.get('Datasheet', {}).get('value', '')), x, y, 0, hide=True))
        props.append(prop_node('Description', (fields or {}).get('Description', sdef.fields.get('Description', {}).get('value', '')), x, y, 0, hide=True))
        for k, v in (fields or {}).items():
            if k in ('Datasheet', 'Description'): continue
            props.append(prop_node(k, v, x, y, 0, hide=True))
        node += props
        for p in sdef.pins:
            if p['unit'] in (0, unit):
                node.append(['pin', p['num'], ['uuid', uid(self.uuid, 'pin', ref, unit, p['num'])]])
        node.append(['instances', ['project', self.project.name,
                                   ['path', self.path, ['reference', ref], ['unit', unit]]]])
        self.items.append(node)
        inst.value = value
        for pp in sdef.pins:
            if pp['unit'] in (0, unit):
                (ax, ay), _ = inst.pin(pp['num'])
                if (ax, ay) not in self.pin_points: self.pin_points.append((ax, ay))
        self.insts.append(inst)
        return inst
    def power(self, kind, p, rot=0):
        lib_id = self.project.power_lib(kind)
        self.power_count += 1
        ref = f'#PWR{self.pwr_ref_base + self.power_count:03d}'
        sdef = self.project.lib.get(lib_id)
        inst = self.place(lib_id, ref, kind, p[0], p[1], rot=rot)
        return inst
    # ----- composite helpers -----
    def stub(self, inst, pin, length=2.54):
        (px, py), (dx, dy) = inst.pin(pin)
        end = (round(px + dx * length, 4), round(py + dy * length, 4))
        if length > 0:
            self.wire((px, py), end)
        return end, (dx, dy)
    def pin_label(self, inst, pin, net, length=2.54, kind='local', shape='bidirectional'):
        end, d = self.stub(inst, pin, length)
        if kind == 'local': self.label(net, end, d)
        elif kind == 'global': self.glabel(net, end, d, shape)
        elif kind == 'hier': self.hlabel(net, end, d, shape)
        self.assign(inst, pin, net)
        return end
    def pin_power(self, inst, pin, kind, length=2.54):
        end, d = self.stub(inst, pin, length)
        rot = {(0, -1): 0, (0, 1): 180, (1, 0): 270, (-1, 0): 90}[d]
        if kind == 'GND' or kind.startswith('GND'):
            rot = {(0, 1): 0, (0, -1): 180, (1, 0): 90, (-1, 0): 270}[d]
        self.power(kind, end, rot)
        self.assign(inst, pin, kind)
        return end
    def pin_nc(self, inst, pin):
        (px, py), _ = inst.pin(pin)
        self.nc((px, py))
        self.assign(inst, pin, f'__NC__{inst.ref}.{pin}')
    def connect(self, net, *pins_or_points, route='auto'):
        """Wire a list of (inst,pin) or points in sequence with orthogonal segments; assign net to pins."""
        pts = []
        for item in pins_or_points:
            if isinstance(item, tuple) and len(item) == 2 and isinstance(item[0], Inst):
                p, _ = item[0].pin(item[1]); pts.append(p); self.assign(item[0], item[1], net)
            else:
                pts.append(item)
        for a, b in zip(pts, pts[1:]):
            if a[0] == b[0] or a[1] == b[1]:
                self.wire(a, b)
            else:
                mid = (b[0], a[1]) if route in ('auto', 'hv') else (a[0], b[1])
                self.wire(a, mid, b)
        return pts
    # ----- output -----
    def node(self, lib_symbols_node, extra=()):
        tb = ['title_block', ['title', self.title], ['date', self.project.date], ['rev', self.project.rev],
              ['company', self.project.company]]
        for i, c in enumerate(self.comments, start=1):
            tb.append(['comment', i, c])
        root = ['kicad_sch', ['version', 20260306], ['generator', 'eeschema'], ['generator_version', '10.0'],
                ['uuid', self.uuid], ['paper', self.paper], tb, lib_symbols_node]
        root += self.items
        root += list(extra)
        root.append(['embedded_fonts', Sym('no')])
        return root

class Project:
    def __init__(self, name, lib, date, rev, company):
        self.name, self.lib, self.date, self.rev, self.company = name, lib, date, rev, company
        self.refs = {}
        self.hier = {}
        self.hier_shape = {}
        self.root_uuid = uid(name, name + '.kicad_sch')
        self.power_map = {'GND': 'power:GND', '+3V3': 'power:+3V3', '+5V': 'power:+5V', 'VBUS': 'power:VBUS',
                          'VSYS': 'robot:VSYS', 'VBAT': 'robot:VBAT', 'PWR_FLAG': 'power:PWR_FLAG'}
    def power_lib(self, kind):
        return self.power_map[kind]

# ---------------- automatic junctions ----------------
def _on_seg(p, a, b):
    if a[0] == b[0] == p[0]:
        return min(a[1], b[1]) < p[1] < max(a[1], b[1])
    if a[1] == b[1] == p[1]:
        return min(a[0], b[0]) < p[0] < max(a[0], b[0])
    return False

def add_junctions(sheet, extra_points=()):
    segs = []
    for it in sheet.items:
        if it[0] == 'wire':
            pts = it[1]
            a = (pts[1][1], pts[1][2]); b = (pts[2][1], pts[2][2])
            segs.append((a, b))
    pts = {}
    def bump(p, n=1):
        p = (round(p[0], 4), round(p[1], 4)); pts[p] = pts.get(p, 0) + n
    for a, b in segs:
        bump(a); bump(b)
    for p in sheet.pin_points:
        bump(p)
    out = []
    for p, n in pts.items():
        interior = sum(1 for a, b in segs if _on_seg(p, a, b))
        if n + 2 * interior >= 3 and (n - sheet.pin_points.count(p) >= 1 or interior):
            out.append(p)
    for p in out:
        sheet.junction(p)
    return out
