# `mods` — MIDI SCENES, Octakit and the fixes, bridged

MIDI SCENES + Octakit + the LO-FI AMF fix + CC PAGE 2 on the stock effects, bridged.

## What is in it

- **MIDI SCENES** (bkkbrls-del, [midisc](https://github.com/bkkbrls-del/midisc) 1.40MIDISC8) — per-scene parameter locks driven over MIDI: a second lock table the panel never had; scene hold, XF morph, part save/reload and the scene clear/copy/paste rows read it when a MIDI event is driving. The panel path is untouched. Thirteen units in DRAM, 38 detours, 4 pokes inside the OS.
- **OCTAKIT** (Em, [ems-octakit](https://github.com/emuyia/ems-octakit) ot-26914) — 256 Kits per Project in place of 64 bank-tied Parts. MKII: PART opens LOAD KIT, FUNC+PART opens SAVE KIT; MKI: FUNC+MIDI opens LOAD KIT, FUNC+BANK opens SAVE KIT. FUNC+CUE reloads the assigned Kit; Kits have 7-character names; the LOAD/SAVE KIT menus copy/paste/clear/undo, LOAD KIT > UNDO KIT reloads the last loaded Kit; FUNC+PASTE+PART (MKI: FUNC+PASTE+MIDI) on a pasted Pattern also saves its Kit to the next free slot; PTN+FUNC+RIGHT saves the current Kit, copies it and the Pattern to the next free slots and loads the pair; PTN+FUNC+TRIG copies/pastes/clears/undoes inactive Patterns (BANK+TRIG, then BANK+FUNC+TRIG for other Banks). Costs 3.6 % of the flex pool (18.4 s at 16-bit). Old projects migrate their Parts into the first 64 Kit slots on load. A 154,718-byte runtime in DRAM, carried by octabam's loader.
- **LOFI AMF FIX** (Bryan T, [octa-bt-pt](https://github.com/bryantysinger/octa-bt-pt)) — stock LO-FI's AMF knob jumps the pitch backwards at some settings because its coefficient multiply is `mpysu` (signed × unsigned) where both operands are magnitudes; two DSP words become `mpyuu`.
- **CC PAGE 2** (Sam Banks) — MIDI CC 62–67 reach the FX2 effect's page-2 knobs (slots 6–11) and CC 68–73 the FX1 effect's; stock reaches only page 1 over MIDI. One ColdFire cave. Confirmed on hardware 13 Sep 2026.
- **SCENES KITS** (Sam Banks) — the bridge that lets CC PAGE 2 and Octakit share the MIDI CC dispatch entry: CCs 62–67 CC PAGE 2's, then Octakit's, then stock's. Nothing of its own to use.
- **KITS RELOAD** (Sam Banks) — the bridge that lets MIDI SCENES' Part Reload run beside Octakit's kit reload: Octakit's reload validates its caller's return address, midisc's stub substituted it (OKMS1 trapped on the first Part Reload); the stock call stays and midisc's post-reload restore runs from the return sites.
- the 14 stock FX2 effects, listed so the chooser is stock's.

## Status

Boots under the ColdFire port; every `apply_part` in a project load runs the chain. Not flashed as a whole; `ok-ms` (its subset) has run on hardware. Unmeasured: MIDI CCs through the chained dispatch, and his Part save/reload menu hooks against her LOAD/SAVE KIT menus.

## Build

```bash
make image REMIX=mods BUILD=1     # -> out/OCTATRACK_OCTABAM1.bin
```

[BUILDING.md](BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `make check REMIX=mods` runs every gate first.

## Before you flash

- **Octakit migrates Parts into Kits on project load.** Back up projects first; going back to stock can lose Kit data.
