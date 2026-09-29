# `oxide` — the OXIDE tape insert, alone

The remix `tools/verify/verify_oxide.py` renders, and the one to listen to OXIDE with.

## What is in it

- **OXIDE** — a stereo tape insert modelled on UADx Oxide (15 IPS NAB): headroom,
  saturation and head bump. `modules/oxide/README.md`.

Absent ids resolve to the firmware's own NONE. OXIDE is written for the master; until
the master strip exists (`docs/proposals/MIXER.md` §8 step 2) it runs as an FX1 or FX2
insert on any track.

## Status

The DSP code renders equal to `design.fixed()` at 0 LSB under `dsp_host`. Not flashed.
