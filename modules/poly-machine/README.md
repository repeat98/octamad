# Poly Machine

`POLY` is an experimental third sample-machine choice beside `STATIC` and
`FLEX`. It provides four untimestretched voices on every audio track: the
stock primary voice plus three rotating extension voices. Across all eight
audio tracks that is 32 simultaneous sample voices, or 24 voices more than
stock firmware 1.40C.

It is selectable in the machine menu, is stored as machine type 5, and
reloads as `POLY`. Internally it presents FLEX semantics to stock
configuration and playback code while retaining type 5 in the Part for UI and
persistence.

## Behavior

- A trigger preserves the current primary voice in the next extension slot,
  then lets the stock initializer start the new primary voice.
- The three extension slots rotate deterministically; a fifth overlapping
  trigger steals the oldest extension.
- Each voice keeps its own pitch. The stock renderer only fetches raw source
  frames (the DSP resamples the whole track by the primary's increment), so
  each extension fetches its own frame count and is linearly resampled on the
  ColdFire to the primary's source rate before the mix. A held C-E-G chord
  sounds as three pitches.
- One voice is unity gain, two are divided by two, and three or four are
  divided by four to retain mix headroom.
- `POLY` always plays untimestretched: the live TSTR is forced to OFF for a
  POLY track (the Part keeps whatever TSTR shows). Earlier images fell back to
  one voice unless TSTR was OFF, and the stock default is AUTO.
- `STATIC` and `FLEX` keep their stock mono path.
- Chromatic mode (FUNC+DOWN, then CHROMATIC): up to four presses arriving in
  one audio frame are accepted, extras are queued over the next three
  16-sample frames, and releasing a key stops exactly the voice that key
  started. When a track's last key is up, the track goes back to the
  sequencer, as stock does.
- Octaves (FUNC+LEFT/RIGHT on the keyboard) walk 0..2 and follow stock's
  mapping: the lowest octave is -12 semitones. Pitches above +24 semitones
  from the sample cannot be fetched in one 16-sample chunk (the caller's
  63-frame limit), so those keys drop an octave. (The walk stops at 2 also
  because the stock chromatic LED routine overruns its stack from octave 4.)
- A sequencer or other non-chromatic trigger plays at the track's pitch with
  no octave shift and no owning key.
- SRC SETUP (double-click SRC or FUNC+SRC) selects POLY, opens its slot list
  with RIGHT (`<<FLEX`: POLY uses the FLEX sample slots) and the file browser
  with a second RIGHT (`LOAD FILE TO FLEX n`); the track stays POLY.

## Current limits

- Emulator-qualified (octemu, 22 Sep 2026), not yet hardware-qualified.
- `POLY` uses FLEX/RAM sample behavior; it is not a polyphonic STATIC streamer.
- An extension keeps the pitch its note had when it was stolen: later pitch
  changes (PTCH knob, LFO, p-locks) reach only the newest voice. RATE, sample
  selection and other p-locks remain track-wide.
- Extension voices are resampled by linear interpolation; off-band energy
  measured at about -60 dB, level with the stock voice alone.
- MIDI chromatic play keeps the stock single-voice behaviour.
- A key released before its queued press has played (more than four presses
  in one frame) is not matched.
- Timestretch polyphony is not implemented.
- The platform reserves 10 MiB of DRAM, leaving 12,895 6 KiB pages (about
  75 MiB) for samples/recorders, versus 14,602 pages in stock.

## Measured emulator load

The deterministic benchmark runs A01-A04 on all eight tracks and validates 8
active primaries, 24 active extensions, four distinct positions per track,
and nonzero DSP output. Measured 22 Sep 2026 (image 92, with the per-voice
resampler; 93 changes no render code) on the ColdFire port:

| Case | ColdFire instructions / 16-sample frame | Relative |
|---|---:|---:|
| Stock 1.40C FLEX, eight mono tracks | 42,552 | 1.00× |
| POLY, four voices on all eight tracks | 65,808 | 1.55× |
| Increment | 23,256 | +54.7% |

The earlier image without the resampler measured 59,768 (1.40×). All voices
in this benchmark share one pitch; an extension pitched above the newest note
fetches proportionally more source frames (up to ~4× at the +24-semitone
limit), so a wide chord costs more than this table shows.

These are emulator instruction counts, not hardware cycles or a deadline
guarantee. Cache misses, SDRAM/CF contention, DMA, interrupt jitter, recorders,
and worst-case effects still require measurement on the Octatrack.

Build and benchmark:

```sh
make bus REMIX=poly-machine
python3 tools/harness/benchmark_polyphony.py \
  --project "template_project/Drum Template TGM"
```

For the first hardware procedure and rollback notes, see
`docs/proposals/POLY_MACHINE.md` and `docs/remixer/FLASHING.md`.
