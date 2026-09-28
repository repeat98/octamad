# BusVerb

An eight-line FDN reverb with ROOM/PLATE/BIG modes, modulated taps, a
shimmer, a gate and mid/side width. Hosted on payload A (core 0), which
serves tracks 5–8 (measured; test it on track 5). Stage 2 of the one aux bus.

Structure, parameters and memory layout: [`docs/effects/REVERB.md`](../../docs/effects/REVERB.md).
Voicing rounds up to 16 Sep 2026: `git show 3ceba41:docs/history/VOICING.md`.

## Measured

- Wet levels at defaults, SEND 100, one sender: ROOM −10.9, PLATE −13.1, BIG −13.0 dBFS (+6 dB since 16 Sep 2026's makeup; before it −16.9 / −19.1 / −19.0). Eight senders at SEND 100 on loud loops, BIG, WET 127: the wet alone peaks −8.9 dBFS, the host's dry + wet −3.8, no clipped samples.
- Wet limiter (27 Sep 2026): a feedback peak limiter on the wet at half
  scale, before the ×2 makeup — `y = wet × g`; while max(|yL|, |yR| of the
  previous sample) is over 0.398 (= −2 dBFS after the ×2) g steps ×0.9 per
  sample; under 0.31 (−4 dBFS after the ×2) it climbs 2^-16 per sample
  (0.9 → 1.0 in ~150 ms; the store's limiter clamps it at 1.0); between
  the two it holds, so a signal sitting at the ceiling is not modulated
  sample by sample (without the hold the knob-click gate read −54 dBFS of
  chatter on a steady 0.3 FS tone; its floor is −70). Three candidates,
  two compares, two `tmi` pick; no `div`/`rep` (neither has a stock site).
  The knob-click gate keeps one residual as KNOWN: a DIFF jump on ROOM
  dumps the diffusers' state as a peak and the limiter turns it into gain
  steps (−51 dBFS, ceiling −45) where the store's clipping, which the
  metric leaves out, used to take it; a gentler ×0.953 attack flagged SHMR
  as well. Drum loop as a send
  from a THRU at AMP VOL 127, REV 127, WET 127, sample-exact per channel:
  at a 0 dBFS send the wet railed 7,463 samples (L) / 11,762 (R) per 9 s
  on PLATE, 469 / 500 on BIG, 3 / 2,874 on ROOM; with the limiter 0 on
  every mode, peaks −1.1 to −1.8 dBFS, PLATE's RMS −11.4 → −16.0 (the
  whole loop is over the ceiling there). At a −6 dBFS send 23 / 46 → 0,
  RMS −15.8 → −16.9. At −12 dBFS bit-identical (max difference −130 dBFS).
  Earlier tries: moving the tank's −12 dB pad to the bus input railed
  MORE at 0 dBFS (the limit is the wet sum, not the diffusers); a `rep
  #24 / div` gain was dropped for lack of a stock site. Slots `$11..$13`
  (inside the one-word displacement range: `(r7+$68)` costs two words),
  +30 cycles/sample static (1,145 → 1,175). Words: the limiter took 32 of
  payload A's 35 free, which left the RIG BURN probe's 21 without a home
  (`verify_burn` refused); four per-block slots the block code reaches
  five times each ($6d, $67, $62, $5e) moved into the one-word
  displacement range ($25, $26, $27, $39), bit-identical, and payload A
  sits at 23 free.
  Unheard on hardware.
- Second slot pass (27 Sep 2026, after the limiter): the sample loop
  reached 35 slots above $3f, two words per access (`(r7+$68)` assembles
  to two words; −64..63 to one). Twenty-two of them trade places with
  per-block slots: thirteen with slots the code addresses by name ($71
  $4e $5c $5d $64 $78 $79 $52 $53 $54 $55 $40 $5f ↔ $09 $0a $10 $26 $28
  $2a $2b $31 $33 $34 $35 $36 $37) and nine MODE-table slots with the LFO
  roll's ($74 $75 $76 $77 $7a $7e $7f $80 $81 ↔ $00..$07 $3e; the
  manifest's `_MODE_SLOTS` and `build_bus.py`'s `LFOTAB` renumbered with
  them; the dormant `LFO01` table follows the map too). fb4..fb7 stay: the
  feedback loops write them through a pointer walk. `rig_render`
  bit-identical on ROOM, PLATE and BIG at −12 and 0 dBFS sends, T1, T5 and
  the mix (max difference −200 dBFS); knob-click gate 0 flagged. Static
  price 1,166 → 1,146 cycles/sample (probe 57: a two-word displaced move
  costs 3.98 cycles on the chip against 2.00, which the pricer cannot
  see), payload A 23 → 34 free words. The header's slot map is read through
  its two swap tables.
- RT60 (a 50 ms burst, −3..−33 dB slope) at TIME 0 / 32 / 64 / 96 / 127:
  ROOM 0.87 / 1.0 / 1.5 / 2.8 / 3.9 s; PLATE 0.9 → 4.4 s; BIG 1.6 → 11.7 s.
  The tank law is `$1e = a − k_mode·(d_min + d_span·(1−t)²)` (k ROOM 0.5 /
  PLATE 0.4 / BIG 0.25; d > 0 always, so the norm-stability proof holds). The
  output-branch bloom pair's g follows TIME (0.40 → 0.86).
- The short-room floor is the input diffusers: at TIME 0, DIFF 0 → 0.50 s,
  40 → 0.64, 80 → 0.87, 127 → 1.49 s. At DIFF 127 the four diffusion
  allpasses at g 0.77 read as a metallic sheen; capping the span at ~0.70
  removes it.
- Cost (pricer `cycle_count.py`, words): 1,135 → 1,117 cycles/sample on
  23 Sep 2026, when the sample loop moved its u vectors, feedback
  scratch, output stage, allpass phase, chain word and aux pointers onto
  pointers and registers: one-word displaced `(r7+$..)` accesses per
  sample 206 → 111 (the loop once, plus fbA/fbB × 4 and apbody × 4; the
  ×8 tank loop had none). Probe 57 (`docs/firmware/CHIP.md` §2) timed a
  displaced move at 3.98 cycles against 2.00 for a pointer or register
  move, which the pricer cannot see. 28 bus-gate cases bit-identical
  (`make verify-bus`, with PLATE, BIG, the shimmer and the gate driven
  since the same day).

## On the unit

Image 26/27 (15 Sep 2026, the WET pedal chain): Sam, "is awesome" -- the
round closed with nothing to change; the reverb's buffers and voicing are
kept whatever the delay-memory work finds ("not willing to sacrifice any
verb").

## Open

- Coupling the diffuser g to TIME (~13 words) waits for payload A words.
- A SIZE turn once killed the reverb (R44) and has not been reproduced. If it
  recurs, the diagnostic is whether tracks 5–8 all died.
