# `repitch` — REPITCH in the TSTR selector

One ColdFire module and the stock effects. For anyone who wants a track to follow the project tempo by playback speed, like a turntable, instead of by grains.

## What is in it

- **REPITCH** — a fifth TSTR value (`RPCH`, after OFF/AUTO/NORM/BEAT on STATIC and FLEX; `REPITCH` in the audio editor's ATTR TIMESTRETCH, applied when the track's TSTR is AUTO): `speed = project BPM / sample BPM`, live, clamped to 2×. PTCH is off on that track; RATE still applies. Existing values keep their raw numbers, so saved projects load unchanged; a project saved with REPITCH stores 4, which a stock OS does not know. `modules/repitch/README.md`.
- the 14 stock FX2 effects, listed so the chooser is stock's.

## Status

Working on an MKII (OCTABAM81, 16 Sep 2026, the author's unit); measured under the ColdFire port and the Python emulator (`docs/firmware/REPITCH.md`, `python3 tools/verify/verify_repitch.py`). Not yet run on an MKI. Slices and the recorder buffers are not measured.

## Build

```bash
make image REMIX=repitch BUILD=1    # -> out/OCTATRACK_OCTABAM1.bin
```

[BUILDING.md](BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `make check REMIX=repitch` runs every gate first.
