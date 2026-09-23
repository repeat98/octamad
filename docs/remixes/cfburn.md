# `cfburn` — stock plus the ColdFire burn knob

Stock 1.40C with one addition: **CF BURN**, an FX2 row whose knobs make the
ColdFire spin a set number of instructions at IPL 5, at the end of the
stock delay routine. Swept on the unit, it measures the base firmware's
spare CPU in whatever project is loaded. It is the ColdFire twin of the
DSP rig burn. The procedure is in [the module's README](../../modules/cfburn/README.md).

## What is in it

- **CF BURN**: BURN (640 instructions per step) and FINE (10 per step).
  Every track that carries it adds its own.
- Every stock effect except DARK REV, whose DSP words hold CF BURN's
  passthrough. A project under test must not use DARK REV.

For the rig and its stress project, use [`bamsep26-burn`](bamsep26-burn.md).

## Status

- **Under the port:** builds, boots, and is inert and exact against stock
  over the complete delay routine (`verify_cfburn`).
- **On hardware:** not flashed and not swept. No ColdFire margin has been
  measured yet.

## Build

```bash
make check REMIX=cfburn
make image REMIX=cfburn BUILD=1     # -> out/OCTATRACK_OCTABAM1.bin
```
