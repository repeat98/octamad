# Drumazon 2 reference, 28 September 2026

The user initialized **SCENE > Init** in their installed Drumazon 2 and
closed the hosted editor. The saved component state identifies `- Init -`,
version 2.0.4. It contains BD Attack 25%, Tune 50%, Decay 25%, Pitch 50%,
and Tune Depth 50%; BD and master levels are 0 dB.

The reference harness restores this state for each capture, disables the
internal sequencer and BD processing, and routes the bass drum directly to
Master with its send off. Note 36, velocity 100, arrives at 100 ms in a
three-second, 44.1 kHz render. No reference gain normalization is applied.
References use float32 WAV to preserve peaks above full scale at high ATTACK.
A repeated init capture is bit-identical. A control with note-off at 200 ms
and one without it produced identical init audio; the reproducible host
omits note-off.

The first Pedalboard audio render crashed inside Drumazon. The companion
JUCE host succeeds with all **16 stereo buses** enabled and backed by real
buffers. Pedalboard was used to open/save the initialized editor state.
No plugin binary, state, preset data or reference recording is included in
the module. All such artifacts are local to ignored `out/`.

## What the synthesis now models

The captures informed independent base pitch, pitch-envelope time, pitch
excursion and amplitude release curves. The body appears after an
approximately 3 ms reset interval; its amplitude is nearly flat until
about 60 ms, followed by the DECAY-controlled release. The original
triangle shaper remains; the trigger transient now has a negative pulse,
a short positive rebound and a filtered noise contribution. The short VCO
release ramp is an empirical fit, not a claim about Drumazon's code or a
particular transistor circuit.

`generate.py` contains the original coefficient fits. The center value 64
maps to 50%, and endpoints 0/127 reach the full reference control range.
The fastest TUNE extrapolation is ill-conditioned: its excursion is capped
and that extreme is not claimed as a match.

## Measured agreement and limits

`tools/harness/compare_analog_bassdrum.py` evaluates 26 patches at their
original trigger times and levels, with the optional SRC SETUP LPF bypassed.
The init patch measured:

| Metric | Result |
|---|---:|
| Body waveform correlation, 6–200 ms after trigger | 0.9964 |
| Mean absolute envelope error, 20–130 ms | 0.234 dB |
| Reference peak | 0.9849 |
| Synth peak | 0.8503 |

After listening, the user identified an overly sharp attack. The 909 output
pole is now 4 kHz instead of 7.2 kHz; pitch and amplitude envelopes are
unchanged. Over the first 20 ms, a third-order 6 kHz high-pass measures
reference RMS 0.0100, previous synth 0.0166, revised synth 0.0112 (linear
full-scale units). This is a brightness check, not a waveform match; the
revised transient peak is lower than the reference.

These are **init-body** measurements. The attack's noise waveform and all
control combinations are not matched. The full sweep report retains the
poor cases: e.g. 75% TUNE DEPTH has negative body waveform correlation,
showing a substantial phase/contour mismatch despite a close amplitude
envelope. PITCH extremes and minimum TUNE also deviate more than init.
At maximum ATTACK the reference peaks around 2.49, while the source engine
clips at full scale; that transient/headroom difference also remains.
They are further calibration work, not hidden by the good default result.
Drumazon agreement does not establish agreement with a physical TR-909.

## Reproduce locally

Build the optional host against a locally available JUCE source tree:

```sh
cmake -S tools/harness/drumazon_host -B out/analog-bassdrum/host-build \
  -DJUCE_SOURCE=/absolute/path/to/JUCE -DCMAKE_BUILD_TYPE=Release
cmake --build out/analog-bassdrum/host-build -j8
```

With scipy installed in a separate Python environment, and the saved
initialized state at `out/analog-bassdrum/drumazon/initialized.state`:

```sh
python tools/harness/drumazon_reference.py --sweep
python tools/harness/compare_analog_bassdrum.py
```

The capture script refuses a state without the expected initialized scene
and bass-drum values. `capture.json` records state/audio hashes and capture
settings. `drumazon-comparison.json` records every comparison, including
unfavorable results. `909-drumazon-then-analog.wav` plays the reference
first, a half-second gap, then this engine, with no time or level fitting.
