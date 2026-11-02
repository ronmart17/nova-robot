import json, sys
d=json.load(open('/tmp/claude-0/-home-claude/20eabc81-f669-53cb-a2b0-f93a4a522b2a/scratchpad/pcb/drc.json'))
types = sys.argv[1:] or ['clearance','shorting_items','hole_clearance','starved_thermal']
for v in d['violations']:
    if v['type'] in types:
        its = v['items']
        pos = its[0]['pos'] if its else {}
        print(f"{v['type']:16s} ({pos.get('x',0)-150:.2f},{pos.get('y',0)-100:.2f}) {v['description'][:70]} || " + ' | '.join(i['description'][:70] for i in its))
