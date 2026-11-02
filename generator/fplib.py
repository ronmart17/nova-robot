"""Project footprint library (robot.pretty) built from the official KiCad 10.0.5 footprints.
Copies each footprint, rewrites the 3D model path to ${KIPRJMOD}/../lib/robot.3dshapes and copies the official
model (STEP/WRL) if it exists; otherwise the model generated with CadQuery (gen3d/models.py) is used."""
import re, os, shutil, uuid
F10 = '/opt/kicad10libs/root/usr/share/kicad/footprints'
M = '/usr/share/kicad/3dmodels'
OUT = '/home/claude/robot/kicad/lib'
FPS = ['Package_DFN_QFN.pretty/Texas_RQM0029A_VQFN-29_4x4mm_P0.4mm',
       'Package_TO_SOT_SMD.pretty/SOT-583-8', 'RF_Module.pretty/ESP32-S3-WROOM-1',
       'Package_SO.pretty/TSSOP-24_4.4x7.8mm_P0.65mm', 'Package_SO.pretty/SSOP-24_5.3x8.2mm_P0.65mm',
       'Package_LGA.pretty/LGA-14_3x2.5mm_P0.5mm_LayoutBorder3x4y',
       'Inductor_SMD.pretty/L_Bourns_SRP5030T',
       'Button_Switch_SMD.pretty/SW_SPST_PTS810', 'Button_Switch_SMD.pretty/SW_SPDT_PCM12',
       'Connector_USB.pretty/USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal',
       'Connector_JST.pretty/JST_PH_S6B-PH-K_1x06_P2.00mm_Horizontal',
       'Connector_JST.pretty/JST_SH_SM20B-SRSS-TB_1x20-1MP_P1.00mm_Horizontal',
       'Sensor_Distance.pretty/ST_VL53L1x', 'OptoDevice.pretty/ST_VL53L0X',
       'Fuse.pretty/Fuse_1812_4532Metric', 'Fuse.pretty/Fuse_Littelfuse-NANO2-451_453',
       'Connector_USB.pretty/USB_C_Receptacle_HRO_TYPE-C-31-M-12']
RENAME = {'ST_VL53L0X': 'ST_VL53L4CD'}   # same LGA12 land pattern (ST: VL53L4CD is pin-to-pin compatible), own 3D model
EXTRA = {}   # name -> list of additional footprints (protector, etc.) added from parts

def add(fp):
    if fp not in FPS: FPS.append(fp)

def silk_text(text, x, y, size=0.8):
    u = str(uuid.uuid5(uuid.NAMESPACE_URL, 'robot-fp-' + text + str(x) + str(y)))
    return (f'\t(fp_text user "{text}"\n\t\t(at {x} {y} 0)\n\t\t(layer "F.SilkS")\n\t\t(uuid "{u}")\n'
            f'\t\t(effects\n\t\t\t(font\n\t\t\t\t(size {size} {size})\n\t\t\t\t(thickness 0.12)\n\t\t\t)\n\t\t)\n\t)\n')

def build():
    os.makedirs(f'{OUT}/robot.pretty', exist_ok=True); os.makedirs(f'{OUT}/robot.3dshapes', exist_ok=True)
    for f in os.listdir(f'{OUT}/robot.pretty'):
        os.remove(f'{OUT}/robot.pretty/{f}')
    report = []
    for fp in FPS:
        src = f'{F10}/{fp}.kicad_mod'; name = os.path.basename(fp)
        t = open(src, encoding='utf-8').read()
        models = re.findall(r'\(model\s+"([^"]+)"', t)
        for m in models:
            p = re.sub(r'\$\{KICAD\d*_3DMODEL_DIR\}', M, m)
            base = os.path.splitext(p)[0]; stem = os.path.basename(base)
            got = []
            for ext in ('.step', '.wrl'):
                if os.path.exists(base + ext):
                    shutil.copy(base + ext, f'{OUT}/robot.3dshapes/{stem}{ext}'); got.append('official' + ext)
            if not got and os.path.exists(f'{OUT}/robot.3dshapes/{stem}.step'):
                got.append('generated')
            report.append((name, stem, got))
            t = t.replace(m, '${KIPRJMOD}/../lib/robot.3dshapes/' + stem + '.step')
        if name == 'USB_C_Receptacle_HRO_TYPE-C-31-M-12':
            # common footprint for HRO TYPE-C-31-M-12 / GCT USB4105-GF-A: same pads (±0.05 mm) and legs; 0.6×1.4 mm
            # rear slots to accept the legs of both; 3D model of the GCT part (equivalent envelope)
            new = 'USB_C_Receptacle_HRO_TYPE-C-31-M-12_GCT_USB4105'
            t = t.replace(f'(footprint "{name}"', f'(footprint "{new}"')
            t = re.sub(r'\(size 1 1\.6\)\s*\(drill oval 0\.6 1\.2\)', '(size 1 1.8)\n\t\t(drill oval 0.6 1.4)', t)
            assert t.count('(drill oval 0.6 1.4)') == 2, 'rear slots'
            t = re.sub(r'\(descr "[^"]*"\)', '(descr "USB 2.0 Type-C receptacle 16P, common footprint for HRO TYPE-C-31-M-12 and GCT USB4105-GF-A (rear slots 0.6x1.4)")', t, count=1)
            t = re.sub(r'\(model "[^"]*"', '(model "${KIPRJMOD}/../lib/robot.3dshapes/USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal.step"', t)
            # front silkscreen: the connector front overhangs the board edge; the side lines are cut
            # 0.4 mm before the edge and the front line is removed (it would fall outside the board)
            for x in ('-4.7', '4.7'):
                a0 = t.count(f'(start {x} 2)\n\t\t(end {x} 3.9)')
                t = t.replace(f'(start {x} 2)\n\t\t(end {x} 3.9)', f'(start {x} 2)\n\t\t(end {x} 2.8)')
                assert a0 == 1, ('side', x)
            t2 = re.sub(r'\t\(fp_line\n\t\t\(start -4\.7 3\.9\)\n\t\t\(end 4\.7 3\.9\)\n(?:\t\t[^\n]*\n)*?\t\)\n', '', t, count=1)
            assert t2 != t, 'front line'
            t = t2
            name = new
        if name in RENAME:
            new = RENAME[name]
            t = t.replace(f'(footprint "{name}"', f'(footprint "{new}"')
            t = re.sub(r'(\$\{KIPRJMOD\}/../lib/robot.3dshapes/)[^"]+\.step', r'\g<1>' + new + '.step', t)
            t = re.sub(r'\(descr "[^"]*"\)', '(descr "ST VL53L4CD optical LGA12 4.4x2.4 mm (land pattern of VL53L0X/L1X, pin-to-pin compatible per ST DS13812)")', t, count=1)
            name = new
        if name in ('ESP32-S3-WROOM-1',):
            # 0.3 mm thermal vias (JLCPCB standard drill; 0.2 mm ones carry a surcharge)
            n0 = len(re.findall(r'\(drill 0\.2\)', t))
            t = re.sub(r'\(size 0\.[56] 0\.[56]\)(\s*)\(drill 0\.2\)', r'(size 0.6 0.6)\1(drill 0.3)', t)
            assert len(re.findall(r'\(drill 0\.2\)', t)) == 0 and n0 > 0, name
        if name == 'SW_SPST_PTS810':
            # pads with the same number are connected inside the push button
            t = t.replace('(duplicate_pad_numbers_are_jumpers no)', '(duplicate_pad_numbers_are_jumpers yes)')
            assert '(duplicate_pad_numbers_are_jumpers yes)' in t
        if name == 'Vishay_TCRT5000':
            i = t.index('\t(pad ')
            t = t[:i] + silk_text('IR', -1.27, -2.9) + t[i:]
        open(f'{OUT}/robot.pretty/{name}.kicad_mod', 'w', encoding='utf-8').write(t)
    import fpgen
    for n in fpgen.build(f'{OUT}/robot.pretty'):
        report.append((n, 'custom', ['generated' if os.path.exists(f'{OUT}/robot.3dshapes/{n}.step') else 'NO MODEL']))
    return report

if __name__ == '__main__':
    for r in build():
        print(r)
