# `ok-ms` — Octakit + MIDI SCENES

Octakit, MIDI SCENES, the KITS RELOAD bridge, the stock effects.

## What is in it

- **MIDI SCENES** (bkkbrls-del, [midisc](https://github.com/bkkbrls-del/midisc) 1.40MIDISC8) — per-scene parameter locks driven over MIDI: a second lock table the panel never had; scene hold, XF morph, part save/reload and the scene clear/copy/paste rows read it when a MIDI event is driving. The panel path is untouched. Thirteen units in DRAM, 38 detours, 4 pokes inside the OS.
- **OCTAKIT** (Em, [ems-octakit](https://github.com/emuyia/ems-octakit) ot-26914) — 256 Kits per Project in place of 64 bank-tied Parts. MKII: PART opens LOAD KIT, FUNC+PART opens SAVE KIT; MKI: FUNC+MIDI opens LOAD KIT, FUNC+BANK opens SAVE KIT. FUNC+CUE reloads the assigned Kit; Kits have 7-character names; the LOAD/SAVE KIT menus copy/paste/clear/undo, LOAD KIT > UNDO KIT reloads the last loaded Kit; FUNC+PASTE+PART (MKI: FUNC+PASTE+MIDI) on a pasted Pattern also saves its Kit to the next free slot; PTN+FUNC+RIGHT saves the current Kit, copies it and the Pattern to the next free slots and loads the pair; PTN+FUNC+TRIG copies/pastes/clears/undoes inactive Patterns (BANK+TRIG, then BANK+FUNC+TRIG for other Banks). Costs 3.6 % of the flex pool (18.4 s at 16-bit). Old projects migrate their Parts into the first 64 Kit slots on load. A 154,718-byte runtime in DRAM, carried by octabam's loader.
- **KITS RELOAD** (Sam Banks) — the bridge that lets MIDI SCENES' Part Reload run beside Octakit's kit reload: Octakit's reload validates its caller's return address, midisc's stub substituted it (OKMS1 trapped on the first Part Reload); the stock call stays and midisc's post-reload restore runs from the return sites.
- the 14 stock FX2 effects, listed so the chooser is stock's.

## Status

Tested on hardware (14 Sep 2026).

## Build

macOS with [Homebrew](https://brew.sh) (Linux/WSL2: [docs/WSL.md](../WSL.md)); `git`, `python3` (3.10+), `cmake`.

```bash
git clone --recurse-submodules https://github.com/sambanks/octabam
cd octabam
make setup                          # toolchain: vendored tools cloned at their pins, patched, built
make os                             # downloads OS 1.40C from Elektron into downloads/ (sha256 370c55a3…)
make recon                          # unpacks it -> out/raw/section_3_MAIN_OS.bin
make image REMIX=ok-ms BUILD=1      # -> out/OCTATRACK_OCTABAM1.bin (card) + out/OCTATRACK_OS1.40C_OCTABAM1.syx (MIDI)
```

`BUILD` is a one- or two-digit number of your choosing; it becomes the OS version string (`OCTABAM1`). Optional gates: `make emu-cf` then `make check REMIX=ok-ms` (builds the local ColdFire emulator and boots the image in it).

Flash: on the unit PROJECT → SYSTEM → USB DISK MODE → YES; copy `out/OCTATRACK_OCTABAM1.bin` to the root of the card; eject; PROJECT → SYSTEM → OS UPGRADE → YES; after the restart, power-cycle once more. SYSTEM STATUS → OS VERSION reads `OCTABAM1`.

Back to stock: power on holding FUNC → STARTUP MENU → TRIG 3 (MIDI UPGRADE) → send `downloads/extracted/OCTATRACK_OS1.40C.syx` over DIN MIDI.

[BUILDING.md](BUILDING.md) has each step in full.

## Before you flash

- **Octakit migrates Parts into Kits on project load.** Back up projects first; going back to stock can lose Kit data.
