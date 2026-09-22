# CHARACTER

The station that dirties or tightens a track, on stock LO-FI's id 0x1c. FX1 only: an FX2 instance runs as a dry pass
(`Claims(fx1_only=True)`, `verify_character.py`); the FX2 chooser hides the
row.

| page 1 | DRV · FOLD · WDTH · COMP · TONE · MIX |
|---|---|
| page 2 | SAT (TAPE TUBE INFL) · WDTH · — · — · — · — |

Chain, fixed: fold → saturate → tilt → compress → width → mix.

- **FOLD** — WarpFold's wavefolder, 1 → 48× into the fold at a held level;
  first fold on a pad at ~24.
- **SAT / DRV** — three JClones (MIT) characters, re-derived here. TAPE =
  TapeHead: a state-variable split at TONE, the low and band parts through
  a cubic smoothstep, the top clean; drive 0.8× → 8× from a 17-word P table.
  TUBE = DaTube: u − u^P with the negative half driven twice as hard,
  level-compensated (a per-block division); the curve is a 17-pair P table.
  INFL = OInflator: a signed cubic, DRV is its Effect. DRV 0 skips the
  stage, bit-exact.
- **TONE** — a tilt after the saturator, drawn −64..+63; 0 flat, bit-exact.
- **COMP** — JClones AC1's console channel law: GLUE (slow, soft-kneed) on
  the master by position, COMP (fast) on every other track. One feedforward
  detector on the mono key, the gain applied to both channels.
- **WDTH** — mid/side: 64 untouched, 0 mono, 127 double sides.
- Page-1 slot 4 is TONE again (20 Sep 2026). It was RET, the bus return
  level, from 13 to 20 Sep 2026: on T8 by dispatch position the last live
  engine's wet entered at the front of the chain and the hosts were stamped
  quiet. The return was degraded on the unit and clean under the port
  (`docs/remixer/FAILURE_MODES.md`) and went; each engine prints its wet
  on its own host. WDTH moved up to page-2 slot 7.

Defaults are a bit-exact passthrough (DRV 0, FOLD 0, TONE 64, COMP 0, MIX
127, WDTH 64): a part that stored LO-FI runs this. A part's stored
bytes are stock LO-FI's until `ot_project.py stamp-defaults` writes ours.

## Measured

- `tools/verify/verify_character.py`: defaults bit-exact; MIX=0 bit-exact
  with every stage driven; every SAT character unity small-signal at DRV=0
  and bounded at DRV=127; FOLD folds a monotonic ramp; COMP reduces the loud
  signal 6.1 dB more than the quiet one and is exactly unity at 0; WDTH 0 is
  mono and 64 exact; an FX2 instance is a bit-exact dry pass.
- COMP is AC1's console law (`docs/effects/MASTER.md`): attack 0.5 ms,
  release 63 ms (K = 4); GLUE on the master 0.5 / 500 ms (K = 3). The
  threshold/ratio numbers that stood here (thr 0.03, invR 0.1, 8/100 ms)
  were the retired law's.
- Cost: 975 words on each payload (1,138 / 1,195 with the return, 20 Sep
  2026); 623 cycles/sample static worst case. The pricer's worst core is
  four of these beside the reverb: 3,657 against 3,120 usable, inside the
  counter's error margin; the hardware burn sweep settles it.
- `verify_menu`, `verify_replaces` (it took LO-FI's FX1 page) and
  `verify_labels` (the select prints its words on the emulated firmware)
  pass on the rig.

On Sam's unit since flash 4; the return confirmed on flash 7; the master
shape (Character everywhere, RET by position, wet in front) flashed 13 Sep
2026 as image 96; the return removed 20 Sep 2026.
