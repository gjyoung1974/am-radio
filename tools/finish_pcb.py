#!/usr/bin/env python3
"""Post-route finishing: GND pour on B.Cu, tidy reference labels, fill zones, save."""
import sys, itertools
import pcbnew
from pcbnew import VECTOR2I, FromMM

IN = sys.argv[1]; OUT = sys.argv[2]
OX, OY, W, H = 20.0, 20.0, 110.0, 83.0
HOLE_IN, KEEPOUT_R = 2.3, 3.2      # case standoffs: 6 mm face, 2.3 mm in from each edge -> copper-free 6.4 mm circle on both sides
HOLES = [(HOLE_IN, HOLE_IN), (W - HOLE_IN, HOLE_IN), (HOLE_IN, H - HOLE_IN), (W - HOLE_IN, H - HOLE_IN)]
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

# ---- keepouts where the standoff faces / screw heads sit (no pour, tracks or vias), and a check that the router stayed out
import math
for hx, hy in HOLES:
    k = pcbnew.ZONE(board); k.SetIsRuleArea(True)
    k.SetDoNotAllowCopperPour(True); k.SetDoNotAllowTracks(True); k.SetDoNotAllowVias(True); k.SetDoNotAllowPads(False); k.SetDoNotAllowFootprints(False)
    ls = pcbnew.LSET(); ls.addLayer(pcbnew.F_Cu); ls.addLayer(pcbnew.B_Cu); k.SetLayerSet(ls)
    poly = pcbnew.SHAPE_POLY_SET(); poly.NewOutline()
    for i in range(36):
        a = 2 * math.pi * i / 36
        poly.Append(VECTOR2I(FromMM(OX + hx + KEEPOUT_R * math.cos(a)), FromMM(OY + hy + KEEPOUT_R * math.sin(a))))
    poly.thisown = 0; KEEP.append(poly); k.SetOutline(poly); k.SetZoneName(f"standoff_{hx:.0f}_{hy:.0f}")
    board.Add(k)
intr = 0
for t in board.GetTracks():
    pts = [t.GetStart(), t.GetEnd()] if t.Type() == pcbnew.PCB_TRACE_T else [t.GetPosition()]
    for hx, hy in HOLES:
        for q in pts:
            if math.hypot(q.x / 1e6 - OX - hx, q.y / 1e6 - OY - hy) < KEEPOUT_R + t.GetWidth() / 2e6:
                print(f"TRACK IN STANDOFF KEEPOUT: net {t.GetNetname()} at ({q.x/1e6-OX:.1f},{q.y/1e6-OY:.1f})"); intr += 1
print("tracks intruding on standoff keepouts:", intr)

# ---- drop dangling track stubs (an end that touches no pad, via or other track)
EPS = 10  # nm: junctions the router makes coincide exactly; anything else is not a connection
def touches(pt, layer, skip):
    for t in board.GetTracks():
        if t is skip: continue
        if t.Type() == pcbnew.PCB_VIA_T:
            if (t.GetPosition() - pt).EuclideanNorm() <= t.GetWidth(layer) / 2: return True
        elif t.GetLayer() == layer:
            if (t.GetStart() - pt).EuclideanNorm() <= EPS or (t.GetEnd() - pt).EuclideanNorm() <= EPS: return True
            if pcbnew.SEG(t.GetStart(), t.GetEnd()).Distance(pt) <= EPS: return True      # T-junction onto a track
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.IsOnLayer(layer) and pad.HitTest(pt, 0): return True
    return False
removed = 0
for t in [t for t in board.GetTracks() if t.Type() == pcbnew.PCB_TRACE_T and t.GetLength() < FromMM(0.05)]:
    board.Delete(t); removed += 1                  # sub-grid slivers the router leaves inside other copper
while True:
    dangling = [t for t in board.GetTracks() if t.Type() == pcbnew.PCB_TRACE_T and (not touches(t.GetStart(), t.GetLayer(), t) or not touches(t.GetEnd(), t.GetLayer(), t))]
    if not dangling: break
    for t in dangling: board.Delete(t); removed += 1
print("dangling stubs removed:", removed)

# ---- reference labels: move each to a free spot around its footprint (plain-tuple boxes: (x0,y0,x1,y1) in nm)
fps = list(board.GetFootprints())
def bbox_of(fp):
    cy = fp.GetCourtyard(pcbnew.F_CrtYd)
    bb = cy.BBox() if cy.OutlineCount() else fp.GetBoundingBox(False, False)
    return (int(bb.GetLeft()), int(bb.GetTop()), int(bb.GetRight()), int(bb.GetBottom()))
def overlap(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]
boxes = {fp.GetReference(): bbox_of(fp) for fp in fps}
def rect(bb): return (int(bb.GetLeft()), int(bb.GetTop()), int(bb.GetRight()), int(bb.GetBottom()))
copper = [rect(pad.GetBoundingBox()) for fp in fps for pad in fp.Pads()] + [rect(t.GetBoundingBox()) for t in board.GetTracks() if t.Type() == pcbnew.PCB_VIA_T]
silks = [d for d in board.GetDrawings() if d.GetLayer() == pcbnew.F_SilkS]
silks += [g for fp in fps for g in fp.GraphicalItems() if g.GetLayer() == pcbnew.F_SilkS]
def silk_hit(tb, margin):
    box = pcbnew.BOX2I(VECTOR2I(tb[0], tb[1]), VECTOR2I(tb[2] - tb[0], tb[3] - tb[1]))
    return any(g.HitTest(box, False, margin) for g in silks)
def m(b, d): return (b[0] - d, b[1] - d, b[2] + d, b[3] + d)
BIG = ("T4", "T5", "L1", "VC1", "BT1", "RV1", "J1", "L2", "T1", "T2", "T3", "SW1")
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
    cands = []
    for off in (FromMM(0.3), FromMM(0.9), FromMM(1.6), FromMM(2.4)):
        oy, ox = th / 2 + off, tw / 2 + off
        cands += [(cx, y0 - oy), (cx, y1 + oy), (x1 + ox, cy), (x0 - ox, cy),
                  (x0 + tw / 2, y0 - oy), (x1 - tw / 2, y0 - oy), (x0 + tw / 2, y1 + oy), (x1 - tw / 2, y1 + oy),
                  (x1 + ox, y0 + th / 2), (x1 + ox, y1 - th / 2), (x0 - ox, y0 + th / 2), (x0 - ox, y1 - th / 2)]
    inside = [(cx, cy), (cx, cy - hh * 0.55), (cx, cy + hh * 0.55), (cx, cy - hh * 0.3), (cx, cy + hh * 0.3)] if r in BIG else []
    best, best_score = None, None
    for (x, y) in inside + cands:
        tb = (int(x - tw / 2), int(y - th / 2), int(x + tw / 2), int(y + th / 2))
        if tb[0] < lim[0] or tb[1] < lim[1] or tb[2] > lim[2] or tb[3] > lim[3]:
            continue
        score = 100 * sum(overlap(m(tb, FromMM(0.15)), cb) for cb in copper) + 10 * sum(overlap(tb, pb) for pb in placed) + 3 * silk_hit(tb, FromMM(0.15))
        if (x, y) not in inside:
            score += sum(overlap(tb, boxes[o]) for o in boxes if o != r and not o.startswith("H"))
        if best is None or score < best_score:
            best, best_score = (x, y, tb), score
        if score == 0: break
    if best_score: print(f"  label {r}: best position still clashes (score {best_score})")
    ref.SetPosition(VECTOR2I(int(best[0]), int(best[1]))); placed.append(best[2])

# ---- fill zones
filler = pcbnew.ZONE_FILLER(board)
filler.Fill(board.Zones())
pcbnew.SaveBoard(OUT, board)
print("saved", OUT, "tracks:", len(board.GetTracks()), "zones:", len(board.Zones()))
