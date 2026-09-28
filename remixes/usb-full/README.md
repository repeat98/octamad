# `usb-full` — USB AUDIO FULL on the stock effects

The stock chooser plus USB MIDI and USB AUDIO FULL, for testing the sixteen-channel stream on a unit that runs stock projects: no rig stations, no chooser changes, no project stamping.

## What is in it

- **USB MIDI** and **USB AUDIO FULL** (markandrus/octemu): USB-MIDI mirroring DIN; sixteen 24-bit channels, track N's L/R on 2N−1/2N, post-FX, pre-fader; the tracks' stereo sum at full speed. [`modules/usb-audio-full`](../../modules/usb-audio-full/README.md).
- the 14 stock FX2 effects.

## Status

Port only (`verify_usb`, 27 Sep 2026). Image 69 (Sam's MKII, 25 Sep 2026) ran sixteen channels at 24 bits from the source as it was before MAIN/CUE; this build is the current source with MAIN/CUE left out, and has not run on a unit.

## Build

```bash
make image REMIX=usb-full BUILD=1   # -> out/OCTATRACK_OCTABAM1.bin
```

[BUILDING.md](../../docs/remixes/BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `make check REMIX=usb-full` runs every gate first.
