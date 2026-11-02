"""Runs ERC and DRC (with schematic parity) on the three Rev B projects and writes docs/verification.json + a table."""
import json, os, subprocess, sys, collections
CLI = '/opt/kicad10/bin/kicad-cli'
BASE = '/home/claude/robot/kicad'
OUT = '/tmp/claude-0/-home-claude/277a7080-1a17-5e2e-be8e-818ab51082a1/scratchpad/verify'
os.makedirs(OUT, exist_ok=True)
res = {}
names = sys.argv[1:] or ['nova-main', 'nova-head', 'nova-dock']
for name in names:
    d = f'{BASE}/{name}'
    r = {}
    erc = f'{OUT}/{name}_erc.json'
    subprocess.run([CLI, 'sch', 'erc', '--format', 'json', '--severity-all', '-o', erc, f'{d}/{name}.kicad_sch'], capture_output=True)
    e = json.load(open(erc))
    sev = collections.Counter(v['severity'] for s in e.get('sheets', []) for v in s.get('violations', []) if not v.get('excluded'))
    r['erc'] = dict(sev)
    r['erc_excluded'] = sum(1 for s in e.get('sheets', []) for v in s.get('violations', []) if v.get('excluded'))
    pcb = f'{d}/{name}.kicad_pcb'
    if os.path.exists(pcb):
        drc = f'{OUT}/{name}_drc.json'
        subprocess.run([CLI, 'pcb', 'drc', '--format', 'json', '--schematic-parity', '--severity-all', '-o', drc, pcb], capture_output=True)
        j = json.load(open(drc))
        r['drc'] = dict(collections.Counter(v['severity'] for v in j.get('violations', [])))
        r['drc_types'] = dict(collections.Counter(v['type'] for v in j.get('violations', [])))
        r['unconnected'] = len(j.get('unconnected_items', []))
        r['parity'] = len(j.get('schematic_parity', []))
    res[name] = r
    print(name, r)
p = '/home/claude/robot/docs/verification.json'
old = json.load(open(p)) if os.path.exists(p) else {}
old.update(res)
json.dump(old, open(p, 'w'), indent=1)
