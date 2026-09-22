# The remixer: `make remix`

The interactive front end: compose a remix, hear any effect through the
real DSP code, and see the firmware draw the choosers you composed in the
local ColdFire emulator. Nothing in it touches hardware.

## Setup

```bash
make emu-setup      # uv provisions .venv with unicorn + textual
make bus            # out/mainos_bus.bin, which the emulator view boots
make remix
```

The frontend is `tools/remix/app.py` (Textual); `make remix` prefers
`.venv/bin/python3` and exits with the setup hint on bare `python3`. The
build and every check stay dependency-free. Playback is `afplay`
(macOS); everything else runs wherever the DSP toolchain does.

## One page, three panes

```
┌ Available ───────┬ Choosers · bus ──┬ BusVerb ────────────────────┐
│ ── Bus ──        │ FX1  10 rows           │ Bus · id 0x07 · tracks 5-8   │
│    BusDelay FX2 │   1 Filter             │ TIME  64  [######......] p1  │
│  ✓ BusVerb  FX2 │   2 Equalizer          │ MOD   30  [###.........] p1  │
│ ── Insert ──     │   … 8 more             │ …                            │
│    WarpFold  FX2 │ FX2  4 rows            │                              │
│ ── Stock ──      │   1 BusVerb    2411w  │                              │
│  ✓ Filter FX1+FX2│   2 BusDelay   2469w  │                              │
│                  │ A 74 free · B 5 free   │                              │
└──────────────────┴────────────────────────┴──────────────────────────────┘
```

| key | does |
|---|---|
| `tab` / `shift+tab` | next / previous pane |
| `up` `down` (`j` `k`) | move within a pane |
| `left` `right` (`h`) | in UNIT: step the knob ±1 (`shift` ±10); in CHOOSERS: move the row |
| `enter` | AVAILABLE: add the highlighted module to the image; CHOOSERS: remove the row from its list |
| `1` | give the highlighted effect an FX1 row, or take it off |
| `f` | pick the fallback explicitly |
| `x` | apply the fix the ⚠ line names |
| `l` / `s` / `k` | load a remix (or `stock`) / save the selection as one / reset to stock |
| `c` | `make check` |
| `r` / `space` / `esc` | render the effect under the cursor on the source and play it / replay / stop |
| `a` / `b` / `,` / `.` | mark A / render and mark B / play A / play B |
| `d` | choose the sample folder |
| `?` / `q` | help / quit |

**AVAILABLE** is everything that could be in an image: modules grouped
bus / inserts / firmware mods / system, then the stock effects the unit
ships. `✓` marks what the selection holds; for an effect the `FX1+FX2`
column is which choosers it *can* appear on (`stock.fx1_ids()` from the
pristine image). A firmware mod (midisc, Octakit, the bridges, the fixes)
has no chooser; its column is the ledger's verdict against what is loaded
— `✓` shares the image, `x octakit` names what it collides with, and
`· add Kits Reload` names the bridge that would clear it (the same
`ledger.check` the build refuses on). The unit pane lists every ledger
line the pointed-at module is party to. `enter` adds and displaces
nothing.

**CHOOSERS** holds both of the unit's effect menus, stacked, in panel row
order; `left`/`right` is a real edit. FX2 starts empty (every row is one
the remix listed); FX1 starts as stock's ten, with the firmware's own NONE
as row 0, never shown and never losable. Leaving an effect off a chooser
removes the row; its code, descriptor and dispatch stay stock. `◀fb` marks the fallback; `·` in the number column is a ColdFire
patch with no row. Each module's word cost comes from the real assembly
the background rebuild runs. The pane closes with one line: the per-payload
budget (`A 74 free · B 5 free`), a ⚠ naming what to remove, or `building…`;
it ends in `boots` when the built image reaches the RTOS handoff in the
emulator.

**UNIT** follows the cursor, so pointing at something in the library
previews it before you add it: kind, id, menus, track range, the one-line
doc, the resource line, and the drawn parameters with values. Values live
per module, seeded from the manifest defaults. `SOURCE` is the first row;
`left`/`right` cycles the wavs in the source folder.

## What costs what

Rows are not the currency; words are. A chooser row costs nothing (seven
fit in place, up to 32 in the long cave), and a stock effect on either menu
costs nothing: its code is already in the image. The budget is per payload
(two regions, the same effects at different addresses; `SPEC=1` puts each
server on its own), reported from the build's own figures. An overrun
arrives as the build's refusal, naming the payload: `payload B: RUNGS
overruns the region (3599 > 2724 words)`.

Measured costs, payload A: Hello World 27, Streamz 255, WarpFold 322,
Ripple 347, BodeShift 391, Nimbus 500, Rungs 880, Send 215, BusVerb 2,411
(+24 LFO table), BusDelay 2,154 (payload B).

The ⚠ line describes the image, not the cursor, and names the cause and
the count; `x` applies its fix and removes every row the build named:

| after you add | what happens |
|---|---|
| no safe fallback | SEND is added: `added Send as the fallback` |
| a buffer clash | `x removes Flanger, Chorus, Spatializer, Comb Filter — they need the same buffer` |
| past a payload's region | the build refuses and names it |

The buffer clash is why adding BusVerb to a stock chooser costs seven
effects: FLANGER, CHORUS, SPATIALIZER, COMB and the three reverbs each
take a per-track instance buffer from the host's bump allocator (each
reads `x:>$213`: PLATE at `0x01018`, SPRING `0x01267`, DARK `0x01692`) at
the addresses BusVerb's tank hardcodes, and the chooser is one list for all
eight tracks. The collision cannot follow them to FX1: the allocator keeps
separate tables, FX1 bases `0x1000 0x1c00 0x2800 0x3400` of 3,072 words
topping out at `0x3fff`, FX2 `0x4000 0x8000` + the shared-window pair of
16,384.

### Harvesting

The remixer opens with nothing harvested: all 6,158 words of a payload's
effect code belong to a stock effect that is using them. Taking an effect
off **both** choosers is the decision to give up its words
(`stock.harvested`); removing it from one menu while it still has a row on
the other frees nothing. The three reverbs are only the default harvest:
the biggest, and FX2-only, so taking them costs FX1 nothing. The thirteen
DSP effects are laid out contiguously and each is self-contained, so any
unbroken run of them is ground a module can be placed into; the map under
the budget draws a bracket per run.

A module must fit inside one run: two runs of 1,500 words will not take a
2,000-word module, so the budget names the largest opening beside the
total. Harvesting an effect that sits between two runs joins them.
Harvested is not unlisted: an effect keeps its algorithm wherever your
code did not reach (the region packs from the lowest address upward and
the build reports which survived), so an effect can be listed and
harvested at once, `✓⌁`, until the placer reaches it; the build then
refuses the row and `x` removes it.

The resource line under the doc:

| | says |
|---|---|
| a listed stock effect | `727 words, already placed` |
| one given up (off both menus) | `594 words — off both menus, so they are yours to place into` |
| DELAY | `no DSP words — it runs on the ColdFire side` |
| a module with DSP code | `2,411 of 2,724 words` |

Stock rows are not in the cycles figure (only FILTER's is measured, 192 per
instance); the row says `14 stock rows not counted`.

### FX1 rows

`1` gives the highlighted effect an FX1 row (`Remix.fx1`, written by `s`).
It costs no words (the DSP dispatch is shared by both menus; the list is
rebuilt in the cave with FX1's three `lea` references, its id lookup and
its cursor table repointed) and it costs cycles: FX1 is four more slots on
the same four tracks, so an effect on both menus can double the worst
per-core load (WarpFold 4× → 8×, 404 → 808 of 3,120). Only a buffer-free
insert, or an allocator reader declaring `buffer_words` ≤ 3,072, may take
one; the UNIT pane says which cannot and why (`FX1 no row — and cannot
take one: it sizes its buffer for an FX2 slot (16,384 words)`; `FX1 ONLY:
passes dry on FX2`). A `replaces` module is listed by its own key. Every id
a shortened FX1 list drops has its cursor row clamped to 0.

## Hearing

`r` renders the effect under the cursor on the SOURCE wav through the
audition backend (`tools/remix/audition.py`) and plays it; `space`
replays. `a` parks the current render as A; point at the rival, `b`
re-renders it on the same source; `,` / `.` flip between them. `d` sets
the source folder and remembers it in `out/_audition/remixer.json`
(`REMIXER_SOURCES` overrides; default `out/dry/`; `WORKBENCH_SOURCES` and
`out/_audition/workbench.json` are still honoured).

Six of the stock effects render dry at their defaults (PHASER, FLANGER,
CHORUS, COMB at `MIX 0`; SPATIALIZER, DELAY at `SEND 0`): stock defaults
are the firmware's own, and the UNIT pane says `⚠ MIX is 0 — this renders
DRY`.

The audition backend, per effect:

| effect | path |
|---|---|
| busverb | `tools/harness/render_reverb.py`, its own fingerprinted engine cache |
| busdelay | the DEV hatch (`DEV=1 XBUS=1` → `out/dsp/mem_dev_A.mem`, rebuilt when stale), then `send_probe --layout DS` |
| inserts, stations | a per-insert scratch image (the insert + SEND), dumped to `out/dsp/_audition_<name>_A.mem`; the user's `out/mainos_bus.bin` is saved and restored around the scratch build |
| stock | a dump of the stock image's payload A, `-alloc 1 -audio 0` |

An id absent from an image dispatches to the fallback; `send_probe`'s
SEND-alias guard refuses to measure it. Every render and A/B mark is
journalled to `out/_audition/log.jsonl` (track, effect, source, every
knob).

## The image follows the selection

Every selection change rebuilds (~0.3 s) and re-boots the ColdFire
emulator (~5 s) in the background; the panel on the right draws what
CHOOSERS says. The emulator draws the FX1 and FX2 choosers and an effect's
page with the firmware's own code. Its limits (`docs/remixer/EMU.md`): no
audio, no key matrix, and item-level menu descent needs the real key
handler.

## Editing in another window

The remixer follows the source: edit a module's `.asm` or manifest and
`r` re-renders it (the scratch image is cached against the newest mtime
under `modules/`).

## Theming

`REMIXER_THEME` picks any built-in Textual theme (default `ansi-dark`;
`WORKBENCH_THEME` still honoured). Colours: aqua = a module, plain =
the box's own; green fits, ochre is a trade or caution, red blocks; a
knob's level is a warm ramp by where the value sits in its range; the
source wav muted blue; the fallback soft purple; the panel frame grey.

## Architecture

| layer | file | job |
|---|---|---|
| composer | `tools/remix/state.py` | selection, `problems()`, `measure()`, scratch builds |
| rig | `tools/remix/rig.py` | category + track-range derivation, knob docs/labels/maxima |
| rendering | `tools/remix/audition.py` | the per-effect dispatch above, the journal, a `__main__` for headless renders |
| shell | `tools/remix/app.py` | Textual only: screens, keys, workers |

The panel render is cached on (page, effect id, build) and `problems()` is
computed once per pass (3.6 ms per knob step).

## Known gaps

- Per-mode `defaults` apply in the remixer; on the unit they land by
  `stamp-defaults`.
- The emulator limits above.
- Stock rows are not priced.
