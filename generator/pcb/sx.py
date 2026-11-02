"""S-expression parser that keeps atom types: quoted -> str, unquoted -> Sym (numbers -> float/int)."""
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sexpr
sexpr.PREC = 6     # lossless internal footprint coordinates (parity with the library)
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
                    nx = s[j + 1]; buf.append('\n' if nx == 'n' else nx); j += 2; continue
                buf.append(s[j]); j += 1
            out.append(('Q', ''.join(buf))); i = j + 1; continue
        j = i
        while j < n and s[j] not in ' \t\r\n()': j += 1
        out.append(('A', s[i:j])); i = j
    return out

def _atom(a):
    try:
        if any(ch in a for ch in '.eE'):
            if a.replace('.', '', 1).replace('-', '', 1).replace('e', '', 1).replace('E', '', 1).replace('+', '', 1).isdigit():
                return float(a)
        else:
            return int(a)
    except ValueError:
        pass
    return Sym(a)

def parse(s):
    toks = tokenize(s); pos = 0
    def rd():
        nonlocal pos
        t = toks[pos]; pos += 1
        if t == '(':
            lst = []
            while toks[pos] != ')': lst.append(rd())
            pos += 1
            return lst
        if t[0] == 'Q': return t[1]
        return _atom(t[1])
    return rd()

def kids(n, head):
    return [c for c in n if isinstance(c, list) and c and c[0] == head]

def kid(n, head):
    k = kids(n, head)
    return k[0] if k else None
