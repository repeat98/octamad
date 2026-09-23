# `kits` — The Octakit family

Octakit + the LO-FI AMF fix + CC PAGE 2 (bridged). Every stock effect stays.

## What is in it

- **OCTAKIT** (Em, [ems-octakit](https://github.com/emuyia/ems-octakit) ot-26914) — 256 Kits per Project in place of 64 bank-tied Parts. MKII: PART opens LOAD KIT, FUNC+PART opens SAVE KIT; MKI: FUNC+MIDI opens LOAD KIT, FUNC+BANK opens SAVE KIT. FUNC+CUE reloads the assigned Kit; Kits have 7-character names; the LOAD/SAVE KIT menus copy/paste/clear/undo, LOAD KIT > UNDO KIT reloads the last loaded Kit; FUNC+PASTE+PART (MKI: FUNC+PASTE+MIDI) on a pasted Pattern also saves its Kit to the next free slot; PTN+FUNC+RIGHT saves the current Kit, copies it and the Pattern to the next free slots and loads the pair; PTN+FUNC+TRIG copies/pastes/clears/undoes inactive Patterns (BANK+TRIG, then BANK+FUNC+TRIG for other Banks). Costs 3.6 % of the flex pool (18.4 s at 16-bit). Old projects migrate their Parts into the first 64 Kit slots on load. A 154,718-byte runtime in DRAM, carried by octabam's loader.
- **LOFI AMF FIX** (Bryan T, [octa-bt-pt](https://github.com/bryantysinger/octa-bt-pt)) — stock LO-FI's AMF knob jumps the pitch backwards at some settings because its coefficient multiply is `mpysu` (signed × unsigned) where both operands are magnitudes; two DSP words become `mpyuu`.
- **CC PAGE 2** (Sam Banks) — MIDI CC 62–67 reach the FX2 effect's page-2 knobs (slots 6–11) and CC 68–73 the FX1 effect's; stock reaches only page 1 over MIDI. One ColdFire cave. Confirmed on hardware 13 Sep 2026.
- **SCENES KITS** (Sam Banks) — the bridge that lets CC PAGE 2 and Octakit share the MIDI CC dispatch entry: CCs 62–67 CC PAGE 2's, then Octakit's, then stock's. Nothing of its own to use.

## Status

Builds and passes every gate. Not flashed; Octakit has run on hardware in `ok-ms`.

## Build

```bash
make image REMIX=kits BUILD=1     # -> out/OCTATRACK_OCTABAM1.bin
```

[BUILDING.md](BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `make check REMIX=kits` runs every gate first.

## Before you flash

- **Octakit migrates Parts into Kits on project load.** Back up projects first; going back to stock can lose Kit data.
