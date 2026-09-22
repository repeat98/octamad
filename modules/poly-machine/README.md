# Poly Machine

`POLY` is an experimental third sample-machine choice beside `STATIC` and
`FLEX`. It provides four untimestretched voices on every audio track: the
stock primary voice plus three rotating extension voices. Across all eight
audio tracks that is 32 simultaneous sample voices, or 24 voices more than
stock firmware 1.40C.

This is the first hardware-test build. It is selectable in the machine menu,
is stored as machine type 5, and reloads as `POLY`. Internally it presents
FLEX semantics to stock configuration and playback code while retaining type
5 in the Part for UI and persistence.

## Behavior

- A trigger preserves the current primary voice in the next extension slot,
  then lets the stock initializer start the new primary voice.
- The three extension slots rotate deterministically; a fifth overlapping
  trigger steals the oldest extension.
- The stock renderer runs once per active record. Four signed 32-bit stereo
  streams are mixed into the normal track buffer before the existing track FX.
- One voice is unity gain, two are divided by two, and three or four are
  divided by four to retain mix headroom.
- `STATIC` and `FLEX` keep their stock mono path.
- `POLY` falls back to the stock mono path unless `TSTR` is `OFF`.

## Current limits

- This is emulator-qualified but not yet hardware-qualified.
- `POLY` uses FLEX/RAM sample behavior; it is not a polyphonic STATIC streamer.
- Pitch, RATE, sample selection, and parameter locks remain track-wide in this
  first image. MIDI chromatic play therefore retains the stock shared ±12
  semitone behavior. Independent wide-range MIDI pitch requires a per-voice
  pitch/resampling stage and is intentionally deferred until the allocator and
  render path pass hardware timing tests.
- Timestretch polyphony is not implemented.
- The linked runtime is 6,520 bytes, but the current platform reserves 10 MiB
  of DRAM, leaving 12,895 6 KiB pages (about 75 MiB) for samples/recorders,
  versus 14,602 pages in stock.

## Measured emulator load

The deterministic benchmark runs A01-A04 on all eight tracks and validates 8
active primaries, 24 active extensions, four distinct positions per track,
and nonzero DSP output.

| Case | ColdFire instructions / 16-sample frame | Relative |
|---|---:|---:|
| Stock 1.40C FLEX, eight mono tracks | 42,783 | 1.00× |
| POLY, four voices on all eight tracks | 59,768 | 1.40× |
| Increment | 16,985 | +39.7% |

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
