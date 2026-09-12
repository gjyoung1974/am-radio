#!/usr/bin/env python3
"""Generate custom symbols (audio.kicad_sym) and footprints (audio.pretty) for the AM radio."""
import uuid, os, re
PROJ = "/home/gyoung/src/am_radio/am-radio"

def U(): return str(uuid.uuid4())

# ---------------------------------------------------------------- symbols
def prop(name, val, x, y, hide=False, just=None, size=1.27):
    eff = f"(effects (font (size {size} {size})){' (justify '+just+')' if just else ''}{' (hide yes)' if hide else ''})"
    return f'(property "{name}" "{val}" (at {x} {y} 0) {eff})'

def pin(ptype, x, y, ang, num, name="~", length=2.54, hide=False):
    return (f'(pin {ptype} line (at {x} {y} {ang}) (length {length}){" (hide yes)" if hide else ""} '
            f'(name "{name}" (effects (font (size 1.016 1.016)))) (number "{num}" (effects (font (size 1.016 1.016)))))')

def poly(pts, w=0.254, typ="default"):
    p = " ".join(f"(xy {x} {y})" for x, y in pts)
    return f"(polyline (pts {p}) (stroke (width {w}) (type {typ})) (fill (type none)))"

def arc(s, m, e, w=0.254):
    return f"(arc (start {s[0]} {s[1]}) (mid {m[0]} {m[1]}) (end {e[0]} {e[1]}) (stroke (width {w}) (type default)) (fill (type none)))"

def rect(a, b, w=0.254, fill="none"):
    return f"(rectangle (start {a[0]} {a[1]}) (end {b[0]} {b[1]}) (stroke (width {w}) (type default)) (fill (type {fill})))"

def winding(x, side, y0=-5.08, y1=5.08, n=4):
    """n humps of a coil on vertical line x, bulging toward side (-1 left, +1 right)."""
    out = []
    h = (y1 - y0) / n
    for i in range(n):
        ya = y0 + i * h; yb = ya + h; ym = (ya + yb) / 2
        out.append(arc((x, ya), (x + side * h / 2, ym), (x, yb)))
    return out

def core_dashed():
    return [poly([(-0.635, -6.35), (-0.635, 6.35)], typ="dash"), poly([(0.635, -6.35), (0.635, 6.35)], typ="dash")]

def symbol(name, ref, value, descr, keywords, fp, graphics, pins, ref_at=(0, 10.16), val_at=(0, -10.16), power=False, extra_props=()):
    g = "\n\t\t\t".join(graphics)
    p = "\n\t\t\t".join(pins)
    props = [prop("Reference", ref, *ref_at), prop("Value", value, *val_at), prop("Footprint", fp, 0, 0, hide=True),
             prop("Datasheet", "", 0, 0, hide=True), prop("Description", descr, 0, 0, hide=True),
             prop("ki_keywords", keywords, 0, 0, hide=True)] + list(extra_props)
    pr = "\n\t\t".join(props)
    return f"""	(symbol "{name}"
		{"(power)" if power else ""}
		(pin_names (offset 1.016)) (exclude_from_sim no) (in_bom {"no" if power else "yes"}) (on_board {"no" if power else "yes"})
		{pr}
		(symbol "{name}_0_1"
			{g}
		)
		(symbol "{name}_1_1"
			{p}
		)
		(embedded_fonts no)
	)"""

syms = []

# --- Xicon 42IF10x IF transformer (tapped tuned primary 1-2-3, secondary 4-6, pin 5 unused)
def ift_graphics(with_cap):
    g = []
    g += winding(-2.54, -1)
    g += winding(2.54, +1, y0=-2.54, y1=2.54, n=2)
    g += core_dashed()
    g += [poly([(-5.08, 5.08), (-2.54, 5.08)]), poly([(-5.08, -5.08), (-2.54, -5.08)]), poly([(-5.08, 0), (-2.54, 0)])]
    g += [poly([(2.54, 2.54), (2.54, 5.08), (5.08, 5.08)]), poly([(2.54, -2.54), (2.54, -5.08), (5.08, -5.08)])]
    if with_cap:  # internal 180pF across 1-3, drawn like the Xicon datasheet
        g += [poly([(-4.445, 5.08), (-4.445, 3.302)]), poly([(-5.207, 3.302), (-3.683, 3.302)]),
              poly([(-5.207, 2.54), (-3.683, 2.54)]), poly([(-4.445, 2.54), (-4.445, -5.08)])]
    # shield can outline
    g += [rect((-6.35, 7.62), (6.35, -7.62), w=0.127)]
    return g

ift_pins = [pin("passive", -7.62, 5.08, 0, "1"), pin("passive", -7.62, 0, 0, "2"), pin("passive", -7.62, -5.08, 0, "3"),
            pin("passive", 7.62, 5.08, 180, "4"), pin("no_connect", 7.62, 0, 180, "5", hide=True), pin("passive", 7.62, -5.08, 180, "6")]

syms.append(symbol("Xicon_42IF10x_IFT", "T", "42IF10x",
                   "Xicon 42IF10x 455kHz IF transformer, 10mm can. Pins 1-3 tuned tapped primary (2 = tap, 180pF internal), 4-6 secondary. Yellow=42IF101 (1st), White=42IF102 (2nd), Black=42IF103 (3rd)",
                   "IF transformer 455kHz AM superhet xicon", "audio:Xicon_42IF10x", ift_graphics(True), ift_pins,
                   ref_at=(0, 8.89), val_at=(0, -8.89)))
syms.append(symbol("Xicon_42IF110_OscCoil", "L", "42IF110",
                   "Xicon 42IF110 AM local oscillator coil (red), 10mm can. Pins 1-3 tapped tank winding (2 = tap), 4-6 feedback winding",
                   "oscillator coil AM superhet local oscillator xicon red", "audio:Xicon_42IF10x", ift_graphics(False), ift_pins,
                   ref_at=(0, 8.89), val_at=(0, -8.89)))

# --- Xicon 42TU audio transformers, 6 pin. Primary 1-2-3 (2 = CT, exits top), secondary 4-5-6 (5 = CT, exits bottom)
def tu_graphics(sec_ct):
    g = []
    g += winding(-2.54, -1)
    g += winding(2.54, +1)
    g += core_dashed()
    g += [poly([(-5.08, 5.08), (-2.54, 5.08)]), poly([(-5.08, -5.08), (-2.54, -5.08)])]
    g += [poly([(-2.54, 0), (-1.27, 0), (-1.27, 6.35)])]                       # primary CT lead up to pin 2
    g += [poly([(2.54, 5.08), (5.08, 5.08)]), poly([(2.54, -5.08), (5.08, -5.08)])]
    if sec_ct:
        g += [poly([(2.54, 0), (1.27, 0), (1.27, -6.35)])]                     # secondary CT lead down to pin 5
    g += [rect((-6.35, 7.62), (6.35, -7.62), w=0.127)]
    return g

tu_pins_ct = [pin("passive", -7.62, 5.08, 0, "1"), pin("passive", -1.27, 8.89, 270, "2"), pin("passive", -7.62, -5.08, 0, "3"),
              pin("passive", 7.62, 5.08, 180, "4"), pin("passive", 1.27, -8.89, 90, "5"), pin("passive", 7.62, -5.08, 180, "6")]
tu_pins_nc = [pin("passive", -7.62, 5.08, 0, "1"), pin("passive", -1.27, 8.89, 270, "2"), pin("passive", -7.62, -5.08, 0, "3"),
              pin("passive", 7.62, 5.08, 180, "4"), pin("no_connect", 1.27, -8.89, 90, "5", hide=True), pin("passive", 7.62, -5.08, 180, "6")]
syms.append(symbol("Xicon_42TU013_1kCT-8CT", "T", "42TU013-RC",
                   "Xicon 42TU013-RC audio transformer 1k ohm CT : 8 ohm CT, EI-24 6-pin PCB mount. Pins 1-2-3 primary (2 = CT), 4-5-6 secondary (5 = CT)",
                   "audio transformer driver push-pull xicon", "audio:Xicon_42TU200-RC", tu_graphics(True), tu_pins_ct,
                   ref_at=(0, 10.16), val_at=(0, -10.16)))
syms.append(symbol("Xicon_42TU200_200CT-8", "T", "42TU200-RC",
                   "Xicon 42TU200-RC audio output transformer 200 ohm CT : 8 ohm, EI-24 6-pin PCB mount. Pins 1-2-3 primary (2 = CT), 4-6 secondary",
                   "audio transformer output push-pull speaker xicon", "audio:Xicon_42TU200-RC", tu_graphics(False), tu_pins_nc,
                   ref_at=(0, 10.16), val_at=(0, -10.16)))

# --- 2-gang polyvaricon: 3 = O (oscillator gang), 1 = A (antenna gang), 2 = G common
vc_g = []
for x in (-2.54, 2.54):
    vc_g += [poly([(x - 1.524, 0.635), (x + 1.524, 0.635)], w=0.381), poly([(x - 1.524, -0.635), (x + 1.524, -0.635)], w=0.381),
             poly([(x, 2.54), (x, 0.635)]), poly([(x, -0.635), (x, -2.54)]),
             poly([(x - 1.905, -1.905), (x + 1.905, 1.905)]),                              # variable arrow
             poly([(x + 1.905, 1.905), (x + 0.9, 1.7)]), poly([(x + 1.905, 1.905), (x + 1.7, 0.9)])]
vc_g += [poly([(-2.54, -2.54), (2.54, -2.54)]), poly([(0, -2.54), (0, -2.54)]), poly([(-2.54, 1.905), (2.54, 1.905)], typ="dash")]
vc_pins = [pin("passive", -2.54, 5.08, 270, "3", "O"), pin("passive", 2.54, 5.08, 270, "1", "A"), pin("passive", 0, -5.08, 90, "2", "G")]
syms.append(symbol("Polyvaricon_2G_AM", "VC", "CBM-223P",
                   "2-gang polyvaricon AM tuning capacitor (e.g. CBM-223P: 140pF antenna + 60pF oscillator, trimmers built in). A = antenna gang, O = oscillator gang, G = common/frame",
                   "variable capacitor tuning polyvaricon varicap AM", "audio:Polyvaricon_CBM-223P_Wired", vc_g, vc_pins,
                   ref_at=(5.08, 1.27), val_at=(5.08, -1.27)))

# --- Ferrite rod antenna coil: 1-2 tuned primary, 3-4 low-Z secondary
fa_g = winding(-2.54, -1) + winding(2.54, +1, y0=-2.54, y1=2.54, n=2)
fa_g += [rect((-1.016, 6.35), (1.016, -6.35), w=0.254, fill="outline")]
fa_g += [poly([(-5.08, 5.08), (-2.54, 5.08)]), poly([(-5.08, -5.08), (-2.54, -5.08)]),
         poly([(2.54, 2.54), (2.54, 5.08), (5.08, 5.08)]), poly([(2.54, -2.54), (2.54, -5.08), (5.08, -5.08)])]
fa_pins = [pin("passive", -7.62, 5.08, 0, "1"), pin("passive", -7.62, -5.08, 0, "2"), pin("passive", 7.62, 5.08, 180, "3"), pin("passive", 7.62, -5.08, 180, "4")]
syms.append(symbol("Ferrite_Rod_Antenna_Coil", "L", "AM loopstick",
                   "AM broadcast ferrite rod (loopstick) antenna coil. 1-2 = tuned primary (~330-600uH, resonates with 140pF gang), 3-4 = low impedance coupling secondary",
                   "antenna ferrite rod loopstick AM coil", "audio:Ferrite_Rod_Antenna_Coil", fa_g, fa_pins,
                   ref_at=(0, 8.89), val_at=(0, -8.89)))

# --- V_RF power symbol (decoupled RF/IF supply rail), modelled on power:+BATT
syms.append(symbol("V_RF", "#PWR", "V_RF", "Power symbol: decoupled supply rail for converter and IF stages", "power-flag",
                   "", [poly([(-0.762, 1.27), (0, 2.54)], w=0), poly([(0, 0), (0, 2.54)], w=0), poly([(0, 2.54), (0.762, 1.27)], w=0)],
                   [pin("power_in", 0, 0, 90, "1", "V_RF", length=0, hide=True)], ref_at=(0, -3.81), val_at=(0, 3.556), power=True))

# keep the user's original IF_Transformer_AM symbol for reference
orig = open(f"{PROJ}/audio.kicad_sym").read()
m = re.search(r'\t\(symbol "IF_Transformer_AM".*?\n\t\)\n', orig, re.S)
orig_sym = m.group(0) if m else ""

lib = "(kicad_symbol_lib\n\t(version 20241209)\n\t(generator \"kicad_symbol_editor\")\n\t(generator_version \"9.0\")\n" + orig_sym + "\n".join(syms) + "\n)\n"
open(f"{PROJ}/audio.kicad_sym", "w").write(lib)
print("wrote audio.kicad_sym", len(syms) + (1 if orig_sym else 0), "symbols")

# ---------------------------------------------------------------- footprints
def fp_text(kind, val, x, y, layer, size=1.0, thick=0.15, hide=False):
    return f'''	(property "{kind}" "{val}"
		(at {x} {y} 0) (layer "{layer}"){" (hide yes)" if hide else ""} (uuid "{U()}")
		(effects (font (size {size} {size}) (thickness {thick})))
	)'''

def fp_line(a, b, layer, w):
    return f'	(fp_line (start {a[0]} {a[1]}) (end {b[0]} {b[1]}) (stroke (width {w}) (type solid)) (layer "{layer}") (uuid "{U()}"))'

def fp_rect(a, b, layer, w):
    return f'	(fp_rect (start {a[0]} {a[1]}) (end {b[0]} {b[1]}) (stroke (width {w}) (type solid)) (fill no) (layer "{layer}") (uuid "{U()}"))'

def fp_circle(c, r, layer, w):
    return f'	(fp_circle (center {c[0]} {c[1]}) (end {c[0]+r} {c[1]}) (stroke (width {w}) (type solid)) (fill no) (layer "{layer}") (uuid "{U()}"))'

def fp_txt(val, x, y, layer, size=0.8, thick=0.12):
    return f'''	(fp_text user "{val}" (at {x} {y} 0) (layer "{layer}") (uuid "{U()}")
		(effects (font (size {size} {size}) (thickness {thick})))
	)'''

def pad(num, shape, x, y, sx, sy, drill, npth=False):
    if npth:
        return f'	(pad "" np_thru_hole {shape} (at {x} {y}) (size {sx} {sy}) (drill {drill}) (layers "*.Cu" "*.Mask") (uuid "{U()}"))'
    return f'	(pad "{num}" thru_hole {shape} (at {x} {y}) (size {sx} {sy}) (drill {drill}) (layers "*.Cu" "*.Mask") (remove_unused_layers no) (uuid "{U()}"))'

def footprint(name, descr, tags, items, ref_y, val_y):
    body = "\n".join(items)
    return f'''(footprint "{name}"
	(version 20241229) (generator "pcbnew") (generator_version "9.0")
	(layer "F.Cu")
	(descr "{descr}")
	(tags "{tags}")
{fp_text("Reference", "REF**", 0, ref_y, "F.SilkS")}
{fp_text("Value", name, 0, val_y, "F.Fab")}
{fp_text("Datasheet", "", 0, 0, "F.Fab", hide=True)}
{fp_text("Description", "", 0, 0, "F.Fab", hide=True)}
	(attr through_hole)
{body}
{fp_text("Reference", "${REFERENCE}", 0, 0, "F.Fab", size=0.8, thick=0.12).replace('(property "Reference"', '(fp_text user').replace('"${REFERENCE}"', '"${REFERENCE}"')}
	(embedded_fonts no)
)
'''

os.makedirs(f"{PROJ}/audio.pretty", exist_ok=True)

# Xicon 42IF10x: 0.4" (10.16) square can, two rows 0.27" (6.858) apart, 3 positions per row on 0.135" (3.429) pitch
p = 3.429; r = 3.429
items = [pad("1", "rect", -p, -r, 1.5, 1.5, 0.8), pad("2", "circle", 0, -r, 1.5, 1.5, 0.8), pad("3", "circle", p, -r, 1.5, 1.5, 0.8),
         pad("6", "circle", -p, r, 1.5, 1.5, 0.8), pad("5", "circle", 0, r, 1.5, 1.5, 0.8), pad("4", "circle", p, r, 1.5, 1.5, 0.8),
         fp_rect((-5.08, -5.08), (5.08, 5.08), "F.SilkS", 0.12), fp_rect((-5.08, -5.08), (5.08, 5.08), "F.Fab", 0.1),
         fp_rect((-5.6, -5.6), (5.6, 5.6), "F.CrtYd", 0.05),
         fp_line((-5.08, -3.0), (-3.0, -5.08), "F.Fab", 0.1),   # pin-1 corner chamfer
         fp_txt("1", -5.9, -3.429, "F.SilkS", 0.8, 0.12), fp_txt("3", 5.9, -3.429, "F.SilkS", 0.8, 0.12)]
open(f"{PROJ}/audio.pretty/Xicon_42IF10x.kicad_mod", "w").write(footprint(
    "Xicon_42IF10x", "Xicon 42IF101/102/103 IF transformer and 42IF110 oscillator coil, 10.16mm square shielded can, 6 pins (3+3) on 3.43mm pitch, rows 6.86mm apart. Pins 1-2-3 primary (2 = tap), 4-(5)-6 secondary. Datasheet XC-600131",
    "IF transformer 455kHz oscillator coil xicon 42IF", items, -6.5, 6.5))

# Polyvaricon CBM-223P (20 x 20 x 11 mm body), wired: three solder pads along the bottom edge + two 2.7mm holes for M2.5 mounting screws.
items = [pad("3", "oval", -6.0, 8.5, 2.6, 1.8, 1.1), pad("2", "oval", 0.0, 8.5, 2.6, 1.8, 1.1), pad("1", "oval", 6.0, 8.5, 2.6, 1.8, 1.1),
         pad("", "circle", -7.5, -7.5, 2.7, 2.7, 2.7, npth=True), pad("", "circle", 7.5, -7.5, 2.7, 2.7, 2.7, npth=True),
         fp_rect((-10.0, -10.0), (10.0, 10.0), "F.SilkS", 0.12), fp_rect((-10.0, -10.0), (10.0, 10.0), "F.Fab", 0.1),
         fp_circle((0, 0), 3.0, "F.Fab", 0.1), fp_rect((-10.5, -10.5), (10.5, 10.5), "F.CrtYd", 0.05),
         fp_txt("O", -6.0, 6.7, "F.SilkS", 0.8, 0.12), fp_txt("G", 0.0, 6.7, "F.SilkS", 0.8, 0.12), fp_txt("A", 6.0, 6.7, "F.SilkS", 0.8, 0.12),
         fp_txt("TUNING", 0, -6.0, "F.SilkS", 1.0, 0.15)]
open(f"{PROJ}/audio.pretty/Polyvaricon_CBM-223P_Wired.kicad_mod", "w").write(footprint(
    "Polyvaricon_CBM-223P_Wired", "2-gang AM polyvaricon (CBM-223P type, 20x20x11mm). Body sits on the board, shaft up; the three terminals are bent/wired to pads O (oscillator), G (common), A (antenna). Two 2.7mm holes for M2.5 screws - VERIFY against your part before fabrication",
    "variable capacitor polyvaricon tuning AM", items, -11.5, 11.5))

# Ferrite rod antenna coil: 4 pads (2.54) + rod outline + zip-tie holes
items = [pad("1", "rect", 0, -3.81, 1.7, 1.7, 1.0), pad("2", "circle", 0, -1.27, 1.7, 1.7, 1.0), pad("3", "circle", 0, 1.27, 1.7, 1.7, 1.0), pad("4", "circle", 0, 3.81, 1.7, 1.7, 1.0),
         pad("", "circle", 14, -7.0, 2.2, 2.2, 2.2, npth=True), pad("", "circle", 14, 7.0, 2.2, 2.2, 2.2, npth=True),
         pad("", "circle", 50, -7.0, 2.2, 2.2, 2.2, npth=True), pad("", "circle", 50, 7.0, 2.2, 2.2, 2.2, npth=True),
         fp_rect((4.0, -5.0), (62.0, 5.0), "F.SilkS", 0.12), fp_rect((4.0, -5.0), (62.0, 5.0), "F.Fab", 0.1),
         fp_rect((-1.5, -8.5), (63.0, 8.5), "F.CrtYd", 0.05),
         fp_txt("FERRITE ROD ANTENNA (tie down here)", 33, 0, "F.SilkS", 1.0, 0.15),
         fp_txt("1 2 3 4", -2.6, 0, "F.SilkS", 0.8, 0.12)]
# rotate the small pin-number text to run along the pads
items[-1] = items[-1].replace("(at -2.6 0 0)", "(at -2.6 0 90)")
open(f"{PROJ}/audio.pretty/Ferrite_Rod_Antenna_Coil.kicad_mod", "w").write(footprint(
    "Ferrite_Rod_Antenna_Coil", "AM ferrite rod (loopstick) antenna coil, up to ~60mm rod laid on the board and secured with cable ties through the 2.2mm holes. Coil leads to pads 1-2 (tuned primary) and 3-4 (secondary)",
    "antenna ferrite rod loopstick AM coil", items, -10.0, 10.0))
print("wrote 3 footprints")
