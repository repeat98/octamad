# CHARACTER

The station that dirties or tightens a track, on stock LO-FI's id 0x1c. FX1 only: an FX2 instance runs as a dry pass
(`Claims(fx1_only=True)`, `verify_character.py`); the FX2 chooser hides the
row.

| page 1 | DRV · FOLD · WDTH · COMP · TONE · MIX |
|---|---|
| page 2 | SAT (TAPE TUBE INFL) · — · — · — · — · — |

Chain, fixed: fold → saturate → tilt → compress → width → mix.

- **FOLD** — WarpFold's wavefolder, 1 → 48× into the fold at a held level;
  first fold on a pad at ~24.
- **SAT / DRV** — three JClones (MIT) characters, re-derived here. TAPE =
  TapeHead: a state-variable split at TONE, the low and band parts through
  a cubic smoothstep, the top clean; drive 0.8× → 8× from a 17-word P table.
  TUBE = DaTube: u − u^P with the negative half driven twice as hard,
  level-compensated (a per-block division); the curve is a 17-pair P table.
  INFL = OInflator: a signed cubic, DRV is its Effect. DRV 0 skips the
  stage, bit-exact. Since 23 Sep 2026 (Sam: "much too subtle") DRV also
  drives the curve's input by G = 1 + 3·DRV/128 (+12 dB at 127), on top of
  each mode's own law, with the output scaled per mode: TAPE ×1 (TapeHead's
  trim already holds its small signal at unity and its smoothstep
  compresses the rest; with 1/G on top a loop sat 18 dB under dry at DRV
  127), TUBE ×(1+d)/G, INFL ×1/G. THD on a 1 kHz tone at −20 dBFS (the
  set's working level), before → after: TAPE DRV 64 −40 → −23 dB, DRV 127
  −18 → −11 dB; TUBE 127 −22 → −18 dB; INFL 127 −58 → −37 dB. Level on that
  tone at DRV 64 / 127: TAPE +7.3 / +1.1 dB, TUBE +2.1 / +1.4, INFL +1.8 /
  +3.1; on the test loop's peaks TAPE +1.7 / −6.7, TUBE +0.5 / −4.2, INFL
  +1.2 / −0.1. Small-signal gain at DRV 127: +12 / +6 / 0 dB by mode
  (`verify_character`).
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
  on its own host. WDTH is page-1 slot 2 (TXTR's until 22 Sep 2026).

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
- Cost: 888 words on each payload (903 after the DRV drive, 790 before it;
  671 before the pointer rewrite; 975 with TXTR; 1,138 / 1,195 with the
  return, 20 Sep 2026); pricer per mode (`cycle_count.py --modes`, words):
  TAPE 325, TUBE 321, INFL 245 (354 / 339 / 268 after the DRV drive, 23
  Sep 2026).
- 23 Sep 2026: the loop's state pointers go through n3 alone (TapeHead's
  states at `$3e..$41`, TUBE's DC blockers at `$42..$45`, the tilt block at
  r4 + n3); COMP reads its key from the frame instead of a per-sample
  store; the tilt's k, TapeHead's 0.7 and TUBE's R load once per sample or
  ride in the ring; twelve parallel moves (forms with stock precedent);
  OInflator inlined per channel. Bit-identical on `make verify-ident
  MOD=character` (9 settings) and a T8 (GLUE) rig render.
- 22 Sep 2026: the sample loop reads its coefficients through two 16-word
  post-increment rings and its state through pointers; displaced `(r7+$..)`
  moves per sample path went TAPE 79 / TUBE 74 / INFL 62 -> 0. Probe 57
  (`docs/firmware/CHIP.md` §2) timed a one-word displaced move at 3.98 cycles
  against 2.00 for a pointer or register move in a one-instruction DO loop,
  so the words the pricer counts understate the chip's cost of the old form.
  Nine renders (three modes x two knob sets, DRV 0 with FOLD, T8 GLUE, T8
  TUBE) are bit-identical to the pre-rewrite build.
- `verify_menu`, `verify_replaces` (it took LO-FI's FX1 page) and
  `verify_labels` (the select prints its words on the emulated firmware)
  pass on the rig.

On Sam's unit since flash 4; the return confirmed on flash 7; the master
shape (Character everywhere, RET by position, wet in front) flashed 13 Sep
2026 as image 96; the return removed 20 Sep 2026.
