import re, sys
sys.path.insert(0, '/home/claude/robot/gen'); sys.path.insert(0, '/home/claude/robot')
from symgen import box_symbol, lib
from symlib import load_lib

KSYM = '/opt/kicad10libs/root/usr/share/kicad/symbols'   # official KiCad 10.0.5 libraries

def esc(v):
    return v.replace('\\', '\\\\').replace('"', '\\"')

def copy_symbol(libfile, src, dst, replace=None, props=None):
    """Copy an official symbol (v10 format) under a new name with new properties."""
    blk = load_lib(f'{KSYM}/{libfile}.kicad_sym')[src]
    blk = blk.replace(f'(symbol "{src}"', f'(symbol "{dst}"', 1)
    blk = re.sub(rf'\(symbol "{re.escape(src)}_(\d+)_(\d+)"', rf'(symbol "{dst}_\1_\2"', blk)
    for a, b in (replace or []):
        blk = blk.replace(a, b)
    for k, v in (props or {}).items():
        pat = rf'\(property "{re.escape(k)}" "(?:[^"\\]|\\.)*"'
        assert re.search(pat, blk), (dst, k)
        blk = re.sub(pat, lambda m: f'(property "{k}" "{esc(v)}"', blk, count=1)
    return '\t' + blk + '\n'

syms = []

# --- TI TPS566238P: 3-18 V, 6 A synchronous buck, D-CAP3, 98 % max duty (frequency foldback), PG (VQFN-HR RQF-9) ---
syms.append(box_symbol(
    'TPS566238PRQFR', ref='U', value='TPS566238PRQFR',
    footprint='robot:Texas_RQF0009A_VQFN-HR-9_1.5x2mm_P0.5mm',
    datasheet='https://www.ti.com/lit/ds/symlink/tps566238.pdf',
    description='3-18 V input, 6 A synchronous step-down converter, D-CAP3, 600 kHz, 98% max duty (frequency foldback), power-good, VQFN-HR-9 1.5x2 mm',
    keywords='buck step-down DC-DC D-CAP3 6A',
    fp_filters='*RQF0009A*',
    left=[('5', 'VIN', 'power_in'), None, None, ('3', 'EN', 'input'), None, ('1', 'VCC', 'power_out')],
    right=[('7', 'BST', 'passive'), ('8', 'SW', 'power_out'), None, ('2', 'FB', 'input'), None, ('9', 'PG', 'open_collector')],
    bottom=[('4', 'PGND', 'power_in')],
    stacked=[('6', 'VIN', 'passive', '5')],
    width=15.24))

# --- Nisshinbo (Ricoh) R5460N212AF 2-cell Li-ion protector (SOT-23-6) ---
syms.append(box_symbol(
    'R5460N212AF', ref='U', value='R5460N212AF',
    footprint='Package_TO_SOT_SMD:SOT-23-6',
    datasheet='https://www.nisshinbo-microdevices.co.jp/en/pdf/datasheet/r5460-ea.pdf',
    description='2-cell Li-ion protector: OV 4.29V/4.05V, UV 3.00V/3.20V, discharge OC 0.2V, charge OC -0.2V, short 1.1V, SOT-23-6',
    keywords='battery protection 2S li-ion overcharge overdischarge overcurrent',
    fp_filters='SOT?23*',
    top=[('5', 'VDD', 'power_in')],
    left=[None, ('4', 'VC', 'input'), None],
    right=[('2', 'COUT', 'output'), ('1', 'DOUT', 'output'), ('3', 'V-', 'input')],
    bottom=[('6', 'VSS', 'power_in')],
    width=15.24))

# --- ST LSM6DSO 6-axis IMU (LGA-14L 2.5x3) ---
syms.append(box_symbol(
    'LSM6DSOXTR', ref='U', value='LSM6DSOXTR',
    footprint='Package_LGA:LGA-14_3x2.5mm_P0.5mm_LayoutBorder3x4y',
    datasheet='https://www.st.com/resource/en/datasheet/lsm6dsox.pdf',
    description='iNEMO 6DoF IMU with machine learning core, 3D accelerometer and 3D gyroscope, I2C/SPI, LGA-14L (pin-compatible with LSM6DSO)',
    keywords='accelerometer gyroscope IMU MEMS',
    fp_filters='LGA*3x2.5mm*P0.5mm*',
    left=[('1', 'SDO/SA0', 'bidirectional'), ('2', 'SDx', 'bidirectional'), ('3', 'SCx', 'input'), None,
          ('14', 'SDA', 'bidirectional'), ('13', 'SCL', 'input'), ('12', 'CS', 'input')],
    right=[('4', 'INT1', 'output'), ('9', 'INT2', 'output'), None, ('10', 'OCS_Aux', 'output'),
           ('11', 'SDO_Aux', 'bidirectional')],
    top=[('5', 'VDDIO', 'power_in'), ('8', 'VDD', 'power_in')],
    bottom=[('6', 'GND', 'power_in')], stacked=[('7', 'GND', 'passive', '6')], width=20.32))

copies = []
# --- ST VL53L4CD (graphics and pinout from VL53L1CX: same LGA12 pinout, pin-to-pin compatible per ST DS13812) ---
copies.append(copy_symbol('Sensor_Distance', 'VL53L1CXV0FY1', 'VL53L4CDV0DH1', props={
    'Value': 'VL53L4CDV0DH/1', 'Footprint': 'robot:ST_VL53L4CD',
    'Datasheet': 'https://www.st.com/resource/en/datasheet/vl53l4cd.pdf',
    'Description': 'Time-of-Flight ranging sensor 1-1300 mm, 18 deg FoV, I2C 0x29, 2.6-3.5 V, optical LGA12 4.4x2.4 mm',
    'ki_keywords': 'time of flight ToF distance sensor laser VCSEL',
    'ki_fp_filters': '*VL53L4CD* *VL53L0X*'}))
# --- TI NexFET N-channel, VSON-8 3.3x3.3 (pinout S 1-3, G 4, D 5-8 + pad) — graphics from the generic NexFET symbol ---
for name, desc in (('CSD17578Q3A', '30V N-channel NexFET, 9.4 mOhm @ VGS 4.5V, VSON-8 3.3x3.3 mm'),
                   ('CSD17579Q3A', '30V N-channel NexFET, 8.7 mOhm @ VGS 10V, VSON-8 3.3x3.3 mm')):
    copies.append(copy_symbol('Transistor_FET', 'Q_NMOS_SSSGD_AvalancheRated', name, props={
        'Value': name, 'Footprint': 'Package_SON:VSON-8_3.3x3.3mm_P0.65mm_NexFET',
        'Datasheet': f'https://www.ti.com/lit/ds/symlink/{name.lower()}.pdf', 'Description': desc}))

# --- Power symbols VSYS / VBAT (graphics from +5V) ---
for net, desc in (('VSYS', 'system rail from the charger power path (6.0-8.4 V)'), ('VBAT', 'battery pack positive after fuse (6.0-8.4 V)')):
    copies.append(copy_symbol('power', '+5V', net, props={
        'Value': net, 'Description': f'Power symbol creates a global label with name "{net}", {desc}'}))

import subprocess, tempfile, os
CLI = os.environ.get('KICAD_CLI', '/opt/kicad10/bin/kicad-cli')
OUTLIB = '/home/claude/robot/kicad/lib/robot.kicad_sym'
tmp = tempfile.mkdtemp()
open(f'{tmp}/box_v7.kicad_sym', 'w').write(lib(syms))
r = subprocess.run([CLI, 'sym', 'upgrade', f'{tmp}/box_v7.kicad_sym', '-o', f'{tmp}/box_v10.kicad_sym'], capture_output=True, text=True)
assert r.returncode == 0, r.stdout + r.stderr
v10 = open(f'{tmp}/box_v10.kicad_sym').read().rstrip()
assert v10.endswith(')')
merged = v10[:-1].rstrip() + '\n' + ''.join(copies) + ')\n'
open(f'{tmp}/merged.kicad_sym', 'w').write(merged)
r = subprocess.run([CLI, 'sym', 'upgrade', '--force', f'{tmp}/merged.kicad_sym', '-o', f'{tmp}/final.kicad_sym'], capture_output=True, text=True)
assert r.returncode == 0, r.stdout + r.stderr
import shutil
shutil.copy(f'{tmp}/final.kicad_sym', OUTLIB)
os.makedirs('/home/claude/robot/lib10', exist_ok=True)
shutil.copy(OUTLIB, '/home/claude/robot/lib10/robot.kicad_sym')
print('written', len(syms) + len(copies), 'symbols ->', OUTLIB)
