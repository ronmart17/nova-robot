"""BOM generation from KiCad netlist (kicadxml) including custom fields; JLCPCB-format BOM."""
import xml.etree.ElementTree as ET, csv, collections, os, re

def load_components(net_xml):
    t = ET.parse(net_xml).getroot()
    comps = []
    for c in t.find('components'):
        d = {'ref': c.get('ref'), 'value': c.findtext('value'), 'footprint': c.findtext('footprint') or ''}
        f = c.find('fields')
        if f is not None:
            for x in f: d[x.get('name')] = x.text or ''
        props = {p.get('name'): p.get('value') for p in c.findall('property')}
        d['dnp'] = 'dnp' in props or props.get('dnp') == '1'
        d['exclude_from_bom'] = 'exclude_from_bom' in props
        d['props'] = props
        comps.append(d)
    return comps

def natkey(ref):
    m = re.match(r'([A-Za-z#]+)(\d+)', ref)
    return (m.group(1), int(m.group(2))) if m else (ref, 0)

def write_boms(net_xml, out_dir, name):
    comps = [c for c in load_components(net_xml) if not c['ref'].startswith('#') and not c['exclude_from_bom']]
    groups = collections.OrderedDict()
    for c in sorted(comps, key=lambda c: natkey(c['ref'])):
        key = (c['value'], c['footprint'], c.get('MPN', ''), c['dnp'])
        groups.setdefault(key, []).append(c)
    full = os.path.join(out_dir, f'{name}_BOM.csv')
    with open(full, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['Item', 'Qty', 'Designators', 'Value', 'Footprint', 'Manufacturer', 'MPN', 'LCSC', 'Mouser', 'DigiKey',
                    'Alt MPN', 'Alt Mouser', 'Alt DigiKey', 'Description', 'Sourcing note', 'DNP'])
        for i, ((val, fp, mpn, dnp), cs) in enumerate(groups.items(), 1):
            c0 = cs[0]
            w.writerow([i, len(cs), ', '.join(c['ref'] for c in cs), val, fp.split(':')[-1], c0.get('Manufacturer', ''), mpn,
                        c0.get('LCSC', ''), c0.get('Mouser', ''), c0.get('DigiKey', ''), c0.get('Alt MPN', ''), c0.get('Alt Mouser', ''),
                        c0.get('Alt DigiKey', ''), c0.get('Description', ''), c0.get('Sourcing note', ''), 'DNP' if dnp else ''])
    jlc = os.path.join(out_dir, f'{name}_BOM_JLCPCB.csv')
    with open(jlc, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['Comment', 'Designator', 'Footprint', 'JLCPCB Part #'])
        for (val, fp, mpn, dnp), cs in groups.items():
            if dnp: continue
            if not cs[0]['footprint'] or cs[0]['props'].get('exclude_from_board'): continue
            w.writerow([val, ','.join(c['ref'] for c in cs), fp.split(':')[-1], cs[0].get('LCSC', '')])
    return full, jlc, groups
