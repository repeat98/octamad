# `bus` — The plain bus

BusVerb + BusDelay + Send + tempo sync. The build's bit-identity subject.

## What is in it

- **BusVerb** — an eight-line FDN reverb (ROOM / PLATE / BIG, shimmer, gate, mid/side width) that serves all eight tracks over a cross-core bus. Hosted on one of tracks 5–8.
- **BusDelay** — a multi-mode delay (CLEAN / pitched GRAIN cloud / REVERSE, tape wow, freeze) serving all eight tracks. Hosted on one of tracks 1–4. TIME reads as a tempo division (TEMPO SYNC).
- **Send** — the FX2 effect every other track runs: one SEND knob into the bus. The fallback for any unassigned track.
- **TEMPO SYNC** (Sam Banks) — two ColdFire caves: the tempo, crossfader and note reach the DSP, and BusDelay's TIME draws as a division (1/8, 1/4 …) instead of milliseconds. On the unit since 24 Aug 2026.

## Status

The shape that has been on Sam's unit since August 2026 (under earlier names). `scripts/refhash.sh` rebuilds it in 26 configurations to prove a build change changed nothing.

## Build

```bash
make image REMIX=bus BUILD=1     # -> out/OCTATRACK_OCTABAM1.bin
```

[BUILDING.md](BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `make check REMIX=bus` runs every gate first.

## Before you flash

- After flashing, stamp every project you will play before pressing play: `python3 tools/hw/ot_project.py stamp-defaults <project> bus`. A part saved under another layout feeds the stations its old bytes and the sequencer stalls.
- Judge BusVerb on track 5 (payload A serves tracks 5–8), BusDelay on track 1.
