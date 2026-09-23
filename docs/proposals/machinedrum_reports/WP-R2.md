# WP-R2 The TRX-S2 residual: report

- **Status:** review
- **Branch and commit:** `machinedrum` @ `PENDING`
- **Date:** 2026-09-24
- **Agent:** Codex

## What was done

The `c1d_16` first-render mismatch was watched at `P:0x102d49` and at the
later loop reads identified by disassembly. The entry registers and memory
words are now recorded at the divergent block, and the packet leaves D3 for
the user: retain the 36-word swap or carry the complete low image.

## Acceptance check

The clean JIT replay still reproduces the known residual:

```
$ out/md_reference/md_replay out/md_profile/cap4/c1d_16 2>&1 | grep '^blocks:'
blocks: 31555 identical, 1951 differ (first difference at block 2288)
```

The disassembly around the entry and later reads is:

```
$ out/md_reference/md_dis out/md_profile/cap4/c1d_16/snapshot.bin 102d49-102db2
P:102d49  move #>$60,r0
P:102d4b  move #>$1f,m0
P:102d4d  move #>$40,r1
P:102d4f  move #>$1f,m1
P:102d52  macr -y1,x1,b x:(r7)+,b y:(r3)+,b
...
P:102d80  move b1,r3
P:102d81  add x,b
P:102d82  and #>$7fff,b
P:102d84  do #<$1f
P:102d86  move y:(r3+$148000),y1
P:102d87  move x:(r0)-n0,x1
...
P:102d8d  move y:(r3+$148000),y1
...
P:102dac  move b1,r3
P:102dad  add x,b
P:102dae  and #>$7fff,b
P:102db0  do #<$1f
P:102db2  move y:(r3+$148000),y1
```

## Measured

- ✅ `c1d_16` first differs at block `2,288`; the differing block has one
  slot-0 output word mismatch in the clean JIT replay.
- ✅ At the divergent block, a temporary block-numbered register and memory
  watch produced:

  ```
  $ MD_REPLAY_WATCH=102d49,102d52,102d8d,102db2 MD_REPLAY_WATCH_MAX=100 MD_REPLAY_WATCH_MEMORY=1 MD_REPLAY_BLOCKS=2304 out/md_reference/md_replay out/md_profile/cap4/c1d_16
  watch 102d49 block 2288: ... 34=00001e ... 37=000040 ... 41=000100 ... B=0612c1e0000000
  watchmem block 2288 pc 102d49 r3 000040 Y[r3] f81a02 r7 000100 X[r7] 000000 Y[148000+r3] 01921d X100 000000 Y040 f81a02
  watchmem block 2288 pc 102d8d r3 007bcc Y[r3] 000000 r7 000100 X[r7] 000000 Y[148000+r3] e5d061 X100 000000 Y040 f81a02
  watchmem block 2288 pc 102db2 r3 001f00 Y[r3] 000000 r7 000100 X[r7] 000000 Y[148000+r3] 7fd885 X100 000000 Y040 f81a02
  slot 0: 143 identical, 1 differ
  blocks: 2303 identical, 1 differ (first difference at block 2288)
  ```

  Here register numbers `37` and `41` are `R3` and `R7`. The watch was a
  temporary diagnostic; it was removed and `md_replay.cpp` was rebuilt clean.
- ✅ The first MAC at `P:0x102d52` reads `X:0x100` and `Y:0x40`. The later
  reads are sine-table reads at `Y:0x148000+R3`, not the initial low-memory
  pair.
- ✅ Poisoning `Y:0x40–0x41` and, separately, `X:0x100–0x101` did not move
  the first mismatch or remove it. *Inferred:* the watch locates the
  carry-in reads, but neither narrow poison is enough to attribute the
  output to one word in isolation.
- ✅ Section 12 of `MACHINEDRUM_MACHINE.md` records the register/memory
  watch, the disassembly, and the D3 options.

## Retracted

None. The earlier section-12 result that the first TRX-S2 render reads
scratch it did not write is confirmed and made more precise; no existing
measurement was withdrawn.

## Open and handover

- **D3 is for the user.** The current driver swaps 36 MD state words and
  leaves the measured `c1d_16` one-block and `c10_16` two-block residuals.
  Carrying the full low image (`X:0–0xff`, `Y:0–0x13f`, 576 words each way)
  fixed `c1d_16` in the prior A/B but not `c10_16`; its additional cost is
  about 70 cycles/sample, estimated rather than hardware measured.
- The next packet is WP-R1. The temporary watch and poison changes are not
  part of the source tree.
