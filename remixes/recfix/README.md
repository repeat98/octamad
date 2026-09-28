# `recfix` — The recorder loop click fix

Four ColdFire modules and the stock effects. For anyone whose recorder loops click at the seam.

## What is in it

- **FLEX SEEK BIND** — a same-buffer FLEX re-bind is a SEEK for the DSP, not a new note: removes the voice-restart transient at a recorder loop's seam.
- **FLEX SEEK BIND CTR** — the per-bind counter is held across that re-bind: removes the ±1.5-sample seam.
- **RECORDER SPACING** — a fixed-RLEN recording is exactly as long as the gap to its next arm: removes the skipped sample on alternate bars at tempos whose pass length is not an integer number of samples (128 BPM; 120 and 125 are exact).
- **RECORDER HOLD** — a recorder-buffer voice reading one sample past its recording repeats the last sample instead of reading zero: removes the zero sample that sound-on-sound (SRC3 = the track) plays and re-records on every pass whose window is one sample longer than the previous pass (128 BPM: every other pass at RLEN 16).
- the 14 stock FX2 effects, listed so the chooser is stock's.

## Status

The three caves plus the bus were measured on hardware as OCTABAM83 (12 Sep 2026): zero of 46 bars above 1.25× where the previous image had 16; 128 BPM reads identical to the stock golden capture. This remix without the bus (the first three) was re-measured on hardware as OCTABAM84 with the same result. RECORDER HOLD is port-gated only (`modules/recorder-hold/README.md`). Whether RECORDER SPACING alone suffices is untested. `docs/firmware/RECORDER_CLICK.md` has the reproduction.

## Build

```bash
make image REMIX=recfix BUILD=1     # -> out/OCTATRACK_OCTABAM1.bin
```

[BUILDING.md](../../docs/remixes/BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `make check REMIX=recfix` runs every gate first.
