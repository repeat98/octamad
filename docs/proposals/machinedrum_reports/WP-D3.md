# WP-D3 The sequencer engine: report

- **Status:** done (under the port; unflashed)
- **Branch and commit:** `machinedrum` @ this commit
- **Date:** 24 September 2026
- **Agent:** Claude (Opus 5.5)

## What was done

`md_ctl.c` plays WP-D2's pattern model. Each frame it does four things:
1. It finds the MD track. The frame builder's MD hook (`md_machine.s`
   `md_pack_fx2`) stores 1 + the track in `md_parent_track`.
2. On the first frame with an MD track, it loads the default kit: eight TRX
   voices and eight empty parts.
3. It updates Euclid's clock, the frame clock `0x46104cf0`, which the
   PLAY hooks anchor to the step clock `0x4610757c`. The hooks are two new
   detours on the stock PLAY paths, `md_start_hook` and `md_resume_hook`.
4. It plays the lanes of `md_patterns[bank·16 + pattern]` on the parent
   track's step grid: its length, its scale (or the pattern's in the
   normal scale mode), and its swing amount and mask.

A step's trigs go to the producer one frame ahead. That lets the record
reach core 1 on time. A step's locks become an overlay on the part's SYN
and VOL/PAN until its next trig. An engine-dependent default kit and the
parent detection mean the machine plays without any test poke: assigning
MACHINEDRUM to T1 is enough.

## Acceptance check

```
$ MD_EMU=$PWD/out/machinedrum/isolated/emu/ot_emu OT_PROJECT=out/machinedrum/testset/OCTABAM/RIG make verify-md-seq
bank01 part1,5 T1 machine type -> 6
bank01 part2,6 T1 machine type -> 6
bank01 part3,7 T1 machine type -> 6
bank01 part4,8 T1 machine type -> 6
bank01 pattern0 LEN 16 SCALE 1X (index 2)
TEMPOx24=7200 (300 BPM)
  [ok] kit: the default kit's engines trigger on lanes 1-3  lane 1: [17] lane 2: [18] lane 3: [23]
  [ok] steps: every lane trigs on its programmed steps, across the wrap  lane 1: 8 trigs, max error 0.5 frames; lane 2: 5 trigs, max error 0.6 frames; lane 3: 2 trigs, max error 0.3 frames
  [ok] lock: lane 3's locked step differs from its unlocked one  differing words [2, 11, 12, 13, 14, 15]
  [ok] vol lock: part 2 is silent after its locked trig, restored after the next  after step 6 0x0/0x0, after step 10 0x13b7e5/0x13f6ad (want 0x13b7e5/0x13f6ad)
  [ok] audio: T1's read-back carries the MD mix while the lanes play  2380 of 2400 blocks non-silent, peak 4250
  verify_md_seq: PASS
```

## Measured

- ✅ The lanes land on the parent track's step grid within 0.6 frames.
- ✅ SYN and VOL locks hold for one trig.
- ✅ The MD mix reaches T1's output.

These are in section 12, "WP-D3 the embedded sequencer".

## Retracted

Nothing.

## Open and handover

- The pattern's first step is due at PLAY. From boot it falls in the
  producer's 16-frame hold. On the unit PLAY comes long after boot.
- Not in the fixture: swing, per-track scale mode, and timing against
  another OT track's own trigs. The anchor is stock's (Euclid's), not
  measured against a sample track.
- The PLAY detours are Euclid's sites, so MACHINEDRUM and EUCLID cannot
  share a remix.
- The lanes are edited only by poking memory so far. WP-D4 (the grid view)
  and WP-D5 (the pages) are the editor. WP-E1 is persistence.
