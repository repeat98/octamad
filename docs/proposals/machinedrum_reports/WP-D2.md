# WP-D2 The sequencer data model: report

- **Status:** review (the user signs off the spec; WP-D3 builds on it now,
  following the rule "decide by architecture, efficiency and OT parity")
- **Branch and commit:** `machinedrum` @ this commit
- **Date:** 24 September 2026
- **Agent:** Claude (Opus 5.5)

## What was done

The spec below fixes the MD pattern model for option B (the embedded 16-part
sequencer). Each choice follows one rule: **the MD lanes behave like
the parent OT track's own steps**. They use the same clock, length, scale,
swing and pattern changes. So nothing is decided twice, and the MD
track stays in step with the rest of the OT pattern. `md_ctl.h` carries it as
C types; WP-D3 implements it.

## The spec

**Ownership.**
- One MD pattern per OT pattern: 16 banks × 16 patterns = 256.
- One MD kit per OT Part: 16 banks × 4 Parts = 64.

The MD track of the active Part plays the MD pattern of the playing OT
pattern with the kit of that pattern's Part. A Part without an MD track has a
kit too, but it is not sounded.

**Pattern.**

```c
typedef struct { uint8_t step, part, param, value; } MdLock;   /* 4 bytes */
typedef struct {
    uint32_t trig[16][2];     /* lane p, step s: bit s of the 64-bit mask */
    MdLock lock[64];          /* part 0xff = free */
} MdPattern;                  /* 384 bytes; 256 of them = 96 KB */
```

- **Lanes.** 16 lanes, one per internal part, of up to 64 steps.
- **Length.** A lane's length is the parent track's length: the pattern
  length, or the track's own in per-track scale mode. So all 16 lanes wrap
  together at the parent track's end, as the OT track's own trigs do.
- **Scale.** The parent track's scale (1/8×, 1/4×, 1/2×, 3/4×, 1×, 3/2×,
  2×): one step is the parent track's step.
- **Swing.** The parent track's swing amount and swing-trig mask, applied
  per step exactly as the OT applies it to that track (Euclid's
  `swing_at`, stock `0x4009d3e0`). The MD's own swing is not stored.
- **Conditions, micro-timing, trig probability, retrigs.** Not in the
  first version. They are OT per-trig features; an MD lane step is a bare
  hit plus its locks.
- **Accent, slide.** Not stored. The MD's accent scales the mixer level,
  and that mixer is not loaded (D1: the OT-side VOL/PAN mix). It is a later
  extension field.
- **Parameter locks.** A lock is (step, part, parameter, value). The
  parameter is 0–7 for SYN 1–8, 8 for VOL and 9 for PAN. There are 64 per
  pattern, as on the MD. A lock applies to that part's trig on that step
  and holds until the part's next trig, the MD's behaviour. There are no
  trigless locks.
- **Transport.** PLAY starts every lane at step 1, on the same PLAY anchor
  that stock uses for the OT tracks. STOP stops triggering; sounding voices
  decay by their own envelopes, as on the MD. The pattern plays whenever
  the OT transport runs, and has no MD-only transport.
- **Pattern changes.** Pattern changes are the OT's own. When the playing
  OT pattern changes, the MD reads the new pattern's lanes from the next
  step on, with the step position still anchored to the common clock. The
  OT has already quantised the change to its boundary, so the MD adds no
  quantisation of its own.
- **Mute.** Muting the parent track mutes the instance, because the OT
  mutes its audio. Each part has its own mute (`MdPart.flags`, the
  gain-pair path).
- **MIDI.** A MIDI note to a part triggers it on top of the running
  pattern (WP-E2), through the same trig request as the sequencer.

**Kit.**

`MdKit` (`md_ctl.h`) holds 16 × {engine, VOL, PAN, flags, SYN 1–8}, 192
bytes. An engine change loads the engine's descriptor defaults, as the MD
does (measured: the 49 non-TRX-S2 base cases in `c2_maps` equal the
descriptor defaults).

**Persistence (WP-E1).** The persistent form is versioned:
- a magic word;
- a version;
- the 64 kits;
- the 256 patterns.

Stock padding is not reused.

## Retracted

Nothing.

## Open and handover

- The user signs off the choices above. The ones most likely to change are
  the parent-track length and scale for all lanes (the MD itself has one
  pattern length, so this is the same shape) and dropping accent from
  the first version.
- WP-D3 implements the clock and the lanes in `md_ctl.c`.
