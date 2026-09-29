# `usb-out-tracks-main-cue` — USB on the stock effects

The stock chooser plus USB MIDI and USB AUDIO, for testing the USB stream on a unit that runs stock projects: no rig stations, no chooser changes, no project stamping. Bryan T's test remix, 25 Sep 2026.

## What is in it

- **USB MIDI** and **USB AUDIO** (markandrus/octemu): USB-MIDI mirroring DIN; twenty 24-bit channels (tracks 1–16, MAIN 17–18, CUE 19–20). [usb.md](../usb/README.md) has the host-side setup.
- the 14 stock FX2 effects.

## Status

Port only. The same USB modules are on hardware in `usb-audio` (Sam's MKII, image 64) and `octatrick-usb` (Tim's MKI, OCTATRICK9).

## Build

```bash
make image REMIX=usb-out-tracks-main-cue BUILD=1   # -> out/OCTATRACK_OCTABAM1.bin
```

[BUILDING.md](../../../docs/remixes/BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `make check REMIX=usb-out-tracks-main-cue` runs every gate first.
