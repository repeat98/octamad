# `rig-mods` — The rig + every mod

`bamsep26` with MIDI SCENES and Octakit (bridged). No LO-FI fix.

## What is in it

- **BusVerb** — an eight-line FDN reverb (ROOM / PLATE / BIG, shimmer, gate, mid/side width) that serves all eight tracks over a cross-core bus. Hosted on one of tracks 5–8.
- **BusDelay** — a multi-mode delay (CLEAN / pitched GRAIN cloud / REVERSE, tape wow, freeze) serving all eight tracks. Hosted on one of tracks 1–4. TIME reads as a tempo division (TEMPO SYNC).
- **Send** — the FX2 effect every other track runs: one SEND knob into the bus. The fallback for any unassigned track.
- **DELAY** (stock) — the stock Echo Freeze delay row, unchanged; it runs on the ColdFire and costs the DSP nothing.
- **Spectrum** (FX1, on FILTER's id) — a filter pedal: SEM LP/BP/HP, Airwindows Capacitor2, formants, the Moog ladder; ENV and LFO onto the cutoff; width. Knobs FREQ RES ENV LDP LSP WDTH / TAME MODE.
- **Character** (FX1, on LO-FI's id) — crush, fold/ring, saturation, compressor, width; GLUE compression on track 8 by position (the bus return left it 20 Sep 2026). Knobs DRV FOLD TXTR COMP TONE MIX / SAT WDTH.
- **Modulation** (FX1, on CHORUS's id) — chorus / flanger / comb. Knobs RATE DPTH FDBK MIX / DLY MODE TONE SHPE WID.
- **TEMPO SYNC** (Sam Banks) — two ColdFire caves: the tempo, crossfader and note reach the DSP, and BusDelay's TIME draws as a division (1/8, 1/4 …) instead of milliseconds. On the unit since 24 Aug 2026.
- **CC PAGE 2** (Sam Banks) — MIDI CC 62–67 reach the FX2 effect's page-2 knobs (slots 6–11) and CC 68–73 the FX1 effect's; stock reaches only page 1 over MIDI. One ColdFire cave. Confirmed on hardware 13 Sep 2026.
- **MIDI SCENES** (bkkbrls-del, [midisc](https://github.com/bkkbrls-del/midisc) 1.40MIDISC8) — per-scene parameter locks driven over MIDI: a second lock table the panel never had; scene hold, XF morph, part save/reload and the scene clear/copy/paste rows read it when a MIDI event is driving. The panel path is untouched. Thirteen units in DRAM, 38 detours, 4 pokes inside the OS.
- **OCTAKIT** (Em, [ems-octakit](https://github.com/emuyia/ems-octakit) ot-26914) — 256 Kits per Project in place of 64 bank-tied Parts. MKII: PART opens LOAD KIT, FUNC+PART opens SAVE KIT; MKI: FUNC+MIDI opens LOAD KIT, FUNC+BANK opens SAVE KIT. FUNC+CUE reloads the assigned Kit; Kits have 7-character names; the LOAD/SAVE KIT menus copy/paste/clear/undo; PTN+FUNC+RIGHT duplicates a Pattern and its Kit. Costs 3.6 % of the flex pool (18.4 s at 16-bit). Old projects migrate their Parts into the first 64 Kit slots on load. A 154,718-byte runtime in DRAM, carried by octabam's loader.
- **SCENES KITS** (Sam Banks) — the bridge that lets CC PAGE 2 and Octakit share the MIDI CC dispatch entry: CCs 62–67 CC PAGE 2's, then Octakit's, then stock's. Nothing of its own to use.
- **KITS RELOAD** (Sam Banks) — the bridge that lets MIDI SCENES' Part Reload run beside Octakit's kit reload: Octakit's reload validates its caller's return address, midisc's stub substituted it (OKMS1 trapped on the first Part Reload); the stock call stays and midisc's post-reload restore runs from the return sites.

FX2 chooser: BusVerb, BusDelay, Send, DELAY. FX1 chooser: NONE, Spectrum, Character, Modulation. The stations are FX1-only and default to a bit-exact passthrough, so a saved part that chose FILTER, LO-FI or CHORUS still plays.

## Status

Builds and passes every gate. Not flashed. The `rig-kits` caveat applies.

## Build

```bash
make image REMIX=rig-mods BUILD=1     # -> out/OCTATRACK_OCTABAM1.bin
```

[BUILDING.md](BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `make check REMIX=rig-mods` runs every gate first.

## Before you flash

- **Octakit migrates Parts into Kits on project load.** Back up projects first; going back to stock can lose Kit data.
- After flashing, stamp every project you will play before pressing play: `python3 tools/hw/ot_project.py stamp-defaults <project> rig-mods`. A part saved under another layout feeds the stations its old bytes and the sequencer stalls.
- Judge BusVerb on track 5 (payload A serves tracks 5–8), BusDelay on track 1.
