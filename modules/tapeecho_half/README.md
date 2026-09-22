# Half-rate Tape Echo experiment

This is an opt-in comparison candidate, **not the shipping Tape Echo**.
`repitch-tapeecho` continues to select the full-rate implementation;
`repitch-tapeecho-half` selects `TAPE ECHO HALF` (panel name `Tape Half`).
Both replace SPRING REV, so they cannot be selected in the same image.
Nothing has been flashed or hardware-qualified.

## Result and recommendation

The half-rate candidate saves approximately **10% in the settled eight-track
fixture and 17.5% under all-control/full-history stress** against the current,
bit-exact-optimized full-rate version. That misses the initial 20–30% total
CPU saving target. The high-frequency change is substantial, and the short
conversion filter permits measurable aliasing. Keep the full-rate version
as the default; retain this candidate only for reproducible A/B evaluation.
The measurements do not establish that the sound change is acceptable.

### Complete CPU routine

Executed instructions per 16-frame block, all eight tracks; 1500 warm-up
blocks and 1000 measured blocks, identical source/control schedules and
stock DMA model. Not hardware cycles or CPU percent.

| Eight instances | Full rate mean | Half rate mean | Reduction |
| --- | ---: | ---: | ---: |
| Settled, WOW=44 | 25,092 | 22,545 | 10.2% |
| Moving FREE TIME, WOW=44 | 25,406 | 23,032 | 9.3% |
| Changing BEAT TIME, WOW=44 | 26,789 | 23,772 | 11.3% |
| Moving FREE TIME, MIX=90 | 25,670 | 23,040 | 10.2% |
| All controls moving | 30,929 | 25,762 | 16.7% |
| All controls, synthetic full history | 31,836 | 26,264 | 17.5% |

Full-history peak falls from 32,233 to 26,567. Settled cost falls from
3.29x to 2.96x original stock DELAY. Stock-only cost is unchanged.
The first straightforward C converter/mixer saved only about 2% settled;
register-resident reconstruction/mixing and a mono record input produce
the final result above. Conversion, full-rate stereo mixing and stock
buffering account for much of the remaining cost.

### Voice and control behavior

Both native engines use the same inputs and output gain; renders are not
independently normalized. These are synthetic signal measurements, not
hardware captures or a claim of completed subjective listening.

| Measurement | Full rate | Half rate |
| --- | ---: | ---: |
| Fresh/short delay, 4 kHz relative to 1 kHz | -0.31 dB | -1.28 dB |
| Fresh/short delay, 8 kHz relative to 1 kHz | -2.33 dB | -7.24 dB |
| Fresh/short delay, 10 kHz relative to 1 kHz | -4.81 dB | -16.03 dB |
| Second/first repeat at 1 kHz, FDBK=89 | +0.127 dB | +0.076 dB |
| Second/first repeat at 4 kHz, FDBK=89 | -1.893 dB | -2.685 dB |
| Hiss buildup after 20 seconds, FDBK=102 | -7.57 dBFS | -7.74 dBFS |
| Rapid FREE sine-recurrence residual | 0.002024 FS | 0.001896 FS |
| Rapid BEAT sine-recurrence residual | 0.004385 FS | 0.005242 FS |
| 6.05 kHz component from 16 kHz input, relative to input | -114.9 dB | -36.8 dB |

Brightness loss is larger at longer delays and worn settings. High-frequency
RMS measurements above the half-rate Nyquist frequency include any alias
energy; they are not measurements of a preserved 12 kHz fundamental.
The recurrence residual is a diagnostic, not a universal audibility bound.
Lows/mids and feedback buildup remain close in these fixtures. The alias
measurement means this is more than just a different treble EQ; a longer
anti-alias filter would cost more instructions.

Rapid BEAT testing caught an overflow in the initial coefficient ramp:
half-rate feedback coefficients can differ by more than signed 32-bit range.
The candidate widens the subtraction before dividing by eight. The rapid
BEAT residual is gated below 0.01 FS so that failure cannot be accepted.

## Listening files

Every `AB.wav` plays **full rate first, 0.5 seconds of silence, then half
rate**, at identical gain. Separate `-full.wav` and `-half.wav` files are
also generated for immediate DAW switching/alignment.

- [Bright repeats](../../out/tapeecho-half/bright-repeats-AB.wav): short delay,
  fresh tape, FDBK=89, WOW=25, MIX=110; synthetic bright plucks.
- [Feedback buildup](../../out/tapeecho-half/feedback-buildup-AB.wav):
  FDBK=102, AGE=64, WOW=44, fully wet; seeded 997 Hz burst.
- [Rapid FREE TIME](../../out/tapeecho-half/rapid-free-time-AB.wav):
  alternating endpoints every 40 blocks, FDBK=64, WOW=44, MIX=110.
- [Rapid BEAT TIME](../../out/tapeecho-half/rapid-beat-time-AB.wav):
  new target every 24 blocks, same source/feedback/wow/mix.

## Implementation

The wet core processes eight samples per 16-frame stock block. Delay,
valid-history, fade and write-pointer units remain in 44.1 kHz frames.
The head reads half-rate cells at even physical ring positions and
interpolates between them. Recording duplicates each cell into two
physical stereo frames, retaining the original ring size, uncached alias,
DMA descriptor order and scratch-buffer toggles. Entry history excludes
the previous effect's samples. Full-rate dry data is exact at MIX=0.

Input uses an 11-tap half-band FIR
`[3,0,-25,0,150,256,150,0,-25,0,3]/512`. Output reconstruction uses its
corresponding two polyphases. Filters add small latency; half-rate
saturation is not oversampled. This finite conversion filter trades
stopband rejection for CPU cost and does not eliminate nonlinear aliasing.
Tone filters are redesigned at 22.05 kHz from the reference's fitted
physical corner/Q, capped at 0.45 times that sample rate. The record FIR
also runs at half rate, contributing additional darkening. The feedback
law, saturation curve and target-delay/control time scales are retained;
feedback/hiss increments advance twice per wet sample. Hiss random numbers
are generated at half rate, so its realization is deliberately different.

State grows from 200 to 260 bytes per track (2080 total). Input history and
wet reconstruction history belong to each instance and reset on entry.
No extra tape ring or DSP processing is allocated. This source snapshot is
intentionally separate so future experimental changes cannot silently
alter the full-rate reference.

## Reproduce

```sh
python3 modules/tapeecho_half/generate_tables.py
python3 modules/tapeecho_half/generate_cpu.py
python3 tools/verify/verify_tapeecho_half.py
make check REMIX=repitch-tapeecho-half
```

The verifier builds both variants from current sources, executes both
against their independent native arithmetic, and benchmarks the complete
stock eight-track routine. Half-rate stress includes full-range input,
all-control sweeps, valid-history wrap, exact dry, dirty entry, BEAT
settling, stereo/record output and persistent-state comparisons. A separate
50,000-block UBSan test exercises full-range input across multiple wraps.
The original direct 16-sample kernel tests remain on the full-rate target;
the half-rate target is validated through complete callback/state identity
rather than pretending the old kernel ABI fixtures apply unchanged.

Results, matched-gain 24-bit stereo WAVs, locally built images and logs are
under `out/tapeecho-half/`. `comparison.json` contains the detailed audio
measurements, and `reference-benchmark.log` / `half-benchmark.log` contain
the paired instruction measurements. `make check` requires the local DSP
emulator's shared-memory access; project-dependent checks require a project.
Neither benchmark proves hardware deadline headroom or resolves the
previous hardware freezes.

Validation on 21 Sep 2026: both `make check REMIX=repitch-tapeecho-half`
and `make check REMIX=repitch-tapeecho` passed all runnable checks,
including loader boot. Project playback/set checks were skipped because
no project was supplied. The final main build output was restored to
`repitch-tapeecho`; the experiment was not flashed or committed.
