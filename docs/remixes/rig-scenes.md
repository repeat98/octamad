# `rig-scenes` — The rig + MIDI SCENES

`bamsep26` with MIDI scene locks. No LO-FI fix (Character replaces LO-FI).

## What is in it

- **BusVerb** — an eight-line FDN reverb (ROOM / PLATE / BIG, shimmer, gate, mid/side width) that serves all eight tracks over a cross-core bus. Hosted on one of tracks 5–8.
- **BusDelay** — a multi-mode delay (CLEAN / pitched GRAIN cloud / REVERSE, tape wow, freeze) serving all eight tracks. Hosted on one of tracks 1–4. TIME reads as a tempo division (TEMPO SYNC).
- **Send** — the FX2 effect every other track runs: one SEND knob into the bus. The fallback for any unassigned track.
- **DELAY** (stock) — the stock Echo Freeze delay row, unchanged; it runs on the ColdFire and costs the DSP nothing.
- **Spectrum** (FX1, on FILTER's id) — a filter pedal: SEM LP/BP/HP, Airwindows Capacitor2, formants, the Moog ladder; ENV and LFO onto the cutoff; width. Knobs FREQ RES ENV LDP LSP WDTH / TAME MODE.
- **Character** (FX1, on LO-FI's id) — fold, saturation, tilt, compressor, width; GLUE compression on track 8 by position (the bus return left it 20 Sep 2026). Knobs DRV FOLD TXTR COMP TONE MIX / SAT WDTH.
- **Modulation** (FX1, on CHORUS's id) — chorus / flanger / comb. Knobs RATE DPTH FDBK MIX / DLY MODE TONE SHPE WID.
- **TEMPO SYNC** (Sam Banks) — two ColdFire caves: the tempo, crossfader and note reach the DSP, and BusDelay's TIME draws as a division (1/8, 1/4 …) instead of milliseconds. On the unit since 24 Aug 2026.
- **CC PAGE 2** (Sam Banks) — MIDI CC 62–67 reach the FX2 effect's page-2 knobs (slots 6–11) and CC 68–73 the FX1 effect's; stock reaches only page 1 over MIDI. One ColdFire cave. Confirmed on hardware 13 Sep 2026.
- **MIDI SCENES** (bkkbrls-del, [midisc](https://github.com/bkkbrls-del/midisc) 1.40MIDISC8) — per-scene parameter locks driven over MIDI: a second lock table the panel never had; scene hold, XF morph, part save/reload and the scene clear/copy/paste rows read it when a MIDI event is driving. The panel path is untouched. Thirteen units in DRAM, 38 detours, 4 pokes inside the OS.

FX2 chooser: BusVerb, BusDelay, Send, DELAY. FX1 chooser: NONE, Spectrum, Character, Modulation. The stations are FX1-only and default to a bit-exact passthrough, so a saved part that chose FILTER, LO-FI or CHORUS still plays.

## Status

Builds and passes every gate. Not flashed as a whole; both halves have run on hardware separately.

## Build

```bash
make image REMIX=rig-scenes BUILD=1     # -> out/OCTATRACK_OCTABAM1.bin
```

[BUILDING.md](BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `make check REMIX=rig-scenes` runs every gate first.

## Before you flash

- After flashing, stamp every project you will play before pressing play: `python3 tools/hw/ot_project.py stamp-defaults <project> rig-scenes`. A part saved under another layout feeds the stations its old bytes and the sequencer stalls.
- Judge BusVerb on track 5 (payload A serves tracks 5–8), BusDelay on track 1.
