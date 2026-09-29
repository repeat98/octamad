# `cfmeter` — the ColdFire's spare time with SYNTH MACHINE running

`octatrick-usb` (SYNTH MACHINE, SCALE QUANTIZER, DIRECT JUMP, USB MIDI, USB
AUDIO, the stock effects) plus [CF METER](../../../modules/cfmeter/README.md)
and [CF METER IDLE](../../../modules/cfmeter-idle/README.md). DARK REV is off
the chooser: its DSP words hold the readout insert. The readout comes over
USB AUDIO, T8 on channels 15/16 (post-FX, pre-fader, so LEVEL and MAIN do
not matter).

## Status

Not flashed. `OT_PROJECT=<dir> make check REMIX=cfmeter` passes every
gate since 28 Sep 2026 (the port follows the idle loop's detour,
[CF METER IDLE](../../../modules/cfmeter-idle/README.md)); `cfmeter-port`,
the same selection without the loop, is the variant that passed before.

## Procedure

1. `make image REMIX=cfmeter BUILD=N`, flash, power-cycle.
2. A new project. Copy a silent 4 s WAV named `SYNTH.wav` to the set's
   audio pool and load it into FLEX slot 1.
3. T8: FX2 = **CF Meter** (T8's audio is replaced by the readout; its
   machine still runs). BURN (FX2 page 1, first knob) at 0.
4. USB to the Mac. Each state below: `tools/rec 12 <name>.wav Octatrack`,
   then `python3 tools/harness/cfmeter.py <name>.wav`.

| take | state |
|---|---|
| `idle` | transport stopped, nothing assigned |
| `play` | transport running, all tracks stock, no trigs |
| `synthN-v1` | N = 1…8 tracks: FLEX, slot 1 (SYNTH.wav), a trig on every step, VOIC 1 |
| `synth8-v4` | 8 tracks, VOIC 4, CHRD OCT3 (four voices per track) |
| `burnB` | the `synth8-v1` state, BURN = 20, 40, 60, … until the unit misbehaves (note the value and what happened) |

Put BURN back to 0 before saving or switching projects: it is stored in
the Part like any knob. A freeze at a high BURN is cleared by a
power-cycle.

The period column should read 362.8 µs; if it does not, DTIM3 is not at
132 MHz and every µs figure scales by 362.8 / period.
