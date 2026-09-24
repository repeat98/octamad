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

- ✅ With every table kept in place (`--keep all`), all five are exact. So
  the code relocation, the hot split, the flips, the splits and the sine move
  are correct.
- ✅ c20_16 breaks only when the P-I buffers move. Up to its first bad block,
  the only instructions whose accesses differ are the stray readers:
  `0x142180`, `0x142ddd`/`0x142dde`, `0x143521`, `0x143e84`. Their pointers
  run through the P-I buffers' old addresses.
- ✅ c37_16 and c40_16 break only when table `0x142f33` moves, to private X
  or to the window alike. Through the first bad block every instruction
  accesses the same addresses in both runs, window included, so a *value*
  differs.
- ✅ Poisoning the plain run's low X scratch (`MD_REPLAY_POISON=X:0-100`)
  changes nothing in c37_16. Stale low-X scratch is not the carrier.
- *Open, the next step.* Find the value that differs in c37_16 slot 10
  (P-I SD) at block 2458. Candidates:
  - an address held in a register or in Y scratch and used as data (the
    32-pointer phase table the sample readers build in `L:0..31` is one);
  - the stray readers' values.

  A value-level diff (record the values read, not only the addresses) would
  settle it.

## Caveats

- The captures on this machine differ from the Mac's (WP-A7), so these
  baselines are this machine's.
- The moved code calls `P:0x0143`, MD low code that is not relocated. On the
  OT that address is payload B's own code, so the routine must be ported
  (open).
- The immediates `#>$135206…$135386` and `cmp #>$135406` (just past the E12
  block) point at words no region holds. The replay still reads the old
  place; the OT needs a home for them.
- `tools/build/md_payload.py` (WP-B2) still reads the core-0 allocation
  names. It is not in `make`, and it will be redone on this layout.

## Handover

1. The value-level diff for c37_16/c40_16 (P-I, table `0x142f33`) and for
   c20_16.
2. Then c1d_16 and c42_16, which likely share a cause.
3. Resolve the `P:0x0143` port and the E12-tail homes before WP-B2.
