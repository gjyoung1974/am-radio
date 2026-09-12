# AM Broadcast Receiver: 6-transistor superhet KiCad

## What it is

A classic 1960's style 455 kHz superheterodyne AM receiver, 4.5 V (3×AAA), negative ground, six 2N3904 NPN transistors:

| Stage | Parts |
|---|---|
| Antenna / tuning | L1 ferrite loopstick, VC1 2-gang polyvaricon (Variable Capacitor) (140 pF antenna gang, 60 pF oscillator gang, trimmers built in) |
| Converter (mixer + local oscillator) | Q1, L2 oscillator coil (i.e. Xicon 42IF110, red), C1 emitter injection, R1/R2/R3 bias |
| IF amp 1 with AGC | T1 (42IF101 yellow) => Q2 => T2; R4/R5/C3 form the AGC network |
| IF amp 2 | T2 (42IF102 white) => Q3 => T3 |
| Detector / volume | T3 (42IF103 black) => D1 1N34A germanium diode => C7 => RV1 10k log |
| Audio driver | C8 => Q4 => T4 (Xicon 42TU013, 1k CT : 8 CT) |
| Class-B push-pull output | Q5/Q6 => T5 (Xicon 42TU200, 200 CT : 8) => J1 speaker terminals; R14/R15 set base bias |
| Power | BT1 3×AAA (Keystone 2479 board-mount holder), SW1 slide switch, C12; R16/C13 make the decoupled `V_RF` rail for the RF/IF stages 
|Detected audio is negative-side, so AGC lowers Q2's base bias on strong stations.

## Files

- `am-radio.kicad_sch` / `am-radio.kicad_pcb` / `am-radio.kicad_pro` — the project.
- `audio.kicad_sym` — custom symbols: Xicon 42IF10x IF transformer, 42IF110 oscillator coil, 42TU013 / 42TU200 audio transformers (6-pin, pin numbers match the footprint pads), 2-gang polyvaricon, ferrite rod coil, `V_RF` power symbol. Your original `IF_Transformer_AM` symbol is kept for reference.
- `audio.pretty/` — footprints: `Xicon_42IF10x` (0.4" can, 3+3 pins on 0.135" pitch, rows 0.27" apart, from Xicon datasheet XC-600131), `Polyvaricon_CBM-223P_Wired`, `Ferrite_Rod_Antenna_Coil`, plus your `Xicon_42TU200-RC` (courtyard moved from the invalid "Rescue" layer to F.CrtYd).
- `am-radio-outputs/` — schematic PDF, grouped BOM (CSV), PCB layer PDF, top/bottom renders, gerbers + Excellon drill files.
- `am-radio-backups/original-sketch/` — your original schematic and symbol library before this rework (also in the dated backup zips).
- `tools/` — the Python generators used to build the schematic (`gen_sch.py`), libraries (`gen_libs.py`), board (`build_pcb.py`) and ground pour / labels (`finish_pcb.py`). Run with the system `python3` (it has KiCad's `pcbnew` module).

## Board

110 × 83 × 1.6 mm, 2 layers, sized to the 3D-printed case in `case/case.FCStd` (rev 1.1; the 180 × 62 mm rev 1.0 board is kept in `am-radio-backups/rev1.0-180x62/`).

Case fit (all taken from the FreeCAD model):

| Item | Value |
|---|---|
| Case | 115 × 88 × 35 mm, 2 mm walls, open top; cavity 111 × 84 mm |
| Board | 110 × 83 mm, 0.5 mm clearance per side |
| Standoffs | 4, Ø6 mm, 18 mm tall on the 2 mm base; board top face at 21.6 mm |
| Mounting holes | 2.7 mm (M2.5 self-tapping into the 2.5 mm standoff holes), centres 2.3 mm in from each edge = 105.4 × 78.4 mm pattern; 6.4 mm copper-free keepouts on both sides |
| Speaker | 76 mm square, 16 mm deep, centred under the board (board x 4.5–80.5, y 3.5–79.5); only 2 mm between it and the back of the board, so nothing is mounted on the back |
| Speaker leads | 3.5 mm pass-through hole at board (107.3, 67.5) next to J1, in the 29 mm strip east of the speaker where there is 18 mm under the board |
| Height above board | 13.4 mm to the top of the case: fine for the 10 mm IF cans and TO-92s; **check** the Keystone 2479 holder (≈13 mm), the 42TU audio transformers, and plan lid holes for the VC1 and RV1 shafts and a side slot for SW1 (it sits 4 mm from the right wall) |
| Case CornerHole | the 12 × 12 mm hole in the base plate (case X 46–58, Y 20–32) is under board x 88.5–100.5, y 9.5–21.5; only top-side parts (T2, L1, C12) are above it, so nothing on the board depends on it |

Coordinates: board x = case X + 42.5, board y = 41.5 − case Y (board origin top-left, y down, as in KiCad).

Layout: ferrite rod along the top edge with the tuning cap in the top-left corner (terminals facing the rod), 3×AAA holder standing on end along the left edge, RF chain left => right across the middle (L2, Q1, T1, Q2, T2, Q3) with T3 turning down the right edge, detector and volume pot below it, driver T4 on end in the middle, push-pull pair below it, output transformer T5 bottom-right with the speaker terminal block and wire hole beside it, power switch and C12 in the top-right corner. Full GND pour on the back. Tracks 0.6 mm (0.8–1.0 mm for GND / +BATT / V_RF), 0.2 mm clearance, 0.9/0.5 mm vias, 0.5 mm hole-to-hole.

## Things to verify before ordering a PCB

- **VC1 footprint is unverified.** No reliable drawing of the CBM-223P terminal layout exists online, so the footprint is a "wired" one: 20 × 20 mm outline, three solder pads (O, G, A) along the bottom edge for short leads, and two 2.7 mm holes for M2.5 mounting screws on a guessed 15 mm spacing. Measure your part and adjust `gen_libs.py` (or edit the footprint) if you want it to drop straight in.
- **Battery holder height.** The 3×AA holder (60 × 50 × 16 mm) did not fit the case, so BT1 is now a Keystone 2479 3×AAA holder (53.6 × 38.6 mm footprint, about 13 mm tall). Confirm its height against the 13.4 mm left above the board, or use a wired 3×AAA pack fixed to the lid and solder the leads to the BT1 pads.
- **Oscillator phasing.** If the oscillator does not start, swap the L2 pin 4 / pin 6 feedback leads (the 42IF110 datasheet does not give winding order?).

## Alignment

1. Set VC1 fully closed (max capacitance). Adjust the L2 slug so the local oscillator is at about 985 kHz (receives 530 kHz). At the high end use VC1's oscillator trimmer for about 2055 kHz (1600 kHz).
2. Peak T1, T2, T3 slugs for maximum audio on a weak station (they are pre-tuned to 455 kHz and need only a touch).
3. Peak L1 by sliding the coil along the rod at the low end of the band and with VC1's antenna trimmer at the high end.
4. Expected currents: converter ≈ 0.4 mA, IF stages ≈ 0.5 mA each, driver ≈ 1.7 mA, output pair a few mA idle. Total idle ≈ 5–8 mA at 4.5 V.

## Regenerating

```
python3 tools/gen_libs.py                       # symbols + footprints
python3 tools/gen_sch.py                        # schematic
kicad-cli sch export netlist --format kicadsexpr -o am-radio.net am-radio.kicad_sch
python3 tools/build_pcb.py am-radio.net placed.kicad_pcb          # placed, unrouted board (110 x 83, case holes, wire hole)
python3 ~/src/KiCadRoutingTools/route.py placed.kicad_pcb routed.kicad_pcb \
    --track-width 0.6 --clearance 0.2 --via-size 0.9 --via-drill 0.5 \
    --power-nets GND V_RF +BATT --power-nets-widths 0.8 0.8 1.0 \
    --board-edge-clearance 0.5 --hole-to-hole-clearance 0.5
python3 tools/finish_pcb.py routed.kicad_pcb am-radio.kicad_pcb   # GND pour, standoff keepouts, stub cleanup, labels
kicad-cli pcb drc --schematic-parity --severity-all am-radio.kicad_pcb
```

---
2026 - Gordon Young WA8Q

