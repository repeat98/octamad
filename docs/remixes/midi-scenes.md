# `midi-scenes` — MIDI SCENES alone

One module. The smallest image with a real mod on the DRAM platform.

## What is in it

- **MIDI SCENES** (bkkbrls-del, [midisc](https://github.com/bkkbrls-del/midisc) 1.40MIDISC8.2) — per-scene parameter locks driven over MIDI: a second lock table the panel never had; scene hold, XF morph, part save/reload and the scene clear/copy/paste rows read it when a MIDI event is driving. The panel path is untouched. Twelve units in DRAM, 38 detours, 4 pokes inside the OS.

## Status

Every region assembles to his encoder's bytes at his addresses; boots under the port with his hooks running from DRAM. Not flashed alone; on hardware in `ok-ms`.

## Build

```bash
make image REMIX=midi-scenes BUILD=1     # -> out/OCTATRACK_OCTABAM1.bin
```

[BUILDING.md](BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `make check REMIX=midi-scenes` runs every gate first.
