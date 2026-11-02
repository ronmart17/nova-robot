"""Compare intended netlist (from generator) with KiCad-exported netlist; summarize ERC."""
import subprocess, json, xml.etree.ElementTree as ET, sys, os, collections
CLI = os.environ.get('KICAD_CLI', '/opt/kicad10/bin/kicad-cli')

def run(args, **kw):
    r = subprocess.run([CLI] + args, capture_output=True, text=True, **kw)
    return r.returncode, r.stdout + r.stderr

def kicad_nets(root_sch, tmp):
    out = os.path.join(tmp, 'net.xml')
    rc, log = run(['sch', 'export', 'netlist', '--format', 'kicadxml', '-o', out, root_sch])
    if rc != 0:
        raise RuntimeError(log)
    t = ET.parse(out).getroot()
    nets = {}
    for n in t.find('nets'):
        name = n.get('name')
        nets[name] = sorted((nd.get('ref'), nd.get('pin')) for nd in n.findall('node'))
    comps = {c.get('ref'): (c.findtext('value'), c.findtext('footprint')) for c in t.find('components')}
    return nets, comps

def intended(prj, sheets):
    globals_ = set(prj.power_map.keys())
    groups = collections.defaultdict(set)
    for sh in sheets:
        hier = {n for n, _ in prj.hier.get(sh.filename, [])}
        for (ref, pin), net in sh.net.items():
            if ref.startswith('#'): continue
            if net.startswith('__NC__'):
                key = net
            elif net in globals_ or net in hier:
                key = net
            else:
                key = (sh.filename, net)
            groups[key].add((ref, pin))
    return groups

def compare(prj, sheets, root_sch, tmp):
    nets, comps = kicad_nets(root_sch, tmp)
    want = intended(prj, sheets)
    # map pin -> kicad net
    pin2k = {}
    for name, nodes in nets.items():
        for rp in nodes:
            if rp[0].startswith('#'): continue
            pin2k[rp] = name
    problems = []
    for key, pins in want.items():
        knets = {pin2k.get(p, '<missing>') for p in pins}
        if len(knets) != 1:
            problems.append(f'SPLIT  {key}: ' + ', '.join(f'{p[0]}.{p[1]}->{pin2k.get(p, "<missing>")}' for p in sorted(pins)))
            continue
        kn = knets.pop()
        kpins = {p for p in nets.get(kn, []) if not p[0].startswith('#')}
        extra = kpins - pins
        if extra:
            problems.append(f'MERGED {key} ({kn}) also has: ' + ', '.join(f'{a}.{b}' for a, b in sorted(extra)))
    assigned = set().union(*want.values()) if want else set()
    unassigned = sorted(p for p in pin2k if p not in assigned)
    return problems, unassigned, nets, comps

def erc(root_sch, tmp):
    out = os.path.join(tmp, 'erc.json')
    rc, log = run(['sch', 'erc', '--format', 'json', '--severity-error', '--severity-warning', '-o', out, root_sch])
    data = json.load(open(out))
    items = []
    for sh in data.get('sheets', []):
        for v in sh.get('violations', []):
            items.append((v.get('severity'), v.get('type'), sh.get('path'), v.get('description'),
                          [i.get('description') for i in v.get('items', [])]))
    return items
