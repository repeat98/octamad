# `miniverb` — MINI VERB alone

Jannik Aßfalg's (repeat98) reverb development image.

## What is in it

- **MINI VERB** — a full-rate stereo FDN reverb in DARK REV's FX2 slot: four input diffusers, eight allpass diffusers inside the feedback tank, two of them modulated. Knobs DECAY DAMP MIX MOD RATE. Independent per-instance FX2 buffers; eight instances render. `modules/miniverb/README.md`.

## Status

Local render only (`make verify-miniverb`: both cores, isolation, dirty memory, buffer guards, audio gates). Not flashed.

## Build

```bash
make image REMIX=miniverb BUILD=1   # -> out/OCTATRACK_OCTABAM1.bin
```

[BUILDING.md](../../../docs/remixes/BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `make check REMIX=miniverb` runs every gate first.
