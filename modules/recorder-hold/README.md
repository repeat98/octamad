# `recorder-hold` — RECORDER HOLD

Three ColdFire code caves, no DSP code: a recorder-buffer FLEX voice that
reads one sample past its recording repeats the last sample instead of
playing a zero.

In sound-on-sound (a REC3 trig with SRC3 = the track, on the same step as
the PLAY trig) the recorder arms 64 samples after the play trig binds, so
the voice plays the previous pass. Its window is the current arm spacing and
its content is the previous one. At a tempo whose bar is not a whole number
of samples the spacings alternate (82,687 / 82,688 at 128 BPM), and on each
pass where the window is one sample longer the voice fetches index END
(`+0x64`). No block is mapped there, so the fetch returns the pool base
`0x40a955e0`, one zero sample plays, and SRC3 records it back into the loop.
This page also carries the user guide to the whole recorder loop click and
its four fixes ([below](#the-loop-click-what-it-is-and-how-to-test-it)).

## Measured

In the port (26 Sep 2026), `recfix` image, fixtures built from the
RECTRIG backup: T1 FLEX on R1, REC1 + REC3 (SRC3 = T1) + PLAY on the same
steps, a 997 Hz tone into A/B. The residual of a two-tap sinusoid predictor
at each wrap, relative to the local amplitude:

| fixture | without | with |
|---|---|---|
| 128 BPM, RLEN 16, trig on step 1 — the one-sample-long wrap | 195 % | 7 % |
| 128 BPM, RLEN 4, trigs 1/5/9/13 — pass 8, then its repeats | 187 %, 47 %, 12 %, 3 % | 9 %, 2 % |
| 128 BPM, RLEN 4 — pass 16 | 62 %, 15 %, 4 % | 13 %, 3 % |

The caves substitute on those wraps only: 2 of 4 wraps at RLEN 16, 3 of 19 at
RLEN 4 (there the crossfade copy reads both positions, so each wrap is two
substitutions). What remains, 7–13 %,
is the one-sample change in loop delay that any whole-sample loop of a
fractional period has: the one-sample-short passes measure the same, with or
without the cave.

Unchanged, all eight tracks' voice audio bit-identical: the self-loop
(REC1 only) at 128 BPM RLEN 4 and 16 against `recfix`, and sound-on-sound at
120 BPM RLEN 4 and 16 against stock.

Before the arena-base rewrite (PR #444 alone), in a remix with a DRAM
runtime the caves compared against the stock base and never fired: 0
substitutions and 31 zero samples at RLEN 4 in the port. Found by Bryan T
on his USB recording remix, 26 Sep 2026.

## On the unit

Bryan T, 26 Sep 2026, his USB recording remix with the caves following the
moved base: 128 BPM / RLEN 16 still clicks every other pass. The port shows
the caves firing on those wraps in the same configuration.

## Open

- Whether the caves fire on the unit.
- Reverse playback (the fixup acts on forward fetches only).
- 16-bit recorder formats (the fixture records 24-bit).

## Gates

The build re-assembles each cave and compares against the pinned bytes.
Assemble from the repo root (for the `.include`):
`m68k-elf-as -mcpu=5475 -o x.o modules/recorder-hold/hold_copy.s`.

## The caves

Each cave sits after one fetch of the forward copy paths and runs the shared
fixup in `fix.inc`: a fetch of exactly END that came back unmapped becomes a
fetch of END − 1 with a count of one.

| cave | hook | stock bytes |
|---|---|---|
| `hold_copy.s` | `0x400086c2` | `move.l d0,d3 / addq.l #8,sp / tst.l d1` |
| `hold_xfade_a.s` | `0x4000853e` | `movea.l d0,a3 / move.l d1,d4 / move.l (76,a2),-(sp)` |
| `hold_xfade_b.s` | `0x4000854e` | `move.l d0,d7 / lea (16,sp),sp / tst.l d4` |

Conditions: the fetch returned the arena base with a positive count, `+0x15`
is negative (a recorder buffer) and the fetched index equals `+0x64`.
Anything further past END is stock.

The arena base is `0x40a955e0` on stock. A remix with a DRAM runtime (USB
AUDIO, any `dram=True` unit) moves it by the platform's 1,707 pages to
`0x41495de0`, and the fetch then returns the moved base. The manifest
declares the caves' three base literals each (`pool_base_literals`); the
build checks the count and rewrites them with the firmware's own base sites
(build report: `arena: hold cave ...: 3 arena-base literal(s) -> ...`).

## The loop click: what it is and how to test it

For anyone who records loops on the Octatrack's recorder. The symptom: a
click at the loop point when recording a bar into the recorder and looping
it back (sound-on-sound); 128 BPM clicks, 120 BPM does not.

> This is not official Elektron firmware. Read `docs/guide/BUILDING.md`
> before you flash. Build your own image from your own copy of the OS.

### What it is

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

### The fixes

Four ColdFire modules, no DSP code:

| module | what it does |
|---|---|
| [`flex-seekbind`](../flex-seekbind/README.md) | a re-bind on the same buffer is a seek for the DSP, not a new note, so the voice is not re-primed |
| [`flex-seekbind-ctr`](../flex-seekbind-ctr/README.md) | holds the per-bind counter, so the read pointer is not reset |
| [`recorder-spacing`](../recorder-spacing/README.md) | makes each pass exactly as long as the gap to its next arm, from where the current arm landed (the sequencer's own `floor(k × period)` grid, reconstructed by integer arithmetic); no lookahead, no state between passes |
| `recorder-hold` (this module) | sound-on-sound: repeats the last sample where the voice would play a zero |

The first three are 186 bytes of code. At any tempo whose bar is a whole
number of samples `RECORDER SPACING` writes back the length that was
already there: a bit-exact no-op, proven for all 11,208 (tempo, RLEN)
pairs and observed over 21,000 emulator calls at 65.6.

The [`mods`](../../remixes/test/mods/README.md) test remix carries all four
(with the other ColdFire mods) on the fourteen stock FX2 effects. `recfix`,
the remix of the first three alone, was removed on 28 Sep 2026 (`git show
13eb3339:remixes/recfix/remix.py`); OCTABAM84 was built from it.

```bash
git clone --recurse-submodules https://github.com/sambanks/octabam
cd octabam
make setup
make os && make recon
make check REMIX=mods
make image REMIX=mods BUILD=84         # -> out/OCTATRACK_OCTABAM84.bin
```

`docs/guide/BUILDING.md` is the walk-through. Always pass `REMIX=mods`
to `make check`, `make bus` and `make image` alike (there is no default
remix, and every verifier reads the one image at `out/mainos_bus.bin`).

### How to test it

The fixture, the self-recording loop:

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
or a step becomes a spike (the per-bar worst-1 ms report was the scratch
script `perbar.py`, not in the repository).

### Measured on the unit, and not

Sam's MKII, a 1 kHz tone into the self-recording loop, 90 s takes:

| | before | after |
|---|---|---|
| worst 1 ms in each bar, even bars | 1.10× the noise floor | 1.10× |
| worst 1 ms in each bar, odd bars | 1.70× (worst bar 11.5×) | 1.10× (worst bar 1.11×) |
| bars with anything above 1.25× the floor | 16 of 23 | 0 of 46 |
| 65.6 BPM control | clean | clean, identical floor |
| 132.0 BPM (a different fraction) | — | clean |

That table was OCTABAM83 (the first three caves plus the DSP effects).
OCTABAM84 (`recfix`) re-flashed and re-captured gives even bars 1.10× / odd
bars 1.10× with a residual floor of 2.67 % of rms, identical to 83's. Sam's
build of that image is sha256 `ecb574a9…`; a build from the same stock
1.40C (`370c55a3…`) should match.

Not proven:

- Any unit other than one MKII. The MKI runs the byte-identical stock OS.
- Whether all three self-loop fixes are needed; they have only been tested
  together.
- Real material over long periods; the measurements are a tone for 90 s.
- A sporadic blip, about one per 45-90 s take, on every image including
  the broken one (1.6× to 11.5× the noise floor, at no repeating bar
  position): something else, untested. An occasional tick that is not
  once-per-bar is probably this.

### Sound-on-sound (SRC3 = the track)

Bryan T, 12 Sep 2026, on OCTABAM84 in his sound-on-sound setup: still a
click, every other pass at RLEN 16 at 128 BPM. The port reproduces it
(26 Sep 2026) and it is a different mechanism from the self-loop, present
on stock firmware too:

- With a REC3 trig (SRC3 = T1) on the step of the PLAY trig, the recorder
  arms 64 samples later than with REC1 alone, so the play trig binds before
  the arm and the voice plays the PREVIOUS pass: the output is the input one
  bar + 64 samples later (REC1 alone: 64 samples, the pass being recorded).
- The window/content mismatch is this module's (top of the page).
- `RECORDER SPACING` changes nothing here: the next arm ends each recording,
  so stock and `recfix` record the same lengths.
- The self-loop fixture (REC1 only) and a 1 kHz tone (1,875 cycles per bar
  at 128 BPM, so a sample one bar old has the same value) cannot show it.

`RECORDER HOLD` repeats the last sample in place of the zero. The
one-sample skip or repeat when the loop length changes by one stays: a loop
whose period is not a whole number of samples cannot be seamless in whole
samples. At a tempo whose bar is a whole number of samples (120 among them)
the window and the content always match and sound-on-sound is clean without
a patch.

### Capturing it sample-exact over USB

On the unit the loop was judged by ear and by analog captures, and the
port shows the caves firing on the wraps where Bryan T's unit still clicks
(26 Sep 2026). [`sos-capture`](../../remixes/test/sos-capture/README.md) is
the recorder fixes with USB AUDIO IN AB and USB AUDIO OUT TRACKS:

```bash
tools/hw/sos_capture.py fixture <a project of yours> SOSCAP --bpm 128 --rlen 16
tools/hw/sos_capture.py signal sig.wav --bpm 128 --rlen 16     # 997 Hz on L, a sample-index ramp on R
# SOSCAP on the card, the image flashed, PLAY pressed, then:
tools/hw/sos_capture.py capture sig.wav unit.wav
tools/hw/sos_capture.py compare sig.wav unit.wav                # each recirculating pass against the one before
tools/hw/sos_capture.py port SOSCAP sig.wav port.wav --image out/mainos_bus.bin
tools/hw/sos_capture.py compare sig.wav unit.wav port.wav       # -> the port delay that matches the unit's arm
tools/hw/sos_capture.py port SOSCAP sig.wav port.wav --delay N
tools/hw/sos_capture.py compare sig.wav unit.wav port.wav       # -> the samples where unit and port differ
```

The ramp on R makes every sample T1 plays name the input sample it was
recorded from, so the unit's arm is located to the sample and the port
is started with its input on the same one. Once the signal stops, the
loop recirculates and each pass is compared with the one before, per
sample over shifts of −2..+2, so the one-sample walk drops out and a
missing, repeated or foreign sample stays.

Measured under the port (30 Sep 2026, `sos-capture`, 128 BPM, RLEN 16,
AMP VOL 127): every recirculating pass matches the one before; a zero
sample and a 20-sample burst planted in a copy of the capture were found
at their pass and offset, and the aligned diff against the unplanted run
listed exactly those 21 samples. The port run takes the arm to the sample
from the ramp (a +7,000-sample input delay recovered exactly).

Not yet known: whether the unit's capture is bit-exact where the port's
is (AMP and the read-back are the same DSP code on both, but the port is
not a timing model of the chip); whether macOS presents the unit as one
device with 16 inputs and 2 outputs (`capture` refuses otherwise and lists
the devices).

The port's ColdFire rate does not produce the click: `--ips` from 1,200 to
3,990 ColdFire instructions per sample (30–100 % of the default, which is
not a measurement), RLEN 16 and RLEN 4, recirculating passes identical to
the pass before at every rate; a slower ColdFire moves the arm 2–8 samples
against the input and nothing else (30 Sep 2026).

### Where the detail is

- `git show 3ceba41:docs/history/RTOS_FORK.md` section 10.53 (the diagnosis and
  the tempo table), section 10.55 (a fix that failed), sections 10.56-10.57 (the cave and
  its gates), section 10.58 (the hardware result)
- `remixes/test/mods/remix.py`, `remixes/test/mods/README.md`
- `out/hw/softretrig/tempo_seam.py`; the arithmetic gate (115,200 cases)
  was the scratch script `lever_e.py`, not in the repository
- this page's earlier home: `git show 666b6154:docs/firmware/RECORDER_CLICK.md`
