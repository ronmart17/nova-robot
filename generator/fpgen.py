"""Custom footprints for NOVA Rev B (KiCad 10 format), for parts with no KiCad library footprint.
Every land pattern below is taken from the manufacturer drawing named in its descr."""
import uuid

def _u(*k):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, 'nova-fp/' + '/'.join(str(x) for x in k)))

def _f(v):
    s = f'{v:.4f}'.rstrip('0').rstrip('.')
    return '0' if s in ('-0', '') else s

class FP:
    def __init__(self, name, descr, tags, attr='smd'):
        self.name, self.descr, self.tags, self.attr = name, descr, tags, attr
        self.items = []
        self.model = None

    def text(self, kind, txt, x, y, layer, size=1.0, hide=False):
        h = '\n\t\t(hide yes)' if hide else ''
        th = round(size * 0.15, 3)
        self.items.append(f'\t(property "{kind}" "{txt}"\n\t\t(at {_f(x)} {_f(y)} 0)\n\t\t(unlocked yes)\n\t\t(layer "{layer}"){h}\n'
                          f'\t\t(uuid "{_u(self.name, kind)}")\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size {size} {size})\n'
                          f'\t\t\t\t(thickness {th})\n\t\t\t)\n\t\t)\n\t)')

    def line(self, x1, y1, x2, y2, layer, w):
        self.items.append(f'\t(fp_line\n\t\t(start {_f(x1)} {_f(y1)})\n\t\t(end {_f(x2)} {_f(y2)})\n\t\t(stroke\n\t\t\t(width {w})\n'
                          f'\t\t\t(type solid)\n\t\t)\n\t\t(layer "{layer}")\n\t\t(uuid "{_u(self.name, "l", x1, y1, x2, y2, layer)}")\n\t)')

    def rect(self, x1, y1, x2, y2, layer, w):
        self.items.append(f'\t(fp_rect\n\t\t(start {_f(x1)} {_f(y1)})\n\t\t(end {_f(x2)} {_f(y2)})\n\t\t(stroke\n\t\t\t(width {w})\n'
                          f'\t\t\t(type solid)\n\t\t)\n\t\t(fill no)\n\t\t(layer "{layer}")\n\t\t(uuid "{_u(self.name, "r", x1, y1, layer)}")\n\t)')

    def circle(self, x, y, r, layer, w, fill=False):
        self.items.append(f'\t(fp_circle\n\t\t(center {_f(x)} {_f(y)})\n\t\t(end {_f(x + r)} {_f(y)})\n\t\t(stroke\n\t\t\t(width {w})\n'
                          f'\t\t\t(type solid)\n\t\t)\n\t\t(fill {"yes" if fill else "no"})\n\t\t(layer "{layer}")\n'
                          f'\t\t(uuid "{_u(self.name, "c", x, y, r, layer)}")\n\t)')

    def poly(self, pts, layer, w=0.12, fill=True):
        xy = ' '.join(f'(xy {_f(x)} {_f(y)})' for x, y in pts)
        self.items.append(f'\t(fp_poly\n\t\t(pts {xy})\n\t\t(stroke\n\t\t\t(width {w})\n\t\t\t(type solid)\n\t\t)\n'
                          f'\t\t(fill {"yes" if fill else "no"})\n\t\t(layer "{layer}")\n\t\t(uuid "{_u(self.name, "p", pts[0], layer)}")\n\t)')

    def fab_ref(self, x=0, y=0, size=0.4):
        th = round(size * 0.15, 3)
        self.items.append(f'\t(fp_text user "${{REFERENCE}}"\n\t\t(at {_f(x)} {_f(y)} 0)\n\t\t(unlocked yes)\n\t\t(layer "F.Fab")\n'
                          f'\t\t(uuid "{_u(self.name, "fabref")}")\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size {size} {size})\n'
                          f'\t\t\t\t(thickness {th})\n\t\t\t)\n\t\t)\n\t)')

    def pad(self, num, x, y, w, h, shape='roundrect', rratio=0.25, layers=('F.Cu', 'F.Paste', 'F.Mask'), kind='smd',
            drill=None, extra=''):
        lay = ' '.join(f'"{l}"' for l in layers)
        rr = f'\n\t\t(roundrect_rratio {_f(rratio)})' if shape == 'roundrect' else ''
        dr = (f'\n\t\t(drill {drill})' if isinstance(drill, str) else f'\n\t\t(drill {_f(drill)})') if drill else ''
        self.items.append(f'\t(pad "{num}" {kind} {shape}\n\t\t(at {_f(x)} {_f(y)})\n\t\t(size {_f(w)} {_f(h)}){dr}\n'
                          f'\t\t(layers {lay}){rr}{extra}\n\t\t(uuid "{_u(self.name, "pad", num, x, y)}")\n\t)')

    def write(self, path):
        attr = f'\t(attr {self.attr})' if self.attr else '\t(attr exclude_from_pos_files exclude_from_bom)'
        head = (f'(footprint "{self.name}"\n\t(version 20260206)\n\t(generator "pcbnew")\n\t(generator_version "10.0")\n'
                f'\t(layer "F.Cu")\n\t(descr "{self.descr}")\n\t(tags "{self.tags}")')
        body = '\n'.join(self.items)
        model = ''
        if self.model:
            model = (f'\n\t(model "${{KIPRJMOD}}/../lib/robot.3dshapes/{self.model}.step"\n\t\t(offset\n\t\t\t(xyz 0 0 0)\n\t\t)\n'
                     f'\t\t(scale\n\t\t\t(xyz 1 1 1)\n\t\t)\n\t\t(rotate\n\t\t\t(xyz 0 0 0)\n\t\t)\n\t)')
        open(path, 'w', encoding='utf-8').write(f'{head}\n{body}\n{attr}\n\t(duplicate_pad_numbers_are_jumpers no){model}\n'
                                                f'\t(embedded_fonts no)\n)\n')

def rqf0009a():
    """TI RQF0009A (VQFN-HR, 9 pins, 1.5 x 2.0 mm, 0.5 mm pitch) — TPS566238. Land pattern measured on the vector
    drawing of TI 4225248/A (example board layout, NSMD, 0.05 mm solder mask expansion)."""
    f = FP('Texas_RQF0009A_VQFN-HR-9_1.5x2mm_P0.5mm',
           'TI RQF0009A VQFN-HR-9 1.5x2.0 mm, 0.5 mm pitch (TPS566238), land pattern per TI drawing 4225248/A, NSMD',
           'VQFN-HR RQF0009A TPS566238 HotRod')
    f.text('Reference', 'REF**', 0, -1.9, 'F.SilkS', 0.8)
    f.text('Value', f.name, 0, 1.9, 'F.Fab', 0.5)
    f.text('Datasheet', 'https://www.ti.com/lit/ds/symlink/tps566238.pdf', 0, 0, 'F.Fab', 1.27, hide=True)
    f.text('Description', 'VQFN-HR-9 1.5x2 mm', 0, 0, 'F.Fab', 1.27, hide=True)
    for num, x, y, w, h in (('1', -0.925, -0.5, 0.55, 0.25), ('2', -0.925, 0.0, 0.55, 0.25), ('3', -0.925, 0.5, 0.55, 0.25),
                            ('7', 0.925, -0.5, 0.55, 0.25), ('6', 0.925, 0.0, 0.55, 0.25), ('5', 0.925, 0.5, 0.55, 0.25),
                            ('9', -0.25, -0.675, 0.25, 0.55), ('8', 0.25, -0.30, 0.25, 1.30), ('4', -0.25, 0.45, 0.25, 1.0)):
        f.pad(num, x, y, w, h, rratio=0.2, extra='\n\t\t(solder_mask_margin 0.05)')
    # fab body with chamfered pin-1 corner
    f.poly([(-0.75, -0.75), (-0.5, -1.0), (0.75, -1.0), (0.75, 1.0), (-0.75, 1.0)], 'F.Fab', 0.1, fill=False)
    f.fab_ref(0, 0, 0.3)
    # silkscreen: corner marks clear of the pads, pin-1 dot
    for sx in (-1, 1):
        f.line(sx * 0.35, -1.11, sx * 0.85, -1.11, 'F.SilkS', 0.12)
        f.line(sx * 0.35, 1.11, sx * 0.85, 1.11, 'F.SilkS', 0.12)
    f.circle(-1.25, -1.05, 0.08, 'F.SilkS', 0.12, fill=True)
    f.rect(-1.45, -1.25, 1.45, 1.25, 'F.CrtYd', 0.05)
    f.model = 'Texas_RQF0009A_VQFN-HR-9_1.5x2mm_P0.5mm'
    return f

def pogo():
    """YIYUAN YTC1P-8020-01 SMD pogo pin (datasheet table, type 8020): base flange D2.00, barrel D1.5 × 8.5 mm,
    plunger D0.9, 10 mm free / 9.0 mm working height, 1.0 mm stroke, 100 ± 20 g, 1.5 A max at 12 V."""
    f = FP('Pogo_YTC1P-8020_D2.0mm', 'SMD pogo pin YIYUAN YTC1P-8020-01, base D2.0 mm, 10 mm free / 9 mm working, 1.5 A max (LCSC C5221286)',
           'pogo spring probe contact')
    f.text('Reference', 'REF**', 0, -2.4, 'F.SilkS', 0.8)
    f.text('Value', f.name, 0, 2.4, 'F.Fab', 0.6)
    f.text('Datasheet', 'https://www.lcsc.com/datasheet/C5221286.pdf', 0, 0, 'F.Fab', 1.27, hide=True)
    f.text('Description', 'Pogo pin D2.0 mm SMD', 0, 0, 'F.Fab', 1.27, hide=True)
    f.pad('1', 0, 0, 2.6, 2.6, shape='circle')
    f.circle(0, 0, 1.0, 'F.Fab', 0.1)
    f.circle(0, 0, 1.6, 'F.SilkS', 0.12)
    f.circle(0, 0, 1.85, 'F.CrtYd', 0.05)
    f.fab_ref(0, 0, 0.4)
    f.model = 'Pogo_YTC1P-8020_D2.0mm'
    return f

def contact_pad():
    """Flat 8 x 12 mm contact target for the dock pogo pins (ENIG, no paste)."""
    f = FP('ContactPad_8x12mm', 'Flat contact pad 8x12 mm for pogo pins, solder mask opening, no paste', 'contact pad pogo target',
           attr=None)
    f.text('Reference', 'REF**', 0, -7.0, 'F.SilkS', 0.8)
    f.text('Value', f.name, 0, 7.0, 'F.Fab', 0.8)
    f.text('Datasheet', '', 0, 0, 'F.Fab', 1.27, hide=True)
    f.text('Description', 'Contact pad 8x12 mm', 0, 0, 'F.Fab', 1.27, hide=True)
    f.pad('1', 0, 0, 8, 12, rratio=0.1, layers=('F.Cu', 'F.Mask'))
    f.rect(-4.3, -6.3, 4.3, 6.3, 'F.CrtYd', 0.05)
    f.fab_ref(0, 0, 1.0)
    return f

def dc_jack_xkb():
    """XKB DC-005-5A-2.0 (LCSC C381116), 5.5 × 2.0 mm right-angle jack, 5 A / 24 V. Land pattern from the XKB drawing
    'PCB LAYOUT TOP VIEW': three 1.0 × 3.5 mm slots; centre pin (1) 13.60 mm behind the front face, sleeve (2) 5.90 mm in
    front of it, switch (3) 3.00 mm in front and 4.70 mm to the side (slot along the jack axis). Body 14.0 × 9.0 × 11 mm."""
    f = FP('DC_Jack_XKB_DC-005-5A-2.0_Horizontal',
           'DC barrel jack 5.5x2.0 mm right angle, XKB DC-005-5A-2.0 (LCSC C381116), 5 A 24 V, slots 1.0x3.5 mm per XKB drawing',
           'DC jack barrel 5.5 2.0 power', attr='through_hole')
    f.text('Reference', 'REF**', -6.6, -5.6, 'F.SilkS', 1.0)
    f.text('Value', f.name, -6.6, 7.0, 'F.Fab', 0.8)
    f.text('Datasheet', 'https://www.lcsc.com/datasheet/C381116.pdf', 0, 0, 'F.Fab', 1.27, hide=True)
    f.text('Description', 'DC jack 5.5x2.0 mm, 5 A', 0, 0, 'F.Fab', 1.27, hide=True)
    tht = ('*.Cu', '*.Mask')
    f.pad('1', 0, 0, 2.0, 4.2, shape='rect', layers=tht, kind='thru_hole', drill='oval 1 3.5')
    f.pad('2', -5.9, 0, 2.0, 4.2, layers=tht, kind='thru_hole', drill='oval 1 3.5')
    f.pad('3', -3.0, 4.7, 4.2, 2.0, layers=tht, kind='thru_hole', drill='oval 3.5 1')
    # body: front face at x = −13.6, rear at +0.4, 9.0 wide
    f.rect(-13.6, -4.5, 0.4, 4.5, 'F.Fab', 0.1)
    f.line(-13.6, -2.0, -12.6, -3.1, 'F.Fab', 0.1)
    for x1, y1, x2, y2 in ((-13.71, -4.61, 0.51, -4.61), (-13.71, -4.61, -13.71, 4.61), (-13.71, 4.61, -5.4, 4.61),
                           (0.51, -4.61, 0.51, -2.4), (0.51, 2.4, 0.51, 4.61), (-0.6, 4.61, 0.51, 4.61)):
        f.line(x1, y1, x2, y2, 'F.SilkS', 0.12)
    f.rect(-13.95, -4.85, 1.25, 5.95, 'F.CrtYd', 0.05)
    f.fab_ref(-6.6, 0, 1.0)
    f.model = 'DC_Jack_XKB_DC-005-5A-2.0_Horizontal'
    return f

def mousebite_tab():
    """Break-away tab 5 mm wide × 3 mm long between two boards of the same panel: two rows of six D0.5 NPTH holes at 0.8 mm
    pitch, centred on the two board edges (x = ±1.5), so each board breaks off with a recessed, clean edge."""
    f = FP('MouseBite_Tab_5x3mm', 'Mouse-bite break-away tab 5 x 3 mm, 2 x 6 NPTH D0.5 mm at 0.8 mm pitch', 'mouse bite tab panel',
           attr=None)
    f.text('Reference', 'REF**', 0, -3.2, 'F.Fab', 0.5, hide=True)
    f.text('Value', f.name, 0, 3.2, 'F.Fab', 0.5, hide=True)
    f.text('Datasheet', '', 0, 0, 'F.Fab', 1.27, hide=True)
    f.text('Description', 'Mouse-bite tab', 0, 0, 'F.Fab', 1.27, hide=True)
    k = 0
    for x in (-1.5, 1.5):
        for i in range(6):
            k += 1
            f.pad('', x, -2.0 + 0.8 * i, 0.5, 0.5, shape='circle', layers=('*.Cu', '*.Mask'), kind='np_thru_hole', drill=0.5)
    f.rect(-1.75, -2.5, 1.75, 2.5, 'F.Fab', 0.05)
    return f

def build(outdir):
    for f in (rqf0009a(), pogo(), contact_pad(), dc_jack_xkb(), mousebite_tab()):
        f.write(f'{outdir}/{f.name}.kicad_mod')
        yield f.name

if __name__ == '__main__':
    import sys
    print(list(build(sys.argv[1] if len(sys.argv) > 1 else '/tmp')))
