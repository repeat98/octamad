# OXIDE

Tape, modelled on UADx Oxide Tape Recorder at 15 IPS / NAB / Repro: how it
takes headroom, how it saturates, the head bump. Wow, flutter and hiss are
left out on purpose. Written for the master; until the OS has a post-mix
insert point it is an ordinary stereo insert on any track (no bus, no
buffers).

| page 1 | IN · OUT |
|---|---|
| IN | drive into the tape, 0.3 dB a step, 48 = 0 dB (the plugin at its default): 0 = -14.4 dB, 127 = +23.7 dB |
| OUT | output, 0.3 dB a step, 80 = 0 dB: 0 = -24 dB, 127 = +14.1 dB |

## The model

A Wiener-Hammerstein fit: a filter, a static curve, a filter
(`design.py` holds every number; `fit/` the tooling, which needs the plugin
installed).

- **Before the curve**: a 5.3 Hz high-pass and a +20.3 dB low shelf
  (5.3 Hz pole, 55 Hz zero). The bass reaches the curve up to +8.5 dB hotter
  at 20 Hz than the mids, which is why a kick saturates first.
- **The curve**: odd, linear to about half scale, flat at 0.909 of full
  scale above |u| ≈ 1.75. At IN 48 a 1 kHz tone is 1 dB compressed at
  -1.7 dBFS; 40 Hz at -6 dBFS; 5 kHz at -0.1 dBFS.
- **After the curve**: a -21.3 dB low shelf at 13.3 Hz, Q 0.72 (with the
  pre shelf it makes the +4.7 dB head bump at 30 Hz and the roll-off below
  it), a +2.1 dB high shelf, and a first-order all-pass at 52.9 Hz with the
  polarity flipped: the plugin's low-frequency phase, which is what sets a
  kick's peaks at the output.

### Measured (against the plugin, 28-29 Sep 2026)

- The plugin, hosted headlessly (`pedalboard`, noise reduction on so
  silence renders exact zeros): stepped sines 2 Hz-21.5 kHz at -30/-40 dBFS
  agree with a 2^19-sample impulse response to 0.15 dB / 0.3 deg; the
  response is linear there (-30 vs -40 dBFS: 0.07 dB, 0.0 deg).
- The split between the two filters, from the gain-vs-level curves at 72
  frequencies (5 Hz-20 kHz): fits to 0.02-0.06 dB RMS per frequency.
- Where each filter sits relative to the curve, from the phases of the 3rd
  and 5th harmonics with the measured linear phase removed: the pre filter
  above fits them to 0.5 / 0.3 deg RMS (worst 2 deg); with the 52.9 Hz
  all-pass before the curve instead, 50 deg.
- The 52.9 Hz all-pass is present under CCIR too (+87 vs +88 deg at 50
  Hz): it is not the NAB 3180 us term (that hypothesis was tested and is
  retracted).
- The float model (`design.reference()`) against the plugin: band levels
  within 0.24 dB and peaks within 0.7 dB on a synthetic drum bus and pink
  noise at -24 .. +6 dBFS; sine gain within 0.5 dB up to 0 dBFS (4 kHz at
  +6 dBFS: -0.9 dB, the one place the compact pre filter shows); two-tone
  (100 Hz + 8 kHz) intermodulation within 0.2 dB. Below 4 kHz the waveform
  nulls against the plugin to -21 .. -33 dB.

### Not modelled

- The plugin's 5.6 kHz all-pass and ~2 samples of latency (phase only;
  above 4 kHz the waveform does not null, the levels do).
- 7.5 IPS (1.2 dB earlier compression, roll-off above 10 kHz), CCIR (a
  larger top lift), hiss, wow and flutter.

## The DSP

`oxide.asm`, per channel: two first-order sections, the curve (a 33-point
table, 32 segments, linear between), a TPT state-variable low shelf, two
first-order sections, the output gain. Every stage is first-order or a
state-variable filter because the poles sit at 5, 13 and 53 Hz, where a
24-bit direct-form biquad cannot place them. Every recursive section ends
in `macr`/`mpyr`: with truncating moves the -1/2 LSB bias through the 5 Hz
poles put a -51 dB DC offset on the curve's input and -70 dBFS of DC on
the output (found by the gate's float-model residual, fixed before it
shipped anywhere).

The sixteen multipliers a channel uses sit in a ring in the instance block
(`r7+$20`), walked modulo 16 and loaded as the parallel move of the
multiply before each use; fourteen are copied from the P table's tail by
the first proc after init, IN and OUT are rewritten every block.

| | words | per stereo sample |
|---|---|---|
| code | 157 | |
| P table (curve, IN, OUT, ring) | 114 | |
| `dsp_host` meter, worst block | | 158 instructions |
| `cycle_count.py` | | 164 cycles (4 on one core: 656 of 3,120) |

(The first version, coefficients as long immediates: 189 / 226.)

The 24-bit engine against the float model: -93 dB residual on drums and
noise at 0 dBFS, -82 dB at -12 dBFS; a level-independent floor of about
-101 dBFS RMS on broadband input, mostly 20-200 Hz (-110 dBFS on a 1 kHz
tone). Silence renders exact zeros. The plugin's own hiss, noise reduction
off, is -88 dBFS.

The gate (`tools/verify/verify_oxide.py`, in `make verify`) holds the
emulator's render to `design.fixed()`, the asm replayed on integers, at 0
LSB: 15 stereo renders (different material per channel, five knob
settings, 16-frame blocks). It also checks the ring order against the
design and every instruction by disassembly.

- `dsp_asm` drops XY parallel moves beside an ALU op and emits the `su`
  form, even for the stock mixdown's own encoding (measured 29 Sep 2026;
  `docs/firmware/DSP.md` §8 said the right register split was enough). The
  code uses no parallel moves.
- Signed-safe multiply operand orders in this `dsp_asm` (measured, both
  `mpy` and `mac`): `x0,y1` `y1,x1` `x1,y0` `y0,x0` `x1,x0` `y1,y0`.

## Open

- A post-mix insert point: the mixdown's end, `P:0x2d5` on payload A
  (`docs/firmware/COLDFIRE_PORT.md`), not yet disassembled or hooked.
- Not on hardware. Not priced in a rig.
