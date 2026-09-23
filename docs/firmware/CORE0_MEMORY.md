# Core-0 memory ledger

Status: measured under the ColdFire port on 23 September 2026. This is the
memory record for the Machinedrum layout review; it is not a claim that the
heavier slice/recorder fixture is complete. `✅` is measured, `🟡` is
unresolved or inferred, and `❌` is retracted.

## Method and evidence

The wordmap records every X, Y and shared-window word touched after the first
frame vector. The isolated port build is made by
`tools/harness/md_reference/core0_wordmap.sh`; it fills DSP RAM with garbage
before boot, then records read/write epochs for 1,000 frame runs. The
classifier's precedence is `state > scratch > table > loaded > garbage >
free` when several runs disagree.

The complete, generated, contiguous-range tables are kept beside the packet
report:

- [all four configurations](../proposals/machinedrum_reports/WP-A1-ledger-all.txt)
  — A+B+C+D, including reverb cases;
- [no-reverb configurations](../proposals/machinedrum_reports/WP-A1-ledger-noreverb.txt)
  — B+C, the relevant baseline when payload A drops PLATE, SPRING and DARK.

Each ledger has one non-overlapping row per class run and covers the whole
requested interval: X `0x00000–0x08fff`, Y `0x00000–0x0bfff`, and the shared
window `0x30000–0x3ffff` for each core. The range end in the tables below is
inclusive, matching the generated ledger.

| space / run | state | scratch | table | loaded | garbage | free | evidence |
|---|---:|---:|---:|---:|---:|---:|---|
| X, all A+B+C+D | 5,172 | 1,294 | 2,976 | 14,008 | 236 | 13,178 | ✅ four 1,000-frame port runs |
| X, no-reverb B+C | 4,899 | 1,285 | 2,626 | 14,358 | 255 | 13,441 | ✅ two 1,000-frame port runs |
| Y, all A+B+C+D | 39,452 | 574 | 920 | 4,971 | 52 | 3,183 | ✅ four 1,000-frame port runs |
| Y, no-reverb B+C | 8,220 | 564 | 914 | 28,043 | 188 | 11,223 | ✅ two 1,000-frame port runs |
| window, core 0, all | 27,173 | 3 | 16 | 5,595 | 0 | 32,749 | ✅ union of P/X/Y views |
| window, core 0, no-reverb | 72 | 0 | 16 | 32,699 | 0 | 32,749 | ✅ union of P/X/Y views |
| window, core 1, all | 27,173 | 3 | 68 | 5,753 | 0 | 32,539 | ✅ union of P/X/Y views |
| window, core 1, no-reverb | 16 | 0 | 68 | 32,913 | 0 | 32,539 | ✅ union of P/X/Y views |

The row counts are an audit summary, not a replacement for the generated
per-range tables. A class is only called free below when the relevant ledger
has no runtime read or write in the covered words.

## Core-0 X, `0x0000–0x8fff`

| range or owner | classification | evidence / consequence |
|---|---|---|
| `0x0000–0x0214` | runtime scratch/state, with small garbage islands | ✅ frame handler and host-port work in every run; see the exact alternating rows in both ledgers |
| `0x0215–0x025c` | table | ✅ curve/table reads; no runtime writes |
| `0x025d–0x0416` | runtime state | ✅ read before write across frame epochs |
| `0x0438–0x05fb` | table | ✅ curve/table reads; no runtime writes |
| `0x05fc–0x1d9e` | loaded tables with interleaved one-word table markers | ✅ loaded image plus repeated table reads; exact sub-ranges are in the ledgers |
| `0x1d9f–0x1fff` | mostly free, with four 32-word scratch buffers and their state words | ✅ `0x1e00–0x1e1f`, `0x1e80–0x1e9f`, `0x1f00–0x1f1f`, `0x1f80–0x1f9f` are written scratch; the surrounding ranges are free in the measured runs |
| `0x1fff–0x283f` | frame context A: state plus boundary scratch | ✅ `r6=0x2000`, per-track records begin at `0x208b`; the exact ledger separates state/scratch |
| `0x2840–0x3fff` | **free in A+B+C+D** | ✅ untouched in all four 1,000-frame fixtures; 🟡 the required heavier eight-track slice/recorder run crashed before producing a map, so this is not closed for that workload |
| `0x3fff–0x483f` | frame context B: state plus boundary scratch | ✅ `r6=0x4000`; present even in no-reverb B+C |
| `0x4840–0x583f` | loaded curve bank | ✅ stock `CURVE_BANK`; only selected words are runtime-read in the fixtures |
| `0x5840–0x60ff` | free | ✅ no-reverb ledger: free; all-run ledger also leaves this interval unused |
| `0x6100–0x6bff` | FX instance blocks, not free allocation space | ✅ ownership depends on the effect in the slot; `r7+$00..$83` is per-instance state |
| `0x6c00–0x7a91` | loaded/table | ✅ sine/ramp and loaded data; exact table markers are in both ledgers |
| `0x7a92–0x7fff` | free | ✅ 1,390 words in the report's four-configuration summary |
| `0x8000–0x80ff` | ESAI DMA ring | ✅ core-0 runtime owner |
| `0x8100–0x833f` | host-port receive DMA state | ✅ 576-word runtime region (`M_DDR3` at the frame transfer) |
| `0x8340–0x857f` | boundary garbage/free, then free | ✅ exact split is in both ledgers; `0x8343–0x857f` is 573 free words |
| `0x8580–0x8d97` | loaded/table | ✅ stock loaded data with table reads |
| `0x8d98–0x8fff` | free | ✅ 616 words in all four configurations |

The coarse rows intentionally call out ownership; the linked ledgers give the
classification of every word where a coarse row contains more than one class.
In particular, the old claim that `0x1d9f–0x483f` is a reverb delay region is
not supported by the port runs.

## Core-0 Y, `0x0000–0xbfff`

| range or owner | classification | evidence / consequence |
|---|---|---|
| `0x0000–0x01ff` | runtime scratch/state with small garbage islands | ✅ frame-local work; exact per-word runs in both ledgers |
| `0x0200–0x05fb` | table, with the surrounding scratch/state words | ✅ table reads at `0x0290–0x05fb` |
| `0x05fc–0x0794` | loaded data with table markers | ✅ stock load map and runtime reads |
| `0x0795–0x0fff` | **free, 2,155 words** | ✅ confirmed in both the four-run and no-reverb ledgers; this is the cleanest MD voice-Y home |
| `0x1000–0x27ff` | effect-dependent state or free in the no-reverb case | ✅ all-run ledger records FX1 state; no-reverb B+C leaves the corresponding gaps free; do not allocate without the proposed remix's slot claims |
| `0x2800–0x3fff` | effect-dependent state, scratch, garbage and free gaps | ✅ no-reverb ledger shows a 3,084-word state block at `0x2800–0x340b` and free gaps around it; exact rows are required for layout checking |
| `0x4000–0x7fff` | FX2/effect state plus loaded data | ✅ all-run ledger; not a generic free pool |
| `0x8000–0xbfff` | second FX2/effect region plus loaded data | ✅ all-run ledger; no-reverb configurations leave large loaded spans, but effect ownership still follows the selected slot |

The no-reverb ledger is the useful one for the MD proposal: it confirms
`Y:0x795–0xfff` as free, while the all-effects ledger demonstrates why a
layout must reserve explicit FX1/FX2 ownership rather than treating every
unwritten-looking Y gap as generally available.

## Shared window, `0x30000–0x3ffff`

The window is one memory viewed through P/X/Y. The two cores must therefore be
reported separately even when a word is visible from both.

| core / range | classification | evidence / consequence |
|---|---|---|
| core 0 `0x30000–0x30047` | state | ✅ stock parameter staging, written and read every frame |
| core 0 `0x30048–0x37fff` | effect-slot storage | ✅ all-run ledger has the T7/T8 FX2 ownership; no-reverb B+C leaves it loaded, not free ground |
| core 0 `0x38000–0x3800f` | table/read-only | ✅ read every frame |
| core 0 `0x38010–0x38012` | loaded | ✅ boot/load data |
| core 0 `0x38013–0x3ffff` | **free** | ✅ 32,749 words in both summaries; this is only core 0's view and is subject to the layout's shared-window claims |
| core 1 `0x30000–0x30044` | table/read-only | ✅ core-1 reads the cross-core staging words |
| core 1 `0x30045–0x300aa` | loaded | ✅ bootstrap data |
| core 1 `0x300ab–0x31fff` | free | ✅ no-reverb ledger |
| core 1 `0x32000–0x32039` | loaded | ✅ bootstrap B |
| core 1 `0x3203a–0x37fff` | free in no-reverb B+C | ✅ exact range; all-run configurations use it for effect state |
| core 1 `0x38000–0x3800f` | state/table | ✅ per-core state/readback |
| core 1 `0x38010–0x3ffff` | loaded/effect storage | ✅ no-reverb ledger marks it loaded; all-run ledger shows the FX2 slot owner |

## Acceptance and open item

The complete four-run ledger is reproducible: each source configuration ran
1,000 frames, and the wordmap/classifier output is committed in the packet
report. The heavier check was attempted twice with
`core0_wordmap.sh`:

1. an eight-track FLEX/slice/recorder fixture without a staged FLEX sample
   exited `-11` before `wordmap.bin` was created;
2. the same fixture with the existing 440 Hz FLEX sample staged and
   `SLIC=1` still exited `-11` before `wordmap.bin` was created.

Therefore `X:0x2840–0x3fff` remains `🟡` for the heavier workload. No
additional attempt is made in this packet; the packet is `blocked` under the
two-honest-attempt rule. A future run should first fix or isolate the emulator
crash, then repeat the exact heavy fixture and inspect the generated wordmap.
