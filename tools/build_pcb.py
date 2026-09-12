#!/usr/bin/env python3
"""Build am-radio.kicad_pcb from the exported netlist: footprints, nets, placement, outline. (pcbnew API, KiCad 9)

Board is sized for the 3D-printed case in case/case.FCStd: the PcbEnvelope reference body is 110 x 83 x 1.6 mm,
sitting on four 6 mm standoffs (2.5 mm screw holes) spaced 105.4 x 78.4 mm, i.e. 2.3 mm in from each board edge.
Case X/Y -> board x/y: x = X + 42.5, y = 41.5 - Y (board origin top-left, y down, as in KiCad).
"""
import re, sys, os
import pcbnew
from pcbnew import VECTOR2I, FromMM

PROJ = "/home/gyoung/src/am_radio/am-radio"
NET = sys.argv[1] if len(sys.argv) > 1 else "am-radio.net"
OUT = sys.argv[2] if len(sys.argv) > 2 else f"{PROJ}/am-radio.kicad_pcb"
SYSFP = "/usr/share/kicad/footprints"

# ------------------------------------------------------------- parse netlist
class Str(str): pass
def parse(text):
    toks = re.findall(r'"(?:[^"\\]|\\.)*"|\(|\)|[^\s()]+', text)
    stack = [[]]
    for t in toks:
        if t == '(': stack.append([])
        elif t == ')':
            l = stack.pop(); stack[-1].append(l)
        else: stack[-1].append(Str(t[1:-1]) if t.startswith('"') else t)
    return stack[0][0]
def get(l, key): return [x for x in l if isinstance(x, list) and x and x[0] == key]
def get1(l, key, default=None):
    r = get(l, key); return r[0][1] if r else default

tree = parse(open(NET).read())
comps = {}
for c in get(get(tree, "components")[0], "comp"):
    ref = str(get1(c, "ref"))
    props = {str(p[1]): str(p[2]) for p in get(c, "property")} if get(c, "property") else {}
    comps[ref] = dict(value=str(get1(c, "value", "")), footprint=str(get1(c, "footprint", "")), tstamps=str(get1(c, "tstamps", "")), props=props)
nets = {}
for n in get(get(tree, "nets")[0], "net"):
    name = str(get1(n, "name"))
    nets[name] = [(str(get1(x, "ref")), str(get1(x, "pin"))) for x in get(n, "node")]
print(f"netlist: {len(comps)} components, {len(nets)} nets")

# ------------------------------------------------------------- case-derived geometry (mm, board coords)
BOARD_W, BOARD_H = 110.0, 83.0
OX, OY = 20.0, 20.0          # board origin on the sheet
HOLE_IN = 2.3                # standoff centres are 2.3 mm in from each edge (105.4 x 78.4 pattern)
HOLES = {"H1": (HOLE_IN, HOLE_IN), "H2": (BOARD_W - HOLE_IN, HOLE_IN), "H3": (HOLE_IN, BOARD_H - HOLE_IN), "H4": (BOARD_W - HOLE_IN, BOARD_H - HOLE_IN)}
# 76 mm square speaker envelope under the board (2 mm clearance): case X -38..38, Y -38..38
SPEAKER = (4.5, 3.5, 80.5, 79.5)
# 12 x 12 mm CornerHole in the case base plate: case X 46..58, Y 20..32
CORNER_HOLE = (88.5, 9.5, 100.5, 21.5)
# speaker lead pass-through: 3.5 mm hole beside J1, in the strip east of the speaker where there is 18 mm under the board
WIRE_HOLE = (107.3, 67.5, 3.5)

# ------------------------------------------------------------- placement (mm, board origin top-left; rotation deg CCW)
# Each entry is the COURTYARD CENTRE of the part after rotation (footprint origins are wherever the library put them).
P = {
 # mounting holes (M2.5, on the case standoffs)
 **{h: (x, y, 0) for h, (x, y) in HOLES.items()},
 # antenna rod along the top edge (pads at its left end), tuning cap in the top-left corner with its terminals facing the rod
 "L1": (60.75, 9.5, 0),
 "VC1": (16.0, 15.5, 90),
 # battery holder (3xAAA, Keystone 2479) standing on end at the left, terminals at its top edge
 "BT1": (24.8, 53.8, 270),
 # power switch + reservoir cap in the top-right corner (switch at the wall so a side slot can reach it); V_RF decoupling next to L2
 "SW1": (105.7, 11.0, 90), "C12": (96.5, 9.5, 0),
 "C13": (48.0, 34.5, 0), "R16": (52.5, 34.5, 90),
 # converter: oscillator coil beside the tuning cap, then Q1 and its bias parts
 "L2": (51.0, 25.0, 0), "C1": (56.0, 34.5, 90),
 "Q1": (61.5, 22.5, 0), "R1": (61.5, 27.0, 0), "R2": (61.5, 30.5, 0), "C2": (61.5, 34.0, 0), "R3": (61.5, 37.5, 0),
 # IF1 with AGC
 "T1": (72.0, 25.0, 0), "R4": (69.5, 34.0, 0), "C3": (76.5, 35.0, 0), "R5": (69.5, 37.5, 0),
 "Q2": (83.5, 22.5, 0), "R6": (83.0, 27.5, 0), "C4": (83.0, 31.0, 0),
 # IF2: T2, Q3 in the top-right, T3 turns the corner down the right edge
 "T2": (94.5, 25.0, 0), "Q3": (106.0, 22.5, 0), "R9": (105.5, 27.5, 0), "C6": (105.5, 31.0, 0),
 "C5": (91.5, 34.5, 0), "R7": (91.5, 38.0, 0), "R8": (91.5, 41.5, 0),
 "T3": (103.5, 41.0, 0),
 # detector / volume (right side, below T3)
 "D1": (89.0, 47.5, 0), "C7": (90.0, 51.0, 0), "RV1": (101.55, 56.5, 0),
 # driver: Q4 feeds T4 (on end, secondary facing down to Q5/Q6)
 "C8": (83.5, 54.5, 90), "C9": (90.0, 56.5, 0), "C10": (77.0, 46.5, 0), "R11": (77.0, 50.0, 0), "Q4": (77.5, 54.5, 0),
 "R12": (77.0, 58.5, 0), "R13": (72.0, 57.0, 90),
 "T4": (55.7, 55.5, 270),
 # push-pull output under T4, output transformer to its right, speaker terminals at the right edge next to the wire hole
 "Q5": (49.0, 72.5, 0), "Q6": (61.0, 72.5, 0), "C11": (55.0, 73.0, 90), "R14": (52.0, 78.5, 0), "R15": (59.5, 78.5, 0),
 "T5": (79.9, 72.3, 0), "J1": (99.3, 71.0, 0),
}

# ------------------------------------------------------------- build board
board = pcbnew.CreateEmptyBoard()
ds = board.GetDesignSettings()
ds.m_MinClearance = FromMM(0.2); ds.m_TrackMinWidth = FromMM(0.25); ds.m_ViasMinSize = FromMM(0.6); ds.m_MinThroughDrill = FromMM(0.3)
ds.m_CopperEdgeClearance = FromMM(0.5); ds.m_HoleClearance = FromMM(0.3); ds.m_HoleToHoleMin = FromMM(0.5)
ds.SetCopperLayerCount(2)
nc = ds.m_NetSettings.GetDefaultNetclass()
nc.SetClearance(FromMM(0.2)); nc.SetTrackWidth(FromMM(0.6)); nc.SetViaDiameter(FromMM(0.9)); nc.SetViaDrill(FromMM(0.5))

netinfo = {}
for name in nets:
    ni = pcbnew.NETINFO_ITEM(board, name)
    board.Add(ni); netinfo[name] = ni
pad_net = {}
for name, nodes in nets.items():
    for ref, pin in nodes:
        pad_net[(ref, pin)] = name

def load_fp(fpid):
    lib, name = fpid.split(":")
    path = f"{PROJ}/audio.pretty" if lib == "audio" else f"{SYSFP}/{lib}.pretty"
    fp = pcbnew.FootprintLoad(path, name)
    if fp is None:
        raise SystemExit(f"cannot load footprint {fpid}")
    fp.SetFPID(pcbnew.LIB_ID(lib, name))          # keep the library nickname so schematic parity checks pass
    return fp

missing = [r for r in comps if r not in P]
if missing: raise SystemExit(f"no placement for {missing}")

for ref, c in comps.items():
    fp = load_fp(c["footprint"])
    fp.SetReference(ref); fp.SetValue(c["value"])
    fp.SetExcludedFromBOM(False)                  # every symbol on the schematic is in the BOM (the mounting-hole footprints default to excluded)
    fp.SetPath(pcbnew.KIID_PATH(c["tstamps"]))
    x, y, rot = P[ref]
    fp.SetPosition(VECTOR2I(0, 0)); fp.SetOrientationDegrees(rot)
    cy = fp.GetCourtyard(pcbnew.F_CrtYd); bb = cy.BBox() if cy.OutlineCount() else fp.GetBoundingBox(False, False)
    ctr = fp.Pads()[0].GetPosition() if ref in HOLES else bb.GetCenter()      # holes: exact hole centre on the standoff pattern
    fp.SetPosition(VECTOR2I(FromMM(OX + x) - ctr.x, FromMM(OY + y) - ctr.y))
    for pad in fp.Pads():
        n = pad_net.get((ref, pad.GetNumber()))
        if n: pad.SetNet(netinfo[n])
    # readable reference text
    fp.Reference().SetTextSize(VECTOR2I(FromMM(0.9), FromMM(0.9))); fp.Reference().SetTextThickness(FromMM(0.15))
    fp.Value().SetVisible(False)
    board.Add(fp)

# outline + speaker-lead hole
def edge(a, b):
    s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetLayer(pcbnew.Edge_Cuts)
    s.SetStart(VECTOR2I(FromMM(a[0]), FromMM(a[1]))); s.SetEnd(VECTOR2I(FromMM(b[0]), FromMM(b[1]))); s.SetWidth(FromMM(0.1)); board.Add(s)
c = [(OX, OY), (OX + BOARD_W, OY), (OX + BOARD_W, OY + BOARD_H), (OX, OY + BOARD_H)]
for i in range(4): edge(c[i], c[(i + 1) % 4])
wx, wy, wd = WIRE_HOLE
s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_CIRCLE); s.SetLayer(pcbnew.Edge_Cuts)
s.SetCenter(VECTOR2I(FromMM(OX + wx), FromMM(OY + wy))); s.SetEnd(VECTOR2I(FromMM(OX + wx + wd / 2), FromMM(OY + wy))); s.SetWidth(FromMM(0.1)); board.Add(s)

def silk(txt, x, y, size=1.5, layer=pcbnew.F_SilkS, rot=0):
    t = pcbnew.PCB_TEXT(board); t.SetText(txt); t.SetLayer(layer)
    t.SetPosition(VECTOR2I(FromMM(OX + x), FromMM(OY + y))); t.SetTextSize(VECTOR2I(FromMM(size), FromMM(size))); t.SetTextThickness(FromMM(size * 0.15))
    t.SetTextAngleDegrees(rot); board.Add(t); return t
silk("AM SUPERHET  rev 1.1", 55.5, 40.4, 1.2)
silk("VOLUME", 102.5, 48.2, 1.0); silk("SPKR", 99.5, 80.3, 1.0); silk("WIRES", 107.3, 71.4, 0.8)
silk("POWER", 101.3, 11.0, 0.9, rot=90); silk("ON", 106.0, 18.2, 0.8); silk("OFF", 101.3, 5.5, 0.8)
silk("3 x AAA  4.5V", 3.0, 52.0, 1.2, rot=90)
silk("+", 40.6, 30.1, 1.2); silk("-", 20.6, 30.1, 1.2)
b = silk("am-radio  rev 1.1  2026-09", 55.0, 41.5, 2.0, pcbnew.B_SilkS); b.SetMirrored(True)

# ---- placement sanity: courtyard overlaps, board bounds, case constraints
import itertools
boxes = {}
for fp in board.GetFootprints():
    cy = fp.GetCourtyard(pcbnew.F_CrtYd)
    bb = cy.BBox() if cy.OutlineCount() else fp.GetBoundingBox(False, False)
    boxes[fp.GetReference()] = (bb.GetLeft()/1e6 - OX, bb.GetTop()/1e6 - OY, bb.GetRight()/1e6 - OX, bb.GetBottom()/1e6 - OY)
bad = 0
def hit(a, b2): return a[0] < b2[2] and b2[0] < a[2] and a[1] < b2[3] and b2[1] < a[3]
for r, bx in boxes.items():
    x0, y0, x1, y1 = bx
    if r.startswith("H"):
        continue                       # the 6 mm standoff face overhangs the board edge by design
    if x0 < 0 or y0 < 0 or x1 > BOARD_W or y1 > BOARD_H:
        print(f"OUT OF BOARD {r}: x[{x0:.1f},{x1:.1f}] y[{y0:.1f},{y1:.1f}]"); bad += 1
    if hit(bx, (wx - wd/2 - 0.3, wy - wd/2 - 0.3, wx + wd/2 + 0.3, wy + wd/2 + 0.3)):
        print(f"ON WIRE HOLE {r}"); bad += 1
for (ra, a), (rb, b2) in itertools.combinations(boxes.items(), 2):
    if hit(a, b2):
        print(f"OVERLAP {ra} x[{a[0]:.1f},{a[2]:.1f}] y[{a[1]:.1f},{a[3]:.1f}]  <->  {rb} x[{b2[0]:.1f},{b2[2]:.1f}] y[{b2[1]:.1f},{b2[3]:.1f}]"); bad += 1
for fp in board.GetFootprints():          # nothing on the back under the speaker (only 2 mm there)
    if fp.GetLayer() == pcbnew.B_Cu and hit(boxes[fp.GetReference()], SPEAKER):
        print(f"BACK-SIDE PART OVER SPEAKER {fp.GetReference()}"); bad += 1
print("placement problems:", bad)
for r in ("BT1", "SW1", "VC1", "L1", "RV1", "J1", "T4", "T5"):
    fp = board.FindFootprintByReference(r)
    print(f"  {r}: " + " ".join(f"{p.GetNumber() or 'np'}@({p.GetPosition().x/1e6-OX:.1f},{p.GetPosition().y/1e6-OY:.1f})" for p in fp.Pads()))
over = [r for r, bx in boxes.items() if hit(bx, CORNER_HOLE)]
print("top-side parts above the case CornerHole (base plate, harmless):", over)

pcbnew.SaveBoard(OUT, board)
print("saved", OUT, "footprints:", len(board.GetFootprints()))
