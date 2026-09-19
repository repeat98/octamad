# Euclid

A stereo Euclidean filter for either FX slot. It follows the Octatrack's
transport, track speed and swing grid. The rhythm can have 1–64 steps and
keeps rolling across pattern loops; PLAY resets its phase.

The `euclid` remix includes stock Plate, Spring and Dark Reverb in FX2.
Their descriptors, DSP code and dispatch entries retain their stock values.

The `octapitch-euclid` remix adds the same effect to Octapitch2's REPITCH,
PREVIEW VOL and FORCE FILENAME BPM improvements. It removes DJ EQ,
Spring Reverb and Plate Reverb, as requested, and retains every other stock
effect. Euclid is available in both FX slots; Dark Reverb remains in FX2.

| Page | A | B | C | D | E | F |
|---|---|---|---|---|---|---|
| Main | FREQ | RES | DEPTH | DEC / LEN | STEPS | PULSE |
| Setup | ROT | RATE | TYPE | ATK / EDGE / SLEW | Output mode | MIX |

FREQ sets the base cutoff, approximately 30 Hz–14 kHz on a logarithmic
scale. TYPE selects low-pass, band-pass or high-pass. LP now has an
S1000-inspired 18 dB/octave response; BP and HP retain their previous sound.
RES=0 approximates a third-order Butterworth low-pass. Higher RES adds
resonance as a Euclid extension: the S1000 had no resonance control.
This is a response approximation, not a model of Akai's complete sampler
or a measured match to its hardware. Reference: [S1000 operator's manual,
page 54](https://manualzilla.com/doc/7360051/akai-s1000-series-operator-s-manual).
DEPTH is bipolar:
zero leaves a static filter, positive opens it, negative closes it. MIX
zero is exact dry passthrough.

STEPS displays 1–64; PULSE displays 0–64 and is limited internally to STEPS.
STEPS, PULSE and ROT use the full dial arc without changing their stored
values or encoder increments.
ROT shifts both the rhythm and captured random values right. RATE offers
1/32, 1/16, 1/8, 1/4 and 1/2 relative to track speed: 1/16 is one track
step. Changing RATE joins the next point on the new grid.

The output selector names itself ENV, GATE, RAND or LOOP:

- **ENV:** each pulse retriggers an attack and curved decay. ATK ranges
  from immediate to one step; DEC reaches eight steps and continues across
  rests until it finishes or another pulse retriggers it. DEC's lower half
  retains its original short range, reaching one step at 63; its upper half
  extends to eight steps at 127. Both use curved control ranges.
- **GATE:** each pulse opens the filter for LEN, from 1/128 to one step.
  EDGE smooths the opening and closing, limited to half the gate length.
  This is a cutoff gate, not an audio mute.
- **RAND:** each pulse chooses a new modulation level and holds it until
  the next pulse. SLEW controls the transition, up to one step.
- **LOOP:** freezes the last random value heard at each Euclidean step.
  Values repeat over STEPS and move with ROT. Switching back to RAND
  resumes generation. Unvisited positions contain seeded values, so LOOP
  also works before a full random cycle has played.

Zero pulses and STOP return to the base cutoff. Captured values survive
transport restarts, but are runtime state: they are not saved in a project
and are cleared when the effect is removed or the unit is restarted.

Swing uses the track's swing mask and amount (including changes made with
Swing All). Rotation and odd Euclidean lengths do not rotate that grid.
The 1/32 subdivision interpolates the surrounding track-step swing offsets.

## Implementation

`control.c` is an integer control engine compiled into the checked-in
`control.s` using `generate_control.py` (m68k-elf GCC 16.2.0). `hooks.s`
publishes cutoff after the stock scene and LFO writes at `0x4000d562`.
Hooking the earlier record writer is insufficient: later stock processing
overwrites its result. Two PLAY hooks reset the shared phase at the stock
transport anchor. The clock uses the firmware's musical position, rather
than accumulating an independent BPM oscillator.

`filter.asm` uses Spectrum's TPT state-variable filter equations, followed
by a TPT one-pole stage on the LP tap. Its two stereo states and coefficient
ramp remain inside the existing initialized 64-word private state block.
The additional coefficient table is generated locally, with no dependency
on the stock FILTER effect. Cutoff
ramps per sample; both the damping coefficient and reciprocal denominator
follow the ramp. Holding the denominator at the destination caused large
transients on full-range closing jumps and is covered by a regression.
All DSP state is initialized and private to the instance; no audio buffers
are allocated. The ColdFire runtime occupies about 5 KiB within the
platform's standard 10 MiB DRAM reserve.

Build and verify with `make check REMIX=euclid OT_PROJECT=`. For Euclid's
full playback test, then run `python3 tools/verify/verify_euclid.py --project
/path/to/project`. It copies the project into `out/euclid/` and uses a
generated tone. No Euclid test writes to the source project or hardware.
The separate generic set gate expects a suitable set with its own samples;
it is skipped by the empty `OT_PROJECT` above. After changing C or hooks,
run `python3 modules/euclid/generate_control.py`.

## Evidence and limits

Measured in the native engine and ColdFire emulator: every steps/pulses
combination, seven track speeds, five rates, three swing amounts, custom
swing masks, odd-length cycles, rotation, clock wrap (including the longest
attack-plus-decay), all output shapes,
captured-random replay, both transport hooks, all sixteen instances and
both outgoing parameter buffers. Compiled ColdFire traces for both slots
on tracks 1 and 8 match the native engine exactly while all sixteen
instances run. Other parameters and caller registers remain intact.
The real stock dial renderer is exercised across every legal STEPS, PULSE
and ROT value: the arc reaches its end, numeric labels keep their original
values, and unrelated dials retain their original drawing.
The shipping FX2 list must include all three stock reverbs, independently of
the remix's declared list; their DSP code and dispatch are compared with the
original firmware on both cores.

Measured through both real DSP payloads: dry passthrough, LP/BP/HP DC
responses, 18.54 dB/octave low-pass rejection in the tested
band, and a maximum 0.070 dB deviation from the third-order Butterworth
target at half, equal and twice three tested cutoffs with RES=0.
Also measured: silence from dirty instance memory and bounded full-range cutoff
jumps at three resonance settings. Full firmware playback verifies that
Euclid is the final cutoff writer and produces audible pulses on a steady
tone through a live 120→90 BPM change.

Static pricing is 196 DSP cycles per sample per instance, or 1568 for eight
instances on one core. This excludes memory contention and ColdFire work;
it is not a hardware load measurement. The CF probe also reports its peak
instruction count. Hardware timing, external MIDI-clock jitter, UI redraw
order and a full-load burn test remain unmeasured. The current revision has
not been flashed by these tools.

The 109 LP revision adds 43 program words and 33 table words over 107.
BP/HP were bit-identical to 107 in stereo noise probes at cutoff/resonance
pairs 0/0, 64/64 and 127/127 on payload A. The response and transient gates
run on both payloads. S1000 hardware matching remains unmeasured.
