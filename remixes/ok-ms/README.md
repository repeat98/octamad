# `ok-ms` — Octakit + MIDI SCENES

The two ColdFire mods together on the stock effects, with the bridge that
lets them share the Part reload. The first octabam image to run on
hardware (OKMS1, 14 Sep 2026).

## What is in it

| module | what you get |
|---|---|
| [OCTAKIT](../../modules/octakit/README.md) (Em, [ems-octakit](https://github.com/emuyia/ems-octakit)) | 256 named Kits per project in place of 64 bank-tied Parts; any Kit on any pattern; old projects migrate on load. Her README is the manual: MKII PART / FUNC + PART open LOAD / SAVE KIT, FUNC + CUE reloads. |
| [MIDI SCENES](../../modules/midi-scenes/README.md) (bkkbrls-del, [midisc](https://github.com/bkkbrls-del/midisc)) | scene locks driven over MIDI: a second lock table the panel never had; hold, morph, save, reload, clear, copy, paste when a MIDI event is driving. The panel path is untouched. |
| [KITS RELOAD](../../modules/kits-reload/README.md) | the bridge: Octakit's reload checks its caller's return address and midisc's stub substituted it (OKMS1 trapped on the first Part Reload); the stock call stays and midisc's restore runs from the return sites. |

The fourteen stock FX2 effects are listed, so the chooser is stock's.

## Where it has run

On midisc's author's unit, 14 Sep 2026 (OKMS1, then OKMS2 with the
bridge). Every build reproduces Em's runtime byte for byte and midisc's
units against his own encoder (`verify_octakit`, `verify_midiscenes`).

## How to flash

```bash
make image REMIX=ok-ms BUILD=1      # -> out/OCTATRACK_OCTABAM1.bin (card) + out/OCTATRACK_OS1.40C_OCTABAM1.syx (MIDI)
```

[BUILDING.md](../../docs/remixes/BUILDING.md) has each step from a fresh
machine to a flashed unit (macOS, or Linux/WSL2 in its §1a) and the
recovery path; `make emu-cf` then `make check REMIX=ok-ms` runs every gate
first. **Octakit migrates Parts into Kits on project load:** back up the
card first; going back to stock can lose Kit data.
