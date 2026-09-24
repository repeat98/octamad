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
