"""Parts database: symbol, value, footprint and purchasing fields.
Rev A stock checked on 2026-10-24 (LCSC/JLCPCB, Mouser, DigiKey); Rev B additions checked on 2026-10-28 against the
JLCPCB parts snapshot (jlcparts, 2026-10-28) — Western distributor numbers left blank where not verified. Rule: one MPN in stock at LCSC and at Mouser or DigiKey;
'JLC Basic alt' gives the JLC Basic alternative (cheaper to assemble) when the main MPN is an Extended part."""

FP = dict(
    R0402='Resistor_SMD:R_0402_1005Metric', R0603='Resistor_SMD:R_0603_1608Metric', R0805='Resistor_SMD:R_0805_2012Metric',
    C0402='Capacitor_SMD:C_0402_1005Metric', C0603='Capacitor_SMD:C_0603_1608Metric', C0805='Capacitor_SMD:C_0805_2012Metric',
    C1206='Capacitor_SMD:C_1206_3216Metric', LED0603='LED_SMD:LED_0603_1608Metric', SOT23='Package_TO_SOT_SMD:SOT-23',
    SOT236='Package_TO_SOT_SMD:SOT-23-6',
)

P = {}
def add(key, **kw):
    P[key] = kw

def src(mpn, maker, lcsc='', mouser='', digikey='', note=''):
    d = {'MPN': mpn, 'Manufacturer': maker, 'LCSC': lcsc, 'Mouser': mouser, 'DigiKey': digikey}
    if note: d['Sourcing note'] = note
    return d

# ------------------------------------------------------------------ resistors (1 %, 0402 unless stated)
def _r(key, val, size='0402', note=''):
    add(key, lib='Device:R', value=val, footprint=FP['R' + size],
        fields={'Description': f'Thick-film resistor {val} 1% {size}' + (f' — {note}' if note else ''), 'Tolerance': '1%'})
for k, v in {'R_0': '0R', 'R_33': '33R', 'R_100': '100R', 'R_1k': '1k', 'R_2k2': '2.2k', 'R_4k7': '4.7k', 'R_5k1': '5.1k',
             'R_5k23': '5.23k', 'R_10k': '10k', 'R_23k2': '23.2k', 'R_30k1': '30.1k', 'R_31k6': '31.6k', 'R_52k3': '52.3k',
             'R_100k': '100k', 'R_102k': '102k', 'R_200k': '200k', 'R_1M': '1M', 'R_330': '330R', 'R_86k6': '86.6k'}.items():
    _r(k, v)
_r('R_180_0805', '180R', size='0805', note='IR LED, 125 mW')
_r('R_1R0_0805', '1R', size='0805', note='VBUS RC damper (hot-plug transients)')

# ------------------------------------------------------------------ capacitors
def _cval(val, volt):
    v = val.replace('nF', 'n').replace('pF', 'p').replace('uF', 'u')
    return v + (f'/{volt}' if v.endswith('u') else (' C0G' if v.endswith('p') else ''))

def _c(key, val, volt, size, diel='X7R', note=''):
    add(key, lib='Device:C', value=_cval(val, volt), footprint=FP['C' + size],
        fields={'Description': f'MLCC {val} {volt} {diel} {size}' + (f' — {note}' if note else ''), 'Voltage': volt, 'Dielectric': diel})
_c('C_100n', '100nF', '50V', '0402')
_c('C_1n', '1nF', '50V', '0402')
_c('C_2n2', '2.2nF', '50V', '0402')
_c('C_8n2', '8.2nF', '50V', '0402', note='QT1010 Cs')
_c('C_33n', '33nF', '50V', '0402')
_c('C_47n', '47nF', '25V', '0402')
_c('C_1u', '1uF', '25V', '0402', diel='X5R')
_c('C_1u_25V', '1uF', '25V', '0603', diel='X5R')
_c('C_4u7', '4.7uF', '16V', '0603', diel='X5R')
_c('C_10u_10V', '10uF', '10V', '0603', diel='X5R')
_c('C_22u_10V', '22uF', '10V', '0805', diel='X5R')
_c('C_22u_25V', '22uF', '25V', '1206', diel='X5R')
_c('C_10u_25V', '10uF', '25V', '1206', diel='X5R', note='VBUS RC damper')
add('C_100u', lib='Device:C_Polarized', value='100u/50V', footprint='Capacitor_SMD:CP_Elec_6.3x7.7',
    fields={'Description': 'Aluminium electrolytic 100uF 50V, 6.3x7.7 mm, ESR 0.34 ohm — damping bulk on VM', 'Voltage': '50V'})

add('FB_220R', lib='Device:FerriteBead_Small', value='220R@100MHz', footprint='Inductor_SMD:L_0603_1608Metric',
    fields={'Description': 'Ferrite bead 220R@100MHz 1.4A 0603'})
add('LED_G', lib='Device:LED', value='Green', footprint=FP['LED0603'], fields={'Description': 'LED yellow-green 574 nm 0603'})
add('LED_O', lib='Device:LED', value='Orange', footprint=FP['LED0603'], fields={'Description': 'LED orange 605 nm 0603'})

# ------------------------------------------------------------------ inductors
add('L_1u0', lib='Device:L', value='1.0uH', footprint='robot:L_Pulse_PA4332',
    fields={'Description': 'Power inductor 1.0uH 20%, Isat 8.5A, Irms 5.8A, 22 mOhm, shielded 4.2x4.2x2.0 — BQ25883 boost'})
add('L_3u3', lib='Device:L', value='3.3uH', footprint='robot:L_Bourns_SRP5030T',
    fields={'Description': 'Power inductor 3.3uH 20%, Isat 8A, Irms 5A, 38 mOhm, shielded 5.7x5.2 — TPS62933 at 1.2 MHz'})

# ------------------------------------------------------------------ semiconductors / ICs
add('U_BQ25883', lib='robot:BQ25883RGER', value='BQ25883RGER',
    footprint='robot:Texas_RGE0024H_VQFN-24-1EP_4x4mm_P0.5mm_EP2.7x2.7mm_ThermalVias', fields={})
add('U_LM66200', lib='robot:LM66200DRLR', value='LM66200DRLR', footprint='robot:SOT-583-8', fields={})
add('U_R5460', lib='robot:R5460N212AF', value='R5460N212AF', footprint=FP['SOT236'], fields={})
add('U_TPS62933', lib='Regulator_Switching:TPS62933', value='TPS62933DRLR', footprint='robot:SOT-583-8', fields={})
add('U_ESP32', lib='RF_Module:ESP32-S3-WROOM-1', value='ESP32-S3-WROOM-1-N16R8', footprint='robot:ESP32-S3-WROOM-1', fields={})
add('U_TCA9535', lib='Interface_Expansion:TCA9535PWR', value='TCA9535PWR', footprint='robot:TSSOP-24_4.4x7.8mm_P0.65mm', fields={})
add('U_TB6612', lib='Driver_Motor:TB6612FNG', value='TB6612FNG', footprint='robot:SSOP-24_5.3x8.2mm_P0.65mm', fields={})
add('U_LSM6DSO', lib='robot:LSM6DSOXTR', value='LSM6DSOXTR', footprint='robot:LGA-14_3x2.5mm_P0.5mm_LayoutBorder3x4y', fields={})
add('U_MAX98357A', lib='Audio:MAX98357A', value='MAX98357AETE+T', footprint='robot:TQFN-16-1EP_3x3mm_P0.5mm_EP1.23x1.23mm', fields={})
add('U_TCRT5000', lib='robot:TCRT5000L', value='TCRT5000L', footprint='robot:Vishay_TCRT5000', fields={})
add('U_USBLC6', lib='Power_Protection:USBLC6-2SC6', value='USBLC6-2SC6', footprint=FP['SOT236'], fields={})
add('D_TVS_5V', lib='Diode:SMF5V0A', value='SMF5.0A', footprint='Diode_SMD:D_SMF',
    fields={'Description': 'TVS unidirectional 5.0V standoff (VBR 6.40-7.07V) 200W SMF'})
add('Q_N_SOT23', lib='Transistor_FET:AO3400A', value='AO3400A', footprint=FP['SOT23'],
    fields={'Description': 'N-MOSFET 30V 5.7A, VGS ±12V, 26 mOhm@4.5V, SOT-23'})
add('Q_2N7002', lib='Transistor_FET:2N7002', value='2N7002LT1G', footprint=FP['SOT23'],
    fields={'Description': 'N-MOSFET 60V 115mA SOT-23'})
add('Q_P_SOT23', lib='Transistor_FET:AO3401A', value='AO3401A', footprint=FP['SOT23'],
    fields={'Description': 'P-MOSFET -30V -4A, VGS ±12V, 60 mOhm@-4.5V, SOT-23'})
add('F_5A', lib='Device:Fuse', value='5A fast', footprint='Fuse:Fuse_1206_3216Metric',
    fields={'Description': 'SMD fuse 5A fast-acting 1206, 32V, 50A breaking'})
add('SW_PUSH', lib='Switch:SW_Push', value='SW_Push', footprint='robot:SW_SPST_PTS810',
    fields={'Description': 'Tactile switch SMD 4.2x3.2 mm, 2.6 N'})
add('SW_SLIDE', lib='Switch:SW_SPDT', value='PWR', footprint='robot:SW_SPDT_PCM12',
    fields={'Description': 'Slide switch SPDT SMD; shorts PWR_EN to GND (OFF), contacts see <= 1.6 V'})
add('J_USBC', lib='Connector:USB_C_Receptacle_USB2.0_16P', value='USB-C', footprint='robot:USB_C_Receptacle_HRO_TYPE-C-31-M-12_GCT_USB4105',
    fields={'Description': 'USB-C receptacle USB 2.0, 16P, top mount, horizontal (HRO TYPE-C-31-M-12 / GCT USB4105-GF-A)'})
add('J_MOTOR', lib='Connector_Generic_MountingPin:Conn_01x06_MountingPin', value='MOTOR+ENC', footprint='Connector_JST:JST_PH_S6B-PH-SM4-TB_1x06-1MP_P2.00mm_Horizontal',
    fields={'Description': 'JST PH 6-pin SMD side entry (bottom side, under the pack) — N20 motor with Hall encoder'})
add('J_SPK', lib='Connector_Generic:Conn_01x02', value='SPEAKER', footprint='Connector_JST:JST_PH_B2B-PH-K_1x02_P2.00mm_Vertical',
    fields={'Description': 'JST PH 2-pin top entry — 4 ohm 3 W speaker'})
add('J_NTC', lib='Connector_Generic:Conn_01x02', value='NTC', footprint='Connector_JST:JST_PH_B2B-PH-K_1x02_P2.00mm_Vertical',
    fields={'Description': 'JST PH 2-pin — 10k NTC (103AT) taped to the cells'})
add('J_BAT', lib='Connector_Generic:Conn_01x03', value='BATTERY 2S', footprint='Connector_JST:JST_VH_B3P-VH_1x03_P3.96mm_Vertical',
    fields={'Description': 'JST VH 3-pin 3.96 mm, 10 A — 2S pack: 1 B-, 2 BM, 3 B+'})
add('J_HEAD', lib='Connector_Generic_MountingPin:Conn_01x20_MountingPin', value='HEAD',
    footprint='robot:JST_SH_SM20B-SRSS-TB_1x20-1MP_P1.00mm_Horizontal', fields={'Description': 'JST SH 20-pin SMD — cable to head board'})
add('J_DBG', lib='Connector_Generic:Conn_01x04', value='UART', footprint='Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical',
    fields={'Description': 'Debug UART header 1x4 2.54 mm (not fitted)'})
add('TP', in_bom=False, lib='Connector:TestPoint', value='TP', footprint='TestPoint:TestPoint_Pad_D1.5mm', fields={'Description': 'Test point pad 1.5 mm'})
add('TP_DOCK', in_bom=False, lib='Connector:TestPoint', value='DOCK', footprint='TestPoint:TestPoint_Pad_4.0x4.0mm',
    fields={'Description': 'Pogo-pin target pad 4x4 mm (bottom side)'})
add('MH', in_bom=False, lib='Mechanical:MountingHole_Pad', value='M3', footprint='MountingHole:MountingHole_3.2mm_M3_Pad_Via',
    fields={'Description': 'Mounting hole M3, plated, to GND'})
add('FID', in_bom=False, lib='Mechanical:Fiducial', value='FID', footprint='Fiducial:Fiducial_1mm_Mask2mm', fields={'Description': 'Fiducial mark'})
# ------------------------------------------------------------------ head board
add('U_VL53L1X', lib='Sensor_Distance:VL53L1CXV0FY1', value='VL53L1CXV0FY/1', footprint='robot:ST_VL53L1x', fields={})
add('U_ICS43434', lib='Sensor_Audio:ICS-43434', value='ICS-43434', footprint='robot:InvenSense_ICS-43434-6_3.5x2.65mm', fields={})
add('U_QT1010', lib='Sensor_Touch:AT42QT1010-TSHR', value='AT42QT1010-TSHR', footprint=FP['SOT236'], fields={})
add('J_LCD', lib='Connector_Generic:Conn_01x08', value='LCD ST7789', footprint='Connector_PinSocket_2.54mm:PinSocket_1x08_P2.54mm_Vertical',
    fields={'Description': 'Female header 1x8 2.54 mm — 2.0" ST7789 240x320 SPI module (GND VCC SCL SDA RES DC CS BLK)'})
add('J_TOUCHPAD', in_bom=False, lib='Connector:TestPoint', value='TOUCH', footprint='TestPoint:TestPoint_Pad_3.0x3.0mm',
    fields={'Description': 'Pad for the touch electrode wire (copper tape on the head)'})
add('MH_M25', in_bom=False, lib='Mechanical:MountingHole', value='M2.5', footprint='MountingHole:MountingHole_2.7mm_M2.5', fields={'Description': 'Mounting hole M2.5'})

# ================================================================== Rev B (Raspberry Pi 5 edition)
FP.update(SOT235='Package_TO_SOT_SMD:SOT-23-5', NEXFET='Package_SON:VSON-8_3.3x3.3mm_P0.65mm_NexFET')
for k, v in {'R_8k2': '8.2k', 'R_182k': '182k', 'R_24k': '24k'}.items():
    _r(k, v)
_c('C_10u_25V_0805', '10uF', '25V', '0805', diel='X5R')
_c('C_47u_10V', '47uF', '10V', '1206', diel='X5R')
_c('C_33p', '33pF', '50V', '0402', diel='C0G')
add('L_2u2', lib='Device:L', value='2.2uH', footprint='Inductor_SMD:L_Sunlord_MWSA0605S',
    fields={'Description': 'Power inductor 2.2uH 20%, Isat 11A, Irms 9A, 12.5 mOhm, shielded 7.0x6.6x5.0 mm'})
add('U_BQ25798', lib='Battery_Management:BQ25798', value='BQ25798RQMR',
    footprint='robot:Texas_RQM0029A_VQFN-29_4x4mm_P0.4mm',
    fields={'Description': 'I2C 1-4 cell 5 A buck-boost charger, dual input selector, NVDC power path, 16-bit ADC, VQFN-HR-29'})
add('U_TPS566238', lib='robot:TPS566238PRQFR', value='TPS566238PRQFR',
    footprint='robot:Texas_RQF0009A_VQFN-HR-9_1.5x2mm_P0.5mm', fields={})
add('U_LVC1G125', lib='74xGxx:74LVC1G125', value='SN74LVC1G125DBVR', footprint=FP['SOT235'],
    fields={'Description': 'Single bus buffer, 3-state, active-low OE, Ioff (partial power-down), 1.65-5.5 V, SOT-23-5'})
add('U_VL53L4CD', lib='robot:VL53L4CDV0DH1', value='VL53L4CDV0DH/1', footprint='robot:ST_VL53L4CD', fields={})
add('Q_ACFET', lib='robot:CSD17578Q3A', value='CSD17578Q3A', footprint=FP['NEXFET'], fields={})
add('Q_PROT', lib='robot:CSD17579Q3A', value='CSD17579Q3A', footprint=FP['NEXFET'], fields={})
add('D_TVS_6V', lib='Diode:SMF6V0A', value='SMF6.0A', footprint='Diode_SMD:D_SMF',
    fields={'Description': 'TVS unidirectional 6.0V standoff (VBR 6.67-7.37V, Vc 10.3V) 200W SMF — Pi 5 V rail'})
add('D_TVS_12V', lib='Diode:SMF12A', value='SMF12A', footprint='Diode_SMD:D_SMF',
    fields={'Description': 'TVS unidirectional 12V standoff (VBR 13.3-14.7V, Vc 19.9V) 200W SMF — USB-C VBUS'})
add('D_TVS_15V', lib='Diode:SMF15A', value='SMF15A', footprint='Diode_SMD:D_SMF',
    fields={'Description': 'TVS unidirectional 15V standoff (VBR 16.7-18.5V, Vc 24.4V) 200W SMF — 12 V dock input'})
add('D_ZENER_10V', lib='Device:D_Zener', value='BZT52C10', footprint='Diode_SMD:D_SOD-123',
    fields={'Description': 'Zener diode 10V 500mW SOD-123 — P-MOSFET gate clamp'})
add('F_10A', lib='Device:Fuse', value='10A very fast', footprint='robot:Fuse_Littelfuse-NANO2-451_453',
    fields={'Description': 'SMD fuse NANO2 10A very fast-acting, 125V, 5.6 mOhm, 2410 (6.1x2.69 mm)'})
add('F_PTC', lib='Device:Polyfuse', value='3A hold', footprint='robot:Fuse_1812_4532Metric',
    fields={'Description': 'PTC resettable fuse 1812, Ihold 3A, Itrip 6A, 16V'})
add('J_PI', lib='Connector_Generic:Conn_02x06_Odd_Even', value='PI GPIO 1-12', footprint='Connector_IDC:IDC-Header_2x06_P2.54mm_Vertical',
    fields={'Description': 'Box header 2x6 2.54 mm, shrouded, vertical — IDC ribbon to Raspberry Pi 5 header pins 1-12'})
add('J_DOCK', lib='Connector_Generic:Conn_01x02', value='DOCK 12V', footprint='Connector_JST:JST_XH_B2B-XH-A_1x02_P2.50mm_Vertical',
    fields={'Description': 'JST XH 2-pin vertical, 3 A — wires from the dock contact plate (1 = +12 V, 2 = GND)'})
add('J_PLATE', lib='Connector_Generic:Conn_01x02', value='TO ROBOT', footprint='Connector_JST:JST_XH_B2B-XH-A_1x02_P2.50mm_Vertical',
    fields={'Description': 'JST XH 2-pin vertical, 3 A — contact plate to the robot main board (J_DOCK)'})
add('J_SERVO', lib='Connector_Generic:Conn_01x03', value='SERVO', footprint='Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical',
    fields={'Description': 'Pin header 1x3 2.54 mm — hobby servo (1 GND, 2 +5V, 3 signal)'})
add('J_DCJACK', lib='Connector:Barrel_Jack_Switch', value='12V IN', footprint='robot:DC_Jack_XKB_DC-005-5A-2.0_Horizontal',
    fields={'Description': 'DC jack 5.5x2.1 mm (2.0 mm pin), right angle THT, 5 A 24 V'})
add('POGO', lib='Connector_Generic:Conn_01x01', value='POGO', footprint='robot:Pogo_YTC1P-8020_D2.0mm',
    fields={'Description': 'Spring-loaded pogo pin, SMD, D2.0 mm, 10 mm long, working height 9 mm, 1.5 A max, contact resistance ≤ 100 mΩ (datasheet)'})
add('MB_TAB', in_bom=False, lib='Mechanical:MountingHole', value='TAB', footprint='robot:MouseBite_Tab_5x3mm',
    fields={'Description': 'Break-away tab (mouse bites) between the dock board and the robot contact plate'})
add('TP_PLATE', in_bom=False, lib='Connector:TestPoint', value='CONTACT', footprint='robot:ContactPad_8x12mm',
    fields={'Description': 'Contact pad 8x12 mm, ENIG, no solder paste — pogo-pin target'})
add('MH_M2', in_bom=False, lib='Mechanical:MountingHole', value='M2', footprint='MountingHole:MountingHole_2.2mm_M2',
    fields={'Description': 'Mounting hole M2 (camera module)'})
add('MH_M25_PAD', in_bom=False, lib='Mechanical:MountingHole_Pad', value='M2.5', footprint='MountingHole:MountingHole_2.7mm_M2.5_Pad_Via',
    fields={'Description': 'Mounting hole M2.5, plated, to GND (Raspberry Pi standoff)'})
add('MH_M3', in_bom=False, lib='Mechanical:MountingHole', value='M3', footprint='MountingHole:MountingHole_3.2mm_M3',
    fields={'Description': 'Mounting hole M3, not plated'})

SRC_B = {
    'R_8k2': src('0402WGF8201TCE', 'UNI-ROYAL', 'C25924', note='JLC Basic'),
    'R_182k': src('RC0402FR-07182KL', 'Yageo', 'C327365', '603-RC0402FR-07182KL', '311-182KLRCT-ND',
                  'TPS566238 feedback: 0.1% option RT0402BRD07182KL (C723556)'),
    'R_24k': src('RC0402FR-0724KL', 'Yageo', 'C138026', '603-RC0402FR-0724KL', '311-24.0KLRCT-ND'),
    'C_10u_25V_0805': src('CL21A106KAYNNNE', 'Samsung', 'C15850', '187-CL21A106KAYNNNE', '1276-6455-1-ND', 'JLC Basic'),
    'C_47u_10V': src('CL31A476MPHNNNE', 'Samsung', 'C96123', '', '', 'JLC Basic; alt. Murata GRM31CR61A476ME15L (C94034)'),
    'C_33p': src('CL05C330JB5NNNC', 'Samsung', 'C70465', '187-CL05C330JB5NNNC', '1276-1009-1-ND'),
    'L_2u2': src('MWSA0605S-2R2MT', 'Sunlord', 'C408463', note='Alt. TAI-TECH TMPC0605H-2R2MG-D (C357209), same land pattern class'),
    'U_BQ25798': src('BQ25798RQMR', 'Texas Instruments', 'C2876593', '595-BQ25798RQMR', ''),
    'U_TPS566238': src('TPS566238PRQFR', 'Texas Instruments', 'C2876603', '595-TPS566238PRQFR', ''),
    'U_LVC1G125': src('SN74LVC1G125DBVR', 'Texas Instruments', 'C23654', '595-SN74LVC1G125DBVR', '296-11603-1-ND'),
    'U_VL53L4CD': src('VL53L4CDV0DH/1', 'STMicroelectronics', 'C3178291', '511-VL53L4CDV0DH/1', ''),
    'Q_ACFET': src('CSD17578Q3A', 'Texas Instruments', 'C205986', '595-CSD17578Q3A', ''),
    'Q_PROT': src('CSD17579Q3A', 'Texas Instruments', 'C97376', '595-CSD17579Q3A', ''),
    'D_TVS_6V': src('SMF6.0A', 'Littelfuse', 'C123790', '576-SMF6.0A', ''),
    'D_TVS_12V': src('SMF12A', 'Littelfuse', 'C123800', '576-SMF12A', ''),
    'D_TVS_15V': src('SMF15A', 'Littelfuse', 'C123802', '576-SMF15A', ''),
    'D_ZENER_10V': src('BZT52C10', 'Jiangsu Changjing (CJ)', 'C173431', note='Western: Diodes BZT52C10-7-F'),
    'F_10A': src('0451010.MRL', 'Littelfuse', 'C44479', '576-0451010.MRL', 'F2350CT-ND'),
    'F_PTC': src('BSMD1812-300-16V', 'BHFUSE', 'C883162', note='Western: Littelfuse 1812L300/16DR'),
    'J_PI': src('2.54-2*6P box header', 'BOOMELE', 'C9136', note='Any 2x6 2.54 mm shrouded box header fits'),
    'J_DOCK': src('B2B-XH-A(LF)(SN)', 'JST', 'C158012', '306-B2B-XH-ALFSN', '455-2247-ND'),
    'J_PLATE': src('B2B-XH-A(LF)(SN)', 'JST', 'C158012', '306-B2B-XH-ALFSN', '455-2247-ND'),
    'J_SERVO': src('2.54-1*3P header', 'BOOMELE', 'C49257', note='Not fitted until a tilt servo is added'),
    'J_DCJACK': src('DC-005-5A-2.0', 'XKB Connection', 'C381116'),
    'POGO': src('YTC1P-8020-01', 'YIYUAN', 'C5221286'),
}

# ------------------------------------------------------------------ purchasing (verified 2026-10-24)
SRC = {
    # --- ICs and semiconductors
    'U_ESP32': src('ESP32-S3-WROOM-1-N16R8', 'Espressif', 'C2913202', '356-ESP32S3WRM1N16R8', ''),
    'U_TB6612': src('TB6612FNG,C,8,EL', 'Toshiba', 'C141517', '757-TB6612FNGC8EL', 'TB6612FNGC8ELCT-ND'),
    'U_LSM6DSO': src('LSM6DSOXTR', 'STMicroelectronics', 'C481766', '511-LSM6DSOXTR', '497-18367-1-ND'),
    'U_MAX98357A': src('MAX98357AETE+T', 'Analog Devices', 'C910544', '700-MAX98357AETE+T', 'MAX98357AETE+TCT-ND',
                       'In production; ADI recommends MAX98365 for new designs'),
    'U_TCA9535': src('TCA9535PWR', 'Texas Instruments', 'C130204', '595-TCA9535PWR', '296-25129-1-ND'),
    'U_TCRT5000': src('TCRT5000L', 'Vishay', 'C24085', '782-TCRT5000L', '751-1034-5-ND'),
    'Q_N_SOT23': src('AO3400A', 'Alpha & Omega', 'C20917', '', '785-1000-1-ND', 'JLC Basic'),
    'Q_2N7002': src('2N7002LT1G', 'onsemi', 'C16338', '863-2N7002LT1G', '2N7002LT1GOSCT-ND'),
    'Q_P_SOT23': src('AO3401A', 'Alpha & Omega', 'C15127', '', '785-1001-1-ND', 'JLC Basic'),
    'U_VL53L1X': src('VL53L1CXV0FY/1', 'STMicroelectronics', 'C190004', '511-VL53L1CXV0FY/1', '497-17764-1-ND'),
    'U_ICS43434': src('ICS-43434', 'TDK InvenSense', 'C5656610', '', '1428-1066-1-ND',
                      'EOL at TDK; sufficient stock. T5848 is NOT compatible (8 pads)'),
    'U_QT1010': src('AT42QT1010-TSHR', 'Microchip', 'C74512', '556-AT42QT1010-TSHR', 'AT42QT1010-TSHRCT-ND'),
    'U_BQ25883': src('BQ25883RGER', 'Texas Instruments', 'C544362', '595-BQ25883RGER', '296-BQ25883RGERCT-ND'),
    'U_LM66200': src('LM66200DRLR', 'Texas Instruments', 'C3235556', '595-LM66200DRLR', '296-LM66200DRLRCT-ND'),
    'U_R5460': src('R5460N212AF-TR-FE', 'Nisshinbo (Ricoh)', 'C259717', '848-R5460N212AF-TR', ''),
    'U_TPS62933': src('TPS62933DRLR', 'Texas Instruments', 'C3200405', '595-TPS62933DRLR', '296-TPS62933DRLRCT-ND'),
    'U_USBLC6': src('USBLC6-2SC6', 'STMicroelectronics', 'C7519', '511-USBLC6-2SC6', '497-5235-1-ND'),
    'D_TVS_5V': src('SMF5.0A', 'Littelfuse', 'C151296', '576-SMF5.0A', ''),
    # --- power passives
    'L_1u0': src('PA4332.102NLT', 'Pulse Electronics', 'C2453566', '673-PA4332102NLT', '553-3287-1-ND'),
    'L_3u3': src('SRP5030T-3R3M', 'Bourns', 'C189931', '652-SRP5030T-3R3M', 'SRP5030T-3R3MCT-ND'),
    'F_5A': src('0466005.NRHF', 'Littelfuse', 'C57525', '576-0466005.NRHF', 'F6019CT-ND'),
    'FB_220R': src('BLM18PG221SN1D', 'Murata', 'C80165', '81-BLM18PG221SN1D', '490-5221-1-ND'),
    'LED_G': src('LTST-C191KGKT', 'Lite-On', 'C125098', '859-LTST-C191KGKT', '160-1446-1-ND'),
    'LED_O': src('LTST-C191KFKT', 'Lite-On', 'C160478', '859-LTST-C191KFKT', '160-1445-1-ND'),
    # --- connectors and mechanical
    'J_USBC': dict(src('TYPE-C-31-M-12', 'Korean Hroparts Elec', 'C165948', '', '',
                       'Approved alternative on the same footprint: GCT USB4105-GF-A (Mouser 640-USB4105-GF-A, DigiKey 2073-USB4105-GF-ACT-ND)'),
                   **{'Alt MPN': 'USB4105-GF-A (GCT)', 'Alt Mouser': '640-USB4105-GF-A', 'Alt DigiKey': '2073-USB4105-GF-ACT-ND'}),
    'J_MOTOR': src('S6B-PH-SM4-TB(LF)(SN)', 'JST', 'C265405'),
    'J_SPK': src('B2B-PH-K-S(LF)(SN)', 'JST', 'C131337', '306-B2BPHKSLFSN', '455-1704-ND',
                 'Vertical (top entry) since the PCB phase: there was no room for the plug on the side-entry version'),
    'J_NTC': src('B2B-PH-K-S(LF)(SN)', 'JST', 'C131337', '306-B2BPHKSLFSN', '455-1704-ND',
                 'Vertical (top entry) since the PCB phase'),
    'J_BAT': src('B3P-VH(LF)(SN)', 'JST', 'C160316', '306-B3P-VHLFSN', ''),
    'J_HEAD': src('SM20B-SRSS-TB(LF)(SN)', 'JST', 'C160415', '306-SM20BSRSSTBLFSN', '455-SM20B-SRSS-TBCT-ND'),
    'J_LCD': src('75915-308LF', 'Amphenol FCI', 'C3322318', '649-75915-308LF', '609-3559-ND', 'LCSC 151 pcs.'),
    'J_DBG': src('22-28-4040', 'Molex', 'C587039', '538-22-28-4040', ''),
    'SW_PUSH': src('PTS810SJK250SMTRLFS', 'C&K', 'C221896', '611-PTS810SJK250SMTR', 'CKN10503CT-ND'),
    'SW_SLIDE': src('PCM12SMTR', 'C&K', 'C221841', '611-PCM12SMTR', '401-2016-1-ND'),
    # --- resistors
    'R_0': src('RC0402JR-070RL', 'Yageo', 'C60485', '603-RC0402JR-070RL', '311-0.0JRCT-ND', 'JLC Basic alt C17168'),
    'R_33': src('RC0402FR-0733RL', 'Yageo', 'C138002', '603-RC0402FR-0733RL', '311-33.0LRCT-ND'),
    'R_100': src('RC0402FR-07100RL', 'Yageo', 'C106232', '603-RC0402FR-07100RL', '311-100LRCT-ND', 'JLC Basic alt C25076'),
    'R_1k': src('RC0402FR-071KL', 'Yageo', 'C106235', '603-RC0402FR-071KL', '311-1.00KLRCT-ND', 'JLC Basic alt C11702'),
    'R_2k2': src('RC0402FR-072K2L', 'Yageo', 'C114762', '603-RC0402FR-072K2L', '311-2.20KLRCT-ND', 'JLC Basic alt C25879'),
    'R_4k7': src('RC0402FR-074K7L', 'Yageo', 'C105871', '603-RC0402FR-074K7L', '', 'JLC Basic alt C25900'),
    'R_5k1': src('RC0402FR-075K1L', 'Yageo', 'C105872', '603-RC0402FR-075K1L', '311-5.10KLRCT-ND', 'JLC Basic alt C25905'),
    'R_5k23': src('CRCW04025K23FKED', 'Vishay', 'C2076550', '71-CRCW0402-5.23K-E3', '541-5.23KLCT-ND'),
    'R_10k': src('RC0402FR-0710KL', 'Yageo', 'C60490', '603-RC0402FR-0710KL', '311-10.0KLRCT-ND'),
    'R_23k2': src('CRCW040223K2FKED', 'Vishay', 'C2076557', '71-CRCW0402-23.2K-E3', '541-23.2KLCT-ND'),
    'R_30k1': src('ERJ-2RKF3012X', 'Panasonic', 'C2076806', '667-ERJ-2RKF3012X', 'P30.1KLCT-ND'),
    'R_31k6': src('CRCW040231K6FKED', 'Vishay', 'C482148', '71-CRCW0402-31.6K-E3', '541-31.6KLCT-ND'),
    'R_52k3': src('ERJ-2RKF5232X', 'Panasonic', 'C416557', '667-ERJ-2RKF5232X', 'P52.3KLCT-ND'),
    'R_100k': src('RC0402FR-07100KL', 'Yageo', 'C60491', '603-RC0402FR-07100KL', '311-100KLRCT-ND', 'JLC Basic alt C25741'),
    'R_102k': src('ERJ-2RKF1023X', 'Panasonic', 'C416459', '667-ERJ-2RKF1023X', ''),
    'R_200k': src('RC0402FR-07200KL', 'Yageo', 'C114763', '603-RC0402FR-07200KL', '311-200KLRCT-ND', 'JLC Basic alt C25764'),
    'R_1M': src('RC0402FR-071ML', 'Yageo', 'C138033', '603-RC0402FR-071ML', '311-1.00MLRCT-ND', 'JLC Basic alt C26083'),
    'R_330': src('RC0402FR-07330RL', 'Yageo', 'C105875', '603-RC0402FR-07330RL', ''),
    'R_86k6': src('RC0402FR-0786K6L', 'Yageo', 'C477807', '603-RC0402FR-0786K6L', ''),
    'R_180_0805': src('RC0805FR-07180RL', 'Yageo', 'C137585', '603-RC0805FR-07180RL', '311-180CRCT-ND'),
    'R_1R0_0805': src('RC0805FR-071RL', 'Yageo', 'C131397', '603-RC0805FR-071RL', '311-1.00CRTR-ND'),
    # --- capacitors
    'C_100n': src('CL05B104KB54PNC', 'Samsung', 'C307331', '187-CL05B104KB54PNC', '1276-CL05B104KB54PNCCT-ND', 'JLC Basic'),
    'C_1n': src('CL05B102KB5NNNC', 'Samsung', 'C14442', '187-CL05B102KB5NNNC', '1276-1032-1-ND'),
    'C_2n2': src('CL05B222KB5NNNC', 'Samsung', 'C84703', '187-CL05B222KB5NNNC', '1276-1054-1-ND'),
    'C_8n2': src('CC0402KRX7R9BB822', 'Yageo', 'C107032', '603-CC402KRX7R9BB822', '311-3817-1-ND'),
    'C_33n': src('CL05B333KB5VPNC', 'Samsung', 'C472437', '187-CL05B333KB5VPNC', ''),
    'C_47n': src('CL05B473KA5NNNC', 'Samsung', 'C318631', '187-CL05B473KA5NNNC', ''),
    'C_1u': src('CL05A105KA5NQNC', 'Samsung', 'C52923', '187-CL05A105KA5NQNC', '1276-1445-1-ND', 'JLC Basic'),
    'C_1u_25V': src('CC0603KRX5R8BB105', 'Yageo', 'C14664', '603-CC603KRX5R8BB105', '311-1445-1-ND'),
    'C_4u7': src('CL10A475KO8NNNC', 'Samsung', 'C19666', '', '1276-1784-1-ND', 'JLC Basic'),
    'C_10u_10V': src('CC0603KRX5R6BB106', 'Yageo', 'C326057', '603-CC603KRX5R6BB106', '', 'JLC Basic alt C19702'),
    'C_22u_10V': src('LMK212BJ226MG-T', 'Taiyo Yuden', 'C92814', '963-LMK212BJ226MG-T', '587-1958-1-ND'),
    'C_22u_25V': src('CL31A226KAHNNNE', 'Samsung', 'C12891', '', '1276-3047-6-ND',
                     'JLC Basic; Western sourcing: Yageo CC1206MKX5R8BB226 (Mouser/DigiKey)'),
    'C_100u': src('EEE-FTH101XAP', 'Panasonic', 'C165974', '667-EEE-FTH101XAP', 'PCE5024CT-ND'),
    'C_10u_25V': src('CL31A106KAHNNNE', 'Samsung', 'C9807', '187-CL31A106KAHNNNE', ''),
}
SRC.update(SRC_B)
for k, d in SRC.items():
    P[k].setdefault('fields', {}).update({kk: vv for kk, vv in d.items() if vv})
