# WP-B2 Build-time extraction: report

- **Status:** blocked
- **Branch and commit:** `machinedrum` @ `50ecf58`
- **Date:** 24 September 2026
- **Agent:** overnight Machinedrum handover

## What was done

Added a standalone, user-input-only payload audit in
`tools/build/md_payload.py` and `tools/verify/verify_md_payload.py`. It runs
the pinned `modules/machinedrum/extraction.py` recipe, consumes the measured
27-unit/2,724-word hot split through the new `--hot-plan` relocator mode, and
assembles the 192-word driver; all generated files remain under ignored
`out/machinedrum/build`. The audit now fails closed before writing a payload
or manifest because the current A2 map puts the full relocated external span
where the sine initializer writes.

## Acceptance check

The pinned extraction passed:

```text
$ python3 modules/machinedrum/extraction.py
input    Elektron_SPS1-1UW_OS1.63.syx  sha256 a58cd61f2efacfb0  ok
section_1_DSP.bin: 135 load records, P 234714, X 13130, Y 1868 words
section_2_DSP.bin: 58 load records, P 18489, X 66, Y 88 words
engines  135 descriptors: GND 4, TRX 14, EFM 8, E12 16, P-I 9, INP 6, MID 16, CTR 6, ROM/RAM 56
         core synthesis catalog (TRX/EFM/E12/P-I/GND, EMPTY excluded): 50
wrote    out/machinedrum/os163/inventory.json
```

The build audit intentionally exits nonzero:

```text
$ python3 tools/build/md_payload.py
hot: pinned 27 measured units, 2724 words at 1000
code: 13757 instructions, 15813 words, from 207 entry points
patches: abs 1, disp 157, imm 116, init 4, live 0, loop 343, loopvar 13, rel 23, table 425, target 2
192 words at 3fe00
layout audit: proposed A2 map is not yet an emit-safe B2 map
  BLOCKED: M 140000..148000 -> 030000 places 29,760 source-loaded external words in the sine allocation 030000..038000; the relocated init writes all 0x8000 sine words there
  BLOCKED: the source-space alias/load policy for the external Y descriptor span must be resolved with the A2 layout sign-off
md-payload: no payload written; move the source code/tables into the window allocation (or revise layout.py) before B2 can pass
[exit 1]
```

The relocator/driver regression used the identical measured hot plan because
the stored fetch files name relocated destination PCs; using `--hot` again
would select from the wrong address space:

```text
$ twelve-kit gate: md_replay baseline; md_relocate.py --hot-plan <canonical reloc.txt>; md_driver.py --reloc; md_replay --reloc --driver
GATE c01_16  baseline blocks: 33513 identical, 0 differ
GATE c01_16  relocated blocks: 22526 identical, 10987 differ (first difference at block 2272)
GATE c10      baseline blocks: 33513 identical, 0 differ
GATE c10      relocated blocks: 32262 identical, 1251 differ (first difference at block 2432)
GATE c10_3    baseline blocks: 33508 identical, 0 differ
GATE c10_3    relocated blocks: 32257 identical, 1251 differ (first difference at block 2400)
GATE c1d_16   baseline blocks: 31555 identical, 1951 differ (first difference at block 2288)
GATE c1d_16   relocated blocks: 19354 identical, 14152 differ (first difference at block 0)
GATE c37_16   baseline blocks: 33504 identical, 0 differ
GATE c37_16   relocated blocks: 33504 identical, 0 differ
GATE c47_2    baseline blocks: 33415 identical, 87 differ (first difference at block 864)
GATE c47_2    relocated blocks: 33415 identical, 87 differ (first difference at block 864)
GATE c10_16  baseline blocks: 33506 identical, 0 differ
GATE c10_16  relocated blocks: 22296 identical, 11210 differ (first difference at block 2305)
GATE c20_16  baseline blocks: 33499 identical, 0 differ
GATE c20_16  relocated blocks: 8253 identical, 25246 differ (first difference at block 0)
GATE c24_16  baseline blocks: 33505 identical, 0 differ
GATE c24_16  relocated blocks: 23027 identical, 10478 differ (first difference at block 0)
GATE c30_16  baseline blocks: 33513 identical, 0 differ
GATE c30_16  relocated blocks: 33474 identical, 39 differ (first difference at block 3919)
GATE c40_16 bounded blocks: 1 identical, 0 differ
GATE c42_16 bounded blocks: 1 identical, 0 differ
```

The full `c40_16` replay was stopped after roughly 90 seconds with no
result; `c42_16` was also only bounded. These are not acceptance passes.

The follow-up static packing audit is reproducible and fails on the
conservative source budget:

```text
$ python3 tools/verify/verify_md_layout.py
static reachable code: 15,813 words
internal low-P loop excluded from packing: 132 words
external source code: 15,681 words
measured hot split: 2,724 source words
post-hot code: 12,957 words
source 100000..103db9: code 9,801, loaded 15,509, gaps 293
source 140000..147fff: code 5,880, loaded 29,760, gaps 3,008
P external records: 16,440; code aliases 5,460; non-code 10,980
X external records: 13,056; code aliases 36; non-code 13,020
Y external records: 264; code aliases 136; non-code 128
post-hot code + existing max table budget: 41,018 words
proposed window + Y-only capacity: 40,960 words
FAIL: static code/table budget exceeds capacity by 58 words
[exit 1]
```

Review verification on 24 September: `md_replay out/md_profile/cap4/c10`
returned `33513 identical, 0 differ`; `make check REMIX=bamsep26` and
`make check REMIX=machinedrum` passed all runnable gates without an
`OT_PROJECT`. `python3 -B tools/build/md_payload.py` exited 1 at the
documented sine/source collision and emitted no payload. These checks
validate the current emulator/tooling behavior, not an Octatrack boot or
hardware result.

## Measured

- ✅ The input SysEx hash is the pinned
  `a58cd61f2efacfb07add0c643162fb4365c30e73831f2021c17b4aa3b42cabd5`;
  section 1 has 135 records and `234,714/13,130/1,868` P/X/Y words. This is
  from `python3 modules/machinedrum/extraction.py`; the update and all
  extracted files remain outside Git.
- ✅ The twelve existing relocation plans have the same 27 hot M-lines and
  2,724 words at `P:0x1000`; the builder records the common plan hash rather
  than reselecting from destination fetch PCs.
- ✅ The relocator decodes 13,757 instructions / 15,813 words from 207 entry
  points and the current driver assembles to 192 words at `P:0x3fe00`.
- ✅ The raw external source span `0x140000–0x147fff` contains 29,760 loaded
  words and 3,008 gaps. This is measured from the pinned section-1 records.
- ✅ The static relocator reachability audit finds 15,813 code words, including
  the explicit boot-init root. Of these, 132 words belong to the existing
  low-P loop and are excluded from external packing. After removing the
  measured hot split, 12,957 external code words remain. It finds 9,801
  code words in the first external region and 5,880 in the second.
- 🟡 With the existing maximum table budget of 28,061, that conservative
  post-hot placement input is 41,018 words against 40,960 proposed shared
  plus Y-only capacity: a 58-word shortfall. The earlier A2 budget closes at
  40,958 because it uses a 15,621-word engine-code estimate, 60 fewer than
  this audit's external source set. The difference must be classified before
  a packed B2 layout can be claimed. This remains an upper-bound estimate,
  not proof that every statically reachable word needs a separate slot.
- 🟡 The relocated init still passes `sine 32768/32768`, `pi 9216/9216`,
  `voice-X 1024/1024`, and `voice-Y 1024/1024` on c10 and c37_16, but that
  success also proves why the current payload placement is unsafe: init owns
  every word of `0x30000–0x37fff`.
- 🟡 The source Y alias record `0x147e00–0x147f07` has 264 words; 201 differ
  from the c10 post-boot P view. The builder cannot silently choose between
  the pre-boot load record and the post-boot runtime state.
- All B2 results are **pending the user's layout sign-off** and are not an
  image or flash qualification.

## Retracted

- ❌ The first uncommitted builder attempt treated relocated `fetch.txt` as
  source-PC evidence and selected no hot units. The second attempt reused the
  measured hot plan but tried to treat the broad replay placement as the A2
  payload; its verifier stopped at `P:0x37e00` (`payload 300000`, reference
  `150000`). The final audit fails closed instead of emitting that invalid
  output. No derived payload was committed.

## Open and handover

- **Blocked after two honest attempts:** A2 must choose the source/window
  policy before B2 can pass. The current test relocation maps the full
  `0x140000–0x147fff` span to `0x30000`, but the proposed sine allocation is
  exactly `0x30000–0x37fff` and the init writes all of it.
- The safe choices are: (A) revise `layout.py` and the relocator to split and
  pack code/tables into the `0x38000–0x3d9ff` shared range plus the proposed
  Y-only range; or (B) reserve a separate 32K shared span for the source
  region and move/relinquish another proposed owner. Even option A must first
  reconcile the conservative 58-word shortfall and the source-space alias
  policy; no alignment slack can be assumed.
- The user must also decide how the pre-boot Y descriptor alias is represented
  in the eventual load records. No new layout decision was made overnight.

## Decision, 24 September 2026

The user delegated this choice. **Option A, the packed split**, with
one extension: a table that is read in one space only goes to private
memory. Y-only tables go to `Y:0x4000–0x85ff`, as proposed. X-only
tables go to core 0's free private X (about 9,870 words, listed in
`MACHINEDRUM_MACHINE.md` §12, "Diagnosis of the A3 gate"). The sine
is read through both X and Y, so it stays in the window. Option B is
not taken: the window has no second free 32K span.

The inferred capacity leaves about 10K words spare against the
28,061-word maximum table estimate, so the 58-word shortfall above does
not apply once X-only tables can leave the window. That depends on a
measurement not yet made: which space each table span is read through.

Next:
1. Measure the access space per table span across the twelve kits.
2. Replace the two whole-span moves with per-table moves, and give the
   sine its own destination.
3. Rerun the twelve-kit gate (this also unblocks WP-A3).
4. Make `md_payload.py` emit from the packed map.

## Access-space measurement, 24 September 2026

```text
$ tools/harness/md_reference/md_reads.sh <scratch> <the twelve captures>
$ python3 tools/harness/md_reference/md_reads.py <scratch>/reads/*/reads.txt
captures: 12
tables (maximal runs of loaded non-code words), words by class:
  X      23,000 words in 18 runs
  XY      4,122 words in 3 runs
  Y       1,706 words in 13 runs
  unread  1,242 words in 5 runs
  single-space (X or Y only): 24,706; needs the window: 4,122; unread: 1,242
sine 148000..14ffff: read 32,768 of 32,768 words, first..last read 148000..14ffff; by class XY 32,768
P-I buffers 135600..13b5ff: read 16,905 of 24,576 words, first..last read 135600..13b4e6; by class X 16,905, unread 7,671
```

Tables are mostly X-only, not Y-only, so private Y barely helps. On core 0
the packed split does not fit unless the MD takes the whole window and runs
at most one P-I voice. See `MACHINEDRUM_MACHINE.md` §12, "Which space the
MD reads its data through". B2 stays blocked, now on the choice of core.



## Core-1 continuation, 24 September 2026

The core-0 blocker and counts above are historical. With the packed core-1
plan, `python3 tools/build/md_payload.py` now succeeds from the user's
pinned OS 1.63 update, writing ignored
`out/machinedrum/build/payload_B.mem` and a source/plan/driver manifest.
The builder reuses the 49 measured hot units in the twelve-kit plan,
assembles the 199-word driver at P:0x1f00, and applies the 203 flips,
14 splits, and one P-I phase expansion. It emits 21 sparse P/X/Y records,
106,694 words, 426,974 bytes; the verifier matches every word against the
relocated source snapshot. The payload SHA-256 in this local build is
`140365542adf3b58f41a0af5f1acdda81200ff97efd04ad69feee8727d99bf30`.

All emitted addresses are checked against `layout.py`. Only X:0..ff and
Y:0..13f may appear outside owned allocations because the driver swaps
those ranges. The update's higher internal X/Y records include the MD
loop's old DMA words and render-buffer state; the new driver does not load
them over stock OT state. Shared-window Y patches are emitted in the
single physical P load image.

This is a verified **load-record artifact**, not an OT payload-B integration
or bootable image. The loader and native dispatcher still have to consume
the records at the right time, run the relocated MD initialization path,
make sample-ROM content available, and connect engine/parameter state to
the track machine. The generated artifact stays outside Git.

The new `python3 tools/harness/md_reference/md_init_gate.py` compares
original and relocated init from each of the twelve captured states after
zeroing the destinations. It reports zero differences for all twelve,
including c37_16, whose second init differs from its own post-boot snapshot.
That distinction is why the gate compares two executions rather than treating
an already-running capture as an init oracle.
