# analog-bd-dynload

Analog BD on all eight tracks, with all 14 stock effects kept on both menus.
No stock DSP effect is built in: the DSP dynamic loader (`DSP DYNLOAD STOCK`)
loads each one into its arena when a Part or a selection needs it.

Port-qualified; **not yet run on hardware** (30 Sep 2026).

## Layout (per core, payload A shown; B is 0x240 lower)

| P range | words | what |
|---|---|---|
| 0x7d1..0x96f | 414 | shared stock routines the effects call (FILTER's library, two reverb helpers) |
| 0x96f..0x1a8f | 4,384 | the loader's table: 64 saved entries + a 4,320-word arena |
| 0x1a8f..0x1bd0 | 321 | the loader's receiver |
| 0x1bdb.. | 996 | Analog BD (reserve 1,028) |

All 13 stock DSP effects together are 5,872 words per core; a core runs at
most eight at once (four tracks, two slots). Any set up to 4,320 words loads,
all three reverbs together included; a larger one (eight different large
effects on one group of four tracks) is refused whole with DSP MEMORY FULL
and the previous Part keeps playing.

## Measured under the port

- `verify_stock_relocation` (dsp_host): all 13 stock DSP effects run
  sample-identically to stock from the lowest, a middle and the highest arena
  address on both cores, with the effect block filled with `illegal` under
  the shared copies (702 renders; a negative control without the copies
  differs).
- `verify_stock_select`: each of the 13 selected through the stock FX
  setters loads, binds into the arena and goes live, on both cores; an
  over-capacity Part is refused whole.
- `verify_stock_load` (dirty DSP memory, pristine 1.40C as the oracle):
  a project with 11 of them loads with no message or error; LO-FI,
  SPATIALIZER and COMB are then sample-exact to stock, FILTER within 2 LSB,
  every chain within 0.3 dB. A Part published around every guard: no burst,
  every chain within 0.31 dB; without the init fix a reverb plays garbage
  (+14.4 dB).
- `scripts/refhash.sh check`: all 24 cases bit-identical; the
  `analog-bassdrum` image and build report unchanged.

## How it behaves

- Selecting an effect, changing Part, loading a project: the effect's code
  is uploaded and bound before stock publishes it (the guards), so it starts
  with its own init, as on stock. A new effect is audible after its upload,
  a few tens of milliseconds for the largest (inferred from the transfer
  rate, not measured on hardware).
- Stock's own boot and project load publish defaults (FILTER on every FX1)
  and some routes publish without asking. Such a slot is held at NONE (dry)
  until its code is bound, then given back, so the dispatcher runs the real
  init before the effect's first block. Reverb tails therefore start later
  than on stock; nothing else differs.
- Not measured: timing on hardware, the MKI, and every route the audit in
  `modules/dsp-dynload/PUBLICATION.md` lists as open (those land in the
  held-at-NONE path above rather than running uninitialised code).
- Cannot combine with USB IN (both own the frame DMA hook).
