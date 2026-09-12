#!/usr/bin/env python3
"""Generate am-radio.kicad_sch : 6-transistor AM superhet, NPN, 4.5 V, negative ground."""
import re, uuid, math, os
from collections import defaultdict

PROJ = "/home/gyoung/src/am_radio/am-radio"
SYSLIB = "/usr/share/kicad/symbols"
OUT = f"{PROJ}/am-radio.kicad_sch"
ROOT_UUID = "5dac0215-3810-4d8c-b2de-2cbfde845382"   # keep the original sheet uuid

# ------------------------------------------------------------------ s-expression utils
class Str(str):
    """A token that was quoted in the source."""

def parse(text):
    toks = re.findall(r'"(?:[^"\\]|\\.)*"|\(|\)|[^\s()]+', text)
    stack = [[]]
    for t in toks:
        if t == '(':
            stack.append([])
        elif t == ')':
            l = stack.pop(); stack[-1].append(l)
        else:
            stack[-1].append(Str(t[1:-1]) if t.startswith('"') else t)
    return stack[0][0]

def ser(node, ind=0):
    if not isinstance(node, list):
        return f'"{node}"' if isinstance(node, Str) else str(node)
    if all(not isinstance(c, list) for c in node):
        return "(" + " ".join(ser(c) for c in node) + ")"
    head = [c for c in node if not isinstance(c, list)]
    kids = [c for c in node if isinstance(c, list)]
    s = "(" + " ".join(ser(c) for c in head)
    for k in kids:
        s += "\n" + "\t" * (ind + 1) + ser(k, ind + 1)
    return s + "\n" + "\t" * ind + ")"

def get(l, key):
    return [x for x in l if isinstance(x, list) and x and x[0] == key]

_libcache = {}
def load_lib(path):
    if path not in _libcache:
        _libcache[path] = parse(open(path).read())
    return _libcache[path]

def lib_symbol(libname, symname):
    """Return the symbol subtree renamed to 'Lib:Name' and its pin table [(num, x, y)] in lib coords."""
    path = f"{PROJ}/audio.kicad_sym" if libname == "audio" else f"{SYSLIB}/{libname}.kicad_sym"
    tree = load_lib(path)
    sym = next(s for s in get(tree, "symbol") if s[1] == symname)
    if get(sym, "extends"):
        raise SystemExit(f"{symname} extends another symbol; use the base symbol")
    sym = parse(ser(sym))  # deep copy
    sym[1] = Str(f"{libname}:{symname}")
    pins = {}
    for sub in get(sym, "symbol"):
        for p in get(sub, "pin"):
            at = get(p, "at")[0]
            pins[str(get(p, "number")[0][1])] = (float(at[1]), float(at[2]), p[1])
    return sym, pins

# ------------------------------------------------------------------ schematic model
def U(): return str(uuid.uuid4())
def g(v): return round(v, 4)

lib_symbols = {}       # "Lib:Name" -> subtree
symbols = []           # instance dicts
wires = []             # [(x1,y1),(x2,y2)]
labels = []            # (name, x, y, rot)
noconnects = []
texts = []             # (text, x, y, size)
power_flags_nets = set()

def rot_pt(x, y, rot, mirror):
    if mirror == "x": y = -y
    if mirror == "y": x = -x
    a = math.radians(rot)
    rx = x * math.cos(a) - y * math.sin(a)
    ry = x * math.sin(a) + y * math.cos(a)
    return rx, ry

class Sym:
    def __init__(self, lib, name, ref, value, at, rot=0, mirror=None, footprint="", fields=None, ref_off=None, val_off=None, hide_value=False):
        key = f"{lib}:{name}"
        if key not in lib_symbols:
            lib_symbols[key], self._pins_lib = lib_symbol(lib, name)
            lib_symbols[key + "__pins"] = self._pins_lib
        else:
            self._pins_lib = lib_symbols[key + "__pins"]
        self.lib_id = key; self.ref = ref; self.value = value; self.at = at; self.rot = rot; self.mirror = mirror
        self.footprint = footprint; self.fields = fields or {}; self.uuid = U()
        self.ref_off = ref_off; self.val_off = val_off; self.hide_value = hide_value
        self.pins = {}
        for num, (x, y, ptype) in self._pins_lib.items():
            rx, ry = rot_pt(x, y, rot, mirror)
            self.pins[num] = (g(at[0] + rx), g(at[1] - ry))
        symbols.append(self)

    def p(self, num):
        return self.pins[str(num)]

def wire(*pts):
    for a, b in zip(pts, pts[1:]):
        if a != b:
            wires.append((a, b))

def label(name, x, y, rot=0):
    labels.append((name, x, y, rot))

def nc(pt):
    noconnects.append(pt)

def text(t, x, y, size=1.5):
    texts.append((t, x, y, size))

# helpers for the standard parts --------------------------------------------------------
FP_R = "Resistor_THT:R_Axial_DIN0204_L3.6mm_D1.6mm_P5.08mm_Horizontal"
FP_C = "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm"
FP_CP = "Capacitor_THT:CP_Radial_D5.0mm_P2.00mm"
FP_Q = "Package_TO_SOT_THT:TO-92"

def R(ref, val, at, rot=0):
    return Sym("Device", "R_US", ref, val, at, rot, footprint=FP_R)
def C(ref, val, at, rot=0):
    return Sym("Device", "C", ref, val, at, rot, footprint=FP_C)
def CP(ref, val, at, rot=0):
    return Sym("Device", "C_Polarized", ref, val, at, rot, footprint=FP_CP)
def Q(ref, at, mirror=None):
    return Sym("Transistor_BJT", "Q_NPN_EBC", ref, "2N3904", at, 0, mirror, footprint=FP_Q)
def GND(at, rot=0):
    return Sym("power", "GND", f"#PWR{len([s for s in symbols if s.ref.startswith('#PWR')])+1:02d}", "GND", at, rot)
def VBAT(at, rot=0):
    return Sym("power", "+BATT", f"#PWR{len([s for s in symbols if s.ref.startswith('#PWR')])+1:02d}", "+BATT", at, rot)
def VRF(at, rot=0):
    return Sym("audio", "V_RF", f"#PWR{len([s for s in symbols if s.ref.startswith('#PWR')])+1:02d}", "V_RF", at, rot)
def FLAG(at, rot=0):
    return Sym("power", "PWR_FLAG", f"#FLG{len([s for s in symbols if s.ref.startswith('#FLG')])+1:02d}", "PWR_FLAG", at, rot)
def IFT(ref, val, at, colour):
    return Sym("audio", "Xicon_42IF10x_IFT", ref, val, at, 0, footprint="audio:Xicon_42IF10x", fields={"Colour": colour})

# ================================================================== CIRCUIT
# ---- Antenna / tuning
L1 = Sym("audio", "Ferrite_Rod_Antenna_Coil", "L1", "AM loopstick", (45.72, 93.98), footprint="audio:Ferrite_Rod_Antenna_Coil")
VC1 = Sym("audio", "Polyvaricon_2G_AM", "VC1", "CBM-223P", (22.86, 104.14), footprint="audio:Polyvaricon_CBM-223P_Wired")
# antenna gang A -> L1.1 ; L1.2 -> GND
wire(VC1.p(1), (25.4, 78.74), (38.1, 78.74), L1.p(1))
wire(L1.p(2), (38.1, 106.68)); GND((38.1, 106.68))
wire(VC1.p(2), (22.86, 111.76)); GND((22.86, 111.76))

# ---- Converter Q1 (mixer + local oscillator)
Q1 = Q("Q1", (63.5, 88.9))
wire(L1.p(3), Q1.p(2))                                   # secondary top -> base
R1 = R("R1", "100k", (48.26, 104.14), 90); R2 = R("R2", "39k", (53.34, 109.22)); C2 = C("C2", "47n", (58.42, 109.22))
wire(L1.p(4), (53.34, 104.14), R2.p(1))                  # secondary bottom -> bias node
wire(R1.p(2), (53.34, 104.14)); VRF(R1.p(1), 180)
wire((53.34, 104.14), (58.42, 104.14), C2.p(1))
wire(R2.p(2), (53.34, 115.57)); GND((53.34, 115.57))
wire(C2.p(2), (58.42, 115.57)); GND((58.42, 115.57))
R3 = R("R3", "1k", (66.04, 104.14)); C1 = C("C1", "10n", (72.39, 93.98), 90)
wire(Q1.p(1), R3.p(1))                                   # emitter -> R3
wire(R3.p(2), (66.04, 110.49)); GND((66.04, 110.49))
wire(Q1.p(1), C1.p(1))                                   # emitter -> C1 -> osc tap
L2 = Sym("audio", "Xicon_42IF110_OscCoil", "L2", "42IF110 (red)", (86.36, 93.98), footprint="audio:Xicon_42IF10x")
wire(C1.p(2), L2.p(2))
wire(L2.p(1), (76.2, 88.9)); GND((76.2, 88.9), 270)      # tank cold end
wire(L2.p(3), (78.74, 121.92), (20.32, 121.92), VC1.p(3))  # tank hot end -> oscillator gang O
wire(Q1.p(3), (66.04, 81.28), (96.52, 81.28), (96.52, 88.9), L2.p(4))   # collector -> feedback winding
T1 = IFT("T1", "42IF101 (yellow)", (111.76, 93.98), "yellow")
wire(L2.p(6), (96.52, 99.06), (96.52, 93.98), T1.p(2))   # feedback winding -> IFT1 tap
VRF(T1.p(1)); nc(T1.p(3))

# ---- IF amplifier 1, Q2, with AGC
Q2 = Q("Q2", (132.08, 88.9))
wire(T1.p(4), Q2.p(2))
R6 = R("R6", "1k", (134.62, 104.14)); C4 = C("C4", "47n", (142.24, 104.14))
wire(Q2.p(1), R6.p(1)); wire((134.62, 99.06), (142.24, 99.06), C4.p(1))
wire(R6.p(2), (134.62, 110.49)); GND((134.62, 110.49))
wire(C4.p(2), (142.24, 110.49)); GND((142.24, 110.49))
T2 = IFT("T2", "42IF102 (white)", (157.48, 93.98), "white")
wire(Q2.p(3), (134.62, 81.28), (147.32, 81.28), (147.32, 93.98), T2.p(2))
VRF(T2.p(1)); nc(T2.p(3))
R4 = R("R4", "47k", (114.3, 104.14), 90); C3 = CP("C3", "10u", (124.46, 109.22)); R5 = R("R5", "10k", (123.19, 121.92), 90)
wire(T1.p(6), (119.38, 104.14), R5.p(1))                 # AGC node
wire(R4.p(2), (119.38, 104.14)); VRF(R4.p(1), 180)
wire((119.38, 104.14), (124.46, 104.14), C3.p(1))
wire(C3.p(2), (124.46, 115.57)); GND((124.46, 115.57))
wire(R5.p(2), (129.54, 121.92)); label("DET", 129.54, 121.92)

# ---- IF amplifier 2, Q3
Q3 = Q("Q3", (177.8, 88.9))
wire(T2.p(4), Q3.p(2))
R9 = R("R9", "680", (180.34, 104.14)); C6 = C("C6", "47n", (187.96, 104.14))
wire(Q3.p(1), R9.p(1)); wire((180.34, 99.06), (187.96, 99.06), C6.p(1))
wire(R9.p(2), (180.34, 110.49)); GND((180.34, 110.49))
wire(C6.p(2), (187.96, 110.49)); GND((187.96, 110.49))
T3 = IFT("T3", "42IF103 (black)", (203.2, 93.98), "black")
wire(Q3.p(3), (180.34, 81.28), (193.04, 81.28), (193.04, 93.98), T3.p(2))
VRF(T3.p(1)); nc(T3.p(3))
R7 = R("R7", "47k", (160.02, 104.14), 90); R8 = R("R8", "15k", (165.1, 109.22)); C5 = C("C5", "47n", (170.18, 109.22))
wire(T2.p(6), (165.1, 104.14), R8.p(1))
wire(R7.p(2), (165.1, 104.14)); VRF(R7.p(1), 180)
wire((165.1, 104.14), (170.18, 104.14), C5.p(1))
wire(R8.p(2), (165.1, 115.57)); GND((165.1, 115.57))
wire(C5.p(2), (170.18, 115.57)); GND((170.18, 115.57))

# ---- Detector, AGC source, volume
D1 = Sym("Device", "D", "D1", "1N34A", (217.17, 88.9), footprint="Diode_THT:D_DO-35_SOD27_P10.16mm_Horizontal")
wire(T3.p(4), D1.p(1))                                   # cathode to IFT3 secondary: negative-going detected audio/AGC
wire(T3.p(6), (210.82, 101.6)); GND((210.82, 101.6))
C7 = C("C7", "10n", (223.52, 96.52))
RV1 = Sym("Device", "R_Potentiometer", "RV1", "10k log", (231.14, 96.52), footprint="Potentiometer_THT:Potentiometer_Bourns_PTV09A-1_Single_Vertical")
wire(D1.p(2), (231.14, 88.9), RV1.p(1))
wire((223.52, 88.9), C7.p(1)); label("DET", 227.33, 88.9)
wire(C7.p(2), (223.52, 102.87)); GND((223.52, 102.87))
wire(RV1.p(3), (231.14, 102.87)); GND((231.14, 102.87))
C8 = CP("C8", "10u", (240.03, 96.52), 270)               # + towards Q4 base
wire(RV1.p(2), C8.p(2))

# ---- Audio driver Q4
Q4 = Q("Q4", (248.92, 96.52)); Q4.hide_value = True
wire(C8.p(1), Q4.p(2))
R11 = R("R11", "33k", (243.84, 87.63)); R12 = R("R12", "12k", (243.84, 105.41))
wire(R11.p(2), Q4.p(2), R12.p(1)); VBAT(R11.p(1))
wire(R12.p(2), (243.84, 111.76)); GND((243.84, 111.76))
R13 = R("R13", "330", (251.46, 109.22)); C9 = CP("C9", "100u", (256.54, 109.22))
wire(Q4.p(1), R13.p(1)); wire((251.46, 104.14), (256.54, 104.14), C9.p(1))
wire(R13.p(2), (251.46, 115.57)); GND((251.46, 115.57))
wire(C9.p(2), (256.54, 115.57)); GND((256.54, 115.57))
T4 = Sym("audio", "Xicon_42TU013_1kCT-8CT", "T4", "42TU013", (266.7, 91.44), footprint="audio:Xicon_42TU200-RC")
C10 = C("C10", "10n", (254.0, 91.44))
wire(Q4.p(3), (251.46, 86.36), T4.p(1))
wire(C10.p(1), (254.0, 86.36))
wire(C10.p(2), (254.0, 96.52), T4.p(3))
wire(T4.p(3), (259.08, 100.33), (261.62, 100.33)); VBAT((261.62, 100.33), 180)
nc(T4.p(2))

# ---- Push-pull output Q5/Q6
R14 = R("R14", "4k7", (273.05, 106.68), 90); R15 = R("R15", "680", (267.97, 111.76))
wire(T4.p(5), R15.p(1))                                  # secondary CT -> bias divider
wire((267.97, 106.68), R14.p(1)); VBAT(R14.p(2), 180)
wire(R15.p(2), (267.97, 118.11)); GND((267.97, 118.11))
Q5 = Q("Q5", (287.02, 83.82)); Q6 = Q("Q6", (287.02, 99.06), mirror="x")
wire(T4.p(4), Q5.p(2)); wire(T4.p(6), Q6.p(2))
wire(Q5.p(1), (289.56, 91.44), Q6.p(1)); G_out = GND((289.56, 91.44), 90)
T5 = Sym("audio", "Xicon_42TU200_200CT-8", "T5", "42TU200", (304.8, 91.44), footprint="audio:Xicon_42TU200-RC")
C11 = C("C11", "22n", (294.64, 88.9))
wire(Q5.p(3), (294.64, 78.74), (294.64, 83.82), T5.p(1)); wire((294.64, 83.82), C11.p(1))
wire(Q6.p(3), (294.64, 104.14), (294.64, 99.06), T5.p(3)); wire((294.64, 99.06), C11.p(2))
VBAT(T5.p(2))
J1 = Sym("Connector", "Screw_Terminal_01x02", "J1", "SPEAKER 8R", (325.12, 91.44), footprint="TerminalBlock:TerminalBlock_Altech_AK300-2_P5.00mm")
wire(T5.p(4), (317.5, 83.82), (317.5, 91.44), J1.p(1))
wire(T5.p(6), (317.5, 99.06), (317.5, 93.98), J1.p(2))

# ---- Power: battery, switch, decoupling, RF rail
BT1 = Sym("Device", "Battery", "BT1", "3xAA 4.5V", (330.2, 137.16), footprint="Battery:BatteryHolder_TruPower_BH-331P_3xAA")
SW1 = Sym("Switch", "SW_SPDT", "SW1", "POWER", (337.82, 127.0), footprint="Button_Switch_THT:SW_Slide_SPDT_Straight_CK_OS102011MS2Q")
wire(BT1.p(1), (330.2, 127.0), SW1.p(2)); nc(SW1.p(3))
C12 = CP("C12", "100u", (345.44, 135.89))
wire(SW1.p(1), (345.44, 124.46), (351.79, 124.46))
wire((345.44, 124.46), (345.44, 121.92)); VBAT((345.44, 121.92))
wire((345.44, 124.46), C12.p(1)); wire(C12.p(2), (345.44, 142.24)); GND((345.44, 142.24))
wire((350.52, 124.46), (350.52, 127.0)); FLAG((350.52, 127.0), 180)
R16 = R("R16", "330", (355.6, 124.46), 90)
C13 = CP("C13", "100u", (363.22, 135.89))
wire(R16.p(2), (363.22, 124.46), (368.3, 124.46)); FLAG((368.3, 124.46), 180)
wire((363.22, 124.46), (363.22, 121.92)); VRF((363.22, 121.92))
wire((363.22, 124.46), C13.p(1)); wire(C13.p(2), (363.22, 142.24)); GND((363.22, 142.24))
wire(BT1.p(2), (330.2, 144.78)); GND((330.2, 144.78))
wire(BT1.p(2), (335.28, 142.24)); FLAG((335.28, 142.24), 180)

# ---- Mounting holes
for i, x in enumerate((380.0, 388.0, 396.0, 404.0), 1):
    Sym("Mechanical", "MountingHole", f"H{i}", "M3", (x, 137.16), footprint="MountingHole:MountingHole_3.2mm_M3")

# ---- Notes
text("AM BROADCAST RECEIVER - 6 transistor superheterodyne, 455 kHz IF, 4.5 V (3xAA), negative ground, all 2N3904 NPN", 20.32, 40.64, 2.5)
text("Stages:  Q1 converter (mixer + local oscillator, L2 red)  ->  T1 (yellow)  ->  Q2 IF amp with AGC  ->  T2 (white)  ->  Q3 IF amp  ->  T3 (black)  ->  D1 detector  ->  RV1 volume  ->  Q4 driver  ->  T4  ->  Q5/Q6 class-B push-pull  ->  T5  ->  8 ohm speaker", 20.32, 46.99, 1.5)
text("Alignment: set VC1 fully closed, adjust L2 slug so the local oscillator is ~985 kHz (station at 530 kHz); at the high end use the VC1 oscillator trimmer for ~2055 kHz (1600 kHz). Peak T1, T2, T3 slugs for max audio on a weak station (they are pre-tuned to 455 kHz). Peak L1 by sliding the coil on the rod at the low end and the VC1 antenna trimmer at the high end. If the oscillator does not start, swap the L2 pin 4/6 feedback leads.", 20.32, 156.21, 1.5)
text("AGC: D1 delivers negative-going audio + DC. R5/C3 filter it onto the Q2 base bias node; strong stations reduce Q2 bias and gain. V_RF is the 330R/100u decoupled rail for the RF/IF stages. Electrolytics: C3, C9, C12, C13 + up; C8 + toward Q4 base.", 20.32, 162.56, 1.5)
text("Substitutions: 2N2222/BC547 for 2N3904 (check pinout), 1N60/BAT46 for 1N34A. T1..T3 and L2 are Xicon 42IF101/102/103/110 (10 mm cans). T4 = Xicon 42TU013 (1k CT : 8 CT), T5 = Xicon 42TU200 (200 CT : 8). VC1 = 2-gang polyvaricon 140/60 pF with trimmers.", 20.32, 168.91, 1.5)

# ================================================================== connectivity post-processing
def onseg(p, a, b, eps=1e-3):
    (px, py), (ax, ay), (bx, by) = p, a, b
    if abs(ax - bx) < eps and abs(px - ax) < eps and min(ay, by) + eps < py < max(ay, by) - eps: return True
    if abs(ay - by) < eps and abs(py - ay) < eps and min(ax, bx) + eps < px < max(ax, bx) - eps: return True
    return False

# split wires at points where other wire endpoints or pins land on their interior
pin_pts = [pt for s in symbols for pt in s.pins.values()]
end_pts = [p for w in wires for p in w] + pin_pts + [(x, y) for _, x, y, _ in labels]
changed = True
while changed:
    changed = False
    for i, (a, b) in enumerate(wires):
        for p in end_pts:
            if onseg(p, a, b):
                wires[i] = (a, p); wires.append((p, b)); changed = True
                break
        if changed: break

# junctions where 3+ wire ends / pins meet
cnt = defaultdict(int)
for a, b in wires:
    cnt[a] += 1; cnt[b] += 1
for pt in pin_pts:
    cnt[pt] += 1
junctions = [pt for pt, n in cnt.items() if n >= 3]

# sanity: every wire end must touch a pin, another wire end, a label, or a junction
ends = defaultdict(int)
for a, b in wires: ends[a] += 1; ends[b] += 1
dangling = [pt for pt, n in ends.items() if n == 1 and pt not in pin_pts and pt not in [(x, y) for _, x, y, _ in labels]]
if dangling:
    print("WARNING dangling wire ends:", dangling)
# pins not touched by anything (and not no_connect)
touched = set(ends) | set(p for p in pin_pts if cnt[p] >= 2)
untouched = []
for s in symbols:
    for num, pt in s.pins.items():
        ptype = s._pins_lib[num][2]
        if ptype == "no_connect": continue
        if pt not in ends and pt not in noconnects and cnt[pt] < 2:
            untouched.append((s.ref, num, pt))
if untouched:
    print("WARNING pins with no wire/no-connect:", untouched)

# ================================================================== write
def fx(v): return f"{v:.4f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v)

out = []
out.append(f'(kicad_sch\n\t(version 20250114)\n\t(generator "eeschema")\n\t(generator_version "9.0")\n\t(uuid "{ROOT_UUID}")\n\t(paper "A3")')
out.append('\t(title_block\n\t\t(title "AM Broadcast Receiver - 6 transistor superhet")\n\t\t(date "2026-09-11")\n\t\t(rev "1.0")\n\t\t(company "")\n\t\t(comment 1 "455 kHz IF, 4.5 V, all NPN 2N3904, negative ground")\n\t)')
out.append("\t(lib_symbols\n" + "\n".join(ser(v, 2) for k, v in lib_symbols.items() if not k.endswith("__pins")) + "\n\t)")

for pt in junctions:
    out.append(f'\t(junction (at {fx(pt[0])} {fx(pt[1])}) (diameter 0) (color 0 0 0 0) (uuid "{U()}"))')
for pt in noconnects:
    out.append(f'\t(no_connect (at {fx(pt[0])} {fx(pt[1])}) (uuid "{U()}"))')
for a, b in wires:
    out.append(f'\t(wire (pts (xy {fx(a[0])} {fx(a[1])}) (xy {fx(b[0])} {fx(b[1])})) (stroke (width 0) (type default)) (uuid "{U()}"))')
for name, x, y, rot in labels:
    out.append(f'\t(label "{name}" (at {fx(x)} {fx(y)} {rot}) (effects (font (size 1.27 1.27)) (justify left bottom)) (uuid "{U()}"))')
for t, x, y, size in texts:
    t = t.replace('"', '\\"')
    out.append(f'\t(text "{t}" (exclude_from_sim no) (at {fx(x)} {fx(y)} 0) (effects (font (size {size} {size})) (justify left bottom)) (uuid "{U()}"))')

def field(name, val, x, y, rot, hide=False, just=None, show_name=False):
    eff = f"(effects (font (size 1.27 1.27)){' (justify '+just+')' if just else ''}{' (hide yes)' if hide else ''})"
    return f'\t\t(property "{name}" "{val}" (at {fx(x)} {fx(y)} {rot}) {eff})'

# absolute field overrides: ref -> (ref_xy, val_xy, justify)
OVR = {
 "L1": ((45.72, 81.28), (45.72, 83.82), None),
 "VC1": ((27.94, 102.87), (27.94, 105.41), "left"),
 "L2": ((86.36, 83.82), (87.63, 106.68), None),
 "T1": ((111.76, 83.82), (109.22, 115.57), None), "T2": ((157.48, 83.82), (154.94, 115.57), None), "T3": ((203.2, 83.82), (200.66, 115.57), None),
 "T4": ((271.78, 80.01), (261.62, 80.01), None), "T5": ((312.42, 81.28), (307.34, 106.68), None),
 "Q1": ((60.96, 84.2), (60.96, 86.6), "right"),
 "Q4": ((252.73, 99.06), (252.73, 101.6), "left"),
 "Q5": ((281.94, 79.4), (281.94, 81.9), "right"), "Q6": ((295.5, 101.6), (295.5, 104.14), "left"),
 "D1": ((217.17, 86.36), (217.17, 91.44), None),
 "RV1": ((233.68, 110.5), (233.68, 113.0), "left"),
 "C11": ((296.9, 80.01), (296.9, 82.55), "left"),
 "R5": ((123.19, 124.21), (123.19, 126.75), None),
 "R2": ((51.05, 109.22), (51.05, 111.76), "right"), "R8": ((162.81, 110.49), (162.81, 113.03), "right"),
 "R13": ((249.17, 107.95), (249.17, 110.49), "right"), "R12": ((241.55, 105.41), (241.55, 107.95), "right"),
 "R15": ((270.26, 114.3), (270.26, 116.84), "left"),
 "R4": ((113.03, 106.43), (114.3, 106.43), "R4"), "R7": ((158.75, 106.43), (160.02, 106.43), "R4"),
 "R1": ((46.99, 106.43), (48.26, 106.43), "R4"),
}
for s in symbols:
    ax, ay = s.at
    is_power = s.ref.startswith("#")
    frot = 90 if s.rot in (90, 270) else 0          # keep field text horizontal on rotated parts
    rjust = vjust = None
    if s.ref in OVR:
        rpos, vpos, j = OVR[s.ref]
        if j == "R4":                                # ref right-justified, value left-justified, same row (mirrored for rotated symbols)
            rjust, vjust = "left", "right"
        else:
            rjust = vjust = j
    elif is_power:
        rpos = (ax, ay)
        if s.lib_id == "power:GND":
            vpos = {0: (ax, ay + 3.81), 90: (ax - 5.08, ay), 180: (ax, ay - 3.81), 270: (ax - 3.81, ay)}[s.rot]
        elif s.lib_id == "power:PWR_FLAG":
            vpos = (ax, ay - 4.5) if s.rot == 0 else (ax, ay + 4.5)
        else:
            vpos = (ax, ay - 3.81) if s.rot == 0 else (ax, ay + 5.08)
    elif s.rot in (90, 270):
        rpos, vpos = (ax, ay - 2.286), (ax, ay + 2.286)
    elif s.lib_id == "Transistor_BJT:Q_NPN_EBC":
        rpos, vpos, rjust, vjust = (ax + 5.08, ay - 1.27), (ax + 5.08, ay + 1.27), "left", "left"
    elif s.lib_id == "Switch:SW_SPDT":
        rpos, vpos = (ax, ay - 5.08), (ax, ay + 5.08)
    elif s.lib_id in ("Device:Battery", "Connector:Screw_Terminal_01x02"):
        rpos, vpos, rjust, vjust = (ax + 3.81, ay - 1.27), (ax + 3.81, ay + 1.27), "left", "left"
    elif s.lib_id == "Mechanical:MountingHole":
        rpos, vpos = (ax, ay - 3.81), (ax, ay + 3.81)
    else:
        rpos, vpos, rjust, vjust = (ax + 2.286, ay - 1.27), (ax + 2.286, ay + 1.27), "left", "left"
    lines = [f'\t(symbol\n\t\t(lib_id "{s.lib_id}")\n\t\t(at {fx(ax)} {fx(ay)} {s.rot})' + (f'\n\t\t(mirror {s.mirror})' if s.mirror else "") +
             f'\n\t\t(unit 1)\n\t\t(exclude_from_sim no)\n\t\t(in_bom {"no" if is_power else "yes"})\n\t\t(on_board {"no" if is_power else "yes"})\n\t\t(dnp no)\n\t\t(uuid "{s.uuid}")']
    lines.append(field("Reference", s.ref, *rpos, frot, hide=is_power, just=rjust))
    lines.append(field("Value", s.value, *vpos, frot, hide=s.hide_value, just=vjust))
    lines.append(field("Footprint", s.footprint, ax, ay, 0, hide=True))
    lines.append(field("Datasheet", "", ax, ay, 0, hide=True))
    lines.append(field("Description", "", ax, ay, 0, hide=True))
    for k, v in s.fields.items():
        lines.append(field(k, v, ax, ay, 0, hide=True))
    for num in s.pins:
        lines.append(f'\t\t(pin "{num}" (uuid "{U()}"))')
    lines.append(f'\t\t(instances (project "am-radio" (path "/{ROOT_UUID}" (reference "{s.ref}") (unit 1))))')
    lines.append("\t)")
    out.append("\n".join(lines))

out.append(f'\t(sheet_instances (path "/" (page "1")))')
out.append("\t(embedded_fonts no)\n)")
open(OUT, "w").write("\n".join(out) + "\n")
print(f"wrote {OUT}: {len(symbols)} symbols, {len(wires)} wires, {len(junctions)} junctions, {len(noconnects)} no-connects")
