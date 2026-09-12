# AM Broadcast Receiver: 6-transistor superhet KiCad

## What it is

A classic 1960's style 455 kHz superheterodyne AM receiver, 4.5 V (3×AA), negative ground, six 2N3904 NPN transistors:

| Stage | Parts |
|---|---|
| Antenna / tuning | L1 ferrite loopstick, VC1 2-gang polyvaricon (Variable Capacitor) (140 pF antenna gang, 60 pF oscillator gang, trimmers built in) |
| Converter (mixer + local oscillator) | Q1, L2 oscillator coil (i.e. Xicon 42IF110, red), C1 emitter injection, R1/R2/R3 bias |
| IF amp 1 with AGC | T1 (42IF101 yellow) => Q2 => T2; R4/R5/C3 form the AGC network |
| IF amp 2 | T2 (42IF102 white) => Q3 => T3 |
| Detector / volume | T3 (42IF103 black) => D1 1N34A germanium diode => C7 => RV1 10k log |
| Audio driver | C8 => Q4 => T4 (Xicon 42TU013, 1k CT : 8 CT) |
| Class-B push-pull output | Q5/Q6 => T5 (Xicon 42TU200, 200 CT : 8) => J1 speaker terminals; R14/R15 set base bias |
| Power | BT1 3×AA, SW1 slide switch, C12; R16/C13 make the decoupled `V_RF` rail for the RF/IF stages |

Detected audio is negative-going, so AGC lowers Q2's base bias on strong stations.

## Files

- `am-radio.kicad_sch` / `am-radio.kicad_pcb` / `am-radio.kicad_pro` — the project.
- `audio.kicad_sym` — custom symbols: Xicon 42IF10x IF transformer, 42IF110 oscillator coil, 42TU013 / 42TU200 audio transformers (6-pin, pin numbers match the footprint pads), 2-gang polyvaricon, ferrite rod coil, `V_RF` power symbol. Your original `IF_Transformer_AM` symbol is kept for reference.
- `audio.pretty/` — footprints: `Xicon_42IF10x` (0.4" can, 3+3 pins on 0.135" pitch, rows 0.27" apart, from Xicon datasheet XC-600131), `Polyvaricon_CBM-223P_Wired`, `Ferrite_Rod_Antenna_Coil`, plus your `Xicon_42TU200-RC` (courtyard moved from the invalid "Rescue" layer to F.CrtYd).
- `am-radio-outputs/` — schematic PDF, grouped BOM (CSV), PCB layer PDF, top/bottom renders, gerbers + Excellon drill files.
- `am-radio-backups/original-sketch/` — your original schematic and symbol library before this rework (also in the dated backup zips).
- `tools/` — the Python generators used to build the schematic (`gen_sch.py`), libraries (`gen_libs.py`), board (`build_pcb.py`) and ground pour / labels (`finish_pcb.py`). Run with the system `python3` (it has KiCad's `pcbnew` module).

## Board

180 × 62 mm, 2 layers, M3 holes in the corners. Antenna rod lies along the top edge (cable-tie holes provided), tuning cap at the left, RF chain left=>right along the middle, audio chain right=>left along the bottom, speaker terminal bottom-left, battery holder and power switch at the right. Full GND pour on the back. Tracks 0.6 mm (0.8–1.0 mm for GND / +BATT / V_RF), 0.2 mm clearance, 0.9/0.5 mm vias.

## Things to verify before ordering a PCB

- **VC1 footprint is unverified.** No reliable drawing of the CBM-223P terminal layout exists online, so the footprint is a "wired" one: 20 × 20 mm outline, three solder pads (O, G, A) along the bottom edge for short leads, and two 2.7 mm holes for M2.5 mounting screws on a guessed 15 mm spacing. Measure your part and adjust `gen_libs.py` (or edit the footprint) if you want it to drop straight in.
- **Oscillator phasing.** If the oscillator does not start, swap the L2 pin 4 / pin 6 feedback leads (the 42IF110 datasheet does not give winding sense).
- **T4 as a driver transformer** is the weakest part choice: a 1k CT : 8 Ω CT part drives the output bases with very low impedance, so audio gain is modest. A 10k : 2k CT driver transformer (Xicon 42TM018, different footprint) would be the textbook part. Kept because it shares the footprint you already made.
- **Resistor footprint** is the DIN0204 3.6 mm / 5.08 mm pitch you chose (1/8 W minis). Standard 1/4 W resistors need the DIN0207 7.62 mm footprint; change `FP_R` in `tools/gen_sch.py` and regenerate if so.
- **Battery holder** is the BH-331P you chose (58 × 48 mm); it dominates the board size.
- D1: 1N34A is a DO-7 part on a DO-35 10.16 mm footprint (fits). 1N60 or BAT46 also work.

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
python3 tools/build_pcb.py am-radio.net am-radio.kicad_pcb        # placed, unrouted board
# route with KiCadRoutingTools route.py, then:
python3 tools/finish_pcb.py routed.kicad_pcb am-radio.kicad_pcb   # GND pour + labels
```

---
2026 - Gordon Young WA8Q

