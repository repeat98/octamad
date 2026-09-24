# WP-A2 (core-1 redo) and WP-A3: layout, relocation and the gate — frozen state

- **Status:** in progress, frozen 24 September 2026 (usage limit). WP-A2: review. WP-A3: 7 of 12 kits pass.
- **Branch:** `machinedrum`
- **Agent:** Claude, interactive session in the WSL checkout

## What was done

- `modules/machinedrum/layout.py` is now core 1's address book (the core-0
  map is superseded):
  - private P `0x0591–0x1eff` for hot code, the driver at `0x1f00`;
  - voice records at `X/Y:0x8c00`: one address for both, since the engines
    use one base register;
  - driver storage in Y `0xb9c0–0xbe43`;
  - table spans: X `0x2840–0x3eff`, `0x5840–0x5fff`, `0x7a92–0x803f`,
    `0x8858–0x8bff`; Y `0x07a5–0x8bff` and `0x9000–0xb9bf`;
  - the window: code at `0x34000–0x363ff`, tables at `0x36400–0x37fff`, the
    sine at `0x38000`.

  `manifest.py` and `remixes/machinedrum.py` follow the new layout
  (payload-B donor). `make modules` passes.
- `md_flip.py --plan out/machinedrum/plan.json` packs the regions:
  - best fit, largest first, each region keeping its alignment (capped at
    `0x200`);
  - into private X/Y, falling back to the window's table area.

  It also emits the flips and the splits. Each split is assembled with
  `dsp_asm`, keeps the original ALU byte, and is decoded back. The two halves
  are ordered so that no read sees a value written in the same original
  instruction. Two region fixes went in:
  - fragments separated only by never-executed words are merged;
  - a base named in word B of code that runs is taken into the table it
    indexes (e.g. `add #>$145224,a`).
- `md_relocate.py` has been rewritten, driven by the plan:
  - code moves unit by unit, with a hardware loop's whole body kept in one
    unit;
  - the hot units come from `out/md_fetch/*/fetch.txt`;
  - one address map handles the inserted split words;
  - tables move by `T` lines into private X/Y, or by `M` lines to the window;
  - live pointers are patched only in the MD's internal RAM (below `0x1000`);
  - `--keep` and `--no-live` are bisection aids.
- `md_replay` gains the `T` line and records window accesses.
  `md_driver.py` reads `T` lines. `md_gate.sh` runs the twelve-kit gate.

## The gate (`sh tools/harness/md_reference/md_gate.sh`), current plan

```
c01_16  plain 33503 identical, 0 differ      moved 33503 identical, 0 differ
c10     plain 33513 identical, 0 differ      moved 33513 identical, 0 differ
c10_3   plain 32804 / 698 (capture)           moved 32804 / 698 (same)
c47_2   plain 33502 / 0                       moved 33502 / 0
c24_16  plain 33505 / 0                       moved 33505 / 0
c30_16  plain 33513 / 0                       moved 33513 / 0
c10_16  plain 33506 / 0                       moved 33504 / 2   (known TRX-S2 driver residual, WP-R2)
c1d_16  plain 31563 / 1949                    moved 30900 / 2612 (first at 2288)
c37_16  plain 33511 / 0                       moved 31570 / 1941 (first at 2458, slot 10, P-I)
c20_16  plain 33499 / 0                       moved 32173 / 1326 (first at 2289)
c40_16  plain 33505 / 0                       moved 29610 / 3895 (first at 2273)
c42_16  plain 33505 / 0                       moved 31558 / 1947 (first at 2357)
```

Plan numbers (`out/machinedrum/plan.json`):
- private X 9,247 words, private Y 44,381, window tables 2,675; plus the sine
  and the window code;
- 161 flips, and 31 static flips (instructions no capture ran);
- 22 splits, +12.1 instructions per sample in the worst kit (c40_16), an
  emulator count.

Hot code is 6,511 words; the window code is about 8,250.

## What is known about the five failing kits

- Correction: The frozen claim that `--keep all` makes every kit exact was too
  strong. c1d_16 retains one known driver-residual block at 2288 even
  with every table kept; the other table-driven failures disappear.
- Measured: c20_16 breaks when the P-I buffers move. Its first non-pointer
  value difference is in the generated low-X phase sequence.
- Measured: c37_16, c40_16 and c42_16 break when table `0x142f33` moves.
  The table word read by the renderer is unchanged; the numerical phase
  values derived from its new pointer are not.
- Measured: Poisoning the plain run's low X scratch
  (`MD_REPLAY_POISON=X:0-100`) changes nothing in c37_16.

## 24 September continuation: read values at the first failing blocks

The interpreter replay now accepts `MD_REPLAY_VALUES=<file>` and
`MD_REPLAY_VALUE_BLOCK=<zero-based block>`; `md_values.py` maps moved
PCs, data addresses and pointer-looking values back through `reloc.txt`.
The trace records instruction RAM reads in execution order. Build with
`cmake --build out/md_reads/build --target md_replay_reads -j8`.
For c37_16, set `MD_REPLAY_BLOCKS=2459` and
`MD_REPLAY_VALUE_BLOCK=2458`, run once plain and once with
`--reloc --driver`, then compare the trace files with
`python3 tools/harness/md_reference/md_values.py <plain> <moved> <reloc.txt>`.
The scratch traces contain capture-derived values and stay outside Git.

- Measured: c37_16 (block 2458), c40_16 (2273) and c42_16 (2357):
  the first non-pointer difference is `P:142dd3` reading `Y:0x20`.
  The matching keep-`142f33` control reads `0x800001`; the current X
  placement reads `0x000001`. The preceding sample read has the same
  word (`X:142f4b` or `X:007aaa`, both `0x0027a6`).
  At the phase loop's relocated `P:0x1938`, the accumulator high words
  contain the old versus new table pointer. A dump immediately after
  the 32-pointer table is built shows all 32 X words shifted by the
  address delta, while Y:0, Y:1, Y:0x20 and Y:0x21 differ by
  `0x800000`. Keeping only `142f33` makes c37_16's first 2,459
  blocks match; moving it to X or the window fails.
- Measured: c20_16 (block 2289) and c1d_16 (first *new* block 2290):
  `P:102fae` reads a P-I buffer pointer from `X:0x15`. Its moved
  value is an equivalent physical pointer, but the first non-pointer
  difference is at `P:102fc5`, reading `X:0x1a` (c20_16:
  `0x8bfa7c` versus `0x78ac7c`; c1d_16:
  `0x8c003c` versus `0x78b23c`). The disassembly at
  `P:102faf` adds that pointer to accumulator A before generating
  the scratch sequence. Keeping the P-I buffers at their old addresses
  removes c20_16's first mismatch and c1d_16's new mismatch at 2290.
- Measured: c1d_16 has a separate driver residual: even with `--keep all`,
  its full result is 31,562 identical / 1,950 different, against the
  plain 31,563 / 1,949. The extra block is 2288, where
  `P:102ee5` reads `X:0xa2` as `0x7fffff` instead of zero.
  The current plan adds 662 more differing blocks; the first is 2290.
- Measured: `--no-live` is not a useful broad control: c37_16 jumps to
  wiped `P:0xa5a5a5` after 1,280 instructions without required live
  pointers. No low X/Y snapshot word lies in
  `0x142f33..0x1433d6` in c37_16, so an accidental live-pointer
  rewrite in that range is not its cause.

*Inferred fix direction:* these engines use address values in numerical
phase calculations as well as for memory access. A simple pointer
rewrite changes the math. Relocation needs separate logical MD pointer
values and physical OT access addresses at these two P-I sequences;
verify the transformation on all twelve kits and count its instruction
and cycle cost before taking it into the payload.

## Caveats

- The captures on this machine differ from the Mac's (WP-A7), so these
  baselines are this machine's.
- The moved code calls `P:0x0143`. Its 23-word straight-line init routine
  now moves to the shared window at `P:0x34000`; the two callers branch
  there. None of the captured fetch profiles visits the routine, so the
  replay gate does not prove its runtime behavior. Its `#>$147e00`
  metadata table is now copied to `0x37200..0x373ff`; the pointer and
  nine other absolute references are patched. Several table entries
  point into MD sample ROM above `0x150000`; that delivery remains open.
- The four 128-word writable E12 buffers at `0x135206..0x135405`
  now occupy the shared window at `0x37000..0x371ff`. The four base
  immediates and the exclusive-end comparison at `0x135406` are patched.
  The gate result is unchanged; these instructions were not observed in
  the captured fetch profiles.
- `tools/build/md_payload.py` (WP-B2) still reads the core-0 allocation
  names. It is not in `make`, and it will be redone on this layout.

## Handover

1. Make the P-I code preserve logical MD pointer arithmetic while
   translating memory accesses to the physical core-1 homes. The two
   measured sites are `P:142db4..142dd3` for table `142f33` and
   `P:102fae..102fc5` for the P-I buffers.
2. Rerun the twelve-kit gate and separate c1d_16's known one-block
   driver residual from any new relocation mismatch.
3. Exercise the low-P port, E12-tail writes and sample metadata in an
   init or targeted replay. Resolve sample-ROM pointers above `0x150000`,
   then rebuild WP-B2.
