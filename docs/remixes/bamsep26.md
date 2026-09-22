# `bamsep26` — The rig

BusVerb + BusDelay on one aux bus (the send passes the delay into the reverb; each engine's WET prints on the track that hosts it), three stations on FX1, the stock delay, tempo sync, CC→page 2. The image on Sam's unit.

## What is in it

- **BusVerb** — an eight-line FDN reverb (ROOM / PLATE / BIG, shimmer, gate, mid/side width) that serves all eight tracks over a cross-core bus; its tail comes out on the host track. Hosted on one of tracks 5–8. Knobs SEND TIME⌐SIZE SHMR⌐SHFT WET / MODE TONE DIFF GATE, page 2 filled from the top left (⌐ = drawn as a linked pair; the 16 Sep 2026 knob pass, image 29 on the unit: the links draw, SHFT draws its words on page 1).
- **BusDelay** — a multi-mode delay (CLEAN / pitched GRAIN cloud / REVERSE, tape wow) serving all eight tracks; its repeats come out on the host track and go on into the reverb. Hosted on one of tracks 1–4. TIME reads as a tempo division (TEMPO SYNC); up to 739 ms (1/4 and 1/2T at 121 BPM) since the 32K lines, image 28 (15 Sep 2026, Sam: "sounds fantastic now"). Knobs SEND TIME⌐FDBK TONE PING WET / MODE SCAT⌐DENS SIZE⌐PTCH WOW (SIZE draws GLEN in GRAIN and SLEN in REVERSE; a knob a mode never reads is named `---` there: SCAT DENS SIZE PTCH in CLEAN, SCAT DENS PTCH and PING in REVERSE; image 29 confirmed the convention; WOW in the freeze's slot since 20 Sep 2026).
- **Send** — the FX2 effect every other track runs: one SEND knob into the bus. The fallback for any unassigned track.
- **DELAY** (stock) — the stock Echo Freeze delay row, unchanged; it runs on the ColdFire and costs the DSP nothing.
- **Spectrum** (FX1, on FILTER's id) — a filter pedal: SEM LP/BP/HP, Airwindows Capacitor2, formants, the Moog ladder; ENV and LFO onto the cutoff; width. Knobs FREQ⌐RES ENV LDP⌐LSP WDTH / MODE (top left; ISO draws LOW COLR, VOWL draws VOWL SHRP).
- **Character** (FX1, on LO-FI's id) — crush, fold/ring, saturation, compressor, width; GLUE compression on track 8 by position. Knobs DRV FOLD TXTR COMP TONE MIX / SAT WDTH (16 Sep 2026: MIX bottom right on page 1; SAT top left on page 2, where every effect's MODE sits; page-1 slot 4 was the bus return from 13 to 20 Sep 2026 and is TONE again).
- **Modulation** (FX1, on CHORUS's id) — JUNO / DIM / FLNG / COMB / PHSR, each from a permissively licensed source (`docs/effects/PORTS.md`), levelled to JUNO at the views. Knobs RATE⌐DPTH DLY FDBK LOFI MIX / MODE TONE WDTH (MODE top left, as on every effect; FLNG draws MANL, COMB PTCH DCAY BRIT with RATE DPTH WDTH `---`, PHSR STGS with TONE `---`) (LOFI clocks the delay line coarse and quantises it; 0 is bit-exact). Heard on the emulator 16 Sep 2026 (ENS dropped, LOFI added); unflashed.
- **TEMPO SYNC** (Sam Banks) — two ColdFire caves: the held MIDI note reaches BusDelay, and BusDelay's TIME draws as a division (1/8, 1/4 …) instead of milliseconds; the tempo itself comes from stock's record word. On the unit since 24 Aug 2026; the note-only cave since image 24 (15 Sep 2026).
- **CC PAGE 2** (Sam Banks) — MIDI CC 62–67 reach the FX2 effect's page-2 knobs (slots 6–11) and CC 68–73 the FX1 effect's; stock reaches only page 1 over MIDI. One ColdFire cave. Confirmed on hardware 13 Sep 2026.
- **MODE DEFAULTS** (Sam Banks) — turning a MODE on the panel re-defaults the knobs around it to that mode's view (BusDelay's three modes, Modulation's five, Spectrum's ISO), on FX1 and FX2; SEND is never touched. Two detours in the page-2 editors. Measured under the port (`verify_modedefaults`); confirmed on the unit, image 26 (15 Sep 2026); a MODE set over CC 62/68 is re-defaulted too since PR #291 (image 28).

FX2 chooser: BusVerb, BusDelay, Send, DELAY. FX1 chooser: NONE, Spectrum, Character, Modulation. Every track but 8 sends, the hosts included; T8 is the master and its send is refused (its input is the mix, the hosts' wet included). The stations are FX1-only and default to a bit-exact passthrough, so a saved part that chose FILTER, LO-FI or CHORUS still plays.

## Status

On Sam's MKII as image 43 (`OCTABAM43`, 21 Sep 2026; `CHANGELOG.md` per image); images 44–47 were probes (two wedged, none a release). Image 49 built, unflashed: SEND returns on an FX1 slot (the bleed with every SEND at 0, and the core-1 tracker's lead of one behind the THRU-host wash), and the bus itself no longer depends on the cores' phase (eight buffers, read three back, a per-client block count; `FAILURE_MODES.md`, `XBUS.md`). Bus latency 48 samples. Heard on 43: the delay on a sample host with a trig every step, clean through eight loops. Not yet heard: the TIME ramp within the block, the once-per-block glides, the `---` and per-mode names, Character's TONE on page 1 (slot 4) with WDTH on page-2 slot 7, Modulation's five modes. The one-aux bus claims all pass on hardware (flash 7); the sends into the delay with the note-only tempo cave, image 24. Every other stock effect is harvested: 13 effects; a saved part naming one plays silence.

## Build

```bash
make image REMIX=bamsep26 BUILD=1     # -> out/OCTATRACK_OCTABAM1.bin
```

[BUILDING.md](BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `make check REMIX=bamsep26` runs every gate first.

## Before you flash

- After flashing, stamp every project you will play before pressing play: `python3 tools/hw/ot_project.py stamp-defaults <project> bamsep26 --all --keep-mode` (the 16 Sep 2026 knob pass moved slots on BusVerb, Character and Modulation; 20 Sep 2026 put Character's TONE in slot 4 and WDTH in page-2 slot 7: a stored RET or page-2 byte lands in them otherwise; CC 38 is TONE, CC 69 WDTH). A part saved under another layout feeds the stations its old bytes and the sequencer stalls. The stamp warns about an engine on the wrong core (BusVerb on T1–4, BusDelay on T5–8: it runs as SEND there).
- Judge BusVerb on track 5 (payload A serves tracks 5–8), BusDelay on track 1.
- First flash with the 32K lines: a stored TIME byte now means twice the time (64 + knob·256 samples). `python3 tools/hw/ot_project.py stamp-slot <project> busdelay 1 20` on every project you will play, or re-set TIME on the delay host per part.
