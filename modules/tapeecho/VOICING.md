# CPU Tape Echo: measured voice and cost

19 Sep 2026. Local native renders plus execution of the compiled ColdFire
engine. **Not a hardware capture or a real-time certification.** This pass
brings the CPU voice closer to Galaxy without moving it back to the DSP.

## Read-head and full-wet optimization (23 Sep 2026)

This pass preserves the native C engine, tables, filters, gain ramps, tape
curve and control timing. The moving reader uses one relative Q16 phase
instead of rebuilding the delay and address each sample. Its +255 bias
preserves the original signed rounding exactly. A signed integer anchor
keeps the four-second ring address outside that phase; negative anchors at
the wrap seam are explicitly tested. Alternating sample registers eliminate
copies when neighbouring reads overlap. When the phase step is zero, a
separate loop uses a constant interpolation fraction and consecutive loads.
Both paths retain 17 uncached sample loads for a contiguous block.

The full-wet record kernel alternates its FIR history registers and removes
an unnecessary branch per sample. No audio approximation or sample-rate
reduction is involved. The generator now pins external tail calls to `jmp`:
GNU as otherwise relaxes `jra te_read_linear` differently for 54454 and
5475 and fails the existing encoding-identity gate. Regeneration uses the
local GCC 15.2.0 toolchain; the numbers below include its changed register
allocation, including a 16-instruction increase in the patched-stock case.

Measured against the checked-in assembly at `1e6d246` with the same stock
firmware, DMA model, stereo tone, 1500 warm-up and 1000 measured blocks.
These are **executed instructions per complete eight-track 16-sample
routine**, not hardware CPU percentages. Full-wet is used unless MIX is
specified:

| Configuration | Before | After | Reduction |
| --- | ---: | ---: | ---: |
| Original stock DELAY x8 | 7,628.0 | 7,628.0 | 0.0% |
| Patched stock DELAY x8 | 7,892.0 | 7,908.0 | -0.2% |
| Tape x8, settled, WOW=0 | 22,506.6 | 20,122.6 | 10.6% |
| Tape x8, settled, WOW=44 | 22,954.1 | 21,989.5 | 4.2% |
| Tape x8, moving FREE TIME, WOW=44 | 23,272.1 | 22,351.0 | 4.0% |
| Tape x8, changing BEAT TIME, WOW=44 | 24,659.6 | 23,556.6 | 4.5% |
| Tape x8, moving FREE TIME, MIX=90 | 25,808.1 | 25,271.0 | 2.1% |
| Tape x8, all controls moving, full synthetic history | 31,974.4 | 30,758.3 | 3.8% |

The settled ratio to stock falls from **2.95x to 2.64x without WOW**, and
from **3.01x to 2.88x with WOW=44**. The fixed-reader kernel costs 185
instructions per call; moving-reader boundary cases peak at 371. Direct
kernel gates enforce ceilings of 200 and 420 respectively. Eight-instance
endpoint stress peaks at 26,563 in FREE and 31,454 in BEAT; settled MIX=90
with full history peaks at 25,028.

Validation: all native voice/control gates and the eight-instance compiled
ColdFire/native output-and-state comparison pass, including full history,
control changes and ring wrap. The expanded kernel suite covers 2048 reader
blocks (signed/outside-ring anchors, fractional positions, fixed/moving
heads, actual uncached read counts and ABI) and 256 full-wet blocks with
full-range input, random FIR history, clipping, state and buffer guards.
Stock DELAY output/rings remain bit-identical. The optimized runtime boots
to the RTOS handoff and all 169,144 runtime bytes match the linked image;
menu and initial-register gates pass.

`make check REMIX=tapeecho` passes the Tape Echo, dirty-state and cycle
gates, then stops in `verify_replaces.py`: six unrelated Octakit remixes
fail to assemble `modules/octakit/upstream/runtime/runtime.S:438` (short
branch displacement out of range). The remaining boot/menu/register gates
were run separately. This is not a clean full-repository check. Hardware
cache/bus timing, CPU deadlines and the previously reported freezes still
need a device test.

## One-page restoration and parameter spikes (21 Sep 2026)

The six experimental page-2 controls were removed after hardware reports of
poor UI responsiveness and ineffective SLEW. This restores the saved optimized
one-page engine exactly: fixed 0.8 Hz wow rate, original flutter, two-sample
per-block FREE slew, AGE-linked hiss, fixed 106 Hz low cut, no freeze, and the
original 200-byte state. The detail page is disabled again.

The parameter-stress gate remains. With eight Tape Echo instances, full
synthetic history and MIX=90, it applies synchronized endpoint reversals every
1, 16 and 64 blocks and profiles the actual worst block:

| Case | p95 | p99 | Peak instructions/block |
| --- | ---: | ---: | ---: |
| Settled | 25,570 | 25,580 | 25,604 |
| TIME | 25,907 | 25,981 | 26,045 |
| FDBK | 26,544 | 26,562 | 26,575 |
| WOW | 25,568 | 25,588 | 25,602 |
| AGE | 26,816 | 26,830 | 26,848 |
| SYNC | 31,180 | 31,284 | 31,458 |
| MIX | 26,578 | 26,593 | 26,599 |
| All page-1 controls, FREE | 27,030 | 27,071 | 27,091 |
| All page-1 controls, BEAT | 32,275 | 32,345 | 32,466 |

The earlier two-page combined-control peak was 35,614 after optimization
(36,424 before it). Removing page 2 lowers that case to 32,466. Counts exclude
cache, DMA and bus stalls and do not certify hardware responsiveness.

## Bit-exact kernel optimization (21 Sep 2026)

This pass preserves the existing economy voice, control timing, tables and
native C oracle. Filter kernels consume the old input history before
replacing it, removing two register copies per sample without changing
individual EMAC product truncation or the bounded sum. Settled recording
extracts the hiss gain once per block, preserving the original full-precision
state word. FIR history registers exchange roles between samples. Small
unrolled groups reduce loop comparisons/branches: four samples per filter
iteration and two per recording, FIR/curve and head-reader iteration.

Same full stock eight-track routine, 1500 warm-up + 1000 measured blocks;
means below count executed instructions, not hardware cycles:

| Configuration | Before | After | Reduction |
| --- | ---: | ---: | ---: |
| Original stock DELAY x8 | 7,628 | 7,628 | 0% |
| Patched stock DELAY x8 | 7,892 | 7,892 | 0% |
| Tape x1 WOW=44 + stock x7 | 10,231 | 10,040 | 1.9% |
| Tape x8 settled WOW=44 | 26,620 | 25,092 | 5.7% |
| Tape x8 moving FREE TIME | 26,934 | 25,406 | 5.7% |
| Tape x8 changing BEAT TIME | 28,344 | 26,789 | 5.5% |
| Tape x8 all controls moving | 32,165 | 30,929 | 3.8% |
| Tape x8 all controls moving, full synthetic history | 33,105 | 31,836 | 3.8% |

The settled eight-instance ratio falls from 3.49x to 3.29x original stock.
The no-WOW per-instance increment over patched stock falls from 2,286 to
2,095 instructions (8.4%). Full-history stress peaks at 32,233, down from
33,505. The profiled two-instance kernels fall from 1408 to 1248 (filter),
1980 to 1854 (record), 1084 to 1020 (FIR/curve), and 920 to 888 (reader).

The Tape Echo verifier passes unchanged: native voice/control gates,
compiled ColdFire/native output and state identity under eight-track
control sweeps and history wrap, kernel clamps/carry/ABI/guards, uncached
read counts, and stock DELAY audio/ring identity. No quality tolerance is
relaxed. Assembled code/tables grow by 1152 bytes (167282 to 168434);
instance state, tables, rings and DSP processing are unchanged. Additional
code may affect instruction-cache behavior, so these instruction savings
still require hardware timing; they do not resolve the reported freezes.

### Fused full-wet record path (21 Sep 2026)

The settled full-wet (`MIX=127`) path now constructs the feedback record,
applies the record FIR and tape curve, stages the stereo DMA record, and
writes the mono wet output in one assembly pass. This removes the temporary
record-buffer round trip, one kernel prologue/epilogue, and repeated constant
loads. The two former kernels cost about 1,413 instructions per instance;
the fused kernel costs 1,135. Record, feedback, filtering, saturation, hiss,
and control state remain fixed-point identical.

The only intentional audio change is at exactly `MIX=127`: the wet sample is
clipped once and copied to both channels. The former interpolation retained a
dry-dependent error of at most one Q23 output LSB. Other MIX values continue
through the original stereo interpolation path.

| Configuration | Before fusion | Fused | Change |
| --- | ---: | ---: | ---: |
| Tape x1 WOW=44 + stock x7 | 10,040 | 9,781 | -2.6% |
| Tape x8 settled WOW=44 | 25,092 | 23,018 | -8.3% |
| Tape x8 moving FREE TIME | 25,406 | 23,336 | -8.1% |
| Tape x8 changing BEAT TIME | 26,789 | 24,724 | -7.7% |
| Tape x8 moving FREE, MIX=90 | 25,670 | 25,872 | +0.8% |
| Tape x8 all controls moving | 30,929 | 31,131 | +0.7% |
| Tape x8 all controls moving, full history | 31,836 | 32,038 | +0.6% |

The small non-full-wet increase is the dispatch and changed compiler register
allocation. The full-wet saving is much larger, and the stress peak
remains below the pre-optimization result. Relative to the original 26,620
settled measurement, both optimization passes together save 13.5%. The
assembled image grows another 620 bytes, from 168,434 to 169,054.

### Per-function profiles

The ColdFire benchmark now profiles 64 complete blocks for each important
scenario, rather than attributing one block from the two-instance moving-TIME
fixture. It reports instructions per full eight-track block, per active Tape
instance, and as a share of the complete routine. Symbol attribution is
exclusive: `te_process` excludes time spent in its assembly callees.

| Function | Settled MIX=127 | Settled MIX=0 | Full-history/all-controls |
| --- | ---: | ---: | ---: |
| `te_record_wet_finish` | 1,135 / Tape | — | — |
| `te_record_block` | — | 516 / Tape | 1,075 / Tape |
| `te_filter_block` (both biquads) | 624 | 624 | 624 |
| `te_finish_record` (FIR + curve) | — | 494 | 494 |
| `te_read_linear` | 444 | 444 | 878 |
| `te_process` exclusive control work | 298 | 309 | 502 |
| `render_head` wrapper | 59 | 59 | 118 |
| `te_cpu_frame` | 96 | 96 | 96 |
| `te_cpu_hook` | 10 | 10 | 10 |

The pre-fusion profile established the optimization order. At settled
MIX=127, record/mix plus FIR/saturation cost 1,413 instructions per instance.
MIX=0 showed that about 403 of `te_record_block`'s former 919 instructions
were output mixing; record construction itself costs about 516. The retained
fusion reduces the combined default path to 1,135. General MIX=90 remains on
the separate kernels at 952 + 494. Under all-control stress, gain ramps add
work and active BEAT fades nearly double the reader. The fixed filters and
FIR/curve do not grow with automation.

Two character-changing trials were rejected after measurement. A parabolic
soft clip passed the voice gates but saved only about 1.1% overall. A fitted
one-pole playback high-pass saved only about 0.3% once it retained clamps and
fraction behavior, while changing the low-frequency noise floor. Neither is
kept in the generated engine. The retained fused path instead attacks the
measured record/FIR cost without reducing sample rate or changing either
playback filter.

## Eight-instance candidate (OCTACLID5, 20 Sep 2026)

OCTACLID4 now freezes while editing the sixth instance (owner report).
Eight instances with editing headroom remain the hardware acceptance
target, **not a result established by this candidate**. Deadline overrun
is still a hypothesis; these tests do not model the rest of the running OS.

- Keep 44.1 kHz audio, the feedback law, saturation curve, bass cut,
  wow/flutter, single head and 512-sample BEAT fades. No half-rate audio.
- Fold TIME/AGE low-passes into one non-resonant biquad; use a cheap
  `[1,6,1]/8` record FIR. The offline fit compensates that FIR at 4/8.4 kHz.
  The extreme top-end slope differs; this is an intentional economy voice.
- Stagger 64-sample tone-control updates across tracks. Gain ramps remain
  sample-accurate; read motion still ramps each sample.
- Register-resident gain/mix and FIR/curve kernels avoid the compiler's
  per-sample spills. Use a full-period LCG for hiss (not its low bits).
- Reuse one overlapping uncached read in each advancing interpolation
  pair. A settled contiguous block performs **17 rather than 32 ring word
  loads** (47% fewer), directly counted in the emulator. This does not mean
  47% less total bus traffic; stock DMA and all other reads remain.
- State is 200 bytes/track (1600 total), down from 256. The larger folded
  tone table uses the existing DRAM reservation; no extra ring is allocated.

Same complete eight-track 16-sample routine, 1500 warm-up + 1000 measured
blocks, original stereo source and loading schedule. These are instruction
counts, **not cycles, CPU percentages or hardware headroom**:

| Eight Tape instances | OCTACLID4 mean / peak | OCTACLID5 mean / peak |
| --- | ---: | ---: |
| Moving FREE TIME, WOW=44, MIX=127 | 34,680 / 35,028 | 26,934 / 27,164 |
| Changing BEAT TIME, WOW=44 | 36,075 / 37,067 | 28,344 / 29,290 |
| Moving FREE TIME, default MIX=90 | 35,208 / 35,556 | 27,198 / 27,428 |
| All six controls + tempo moving | 40,592 / 42,085 | 32,165 / 33,443 |

This is 21–23% less measured work in those workloads. The new all-controls
fixture with **synthetically filled delay history** costs 33,105 mean /
33,505 peak, avoiding startup's silent-history shortcuts. It has no old
baseline and is not presented as an equal-work speedup. Test ceilings are
30,000 for TIME-only and 35,000 for all-control eight-track workloads, plus
5,000 per isolated callback; these are regression budgets only.

Audio tradeoff: the original 12 pedal frequency/AGE reference points now
differ by up to 1.89 dB (was 0.44 dB in OCTACLID4). The reference stays
unchanged, while its explicitly economy-model tolerance changes from
1.25 to 2 dB. Worn tape is darker around 4 kHz and brighter at 10 kHz;
this tolerance is not a bound over every frequency/TIME setting. The
other sound/safety gates are not relaxed: feedback decay stays within
0.38 dB of the historical Galaxy points, WOW=44 stays about 7.75 cents RMS,
noise after 20 seconds at FDBK=102 is about -7.69 dBFS, and full-scale
record compression remains about 1.64 dB. FREE/BEAT click residual is
0.000443 FS; rapid FREE reversals are 0.001070 FS in the existing fixtures.
Galaxy was not freshly rendered for this pass.

The oracle now covers all-control gain ramps, full synthetic history,
active-history wrap, direct record/mix clamps, FIR/curve boundaries,
callee-saved registers, output guards and uncached read counts. Stock
DELAY remains independently compared against the original firmware.
Physical eight-track playback, timestretch, streaming, recording and
live knob/lock changes still need on-device validation before calling
the freeze fixed or declaring headroom.

## Previous economy candidate (OCTACLID4, 20 Sep 2026)

The owner reported OCTACLID3 still freezing on TIME edits with three
instances, and explicitly accepted less physical tape/motor modelling for
lower cost. This is a performance redesign, not a proven hardware diagnosis.

- Nine biquads become four; the record top is second-order, emphasis and
  de-emphasis plus the small low-mid lift are omitted. Feedback law and
  saturation curve remain; time and AGE bandwidth filters remain separate.
- FREE uses one bounded block-rate slew, not a per-sample velocity model.
  Ordinary TIME edits and both ends of BEAT crossfades use the fast reader.
- Two simple wow/flutter oscillators replace five transport-integrated
  oscillators. There is no time-dependent cancellation of wow, harmonic
  capstan or drift oscillator. Tone-control division/interpolation runs
  only after a 32-sample delay-bin change, not on every changing sample.
- AGE is now page 1, slot 3. Per-instance state shrinks 388 → 256 bytes.

Same full eight-track routine, same input/controls (AGE moved to its new
slot), same sequential-loading schedule, same 1,500 warm-up + 1,000 measured
blocks. Counts are **instructions**, not clock cycles or device CPU percent.

| Case | OCTACLID3 | OCTACLID4 | Reduction |
| --- | ---: | ---: | ---: |
| Stock DELAY ×8, patched | 7,892 | 7,892 | unchanged |
| Tape ×3 settled, WOW=44, stock ×5 | 23,791 | 17,548 | 26% |
| Tape ×3 moving FREE TIME, stock ×5 | 27,582 | 17,931 | 35% |
| Tape ×3 changing BEAT TIME, stock ×5 | 25,272 | 18,515 | 27% |
| Tape ×8 moving FREE TIME, WOW=44 | 60,399 | 34,680 | 43% |

The three-instance moving-TIME increment above settled work falls from
3,791 to 384 instructions (~90%). This is that control-change overhead,
not a 90% reduction in the whole effect. Third-instance selection frames
also complete locally: 16,398 settled / 17,122 moving FREE / 17,880 BEAT
instructions. The expanded callback stress sweeps AGE as well as TIME;
peak 5,124, under a tightened 6,000-instruction regression limit.

Measured sonic tradeoffs: the 12 frequency/age points remain within
0.44 dB of the existing pedal reference; WOW=44 measures 7.74 cents RMS,
and worn tape 8.20. Repeats at 1 kHz lose about 0.24 dB more per repeat than
OCTACLID3 (still within 0.36 dB of the historical Galaxy reference points).
Full-scale-input compression decreases from 2.48 to 1.64 dB. At FDBK=102,
20-second noise build-up is -7.80 dBFS instead of -8.81 dBFS; low-feedback
noise floors differ by less than 0.7 dB. These are explicitly accepted
economy-model tradeoffs; the voice gate retains the old references but
allows 1.5 dB buildup and 1 dB floor differences. Clipping, DC, runaway,
dirty-state, click and memory-bound gates are not relaxed.

The newer cheap-slew mode-switch residual is 0.000279 FS in the existing
test. Actual CPU/cache/DMA timing and physical three-instance stability
remain unverified. Do not call the reported freeze fixed based on this gate.

## Historical single-head candidate (OCTACLID3)

The sections below retain the historical DRIVE=51/multi-head comparison.
That candidate removed HEADS and DRIVE, fixing the voice at DRIVE=0
as requested. Feedback law, record/playback filters and saturation curve
are unchanged. A pre-change DRIVE=0/HEADS=1 native binary matched the first
single-head implementation's audio and recorded ring bit-for-bit over
12,000 blocks in each of four feedback/wow/age combinations. Subsequent
wow-offset acceleration limiting specifically changes transition behaviour;
the numerical voice gates, not that earlier identity comparison, validate
the final candidate.

OCTACLID3 DRIVE=0 measurements: WOW=44 is 7.734 cents RMS; 1 kHz decay at
FDBK=32/64/76/83/89 is -19.702/-6.094/-2.720/-0.991/+0.379 dB per repeat.
At FDBK=102, silence builds to -8.81 dBFS after 20 seconds, versus the old
DRIVE=0 -8.83 dBFS baseline. This is louder than DRIVE=51's -17.24 dBFS
because of the existing output compensation, not increased loop gain.
Noise floors at AGE=0/64/127 remain -119.05/-118.03/-114.23 dBFS. Loud-input
compression is 2.48 dB. FREE/BEAT interrupted-transition sine-recurrence
residual is 0.000541 FS worst case across WOW=0/44/127.

Same full eight-track routine, instruction counts (not CPU percentages):

| Configuration | Mean instructions / 16 samples |
| --- | ---: |
| Stock DELAY ×8, original firmware | 7,628 |
| Single-head Tape ×1, WOW=44, plus stock ×7 | 13,190 |
| Tape ×2, moving FREE TIME, plus stock ×6 | 21,017 |
| Tape ×2, changing BEAT TIME, plus stock ×6 | 19,481 |
| Tape ×3, settled, plus stock ×5 | 23,791 |
| Tape ×3, moving FREE TIME, plus stock ×5 | 27,582 |
| Tape ×3, changing BEAT TIME, plus stock ×5 | 25,272 |
| Tape ×8, settled, WOW=44 | 50,292 |

The prior three-head ×8/WOW=44 case was 65,589: this one-head configuration
uses about 23% fewer instructions. That is a different head configuration,
not an equal-work speedup. Against the prior **one-head** case (53,106), the
saving is about 5%. Instances are loaded sequentially during warm-up;
the third-instance selection frame peaks at 24,544 instructions for the
settled-TIME case, 26,452 while moving FREE TIME, and 25,539 in BEAT.
These frames complete in the emulator, not a physical Octatrack test.
The new automated eight-instance callback peaks at
7,461 instructions. None of these figures includes real memory/cache/DMA
stalls or the rest of the firmware's workload. Hardware has frozen with two
instances plus TIME edits and when adding three; the cause and the new
candidate's hardware headroom remain unverified.

## References and method

The user's local `DJ Mixer/firmware/fx-dsp/core/src/blocks/TapeEchoBlock.cpp`
is the sonic design reference. A fresh 44.1 kHz native comparison compiled
that source directly (not just its potentially older built library).
The earlier `DJ Mixer/test/results/07-fx-tape-echo-galaxy-2026-09-11.md`
contains direct UADx Galaxy measurements at 48 kHz. **Galaxy itself was not
freshly rendered in this pass.** No proprietary plugin code, samples or
firmware bytes are included here.

Unless stated: first head, 5888-sample delay (133.515 ms), wet only,
DRIVE=51/127 (pedal 40%), WOW=0, FDBK=0. Response is steady sine RMS
relative to 1 kHz at -40 dBFS. WOW is pitch variation of a 3 kHz tone,
interpolated zero crossings over ten periods, first second discarded.
Noise buildup starts from silence, not an injected impulse. Details and
numerical assertions live in `tools/harness/tapeecho_voice_probe.cpp`.

## Changes and results

* Feedback law: `2.3 * (FDBK/127)^2.26`, rather than `1.2 * FDBK/127`.
* Record path: drive and partial makeup, +3 dB broad 1 kHz emphasis,
  sixth-order 11.5 kHz top and lookup-table soft tape saturation
  `tanh(1.7*u)/1.7`, `u=x/(1+0.4*abs(x))`.
* Playback/feedback: inverse emphasis, 106 Hz low cut, +0.8 dB low-mid
  lift, speed-dependent playback corner and AGE-dependent upper loss.
* WOW: speed-dependent capstan rate/depth, second harmonic, two
  per-cycle-randomized flutter oscillators and a slow drift oscillator.
  Modulation integrates speed variation over each head's travel time.
* Hiss increases with AGE and circulates through the same nonlinear loop.
  Fraction-saving EMAC filters avoid the large fixed-point noise/limit-cycle
  floor observed in the first implementation attempt.

| Measurement | Previous CPU | Re-voiced CPU | Reference |
| --- | ---: | ---: | ---: |
| WOW at 44/127, cents RMS | 0.58 | 7.73 | pedal 7.99; historical Galaxy New 7.9 |
| 80% feedback, noise after 20 s, dBFS | -95.7 | -17.24 | fresh pedal -17.1 |
| 100 Hz response, new tape, dB re 1 kHz | -0.14 | -6.08 | fresh pedal -6.07 |
| 10 kHz response, new tape, dB re 1 kHz | -1.83 | -17.14 | fresh pedal -17.73 |
| 10 kHz response, old tape, dB re 1 kHz | -18.71 | -25.87 | fresh pedal -26.46 |

The 12 response points (100 Hz, 4/8/10 kHz at AGE=0/64/127) differ from
the fresh pedal measurements by at most **0.59 dB**. First-to-second repeat
decay at 1 kHz is -19.70/-6.09/-2.73/-1.00/+0.37 dB at FDBK=32/64/76/83/89;
at most **0.20 dB** from the historical Galaxy values at 25/50/60/65/70%.
Additional 8 kHz loss is **11.83 dB per repeat**, not merely an output EQ.

WOW=0 measures 0.00003 cents RMS; WOW=127 measures 22.32. At WOW=44, old
tape increases variation to 8.14 cents RMS. Full-scale 1 kHz input compresses
by 11.16 dB at DRIVE=51 and 18.98 dB at DRIVE=127, relative to low-level gain.

Known differences remain: the old head spacing (1:1.96875:2.9609375), linear
time-domain reads rather than physical tape-cell writes, approximate drift,
no scrape flutter and no spring/stereo Dual. The low-feedback noise floors
are -126.69/-125.83/-122.45 dBFS at AGE=0/64/127, **higher and with less age
contrast** than the historical Galaxy values -138.8/-132.8/-126.8. This is
closer tape behavior, not a bit-exact pedal port or a claim to clone Galaxy.

## Efficiency and stock comparison

All runtime arithmetic is fixed point. Coefficients, saturation, and sine
tables are generated offline. Nine biquads run in 16-sample EMAC batches,
holding coefficients/history in registers, with one accumulator read per
section/sample. WOW/flutter are evaluated at block rate and interpolated.
Head geometry is factored out of the sample loop. No allocations, libm,
runtime floating point or physical-tape cell-writing loop.

The compiled callback's stress-test peak fell from **16,123** in the first
re-voicing draft to **11,588**, then **10,138 instructions/16-sample track**
in the efficiency pass. The previous,
much simpler CPU voice peaked at 7,226 in its earlier fixture. A 12,000
instruction regression ceiling now guards this test; **it is not a hardware
deadline budget**. State occupies 400 bytes/track (3200 total), using the
existing stock delay rings rather than allocating another delay buffer.

Benchmark: original and patched firmware execute the same complete stock
CPU delay routine at `0x400031a0`, with the same synchronous DMA model,
stereo tone, nonzero feedback/wet level, four control slots and both audio
buffers. 1500 warm-up blocks, then 1000 measured blocks at 44.1 kHz/16
samples. Tape settings: TIME=60, FDBK=64, DRIVE=51, AGE=64, MIX=127.
Stock settings: TIME=60, FDBK=64, VOL=127, BASE=0, WDTH=127, SEND=127;
stock setup bytes zero except byte 2=127. Effect delay times need not be
identical: this measures CPU work, not matching those two TIME knob laws.

| Whole eight-track CPU routine | Mean instructions / block | vs original stock |
| --- | ---: | ---: |
| Stock DELAY x8, original firmware | 7628.0 | 1.000x |
| Stock DELAY x8, patched firmware | 7892.0 | 1.035x |
| One Tape, head 1, WOW=0 + seven stock | 13304.1 | 1.744x |
| One Tape, head 1, WOW=44 + seven stock | 13543.7 | 1.776x |
| One Tape, three heads, WOW=44 + seven stock | 15104.1 | 1.980x |
| Eight Tape, head 1, WOW=0 | 51188.5 | 6.711x |
| Eight Tape, head 1, WOW=44 | 53105.8 | 6.962x |
| Eight Tape, three heads, WOW=44 | 65588.8 | 8.598x |

The extra WOW cost in the single-Tape fixture is about 240 instructions
per block. A profiled three-head callback spends 3168 instructions in its
filters (previously 4401), 1377 in contiguous head reads, 1148 in steady
record/mix, and 2176 in `te_process` including the now-inlined modulation.

### Bit-exact efficiency pass

Compared with the just-revoiced CPU engine, the eight-Tape fixtures fell
from 67720.4 to 51188.5 instructions (WOW=0, **24.4% less**), 70354.9 to
53105.8 (one head/WOW=44, **24.5% less**), and 89781.0 to 65588.8 (three
heads/WOW=44, **26.9% less**). These are whole-routine reductions, not
isolated callback or device-load percentages.

* Hand-scheduled two-sample biquad kernels keep histories in registers and
  retain every fractional-carry and overload-clamp operation.
* Settled motor/gain blocks use a bounded contiguous head reader. History,
  modulation and ring-seam checks select the general path when necessary.
* Constant record/mix gains and the PRNG remain local through each block;
  automation still uses the exact original ramps.
* Filter targets and the speed division are cached; coefficient smoothing
  stops only after its integer deltas reach zero. This costs 60 extra bytes
  of state per track, not another audio buffer.
* Measured `-O3` compilation reduces work further than `-O2`; neither uses
  floating-point fast-math or changes filter count, sample rate or tables.

A saved pre-optimization native engine and the new one produced identical
audio **and recorded tape** over 14 scenarios x 35,000 blocks (490,000 total):
all head masks, settled and randomized controls, and three physical ring
wraps per scenario. The disposable comparison and baseline are retained
locally under `out/tapeecho-cpu/`; the permanent voice and ColdFire gates
remain the reproducible checks. All reported sonic measurements above are
unchanged. Direct assembly tests additionally cover 1024 filter blocks with
both overload clamps/fractional carry and 512 boundary reader blocks, plus
callee-saved register preservation.

### Hardware address-error correction

The first hardware load of the optimized image raised `Vec:03` at
`te_read_linear`'s scaled-index ring read (`move.l (a1,d0.l*8),d5`). ColdFire
defines scale factor eight in an indexed effective address to raise an address
error; the emulator incorrectly accepted it. The reader now forms the byte
offset explicitly and loads through a plain address register. Generation
rejects any future `*8` memory address form. This changes addressing only;
interpolation and audio arithmetic remain bit-identical. The corrected image
still requires a hardware retest.

**Tape Echo remains substantially more expensive than stock DELAY.** These
counts exclude DSP work and hardware cache misses, RAM/bus contention and
DMA stalls; they cannot be converted directly into total-device CPU usage.
Eight instances pass functional tests, but are not approved for real-time
use alongside the rest of the Octatrack engine. Hardware timing under
timestretch/recording/streaming remains a release prerequisite. Nothing was
flashed or packaged as a new release by this voicing pass.

## Reproduction and gates

```
python3 modules/tapeecho/generate_tables.py --check
python3 modules/tapeecho/generate_cpu.py --check
.venv/bin/python3 tools/verify/verify_tapeecho_cpu.py tapeecho
make check REMIX=tapeecho
```

The verifier writes `out/tapeecho-cpu/{voice,coldfire,benchmark}.log` and
`audition.wav`. The latter is a native fixed-point render, not a hardware
capture. ColdFire execution is checked bit-for-bit against native samples,
recorded tape and state across all eight instances, transitions and ring
wraps. Mixed stock DELAY output and rings must remain identical to stock.
FREE/BEAT interruption tests include WOW=0 and WOW=44. Long-delay arrival
tests allow the new filters' bounded group delay, but forbid early echoes.
The voice probe also exercises 35,000 blocks of rapid controls/full-scale
input over three ring wraps; an ASan/UBSan build is run separately.

Final local results: both remix `make check` runs passed all runnable gates,
including loader boot. Project playback was skipped (no `OT_PROJECT`);
module-absent gates were skipped as expected. ASan/UBSan voice plus stress
tests passed with no diagnostics. FREE/BEAT peak recurrence residual was
0.001618 FS. The final standalone build leaves the `tapeecho` remix selected;
no release image/container is emitted.
