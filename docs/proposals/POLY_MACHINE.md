# Poly Machine: first hardware test

Status: selectable four-voice machine implemented and emulator-qualified;
hardware qualification pending.

## Scope

The `poly-machine` remix adds `POLY` beside `STATIC`, `FLEX`, `THRU`,
`NEIGHBOR`, and `PICKUP`. Existing STATIC/FLEX tracks remain mono. A POLY
track uses one stock primary plus three rotating extension states, giving
four voices per track and 32 voices at the eight-track maximum (24 additional
voices over stock).

POLY currently uses FLEX sample behavior and accepts only `TSTR OFF` for the
four-voice path. Track FX remain after the voice sum and run once per track.

## Implementation boundary

Raw machine type 5 is retained in the Part for menu display, save, and reload.
At stock playback/configuration boundaries it is exposed as FLEX type 1. This
lets 1.40C initialize sample slots, SRC parameters, playback increments, and
voice records without indexing beyond its five stock machine rows.

Immediately before a stock retrigger overwrites the primary 168-byte voice
record, the active record is copied to one of three per-track extension
records. The extension selector rotates `0, 1, 2`; when all are occupied, the
oldest is stolen. The renderer's stock stop helper is redirected to the
selected extension so an ending or inactive extension cannot clear the
primary voice or the track's shared increment state.

### Memory

| Item | Bytes |
|---|---:|
| 24 extension records (`24 × 168`) | 4,032 |
| Three 64-frame stereo scratch buffers | 1,536 |
| Saved increments, selector, allocator, code, marker | 952 |
| Complete linked runtime | 6,520 |

The current platform still reserves a fixed 10 MiB DRAM unit. The build reports
12,895 free 6 KiB pages (about 75 MiB) for samples and recorders, versus 14,602
stock pages. Reducing that reserve is a worthwhile follow-up after hardware
stability is established.

## Reproducible benchmark

```sh
make bus REMIX=poly-machine
python3 tools/harness/benchmark_polyphony.py \
  --project "template_project/Drum Template TGM"
```

The fixture removes inherited masks, locks, conditions, and retrigs; assigns a
seamless looping sample to all eight tracks; disables timestretch; and writes
only A01-A04. It runs the same workload first on stock 1.40C FLEX and then on
POLY. A pass requires all 32 POLY records active, four distinct playback
positions on every track, and nonzero audio through the DSP handoff.

| Eight-track workload | Instructions / 16-sample frame | Relative |
|---|---:|---:|
| Stock FLEX mono | 42,783 | 1.000× |
| POLY four voices/track | 59,768 | 1.397× |
| Additional work | **16,985** | **+39.7%** |

At 44.1 kHz, 2,756.25 firmware frames occur each second. The counter therefore
represents about 117.9 million instructions/s for mono and 164.7 million for
the 32-voice case, an increment of about 46.8 million instructions/s. These
are executed-instruction counts from the emulator, not ColdFire cycle counts;
they do not prove hardware deadline margin.

Raw evidence is written to `out/polyphony-benchmark/result.json`, with command
logs, memory dumps, and rendered audio in the same untracked directory.

## First hardware test

1. Back up the CF card and keep the official 1.40C SysEx available for Startup
   Menu recovery.
2. Build with a unique version number:
   `make image REMIX=poly-machine BUILD=<nn>`.
3. Flash the generated card `.bin` using `docs/remixer/FLASHING.md`, then power
   cycle the unit.
4. Start with one POLY track, a long looping FLEX sample, neutral PTCH/RATE,
   `TSTR OFF`, no FX, and four quick manual or sequencer triggers.
5. Confirm four audible overlaps, deterministic oldest-voice stealing on a
   fifth trigger, stop/retrigger behavior, and save/reload persistence.
6. Expand through 1/2/4 POLY voices on 1/4/8 tracks, then add worst-case stock
   FX, recording, CF streaming, scenes, sample locks, reverse, slices, and MIDI.
7. Watch for audio clicks, stalled UI/sequencer, watchdog resets, or corrupt
   projects. Revert to official 1.40C immediately if the unit behaves badly.

Do not open a POLY-saved project in stock 1.40C without a backup: stock does
not know machine type 5 and may clamp or reinterpret it.

## Deliberately deferred

Pitch and RATE are still shared track parameters. Stock MIDI chromatic play
therefore remains limited to its shared ±12-semitone mapping. Detaching MIDI
note pitch from SRC PTCH/RATE and supporting a wider range requires independent
per-voice increments or resampling; it should follow only after this allocator,
looping, voice stealing, and CPU margin pass on hardware.
