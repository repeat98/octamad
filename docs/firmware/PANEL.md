# The panel: surface, fonts, text and regions (OS 1.40C, MKII)

Read out of `out/raw/section_3_MAIN_OS.bin` (SHA256 `164f3122…`), base
`0x40000400`, on 16 Sep 2026, while chasing why the arranger greys a field
out. This is the part of `MAINMENU.md` §8's "drawing primitives behind the
state table's draw functions" now read: enough to draw text, boxes and
shading of your own.

Static reading unless marked ✅. The one hardware fact is negative and cost
a flash: the formatting drawer's two spare arguments are **not** a shade
(§3). `0x40012368` (§4) was re-read from objdump on 16 Sep, by hand, not
run (🟡 where marked).

---

## 1. The surface — 128 × 64, four grey levels

The descriptor every UI call passes (`0x400bf10a`):

| offset | value | meaning |
|---|---|---|
| `+0` | `0x80` | width, 128 |
| `+4` | `0x40` | height, 64 |
| `+8` | `0x02` | **bits per pixel** |
| `+12` | `0x46c7e0ea` | the buffer every drawer writes |
| `+16` | `0x46c7ca38` | a second buffer |
| `+20`, `+24` | `0x90000000`, `0x10004008` | 🟡 unidentified |

Both buffers are 1,024 bytes = 128 × 64 ÷ 8: two 1-bit planes. ✅ `+12`
is the picture, and it is stored a quarter turn round: 64 columns × 128
rows, 8 bytes per row, MSB left, screen pixel (x, y) = column 63−y of row
x (rendered from a port dump under every candidate layout, 17 Sep 2026;
`ot_emu --lcd` + `tools/emu/lcd_view.py`, `EMU.md`). `+16` read as all
`0xff` after a boot and a load; the UI init at `0x40063264` clears both
with `0x40020950(buf, 0x400)` (a memset — ~~the refresh or DMA setup~~,
retracted 17 Sep) and then fills a 1,024-byte block from `0x40011804`
with `-1`. Every drawing routine below writes only `+12`. What sends the
plane to the panel controller over UART1 (`0xfc064000`; the byte queue is
`0x40010aa4`) is not located.

## 2. Fonts — metrics records, no colour

A font is a 20-byte record. Two are in use:

| | `0x400ba862` | `0x400ba876` |
|---|---|---|
| `+0` default advance | 5 | 3 |
| `+4` `(yOffset << 16) \| height` | `0/5` | `1/6` |
| `+8` | → per-glyph width table | ← |
| `+12` | → per-glyph offset table (signed words; negative = absent) | ← |
| `+16` | → the glyph bitmaps | ← |

Read off the **width-measuring** routine `0x40012f30(font, limit, str)`,
which walks a string adding `+8`'s per-glyph widths, falling back to `+0`
when a glyph has none, and skipping glyphs whose `+12` word is negative.

There is no colour or level anywhere in the record.

Eight such records sit at `0x400ba812 … 0x400ba89e` (nordseele, 22 Sep
2026): `0x400ba876` is the small UI font, 506 literal references in the
image (✅ counted here), `0x400ba83a` a large one (29 references). The two
in the table are the ones the text routines use; the other six are not
decoded.

## 3. Text — one bit, ORed, no intensity

Two entry points, both ultimately the same blitter:

```
0x40013904(font, surface, x, y, a, b, fmt, args…)   printf-style
0x40012bd8(font, surface, x, y, limit, str)         a plain string
```

⚠️ **The `-1` that every call passes is a maximum character count**, not a
shade: the blitter compares it against a character counter at `0x40012cea`
and `0x40012da4`.

The inner loop:

```
40012caa:  mvz.w (%a1)+,%d0      ; a row of glyph bits
40012cb0:  lsr.l %d5,%d0         ; shift to x
40012cb2:  or.l  %d0,(%a0)       ; OR into surface@(12)
```

One bit per pixel, ORed in, always into the same buffer. Text drawing takes
no intensity. ✅ Confirmed negatively on the unit: a probe module
(`ui-dimprobe`, not in this tree) recorded the two spare arguments of
`0x40013904` (`fp@(24)`, `fp@(28)`) and they never varied with what was
dimmed.

### 3b. The SETUP windows' calls, for a page of one's own (nordseele, MKI, 15 Sep 2026)

Run on a MKI by octalab; each entry point re-read here as a function
prologue with the reference count shown ✅. `0x4005829c(115, 64, 0, 0, 1,
closed)` the window; `0x400125ac(surface, 0, 1)` its planes cleared as the
SETUP windows do; `0x400570b8(object, title, "")` the frame and title band
(5 refs); `0x40011b94(surface, x, y0, y1, 1)` a solid vertical line;
`0x40011a58(surface, x0, y, x1)` a dotted horizontal line, one pixel in
two (26 refs); `0x40012004(surface, x0, y0, x1, y1, 1)` a line drawn pixel
by pixel with the ink toggling (15 refs); `0x40013904(font, surface, x, y,
align, invert, width, fmt, …)` formatted text, align 1 centred / 2 right,
its box cleared first, `width` a template string sizing the box (the
stock's `"XXXX"` at `0x400b451d`) (128 refs). Not reconciled: §3 reads
`0x40013904` as `(font, surface, x, y, a, b, fmt, args…)`, six fixed
arguments before `fmt`; nordseele's read has seven. The stock example is
EFFECT 1 SETUP (opener `FUN_40059afc`, descriptor `0x400bc25a`, draw
`FUN_4003792c`): a solid line at x `0x34`, dotted verticals at `0x48` and
`0x5c`, a dotted horizontal at y `0x1c`, 20-px cells, labels centred at x
`col·0x14 + 0x3e`, y `0x30 − row·0x1b`; y runs up from the bottom row.

## 4. Regions — where shading lives

```
0x40012368(ctx, x1, y1, x2, y2, mode)     dithered rectangle: set / clear / invert
0x40012254(ctx, x1, y1, x2, y2, …)        boxes and lines — 224 callers
```

`0x40012368` normalises the corners (swaps so x1 ≤ x2, y1 ≤ y2, clips to
the surface), builds a per-word column mask from `-1 >> (x1 & 31)` and
`-1 << (31 − (x2 & 31))` (MSB = leftmost pixel), and branches on the
**sign of `mode`**:

| mode | operation | at |
|---|---|---|
| `< 0` | `eor.l` — invert | `0x40012442` |
| `> 0` | `or.l` — set | `0x40012460` |
| `= 0` | `and.l` — clear | `0x4001247a` |

**Every mode is dithered.** 🟡 The per-row loop starts from `0xaaaaaaaa`
(`0x55555555` for clear) and re-applies `not` + `and mask` each row, so the
phase alternates row by row: a true 50% checkerboard, not stripes. There is
no solid-fill path in this routine; solid boxes are `0x40012254`'s.

That is the panel's grey. To grey an area, invert a checkerboard over it
(the arranger's cursor); to light it, OR one; to dim what is already drawn,
AND one — the glyph loses every other lit pixel and the background stays
black. XOR over a black background lights half of it (a grey box).

🟡 **The AND path clears outside its rectangle.** `0x4001246e..0x40012484`
ANDs the surface word with `mask & 0xaaaaaaaa`, where `mask` is the
in-rectangle column mask, so every pixel of the same 32-pixel word that lies
outside the rectangle is cleared too. Whether stock only ever calls mode 0
on word-aligned spans is not checked. An overlay that dims one knob cell
(≈21 px of 128, never word-aligned) cannot use it as-is; a cave-side
`and ~(mask & 0x55555555)` is the fix if the reading holds.

## 4b. The panel link: what the controller sends (18 Sep 2026) ✅ under the port

UART1 (`0xfc064000`, 312,500 baud, ISR `0x400109bc`, `KERNEL.md`) carries
the panel controller's events to the OS. The ISR rings each byte
(`0x46100b28`, 32 deep, count `0x460ffda0`) and forces INTC0 source 37,
whose handler `0x4009228c` parses:

| header | payload | meaning |
|---|---|---|
| `0x2n` | 1 byte | key row `n` (0..7): bit `b` = key `n·8 + b` held. The parser XORs against the row's last state (`0x46100b18[n]`) and queues one event per changed bit from the keymap at `[0x46c901dc]` (12-byte records `{01, code, 01, 00, queue, 0}`, the identity map, so **key code = row·8 + bit**; a second table at `+0x302` is selected while the header's FUNCTION row/mask matches — `0xff`/`0x80` in 1.40C, never) |
| `0x3n` | 1 byte | encoder `n`: signed delta (A..F = 0..5, LEVEL = 6); coalesced into a pending event's delta if one is queued |
| `0x40` | 1 byte | the MAIN pot, 0..255, scaled by the calibration at `0x1ffffa..0x1ffffe` (magic `0x1234`) to 0..127 → `0x40092fac` |
| `0x7n` | 9 bytes | copied to `0x46100b48` (pointer `0x46100b52`); the controller's identity 🟡 |

Key events go through `0x40000c3c(queue 0x460d17ae, event)` — 8-byte
records `{code, 0, pressed, 0, ticks}` in the ring at `0x46c9026c` — to
the UI task, which reaches `FUN_4005578c(code, edge)` for a page key and
the key layers `0x46c7d8de + code·0x18`. Keymaps are layers (octalab,
MKI, 13 Sep 2026 ✅): `0x40031494(map)` / `0x4003146c(map)` register /
remove a 20-byte map `{next, keys, encoders, 0, marker}`; rebuild
(`FUN_4003125c`) into keys `0x46c7d8de + code·0x18` and encoders
`0x46c7dede + enc·0x14`; last registered wins; −1 lets the layer below
through; a null encoder handler swallows the turn. The image's keymaps
(§4c): the MKI layer `0x400c090a` → keys `0x400bfc10` (57 records, no
`0x1c`) and the MKII layer `0x400c091e` → keys `0x400c01f4` (62: the same
57 plus `0x1c..0x1f`, `0x36`); ✅ which one `0x40061bc4` pushes follows
`0x46c8d18c`. (Until 25 Sep 2026 this read "`0x400bfbf6` (59 records)":
`0x400bfbf6` is 0x1a before the table the MKI layer points at, inside the
record before it.) Record, 0x1a bytes: `+0 code, +2 press, +6 release,
+0xa, +0xe sub-map, +0x12, +0x16`; the table ends at a code `0xff`. Double press: `0x400c0aac` last keycode,
`0x460d5de0` ticks (display loop `0x40052204`, reset `0x40033e20`), window
14 ticks. LEVEL press `0x3e` special-cased at `0x4004ecfc`. Popups: yes/no
`0x4006d57c(title, n, lines[], 3, handler)`; scrolling list
`0x4006d94c(count, sel, arg3, labels[], handlers[])` / close `0x4006d754`
/ refresh `0x4006d784`; labels pointer `0x460e5e2c`. Grid recording
`0x460d1736 != 0`; audio editor `0x4006de34(type, slot)` + `0x4006e160()`.
Measured under
the port: `0x24 0x08` (row 4 bit 3 = `0x23`) switched the page kind to 2
and the plane redrew as AMP.

Key codes (octalab's list, plus the probe of 18 Sep 2026 under the
port, each code alone in a fresh session): trigs `0x00..0x0f`, tracks
`0x10..0x17`, PROJ (MKII) `0x1c`, PART `0x1d`, AED `0x1e`, ARR `0x1f`
(§4c), DOWN `0x20`, RIGHT `0x21`, page keys
`0x22..0x26` (SRC, AMP, LFO, FX1, FX2), STOP `0x27`, PLAY `0x28`, REC
`0x29`, CUE `0x2a`, FUNCTION `0x2d`, PATTERN `0x2e`, BANK `0x2f`, YES `0x31`, NO
`0x32`, UP `0x33`, LEFT `0x34`, MIDI `0x35`, encoder pushes `0x38..0x3d`,
LEVEL push `0x3e`. KEYPROBE ✅ STOP is `0x27`, not `0x2a` as this list
said until 25 Sep 2026: under the port (`--mkii`, bamsep26 +
OCTABAM89_setgate) PLAY `0x28` turned LED row 11 from `0x01` (stop) to
`0x08` (play), `0x2a` left it at `0x08`, `0x27` put it back to `0x01`
(`KEYMAP.md` has 0x24.7 = STOP and 0x25.2 = CUE from route A); in both
keymaps `0x27` has one handler `0x4004aca4` for press and repeat, `0x2a`
a press and a release handler (`0x4004e978`/`0x4004e968`) and a sub-map
(`0x400bf2a0`), the held-modifier shape.

`ot_emu --live FIFO` feeds these bytes from text lines and
`tools/emu/lcd_view.py --panel FIFO` draws a control surface (`EMU.md`).
What the OS sends BACK on the same link (LEDs, the plane) is unread.

## 4c. The MKII: model flag, panel loader, report, keys (25 Sep 2026) ✅ under the port

What makes the firmware run as an MKII, and what the port (`ot_emu
--mkii`) models so that it does. Read from the image (base `0x40000400`)
and measured on bamsep26 + OCTABAM89_setgate staged as `verify_set.py`
stages it; scratch drivers in `out/_agents/mkii/` (gitignored).

**The model flag `0x46c8d18c`.** The panel-link init at `0x4001f834` sets
it to 1 (`0x4001f8ce`), then ten times writes `0x20` to GPIO
`0xfc0a403a` (bit 5 high), reads bit 6, writes `0xdf` to `0xfc0a4052`
(bit 5 low), reads bit 6; bit 6 not following bit 5 clears the flag
(`0x4001f910`, MKI). ✅ With bit 6 tied to bit 5 (`--mkii`) the flag stays
1. 28 `tstl` sites read it; among them the keymap push
`0x40061bc4`, the loader call `0x4001f976`, the `74 00` / `43` choice
`0x4001f982`, the crossfader poll install `0x4001f9d2` (MKI only:
`0x40010ce8(0x7a12, 0x40092f88 | 0x40092fac)`), the `60 00` at
`0x4001fa08`, the report check `0x40061c94` and the OS-upgrade refusal
`0x4007f87a` (MKII refuses an OS string ≤ `"0155"`, a panel with report
byte 4 = 22 one ≤ `"0177"`).

**The panel loader handshake `0x4001f4dc`** (MKII only; interrupts off,
polled on `0xfc064004` bit 0 / `0xfc06400c`): send `60 02 70 00`, read 5
bytes. `70 05 v ..` with `v` = the long at `0x400d81a4` (8 in 1.40C) →
send `60 00`, return 0. `70 05` with another `v` → reflash the panel from
the image at `0x400d81a8..0x400db3d4` (erase `80 42`, five `ff` back, then
5-byte `cmd addr32` writes echoed by the panel through `0x4001f40c`, up to
3 tries), return `v`. Any other reply → `60 00`, return −1. ✅ With nothing
answering, the port's TX stream stopped at `60 02 70 00` and the boot sat
in the polled read `0x4001f540` (interrupts off) until the first bytes
arrived on the panel line. Inferred from that: in the WIP port the first
key report was taken as the loader's reply (return −1), which is why the
boot then continued, the `74 00` went unanswered and "UI NOT TESTED!"
appeared.

**The report.** On an MKII the CPU sends `74 00` (`0x4001f98a`) where an
MKI gets `43`. The RX parser `0x4009228c` has one format for both models
(no reference to `0x46c8d18c`): header `0x7n` + 9 bytes → `0x46100b48`,
pointer `0x46100b52`. Readers: `0x40061c94` (byte 3 == 0 → "UI NOT
TESTED!" `0x400b4e17`; byte 4 == 22 → `0x46c8d188` = 1) and the system
page `0x400698a6` ("UI VERSION" `1.<byte 1>.<byte 4 == 22>`, format
`0x400b64e7`).

**What the port answers** (`ot::MkiiPanel`, `tools/emu/ot_emu/periph.h`,
on the far end of `Uart@fc064000`, the TX stream framed by the
PANEL_LINK.md opcode lengths): `60 02` enters the loader state, `70 00`
there gets `70 05 v 00 00` with `v` read from the image, `60 00` leaves
it; `74 00` gets `70 00 v 00 01 00 00 00 00 00` (byte 1 = `v`, byte 3 = 1
tested, byte 4 = 0). 🟡 The report's values other than byte 3 are chosen,
not captured from an MKII panel. ✅ Measured order: loader entered at
instruction 10,198,954, returned 0 at 10,199,051, report parsed
(`0x40092608`) at 10,199,687, checked (`0x40061c94`) at 45,935,951;
`0x40061cbc` ("UI NOT TESTED!") never runs; `0x46100b48` =
`00 08 00 01 00 00 00 00 00`, `0x46c8d188` = 0.

**Keys.** The MKII panel's key, encoder and crossfader reports are the
MKI's `0x2r` / `0x3r` / `0x40` (the parser has one format), so the key
code is still `row·8 + bit`. What differs is the UI layer: the MKII key
table `0x400c01f4` = the MKI's `0x400bfc10` + five records:

| code | matrix | handler | measured under `--mkii` |
|---|---|---|---|
| `0x1c` | `0x23` bit 4 | `0x40064d78` | PROJ: the PROJECT menu (PROJECT / SYSTEM / CONTROL / MIDI) |
| `0x1d` | `0x23` bit 5 | `0x4002e7c8` | PART: the part chooser (ONE / TWO / THREE / FOUR) |
| `0x1e` | `0x23` bit 6 | `0x4006e274` | AED: the audio editor (`STATIC 001`, TRIM SLICE EDIT ATTR FILE) |
| `0x1f` | `0x23` bit 7 | `0x40058ab8` | ARR: the arranger menu (`ARR 1:` EDIT RENAME CHANGE CHAIN CLEAR SAVE RELOAD) |
| `0x36` | `0x26` bit 6 | `0x40030a6c` | REC3 🟡: beside REC AB `0x2b` (`0x40030e6c`) and REC CD `0x2c` (`0x40030c60`), same sub-map `0x400b9e02`; nothing drawn on a STATIC track |

PAGE is code `0x1b` (`0x23` bit 3), the MKI's SCALE key: the same handler
`0x4004ffc4` in both tables. ✅ FUNC + `0x1b` under `--mkii` draws
`SCALE, TRACK 3 64/64` (per-track scale). Every tap above hits the key
dispatcher `0x40031904` once (press) and the key-row path `0x400923c0`
twice (press, release), in both models; under MKI the same `0x23.4-7`
taps draw nothing (the MKI table has no record for them). Also measured
under `--mkii`: YES on the date prompt (`DATE/TIME STORED`), T2 then T1
(`0x80000000` 1 → 0), knob A +3 on T3's SRC page (`0x40170fc6` and
`0x800008a0` 64 → 66, PTCH draws `+0.4`), code `0x27` = STOP (above).

**LCD and LEDs under `--mkii`** ✅: the stream decodes with
`panel_link.PanelLink` as on an MKI (897 LCD blocks, 81 LED rows, 785 LED
levels after boot + 500 ms); new on the wire: `60 02 70 00`, `74 00`,
`60 00`, and 204 `0xb5` messages (`0x4003f430` called from
`0x40061af2` / `0x40061b22` only when the flag is set).

Where it is wired: `ot_emu --mkii`; `tools/panel/panel_server.py` passes it
by default (`--mki` to run as an MKI; `/map` says `"model"`), and
`panel.html` draws PROJ/PART/AED/ARR/REC3 and the PAGE legend when it is
an MKII; `tools/emu/live.py` passes it by default (`--mki`);
`tools/panel/key_map.json` `proj`/`part`/`aed`/`arr`/`rec3`/`page`;
`panel_check.py` opens the PROJECT menu with PROJ on an MKII (✅ FUNC +
MIXER does not open it there; both models pass all five checks). The
gates (`verify_set`, the port's self-tests) run as an MKI, unchanged.

## 5. The cursor idiom — and the arranger's giant one

A screen highlights a cell by looking up its geometry in a per-type table
and inverting a rectangle around it. The arranger's (`0x40049896`):

```
a0 = x[type][column]            ; 0x400a775e
a1 = w[type][column]            ; 0x400a783c
pea -1                          ; mode: EOR
pea (1,%a0,%a1)                 ; x2 = x + w + 1
a0 = a0 - 1 - a1                ; x1 = x - w - 1
jsr 0x40012254
```

✅ **Those tables are (centre, half-width)**, not (left, width): the
arithmetic is symmetric about `x`, and a pattern row's column 0 (centre 12,
half 5 → 6..18) is a three-digit row number's span.

A REMINDER row appears to grey out when the cursor reaches its text column
because that cell is centre 82, half-width **38**: the inverted checkerboard
is 78 pixels of a 128-pixel line, against under 20 for every other cell on
every row type. Nothing is dimmed; XOR-ing a checkerboard over lit pixels
turns half of them off.

## 6. Greying a blanked parameter slot — what is still missing

A nibble-0 slot (`PARAM_PAGES.md` §3b) draws an empty circle and `---` on
the unit (our image, 16 Sep 2026). To dim it with §4 the following are
unread:

- which drawer puts the circle and `---` there and its per-slot geometry
  (x1, y1, x2, y2 for slots 0–5, pages 1 and 2). Candidates: the knob
  renderer `0x400479b4` and the list drawer `FUN_40037590` that calls it
  (§3b's bit-2 reading), neither traced past the flags word;
- a hook site after the page draw and before the plane goes out over
  UART1 (the sender is unlocated), on every refresh; a one-shot overlay
  is redrawn away;
- a per-slot flag: every nibble bit is in use (§3b: bit 1 = link bracket,
  bit 2 = the PLAYBACK page-2 layout flag, bit 3 = the scene-held XVOL);
- the cell geometry is a framebuffer read now: `ot_emu --lcd --live`
  with the page keys (§4b) leaves a run on any page.

## 7. Not known

- `+20` / `+24` of the surface descriptor, and what `+16` (all `0xff`
  after a load) is for;
- how the two bits per pixel are composed for the display — every drawer
  here is 1-bit-per-pixel into one buffer, so the second bit comes from
  somewhere not yet found — and the UART1 sender;
- the window/geometry descriptor internals `MAINMENU.md` lists, a layer
  above these primitives.
