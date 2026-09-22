# Poly Machine: four-voice prototype and load benchmark

Status: render-path prototype, measured under the ColdFire/DSP emulator; not
yet a user-selectable machine and not hardware-qualified.

## Decision

Polyphony should be introduced as a third `POLY` sample machine beside
`STATIC` and `FLEX`, rather than changing either existing machine. Existing
projects would therefore retain their current mono behavior and CPU load.
Only a track explicitly assigned `POLY` would allocate four voices.

The target is four total voices on each of the eight audio tracks. That is 32
simultaneous render slots at the global maximum: the eight stock primary
voices plus 24 additional voices.

## Implemented prototype

`modules/polyphony-proto` reuses the 1.40C sample renderer rather than
reimplementing it:

1. The stock 168-byte voice record remains voice 0.
2. Three additional records per track live in the platform DRAM runtime.
3. On the first active, untimestretched chunk, the primary record is cloned
   into those three records.
4. The stock renderer runs once for each record.
5. The three extra streams use scratch buffers; four signed 32-bit stereo
   streams are divided by four and summed into the normal track buffer.
6. The existing per-track DSP effects remain downstream of that buffer and
   still run once per track.

The prototype deliberately applies to `TSTR OFF` only. Other TSTR modes take
the original mono path. It also does not yet interpret separate trigs; its
three additional voices initially clone the same note. This isolates the
real renderer/memory cost before adding machine UI and allocation policy.

### Firmware hooks

| Address | Purpose |
|---|---|
| `0x400041c4` | Replace the renderer call and stack cleanup with the one-or-four-call wrapper. |
| `0x40007978` | Select the stock voice record or one of the extra DRAM records. |

### Memory

| Item | Bytes |
|---|---:|
| 24 extra voice records (`24 × 168`) | 4,032 |
| Three 64-frame stereo scratch buffers | 1,536 |
| Selector, prime flags, alignment/end marker | 16 |
| Code | 412 |
| Complete linked runtime | 5,996 |

The module currently opts into octabam's fixed 10 MiB platform reserve, so
the practical sample-memory cost is that reserve, not merely 5,996 bytes.
If Poly becomes a production machine, the reserve policy should be revisited
so small ColdFire modules do not pay a disproportionate 10 MiB minimum.

## Benchmark

Command:

```sh
make bus REMIX=polyphony-proto
python3 tools/harness/benchmark_polyphony.py \
  --project "template_project/Drum Template TGM" --frames 600
```

Fixture: one looping FLEX sample on all eight audio tracks, neutral pitch,
forward rate, `TSTR OFF`, all tracks triggered on A01 step 1. The exact same
card image runs first on unmodified 1.40C and then on the prototype image.

| Eight sustained tracks | ColdFire instructions / 16-sample frame | Relative |
|---|---:|---:|
| Stock mono | 41,321 | 1.000× |
| Four render voices | 63,826 | 1.545× |
| Additional load | **22,505** | **+54.5%** |

At 44.1 kHz this corresponds to 2,756.25 firmware frames per second:

- stock workload represented by the counter: about 113.9 million
  instructions/second;
- four-voice workload: about 175.9 million instructions/second;
- increment: about 62.0 million instructions/second, or approximately 2,813
  instructions per frame per active four-voice track in this fixture.

These are emulator instruction counts, not ColdFire cycles. They do not model
cache misses, SDRAM contention, DMA contention, interrupt jitter, or missed
hardware audio deadlines. The result quantifies relative CPU work; it does
not establish safe hardware headroom.

Because the three prototype voices clone one note, they also share sample
locality. Four genuinely independent notes may incur more cache, page, and
streaming traffic; this result is a renderer-work baseline, not a worst case.

### Correctness gates observed

- The DRAM loader reached the RTOS handoff and restored all 5,996 runtime
  bytes exactly.
- All eight stock voice records remained active after the run.
- All eight three-voice extension groups were primed.
- The four-voice averaged output matched mono sample-for-sample after allowing
  the two separately booted emulator runs' per-lane DSP ring phase to align by
  at most two samples.
- Both runs reached all 600 requested frames without a ColdFire fault.

Raw result: `out/polyphony-benchmark/result.json`. Logs and audio are in the
same directory and remain untracked build artifacts.

## Product path to a selectable Poly Machine

The next implementation milestone should preserve the successful render
engine but replace the clone trigger with a real machine boundary:

1. Add a `POLY` entry to the track machine chooser and a persistent machine
   value that round-trips through project/part load and save.
2. Route only `POLY` tracks through the four-voice wrapper. `STATIC` and
   `FLEX` must continue directly to the stock mono renderer.
3. On each trig, select an idle voice; when all four are active, steal the
   oldest voice deterministically.
4. Copy the track/sample state required for the new note, then apply that
   trig's pitch and start position to the selected voice.
5. Keep track FX after the voice sum so adding voices does not multiply DSP
   effect load.
6. Reject or explicitly fall back for timestretch until four simultaneous
   grain engines have a separate measured budget.
7. Add save/load compatibility, retrig, one-shot, loop, reverse, sample-lock,
   slice, choke, and voice-stealing tests.
8. Run a hardware stress matrix before calling it usable: 1/2/4 voices on
   1/4/8 tracks, both DSP cores loaded with worst-case stock effects, recorder
   and streaming activity, and deadline/xrun instrumentation.

The +54.5% eight-track increase is encouraging enough to continue, but too
large to infer safety from clock frequency alone. A selectable Poly Machine
should remain experimental until hardware deadline measurements show a useful
worst-case margin.
