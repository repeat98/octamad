# BusVerb

An eight-line FDN reverb with ROOM/PLATE/BIG modes, modulated taps, a
shimmer, a gate and mid/side width. Hosted on payload A (core 0), which
serves tracks 5–8 (measured; test it on track 5). Stage 2 of the one aux bus.

Structure, parameters and memory layout: [`docs/effects/REVERB.md`](../../docs/effects/REVERB.md).
Voicing rounds up to 16 Sep 2026: `git show 3ceba41:docs/history/VOICING.md`.

## Measured

- Wet levels at defaults, SEND 100, one sender: ROOM −10.9, PLATE −13.1, BIG −13.0 dBFS (+6 dB since 16 Sep 2026's makeup; before it −16.9 / −19.1 / −19.0). Eight senders at SEND 100 on loud loops, BIG, WET 127: the wet alone peaks −8.9 dBFS, the host's dry + wet −3.8, no clipped samples.
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
