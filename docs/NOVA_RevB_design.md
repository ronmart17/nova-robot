# NOVA — Rev B (Raspberry Pi 5 edition): design, layout and mechanics

Date: 2026-10-28 · KiCad 10.0.7 · ronmart · Caril Ronnie Martínez Vera

Rev B is derived from Rev A and adds the Raspberry Pi 5 brain, a 12 V charging dock and a full 3D-printed enclosure.
Three KiCad 10 projects: `nova-main` (4 layers, 136 × 136 mm), `nova-head` (2 layers, 76 × 74.9 mm) and `nova-dock`
(2 layers, dock board 58 × 34 mm + break-away robot contact plate 42 × 18 mm).

## 1. Architecture (what changed from Rev A)

| Block | Rev B | Why |
|---|---|---|
| Charger | TI **BQ25798** buck-boost NVDC charger, 2S, I2C 0x6B; two inputs: USB-C (VAC1) and 12 V dock (VAC2), each behind a back-to-back N-FET pair (CSD17578Q3A) driven by ACDRV1/2 | Two sources with automatic selection, 12 V dock charging, ideal for a robot that docks itself |
| Pi 5 rail | TI **TPS566238** 6 A D-CAP3 buck, 5.15 V, 2.2 µH, 3 × 47 µF; enable held by the ESP32 (PI_PWR_OFF), power-good to the expander | Pi 5 needs 5.0–5.25 V at up to 5 A |
| Logic rail | TPS62933 3.3 V (unchanged topology) | — |
| Battery | 2S2P 18650 (44 Wh), JST VH, NANO2 10 A fuse, R5460N212AF protector with 2 × CSD17579Q3A (common drain) | Higher current for the Pi 5 and motors |
| Pi link | 2 × 6 IDC (J701) to the Pi GPIO 1–12: UART (ESP32 UART0 ↔ Pi UART0, so the Pi can flash the ESP32 through the ROM bootloader) with a 74LVC1G125 isolating buffer, shutdown request (GPIO3), remote reset/boot of the ESP32 (GPIO17/18), PI_ALIVE from the Pi 3.3 V rail | ESP32 keeps the body alive and can power-cycle the Pi; the Pi can re-flash the ESP32 |
| USB | USB-C J201 is the charging input only (its D+/D− go to the BQ25798 for BC1.2 detection); the ESP32's native USB is on three test pads under the module | The first Rev B draft shared D+/D− between the charger's BC1.2 detection and the ESP32 (detection pulses on a live USB link) and ran the pair ~100 mm across the board; the Pi now flashes the ESP32 over UART0 |
| Pi power | USB-C receptacle J702 on the main board (Rp 10 kΩ = 3 A source) → short right-angle USB-C cable → Pi 5 | Pi 5 runs at full power with `PSU_MAX_CURRENT=5000` and `usb_max_current_enable=1` |
| Cliff sensors | 2 × VL53L4CD (bottom side, at the front corners) | Distance instead of reflectance: works on dark floors |
| Head | ST7789 2.0" display, VL53L1X ToF, AT42QT1010 touch, mounting for the Camera Module 3 (FPC to the Pi) | Camera added; microphone moved to the XVF3800 array |
| Audio | ReSpeaker XVF3800 (4 mics, AEC) on the top deck, mono speaker from its amplifier | Hear over music; far-field |
| Dock | 12 V adapter → PTC 3 A → reverse-polarity P-FET (AO3401A, VGS clamped) → SMF15A → two pogo pairs | Robot charges by reversing onto the dock |

### Changes made during the layout (and why)

| Change | Reason |
|---|---|
| Pi ↔ ESP32 link moved from UART1 to **UART0** (GPIO43/44); debug header J401 now on UART1 (GPIO4/5) | The ESP32-S3 ROM bootloader only listens on UART0 or USB: on UART1 the Pi could never have flashed the ESP32 |
| ESP32 native USB on three bottom test pads (TP401–TP403) instead of the USB-C input | The USB-C D+/D− are driven by the charger's BC1.2 detection; sharing them with a live USB link is unreliable, and the pair crossed ~100 mm of board |
| ESP32 GPIO map reassigned to the layout (table in §7) | Rear signals (motors, encoders) leave from the side of the module that faces the rear; fewer crossings at the module |
| Charge LED (D203/R211) removed, BQ25798 STAT unused | It would be hidden inside the enclosure; the charge state is read over I2C and shown on the face display |
| BQ25798 ~CE held low by R214 (expander control removed; TCA9535 P02 spare, tied to GND) | No route left between the charger and the expander; charging is still switched over I2C (EN_CHG) |
| Spare GPIO39/GPIO46 test points removed | They were > 50 mm from the module and only cost routing space |
| C501 rotated, TP201 to the bottom, Rp resistors R712/R713 level with the CC pads, SW301 0.45 mm inside the edge | Shorted/blocked fixed copper and edge clearance found by the layout checks |

## 2. Power layout (main board) — checked against the data sheets

- **BQ25798** (TI layout guide): 100 nF PMID and SYS capacitors on the IC layer right at their pins; SW1/SW2 leave the
  package through via pairs to B.Cu bands and come back up beside the inductor; PMID and SYS F.Cu corridors under the
  inductor with the bulk capacitors on them; SYS stitched to the In2 VSYS plane; BTST capacitors on the bottom under
  the IC; VBUS 100 nF at the pins with two GND vias; REGN capacitor with two GND vias; BAT capacitors with their VBAT pads
  on a dedicated pour to the fuse.
- **TPS566238** (RQF0009A): hot loop VIN → 100 nF (C304) → PGND under the IC, 3 × 10 µF in a row on the VIN bar stitched
  to In2 VSYS; SW goes straight up from pin 8 through the bootstrap capacitor's SW pad into L301; VCC, FB, EN, PG leave
  on the quiet side; FB divider pads in one row level with FB; COUT 3 × 47 µF on the +5V band with their GND on a pour
  with 6 vias.
- **+5V to the Pi**: F.Cu band ≥ 3.6 mm from L301 over the COUT stack to the two VBUS pads of J702 (2.5 A per pad),
  J702 decoupling (22 µF + 100 nF) and TVS (SMF6.0A) above the receptacle, Rp resistors on the bottom under it.
- **Battery**: B+ pour J301 → F301, VBAT pour F301 → BAT capacitors → BAT pins; B− pour J301 → Q301; common-drain bridge
  Q301/Q302; Q302 source pour with three vias to GND.
- The router's model of the NexFET drain pad now includes its four fingers (custom-pad primitives), so no via or track
  can land on them.

## 3. Mechanics (single source: `mech/dims.py`)

Robot frame: X right, Y forward, Z up, origin on the floor under the wheel axle.

- Main board 136 × 136 R30 at Z 27.5–29.1; wheel cut-outs |X| ≥ 49 for |Y| ≤ 23.5; notch at the right edge for the
  J702 plug (merged with the wheel cut-out, no thin slivers).
- N20 motors with U brackets under the board, Ø43 wheels, ball caster at Y = 50.
- 2S2P pack on the board inside a printed cage that slides over the four Pi standoffs (no straps, no extra holes).
- Pi 5 on M2.5 × 45 standoffs (25 + 20), Active Cooler; top deck on M2.5 × 20 standoffs from the Pi carries the XVF3800
  (centred at Y = −4, 3 mm clear of the head board).
- Head board vertical at Y 52–53.6, standing on the main board, two M3 angle brackets (head holes at z = 10 so that the
  nut clears the main-board screw head). Display at z = 27, Camera Module 3 above it (lens z ≈ 58), FPC through an
  18 × 2 mm slot to the Pi CAM/DISP connector, ToF beside the camera.
### Industrial design (enclosure)

The enclosure is five parts with one design language: **matte white body, graphite base, glossy black face, light
accents only where there is real light** (display, XVF3800 LED ring, dock status LED).

| Part | Material / finish | Notes |
|---|---|---|
| Upper body | PETG or ASA, matte white | 141 × 141 mm, R32.5 corners, R12 top edges, 2 mm walls; printed upside down. Bottom edge on a parting plane that rises from Z 32.5 (front) to Z 39.5 (rear); 0.6 mm shadow gap to the skirt. Four corner bosses with ribs and M3 heat-set inserts; speaker cup; forward-leaning side gills over the Pi; hexagonal speaker grille and engraved NOVA mark at the rear; engraved touch spot on the top. |
| Skirt | PETG, graphite | Z 8 up to the parting plane; 4 × 1.6 mm tucked-under lower chamfer; **fender bands** (R24.5–30.5) rise around the wheels into the white body with 1.5 mm flared lips; rear port bay (USB-C, power switch); dock opening ±34 × 18 mm; four ears under the board corners take the same M3 screws as the body. |
| Visor | 2 mm smoked acrylic (laser cut), gloss | 72 × 59 mm, R12, covers the whole flat front; glued into a 2 mm pocket with a frame behind it. Clear cut-outs for the camera lens (Ø8) and the ToF (6 × 4). The display reads through the tint (show bright content on a black background). |
| Halo | Translucent / light-diffusing PETG | Ring r 28–49 over the XVF3800 LEDs and microphones, 0.8 mm proud with chamfered edges; flange under the top skin; 48 × Ø1.2 holes on r 46.7 (four of them exactly over the microphones, which sit at (±33, ±33) mm per the XVF3800 `AEC_MIC_ARRAY_GEO`) and 48 on r 38. |
| Top cap | PETG, matte white | Ø55.6 disc inside the halo, glued onto the halo's inner flange. |

Assembly: four M3 screws from under the main board pass through the skirt ears and the board into the inserts of the
upper body (front corners M3 × 8; rear corners M3 × 10 through the dock plate bar), so one screw set holds skirt, board and body. Clearances checked in CAD against every board component, the
Pi 5, the XVF3800, the speaker, the drive and the dock (no interference).

### Printed and cut parts (files in `Mechanics_3D/printed_parts`, STEP + STL)

| File | Qty | Material | Orientation / notes | Hardware |
|---|---|---|---|---|
| `NOVA_shell_upper` | 1 | PETG/ASA white, 0.2 mm, 3 walls | top face down on a smooth PEI sheet; tree supports only inside the visor frame | 4 × M3 heat-set insert (Ø4 hole, ≤ 6 mm long) |
| `NOVA_shell_skirt` | 1 | PETG graphite | upside down (top edge on the bed) | — |
| `NOVA_halo` | 1 | translucent PETG (natural) | flange down, 100 % infill for even light | glued (CA or epoxy) |
| `NOVA_top_cap` | 1 | PETG white | flat | glued onto the halo flange |
| `NOVA_visor` | 1 | 2 mm smoked acrylic (grey 50–70 % transmission) | laser cut from the STEP outline (holes included) | glued with a thin bead of clear silicone/UV glue |
| `NOVA_battery_cage`, `NOVA_top_deck`, `NOVA_head_bracket_L/R`, `NOVA_dock_plate_bar` | 1 each | PETG | as modelled, flat face down | M2.5/M3 as noted in the part docstrings |
| `NOVA_dock_base` | 1 | PETG graphite | flat | 4 × rubber feet Ø10; 4 × M3 heat-set insert ≤ 4 mm long (PCB bosses) |
| `NOVA_dock_tower` | 1 | PETG white | on its side (flat front down) | 2 × M3 heat-set insert; 2 × M3 × 8 countersunk from below through the base |
| `NOVA_dock_tongue` | 1 | PETG graphite | top down | 4 × M3 × 10 through the tongue and the PCB into the base inserts |
| `NOVA_dock_tag_panel` | 1 | PETG graphite, 1.2 mm | flat | AprilTag sticker 50 × 50 mm (matte) |
| `NOVA_dock_lightpipe` | 1 | Ø3 clear acrylic rod, 6.4 mm long | — | press fit |

Screws for the robot: 2 × M3 × 8 (enclosure, front corners) and 2 × M3 × 10 (enclosure + dock plate bar, rear
corners), all from below into M3 heat-set inserts (Ø4 hole, insert ≤ 6 mm long); M2.5 standoffs
45 mm (25 + 20) and 20 mm for the Pi and the top deck.

### Charging dock

- The robot reverses until its rear touches the back wall; the shell's rear opening (±34 mm, 18 mm high) self-centres on
  the dock tongue (±32 mm, chamfered front): ±2 mm lateral, within the ±3.5 mm of the 8 × 12 mm pads.
- Robot side: a bar under the rear of the main board (on the two rear shell screws) holds the break-away contact plate
  face down at Z = 15.6 mm, flush with the bar, with 20° ramps in front of and behind the pads so the pogo tips are
  pressed down before they reach the pads.
- Dock side: dock PCB at Z = 5.0 mm (top 6.6), YTC1P-8020 pogo pins → 9.0 mm working height reaches the plate exactly;
  graphite tongue (top at 13 mm) with pogo guides and a Ø3 light pipe over the status LED.
- Dock body: graphite base 96 × 68 mm on four rubber feet; white tower (88 mm wide at the foot, 64 mm at the top, R16
  shoulders, flat front, curved back, 126 mm tall). The DC jack sits on the PCB tail **inside the tower foot**; the
  plug enters from the back. The tower is screwed to the base from below (2 × M3), after the PCB is in place.
- AprilTag on a graphite panel in the tower front, centred at the camera height (Z 87.1): **tag36h11 id 0**, sticker
  50 × 50 mm with a 40 × 40 mm black square → tag size for the detector = **0.040 m**. Print it matte (no gloss). The
  robot sees the tag, turns 180° and reverses (procedure and error budget: simulation report, §3 H).
- Pogo pins: 1.5 A max and ≤ 100 mΩ each (datasheet) → two pins per polarity; set the BQ25798 input current limit on
  VAC2 to **1.8 A** in firmware (at 2.5 A unequal contact resistance can put more than 1.5 A on one pin — see the
  simulation report, §3 E).

## 4. Verification

KiCad 10.0.7 (`kicad-cli`), all violations and warnings included:

| Board | ERC | Netlist vs. schematic | DRC errors / warnings | Unconnected | Schematic parity | Size |
|---|---|---|---|---|---|---|
| nova-main (4 layers) | 0 (3 documented exclusions*) | 0 mismatches, 145 nets, 201 parts | 0 / 0 | 0 | 0 | 1581 track segments, 471 vias |
| nova-head (2 layers) | 0 | 0 mismatches | 0 / 0 | 0 | 0 | 280 segments, 66 vias |
| nova-dock (2 layers) | 0 | 0 mismatches | 0 / 0 | 0 | 0 | 31 segments, 13 vias |

\* Intentional pin straps reported as "bidirectional pin on a power net": LSM6DSOX SA0 and SDx to GND (address 0x6A,
auxiliary I2C unused) and TCA9535 P02 (spare) to GND.

Design rules (main board): 0.15 mm clearance, 0.15 mm minimum track, vias 0.3 mm drill / ≥ 0.5 mm pad, 0.3 mm
copper-to-edge, 0.25 mm hole-to-hole.
Custom rule in `nova-main.kicad_dru`: 0.12 mm between pads inside the NexFET SON land pattern (TI footprint;
JLCPCB minimum 0.10 mm). The footprint-library comparison is
disabled because the silkscreen of four footprints is trimmed to the board edge and pads on purpose.

Mechanical (CadQuery, exact solids): no interference between the enclosure, the internal printed parts, the dock and
any board component, the Pi 5, the XVF3800, the speaker, the drive or the battery.


## 5. Fabrication (JLCPCB)

- Main: 4 layers, 1.6 mm, JLC04161H-7628, HASL lead-free. Head: 2 layers, 1.6 mm. Dock + plate: 2 layers, 1.6 mm,
  **ENIG** (flat, corrosion-resistant contact pads); the plate is joined by two mouse-bite tabs (MB1/MB2).
- Per board: `*_gerbers_JLCPCB.zip`, `*_BOM_JLCPCB.csv`, `*_CPL_JLCPCB.csv`, full BOM with Mouser/DigiKey codes,
  assembly drawings (top/bottom), 1:1 mechanical drawing, copper layers PDF, STEP and 3D renders.
- Check every part rotation in the JLCPCB preview before ordering (SOT-23, QFN and connectors especially).

## 6. Check with the real parts before ordering (hard to undo)

1. J702: the right-angle USB-C plug must fit in ≤ 11 mm from the receptacle face to the shell wall; the cable to the
   Pi 5 should be ≈ 15 cm.
2. N20 brackets, wheels and caster against the slots and cut-outs (1:1 drawing).
3. Display module: active-area position on your module (window 46 × 34 mm centred on the module).
4. Camera Module 3 standoffs 2.5 mm (lens 0.9 mm behind the shell's inner face).
5. Pogo pins: free height 10 mm, stroke 1.0 mm; contact plate pads 8 × 12 mm.
6. J701 ribbon: pin 1 ↔ pin 1 with the Pi header; depending on the IDC cable orientation a half twist may be needed.
7. ReSpeaker XVF3800: microphone positions taken from its firmware geometry (AEC_MIC_ARRAY_GEO = (±0.033, ±0.033) m);
   check them and the board outline (Ø99) against Seeed's 2D drawing; the USB-only version is assumed (the XIAO
   ESP32S3 version adds parts under the board — check the top-deck clearance).
8. Smoked visor: choose a grey acrylic with 50–70 % transmission so the display reads clearly and the internals hide.


### ESP32-S3 pin map (Rev B)

Chosen for the layout: signals that go to the rear of the board leave from the module's right column and the right
half of its bottom row; front signals leave from the top row.

| GPIO | Net | Function | GPIO | Net | Function |
|---|---|---|---|---|---|
| 0 | ESP_BOOT | boot (button, Pi via Q703) | 21 | MOT_AIN1 | TB6612 AIN1 |
| 1 | PI_PWR_OFF | Pi 5 V rail off (RTC, held in sleep) | 38 | LCD_DC | display D/C |
| 2 | CLIFF_INT | cliff ToF interrupt | 40 | LCD_BL | display backlight |
| 3 | IRQ_N | charger/expander interrupt | 41 | SERVO_PWM | servo |
| 4 / 5 | UART_TX / UART_RX | UART1, debug header J401 | 42 | LCD_CS | display CS |
| 6 | PI_PWROFF | Pi gpio-poweroff signal (in) | 43 / 44 | UART_PI_TX / RX | **UART0 ↔ Pi** (also ROM download) |
| 7 | PI_SHDN_REQ | shutdown request to the Pi | 45 | MOT_STBY | TB6612 STBY (strap: low at boot) |
| 8 / 9 | I2C_SDA / SCL | I2C bus | 46 | — | spare, not connected (strap, internal pull-down) |
| 10 | MOT_BIN1 | TB6612 BIN1 | 47 | MOT_BIN2 | TB6612 BIN2 |
| 11 / 12 | LCD_MOSI / SCLK | FSPI IO_MUX (33 Ω series) | 48 | MOT_PWMB | TB6612 PWMB |
| 13 | MOT_AIN2 | TB6612 AIN2 | 19 / 20 | ESP_USB_DM / DP | native USB on bottom pads TP401/TP402 (+ TP403 GND), development only |
| 14 | MOT_PWMA | TB6612 PWMA | 39 | — | spare, not connected |
| 15 / 16 | ENC_L_A / B | left encoder (PCNT) | 35–37 | — | octal PSRAM, do not use |
| 17 / 18 | ENC_R_A / B | right encoder (PCNT) | | | |


## 7. Firmware notes (hardware-dependent)

- BQ25798: set IINDPM per source — USB-C: the charger only sees BC1.2 on D+/D− (it cannot read the Type-C CC
  advertisement), so keep VINDPM ≈ 4.5 V and ICO enabled; VAC2 (dock) 1.8 A — charge voltage 8.4 V, service the
  watchdog; ACDRV enables both input FET pairs.
- BQ25798 ~CE is held low by R214 (charging enabled in hardware): enable/disable charging with EN_CHG over I2C.
  TCA9535 P02 is a spare tied to GND: keep it configured as an input.
- BQ25798 STAT is not connected (a charge LED would be hidden inside the enclosure): set DIS_STAT = 1 and show the
  charge state (read over I2C) on the face display; the ESP32 runs from the always-on 3.3 V rail, so this also works
  with the Pi off.
- TPS566238 enable: ESP32 drives PI_PWR_OFF low to keep the Pi on; request the Pi shutdown (GPIO3) before cutting it.
- Flashing the ESP32 from the Pi: hold GPIO0 low (Pi GPIO18 → Q703), pulse EN (Pi GPIO17 → Q702), then
  `esptool.py --chip esp32s3 -p /dev/serial0 write_flash ...` (UART0). On the bench (no Pi): a USB cable soldered
  or pogo-probed to TP401/TP402/TP403 under the ESP32 (native USB: flashing and JTAG), or a 3.3 V USB-UART on the
  Pi-link header J701 (UART0) with the BOOT/RESET buttons.
- Pi 5: `PSU_MAX_CURRENT=5000` in the EEPROM and `usb_max_current_enable=1` in config.txt.
- VL53L4CD × 2 + VL53L1X share the I2C bus: reassign addresses at boot using the XSHUT lines.
- From the simulations (`NOVA_RevB_simulations`): ESP32-S3 drive strength 1 on GPIO11/12 (display SPI ringing);
  acceleration and braking ≤ 0.4 m/s² with a jerk-limited ramp (tip-back limit 0.58 m/s²); motor PWM limited to a
  6 V average; docking: last tag fix at 0.12 m, 180° turn 134 mm from the dock wall, reverse until VAC2 is detected,
  retry otherwise.
