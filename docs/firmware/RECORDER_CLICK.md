# The recorder loop click

For anyone who records loops on the Octatrack's recorder. The symptom: a
click at the loop point when recording a bar into the recorder and looping
it back (sound-on-sound); 128 BPM clicks, 120 BPM does not.

> This is not official Elektron firmware. Read `docs/remixer/FLASHING.md`
> before you flash. Build your own image from your own copy of the OS.

## 1. What it is

A bar is not always a whole number of samples. At 128 BPM a bar is
82,687.5 samples. The recorder writes whole samples, so the length
converter writes 82,687 every pass; the sequencer keeps the halves and
fires each recorder trig at `floor(k × 82,687.5)`, so consecutive arms are
alternately 82,687 and 82,688 samples apart. On every pass where the arm
came one sample later than the recording ended, one sample of the input is
never recorded, and the loop's wrap splices two moments two samples apart.

At 120 BPM a bar is 88,200 samples, exact, so the arms are evenly spaced.
At RLEN 4 the period is 20,671.875 samples, so the sample is lost once
every eight passes ("around the sixth repeat"). Only 46 of the 1,401 tempi
from 60.0 to 200.0 give a whole-number bar: 120, 125, 126, 135, 140, 144
and 150 among them (`out/hw/softretrig/tempo_seam.py` lists them).

Two louder faults sat on top of it:

1. The voice was restarted from scratch every loop: the DSP was told the
   re-bind was a new note and re-primed the voice: a chirp, then hash at
   140 % of the signal's level over 300 samples.
2. The read pointer was reset onto the same alternating grid: a
   ±1.5-sample lurch every bar.

## 2. The patch

Three ColdFire code caves, 186 bytes of code, no DSP code:

| module | what it does |
|---|---|
| `FLEX SEEK BIND` | a re-bind on the same buffer is a seek for the DSP, not a new note, so the voice is not re-primed |
| `FLEX SEEK BIND CTR` | holds the per-bind counter, so the read pointer is not reset |
| `RECORDER SPACING` | makes each pass exactly as long as the gap to its next arm, from where the current arm landed (the sequencer's own `floor(k × period)` grid, reconstructed by integer arithmetic); no lookahead, no state between passes |

At any tempo whose bar is a whole number of samples `RECORDER SPACING`
writes back the length that was already there: a bit-exact no-op, proven
for all 11,208 (tempo, RLEN) pairs and observed over 21,000 emulator calls
at 65.6.

The `recfix` remix is these three and the fourteen stock FX2 effects
(every octabam image rebuilds the FX2 chooser from the remix's contents;
listing the stock effects costs nothing and keeps the unit normal).

```bash
git clone --recurse-submodules https://github.com/sambanks/octabam
cd octabam
make setup
make os && make recon
make check REMIX=recfix
make image REMIX=recfix BUILD=84         # -> out/OCTATRACK_OCTABAM84.bin
```

`docs/remixes/BUILDING.md` is the walk-through. Always pass `REMIX=recfix`
to `make check`, `make bus` and `make image` alike (there is no default
remix, and every verifier reads the one image at `out/mainos_bus.bin`). Sam's build of that image is sha256 `ecb574a9…`;
yours should match if your stock 1.40C does (`370c55a3…`).

## 3. How to test it

The fixture, the sound-on-sound shape:

- T1 = FLEX machine, pointed at its own recorder buffer (R1)
- recorder source INAB, RLEN 16 (then repeat at RLEN 4)
- a RECORDER trig and a PLAY trig on T1, on step 1, pattern 1X/16 steps
- internal clock, 128.0 BPM
- FX1 and FX2 off on T1 (a reverb smears a discontinuity)
- a continuous source into A/B: a steady tone is the most revealing; a
  drum loop hides the click under its transients

Listen for a tick once per bar at the loop point. Before the patch it is
there at 128 and absent at 120; after, absent at both.

| # | do this | before | after |
|---|---|---|---|
| 1 | 128.0 BPM, RLEN 16 | tick every bar | nothing |
| 2 | 120.0 BPM, same | clean | still clean; if 120 got worse, stop and say so: the patch does nothing there by construction |
| 3 | 128.0 BPM, RLEN 4 | tick roughly every 8th pass | nothing |

If you can record the output: `out/hw/softretrig/gaps.py` predicts each
sample from one tone period earlier, so a steady tone cancels and a hole
or a step becomes a spike; `perbar.py` prints the worst 1 ms of each bar.

## 4. Measured, and not

Measured on one unit (Sam's MKII), a 1 kHz tone into the self-recording
loop, 90 s takes:

| | before | after |
|---|---|---|
| worst 1 ms in each bar, even bars | 1.10× the noise floor | 1.10× |
| worst 1 ms in each bar, odd bars | 1.70× (worst bar 11.5×) | 1.10× (worst bar 1.11×) |
| bars with anything above 1.25× the floor | 16 of 23 | 0 of 46 |
| 65.6 BPM control | clean | clean, identical floor |
| 132.0 BPM (a different fraction) | — | clean |

That table was OCTABAM83 (the three caves plus the DSP effects). `recfix`
itself (OCTABAM84) re-flashed and re-captured gives even bars 1.10× / odd
bars 1.10× with a residual floor of 2.67 % of rms, identical to 83's.

Not proven:

- Any unit other than one MKII. The MKI runs the byte-identical stock OS.
- Whether all three fixes are needed; they have only been tested together.
- Real material over long periods; the measurements are a tone for 90 s.
- A sporadic blip, about one per 45-90 s take, on every image including
  the broken one (1.6× to 11.5× the noise floor, at no repeating bar
  position): something else, untested. An occasional tick that is not
  once-per-bar is probably this.

## 5. Sound-on-sound (SRC3 = the track)

Bryan T, 12 Sep 2026, on OCTABAM84 in his sound-on-sound setup: still a
click, every other pass at RLEN 16 at 128 BPM. The port reproduces it
(26 Sep 2026) and it is a different mechanism from §1, present on stock
firmware too:

- With a REC3 trig (SRC3 = T1) on the step of the PLAY trig, the recorder
  arms 64 samples later than with REC1 alone, so the play trig binds before
  the arm and the voice plays the PREVIOUS pass: the output is the input one
  bar + 64 samples later (REC1 alone: 64 samples, the pass being recorded).
- The voice's window is the current arm spacing; its content is the previous
  pass, one spacing earlier. At 128 BPM they alternate 82,687 / 82,688, so on
  every pass where the window is one sample longer the voice reads index END,
  where no block is mapped, and plays one zero sample. SRC3 records it back
  into the loop. The passes one sample shorter skip one sample instead.
- `RECORDER SPACING` changes nothing here: the next arm ends each recording,
  so stock and `recfix` record the same lengths.
- The fixture in §3 (REC1 only) and a 1 kHz tone (1,875 cycles per bar at
  128 BPM, so a sample one bar old has the same value) cannot show it.

`RECORDER HOLD` (in `recfix`) repeats the last sample in place of the zero.
In a remix with a DRAM runtime the caves follow the moved arena base (the
build report prints `arena: hold cave ...`); a build of main before that
change carries caves that never fire in such a remix.
Port results and conditions: `modules/recorder-hold/README.md`. The
one-sample skip or repeat when the loop length changes by one stays: a loop
whose period is not a whole number of samples cannot be seamless in whole
samples. At a tempo whose bar is a whole number of samples (120 among them)
the window and the content always match and sound-on-sound is clean without
a patch.

On hardware (Bryan T, 26 Sep 2026, his USB recording remix with the caves
following the moved base): 128 BPM / RLEN 16 still clicks every other pass.
The port shows the caves firing on those wraps in the same configuration.
Open: whether the caves fire on the unit.

## 6. Where the detail is

- `docs/history/RTOS_FORK.md` §10.53 (the diagnosis and the tempo table),
  §10.55 (a fix that failed), §10.56-10.57 (the cave and its gates), §10.58
  (the hardware result)
- `modules/recorder-spacing/`, `modules/recorder-hold/`, `modules/flex-seekbind/`,
  `modules/flex-seekbind-ctr/`
- `remixes/recfix/remix.py`, `remixes/recfix/README.md`
- `out/hw/softretrig/tempo_seam.py`, `lever_e.py` (the arithmetic gate,
  115,200 cases)
