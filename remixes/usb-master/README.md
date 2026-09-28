# `usb-master` — USB AUDIO MASTER on the stock effects

The stock chooser plus USB MIDI and USB AUDIO MASTER, for testing the two-channel stream on a unit that runs stock projects: no rig stations, no chooser changes, no project stamping.

## What is in it

- **USB MIDI** and **USB AUDIO MASTER**: USB-MIDI mirroring DIN; track 8's L/R, post-FX, pre-fader, on channels 1/2 at both USB speeds. [`modules/usb-audio-master`](../../modules/usb-audio-master/README.md).
- the 14 stock FX2 effects.

## Status

Port only (`verify_usb`, 27 Sep 2026). Not on a unit.

## Build

```bash
make image REMIX=usb-master BUILD=1   # -> out/OCTATRACK_OCTABAM1.bin
```

[BUILDING.md](../../docs/remixes/BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `make check REMIX=usb-master` runs every gate first.
