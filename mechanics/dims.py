"""NOVA Rev B (Raspberry Pi 5 edition) — single source of truth for the mechanical layout.

Robot frame: X to the robot's right, Y forward, Z up; origin on the floor, under the centre of the wheel axle.
KiCad local frame of the main board: (x, y_k) = (X, -Y)  (front of the robot = up on the screen = -y in KiCad).
All dimensions in mm.
"""

# ------------------------------------------------------------------ wheels, motors, caster
WHEEL_D, WHEEL_W = 43.0, 18.0            # N20 wheel (D-shaft 3 mm)
AXLE_Z = WHEEL_D / 2                     # 21.5
WHEEL_X = 59.5                           # wheel centre |X|
MOTOR_W, MOTOR_H = 12.0, 10.0            # N20 cross-section (12 wide along Y, 10 tall)
MOTOR_X = (13.0, 47.0)                   # encoder end .. gearbox face (|X|)
BRACKET_T = 1.0                          # U bracket sheet between motor and board
BRK_X = (29.5, 42.25)                    # U brackets: on the motor can and on the gearbox (|X|)
BRK_Y, BRK_SLOT = 9.65, 4.0              # bracket ears at |Y| = 9.65 (M2), 4 mm slots along Y

# ------------------------------------------------------------------ main board (chassis)
MB_T = 1.6
MB_Z0 = AXLE_Z + MOTOR_H / 2 + BRACKET_T          # board bottom = 27.5
MB_Z1 = MB_Z0 + MB_T                               # board top = 29.1
MB_W, MB_D, MB_R = 136.0, 136.0, 30.0              # rounded-square outline, corner radius
WCUT_X, WCUT_Y = 49.0, 23.5                        # wheel cut-out: |X| >= WCUT_X and |Y| <= WCUT_Y
CASTER_Y = 50.0                                    # ball caster (bottom side), on the centre line, front
CASTER_DX = 8.25                                   # caster M2 slots at X = +-8.25
CLIFF = [(-34.0, 62.0), (34.0, 62.0)]              # VL53L4CD cliff sensors (bottom side), facing down
SHELL_HOLES = [(-55.0, -55.0), (55.0, -55.0), (-55.0, 55.0), (55.0, 55.0)]   # M3, shell bosses in the four corners (from below)

# ------------------------------------------------------------------ battery (2S2P 18650, 2x2 block) on the main board
CELL_D, CELL_L = 18.6, 65.2
BAT_W, BAT_H, BAT_L = 2 * CELL_D + 1.6, 2 * CELL_D + 1.6, CELL_L + 2.6   # with nickel strips and insulation
BAT_Y0, BAT_Y1 = -30.0, -30.0 + BAT_L            # along Y (rear .. front): -30 .. 37.8
BAT_X = BAT_W / 2                                # 19.4
# the pack is held by a 3D-printed cage that slides over the four Pi standoffs (no straps, no extra holes)

# ------------------------------------------------------------------ Raspberry Pi 5, long side along Y:
# USB/Ethernet end at the REAR, HDMI/USB-C long edge on the RIGHT, GPIO header on the LEFT (pin 1 at the front end).
# Pi local frame (u, v) = official drawing (origin bottom-left, u along the 85 mm edge towards USB/Ethernet,
# v along the 56 mm edge towards the GPIO header)  ->  robot X = PI_XR - v, Y = PI_YF - u.
PI_W, PI_D, PI_T = 85.0, 56.0, 1.6
PI_XR, PI_YF = 28.0, 45.0                        # right edge (HDMI side) and front edge of the Pi in the robot frame
PI_HOLES_UV = [(3.5, 3.5), (61.5, 3.5), (3.5, 52.5), (61.5, 52.5)]
PI_PIN1_UV = (8.37, 51.23)                       # GPIO header pin 1 (inner row); pin 2 on the outer row (v + 2.54)
PI_USBC_U = 11.2                                 # USB-C power on the HDMI edge (v = 0)
PI_HDMI_U = (25.8, 39.2)
PI_STANDOFF = 45.0                               # main board top -> Pi PCB bottom (M2.5 standoffs 25 + 20)
PI_Z0 = MB_Z1 + PI_STANDOFF                      # Pi PCB bottom (74.1)
COOLER_H = 13.7                                  # Active Cooler above the Pi PCB (RP-008187 drawing)
PI_CX, PI_CY = PI_XR - PI_D / 2, PI_YF - PI_W / 2   # centre of the Pi board (0, 2.5)

def pi_xy(u, v):
    return (PI_XR - v, PI_YF - u)

# ------------------------------------------------------------------ top deck with the XVF3800 mic array (Ø100)
XVF_D = 100.0
DECK_Z0 = PI_Z0 + PI_T + 20.0                    # deck on M2.5 × 20 standoffs from the Pi (95.7)
XVF_Z0 = DECK_Z0 + 2.0                           # XVF3800 PCB bottom
XVF_CY = -4.0                                    # deck/array centre (Y): 3 mm clear of the head board (Y 52) with the Ø106 deck

# ------------------------------------------------------------------ head board (vertical, at the front)
HEAD_Y0 = 52.0                                   # rear face of the head board (Y)
HEAD_T = 1.6
HEAD_W = 76.0
HEAD_Z0, HEAD_Z1 = MB_Z1, 104.0                  # sits on the main board
HEAD_BRK = [(-32.0, 47.5), (32.0, 47.5)]         # M3 angle-bracket holes on the main board

# ------------------------------------------------------------------ shell
SHELL_GAP = 0.5                                  # shell inner face to the main board edge
SHELL_WALL = 2.0
SHELL_W, SHELL_D = MB_W + 2 * (SHELL_GAP + SHELL_WALL), MB_D + 2 * (SHELL_GAP + SHELL_WALL)   # 141 × 141
SHELL_R = MB_R + SHELL_GAP + SHELL_WALL
SHELL_Z0, SHELL_Z1 = 8.0, 106.0
TOP_T = 2.0
SPEAKER = (18.0, -66.0, 62.0)                    # 40 mm speaker on the rear wall (X, Y, Z of its centre), inside the flat part

# ------------------------------------------------------------------ head board features (front view: x, z from its bottom edge)
HEAD_HOLE = (32.0, 10.0)                         # M3 angle-bracket holes H101/H102
HEAD_LCD_ZC = 27.0                               # display module centre
HEAD_CAM_TOP, HEAD_CAM_LENS_Z = 72.4, 58.0       # Camera Module 3 top edge and lens centre
HEAD_TOF = (19.0, 58.0)

# ------------------------------------------------------------------ dock and robot contact plate
DOCK_PLATE_Y = -55.0                             # contact plate centre (under the rear of the robot)
DOCK_PLATE_Z = 15.6                              # pad face (pogo working height 9.0 above the dock PCB top)
DOCK_PCB_Z = DOCK_PLATE_Z - 9.0 - 1.6            # dock PCB bottom (5.0)
DOCK_TONGUE_H = 13.0                             # top of the pogo housing above the floor
DOCK_OPENING = (34.0, 18.0)                      # rear skirt opening of the shell: |X| <= 34, Z <= 18 (tongue ±32)
DOCK_WALL_Y = -71.5                              # front face of the dock back wall (robot rear touches it)
