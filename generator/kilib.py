"""Load KiCad (v10-format) .kicad_sym libraries; flatten derived symbols; expose pins/fields; emit lib_symbols."""
import os, copy
from sexpr import Sym, fmt

def tokenize(s):
    i, n = 0, len(s); out = []
    while i < n:
        c = s[i]
        if c in ' \t\r\n': i += 1; continue
        if c in '()': out.append(c); i += 1; continue
        if c == '"':
            j = i + 1; buf = []
            while s[j] != '"':
                if s[j] == '\\':
                    nx = s[j+1]; buf.append({'n': '\n'}.get(nx, nx)); j += 2; continue
                buf.append(s[j]); j += 1
            out.append(('S', ''.join(buf))); i = j + 1; continue
        j = i
        while j < n and s[j] not in ' \t\r\n()': j += 1
        out.append(Sym(s[i:j])); i = j
    return out

def parse(s):
    toks = tokenize(s); pos = 0
    def rd():
        nonlocal pos
        t = toks[pos]; pos += 1
        if t == '(':
            lst = []
            while toks[pos] != ')': lst.append(rd())
            pos += 1; return lst
        if isinstance(t, tuple): return t[1]
        return t
    return rd()

def children(node, key):
    return [c for c in node if isinstance(c, list) and c and c[0] == key]

def child(node, key):
    c = children(node, key)
    return c[0] if c else None

class SymDef:
    pass

class Library:
    def __init__(self, libs):
        """libs: dict nickname -> path of .kicad_sym (v10 format)"""
        self.libs = libs
        self._cache = {}
        self._trees = {}
    def _tree(self, nick):
        if nick not in self._trees:
            t = parse(open(self.libs[nick], encoding='utf-8').read())
            self._trees[nick] = {c[1]: c for c in children(t, 'symbol')}
        return self._trees[nick]
    def _flat(self, nick, name):
        syms = self._tree(nick)
        node = copy.deepcopy(syms[name])
        ext = child(node, 'extends')
        if ext is None:
            return node
        parent = self._flat(nick, ext[1])
        flat = copy.deepcopy(parent)
        flat[1] = name
        # rename unit sub-symbols
        for sub in children(flat, 'symbol'):
            sub[1] = name + sub[1][len(ext[1]):]
        # merge properties: child's override
        cprops = {p[1]: p for p in children(node, 'property')}
        newflat = []
        seen = set()
        for c in flat:
            if isinstance(c, list) and c and c[0] == 'property':
                if c[1] in cprops:
                    newflat.append(cprops[c[1]]); seen.add(c[1])
                else:
                    newflat.append(c)
            else:
                newflat.append(c)
        # insert child-only properties before first sub-symbol
        extra = [p for k, p in cprops.items() if k not in seen]
        idx = next(i for i, c in enumerate(newflat) if isinstance(c, list) and c and c[0] == 'symbol')
        newflat[idx:idx] = extra
        # other attributes from child (in_bom etc) keep parent's
        return newflat
    def get(self, lib_id):
        if lib_id in self._cache: return self._cache[lib_id]
        nick, name = lib_id.split(':', 1)
        node = self._flat(nick, name)
        sd = SymDef(); sd.lib_id = lib_id; sd.node = node
        sd.is_power = child(node, 'power') is not None or any(isinstance(a, Sym) and a == 'power' for a in node)
        sd.fields = {}
        for p in children(node, 'property'):
            at = child(p, 'at'); e = child(p, 'effects')
            j = child(e, 'justify') if e else None
            hide = child(p, 'hide') is not None or (e is not None and child(e, 'hide') is not None)
            sd.fields[p[1]] = dict(value=p[2], x=float(at[1]), y=float(at[2]), ang=float(at[3]) if len(at) > 3 else 0,
                                   justify=' '.join(str(x) for x in j[1:]) if j else None, hide=hide)
        sd.pins = []
        sd.graphics = {}
        for sub in children(node, 'symbol'):
            parts = sub[1].rsplit('_', 2)
            unit = int(parts[-2]); body = int(parts[-1])
            if body not in (0, 1): continue
            pts = sd.graphics.setdefault(unit, [])
            for g in sub[2:]:
                if not isinstance(g, list) or not g: continue
                if g[0] == 'rectangle':
                    a, b = child(g, 'start'), child(g, 'end')
                    pts += [(float(a[1]), float(a[2])), (float(b[1]), float(b[2]))]
                elif g[0] in ('polyline', 'bezier'):
                    for xy in children(child(g, 'pts'), 'xy'): pts.append((float(xy[1]), float(xy[2])))
                elif g[0] == 'circle':
                    c = child(g, 'center'); r = float(child(g, 'radius')[1])
                    pts += [(float(c[1]) - r, float(c[2]) - r), (float(c[1]) + r, float(c[2]) + r)]
                elif g[0] == 'arc':
                    for k in ('start', 'mid', 'end'):
                        q = child(g, k)
                        if q: pts.append((float(q[1]), float(q[2])))
        for sub in children(node, 'symbol'):
            parts = sub[1].rsplit('_', 2)
            unit = int(parts[-2]); body = int(parts[-1])
            if body not in (0, 1): continue
            for p in children(sub, 'pin'):
                at = child(p, 'at'); ln = child(p, 'length')
                nm = child(p, 'name')[1]; num = child(p, 'number')[1]
                hc = child(p, 'hide')
                hidden = (hc is not None and str(hc[1]) == 'yes') or any(isinstance(a, Sym) and a == 'hide' for a in p)
                sd.pins.append(dict(unit=unit, type=str(p[1]), x=float(at[1]), y=float(at[2]), ang=float(at[3]),
                                    len=float(ln[1]), name=nm, num=num, hidden=hidden))
        self._cache[lib_id] = sd
        return sd
    def lib_symbols_node(self, lib_ids):
        out = ['lib_symbols']
        for lid in sorted(lib_ids):
            n = copy.deepcopy(self.get(lid).node)
            n[1] = lid
            out.append(n)
        return out
