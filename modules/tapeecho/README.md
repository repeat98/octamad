# `tapeecho` — TAPE ECHO

A mono single-head tape echo on the ColdFire CPU, in place of FX2 SPRING REV.

`TAPE ECHO` replaces FX2 **SPRING REV**. It is a mono single-head tape echo
with stereo dry output, running on the **ColdFire CPU**, in the stock
delay's four-second per-track ring. The DSP side is an empty passthrough
(one NOP per sample for the generic insert cycle gate) and allocates no tape buffer.
DJ-Mixer's `fx-dsp/core/src/blocks/TapeEchoBlock.cpp` is the behavioural
reference for voicing. Its multi-head geometry and physical-cell
variable-speed write model are not copied. This CPU version uses
a fractional moving read head.

The economy model keeps one record head and one playback head. DRIVE is
fixed at 0, the owner's preferred setting. The CPU voice keeps the
FX-pedal's Galaxy-measured feedback law, record saturation, time-dependent
bandwidth and tape-age loss/noise. Two biquads and a `[1,6,1]/8` record FIR
replace the former four biquads: playback low cut plus a combined TIME/AGE
low-pass, fitted offline to the previous response. The opposed emphasis
EQs, low-mid lift and steep record top are omitted; the extreme top-end
slope is less steep. Two inexpensive oscillators supply wow and randomized flutter;
there is no transport-history integration, capstan harmonic or drift model.

FREE uses one bounded slew calculation per 16-sample block and linearly
interpolates the read position. BEAT snaps to a note target and crossfades reads for 512 samples
(11.6 ms), without clearing feedback history or resetting gain/oscillators.
Rapid changes are coalesced: the latest target settles within 1024 samples
(23.2 ms) after the last edit. Two reads exist only during a transition,
not as multiple audible echo heads. Wow-offset acceleration is limited
after a snapped delay change to avoid briefly sweeping the old offset in
a single 16-sample block.

## Knobs

The first page follows the stock Delay pattern: performance controls stay on
the normal FX page, with MIX in the final bottom-right position. Character
controls, including AGE, are on that same page; the detail page is disabled.

| page | slot | name | range | what it does |
|---|---|---|---|---|
| 1 | 0 | TIME | 0–127 | 46-231 ms in FREE; musical divisions in BEAT |
| 1 | 1 | FDBK | 0–127 | Regeneration; the upper range safely grows tape noise into self-oscillation. |
| 1 | 2 | WOW | 0–127 | 0.8 Hz wow plus randomized flutter; 0 is static. 44/127 gives about 7.7 cents RMS. |
| 1 | 3 | AGE | 0–127 | Repeat bandwidth, flutter and hiss; fresh at 0, worn at 127. Former HEADS slot. |
| 1 | 4 | SYNC | FREE, BEAT | `FREE` continuous time, or `BEAT` tempo-quantised time. |
| 1 | 5 | MIX | 0–127 | Dry/wet crossfade; 0 is exact dry. |
| 2 | 6 | — | | Former DRIVE slot: disabled; the engine always uses DRIVE=0, including on saved parts. |
| 2 | 7 | — | | Former AGE slot: disabled; AGE now lives on page 1. |

In `BEAT`, TIME selects twelve divisions from `1/64` through dotted `1/4`
and displays their names (T = triplet, dot = dotted). In FREE it displays
milliseconds. The 128-value automation lane is retained: each BEAT band
maps to one exact target, not an interpolated value between notes.
The stock frame builder already publishes
tempo to `0x8000181c` as BPM x 24, so no tempo cave is required. Tape Echo
retains the last valid tempo if that word is briefly absent. All twelve
divisions fit at 30–300 BPM; the longest is three seconds at 30 BPM, leaving
room for wow and interpolation. The previous DSP version's 249 ms cap is gone.

| TIME values in BEAT | Division |
| --- | --- |
| 0–10 | 1/64 |
| 11–21 | 1/32 triplet |
| 22–31 | 1/32 |
| 32–42 | 1/16 triplet |
| 43–53 | 1/16 |
| 54–63 | 1/8 triplet |
| 64–74 | dotted 1/16 |
| 75–85 | 1/8 |
| 86–95 | 1/4 triplet |
| 96–106 | dotted 1/8 |
| 107–117 | 1/4 |
| 118–127 | dotted 1/4 |

FDBK/WOW/SYNC/MIX retain their existing slots. AGE moves from detail slot 7
to page-1 slot 3. Existing HEADS values/locks in that slot now mean AGE:
they must be reset/remapped when migrating a project. Old detail-page AGE
and DRIVE bytes are ignored. BEAT keeps OCTACLID3's twelve-band mapping.
Use a fresh test project, or back up and stamp/reset old effect defaults
before playback; default stamping does not remove obsolete parameter locks.
No automatic project migration is performed.

## Measured

Local native renders and execution of the compiled ColdFire engine under
the port's instruction meter; no hardware capture. The dated log of every
voicing and optimisation round (19–23 Sep 2026, OCTACLID3/4/5, the
multi-head and DRIVE=51 comparisons) is
`git show 666b6154:modules/tapeecho/VOICING.md`.

**Method.** The user's local DJ-Mixer `TapeEchoBlock.cpp` is the sonic
design reference, compiled directly for a 44.1 kHz native comparison; the
direct UADx Galaxy measurements at 48 kHz are DJ-Mixer's
`test/results/07-fx-tape-echo-galaxy-2026-09-11.md`. Galaxy was not
freshly rendered for the current voice. Response is steady sine RMS
relative to 1 kHz at -40 dBFS. WOW is pitch variation of a 3 kHz tone,
interpolated zero crossings over ten periods, first second discarded.
Noise buildup starts from silence. The numerical assertions are in
`tools/harness/tapeecho_voice_probe.cpp`. No proprietary plugin code,
samples or firmware bytes are included.

**Voice** (the economy voice, OCTACLID5, 20 Sep 2026; restored unchanged
on 21 Sep 2026 after six page-2 controls were removed):

- The 12 pedal frequency/AGE reference points (100 Hz, 4/8/10 kHz at AGE
  0/64/127) differ by up to 1.89 dB; the economy-model tolerance is 2 dB.
  Worn tape is darker around 4 kHz and brighter at 10 kHz; the tolerance
  is not a bound over every frequency/TIME setting.
- Feedback law `2.3 * (FDBK/127)^2.26`. Repeat decay at 1 kHz stays within
  0.38 dB of the historical Galaxy points (25/50/60/65/70 %).
- WOW=44 about 7.75 cents RMS.
- Noise after 20 seconds at FDBK=102: about -7.69 dBFS.
- Full-scale record compression about 1.64 dB.
- FREE/BEAT click residual 0.000443 FS; rapid FREE reversals 0.001070 FS.

**EMAC rewrite** (23 Sep 2026). The arithmetic is written the way stock's
delay loops (`0x40003664`, `0x40003734`) are; every EMAC form used has
sites in stock 1.40C. Three kernels:

- Reader (`te_read_linear`): a DDA replaces the per-sample phase and
  address rebuild; interpolation is stock's `a*(1-f) + b*f` accumulator
  form on raw ring words (the 1/4 operand scales Q1.31 to Q3.29), 8-bit
  fraction, 17 uncached loads per contiguous block.
- Filters (`te_filter_block`): both sections in one pass, each
  `g*(x +/- 2*x1 + x2) + y1 + (a1-1)*y1 + a2*y2` (RBJ low/high-pass
  numerators are exactly `b0*(1, +/-2, 1)`). The tone section's input
  history is the low cut's output history. `te_feedback` is Q2.30.
- Tape (`te_tape_block`): record sum, FIR, curve, stereo DMA staging and
  output mix in one pass. Full wet is `sat(4*wet)`, other MIX values
  `sat(4*mix*wet + (1-mix)*dry)`.

`te_tone` shrank 5 -> 3 columns; the runtime went from 169,144 to 110,648
bytes.

Executed instructions per complete eight-track 16-sample routine (same
stock firmware, synchronous DMA model, stereo tone, 1500 warm-up + 1000
measured blocks); not hardware cycles:

| Configuration | Instructions | vs stock |
| --- | ---: | ---: |
| Original stock DELAY x8 | 7,628.0 | 1.00x |
| Patched stock DELAY x8 | 7,900.0 | 1.04x |
| Tape x1 WOW=44 + stock x7 | 8,821.3 | 1.16x |
| Tape x3 settled WOW=44 + stock x5 | 10,667.5 | 1.40x |
| Tape x8, settled, WOW=0 | 14,244.5 | 1.87x |
| Tape x8, settled, WOW=44 | 15,283.3 | 2.00x |
| Tape x8, settled MIX=0 | 14,531.3 | 1.90x |
| Tape x8, moving FREE TIME, WOW=44 | 15,539.1 | 2.04x |
| Tape x8, changing BEAT TIME, WOW=44 | 16,329.0 | 2.14x |
| Tape x8, moving FREE TIME, MIX=90 | 16,459.1 | 2.16x |
| Tape x8, all controls moving | 20,257.0 | 2.66x |
| Tape x8, all controls moving, full history | 20,677.6 | 2.71x |

Before the rewrite (`f80f45e`) the same rows were 14–35 % higher (settled
WOW=44 21,989.5; moving FREE TIME MIX=90 25,271.0).

Parameter-edit stress (full synthetic history, peak of 1000 blocks):
settled MIX=90 16,248; TIME / FDBK / WOW / AGE / MIX reversals
16,270-17,776; SYNC reversals 19,624; all controls 18,063 in FREE and
21,547 in BEAT.

Per instance, settled WOW=44 full wet (MIX=90 moving TIME in brackets):
record/output 663 [778], both filters 401 [401], `te_process` 268 [284],
reader 221 [224], stock routine 203, `te_cpu_frame` 75, `render_head` 62,
hook 10, tone update 7 [20]. Inlining `te_process` into `te_cpu_frame`
was tried and rejected: 20 instructions per instance dearer.

Same sound before and after the rewrite, fed the same 5 s chord bursts:
residual -115 to -123 dBFS RMS, 86-103 dB below the signal, peak difference
-98 dBFS (FDBK=100). Frequency response, wow and pitch identical to the
printed precision; repeat decay and treble loss move by at most 0.003 dB.

The noise floor the gate measured before 23 Sep 2026 was mostly a DC
offset: the old engine's output carried a constant -120 dBFS offset
(truncation bias in its playback path). Its hiss was -128.90 / -123.56 /
-116.38 dB at AGE 0/64/127; the current engine's hiss is -128.80 / -123.49
/ -116.36 dB and its offset -147 dBFS. The gate measures the hiss without
DC and separately requires the offset below -130 dBFS.

The ColdFire kernels match the native oracle bit for bit: eight instances
over 2300 blocks (all controls, tempo, BEAT, full history, ring wrap), 1024
filter blocks with both read-outs saturated both ways, 1024 tape blocks
over all four output modes, 2048 plain and crossfading reader blocks with
uncached-load counts. Stock DELAY on the neighbouring tracks stays
bit-identical to 1.40C, which also shows every accumulator is left empty.
Kernel instruction ceilings: reader 165 fixed / 250 moving (+90 while
crossfading; measured 152/229, 232/309), filters 420 (401), tape 1000
(946, knob ramps).

Two character-changing trials were rejected after measurement (21 Sep
2026): a parabolic soft clip (about 1.1 % saved) and a fitted one-pole
playback high-pass (about 0.3 % saved, changed the low-frequency noise
floor).

## On the unit

- The first hardware load of an optimised image (before 21 Sep 2026)
  raised `Vec:03` at `te_read_linear`'s scaled-index ring read (`move.l
  (a1,d0.l*8),d5`): ColdFire raises an address error on scale factor
  eight, and the emulator accepted it. The reader forms the byte offset
  explicitly; generation rejects any `*8` memory address form.
- **Hardware freeze remains open:** OCTACLID4 reached six instances before
  freezing during edits; OCTACLID3 froze on TIME with three. Earlier images
  also froze on second-instance TIME changes and loading three instances.
  No exception screen was shown. OCTACLID5 targets eight instances with
  editing headroom and reduces measured work again; it is not yet a physical
  fix confirmation. The 21 Sep 2026 restoration removed six page-2 controls
  after hardware reports of poor UI responsiveness and ineffective SLEW.
- The EMAC rewrite (23 Sep 2026) is not flashed.

## Open

- CPU cost is not hardware-qualified. Eight instances are verified for
  correctness, not certified to meet deadlines alongside timestretch,
  recording and streaming. Emulator instruction counts are not hardware
  cycles: the port's meter prices an uncached SDRAM access at one cycle.
  The frame period is 363 µs, ~95,800 cycles at 264 MHz, shared with
  everything else the ColdFire runs; the hardware freezes (On the unit) are
  the only bracket on the routine's budget. The meter cannot see EMAC pipeline stalls, cache misses, RAM/bus
  contention or DMA stalls. The rewrite removed most back-to-back MAC ->
  MOVCLR pairs on one accumulator (stock never does this), so the hardware
  saving may be larger than the instruction saving; neither version is
  timed on the unit.
- Saturation semantics: overload behaviour depends on MOVCLR saturating
  under MACSR OMC, per the CFPRM pseudocode the emulator follows. Bounded
  tape content keeps every read-out inside +/-4 FS in normal use, so a chip
  that differed would change overload, not the voice.
- ACCEXT01 layout: fraction saving reads byte 0 of `ACCEXT01`/`ACCEXT23`
  as the low accumulator byte of acc0/acc2, the emulator's (QEMU-derived)
  fractional layout, not checked against the CFPRM figure. If the chip
  puts ACC0/ACC2 in the upper halves, fraction saving is inert on the
  unit, and the bit-identity gates cannot show it because both sides use
  the emulator's layout.
- The ring-seam block (once per four seconds per head) takes the C
  per-sample loop, about 18 instructions per sample instead of 12.
- Hardware listening, cache/bus timing, UI responsiveness and worst-case
  CPU load.

## Gates

`.venv/bin/python3 tools/verify/verify_tapeecho_cpu.py tapeecho` (the
manifest's gate, stage `image`) runs the CPU gate with the same native
architecture used by `make check`; `make check REMIX=tapeecho` includes it
and the loader boot. It
also measures parameter-edit spikes with full synthetic tape history and
all eight tracks active. Endpoint reversals run every 1, 16 and 64 blocks for
TIME, FDBK, WOW, AGE, SYNC and MIX, plus all six controls together in FREE
and BEAT. The gate records mean, p95, p99, the maximum, and the actual worst
block's function profile, with a separate peak ceiling for every case.

It consumes the remix image built by `make check`, checks generated-source
drift, incrementally rebuilds its ColdFire probe, and runs:

* every TIME value at six tempos, plus actual long-delay impulses, bounded BEAT settling and monotonic FREE slew;
* shipped TIME formatter across all values, tracks, Parts and both modes;
* repeated FREE/BEAT toggles with and without WOW, dirty-memory entry, exact stereo dry and bounded feedback;
* measured bandwidth, WOW depth, frequency-dependent repeat decay, noise
  buildup, age-dependent noise and fixed DRIVE=0 compression;
* eight compiled ColdFire instances sweeping every control, tempo and mode,
  including synthetic full history and an active-history wrap, bit-identical to native arithmetic;
* direct assembly-kernel tests against the native oracle's own kernels:
  1024 filter blocks driving both read-outs into saturation with random
  carries, 1024 record/output blocks across full wet, MIX, MIX=0 and knob
  ramps, 2048 plain and crossfading reader blocks with uncached-load counts,
  callee-saved registers, buffer guards and per-kernel instruction ceilings;
* the complete stock delay routine with modelled DMA transfers, mixed Tape
  Echo / stock DELAY tracks, and stock audio/ring identity against 1.40C.
* stock-versus-Tape instruction benchmarks through that complete routine,
  including original/patched stock baselines, two/three-instance automation,
  eight-instance default MIX, all-control edits and full-history stress.

```
python3 modules/tapeecho/generate_tables.py --check
python3 modules/tapeecho/generate_cpu.py --check
.venv/bin/python3 tools/verify/verify_tapeecho_cpu.py tapeecho
make check REMIX=tapeecho
```

The verifier writes `out/tapeecho-cpu/{voice,coldfire,benchmark}.log` and
`audition.wav`, a native fixed-point render whose arithmetic is
cross-checked against ColdFire execution; it is not a hardware capture.
The voice probe also exercises 35,000 blocks of rapid controls and
full-scale input over three ring wraps; an ASan/UBSan build is run
separately. The remixer's DSP-only audition refuses Tape Echo explicitly
instead of silently playing its dry stub; use the CPU verifier's audition.

## Deliberate constraints

This is not a line-by-line desktop port. TIME uses a Q24.8 position and a
block-rate slew bounded to two samples per block (1/8 sample per sample).
There is no velocity/acceleration motor state. Large FREE time changes
take time to settle; position cannot overshoot the target. Linear
interpolation includes both TIME and WOW movement, using the same fast
reader during knob edits as at rest. Both sides of BEAT transitions use
that reader, too. Two oscillators are evaluated once per 16-sample block
and their offsets interpolated at audio rate. Tone coefficients update
when the delay crosses a 32-sample bin; timing itself is not quantized in
FREE. The pedal's scrape
flutter, physical-cell write/interpolation, spring reverb, stereo Dual mode
and separate bass/treble controls are omitted.

The audio arithmetic is written for the ColdFire EMAC the way stock's own
delay loops are: multiply-with-load, accumulator loads, several
accumulators, and the saturating MOVCLR read-out (MACSR OMC) in place of
explicit clamps. Playback, both filter sections and the record sum run in
Q3.29 (+/-4 FS, the old clamp points); the record FIR and curve index stay
Q6.26. The two biquad sections share one pass and carry their eight low
accumulator bits to the next sample to suppress fixed-point limit cycles.
Both are stored as g*(x +/- 2*x1 + x2) + a1*y1 + a2*y2 with the unit part
of a1 as an exact accumulator load; the wet makeup gain lives in the tone
section's numerator and feedback is divided by it. The tape curve (a
signed table of finished ring words) and control laws are offline-generated
lookup tables; there is no per-sample floating point, trigonometry,
division, allocation or variable-speed cell-writing loop. Full-period LCG
hiss grows with AGE; flutter still uses xorshift. Tone updates/ramping run
once per 64 samples (~1.45 ms), staggered by track so only two of eight
active instances do that slow control work per block. TIME/WOW geometry and
gain smoothing are not decimated. The head reader steps a DDA and reuses
the overlapping sample from the preceding read: 17 instead of 32 uncached
word loads for a normal contiguous block. No persistent ring cache or
cache-coherency assumption is introduced. A BEAT crossfade's outgoing head
is blended into the incoming one as it is read.

## CPU integration

`cpu.c` is freestanding fixed-point C with signed fractional EMAC multiplies,
and its native build is the bit-exact arithmetic oracle for three
assembly kernels in `cpu_kernels.s`: the head reader (with crossfade), both
playback filter sections, and the record sum / FIR / curve / output mix.
Every EMAC form they use has sites in stock 1.40C.
`generate_cpu.py` produces the checked-in `cpu.s`, following Euclid's build
pattern. No float, heap allocation, runtime library or firmware bytes are
vendored. The platform loader owns the code/tables and 1600 bytes of instance
state (200 bytes per track). `generate_tables.py` designs the fixed-point
tables; `generate_cpu.py` checks them before compiling the ColdFire unit.
Its existing 10 MiB arena reservation is required (shared with other DRAM
modules), reducing the available sample/recorder pool in a formerly ROM-only
remix. The rings themselves are already reserved by the stock OS.

* `0x40002f44`: reset our state with the stock delay's ring reset.
* `0x4000361a`: after stock DMA read completion / next-track prefetch,
  run Tape Echo only for id `0x15`; replay the original path for every other id.
* Preserve the stock ping-pong scratch-buffer toggle and 68-byte state stride,
  then rejoin `0x4000377a` for the existing ring DMA writes.
* Ring base is `0x4f502c10 + track * 1411328`, through the **uncached** alias.
  Each ring contains 176400 stereo frames; Tape Echo writes mono to both sides.
* On effect entry, a valid-history counter excludes the previous effect's
  samples. There is no large buffer clear inside the audio callback.

Stock DELAY remains id `0x08` and is not replaced. CPU Tape Echo claims no
DSP delay memory.
