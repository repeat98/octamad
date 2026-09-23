# WP-A3 Layout-driven relocation and driver: report

- **Status:** review
- **Branch and commit:** `machinedrum` @ `ab87e7e` (metadata follow-up commit)
- **Date:** 24 September 2026
- **Agent:** overnight Machinedrum handover

## What was done

`md_relocate.py` and `md_driver.py` now read their relocation, hot-code, loop,
scratch, and driver-code addresses from `modules/machinedrum/layout.py`.
The source spans are relocated to `P:0x38000` and `P:0x30000`, hot units to
`P:0x1000`, the loop words to `Y:0x0c00`, and the driver to `P:0x3fe00`.
The legacy `--loopvars` argument remains an explicit override, but the normal
path needs no address argument.

## Acceptance check

```
$ python3 modules/machinedrum/layout.py
PASS: 12 MD allocations are internally non-overlapping
PASS: source budgets fit with max_pi_voices=6
REVIEW: 8 stock conflicts remain explicitly listed

$ head -2 out/md_profile/cap4/c10/reloc.txt; grep '^V ' out/md_profile/cap4/c10/reloc.txt | head -4; cat out/md_profile/cap4/c10/driver.cfg
M 100000 103dba 038000
M 140000 148000 030000
V 000140 000c00
V 000141 000c01
V 000142 000c02
V 000153 000c10
LV140 000c00
LV141 000c01
LV142 000c02
ENG 000c10
HALF 000c03
TMP 000c04
OUTBUF 000d00
STASH 001800
MDSAVE 000f20
INIT 035af5
TRIG 035bb6
RENDER 035c77
EMPTY 03808f
MDFULL 000000

$ out/md_reference/md_replay out/md_profile/cap4/c10 --reloc --driver
blocks: 33513 identical, 0 differ

$ MD_REPLAY_STATEDIFF=5 out/md_reference/md_replay out/md_profile/cap4/c10 --reloc --driver
state block 13744 slot 0: [3] emu 000b54 ref 000b45
state block 14144 slot 0: [3] emu 000b35 ref 000b45
state block 14528 slot 0: [3] emu 000b45 ref 000b54
state block 14720 slot 0: [3] emu 000b54 ref 000b64
blocks: 33513 identical, 0 differ
```

The full twelve-kit gate used one hot-set relocation over all twelve capture
directories and assembled each driver without `--loopvars`:

```
cap4/c01_16  33513/0 -> 33513/0
cap4/c10      33513/0 -> 33513/0
cap4/c10_3    33508/0 -> 33508/0
cap4/c1d_16   31555/1951 -> 31554/1952
cap4/c37_16   33504/0 -> 33504/0
cap4/c47_2    33415/87 -> 33415/87
cap5/c10_16   33506/0 -> 33504/2
cap5/c20_16   33499/0 -> 33499/0
cap5/c24_16   33505/0 -> 33505/0
cap5/c30_16   33513/0 -> 33513/0
cap5/c40_16   33505/0 -> 33505/0
cap5/c42_16   33505/0 -> 33505/0
```

The gate accepts the two known TRX-S2 residual patterns. No other kit gained
a difference.

## Measured

- ✅ The layout checker reports 12 internal allocations with no overlap and
  the six-voice source budget fits. This is recorded in section 12 of
  `MACHINEDRUM_MACHINE.md`.
- ✅ `md_driver.py` assembled 192 words at `P:0x3fe00`, below the proposed
  512-word driver allocation. The result is written only under ignored
  `out/`.
- ✅ The relocator emitted `100000–103dba → 38000`,
  `140000–148000 → 30000`, and `140–142 → 0c00–0c02`; the driver config
  emitted `HALF=0c03`, `TMP=0c04`, `OUTBUF=0d00`, `MDSAVE=0f20`, and
  `STASH=1800`.
- ✅ The twelve-kit gate produced 10 unchanged results and only the known
  `c1d_16`/`c10_16` residual deltas above.
- ✅ `MD_REPLAY_STATEDIFF=5` was checked on c10; the four printed late word-3
  differences did not change any rendered block. The driver takes the voice
  block base from `r6` and does not move it through another address register.

## Retracted

None.

## Open and handover

- **User sign-off required:** accept or reject the WP-A2 proposed stock-slot
  conflicts, the `X/Y:0x3400` voice home, and the six P-I-voice budget. Until
  then this packet stays `review`; every A3 result is pending that sign-off.
- The two known first-render residuals remain the D3 choice documented in
  section 12: keep the 36-word swap, or pay the estimated ~70 cycles/sample
  for the full low-image swap (which still does not fix c10_16).
- WP-A4 can now exercise boot-time init against these relocated addresses.
