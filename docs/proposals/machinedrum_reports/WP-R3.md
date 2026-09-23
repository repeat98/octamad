# WP-R3 The interpreter/JIT mismatch: report

- **Status:** blocked
- **Branch and commit:** `machinedrum` @ `94ef689`
- **Date:** 24 September 2026
- **Agent:** overnight Machinedrum handover

## What was done

Compared the existing JIT and forced-interpreter replays on `cap4/c01_16`
and `cap4/c1d_16`, then used temporary, uncommitted trace instrumentation to
probe JIT block boundaries. The mismatch is reproducible and the boundary
probe isolates `ADD X,B` immediately after `MOVE B1,R3` in both captures, but
the result depends on whether the old JIT keeps that instruction in the same
block; this is not enough evidence to blame one standalone interpreter
opcode. The temporary tracing was removed and both replay binaries were
rebuilt; no vendor source or firmware-derived bytes changed.

## Acceptance check

The normal replay comparison remains:

```
$ out/md_reference/md_replay out/md_profile/cap4/c01_16 2>/dev/null | grep '^blocks:'
blocks: 33513 identical, 0 differ
$ out/md_reference_interp/md_replay out/md_profile/cap4/c01_16 2>/dev/null | grep '^blocks:'
blocks: 30873 identical, 2640 differ (first difference at block 2340)
$ out/md_reference/md_replay out/md_profile/cap4/c1d_16 2>/dev/null | grep '^blocks:'
blocks: 31555 identical, 1951 differ (first difference at block 2288)
$ out/md_reference_interp/md_replay out/md_profile/cap4/c1d_16 2>/dev/null | grep '^blocks:'
blocks: 31218 identical, 2288 differ (first difference at block 2272)
```

The two honest isolation attempts were:

```
$ MD_REPLAY_BLOCK_SIZE=18 MD_REPLAY_BLOCKS=2400 out/md_reference/md_replay out/md_profile/cap4/c01_16 2>/dev/null | grep '^blocks:'
blocks: 2396 identical, 4 differ (first difference at block 2340)
$ MD_REPLAY_BLOCK_SIZE=19 MD_REPLAY_BLOCKS=2400 out/md_reference/md_replay out/md_profile/cap4/c01_16 2>/dev/null | grep '^blocks:'
blocks: 2400 identical, 0 differ
$ MD_REPLAY_BLOCK_SIZE=8 MD_REPLAY_BLOCKS=2300 out/md_reference/md_replay out/md_profile/cap4/c1d_16 2>/dev/null | grep '^blocks:'
blocks: 2298 identical, 2 differ (first difference at block 2272)
$ MD_REPLAY_BLOCK_SIZE=9 MD_REPLAY_BLOCKS=2300 out/md_reference/md_replay out/md_profile/cap4/c1d_16 2>/dev/null | grep '^blocks:'
blocks: 2299 identical, 1 differ (first difference at block 2288)
```

The relevant disassembly is:

```
$ out/md_reference/md_dis out/md_profile/cap4/c01_16/snapshot.bin 10078e-100790
10078e 1 21b300 200028 move    b1,r3
10078f 1 200028 0140ce add     x,b
$ out/md_reference/md_dis out/md_profile/cap4/c1d_16/snapshot.bin 102d80-102d82
102d80 1 21b300 200028 move    b1,r3
102d81 1 200028 0140ce add     x,b
```

## Measured

- ✅ The four normal replay lines above were measured after restoring the
  original `tools/harness/md_reference/md_replay.cpp` and rebuilding both
  targets. The JIT is still the bit-identical reference on c01; c1d retains
  the already documented TRX-S2 residual.
- ✅ Changing only the old JIT maximum block size changes the c01 result at
  block 2340 and the c1d first difference between blocks 2272 and 2288. The
  threshold crosses the `ADD X,B` after `MOVE B1,R3` in each capture.
- *inferred* The old JIT's block-boundary/register-allocation handling around
  `ADD X,B` is the common suspect. A corrected vendor implementation must be
  tested before calling the interpreter or JIT authoritative.
- The measured result and handover were added to `docs/proposals/MACHINEDRUM_MACHINE.md`
  §12.

## Retracted

None. The existing section-12 statement that the interpreter/JIT discrepancy
was unexplained is narrowed to the measured `ADD X,B` block-boundary region,
not declared fixed.

## Open and handover

- **Blocked on WP-R4/toolchain ownership:** the checkout still uses the stale
  vendor pin `c051afad`. The user must rerun `scripts/setup.sh` to repin the
  shared vendor, then rerun both c01/c1d parity checks and this boundary
  probe.
- Do not rebuild or modify the shared `vendor/` in this packet. No firmware,
  samples, `.syx` files, or extracted blobs were committed.
- This research packet is not layout-dependent and does not require the
  twelve-kit gate.
