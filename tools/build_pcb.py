#!/usr/bin/env python3
"""Build am-radio.kicad_pcb from the exported netlist: footprints, nets, placement, outline. (pcbnew API, KiCad 9)"""
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

# ------------------------------------------------------------- placement (mm, board origin top-left; rotation deg CCW)
BOARD_W, BOARD_H = 180.0, 62.0
OX, OY = 20.0, 20.0          # board origin on the sheet

P = {
 # mounting holes
 "H1": (3.5, 3.5, 0), "H2": (176.5, 3.5, 0), "H3": (3.5, 58.5, 0), "H4": (176.5, 58.5, 0),
 # antenna rod along the top edge, tuning cap below it at the left
 "L1": (9.0, 10.0, 0),
 "VC1": (13.5, 29.5, 0),
 # converter
 "Q1": (28.5, 22.5, 0), "R1": (26.0, 27.0, 0), "R2": (26.0, 30.5, 0), "C2": (26.0, 34.0, 0), "R3": (26.0, 37.5, 0),
 "C1": (35.5, 32.5, 90), "L2": (43.5, 24.5, 0), "T1": (57.0, 24.5, 0),
 # IF1 with AGC
 "Q2": (67.5, 22.5, 0), "R6": (65.0, 27.5, 0), "C4": (65.0, 31.0, 0),
 "R4": (50.0, 33.5, 0), "C3": (58.5, 34.5, 0), "R5": (50.0, 37.0, 0),
 "T2": (80.0, 24.5, 0),
 # IF2
 "Q3": (90.0, 22.5, 0), "R9": (87.5, 27.5, 0), "C6": (87.5, 31.0, 0),
 "R7": (72.0, 34.0, 0), "R8": (72.0, 37.5, 0), "C5": (79.5, 34.0, 0),
 "T3": (102.5, 24.5, 0),
 # RF supply decoupling, at the end of the RF row
 "R16": (110.5, 36.0, 90), "C13": (105.5, 35.0, 0),
 # detector / volume (audio row runs right -> left)
 "D1": (96.0, 40.5, 0), "C7": (99.5, 44.0, 0), "RV1": (98.0, 57.0, 0), "C8": (93.5, 52.5, 90),
 # driver
 "Q4": (86.0, 45.5, 0), "R11": (84.5, 41.0, 0), "C10": (86.5, 37.5, 0), "R12": (84.5, 50.5, 0), "R13": (84.5, 54.0, 0), "C9": (85.5, 58.5, 0),
 "T4": (69.0, 51.0, 180),
 # push-pull output
 "Q5": (51.0, 43.5, 0), "Q6": (51.0, 59.0, 0), "R14": (48.5, 54.0, 90), "R15": (45.5, 54.0, 90),
 "C11": (45.0, 46.5, 90), "T5": (29.5, 51.0, 180), "J1": (8.0, 51.0, 90),
 # power (below the battery holder)
 "BT1": (116.0, 12.0, 0), "SW1": (150.0, 57.5, 0), "C12": (125.0, 57.5, 0),
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
    return fp

missing = [r for r in comps if r not in P]
if missing: raise SystemExit(f"no placement for {missing}")

for ref, c in comps.items():
    fp = load_fp(c["footprint"])
    fp.SetReference(ref); fp.SetValue(c["value"])
    fp.SetPath(pcbnew.KIID_PATH(c["tstamps"]))
    x, y, rot = P[ref]
    fp.SetPosition(VECTOR2I(FromMM(OX + x), FromMM(OY + y)))
    fp.SetOrientationDegrees(rot)
    for pad in fp.Pads():
        n = pad_net.get((ref, pad.GetNumber()))
        if n: pad.SetNet(netinfo[n])
    # readable reference text
    fp.Reference().SetTextSize(VECTOR2I(FromMM(0.9), FromMM(0.9))); fp.Reference().SetTextThickness(FromMM(0.15))
    fp.Value().SetVisible(False)
    board.Add(fp)

# outline
def edge(a, b):
    s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetLayer(pcbnew.Edge_Cuts)
    s.SetStart(VECTOR2I(FromMM(a[0]), FromMM(a[1]))); s.SetEnd(VECTOR2I(FromMM(b[0]), FromMM(b[1]))); s.SetWidth(FromMM(0.1)); board.Add(s)
c = [(OX, OY), (OX + BOARD_W, OY), (OX + BOARD_W, OY + BOARD_H), (OX, OY + BOARD_H)]
for i in range(4): edge(c[i], c[(i + 1) % 4])

def silk(txt, x, y, size=1.5, layer=pcbnew.F_SilkS, rot=0):
    t = pcbnew.PCB_TEXT(board); t.SetText(txt); t.SetLayer(layer)
    t.SetPosition(VECTOR2I(FromMM(OX + x), FromMM(OY + y))); t.SetTextSize(VECTOR2I(FromMM(size), FromMM(size))); t.SetTextThickness(FromMM(size * 0.15))
    t.SetTextAngleDegrees(rot); board.Add(t); return t
silk("AM SUPERHET RECEIVER  rev 1.0", 92.0, 3.0, 1.5)
silk("VOLUME", 108.0, 45.5, 1.0); silk("SPKR", 8.0, 41.5, 1.0); silk("POWER", 152.0, 53.5, 1.0); silk("ON", 156.5, 57.5, 0.8); silk("OFF", 143.5, 57.5, 0.8)
silk("3 x AA  4.5V", 143.0, 27.0, 2.0)
silk("+", 110.5, 12.0, 1.5); silk("-", 110.5, 24.8, 1.5)
b = silk("am-radio  rev 1.0  2026-09", 90.0, 31.0, 2.0, pcbnew.B_SilkS); b.SetMirrored(True)

# ---- placement sanity: courtyard overlaps and board bounds
import itertools
boxes = {}
for fp in board.GetFootprints():
    cy = fp.GetCourtyard(pcbnew.F_CrtYd)
    bb = cy.BBox() if cy.OutlineCount() else fp.GetBoundingBox(False, False)
    boxes[fp.GetReference()] = (bb.GetLeft()/1e6 - OX, bb.GetTop()/1e6 - OY, bb.GetRight()/1e6 - OX, bb.GetBottom()/1e6 - OY)
bad = 0
for r, (x0, y0, x1, y1) in boxes.items():
    if x0 < 0 or y0 < 0 or x1 > BOARD_W or y1 > BOARD_H:
        print(f"OUT OF BOARD {r}: x[{x0:.1f},{x1:.1f}] y[{y0:.1f},{y1:.1f}]"); bad += 1
for (ra, a), (rb, b2) in itertools.combinations(boxes.items(), 2):
    if a[0] < b2[2] and b2[0] < a[2] and a[1] < b2[3] and b2[1] < a[3]:
        print(f"OVERLAP {ra} x[{a[0]:.1f},{a[2]:.1f}] y[{a[1]:.1f},{a[3]:.1f}]  <->  {rb} x[{b2[0]:.1f},{b2[2]:.1f}] y[{b2[1]:.1f},{b2[3]:.1f}]"); bad += 1
print("placement problems:", bad)

pcbnew.SaveBoard(OUT, board)
print("saved", OUT, "footprints:", len(board.GetFootprints()))
