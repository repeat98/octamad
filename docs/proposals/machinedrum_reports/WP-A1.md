# WP-A1 Core-0 memory ledger: report (IN PROGRESS, handed over)

- **Status:** claimed, not finished. Frozen on the user's request (23 Sep
  2026) for another agent to take over. The measurement is done; the
  write-up (`docs/firmware/CORE0_MEMORY.md`), the section 12 entry and the
  `DSP.md` retraction are not.
- **Branch and commit:** `machinedrum` (this commit)
- **Date:** 2026-09-23
- **Agent:** Claude Opus 5.5

## What was done

- **A per-word read/write map under the ColdFire port, in an isolated
  build.** `tools/harness/md_reference/core0_wordmap.patch` adds a read
  hook to a copy of the vendored `Memory::get` and a `--dsp-wordmap FILE`
  option to a copy of the port. For every word of X, Y and P below 0x40000
  on both cores it records flags, plus the epochs in which the word was
  written, read, and read before any write. An epoch is one frame vector:
  0x18 on core 0 and 0x12 on core 1, each taken once per frame. The map is
  enabled after `--dsp-dirty`'s garbage fill, so the fill doesn't count as
  a load.
  - `tools/harness/md_reference/core0_wordmap.sh <scratch> <project> <tag>
    [frames]` builds the copy in `<scratch>` and runs it. `vendor/` and
    `out/emu` are untouched.
  - The run stages the card like `verify_set`, boots the stock image
    `out/raw/section_3_MAIN_OS.bin`, and runs 1,000 frames with the
    sequencer playing.
- **`tools/harness/md_reference/core0_ledger.py WORDMAP...`** classifies
  every word as state, scratch, table, loaded, garbage or free. With
  several maps, a word keeps the most-used class any run gave it.
- **Four project configurations.** All are copies of the user's Template
  Live, with `TONE.wav` (a generated 440 Hz test tone) as FLEX slot 1 on
  T5–T8, four trigs each, and every page byte at 64:

  | Config | Tracks | FX1 | FX2 |
  |---|---|---|---|
  | A | T1/2/5/6 | FLANGER | DARK |
  | A | T3/4/7/8 | CHORUS | PLATE |
  | B | T1/T5 | FILTER | DELAY |
  | B | T2/T6 | PHASER | COMB |
  | B | T3/T7 | SPAT | LO-FI |
  | B | T4/T8 | COMP | DJEQ |
  | C | T1/T5 | EQ | FLANGER |
  | C | T2/T6 | LO-FI | CHORUS |
  | C | T3/T7 | COMB | FILTER |
  | C | T4/T8 | DJEQ | COMP |
  | D | T1/T5 | COMB | SPRING |
  | D | T2/T6 | LO-FI | SPRING |
  | D | T3/T7 | SPAT | DARK |
  | D | T4/T8 | PHASER | PLATE |

  Every stock effect runs on core 0 at least once.
- **Outputs**, committed beside this report:
  - `WP-A1-ledger-all.txt`: A+B+C+D merged;
  - `WP-A1-ledger-noreverb.txt`: B+C, which is the MD remix's case, since
    it drops PLATE, SPRING and DARK from payload A.

## Acceptance check (partial)

The build and the run reproduce: a second build of the patch in a fresh
scratch directory gave a byte-identical word map for config A.

```
$ tools/harness/md_reference/core0_wordmap.sh <fresh scratch> <projFX> fx1000 1000 && cmp <fresh>/fx1000/wordmap.bin <first>/fx1000/wordmap.bin && echo IDENTICAL
fx1000 exit 0
IDENTICAL
```

Every run ended with `frames run : 1000 since transport start (target 1000),
run ended REACHED`. Core 0 took the frame vector 0x18 1,000 times.

The packet's "done when" is not met yet. The words are classified (see
the ledgers), but `docs/firmware/CORE0_MEMORY.md` with the evidence per
range is not written.

## Measured (all under the port, stock image; ✅ for these configurations)

**Core 0 X** (A+B+C+D merged):

| Range | Class | Evidence and owner |
|---|---|---|
| `0x000–0x133` | scratch | Rewritten every frame. `0x146–0x1ff` is partly state and partly "garbage": read, never written, likely the read-back block. The MD driver already stashes low memory |
| `0x215–0x25c` | table | |
| `0x25d–0x416` | state | |
| `0x438–0x5fb` | table | |
| `0x603–0x1d9e` | table/loaded | The curve bank |
| `0x1d9f–0x1ffe` | free | Except four 32-word scratch buffers at `0x1e00/1e80/1f00/1f80`: `x:$20b = 0x1e00`, set at `P:0x37d`, a per-track buffer |
| `0x1fff–0x2836` | state/scratch | **Frame context A**, used on alternate frames: stock's frame handler at `P:0x64` sets `r6=0x2000 r7=0x2080 r2=0x2400 r5=0x2600 r4=0x2800`, and the ColdFire's DMA writes these per-frame blocks. Context A uses up to `0x2836`, with per-track records at a 0xa8 stride from `0x208b` |
| `0x2840–0x3fff` | **free** in all four configurations | Inside the host-DMA mask: the frame handler patches the `and #>$ffff` at `P:0x58b/58c` to `0x3fff`/`0x5fff`, which bounds the destination the ColdFire can pick, not what it writes. By symmetry with context B (the boot clear stops at `0x4840`, `stock.py` `CURVE_BANK`), context A should end at `0x283f`. 🟡 A heavier project (8 voices, slices, recorders) was **not** tested |
| `0x3fff–0x4836` | state/scratch | **Frame context B**: `r6=0x4000`, and the rest as for A with +0x2000 |
| `0x4840–0x583f` | loaded | The 4,096-word curve bank, DJ EQ's (`stock.py` `CURVE_BANK`). Only a few words were read here, at the knob values tested |
| `0x5840–0x60ff` | free | 1,984 + 227 words |
| `0x6100–0x6bff` | r7 instance blocks | Partly free at these effects' footprints, but they are instance blocks: `r7+$00..$83` belongs to whichever effect is on the slot. Not free ground |
| `0x6c00–0x6fff` | table | The sine and the ramp (`TABLES.md`) |
| `0x7000–0x7a91` | loaded/table | |
| `0x7a92–0x7fff` | free | 1,390 words |
| `0x8000–0x80ff` | ESAI DMA ring | |
| `0x8100–0x833f` | state | The host-port receive DMA destination (`M_DDR3 = 0x8100`, `P:0x3005e`), 576 words |
| `0x8343–0x857f` | free | 573 words |
| `0x8580–0x8d97` | table/loaded | |
| `0x8d98–0x8fff` | free | 616 words |

**Core 0 Y:**

| Range | Class | Evidence and owner |
|---|---|---|
| `0x000–0x27f` | scratch/table | |
| `0x290–0x5fb` | table | |
| `0x5fc–0x794` | loaded | |
| `0x795–0xfff` | **free** (2,155 words) | ✅ **Confirms `CHIP.md`** |
| `0x1000–0x3fff` | FX1 slots | Used only by effects that allocate memory: FLANGER/CHORUS 2,048 words, COMB 3,084 |
| `0x4000–0xbfff` | FX2 slots of T5/T6 | The reverbs and DELAY-class effects fill them |

**The window**, judged on the union of its P/X/Y views, per core:
- **Core 0:**
  - `0x30000–0x30047` is state every frame, stock's parameter staging;
  - `0x30048–0x37fff` holds the FX2 slots of T7/T8 (`0x30000`/`0x34000`),
    live only when those tracks carry a reverb;
  - `0x38000–0x3800f` is read every frame;
  - `0x38013–0x3ffff` is untouched by core 0.
- **Core 1:**
  - it reads `0x30000–0x30044` every frame, so core 0's staging is read
    cross-core;
  - `0x32000–0x32039` is bootstrap B;
  - `0x38000–0x3800f` is state;
  - `0x38010–0x3ffff` holds the FX2 slots of T3/T4, and nothing else.

## Retracted

- ❌ `DSP.md` §7: "X: `0x01d9f–0x0483f` (10,913 words) delay region for
  PLATE/DARK". Under the port, with PLATE, DARK and SPRING on every core-0
  track (configs A and D), no reverb writes X there:
  - `0x1fff–0x2836` and `0x3fff–0x4836` are the frame contexts, live in
    every configuration, including ones without reverbs;
  - `0x2840–0x3fff` is untouched in all four.

  **Not yet propagated:** `DSP.md` still carries the old line. The next
  agent should mark it ❌ there, pointing to `CORE0_MEMORY.md`.

## Open and handover

1. **Write `docs/firmware/CORE0_MEMORY.md`** from the two ledgers and the
   tables above. Classify every word of X `0–0x8fff`, Y `0–0xbfff` and the
   window, with the evidence per range. Then add a section 12 entry to
   `MACHINEDRUM_MACHINE.md`, and set WP-A1 to `done`.
2. **The one real doubt:** is X `0x2840–0x3fff` safe (6,078 words)?
   - Run one heavier project: all eight tracks playing, a slice machine,
     and a recorder armed.
   - Or find where the ColdFire builds the DMA destination addresses.
   - If it stays free, it is the MD's largest private-X home.
3. **What this means for WP-A2** (*inferred*, not yet written into section
   12):
   - The MD's voice Y block (1 K) fits at `Y:0x800–0xbff`, in the free
     `Y:0x795–0xfff`, provided the MD remix carries no bus module.
     `Y:0x900–0xad9` is BusVerb/SEND scratch in bus remixes.
   - The P-I X words use the same base, and `X:0x800–0xbff` is the curve
     bank. So the three options of section 12, "The OT-side driver", stand.
   - One new option: base both blocks where X is free and Y belongs to an
     FX1 slot the MD track gives up. For example, base `0x3400` puts the X
     block in the free `0x2840–0x3fff`, and T8's FX1 slot is Y
     `0x3400–0x3fff`. The cost is T8's FX1, or the MD track's FX1 if the
     base follows the track. This is a user decision (layout review).
   - The window gives the MD at most `0x30048–0x37fff` (32 K) on core 0's
     side, and only when T7/T8's FX2 are memoryless. The other half costs
     T3/T4's FX2 memory on core 1. The MD needs 71–76 K plus P-I buffers,
     so the layout must also use private Y `0x4000–0xbfff` (T5/T6 FX2)
     for Y-only tables. That is the WP-A2 trade-off to put to the user.
4. **WP-D1, a partial static read** (not claimed; it belongs to that
   packet):
   - The MKII keymap at `0x400c01f4` has 62 records of 26 bytes:
     - track keys `0x10–0x17` → handler `0x40040250`, with a
       track-held sub-map `0x400d164a`;
     - trigs `0x00–0x0f` → `0x40060ce0`.
   - The track-held sub-map's keys (at `0x400d1594`) are only `0x27`,
     PLAY `0x28`, BANK `0x2f`, YES `0x31`, NO `0x32` and `0x18`. It has
     no encoder table and **binds no trig**.
   - So with a track key held, a trig falls through to `0x40060ce0`,
     which branches on grid recording (`0x460d1736`: `0x40060b58`, else
     `0x400501d8`).
   - **Still to check:** whether either target tests a held track key.
     Disassemble them with `m68k-elf-objdump -D -b binary -m m68k:cfv4e
     --adjust-vma=0x40000400 out/raw/section_3_MAIN_OS.bin`.
