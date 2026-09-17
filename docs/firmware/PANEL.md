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
- a hook site after the page draw and before the buffers go out (§1's
  `0x40063270` / `0x40063282`), on every refresh; a one-shot overlay is
  redrawn away;
- a per-slot flag: every nibble bit is in use (§3b: bit 1 = link bracket,
  bit 2 = the PLAYBACK page-2 layout flag, bit 3 = the scene-held XVOL);
- the cell geometry is now a framebuffer read (`ot_emu --lcd`), once a
  run can be left on an FX page: the port drives no keys.

## 7. Not known

- `+20` / `+24` of the surface descriptor, and what `+16` (all `0xff`
  after a load) is for;
- how the two bits per pixel are composed for the display — every drawer
  here is 1-bit-per-pixel into one buffer, so the second bit comes from
  somewhere not yet found — and the UART1 sender;
- the window/geometry descriptor internals `MAINMENU.md` lists, a layer
  above these primitives.
