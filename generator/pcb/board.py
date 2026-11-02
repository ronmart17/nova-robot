"""KiCad 10 board generator (.kicad_pcb, format 20260206): library footprints transformed to the top/bottom
side, nets by name, tracks, vias, zones, outline and texts."""
import os, sys, math, copy, uuid, re
import xml.etree.ElementTree as ET
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sx import parse, kids, kid, Sym, fmt
import fpdb as fplib

NS = uuid.UUID('3a1f6c2e-8d4b-4e7a-9c55-2b7d1e0f4a63')
def uid(*p):
    return str(uuid.uuid5(NS, '/'.join(str(x) for x in p)))

def r4(v):
    return round(v + 0.0, 4)

SLASH_SHEETS = []      # sheet names containing '/', which KiCad escapes as {slash} in net names

def knet(name):
    for sh in SLASH_SHEETS:
        name = name.replace('/' + sh + '/', '/' + sh.replace('/', '{slash}') + '/')
    return name

# ------------------------------------------------------------------ netlist (kicadxml)
class Comp:
    def __init__(self, ref, value, footprint, fields, path, sheetname, sheetfile, dnp, in_bom):
        self.ref, self.value, self.footprint, self.fields = ref, value, footprint, fields
        self.path, self.sheetname, self.sheetfile, self.dnp, self.in_bom = path, sheetname, sheetfile, dnp, in_bom
        self.pins = {}   # pin -> (net, pinfunction, pintype)

def read_netlist(xml_path):
    t = ET.parse(xml_path).getroot()
    comps = {}
    for c in t.find('components'):
        f = {x.get('name'): (x.text or '') for x in (c.find('fields') if c.find('fields') is not None else [])}
        props = {p.get('name'): p.get('value') for p in c.findall('property')}
        sp = c.find('sheetpath').get('tstamps')
        ts = c.findtext('tstamps')
        path = (sp if sp.endswith('/') else sp + '/') + ts
        comps[c.get('ref')] = Comp(c.get('ref'), c.findtext('value'), c.findtext('footprint') or '', f, path,
                                   props.get('Sheetname', ''), props.get('Sheetfile', ''), 'dnp' in props,
                                   'exclude_from_bom' not in props)
        shn = props.get('Sheetname', '')
        if '/' in shn and shn not in SLASH_SHEETS: SLASH_SHEETS.append(shn)
    nets = {}
    for n in t.find('nets'):
        name = n.get('name')
        nodes = []
        for nd in n.findall('node'):
            r, p = nd.get('ref'), nd.get('pin')
            nodes.append((r, p))
            if r in comps:
                comps[r].pins[p] = (name, nd.get('pinfunction') or '', nd.get('pintype') or '')
        nets[name] = nodes
    return comps, nets

# ------------------------------------------------------------------ geometry
def rot(lx, ly, deg):
    """KiCad rotation (counter-clockwise angle on screen, Y axis pointing down)."""
    a = math.radians(deg); c, s = math.cos(a), math.sin(a)
    return (lx * c + ly * s, -lx * s + ly * c)

FLIP_LAYER = {}
for a, b in (('F.Cu', 'B.Cu'), ('F.Mask', 'B.Mask'), ('F.Paste', 'B.Paste'), ('F.SilkS', 'B.SilkS'), ('F.Fab', 'B.Fab'),
             ('F.CrtYd', 'B.CrtYd'), ('F.Adhes', 'B.Adhes')):
    FLIP_LAYER[a] = b; FLIP_LAYER[b] = a

class Placed:
    def __init__(self, comp, libid, x, y, angle, side, node, pads):
        self.comp, self.libid, self.x, self.y, self.angle, self.side, self.node, self.pads = comp, libid, x, y, angle, side, node, pads

    def pad_xy(self, num):
        """Absolute centres of all pads with that number."""
        out = []
        for p in self.pads:
            if p['num'] == str(num):
                ly = -p['y'] if self.side == 'B' else p['y']
                dx, dy = rot(p['x'], ly, self.angle)
                out.append((r4(self.x + dx), r4(self.y + dy)))
        return out

    def pad(self, num):
        return self.pad_xy(num)[0]

    def bbox(self):
        x0, y0, x1, y1 = fplib.courtyard(fplib.load(self.libid))
        pts = []
        for (lx, ly) in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            if self.side == 'B': ly = -ly
            dx, dy = rot(lx, ly, self.angle); pts.append((self.x + dx, self.y + dy))
        return (min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts))

# ------------------------------------------------------------------ board
class Board:
    def __init__(self, name, comps, nets, layers=4, thickness=1.6, title='', rev='A', date='', company='', aux=(90, 160)):
        self.aux = aux
        self.name, self.comps, self.nets = name, comps, nets
        self.layers, self.thickness = layers, thickness
        self.title, self.rev, self.date, self.company = title, rev, date, company
        self.placed = {}
        self.items = []          # board items (not footprints)
        self.segments = []       # (net, (x1,y1), (x2,y2), w, layer)
        self.locked = set()      # indices of hand-drawn segments (straighten.py leaves them alone)
        self.vias = []           # (net, (x,y), size, drill)
        self.zones = []
        self.texts = []

    # ---------------- footprints
    def place(self, ref, x, y, angle=0, side='F', libid=None):
        c = self.comps[ref]
        libid = libid or c.footprint
        fp = fplib.load(libid)
        node = self._fp_node(c, libid, fp, x, y, angle, side)
        pl = Placed(c, libid, x, y, angle, side, node, fplib.pads(fp))
        self.placed[ref] = pl
        return pl

    def _fp_node(self, c, libid, fp, x, y, angle, side):
        B = side == 'B'
        out = ['footprint', libid, ['layer', 'B.Cu' if B else 'F.Cu'], ['uuid', uid(self.name, 'fp', c.ref)]]
        out.append(['at', r4(x), r4(y), angle] if angle else ['at', r4(x), r4(y)])
        skip = {'version', 'generator', 'generator_version', 'layer', 'uuid', 'at'}
        def fl(lay):
            return FLIP_LAYER.get(lay, lay) if B else lay
        def fy(v):
            return (-v if B else v) if not isinstance(v, int) else (-v if B else v)
        def ex(v):
            # internal coordinates not rounded (same as the library) except for the sign on the B side
            return v
        k = 0
        for it in fp[2:]:
            if not isinstance(it, list) or not it: continue
            h = it[0]
            if h in skip: continue
            it = copy.deepcopy(it); k += 1
            if h in ('property', 'fp_text'):
                name = it[1]
                if h == 'property' and name == 'Reference': it[2] = c.ref
                if h == 'property' and name == 'Value': it[2] = c.value
                if h == 'property' and name == 'Footprint': it[2] = libid
                if h == 'property' and name in ('Datasheet', 'Description'):
                    it[2] = c.fields.get(name, it[2])
                at = kid(it, 'at')
                if at:
                    a0 = float(at[3]) if len(at) > 3 else 0.0
                    new = ['at', at[1], fy(at[2])]
                    ang = (angle + (-a0 if B else a0)) % 360
                    if ang: new.append(ang)
                    it[it.index(at)] = new
                lay = kid(it, 'layer')
                if lay: lay[1] = fl(str(lay[1]))
                if B:
                    eff = kid(it, 'effects')
                    if eff is not None:
                        j = kid(eff, 'justify')
                        if j is None: eff.append(['justify', Sym('mirror')])
                        elif 'mirror' not in [str(v) for v in j[1:]]: j.append(Sym('mirror'))
                if not kid(it, 'uuid'): it.append(['uuid', uid(self.name, c.ref, h, k)])
            elif h in ('fp_line', 'fp_rect', 'fp_circle', 'fp_arc', 'fp_poly', 'fp_curve'):
                for key in ('start', 'end', 'mid', 'center'):
                    e = kid(it, key)
                    if e: e[2] = fy(e[2])
                pts = kid(it, 'pts')
                if pts:
                    for xy in kids(pts, 'xy'): xy[2] = fy(xy[2])
                lay = kid(it, 'layer')
                if lay: lay[1] = fl(str(lay[1]))
                if not kid(it, 'uuid'): it.append(['uuid', uid(self.name, c.ref, h, k)])
            elif h == 'pad':
                num = str(it[1])
                at = kid(it, 'at')
                a0 = float(at[3]) if len(at) > 3 else 0.0
                new = ['at', at[1], fy(at[2])]
                ang = (angle + (-a0 if B else a0)) % 360
                if ang: new.append(ang)
                it[it.index(at)] = new
                lays = kid(it, 'layers')
                for i in range(1, len(lays)): lays[i] = fl(str(lays[i]))
                for sub in ('primitives',):
                    pr = kid(it, sub)
                    if pr and B:
                        for g in pr[1:]:
                            for key in ('start', 'end', 'mid', 'center'):
                                e = kid(g, key)
                                if e: e[2] = -e[2]
                            pts = kid(g, 'pts')
                            if pts:
                                for xy in kids(pts, 'xy'): xy[2] = -xy[2]
                # net
                for q in [q for q in it if isinstance(q, list) and q and q[0] in ('net', 'pinfunction', 'pintype', 'uuid')]:
                    it.remove(q)
                if num in c.pins:
                    net, pf, pt = c.pins[num]
                    it.append(['net', knet(net)])
                    if pf: it.append(['pinfunction', pf])
                    if pt: it.append(['pintype', pt])
                it.append(['uuid', uid(self.name, c.ref, 'pad', num, k)])
            elif h == 'zone':
                # footprint zones: absolute board coordinates
                for pol in kids(it, 'polygon'):
                    for xy in kids(kid(pol, 'pts'), 'xy'):
                        lx, ly = float(xy[1]), fy(float(xy[2]))
                        dx, dy = rot(lx, ly, angle)
                        xy[1] = r4(x + dx); xy[2] = r4(y + dy)
                lays = kid(it, 'layers') or kid(it, 'layer')
                if lays and B:
                    for i in range(1, len(lays)): lays[i] = fl(str(lays[i]))
                if not kid(it, 'uuid'): it.insert(2, ['uuid', uid(self.name, c.ref, 'zone', k)])
            out.append(it)
        # schematic fields missing from the footprint: hidden properties on Fab
        have = {str(it[1]) for it in out if isinstance(it, list) and it and it[0] == 'property'}
        for fname, fval in c.fields.items():
            if fname in ('Footprint', 'Reference', 'Value') or fname in have: continue
            out.append(['property', fname, fval, ['at', 0, 0, angle] if angle else ['at', 0, 0],
                        ['unlocked', Sym('yes')], ['layer', 'B.Fab' if B else 'F.Fab'], ['hide', Sym('yes')],
                        ['uuid', uid(self.name, c.ref, 'field', fname)],
                        ['effects', ['font', ['size', 1, 1], ['thickness', 0.15]]] + ([['justify', Sym('mirror')]] if B else [])])
        # schematic fields
        out.insert(5, ['path', c.path])
        out.insert(6, ['sheetname', c.sheetname])
        out.insert(7, ['sheetfile', c.sheetfile])
        attr = kid(out, 'attr')
        flags = []
        if not c.in_bom: flags.append('exclude_from_bom')
        if c.dnp: flags.append('dnp')
        if flags:
            if attr is None:
                out.insert(8, ['attr'] + [Sym(f) for f in flags])
            else:
                for f in flags:
                    if f not in [str(v) for v in attr[1:]]: attr.append(Sym(f))
        return out

    # ---------------- copper
    def track(self, net, pts, w, layer='F.Cu', locked=False):
        for a, b in zip(pts, pts[1:]):
            if abs(a[0] - b[0]) < 1e-6 and abs(a[1] - b[1]) < 1e-6: continue
            if locked: self.locked.add(len(self.segments))
            self.segments.append((net, (r4(a[0]), r4(a[1])), (r4(b[0]), r4(b[1])), w, layer))

    def via(self, net, p, size=0.6, drill=0.3):
        self.vias.append((net, (r4(p[0]), r4(p[1])), size, drill))

    def zone(self, net, layer, poly, priority=0, clearance=0.25, min_w=0.2, thermal_gap=0.3, spoke=0.4, connect='thermal',
             name=None, island='always'):
        self.zones.append(dict(net=net, layer=layer, poly=poly, priority=priority, clearance=clearance, min_w=min_w,
                               thermal_gap=thermal_gap, spoke=spoke, connect=connect, name=name, island=island))

    def keepout(self, layers, poly, tracks=False, vias=False, pads=True, pour=False, fps=True, name=None):
        self.zones.append(dict(keepout=True, layers=layers, poly=poly, tracks=tracks, vias=vias, pads=pads, pour=pour, fps=fps, name=name))

    # ---------------- graphics
    def gr(self, node):
        self.items.append(node)

    def edge_line(self, a, b):
        self.gr(['gr_line', ['start', r4(a[0]), r4(a[1])], ['end', r4(b[0]), r4(b[1])], ['stroke', ['width', 0.1], ['type', Sym('solid')]],
                 ['layer', 'Edge.Cuts'], ['uuid', uid(self.name, 'edge', a, b)]])

    def edge_arc(self, a, m, b):
        self.gr(['gr_arc', ['start', r4(a[0]), r4(a[1])], ['mid', r4(m[0]), r4(m[1])], ['end', r4(b[0]), r4(b[1])],
                 ['stroke', ['width', 0.1], ['type', Sym('solid')]], ['layer', 'Edge.Cuts'], ['uuid', uid(self.name, 'arc', a, m, b)]])

    def edge_circle(self, c, r):
        self.gr(['gr_circle', ['center', r4(c[0]), r4(c[1])], ['end', r4(c[0] + r), r4(c[1])], ['stroke', ['width', 0.1], ['type', Sym('solid')]],
                 ['fill', Sym('no')], ['layer', 'Edge.Cuts'], ['uuid', uid(self.name, 'circ', c, r)]])

    def line(self, a, b, layer, w=0.15):
        self.gr(['gr_line', ['start', r4(a[0]), r4(a[1])], ['end', r4(b[0]), r4(b[1])], ['stroke', ['width', w], ['type', Sym('solid')]],
                 ['layer', layer], ['uuid', uid(self.name, 'line', layer, a, b)]])

    def rect(self, a, b, layer, w=0.15, fill=False):
        self.gr(['gr_rect', ['start', r4(a[0]), r4(a[1])], ['end', r4(b[0]), r4(b[1])], ['stroke', ['width', w], ['type', Sym('solid')]],
                 ['fill', Sym('yes' if fill else 'no')], ['layer', layer], ['uuid', uid(self.name, 'rect', layer, a, b)]])

    def circle(self, c, r, layer, w=0.15):
        self.gr(['gr_circle', ['center', r4(c[0]), r4(c[1])], ['end', r4(c[0] + r), r4(c[1])], ['stroke', ['width', w], ['type', Sym('solid')]],
                 ['fill', Sym('no')], ['layer', layer], ['uuid', uid(self.name, 'circle', layer, c, r)]])

    def text(self, s, p, layer='F.SilkS', size=1.0, thick=0.15, angle=0, justify=None, bold=False):
        eff = ['effects', ['font', ['size', size, size], ['thickness', thick]] + ([['bold', Sym('yes')]] if bold else [])]
        j = []
        if justify: j += justify.split()
        if layer.startswith('B.'): j.append('mirror')
        if j: eff.append(['justify'] + [Sym(v) for v in j])
        at = ['at', r4(p[0]), r4(p[1])] + ([angle] if angle else [])
        self.gr(['gr_text', s, at, ['layer', layer], ['uuid', uid(self.name, 'text', s, p, layer)], eff])

    # ---------------- output
    def _layers(self):
        L = [[0, 'F.Cu', Sym('signal')]]
        if self.layers == 4:
            L += [[4, 'In1.Cu', Sym('signal')], [6, 'In2.Cu', Sym('signal')]]
        L += [[2, 'B.Cu', Sym('signal')], [9, 'F.Adhes', Sym('user'), 'F.Adhesive'], [11, 'B.Adhes', Sym('user'), 'B.Adhesive'],
              [13, 'F.Paste', Sym('user')], [15, 'B.Paste', Sym('user')], [5, 'F.SilkS', Sym('user'), 'F.Silkscreen'],
              [7, 'B.SilkS', Sym('user'), 'B.Silkscreen'], [1, 'F.Mask', Sym('user')], [3, 'B.Mask', Sym('user')],
              [17, 'Dwgs.User', Sym('user'), 'User.Drawings'], [19, 'Cmts.User', Sym('user'), 'User.Comments'],
              [21, 'Eco1.User', Sym('user'), 'User.Eco1'], [23, 'Eco2.User', Sym('user'), 'User.Eco2'], [25, 'Edge.Cuts', Sym('user')],
              [27, 'Margin', Sym('user')], [31, 'F.CrtYd', Sym('user'), 'F.Courtyard'], [29, 'B.CrtYd', Sym('user'), 'B.Courtyard'],
              [35, 'F.Fab', Sym('user')], [33, 'B.Fab', Sym('user')]]
        return ['layers'] + L

    def _stackup(self):
        st = ['stackup',
              ['layer', 'F.SilkS', ['type', 'Top Silk Screen'], ['color', 'White']],
              ['layer', 'F.Paste', ['type', 'Top Solder Paste']],
              ['layer', 'F.Mask', ['type', 'Top Solder Mask'], ['color', 'Green'], ['thickness', 0.01]],
              ['layer', 'F.Cu', ['type', 'copper'], ['thickness', 0.035]]]
        if self.layers == 4:   # JLC04161H-7628
            st += [['layer', 'dielectric 1', ['type', 'prepreg'], ['thickness', 0.2104], ['material', '7628'], ['epsilon_r', 4.4], ['loss_tangent', 0.02]],
                   ['layer', 'In1.Cu', ['type', 'copper'], ['thickness', 0.0152]],
                   ['layer', 'dielectric 2', ['type', 'core'], ['thickness', 1.065], ['material', 'FR4'], ['epsilon_r', 4.6], ['loss_tangent', 0.02]],
                   ['layer', 'In2.Cu', ['type', 'copper'], ['thickness', 0.0152]],
                   ['layer', 'dielectric 3', ['type', 'prepreg'], ['thickness', 0.2104], ['material', '7628'], ['epsilon_r', 4.4], ['loss_tangent', 0.02]]]
        else:
            st += [['layer', 'dielectric 1', ['type', 'core'], ['thickness', 1.51], ['material', 'FR4'], ['epsilon_r', 4.5], ['loss_tangent', 0.02]]]
        st += [['layer', 'B.Cu', ['type', 'copper'], ['thickness', 0.035]],
               ['layer', 'B.Mask', ['type', 'Bottom Solder Mask'], ['color', 'Green'], ['thickness', 0.01]],
               ['layer', 'B.Paste', ['type', 'Bottom Solder Paste']],
               ['layer', 'B.SilkS', ['type', 'Bottom Silk Screen'], ['color', 'White']],
               ['copper_finish', getattr(self, 'finish', 'HAL lead-free')], ['dielectric_constraints', Sym('no')]]
        return st

    def node(self):
        root = ['kicad_pcb', ['version', 20260206], ['generator', 'pcbnew'], ['generator_version', '10.0'],
                ['general', ['thickness', self.thickness], ['legacy_teardrops', Sym('no')]], ['paper', 'A4'],
                ['title_block', ['title', self.title], ['date', self.date], ['rev', self.rev], ['company', self.company]],
                self._layers(),
                ['setup', self._stackup(), ['pad_to_mask_clearance', 0], ['allow_soldermask_bridges_in_footprints', Sym('no')],
                 ['tenting', ['front', Sym('yes')], ['back', Sym('yes')]],
                 ['aux_axis_origin', self.aux[0], self.aux[1]], ['grid_origin', 150, 100]]]
        for ref in sorted(self.placed, key=lambda r: (re.sub(r'\d', '', r), int(re.sub(r'\D', '', r) or 0))):
            root.append(self.placed[ref].node)
        root += self.items
        for i, (net, a, b, w, layer) in enumerate(self.segments):
            node = ['segment', ['start', a[0], a[1]], ['end', b[0], b[1]], ['width', w]]
            if i in self.locked: node.append(['locked', Sym('yes')])
            root.append(node + [['layer', layer], ['net', knet(net)], ['uuid', uid(self.name, 'seg', i, a, b, layer)]])
        for i, (net, p, size, drill) in enumerate(self.vias):
            root.append(['via', ['at', p[0], p[1]], ['size', size], ['drill', drill], ['layers', 'F.Cu', 'B.Cu'], ['net', knet(net)],
                         ['uuid', uid(self.name, 'via', i, p)]])
        for i, z in enumerate(self.zones):
            root.append(self._zone_node(i, z))
        root.append(['embedded_fonts', Sym('no')])
        return root

    def _zone_node(self, i, z):
        pts = ['pts'] + [['xy', r4(x), r4(y)] for x, y in z['poly']]
        if z.get('keepout'):
            n = ['zone', ['net', ''] if False else None]
            node = ['zone', ['layers'] + list(z['layers']), ['uuid', uid(self.name, 'keepout', i)]]
            if z.get('name'): node.append(['name', z['name']])
            node += [['hatch', Sym('edge'), 0.5], ['connect_pads', ['clearance', 0]], ['min_thickness', 0.25],
                     ['filled_areas_thickness', Sym('no')],
                     ['keepout', ['tracks', Sym('allowed' if z['tracks'] else 'not_allowed')], ['vias', Sym('allowed' if z['vias'] else 'not_allowed')],
                      ['pads', Sym('allowed' if z['pads'] else 'not_allowed')], ['copperpour', Sym('allowed' if z['pour'] else 'not_allowed')],
                      ['footprints', Sym('allowed' if z['fps'] else 'not_allowed')]],
                     ['placement', ['enabled', Sym('no')], ['sheetname', '']],
                     ['fill', ['thermal_gap', 0.5], ['thermal_bridge_width', 0.5]], ['polygon', pts]]
            return node
        node = ['zone', ['net', knet(z['net'])], ['layer', z['layer']], ['uuid', uid(self.name, 'zone', i, z['net'], z['layer'])]]
        if z.get('name'): node.append(['name', z['name']])
        cp = ['connect_pads'] + ([Sym('yes')] if z['connect'] == 'solid' else ([Sym('thru_hole_only')] if z['connect'] == 'tht' else [])) + [['clearance', z['clearance']]]
        node += [['hatch', Sym('edge'), 0.5], ['priority', z['priority']] if z['priority'] else None, cp, ['min_thickness', z['min_w']],
                 ['filled_areas_thickness', Sym('no')],
                 ['fill', Sym('yes'), ['thermal_gap', z['thermal_gap']], ['thermal_bridge_width', z['spoke']],
                  ['island_removal_mode', 0 if z['island'] == 'always' else 1]],
                 ['polygon', pts]]
        return [n for n in node if n is not None]

    def write(self, path):
        open(path, 'w', encoding='utf-8').write(fmt(self.node()) + '\n')
