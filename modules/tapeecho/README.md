# Tape Echo

`TAPE ECHO` replaces FX2 **SPRING REV**. It is a mono single-head tape echo
with stereo dry output, now running on the **ColdFire CPU**, in the stock
delay's four-second per-track ring. The DSP side is an empty passthrough
(one NOP per sample for the generic insert cycle gate) and allocates no tape buffer.

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

DJ-Mixer's `fx-dsp/core/src/blocks/TapeEchoBlock.cpp` is the behavioural
reference for voicing. Its multi-head geometry and physical-cell
variable-speed write model are not copied. This CPU version still uses
a fractional moving read head.

## Controls

The first page follows the stock Delay pattern: performance controls stay on
the normal FX page, with MIX in the final bottom-right position. Character
controls, including AGE, are on that same page; the detail page is disabled.

| Page | Control | Meaning |
| --- | --- | --- |
| 1 | TIME | 46-231 ms in FREE; musical divisions in BEAT |
| 1 | FDBK | Regeneration; the upper range safely grows tape noise into self-oscillation. |
| 1 | WOW | 0.8 Hz wow plus randomized flutter; 0 is static. 44/127 gives about 7.7 cents RMS. |
| 1 | AGE | Repeat bandwidth, flutter and hiss; fresh at 0, worn at 127. Former HEADS slot. |
| 1 | SYNC | `FREE` continuous time, or `BEAT` tempo-quantised time. |
| 1 | MIX | Dry/wet crossfade; 0 is exact dry. |
| Detail | — | Former DRIVE slot: disabled; the engine always uses DRIVE=0, including on saved parts. |
| Detail | — | Former AGE slot: disabled; AGE now lives on page 1. |

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
is blended into the incoming one as it is read. See [VOICING.md](VOICING.md)
for measured results, deviations from Galaxy and the stock-delay CPU
benchmark.

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

Stock DELAY remains id `0x08` and is not replaced. CPU Tape Echo no longer
claims any DSP delay memory.

CPU cost is not yet hardware-qualified. Eight instances are verified for
correctness, **not** certified to meet deadlines alongside timestretch,
recording and streaming. Emulator instruction counts are not hardware cycles.

## Local gates and audition

`.venv/bin/python3 tools/verify/verify_tapeecho_cpu.py tapeecho` runs the CPU
gate with the same native architecture used by `make check`.
It also measures parameter-edit spikes with full synthetic tape history and
all eight tracks active. Endpoint reversals run every 1, 16 and 64 blocks for
TIME, FDBK, WOW, AGE, SYNC and MIX, plus all six controls together in FREE
and BEAT. The gate records mean, p95, p99, the maximum, and the actual worst
block's function profile, with a separate peak ceiling for every case.

After the EMAC rewrite (23 Sep 2026), eight settled full-wet instances
cost 14,245 instructions per frame with WOW=0 and 15,283 with WOW=44
(1.87x and 2.00x stock DELAY, from 2.64x and 2.88x); the MIX=90 default
with moving TIME costs 16,459 (2.16x, from 3.31x). All controls reversing
peak at 18,063 in FREE and 21,547 in BEAT (from 26,563 and 31,454).
Settled MIX=90 with full history peaks at 16,248. These are
executed-instruction counts, not hardware cycles, and hardware UI
responsiveness remains unverified.

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

**Hardware freeze remains open:** OCTACLID4 reached six instances before
freezing during edits; OCTACLID3 froze on TIME with three. Earlier images
also froze on second-instance TIME changes and loading three instances.
No exception screen was shown. OCTACLID5 targets eight instances with
editing headroom and reduces measured work again; it is not yet a physical
fix confirmation. Local instruction counts
do not establish CPU deadline headroom. Do not treat this candidate as a
hardware-confirmed fix or as safe for a live set.

`make check REMIX=tapeecho` includes this gate and the loader boot.
The native audition is `out/tapeecho-cpu/audition.wav`. Its arithmetic is
cross-checked against actual ColdFire execution, but it is not a hardware
capture. Hardware listening, cache/bus timing and worst-case CPU load remain open.
The remixer's DSP-only audition refuses Tape Echo explicitly instead of
silently playing its dry stub. Use the CPU verifier's audition for now.
