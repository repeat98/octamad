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

- A trigger moves the sounding primary voice -- with its pitch, envelope and
  resampler state -- into an extension slot, then lets the stock initializer
  start the new primary voice. The slot is a free one, else the quietest
  voice already in its release, else the next in rotation (a fifth
  overlapping note steals).
- Each voice keeps its own pitch. On a POLY track the DSP resamples at unity
  and every voice is resampled on the ColdFire (linear interpolation) by its
  own increment. (Up to image 94 the DSP resampled the whole track by the
  newest note's rate, and each new note made the notes still sounding step.)
- **Each voice has its own AMP envelope** (image 95): ATK, HOLD and REL from
  the AMP page, with stock's curves and times -- linear attack, hold for
  HOLD (tempo-synced with SYNC, INF = until the key is up), exponential
  release; REL INF holds the level. A released key's voice fades out with
  its REL while the others hold; the stock track envelope is held open on a
  POLY track. The laws were measured from stock FLEX under octemu; see
  STATUS.md.
- Every voice plays at unity gain; a limiter turns the track down only where
  the voices' sum would clip, moving its gain smoothly. (Up to image 94 the
  sum was divided by 2 or 4 by voice count, so a held chord jumped 6 dB every
  time a voice started or stopped.)
- FX stay per track. While any voice sounds, a new note does not retrigger
  the DSP's track processing: an FX envelope (FILTER's, for example) restarts
  only on a note that starts from silence.
- `POLY` always plays untimestretched: the live TSTR is forced to OFF for a
  POLY track (the Part keeps whatever TSTR shows).
- `STATIC` and `FLEX` keep their stock mono path.
- Chromatic mode (FUNC+DOWN, then CHROMATIC): up to four presses arriving in
  one audio frame are accepted, extras are queued over the next three
  16-sample frames, and releasing a key releases exactly the voices that key
  started. When a track's last key is up, the track goes back to the
  sequencer, as stock does. The on-screen keyboard boxes every held key
  (stock boxes only the last one pressed), and AUDIO NOTE OUT sends a note
  on and off for each key.
- MIDI chromatic play (notes 72..96 on the track's channel, AUDIO NOTE IN on)
  is polyphonic the same way: a chord arriving in one MIDI packet plays every
  note, each note-off releases its own voice, and held MIDI notes are boxed on
  the keyboard too.
- **Octaves**: FUNC+LEFT/RIGHT walk POLY's own octave, -2..+2, shown signed
  on the keyboard page; 0 plays as stock's octave 0 (TRIG1 = -12 semitones),
  so TRIG1 reaches from -36 to +12 semitones and the top keys of +2 to +28.
  The four page lamps show it (-2 and -1 share the first). Stock tracks keep
  stock's own 0/1 octave. Pitches up to about +30 semitones from the sample
  play; above that a voice's fetch would not fit and it drops an octave.
- A sequencer or other non-chromatic trigger plays at the track's pitch with
  no octave shift and no owning key; its voice releases when HOLD runs out.
- SRC SETUP (double-click SRC or FUNC+SRC) selects POLY, opens its slot list
  with RIGHT (`<<FLEX`: POLY uses the FLEX sample slots) and the file browser
  with a second RIGHT (`LOAD FILE TO FLEX n`); the track stays POLY.

## Current limits

- Emulator-qualified (octemu, 22 and 25 Sep 2026), not yet hardware-qualified.
- In octemu a track is POLY only after SRC SETUP (double-click SRC) -> POLY ->
  YES; the screen then reads `SRC>POLY`. A track that reads `SRC>FLEX` plays
  one voice, as stock.
- `POLY` uses FLEX/RAM sample behavior; it is not a polyphonic STATIC streamer.
- A voice keeps the pitch its note had when the next note started: later
  pitch changes (PTCH knob, LFO, p-locks) reach only the newest voice. RATE,
  sample selection and other p-locks remain track-wide. AMP values are read
  every frame, so an ATK/HOLD/REL change reaches every voice at once.
- Every voice is resampled by linear interpolation, the newest too (image 95;
  before, the newest used the DSP's resampler). Off-band energy measured at
  about -60 dB for moderate intervals (image 92); high transpositions alias
  more than the DSP's resampler would. Not measured on hardware.
- The per-voice AMP follows the AMP page's ATK/HOLD/REL/SYNC. The AMP mode
  (ANLG/RTRG/R+T/TTRG) and the attack curve (LIN/LOG) are not modelled: every
  voice starts from zero with a linear attack.
- Live recording of PANEL chromatic keys on a POLY track is not wired: POLY's
  key handler returns before stock's recorder calls (`0x40042d1c`; read from
  the code, not tried). MIDI notes keep stock's recorder event.
- Timestretch polyphony is not implemented.
- The platform reserves 10 MiB of DRAM, leaving 12,895 6 KiB pages (about
  75 MiB) for samples/recorders, versus 14,602 pages in stock.

## Measured emulator load

The deterministic benchmark runs A01-A04 on all eight tracks and validates 8
active primaries, 24 active extensions, four distinct positions per track,
and nonzero DSP output. Measured 25 Sep 2026 (image 95) on the ColdFire port:

| Case | ColdFire instructions / 16-sample frame | Relative |
|---|---:|---:|
| Stock 1.40C FLEX, eight mono tracks | 42,539 | 1.00x |
| POLY, four voices on all eight tracks, at the sample's pitch | 65,228 | 1.53x |
| POLY, the same with every voice resampled (image 95 without its fast paths) | 76,056 | 1.79x |

Image 92 measured 65,808 (1.55x) for the first case. Since image 95 every
voice, the newest too, is resampled on the ColdFire unless it plays at
exactly the sample's own rate, and each carries its own envelope; the third
row bounds a chord of transposed notes on every track.

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
