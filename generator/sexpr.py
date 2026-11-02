"""Tiny S-expression model + KiCad-style formatter."""
class Sym(str):
    """Unquoted atom."""
    pass

def q(s):
    return '"' + str(s).replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n') + '"'

PREC = 4   # decimals (the PCB generator uses 6 = KiCad's 1 nm resolution)

def num(v):
    if isinstance(v, bool):
        return 'yes' if v else 'no'
    if isinstance(v, int):
        return str(v)
    s = f"{v:.{PREC}f}".rstrip('0').rstrip('.')
    if s in ('-0', ''):
        s = '0'
    return s

def atom(a):
    if isinstance(a, Sym):
        return str(a)
    if isinstance(a, bool):
        return 'yes' if a else 'no'
    if isinstance(a, (int, float)):
        return num(a)
    return q(a)

INLINE_HEADS = {'at', 'xy', 'size', 'start', 'end', 'mid', 'center', 'color', 'width', 'type', 'offset', 'length',
                'diameter', 'uuid', 'lib_id', 'unit', 'body_style', 'exclude_from_sim', 'in_bom', 'on_board', 'in_pos_files',
                'dnp', 'fields_autoplaced', 'hide', 'show_name', 'do_not_autoplace', 'justify', 'reference', 'page',
                'paper', 'version', 'generator', 'generator_version', 'mirror', 'shape', 'thickness', 'bold', 'italic',
                'margins', 'embedded_fonts', 'power', 'duplicate_pin_numbers_are_jumpers', 'radius', 'title', 'date', 'rev',
                'company', 'comment', 'convert'}

def head_atom(h):
    # The head of a KiCad S-expr list is always an unquoted keyword
    return str(h) if isinstance(h, str) else atom(h)

def fmt(node, indent=0):
    t = '\t' * indent
    if not isinstance(node, list):
        return t + atom(node)
    head = node[0]
    has_list = any(isinstance(c, list) for c in node[1:])
    if not has_list:
        return t + '(' + ' '.join([head_atom(head)] + [atom(c) for c in node[1:]]) + ')'
    if head == 'pts':
        return t + '(pts\n' + t + '\t' + ' '.join(fmt(c, 0) for c in node[1:]) + '\n' + t + ')'
    # first line: head + leading atoms
    i = 1
    first = [head_atom(head)]
    while i < len(node) and not isinstance(node[i], list):
        first.append(atom(node[i])); i += 1
    lines = [t + '(' + ' '.join(first)]
    for c in node[i:]:
        lines.append(fmt(c, indent + 1))
    lines.append(t + ')')
    return '\n'.join(lines)
