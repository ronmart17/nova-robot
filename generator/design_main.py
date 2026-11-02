import sys, os, json, importlib
sys.path.insert(0, os.path.dirname(__file__))
from sch import Sheet, Project, uid, add_junctions, eff, prop_node, Sym, G
from sexpr import fmt
from kilib import Library
import s_power_in, s_power_sys, s_mcu, s_motors, s_sensors, s_pi
from helpers import place_part

OUT = sys.argv[1] if len(sys.argv) > 1 else '/home/claude/robot/kicad/nova-main/nova-main'
LIB10 = os.environ.get('LIB10', '/home/claude/robot/lib10')
LIBS = ['Device', 'power', 'Connector', 'Connector_Generic', 'Connector_Generic_MountingPin', 'RF_Module', 'Driver_Motor',
        'Interface_Expansion', 'Power_Protection', 'Transistor_FET', 'Diode', 'Switch', 'Mechanical', '74xGxx',
        'Regulator_Switching', 'Power_Management', 'Battery_Management', 'Sensor_Distance', 'Sensor_Touch', 'Simulation_SPICE']
REV, DATE = 'B', '2026-10-28'
COMPANY = 'ronmart · Caril Ronnie Martínez Vera'

def library():
    d = {n: f'{LIB10}/{n}.kicad_sym' for n in LIBS}
    d['robot'] = f'{LIB10}/robot.kicad_sym'
    return Library(d)

SHEETS = [  # file, title, module, page, block name, column
    ('power_in.kicad_sch', 'Power inputs and 2S buck-boost charger', s_power_in, 2, 'USB-C + 12 V dock, BQ25798 charger', 'L'),
    ('power_sys.kicad_sch', 'Battery, protection and regulators', s_power_sys, 3, '2S battery, protection, 3V3 and Pi 5 V bucks', 'L'),
    ('mcu.kicad_sch', 'ESP32-S3 microcontroller and IO expander', s_mcu, 4, 'MCU ESP32-S3 and IO expander', 'C'),
    ('motors.kicad_sch', 'Motors and encoders', s_motors, 5, 'Motors and encoders', 'R'),
    ('sensors.kicad_sch', 'IMU, cliff sensors, servo and head connector', s_sensors, 6, 'IMU, cliff ToF, servo and head', 'R'),
    ('pi.kicad_sch', 'Raspberry Pi 5 link and power output', s_pi, 7, 'Raspberry Pi 5 link and USB-C power', 'L'),
]

def sheet_symbol(root, child, x, y, w, pins_left, pins_right, name, page):
    """Sheet symbol. pins_*: lists of (net, shape) or None (empty row). Returns {net: (point, direction)}."""
    n = max(len(pins_left), len(pins_right), 1)
    h = (n + 1) * G
    suid = uid(root.project.name, 'sheetsym', child.filename)
    node = ['sheet', ['at', x, y], ['size', w, h], ['exclude_from_sim', Sym('no')], ['in_bom', Sym('yes')], ['on_board', Sym('yes')],
            ['dnp', Sym('no')], ['fields_autoplaced', Sym('yes')], ['stroke', ['width', 0.1524], ['type', Sym('solid')]],
            ['fill', ['color', 0, 0, 0, 0.0]], ['uuid', suid],
            prop_node('Sheetname', name, x, y - 0.7116, 0, justify='left bottom', size=1.524),
            prop_node('Sheetfile', child.filename, x, y + h + 0.5846, 0, justify='left top', size=1.27)]
    pts = {}
    for side, pins in (('L', pins_left), ('R', pins_right)):
        for i, pn in enumerate(pins):
            if pn is None: continue
            net, shape = pn; py = y + (i + 1) * G
            px = x if side == 'L' else x + w
            node.append(['pin', net, Sym(shape), ['at', px, py, 180 if side == 'L' else 0], ['uuid', uid(suid, 'pin', net)],
                         eff(1.27, 'left' if side == 'L' else 'right')])
            pts[net] = ((px, py), (-1, 0) if side == 'L' else (1, 0))
    node.append(['instances', ['project', root.project.name, ['path', '/' + root.uuid, ['page', str(page)]]]])
    root.items.append(node)
    return pts, h

def build(date=DATE):
    lib = library()
    prj = Project('nova-main', lib, date, REV, COMPANY)
    prj.power_map['+5V'] = 'power:+5V'
    root = Sheet(prj, 'nova-main.kicad_sch', 'NOVA — Main board (chassis)', 1, path='/' + prj.root_uuid,
                 comments=('Main board Rev B — Raspberry Pi 5 edition',
                           'Schematic generated and verified with KiCad 10.0.7 (ERC)', '', ''))
    root.uuid = prj.root_uuid
    subs = []
    for fname, title, mod, page, _, _ in SHEETS:
        suid = uid(prj.name, 'sheetsym', fname)
        sh = Sheet(prj, fname, title, page, path=f'/{prj.root_uuid}/{suid}', comments=(f'Sheet {page}: {title}', '', '', ''))
        mod.build(sh)
        add_junctions(sh)
        subs.append(sh)
    build_root(root, subs)
    add_junctions(root)
    return prj, root, subs

def uniq(seq):
    seen = set(); out = []
    for n, s in seq:
        if n in seen: continue
        seen.add(n); out.append((n, s))
    return out

def build_root(root, subs):
    """Block diagram: MCU in the centre, power and Pi sheets on the left, motors and sensors on the right.
    Pins shared only by the MCU and one sheet are joined by straight wires; every pin also carries its net label."""
    prj = root.project
    byname = {s.filename: s for s in subs}
    H = {f: dict(uniq(prj.hier.get(f, []))) for f in byname}
    meta = {f: (name, page, col) for f, _, _, page, name, col in SHEETS}
    mcu = 'mcu.kicad_sch'
    root.text('NOVA — MAIN BOARD REV B (RASPBERRY PI 5 EDITION) — BLOCK DIAGRAM', (25.4, 30.48), size=2.54, bold=True)
    left = [f for f, *_ in SHEETS if meta[f][2] == 'L']
    right = [f for f, *_ in SHEETS if meta[f][2] == 'R']
    def owners(net):
        return [f for f in byname if net in H[f]]
    # MCU pin order, grouped by the sheet each net goes to (first non-MCU owner, in sheet order)
    side_of = {}
    groups = {f: [] for f in left + right}
    for net in H[mcu]:
        others = [f for f in left + right if net in H[f]]
        if not others:
            raise ValueError(f'MCU net {net} not used by any other sheet')
        groups[others[0]].append(net)
    import math
    y0 = 50.8
    def extra_of(f):
        return [n for n in H[f] if n not in groups[f]]
    def column(files):
        """MCU pin rows for one side, padded so that each sheet symbol aligns with its MCU pin group and
        clears the sheet symbol above it by at least 12.7 mm. Returns (rows, {file: sheet top y})."""
        rows = []; tops = {}; bottom = None
        for f in files:
            linked = groups[f]; extra = extra_of(f)
            n_all = len(linked) + (1 if linked and extra else 0) + len(extra)
            if linked:
                s0 = len(rows)
                if bottom is not None:
                    s0 = max(s0, math.ceil((bottom + 12.7 - y0) / G - 1e-9))
                rows += [None] * (s0 - len(rows))
                tops[f] = y0 + s0 * G
                rows += [(n, H[mcu][n]) for n in linked]
            else:
                tops[f] = y0 if bottom is None else bottom + 12.7
            bottom = tops[f] + (n_all + 1) * G
        return rows, tops
    lrows, ltops = column(left)
    rrows, rtops = column(right)
    xm, wm = 177.8, 60.96
    pm, hm = sheet_symbol(root, byname[mcu], xm, y0, wm, lrows, rrows, meta[mcu][0], meta[mcu][1])
    placed = {}
    def place_side(files, tops, x, facing):
        for f in files:
            linked = groups[f]; extra = extra_of(f)
            rows_all = [(n, H[f][n]) for n in linked] + ([None] if linked and extra else []) + [(n, H[f][n]) for n in extra]
            if facing == 'R':
                pts, h = sheet_symbol(root, byname[f], x, tops[f], 60.96, [], rows_all, meta[f][0], meta[f][1])
            else:
                pts, h = sheet_symbol(root, byname[f], x, tops[f], 60.96, rows_all, [], meta[f][0], meta[f][1])
            placed[f] = pts
    place_side(left, ltops, 66.04, 'R')
    place_side(right, rtops, 299.72, 'L')
    # wires/labels
    for f, pts in placed.items():
        for net, ((x, y), d) in pts.items():
            if net in pm and len(owners(net)) == 2 and abs(pm[net][0][1] - y) < 1e-6:
                (a, _) = pm[net]
                root.wire((x, y), a)
                root.label(net, ((x + a[0]) / 2 - 2.54, y), (1, 0))
            else:
                end = (x + d[0] * 7.62, y)
                root.wire((x, y), end); root.label(net, end, d)
    for net, ((x, y), d) in pm.items():
        if len(owners(net)) == 2 and any(net in placed[f] and abs(placed[f][net][0][1] - y) < 1e-6 for f in placed):
            continue
        end = (x + d[0] * 7.62, y)
        root.wire((x, y), end); root.label(net, end, d)
    ybot = max(y0 + hm, 190.0)
    root.text('Shared I2C bus: BQ25798 (0x6B), TCA9535 (0x20), LSM6DSOX (0x6A), VL53L1X head (0x29) and 2× VL53L4CD\n'
              '(0x29 at power-up, moved to 0x30/0x31 by firmware). Power nets VSYS, VBAT, +5V (Pi), +3V3 and GND are global.',
              (25.4, ybot + 7.62), size=1.27, italic=True)
    root.text('MECHANICAL', (25.4, ybot + 17.78), size=1.524, bold=True)
    for i in range(10):
        key = 'MH' if i < 4 or i >= 8 else 'MH_M25_PAD'
        h = place_part(root, key, f'H{i+1}', 33.02 + i * 12.7, ybot + 30.48, ref_at=(2.54, -2.54, 'left'), val_at=(2.54, 0, 'left'))
        if True:
            (px, py), _ = h.pin('1'); root.assign(h, '1', 'GND')
            root.wire((px, py), (px, py + 2.54)); root.power('GND', (px, py + 2.54))
    for i in range(3):
        place_part(root, 'FID', f'FID{i+1}', 33.02 + i * 12.7, ybot + 58.42, ref_at=(2.54, -1.27, 'left'), val_at=(2.54, 1.27, 'left'))
    root.text('H1–H4: shell (M3, from below) · H5–H8: Pi 5 standoffs (M2.5) · H9–H10: head brackets (M3) · FID1–3: fiducials', (25.4, ybot + 45.72), size=1.27)
    notes = ('DESIGN NOTES\n'
             '1. Inputs: USB-C 5 V (VAC1) and 12 V charging dock (VAC2) → BQ25798 buck-boost charger, NVDC power path → VSYS.\n'
             '2. VSYS (6.0–8.4 V) feeds the TB6612 directly, the always-on 3.3 V buck and the 5.15 V / 5 A Pi buck.\n'
             '3. The power switch acts on the buck enables: charging still works with the robot switched off.\n'
             '4. The ESP32 switches the Pi rail (PI_PWR_OFF) after the shutdown handshake (sheet 7).\n'
             '5. Head board (nova-head): ST7789 display, VL53L1X ToF, AT42QT1010 touch, Camera Module 3 mount.\n'
             '6. References per sheet: 2xx inputs/charger, 3xx battery/regulators, 4xx MCU, 5xx motors, 6xx sensors, 7xx Pi.')
    root.text(notes, (149.86, ybot + 17.78), size=1.27)
    rev = ('REVISIONS\nA  2026-10-24  ESP32-only robot (first release)\n'
           'B  2026-10-28  Raspberry Pi 5 edition: BQ25798 dual-input charger (USB-C + 12 V dock), 5 V / 5 A Pi rail,\n'
           '                    Pi link, VL53L4CD cliff sensors, servo; audio moved to the XVF3800 mic array')
    root.text(rev, (149.86, ybot + 50.8), size=1.27)

def write(prj, root, subs, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    lib = prj.lib
    for sh in [root] + subs:
        extra = []
        if sh is root:
            extra.append(['sheet_instances', ['path', '/', ['page', '1']]])
        node = sh.node(lib.lib_symbols_node(sh.lib_ids), extra)
        open(os.path.join(out_dir, sh.filename), 'w', encoding='utf-8').write(fmt(node) + '\n')
    return [root] + subs

if __name__ == '__main__':
    prj, root, subs = build()
    write(prj, root, subs, OUT)
    print('ok', OUT)
