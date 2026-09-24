# WP-A7 The X/Y flip audit: report

- **Status:** done
- **Branch and commit:** `machinedrum` (the commit that adds this report)
- **Date:** 24 September 2026
- **Agent:** Claude, interactive session in the WSL checkout (`/home/jannikassfalg/octamad`)

## What was done

The core-1 direction (section 12, "Core 1's memory and the MD's full
footprint") moves the tables and P-I buffers into core 1's private memory by
flipping X reads to Y where the instruction form allows it. This packet
measured where it allows it, for every instruction that touched external data
in the twelve kits. It adds:

- `md_replay` `MD_REPLAY_ACCESS=<file>` (interpreter build): every data read
  and write by the PC that made it, and the executed PCs. `MD_REPLAY_INIT_ONLY=1`
  runs only the boot init at MD addresses (the replay never runs it).
  `md_reads.sh` adds a write hook in `Memory::dspWrite` and records both files.
- `md_forms.cpp`: the emulator decoder's form for each word, so the
  classification uses the emulator's own tables. It is built with the other
  reference tools (`md_profile.cmake`).
- `md_flip.py`: the audit. It builds regions, links the regions each
  instruction touches, and chooses a space per group. Then it packs the
  groups into core 1's free spans and checks each flipped word decodes as its
  twin. It also lists the stock precedent and a static census.
- `verify_md_layout.reachable_code()`: the static descent, returning
  instructions (`reachable_words` is unchanged; it gives 15,813 words, the
  recorded 15,681 external plus the 132-word loop).

The reference was rebuilt on this machine: `vendor/gearmulator-md-mm`
cloned at `8cea052`, with both `tools/patches/gearmulator-md-*.patch` applied.
The twelve captures were regenerated from the pinned dump (SHA-256
`68542e30…4fbca44c8`). `md_reads.sh` needed `vtuneSdk` on Linux; that is fixed.

## Acceptance check

```
$ for d in out/md_profile/cap4/c* out/md_profile/cap5/c*; do sh tools/harness/md_reference/md_reads.sh $PWD/out/md_reads $d; done
out/md_profile/cap4/c01_16 blocks: 31153 identical, 2350 differ (first difference at block 2340)
out/md_profile/cap4/c10 blocks: 33513 identical, 0 differ
out/md_profile/cap5/c10_16 blocks: 29948 identical, 3558 differ (first difference at block 2321)
out/md_profile/cap4/c10_3 blocks: 32804 identical, 698 differ (first difference at block 22338)
out/md_profile/cap4/c1d_16 blocks: 31226 identical, 2286 differ (first difference at block 2304)
out/md_profile/cap5/c20_16 blocks: 32827 identical, 672 differ (first difference at block 2390)
out/md_profile/cap5/c24_16 blocks: 32993 identical, 512 differ (first difference at block 2290)
out/md_profile/cap5/c30_16 blocks: 33513 identical, 0 differ
out/md_profile/cap4/c37_16 blocks: 33511 identical, 0 differ
out/md_profile/cap5/c40_16 blocks: 33505 identical, 0 differ
out/md_profile/cap5/c42_16 blocks: 33169 identical, 336 differ (first difference at block 2358)
out/md_profile/cap4/c47_2 blocks: 33502 identical, 0 differ

$ MD_REPLAY_ACCESS=$PWD/out/md_reads/init_access.txt MD_REPLAY_INIT_ONLY=1 out/md_reads/build/md_replay_reads out/md_reads/reads/c10
init: accesses recorded

$ python3 tools/harness/md_reference/md_flip.py out/md_reads/reads/*/access.txt --init out/md_reads/init_access.txt
captures: 12 (804,128 samples), plus the boot init
instructions with a data access: 5,528; executed: 9,788
[...]
  stray accesses (a pointer past its table; they link nothing): 6 sites
    143521 X home 143661 (1,300 words); stray e12 63, intX 45, pi 13, sine 11, 100881 4, 146000 3 ...
    143e84 X home 143f38 (1,275 words); stray intX 50, e12 8, code 3, pi 2, sine 1
    142ddd X home 142f33 (752 words); stray intX 19, e12 3, sine 2, pi 1
    142dde X home 142f33 (752 words); stray intX 19, e12 3, sine 2, pi 1
    144b3e X home 144c9a (210 words); stray intX 19, e12 3, sine 2, pi 1
    142180 X home 142279 (839 words); stray intX 10, e12 3, pi 1, sine 1
  code words read as data: 6 words by 2 instructions (143521, 143e84)

the MD's internal data touched: X 332 words, Y 1,218 words (the voice records, state and buffers; they keep their space)
[...]
plan within core 1's private memory: X spans 5,824, 1,984, 1,454, 1,960, Y span 47,195; reserved first: X 332 (MD internal), Y 2,374 (MD internal 1,218 + driver 1,156)
  left free: X 188, 43, 21, 2; Y 3,710
  words by home (E12 is a stream buffer and is left out; the sine's 32,768 are in the window): X 10,636, Y 41,111
    10050c 10050c..10074b     576 -> X
    100881 100881..101881   4,097 -> Y
    101ba0 101ba0..101e9f     768 -> X
    103c7b 103c7b..103d97     285 -> Y
    e12    103dba..135205 201,804 -> X
    pi     135600..13b5ff  24,576 -> Y
    140000 140000..1420ff   8,448 -> Y
    142279 142279..142886   1,550 -> X
    14294f 14294f..142b48     506 -> Y
    142b6a 142b6a..142d48     479 -> Y
    142f33 142f33..1433d6   1,188 -> X
    143661 143661..143d59   1,785 -> X
    143f38 143f38..1449e9   2,738 -> X
    144c9a 144c9a..144f28     655 -> X
    1452b3 1452b3..145423     369 -> X
    145426 145426..145623     510 -> X
    145af5 145af5..145d37     579 -> Y
    146e24 146e24..1475ff   2,012 -> Y
    smaller regions: X 497, Y 129
  rewrites: 14 instructions split into two single-space moves; one more instruction per execution, worst kit c40_16: 7.8 per sample
    142ea0 X dual  move    a,x:(r0)+       y:(r4)+,a                        0.93/smp
    142ea7 X dual  move    a,x:(r1)+       y:(r5)+,a                        0.93/smp
    142e9f X dual  move    b,x:(r0)+       y:(r4)+,b                        0.93/smp
    142ea6 X dual  move    b,x:(r1)+       y:(r5)+,b                        0.93/smp
    144c0b X dual  move    a,x:(r1)+       y:(r5)+,a                        0.93/smp
    144c0e X dual  move    b,x:(r0)+       y:(r5)+,b                        0.93/smp
    144c0f X dual  move    a,x:(r0)+       y:(r5)+,a                        0.93/smp
    144c0a X dual  move    b,x:(r1)+       y:(r5)+,b                        0.93/smp
    142eee Y dual  move    x0,x:(r3)+      y:(r5)+,y0                       0.06/smp
    142ef1 Y dual  move    x0,x:(r3)+      y:(r5)+,y0                       0.06/smp
    142ef7 Y dual  mpy     x1,x0,a         a,x:(r3)+       y:(r5)+,y0       0.06/smp
    144c54 Y dual  move    x0,x:(r3)+      y:(r5)+,y0                       0.06/smp
    144c57 Y dual  move    x0,x:(r3)+      y:(r5)+,y0                       0.06/smp
    144c5d Y dual  mpy     x1,x0,a         a,x:(r3)+       y:(r5)+,y0       0.06/smp
  flips: 178 instructions, each one bit; their forms after the flip:
    Movey_Rnxxxx.r            102; stock A+B     0  <-- no stock precedent
    Movey_ea.r                 59; stock A+B   299
    Movex_ea.r                 16; stock A+B  1833
    Movey_ea.w                  1; stock A+B   353
[...]
static census: reachable instructions with an X-space data operand, by class
  twin   1766   ran with a data access  1604, never ran   162
  split   112   ran with a data access    94, never ran    18
  dual    917   ran with a data access   419, never ran   498
  long    169   ran with a data access   157, never ran    12
```

The `[...]` parts are the region table, the option table per group, the list
of non-twin sites and the probe list; they are regenerated by the same
command. The interpreter replays diverge on six kits from about block 2,300
(the WP-R3 mismatch), so those kits' late accesses come from a slightly
different run. c10_3 differs under the JIT build as well (below).

## Measured

All in `MACHINEDRUM_MACHINE.md` section 12, "The flip audit: what can leave
the window".

- ✅ The P-I buffers are written through Y and read through X. All 14,848
  words written through Y (20 instructions) are read back through X. The boot
  init zeroes all 24,576 through X (`rep x0` / `move a,x:(r0)+`,
  `P:0x100066–0x100067`). The init also builds the sine through Y (`P:0x10008a`).
- ✅ Forms, over the static set: 1,766 X-space instructions have a one-bit
  twin, 112 are X:R/R:Y, 917 are XY dual moves and 169 are long moves.
  Of these, 162, 18, 498 and 12 never ran in any kit.
- ✅ Six sample-table readers run past their table and read memory below it.
- ✅ The static descent counts 939 data words in the table spans as code.
- ✅ The MD's internal data touched: X 332 words, Y 1,218.
- ✅ The span-packed plan: everything but the sine leaves the window, with
  178 flips and 14 rewrites (+7.8 instructions per sample, worst kit c40_16).
- ✅ Without rewrites, the P-I buffers and tables `0x142f33` and
  `0x144c9a` (26,419 words) stay in the window under every option.
- ✅ Precedent: the 102 two-word displaced Y reads the flips create have no
  stock site. The MD's reachable code already has 125 of them and 183 writes.
  Stock does use the one-word displaced Y move: 33 sites (3 in payload A,
  30 in payload B).
- *inferred* The P-I sub-buffers are 512-word modulo buffers (`m2 = $1ff` at
  `0x142e07`, `0x144b75`), so the P-I base needs 0x200 alignment.

The captures regenerated here do not all replay like the Mac's. JIT
`md_replay`, same builds and dump, blocks identical / total:

| Capture | Here (WSL, x86-64) | Recorded (Mac), section 12 or WP reports |
|---|---|---|
| c10 | 33,513 / 33,513 | 33,513 / 33,513 |
| c10_3 | 32,804 / 33,502 | 33,508 / 33,508 |
| c01_16 | 33,503 / 33,503 | 33,513 / 33,513 |
| c1d_16 | 31,563 / 33,512 | 31,555 / 33,506 |
| c37_16 | 33,511 / 33,511 | 33,504 / 33,504 |
| c47_2 | 33,502 / 33,502 | 33,415 / 33,502 |
| c10_16 | 33,506 / 33,506 | TRX-S2 residual, 2 blocks (WP-R2) |
| c20_16, c24_16, c30_16, c40_16, c42_16 | 33,499, 33,505, 33,513, 33,505, 33,505 / same | |

`md_profile` is therefore not reproducible across the two machines. Each
machine's gate needs its own baselines. The c1d_16/c10_16 TRX-S2 residuals
(WP-R2) are a Mac-capture result.

## Retracted

- ❌ "The P-I buffers `135600..13b5ff` are read through X only" was used as a
  placement fact ("Direction", item 4). It is true of the reads, but the
  buffers are also written through Y and depend on the X/Y alias. Marked in
  section 12.
- ❌ The table classes in "Which space the MD reads its data through" (X only
  23,000, X and Y 4,122, …) exclude 939 data words that the static set counts
  as code, so they are low. `md_flip.py` builds its regions from the
  accesses, so its totals include those words.
- ❌ Outside the MD work (not edited here): `CLAUDE.md` ("AN INSTRUCTION FORM
  THE CHIP HAS NEVER RUN") and `docs/remixer/FAILURE_MODES.md` (images 44/45)
  say no stock code uses the one-word displaced Y store. Stock payload B does:
  `move a,y:(r7+$0)` at `P:0xd3`, `move b,y:(r7+$1)` at `P:0xd4` and
  28 more, found with `md_forms` on `out/dsp/payload_B.asm` (from the stock
  `out/raw/section_3_MAIN_OS.bin`). The base register differs (`r7` there,
  `r3` in image 44). The user decides whether to correct those two files.
- ❌ A `md_dis` built against `vendor/dsp56300` (octamad's pin) gives a
  different static set: 16,281 words where the gearmulator-tree build gives
  15,813. Build `md_dis` and `md_forms` from `vendor/gearmulator-md-mm` only,
  as `md_profile.cmake` does.

## Open and handover

- **WP-A2 (core-1 layout) takes this plan as its input.** Only the sine
  (32K at `0x38000`) and the code beyond private P stay in the window. T8's
  FX2 slot would then hold code only, not tables (*inferred*; the code size
  comes from the hot split).
- **The rewrites need relocator support.** Splitting an instruction adds a
  word, which moves `do` loop ends and branch targets. All 14 are in
  two-instruction `do #16` block copies, and none is under a `rep`. Each
  splits as the store, then the load, which keeps the old-value semantics of
  the parallel move.
- **New decision D6: accept the plan's cost.** It needs 178 one-bit flips and
  14 rewrites, +7.8 instructions per sample worst case (emulator count). The
  alternative keeps the P-I buffers in the window (24,576 words), which the
  window cannot hold beside the sine.
- **Hardware probe list** (the CLAUDE.md rule): `Movey_Rnxxxx` is needed
  anyway by the MD's own 308 sites. The same goes for short-absolute X reads
  (149), short-absolute long moves (118), `rep #` (17), `dor #` (15),
  `lsl #` (12), and 25 forms with 3 sites or fewer. `md_flip.py --static`
  prints the list.
- **E12:** its 12 reading instructions are X twins. X is full after the plan
  (largest fragment: 188 words), so the stream buffer (WP-R1, D4) goes in Y,
  with 12 flips.
- **Strays:** after relocation the six runaway readers read different memory.
  Whether that reaches the output shows in the relocated gate. No placement
  can make those reads bit-identical.
- The internal reservation (X 332, Y 1,218 + the driver's 1,156) is one lump
  per space. The core-1 layout places the real blocks.
