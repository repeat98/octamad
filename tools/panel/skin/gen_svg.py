# SPDX-License-Identifier: MIT
# From markandrus/octemu (assets/panel/gen_svg.py, MIT, Copyright (c) 2026 Mark
# Roberts); octabam adds the `dark` palette (the default) and an output dir.
# Generates octatrack.svg — Elektron Octatrack MK2 top panel, all controls in
# default (unlit) state, with CSS hooks for conditional lighting and a 2:1
# (128x64-ratio) screen cutout. Geometry measured from the 1250x682 base image;
# colors and label hierarchy taken from the octaface.jpg reference.

import sys, pathlib

W, H = 1250, 682
# ---- palettes ------------------------------------------------------------
# `grey`: octemu's own (Mark Roberts). `dark` (octabam's default): the MKII's
# black anodised face from Elektron's product photo -- the plate, the print
# (white names, mid-grey secondary labels, darker grey FUNC labels), the
# keys and knobs unchanged.
PALETTES = {
    'grey': dict(PLATE='#828486', CHASSIS='#2b2c2e', INK_HI='#ebeced', INK_MID='#b6b8b9', INK_DK='#2f3032'),
    'dark': dict(PLATE='#1e1f21', CHASSIS='#101012', INK_HI='#e4e4e4', INK_MID='#9c9da0', INK_DK='#76777a'),
}
ARGS = [a for a in sys.argv[1:] if not a.startswith('--')]
PAL = PALETTES['grey' if '--grey' in sys.argv else 'dark']
OUTDIR = pathlib.Path(ARGS[0]) if ARGS else pathlib.Path('.')
PLATE, CHASSIS = PAL['PLATE'], PAL['CHASSIS']
INK_HI, INK_MID, INK_DK = PAL['INK_HI'], PAL['INK_MID'], PAL['INK_DK']
parts = []
add = parts.append
REG = {'buttons': {}, 'knobs': {}, 'leds': {}}

FONT = "'Helvetica Neue', Helvetica, Arial, sans-serif"

add(f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="{FONT}">
<defs>
  <filter id="glow" x="-40%" y="-40%" width="180%" height="180%">
    <feGaussianBlur stdDeviation="1.4" result="b"/>
    <feColorMatrix in="b" type="matrix"
      values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 0.55 0" result="b2"/>
    <feMerge><feMergeNode in="b2"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
</defs>
<style>
  text {{ user-select: none; font-weight: 600; text-anchor: middle; }}
  .hi  {{ fill:{INK_HI}; }}   /* near-white print   */
  .mid {{ fill:{INK_MID}; }}  /* lighter-gray print */
  .dk  {{ fill:{INK_DK}; }}   /* near-black print   */
  .t10 {{ font-size:10.5px; }}
  .t9  {{ font-size:9.5px; }}
  .cap-txt {{ fill:#e8e8e8; }}

  /* ---- lighting API -------------------------------------------------
     Add class "lit" to any .key / .led group to light it up.
     Color: set --lit inline, or add a helper class:
       .lit-red (default) | .lit-green | .lit-yellow                    */
  .lit-red    {{ --lit:#ff5340; }}
  .lit-green  {{ --lit:#b5e8bf; }}
  .lit-yellow {{ --lit:#ffd23e; }}
  /* The square ring is PRINT that exists only on trigs 1/5/9/13 (.marked).
     It stays transparent on every other key, lit or not, so toggling "lit"
     never changes geometry — only colors. */
  .key .ring {{ fill:none; stroke:transparent; stroke-width:2.5; }}
  .key.marked .ring {{ stroke:#e8e8e8; }}
  .key.marked.lit .ring {{ stroke:var(--lit,#ff5340); filter:url(#glow); }}
  .key.lit .cap-txt {{ fill:var(--lit,#ff5340); filter:url(#glow); }}
  .key .u {{ fill:#e8e8e8; }}
  .key.lit .u {{ fill:var(--lit,#ff5340); filter:url(#glow); }}
  /* icons: outline glyphs stay outline-only when lit (e.g. record circle) */
  .key .icon {{ fill:none; stroke:#e8e8e8; stroke-width:2.6; }}
  .key.lit .icon {{ stroke:var(--lit,#ff5340); filter:url(#glow); }}
  .led circle.core {{ fill:#3a3a3c; }}
  .led.lit circle.core {{ fill:var(--lit,#ff5340); filter:url(#glow); }}
</style>
''')

# ---------------------------------------------------------------- chassis
# The face plate, inset in the dark chassis. Everything printed or lit lives
# on this rectangle; the surround is the machine's edge. It is published in
# the registry because a GIF of the panel crops to it — see REG['plate'].
PLATE_RECT = (34, 35, 1177, 611)
add(f'<rect width="{W}" height="{H}" fill="{CHASSIS}"/>')
add(f'<rect x="{PLATE_RECT[0]}" y="{PLATE_RECT[1]}" width="{PLATE_RECT[2]}" '
    f'height="{PLATE_RECT[3]}" fill="{PLATE}"/>')

# ---------------------------------------------------------------- screws
def screw(x, y, r=9.5):
    """Hex-socket button-head bolt holding the face plate."""
    import math
    hr = r * 0.42
    pts = ' '.join(f'{x+hr*math.cos(math.radians(a)):.1f},{y+hr*math.sin(math.radians(a)):.1f}'
                   for a in range(0, 360, 60))
    add(f'<g class="bolt">'
        f'<circle cx="{x+1}" cy="{y+2}" r="{r}" fill="#000" opacity="0.25"/>'
        f'<circle cx="{x}" cy="{y}" r="{r}" fill="#333436"/>'
        f'<path d="M {x-r} {y} a {r} {r} 0 0 1 {2*r} 0" fill="#3f4042"/>'
        f'<circle cx="{x}" cy="{y}" r="{r*0.66}" fill="#161618"/>'
        f'<polygon points="{pts}" fill="#050506"/>'
        f'<circle cx="{x-r*0.42}" cy="{y-r*0.52}" r="{r*0.14}" fill="#6a6b6d"/></g>')
for sx, sy in [(70,53),(601,53),(1178,53),(70,627),(601,627),(1178,628)]:
    screw(sx, sy)

# ---------------------------------------------------------------- helpers
def key(id_, x, y, w, h, label=None, fs=13, cls='key', face='#2c2d2f',
        skirt='#0d0d0f', bevel='#47484a', txt_fill=None, icon=None, extra=None):
    """Raised keycap: shadow + skirt + inset flat top face + top bevel highlight."""
    g = [f'<g class="{cls}" id="{id_}">']
    g.append(f'<rect x="{x+1.5}" y="{y+3.5}" width="{w-1}" height="{h-2}" rx="8" fill="#000" opacity="0.3"/>')
    g.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="7" fill="{skirt}"/>')
    g.append(f'<rect x="{x+3}" y="{y+2.5}" width="{w-6}" height="{h-8}" rx="5" fill="{face}"/>')
    g.append(f'<path d="M {x+8} {y+4.3} H {x+w-8}" stroke="{bevel}" stroke-width="1.3" stroke-linecap="round" fill="none"/>')
    g.append(f'<rect class="ring" x="{x+7.5}" y="{y+7}" width="{w-15}" height="{h-17}" rx="3.5"/>')
    if label is not None:
        tf = f' style="fill:{txt_fill}"' if txt_fill else ''
        g.append(f'<text class="cap-txt" x="{x+w/2}" y="{y+h/2-1.5+fs*0.36}" font-size="{fs}"{tf}>{label}</text>')
    if icon:
        g.append(icon)
    if extra:
        g.append(extra)
    g.append('</g>')
    add(''.join(g))
    REG['buttons'][id_] = {'x': x, 'y': y, 'w': w, 'h': h,
                           'marked': 'marked' in cls, 'label': label}

def knob(id_, cx, cy, r, pointer=False):
    """Cylinder seen from above: shadow, dark side wall, lighter top face offset up-left."""
    fx, fy = cx - r*0.10, cy - r*0.12
    g = [f'<g id="{id_}">',
         f'<circle cx="{cx+r*0.10}" cy="{cy+r*0.14}" r="{r}" fill="#000" opacity="0.3"/>',
         f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#1d1e20"/>',
         f'<circle cx="{fx}" cy="{fy}" r="{r*0.85}" fill="#333437"/>']
    if pointer:
        g.append(f'<circle class="pointer" cx="{fx-r*0.42}" cy="{fy-r*0.42}" r="2.6" fill="{INK_HI}"/>')
    g.append('</g>')
    add(''.join(g))
    REG['knobs'][id_] = {'cx': cx, 'cy': cy, 'r': r,
                         'face_cx': fx, 'face_cy': fy, 'face_r': r*0.85,
                         'has_pointer': pointer}

def led(id_, cx, cy, r=6.5):
    add(f'<g class="led" id="{id_}">'
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#1c1c1e"/>'
        f'<circle class="core" cx="{cx}" cy="{cy}" r="{r-2}"/></g>')
    REG['leds'][id_] = {'cx': cx, 'cy': cy, 'r': r}

def lbl(x, y, lines, color='hi', size='t10', dy=11):
    for i, ln in enumerate(lines if isinstance(lines, (list, tuple)) else [lines]):
        c = color[i] if isinstance(color, (list, tuple)) else color
        add(f'<text class="{c} {size}" x="{x}" y="{y+i*dy}">{ln}</text>')

# ---------------------------------------------------------------- top labels
add('<g id="rear-labels">')
add(f'<path d="M 89 52 a 6.5 6.5 0 0 1 13 0" fill="none" stroke="{INK_MID}" stroke-width="2"/>'
    f'<rect x="87.5" y="50" width="3.6" height="6.5" rx="1.6" fill="{INK_MID}"/>'
    f'<rect x="99.9" y="50" width="3.6" height="6.5" rx="1.6" fill="{INK_MID}"/>')
for x, t in [(160,'Main Out'),(220,'Cue Out'),(288,'Input A B'),(348,'Input C D'),
             (422,'MIDI In'),(491,'MIDI Out'),(560,'MIDI Thru'),(729,'Compact Flash'),
             (867,'USB'),(1006,'DC In'),(1106,'Power')]:
    lbl(x, 54, t, 'mid')
lbl(781, 95, 'Card Status', 'mid')
add('</g>')
led('led-card-status', 783, 79)

# ---------------------------------------------------------------- left cluster
knob('knob-phones', 115.5, 148, 22.5, pointer=True)
lbl(113, 181, 'Headphones Vol')

key('btn-midi', 69, 205, 40, 39, 'MIDI', fs=11)
lbl(89, 254, 'MIDI Sync')

for i, (x, id_) in enumerate([(185.5,'led-in-a'),(213.5,'led-in-b'),(241,'led-in-c'),
                              (269,'led-in-d'),(296.5,'led-int-l'),(324,'led-int-r')]):
    led(id_, x, 165.5)
lbl(198, 150, 'A — B'); lbl(253, 150, 'C — D'); lbl(309, 150, '- Int -')

key('btn-rec1', 180, 184, 39, 39, 'REC1', fs=10)
key('btn-rec2', 235, 184, 40, 39, 'REC2', fs=10)
key('btn-rec3', 291, 184, 39, 39, 'REC3', fs=10)
lbl(199, 233, ['Setup 1','Pickup +'], ['hi','mid'], 't9', 10.5)
lbl(254, 233, ['Setup 2','Pickup ▸/▪'], ['hi','mid'], 't9', 10.5)
lbl(309, 233, ['Rec Edit','Erase'], ['hi','mid'], 't9', 10.5)
led('led-rec-status', 310, 255)
# short tick between the rec-status LED and the ARR button below it
add(f'<rect x="{310-0.75}" y="264" width="1.5" height="7" fill="{INK_MID}"/>')

key('btn-proj', 69, 274, 40, 39, 'PROJ', fs=10)
key('btn-part', 125, 274, 39, 39, 'PART', fs=10)
key('btn-aed',  180, 274, 39, 39, 'AED',  fs=10)
key('btn-mix',  235, 274, 40, 39, 'MIX',  fs=10)
key('btn-arr',  291, 274, 39, 39, 'ARR',  fs=10)
lbl(88, 323, 'Save Proj'); lbl(143, 323, 'Part Edit'); lbl(199, 323, 'Slice Grid')
lbl(254, 323, 'Click');    lbl(309, 323, 'Arr Mode')

key('btn-func', 71, 364, 60, 39, 'FUNC', fs=11, face='#e6e6e7',
    skirt='#a0a1a2', bevel='#f8f8f8', txt_fill='#1a1a1a')
key('btn-cue',  169, 364, 61, 39, 'CUE', fs=11)
lbl(199, 413, 'Reload Part')

key('btn-ptn',  69, 447, 62, 39, 'PTN', fs=11)
key('btn-bank', 169, 447, 61, 39, 'BANK', fs=10)
lbl(100, 496, 'Pattern Settings'); lbl(200, 496, 'Track Trig Edit')

# ---------------------------------------------------------------- nav keys
key('btn-yes', 267, 391, 39, 39, 'YES', fs=10)
key('btn-up', 377, 391, 40, 39,
    icon='<path class="icon" d="M 389 415 l 8 -9 l 8 9" stroke-linecap="round" stroke-linejoin="round"/>')
key('btn-no', 267, 447, 39, 39, 'NO', fs=10)
key('btn-left', 322, 447, 39, 39,
    icon='<path class="icon" d="M 346 458 l -9 8.5 l 9 8.5" stroke-linecap="round" stroke-linejoin="round"/>')
key('btn-down', 377, 447, 40, 39,
    icon='<path class="icon" d="M 389 462 l 8 9 l 8 -9" stroke-linecap="round" stroke-linejoin="round"/>')
key('btn-right', 433, 447, 39, 39,
    icon='<path class="icon" d="M 448 458 l 9 8.5 l -9 8.5" stroke-linecap="round" stroke-linejoin="round"/>')
lbl(286, 441, 'Arm'); lbl(397, 441, 'Trig Mode')
lbl(285, 496, 'Disarm'); lbl(341, 496, 'µTime -', 'dk')
lbl(397, 496, 'Trig Mode'); lbl(452, 496, 'µTime +', 'dk')

# ---------------------------------------------------------------- transport
key('btn-rec', 529, 447, 62, 39,
    icon='<circle class="icon" cx="560" cy="466.5" r="9"/>')
key('btn-play', 595, 447, 62, 39,
    icon='<path class="icon" d="M 620 458 l 14 8.5 l -14 8.5 Z" stroke-linejoin="round"/>')
key('btn-stop', 661, 447, 61, 39,
    icon='<rect class="icon" x="684" y="459" width="15" height="15" rx="2"/>')
lbl(559, 496, 'Copy'); lbl(624, 496, 'Clear'); lbl(689, 496, 'Paste')

# ---------------------------------------------------------------- track keys
for i, y in enumerate([128, 184, 239, 294]):
    key(f'btn-t{i+1}', 398, y, 39, 40, f'T{i+1}', fs=12)
    key(f'btn-t{i+5}', 749, y, 39, 40, f'T{i+5}', fs=12)
# "Cue/" dark, "Mute" light
for y in [178, 233.5, 288.5, 343.5]:
    for x in (417, 767):
        add(f'<text class="t9" x="{x}" y="{y}"><tspan class="dk">Cue/</tspan>'
            f'<tspan class="mid">Mute</tspan></text>')

# ---------------------------------------------------------------- screen
SX, SY, SW, SH = 465, 134, 256, 193
add(f'<g id="display"><rect x="{SX}" y="{SY}" width="{SW}" height="{SH}" rx="4" fill="#0a0a0a"/>')
add(f'<text x="{SX+13}" y="{SY+27}" fill="#e8e8e8" font-size="9.5" '
    f'style="text-anchor:start;font-weight:400">8 Track Dynamic Performance Sampler</text>')
# --- screen cutout: 128 x 64 at exactly 2x (256 x 128), the window's full
# width, so every LCD pixel is a 2x2 block (octemu's 240 x 120 is 1.875x).
add(f'<rect id="screen" x="{SX}" y="{SY+33}" width="256" height="128" fill="#060607"/>')
add(f'<text x="{SX+13}" y="{SY+180}" fill="#e8e8e8" font-size="17" '
    f'style="text-anchor:start">octabam <tspan style="font-weight:400">MKII</tspan></text>')
add('</g>')

# ---------------------------------------------------------------- page keys row (SRC..FX2)
for x, id_, t in [(463,'btn-src','SRC'),(518,'btn-amp','AMP'),(573,'btn-lfo','LFO'),
                  (629,'btn-fx1','FX1'),(684,'btn-fx2','FX2')]:
    key(id_, x, 347, 39.5, 40, t, fs=10)
lbl(481, 397, 'Note', 'mid'); lbl(536, 397, 'Arp', 'mid'); lbl(592, 397, 'LFO', 'mid')
lbl(646, 397, 'Ctrl 1', 'mid'); lbl(702, 397, 'Ctrl 2', 'mid')
# "Setup" sits in a gap at the middle of the line spanning Note..Ctrl 2
add(f'<path d="M 462 411 H 570 M 614 411 H 722" stroke="{INK_HI}" stroke-width="1.2" fill="none"/>')
lbl(592, 414.5, 'Setup')

# ---------------------------------------------------------------- encoders
lbl(879, 219, 'Level', 'hi', 't9'); lbl(879, 230, 'Cursor Pos', 'mid', 't9')
for x, a, b in [(972,'A','Start Pos'),(1066,'B','Loop Pos'),(1159,'C','End Pos')]:
    lbl(x, 219, a, 'hi', 't9'); lbl(x, 230, b, 'mid', 't9')
knob('knob-level', 879.5, 184.5, 22.5)
knob('knob-a', 972.5, 184.5, 22.5)
knob('knob-b', 1066, 184.5, 23)
knob('knob-c', 1159.5, 184.5, 22.5)
# icon traced from source pixels: rounded triangle, apex (877,269.5), base
# 871.5..886.5 at y 283.5; pendulum from mid-interior (879.5,278.5) out to
# its tip at (889.5,272.5), crossing the triangle's right side
key('btn-tempo', 860, 258, 39, 39,
    icon='<path class="icon" d="M 877 269.5 L 871.5 283.5 L 886.5 283.5 Z '
         'M 879.5 278.5 L 889.5 272.5" '
         'stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>')
knob('knob-d', 973, 277.5, 23)
knob('knob-e', 1066, 277.5, 23)
knob('knob-f', 1159.5, 277.5, 22.5)
lbl(879, 312, 'Tap Tempo', 'hi', 't9'); lbl(879, 323, 'Pickup Sync', 'dk', 't9')
lbl(971, 312, 'D', 'hi', 't9'); lbl(967, 323, 'Zoom', 'mid', 't9')
add(f'<path d="M 985 314.5 l 3 -4.5 l 3 4.5 Z M 985 318.5 l 3 4.5 l 3 -4.5 Z" fill="{INK_MID}"/>')
lbl(1065, 312, 'E', 'hi', 't9'); lbl(1065, 323, 'Scroll ◂▸', 'mid', 't9')
lbl(1166, 312, 'F', 'hi', 't9'); lbl(1166, 323, 'Zoom ◂▸', 'mid', 't9')

# ---------------------------------------------------------------- crossfader + A/B
key('btn-a', 788, 408, 61, 61, 'A', fs=22)
key('btn-b', 1121, 408, 61, 61, 'B', fs=22)
lbl(818, 479, 'Mute', 'mid'); lbl(1152, 479, 'Mute', 'mid')
screw(872.5, 438.5); screw(1097.5, 438.5)
# tick marks — white; tall at ends/center, medium at quarters, short elsewhere
tall_t, med_t = [], []
for i in range(17):
    tx = 906 + i*10
    if i in (0, 8, 16):   h1, h2, bold = 22, 22, tall_t
    elif i in (4, 12):    h1, h2, bold = 16, 16, tall_t
    else:                 h1, h2, bold = 14, 14, med_t
    bold.append(f'M {tx} {421-h1} V 421')
    bold.append(f'M {tx} 450 V {450+h2}')
add(f'<path d="{" ".join(tall_t)}" stroke="{INK_HI}" stroke-width="2" fill="none"/>')
add(f'<path d="{" ".join(med_t)}" stroke="{INK_HI}" stroke-width="1.5" fill="none"/>')
# full-width slot; carriage + cap ride in it — translate #fader-handle in x
# to move the crossfader (range roughly 0..160)
add('<rect x="887" y="430" width="194" height="15.5" rx="7.5" fill="#141414"/>'
    '<rect x="890" y="433" width="188" height="9.5" rx="4.5" fill="#241010"/>')
add('<g id="fader-handle">'
    '<rect x="888.5" y="429.5" width="23" height="16.5" rx="5" fill="#1c1c1c"/>'
    # fader cap seen from above: wide base, smaller tapered top face inset
    # toward the center, white grip stripe across the top face
    '<rect x="882" y="404" width="36" height="68" rx="10" fill="#232426"/>'
    '<rect x="887.5" y="411" width="25" height="54" rx="7" fill="#3a3b3d"/>'
    '<rect x="897" y="404.5" width="6" height="67" rx="3" fill="#eeefef"/></g>')

# ---------------------------------------------------------------- page LEDs + PAGE key
# LED colors are fixed on the panel: 1:4 is yellow, the rest are red
led('led-page-1', 1124.5, 518, 6)
for i in range(1, 4):
    led(f'led-page-{i+1}', 1124.5 + i*19, 518, 6)
lbl(1124.5, 506, '1:4', 'hi', 't9'); lbl(1143.5, 506, '2:4', 'hi', 't9')
lbl(1162.5, 506, '3:4', 'hi', 't9'); lbl(1181.5, 506, '4:4', 'hi', 't9')
key('btn-page', 1121, 537, 61, 39, 'PAGE', fs=11)
lbl(1153, 590, 'Scale', 'mid')

# ---------------------------------------------------------------- trig keys 1-16
trig_x = [69,135,201,266,332,398,464,529,595,661,727,792,858,924,989,1055]
for i, x in enumerate(trig_x):
    marked = ' marked' if i % 4 == 0 else ''       # printed outline on 1, 5, 9, 13
    cx = x + 30.75
    underline = f'<rect class="u" x="{cx-8}" y="568.9" width="16" height="2.2" rx="1.1"/>'
    key(f'trig-{i+1}', x, 526, 61.5, 61, str(i+1), fs=20,
        cls='key trig' + marked, extra=underline)
for i, x in enumerate(trig_x[:8]):
    lbl(x+31, 598, f'T{i+1}', 'mid')
for i, x in enumerate(trig_x[8:]):
    lbl(x+31, 598, f'T{i+1}', 'mid')
add(f'<path d="M 69 601 v 5 H 591 v -5 M 330 606 v 4" fill="none" stroke="{INK_MID}" stroke-width="1.2"/>')
add(f'<path d="M 597 601 v 5 H 1116 v -5 M 856 606 v 4" fill="none" stroke="{INK_MID}" stroke-width="1.2"/>')
add(f'<rect x="288" y="608" width="86" height="12" fill="{PLATE}"/>')
add(f'<rect x="806" y="608" width="102" height="12" fill="{PLATE}"/>')
lbl(330, 617, 'Track Trigs', 'mid'); lbl(856, 617, 'Sample/MIDI Trigs', 'mid')

add('</svg>')

svg = '\n'.join(parts)
# bake the fixed page-LED colors
svg = svg.replace('id="led-page-1"', 'id="led-page-1" style="--lit:#ffd23e"')
for n in (2, 3, 4):
    svg = svg.replace(f'id="led-page-{n}"', f'id="led-page-{n}" style="--lit:#ff5340"')
(OUTDIR / 'octatrack.svg').write_text(svg)
print('wrote octatrack.svg', len(svg), 'bytes')

import json
REG['viewBox'] = [0, 0, W, H]
REG['plate'] = {'x': PLATE_RECT[0], 'y': PLATE_RECT[1],
                'w': PLATE_RECT[2], 'h': PLATE_RECT[3],
                'note': 'the face plate inside the chassis surround; a panel GIF is cropped to it'}
REG['screen'] = {'x': SX, 'y': SY+33, 'w': 256, 'h': 128,
                 'native': [128, 64], 'px_per_native_px': 2}
REG['fader'] = {'handle_id': 'fader-handle',
                'travel': {'axis': 'x', 'min': 0, 'max': 166},
                'slot': {'x': 887, 'y': 430, 'w': 194, 'h': 15.5},
                'note': 'translate #fader-handle in x; 0 = far left (default), 166 = far right'}
REG['led_fixed_colors'] = {'led-page-1': '#ffd23e', 'led-page-2': '#ff5340',
                           'led-page-3': '#ff5340', 'led-page-4': '#ff5340'}
(OUTDIR / 'octatrack-elements.json').write_text(json.dumps(REG, indent=1))
print('wrote octatrack-elements.json')
