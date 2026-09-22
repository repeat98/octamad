# Poly Machine render-path prototype

The intended product boundary is a new `POLY` machine beside `STATIC` and
`FLEX`; this first-stage remix forces eligible tracks through its engine only
to benchmark feasibility. It does not add the machine chooser entry yet.

This module measures the feasibility of four voices per Octatrack audio
track without replacing the stock sample renderer. It keeps the stock
168-byte voice record as voice 0 and adds three records per track in the
platform DRAM runtime: 24 additional records, 4,032 bytes total. Four
voices on each of eight audio tracks means 32 simultaneous render slots;
“24 global” is the additional-voice count, not the total.

For an active track whose SETUP `TSTR` is exactly `OFF`, the first chunk
copies the stock voice record into the three extra records. The firmware's
own renderer then runs once per record. Three results use 512-byte scratch
buffers, and the four signed 32-bit stereo streams are averaged into the
normal destination. Timestretched tracks and invalid/oversized chunks take
the original mono path.

## What this prototype proves

- Three extra voice states can live outside the fixed stock eight-record
  array while the stock renderer operates on them.
- The real ColdFire renderer and mixer cost can be measured under the port
  for mono versus four calls per active track.
- The audio handoff retains the stock buffer shape and unity-ish gain.

## What it does not implement yet

- A trig allocator, four different notes, or deterministic oldest-voice
  stealing.
- Re-priming on legato/retrig while the primary voice remains active.
- Per-voice parameter locks, independent pitch, or independent sample
  selection.
- Timestretched polyphony.
- A hardware timing guarantee. The emulator counts ColdFire instructions;
  it does not model cache misses, memory-bus contention, or DSP deadlines.

## Hooks and memory

- `0x400041c4`: replaces the renderer call and its stack cleanup.
- `0x40007978`: replaces the renderer's stock voice-pointer calculation.
- 4,032 bytes: 24 extra voice records.
- 1,536 bytes: three 64-frame stereo scratch buffers.
- 12 bytes: selector and per-track prime flags (plus alignment).

Build and benchmark with:

```sh
make bus REMIX=polyphony-proto
python3 tools/harness/benchmark_polyphony.py --project "template_project/Drum Template TGM"
```
