"""Generate KLC-style rectangular symbols in KiCad v7 library syntax (upgraded later with kicad-cli 10)."""
G = 2.54

def fmt(v):
    s = f"{v:.4f}".rstrip('0').rstrip('.')
    return '0' if s in ('-0', '') else s

def esc(s):
    return s.replace('\\', '\\\\').replace('"', '\\"')

def prop(name, val, x, y, rot=0, hide=False, justify=None):
    j = f" (justify {justify})" if justify else ""
    h = " hide" if hide else ""
    return f'    (property "{esc(name)}" "{esc(val)}" (at {fmt(x)} {fmt(y)} {rot}) (effects (font (size 1.27 1.27)){j}{h}))\n'

def pin(ptype, x, y, ang, num, name, length=G, hide=False, style='line'):
    h = " hide" if hide else ""
    return (f'      (pin {ptype} {style} (at {fmt(x)} {fmt(y)} {ang}) (length {fmt(length)}){h}\n'
            f'        (name "{esc(name)}" (effects (font (size 1.27 1.27))))\n'
            f'        (number "{esc(num)}" (effects (font (size 1.27 1.27))))\n      )\n')

def box_symbol(name, ref='U', value=None, footprint='', datasheet='', description='', keywords='', fp_filters='',
               left=(), right=(), top=(), bottom=(), width=None, stacked=(), pin_len=G, extra_graphics=''):
    """left/right/top/bottom: lists of (num, name, type) or None for an empty slot (spacing 2.54).
    stacked: list of (num, name, type, same_as_num) hidden pins placed on another pin's location."""
    value = value or name
    nl, nr = len(left), len(right)
    rows = max(nl, nr, 1)
    h = (rows + 1) * G
    nt, nb = len(top), len(bottom)
    if width is None:
        longest_l = max([len(p[1]) for p in left if p] + [0])
        longest_r = max([len(p[1]) for p in right if p] + [0])
        width = max((longest_l + longest_r) * 1.0 + 6 * G / 2, (max(nt, nb) + 1) * G, 5 * G)
        width = round(width / (2 * G) + 0.4999) * 2 * G
    hw = width / 2
    # vertical extents: top of body at +h/2 rounded to grid
    top_y = round((h / 2) / G) * G
    bot_y = top_y - h
    bot_y = round(bot_y / G) * G
    out = []
    pos = {}
    body = f'      (rectangle (start {fmt(-hw)} {fmt(top_y)}) (end {fmt(hw)} {fmt(bot_y)}) (stroke (width 0.254) (type default)) (fill (type background)))\n'
    pins = ''
    y = top_y - G
    for p in left:
        if p:
            num, nm, tp = p[:3]
            hide = len(p) > 3 and p[3]
            pins += pin(tp, -hw - pin_len, y, 0, num, nm, pin_len, hide)
            pos[num] = (-hw - pin_len, y, 0)
        y -= G
    y = top_y - G
    for p in right:
        if p:
            num, nm, tp = p[:3]
            hide = len(p) > 3 and p[3]
            pins += pin(tp, hw + pin_len, y, 180, num, nm, pin_len, hide)
            pos[num] = (hw + pin_len, y, 180)
        y -= G
    def spread(n):
        xs = []
        start = -((n - 1) * G) / 2
        start = round(start / G) * G
        return [start + i * G for i in range(n)]
    for p, x in zip(top, spread(nt)):
        if p:
            num, nm, tp = p[:3]
            pins += pin(tp, x, top_y + pin_len, 270, num, nm, pin_len)
            pos[num] = (x, top_y + pin_len, 270)
    for p, x in zip(bottom, spread(nb)):
        if p:
            num, nm, tp = p[:3]
            pins += pin(tp, x, bot_y - pin_len, 90, num, nm, pin_len)
            pos[num] = (x, bot_y - pin_len, 90)
    for num, nm, tp, same in stacked:
        x, yy, ang = pos[same]
        pins += pin(tp, x, yy, ang, num, nm, pin_len, hide=True)
    s = f'  (symbol "{esc(name)}" (in_bom yes) (on_board yes)\n'
    s += prop('Reference', ref, -hw, top_y + 1.27, justify='left bottom')
    s += prop('Value', value, hw, top_y + 1.27, justify='right bottom')
    s += prop('Footprint', footprint, 0, bot_y - 5.08, hide=True)
    s += prop('Datasheet', datasheet, 0, bot_y - 7.62, hide=True)
    s += prop('ki_keywords', keywords, 0, 0, hide=True)
    s += prop('ki_description', description, 0, 0, hide=True)
    if fp_filters:
        s += prop('ki_fp_filters', fp_filters, 0, 0, hide=True)
    s += f'    (symbol "{esc(name)}_0_1"\n{body}{extra_graphics}    )\n'
    s += f'    (symbol "{esc(name)}_1_1"\n{pins}    )\n'
    s += '  )\n'
    return s

def lib(symbols):
    return '(kicad_symbol_lib (version 20220914) (generator kicad_symbol_editor)\n' + ''.join(symbols) + ')\n'
