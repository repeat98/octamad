# Borrowed voicings: sources, laws, licences

The published algorithms the stations' modes are derived from. What is
borrowed is the curve or the law, re-derived under the gates; the source
code never runs here. Character and Spectrum (13 Sep 2026):
[JClones/JSFXClones](https://github.com/JClones/JSFXClones) (MIT; console,
tape and tube processors) and [audiojs/filter](https://github.com/audiojs/filter)
(MIT; ZDF ladders and SVFs, a formant bank, resonators, tilt). Modulation
(14 Sep 2026): the licence map below. Word and cycle figures marked "est"
are estimates from reading; the "Built" tables are measured.

## The rules that shape a port (the 56300 side)

- No per-sample division, log, exp, tan or tanh: each becomes a P-table
  (33 pairs interpolated, as Character's tables are) or moves to the
  per-block path, which has one real division.
- A sample-loop callee may contain no control transfer; forward skips in the
  loop body are priced as the worst path (`CYCLES_FORWARD_BRANCHES`).
- Lookahead needs delay memory an FX1 station has not got: limiters and
  maximizers are out.
- 2x oversampling doubles the cycle price. Nothing chosen below needs it.
- A stepped select cannot sit on page 1 (the schema refuses it): a
  page-1 control is a knob.

## CHARACTER from JSFXClones

Reference: today's saturator ≈ 170 words both channels, the compressor
≈ 150, 458 cycles/sample worst (before the TapeHead stage).

| stage | source | the law | port | cost (est) |
|---|---|---|---|---|
| **TAPE** | TapeHead | Chamberlin SVF at 2.1 / 3.7 / 5 kHz; `ss(v) = 1.5v − 0.5v³` clipped ±1 on the LP and BP bands, the HP band passed at −1.157; drive 0.8x..8x = `0.8·10^((D−1)/9)`; trim 0.7 | done 13 Sep: MODEFORK, TONE (page-1 slot 5, plain knob) sweeps the split 2.1→5 kHz, `k2` linear in TONE (0.5 % from the sine); error vs the float reference ≤ 7e-3 (2e-2 on noise at DRV 127, the drive table's interpolation) | −60 words |
| **TUBE** | DaTube | `x *= drive+0.5`; `y = x + (d/2)((1−x) − (1−x)^P)` for x>0, `x + d((1+x)^P − (1+x))` for x<0, P = ln10+1; 3 Hz DC remover | one table `T(u) = u − u^P`, sign selects d/2 vs d | +20 words |
| **INFL** (SAT's third slot; FUZZ dropped) | OInflator | `x *= 0.5`; `gr = clamp(2c·|x| + (1−c))`, `y = (1 − |gr·x|)(gr·x)·2e + (1−e)x`; ×2 | no table, no division; Effect on DRV | +50 words |
| **GLUE** | AC1 | level = |x| smoothed 0.5 ms / 500 ms; `gr = (Lv²/2 − 1)² + Lv·a`, `a = 0.75 − (Comp−1)·0.075`, clamp ≤ 1 | polynomial gain per sample, no table | −40 words |
| **COMP** | LMC1 | feedback console comp: sidechain HP 340 Hz → LP 4 kHz → ×gr → square → 2.5 / 25 ms smoother → √; hard knee, `gr = (L/thr)^−3.077` (≈4:1), −40 dB floor | the power per block: one division + a 33-entry table of r^−1.538 | +60 words |
| TRNS | ours | on trial (Sam) | | |

Blockers: TubeDriver (`t/(t+bias)`, a division per sample); the full SatBuss
(13 one-poles and a feedback mesh, ≈ +130 cycles); a reduced SatBuss
(the √2 squarer + the rational soft clip as a table + an 8 Hz DC block,
≈ +40 words) keeps its harmonic signature without the bloom, if ever wanted.
Net for TAPE + TUBE + INFL + GLUE: ≈ −55 words, ≈ +30 cycles/sample against
today's Character; + COMP ≈ +5 words.

## SPECTRUM from audiojs/filter

Reference: today's SVF core ≈ 13 words/channel, `f` capped at 0.977 (a
~7.2 kHz cutoff ceiling if `f = 2 sin(π fc/fs)` — inferred, not measured on
the unit); 322 cycles/sample, 861 words.

| candidate | the law | port | cost (est) | gives |
|---|---|---|---|---|
| **Oberheim SEM ZDF SVF** (linear) | per block `g = tan(π fc/fs)`, `R = 1 − res`, `d = 1/(1 + 2Rg + g²)`; per sample `hp = (x − (2R+g)s0 − s1)·d`, `bp = g·hp + s0`, `s0 = bp + g·hp`, `lp = g·bp + s1`, `s1 = lp + g·bp`; notch = hp + lp | replaces the SVF core one for one, same taps, MODE / mix / FM unchanged (FM as an offset on `g` with `d` frozen per block) | +8 words, +6 cycles | no cutoff ceiling, stable at any RES, resonance tracks fc, self-oscillation without the clamp |
| … with the state tanh | `s0 = tanh(s0)`, `s1 = tanh(s1)` | two lookups per channel + one 33-pair table | +120 words, +70 cycles | the SEM warmth: a bounded, warm resonance instead of a limiter clamp |
| **Formant bank** for VOWL | three parallel constant-peak resonators `y = b0 x + b2 x2 − a1 y1 − a2 y2`, `R = e^(−π bw/fs)`, `a1 = −2R cos w0`, `a2 = R²`, `b0 = (1−R²)/2`; /a/ = 730/1090/2440 Hz, bw 90/110/170, gains 1/0.5/0.3 | replaces the two-peak trick; 5 vowels × 3 formants × (a1, a2, b0) = 45 words of table with the existing FREQ morph; RES scales the bandwidths | +80 words, +40 cycles | named vowels with real F1/F2/F3; DRV/FM/ROUT keep meaning in VOWL |
| per-sample `f` ramp | `f += (fA_new − fA_old)/16` per sample | | +3 words, +2 cycles | removes the block-rate zipper on a fast sweep (measure it first: a CC 34 sweep, soloed, look for the ~2.8 kHz comb) |
| 2-shelf TILT on the blank slot 4 | two one-pole shelves at 250 Hz and 2.5 kHz, ± slope | | +20 words, +12 cycles | a tone knob; only if BASE/WDTH do not already cover it |
| Moog ladder as a MODE | ZDF 4-pole, `G = g/(1+g)`, `u = (x − k·S)·d`, `u = tanh(u·drive)`, four trapezoidal stages | +150 words, +70..90 cycles | 24 dB/oct, the Moog resonance, true self-oscillation | **blocked** at four Spectrums per core (+300 cycles against 194 headroom) unless it replaces the SVF or a ladder-mode Spectrum counts as heavy |
| diode ladder (303) | four state tanh + two tridiagonal solves per sample | ≈ +200 cycles | | **blocked** |
| 8-stage tilt | | +50 cycles | | blocked at four per core |
| Korg35, lone resonator, RBJ core | | | | low value; skip |

Net for the linear SEM + the formant bank + the ramp: ≈ +90 words,
+50 cycles/sample per Spectrum — four per core is +200, over the pricer's
194 headroom on the worst core, so the set waits on the pricer's
bsr-in-fork attribution fix and a re-price; the linear SEM alone is
affordable now.

## Built, 13 Sep 2026 late (image 98, unflashed at the time of writing)

| stage | result |
|---|---|
| Character TAPE / TUBE / INFL | TapeHead / DaTube / OInflator; FUZZ and TRNS retired; TONE (page-1 slot 5) sweeps the tape split; references matched to ≤ 7e-3 / 2e-3 / 1.4e-3 |
| Character GLUE / COMP | AC1's law, 0.5/500 ms and 0.5/50 ms; COMP 40 = +0.96 dB; LMC1 built, +125 words over, kept as a draft |
| Character total | 1,170 words, 466 cycles/sample (the pricer's bsr-in-fork attribution fixed the same evening: 685 reported before) |
| Modulation | PHSR, TREM, VIB, PAN retired (the OT's LFOs do trem/pan): CHOR / FLNG / COMB, 767 words, 386 cycles |
| Spectrum | SEM ZDF core (no cutoff ceiling, RES 127 bounded, Q ≈ 34), per-sample cutoff ramp (block comb −11..−26 dB), three-formant VOWL (Peterson & Barney): 1,141 words, 462 cycles |
| the rig | core A FREE 283, core B 385; worst core 3,654, headroom +234; every gate green |

Not yet: heard on the unit (the live rounds), the LMC1 COMP, the Moog ladder.

## MODULATION from the chorus / flanger / phaser canon (14 Sep 2026)

Budget as it stands on origin/main (14 Sep): Modulation 453 words /
277 cycles; core A FREE 1,282 (1,735 with today's Modulation removed),
core B 1,744; the worst core is 4 × Character at 639, headroom 57, so a
Modulation up to 639 cycles does not move the line. A track's line is
2 × 1,024 words (23 ms per channel).

### Licence map

| source | licence | use |
|---|---|---|
| Airwindows (Chorus, ChorusEnsemble, StereoChorus, Vibrato, GalacticVibe, Flutter2, Ensemble) | MIT | code |
| jpcima `string-machine` (Solina tri-chorus + Holters-Parker BBD), `bbd-delay-experimental`, `ensemble-chorus` | BSL-1.0 | code |
| jpcima `rc-effect-playground` / Hera `HeraChorus.dsp`, `bbd_line.h` (Juno-60 chorus) | ISC (file-level) | code |
| Mutable Instruments Rings `chorus.h`, `ensemble.h` | MIT | code |
| ChowDSP ChowPhaser (Schulte Compact Phasing A) | BSD-3 | code |
| Faust `phaflangers.lib` `phaser2`, `flanger_mono` (J.O. Smith) | STK-4.3 (MIT-style) | code |
| Dattorro, Effect Design Part 2, JAES 1997 | paper | laws (Tables 6/7, the white chorus) |
| pendragon-andyh Juno-60 measurements | data | laws |
| TAL-NoiseMaker chorus, Surge XT chorus/Ensemble, JunoX, chowdsp BBD | GPL | laws only |
| Rakarrack/guitarix Vibe, BYOD Solo-Vibe, Zyn APhaser | GPL | laws only |

Not found anywhere permissive: a Uni-Vibe, a Dimension D clone, a
through-zero flanger plugin, an Airwindows Flanger or Phaser (the 2007
pages are Kagi-era AU with no source).

### The candidates

| candidate | source | the law | delay (samples at 44.1 k) | cost est. per stereo sample |
|---|---|---|---|---|
| **JUNO** | Juno-60 measured (pendragon-andyh) + jpcima ISC | two BBD lines, ONE triangle LFO, R's inverted; I = 0.513 Hz, II = 0.863 Hz, sweep 1.54→5.15 ms (L) / 1.51→5.40 (R); I+II = 9.75 Hz, 3.22→3.56 ms, mono; dry 0.83 + wet 1.0; BBD +2.3 dB; in/out filters ≈ 9.9 / 9.5 kHz 5th-order (one-pole proxies in the practical ports: 7.2 k in, 10.6 k out) | 67..238 | ≈ 35 (one-pole proxies), ≈ 60 (biquads) |
| **DIM** | SDD-320 service notes + measurements (Synthbuilder, Fractal) | two lines on one triangle LFO in ANTIPHASE (motionless: the mean delay is constant); 0.25 Hz (modes 1/2) / 0.5 Hz (3/4); sweep 5→12, 5→10, 6→9 ms; each output = bass-boosted dry + a little same-side wet + the OTHER side's wet through a HPF, inverted; mode 4 raises same-side | 221..529 | ≈ 50; the mix and HPF constants are unpublished (ours to voice) |
| **ENS** | jpcima string-machine (BSL) / Rings ensemble (MIT) / Haible | Solina: three taps on ONE mono line, two 3-phase sine LFOs summed, 0.6 Hz × 0.5 + 6 Hz × 0.05..0.1; 5 ± 1 ms (TCA350, 185 stages); L = t1 + t2 − t3, R = t1 − t2 − t3; 12 kHz 2nd-order input LP | 176..265 | ≈ 45 |
| **FLNG** | Dattorro Table 6/7 + Faust `flanger_mono` | blend = feedforward = 0.7071, feedback −0.7071 (max trough); delay 0→10 ms, the strong zone the first 1 ms; L/R the SAME phase; through-zero = the dry read from a FIXED tap at the sweep's centre, the wet inverted, so the sweep crosses it (McCurdy) | ≤ 441 + centre | ≈ 25 |
| **WHITE** (a CHOR variant) | Dattorro Fig. 36 | feedforward 1.0, blend = feedback = 0.7071, the feedback tapped at the FIXED centre (never the moving tap: modulated feedback pitch-shifts), so the chorus is an allpass at the centre; centre 400, width 350, 0.15 Hz, quadrature L/R | 50..750 | ≈ 25 |
| **PHSR** | ChowPhaser BSD-3 | Schulte: one feedback biquad (two RC allpasses collapsed, C 15 nF, fb ≤ 0.95, three tanh) then N first-order allpasses on one shared coefficient (C 25 nF), 3 MAC a stage; LDR: light = 20.1 − 20·lfo, R = 100 k·(light/0.1)^−0.75 → the whole coefficient set is a P-table on the LFO word; sine LFO 0..16 Hz, skew `2^s` | none | ≈ 100..130 at 8 stages (the R→coefficient chain block-rate, tabled) |
| PHSR alt. | Faust `phaser2` STK | 4 second-order allpasses, notch k at `fratio^(k+1)·θ`, R = e^(−π·width/fs), fb ±0.999, quadrature L/R; the cos per stage a table | none | ≈ 100..120 |
| **VIBE** | Uni-Vibe (laws only: Rakarrack/guitarix, BYOD, Keen) | four stages, C = 0.015 µ / 0.22 µ / 470 p / 0.0047 µ; LDR 500 kΩ dark → 600 Ω lit through a lamp one-pole (10 ms) and a cell with asymmetric TC (85 ms dark, 5 ms lit); BJT shaper per stage | none | ≈ 160..250; no permissive code, every constant ours |
| **VIB** | Airwindows StereoChorus / GalacticVibe MIT | quadrature dual vibrato; GalacticVibe: fixed 0..254 samples, a NEW random rate each LFO cycle (0.43..0.70 × drift), Leslie-like; StereoChorus: depth ∝ 1/speed so every setting feels equally intense, L/R 1.98 rad apart | 257 | ≈ 35 |
| **FLUT** | Airwindows Flutter2 MIT | independent L/R LFOs, a random rate 0.24..0.98 × per cycle; depth ≤ 90 ± 90 samples; "reel-to-reel to cassette to VHS" | ≤ 182 | ≈ 45 |
| COMB | ours | DLY the pitch, FDBK the ring (Sam: "works, sounds good", 12 Sep) | | today's |

Not portable: Airwindows Ensemble (2..48 taps each with its own sine, ≈ 30
a tap), TakeCare (18 lines ≥ 4,626 words), StereoEnsemble (7,523-sample
lines); the full Holters-Parker BBD (≈ 100..150 a line a channel, five
complex poles a side) — the proxy every practical port uses is a one-pole
or a biquad each side of the line plus a soft clip, ≤ 15 a line.

### Interpolation

- Airwindows: a 3-point read (weights 1−f, 1, f, × 0.5, minus 1/50 of
  the second difference) preceded by an "air" pre-emphasis (3 mul, 8 add
  a channel) that puts back the highs the averaging takes. Chris: "the
  moving part [is] totally fluid, analog-like".
- Dattorro: "all-pass interpolation for delay modulation becomes critical
  to the transparency of any chorus"; linear = a time-varying lowpass.
  THD+N: linear −78..−88 dB, warped allpass −77..−85, unwarped −53..−59.
  TAL uses the first-order allpass interpolation.
- Ours: linear, blended toward the OLDER sample since 12 Sep (the crackle
  fix). A chorus that reads darker at the sweep's extremes is the linear
  interpolation; the BBD proxy filter hides it, the air/allpass reads fix it.

### The pedal's surface

Page 1 the performance surface, page 2 knob / select / knob / select:

| page 1 | RATE · DPTH · FDBK · MIX · TONE · WDTH |
|---|---|
| page 2 | DLY · MODE · — · — · — · — |

- **RATE / DPTH** keep today's laws (RATE squared 0.05..8 Hz); a mode's
  ModeView re-defaults them to its source's numbers (JUNO 0.513 Hz and
  the Juno's depth; DIM 0.25 Hz; ENS 0.6 Hz; FLNG 0.15 Hz).
- **FDBK** bipolar: negative = Dattorro's white chorus / the flanger's
  inverted regen; in PHSR the Schulte feedback; in COMB the ring.
- **TONE** the BBD proxy: the in/out one-pole corner, 64 = the Juno's,
  down = darker (the CE-2's 6.6 kHz, TAL's 2 kHz), up = open.
- **WDTH** the L/R LFO relationship: 0 = mono (the Juno I+II, the
  flanger), 64 = the source's (Juno antiphase, Dattorro quadrature,
  Dimension antiphase), 127 = beyond.
- **DLY** the centre (Dattorro: "manual" on a flanger pedal); in COMB the
  pitch.
- **MODE** JUNO · DIM · ENS · FLNG · PHSR · COMB (six positions, the
  select's maximum). VIBE is out: no permissive code, every constant
  unproven.
- Each mode is proven against a float transcription of its source
  (`modules/modulation/<source>_ref.py`, the Capacitor2/Pockey pattern);
  the Juno and Solina against the measured delay ranges and rates.

Cost: the dearest mode sets the price; PHSR ≈ 130 +
the LFO and mix ≈ 200, else ENS ≈ 60 + ≈ 130 — both under today's 277.
Words: two lines of 1,024 as today; ENS shares one line (mono in), DIM
and JUNO use both. Estimate ≈ 700..900 words with six modes and the
reference tables in X.

### Built, 14 Sep 2026 (branch modulation-v2, unflashed)

| | measured |
|---|---|
| modes | JUNO · DIM · FLNG · COMB · PHSR since 16 Sep 2026 (ENS heard and dropped: the 6 Hz LFO "super unnatural", jpcima's own render judged the same; PHSR kept, "pretty good"); built 14 Sep as JUNO · DIM · ENS · FLNG · COMB · PHSR; PHSR was pending Sam's call (retired 13 Sep at 464 cycles; ChowPhaser's law prices 476 with the LFO, the ramps and the mix, under Character's 639 so the worst core is unchanged) |
| words | 1,199 (v1 453); core A FREE 536, B 998; 132 words of tables in X |
| cycles/sample | LINE (JUNO/DIM/FLNG) 446, PHSR 525, COMB 359 with LOFI (401 / 476 / 314 before; ENS was 440) |
| proof | `modules/modulation/modulation_ref.py` — one float class per mode, the source's per-sample law with the station's knob decode; `tools/verify/verify_modulation.py` 24 gates green: every mode ≤ 1e-4 max error on a stereo signal (COMB 5.5e-4: its ring recirculates the Q23 rounding), the Juno's sweep 1.56..5.10 ms at 0.5 Hz, the through-zero null −138 dB, the phaser unity, the comb's period at three pitches |
| estimate vs built | the words estimate (700..900) was low by 300: the phaser's unrolled tap weighting is ~180 words per channel pair, the Hermite read 90; the cycle estimate (≈ 200) was low by 270: the LFO shaping (the parabola sine is 17 instructions a call, six calls in ENS) and the one-poles are the difference |
| departures from the sources | DIM's amounts (ours); PHSR's feedback through one sample, no tanh, the coefficient per block + ramp; COMB without the IIR damping and dispersion, with a polarity sign; the Juno's L/R asymmetry and its I+II "sine-like" shape not modelled; the tap read linear (the sources' allpass / 3-point + air reads are open) |
| heard | 16 Sep 2026 on the emulator: JUNO/DIM/PHSR good, FLNG good at RATE 8, COMB kept, ENS dropped; LOFI knob added the same day (page-2 slot 8: hold + bit mask at the line write, Sam's pick over the wet-only placement); per-mode output trims DIM −8 / FLNG −7 / PHSR −2 / COMB −12 dB (`modules/modulation/README.md`); unheard on the unit |
