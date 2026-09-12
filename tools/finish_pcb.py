#!/usr/bin/env python3
"""Post-route finishing: GND pour on B.Cu, tidy reference labels, fill zones, save."""
import sys, itertools
import pcbnew
from pcbnew import VECTOR2I, FromMM

IN = sys.argv[1]; OUT = sys.argv[2]
OX, OY, W, H = 20.0, 20.0, 180.0, 62.0
board = pcbnew.LoadBoard(IN)

# ---- GND zone on the back (and front) copper
gnd = board.FindNet("GND")
KEEP = []
def add_zone(layer):
    z = pcbnew.ZONE(board)
    z.SetLayer(layer); z.SetNet(gnd); z.SetAssignedPriority(0)
    z.SetLocalClearance(FromMM(0.3)); z.SetMinThickness(FromMM(0.3))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL); z.SetThermalReliefGap(FromMM(0.4)); z.SetThermalReliefSpokeWidth(FromMM(0.6))
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_AREA); z.SetMinIslandArea(int(FromMM(3) * FromMM(3)))
    m = 0.6
    pts = [(OX + m, OY + m), (OX + W - m, OY + m), (OX + W - m, OY + H - m), (OX + m, OY + H - m)]
    poly = pcbnew.SHAPE_POLY_SET(); poly.NewOutline()
    for x, y in pts: poly.Append(VECTOR2I(FromMM(x), FromMM(y)))
    poly.thisown = 0; KEEP.append(poly)
    z.SetOutline(poly); z.SetZoneName(f"GND_{board.GetLayerName(layer)}")
    board.Add(z); return z
zones = [add_zone(pcbnew.B_Cu)]

# ---- reference labels: move each to a free spot around its footprint (plain-tuple boxes: (x0,y0,x1,y1) in nm)
fps = list(board.GetFootprints())
def bbox_of(fp):
    cy = fp.GetCourtyard(pcbnew.F_CrtYd)
    bb = cy.BBox() if cy.OutlineCount() else fp.GetBoundingBox(False, False)
    return (int(bb.GetLeft()), int(bb.GetTop()), int(bb.GetRight()), int(bb.GetBottom()))
def overlap(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]
boxes = {fp.GetReference(): bbox_of(fp) for fp in fps}
BIG = ("T4", "T5", "L1", "VC1", "BT1", "RV1", "J1", "L2", "T1", "T2", "T3")
placed = []
lim = (FromMM(OX + 0.8), FromMM(OY + 0.8), FromMM(OX + W - 0.8), FromMM(OY + H - 0.8))
for fp in fps:
    ref = fp.Reference(); r = fp.GetReference()
    if r.startswith("H"):
        ref.SetVisible(False); continue
    ref.SetTextSize(VECTOR2I(FromMM(0.9), FromMM(0.9))); ref.SetTextThickness(FromMM(0.15)); ref.SetTextAngleDegrees(0); ref.SetKeepUpright(True)
    x0, y0, x1, y1 = boxes[r]
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2; hh = (y1 - y0) // 2
    tw = int(FromMM(0.9 * 0.85 * len(r))); th = int(FromMM(1.0))
    cands = [(cx, y0 - th * 0.7), (cx, y1 + th * 0.7), (x1 + tw / 2 + FromMM(0.3), cy), (x0 - tw / 2 - FromMM(0.3), cy),
             (x0 + tw / 2, y0 - th * 0.7), (x1 - tw / 2, y0 - th * 0.7), (x0 + tw / 2, y1 + th * 0.7), (x1 - tw / 2, y1 + th * 0.7)]
    inside = [(cx, cy - hh * 0.55), (cx, cy + hh * 0.55)] if r in BIG else []
    best = None
    for (x, y) in inside + cands:
        tb = (int(x - tw / 2), int(y - th / 2), int(x + tw / 2), int(y + th / 2))
        if tb[0] < lim[0] or tb[1] < lim[1] or tb[2] > lim[2] or tb[3] > lim[3]:
            continue
        if (x, y) in inside:
            clash = any(overlap(tb, pb) for pb in placed)
        else:
            clash = any(overlap(tb, boxes[o]) for o in boxes if o != r and not o.startswith("H")) or any(overlap(tb, pb) for pb in placed)
        if not clash:
            best = (x, y, tb); break
    if best is None:
        x, y = cands[0]; best = (x, y, (int(x - tw / 2), int(y - th / 2), int(x + tw / 2), int(y + th / 2)))
    ref.SetPosition(VECTOR2I(int(best[0]), int(best[1]))); placed.append(best[2])

# ---- fill zones
filler = pcbnew.ZONE_FILLER(board)
filler.Fill(board.Zones())
pcbnew.SaveBoard(OUT, board)
print("saved", OUT, "tracks:", len(board.GetTracks()), "zones:", len(board.Zones()))
