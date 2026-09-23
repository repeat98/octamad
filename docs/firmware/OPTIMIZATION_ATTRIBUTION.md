# Stock optimization attribution audit

23 September 2026. Read-only audit of the corrected 1.40C emulator run in
out/stock-profile/aba-fixed-5600/stock-a.*. The checkout baseline is ccb11fb;
the recorded run was produced from the then working tree at 2deac4b, with
source and input hashes in result.json. The stock MAIN_OS SHA-256 is
164f31224bf61181e3f50e7dec40df9afcae5b16dbf6e4c0d0cc5e986af0a84e.
Stock A and stock B PC tables and audio match exactly. This audit did not
rebuild or rerun either image.

This is one 5,600-frame, eight-FLEX-track workload, with stock delay on T1–T7
and plate reverb on T8; see [STOCK_PROFILE.md](STOCK_PROFILE.md) for the full
fixture. Counts are executed emulator instructions, not processor cycles,
hardware utilization, or deadline margin. Other workload families from
[OPTIMIZATION_PLAN.md](OPTIMIZATION_PLAN.md) assignment B are not available
in this evidence set, so no cross-family ranking is claimed.

## Verified boundaries and exclusive CPU attribution

The four principal half-open ranges were checked with
scripts/disasm.sh emac against the hashed stock image. ISR
0x4000aad0..0x4000d9b0 begins with a stack frame and ends in RTE at
0x4000d9ae; the normal path at 0x4000aaee and that RTE each execute 5,600
times. The initial prologue at 0x4000aad0 executes only 21 times in this
window. Delay 0x400031a0..0x4000385a, analysis
0x40098388..0x400985ac, and voice renderer 0x40007960..0x40008f82
each begin with a function prologue and end in RTS at the exclusive end
minus two bytes. The correlation routine
0x4009871c..0x40098a2c is the existing verified profile scope; its
caller at 0x40098b46 is visible in the disassembly.

| Exclusive PC range | Calls or entries in window | Instructions/frame | Share of 229,054,472 CPU instructions |
| --- | ---: | ---: | ---: |
| Frame ISR body, 0x4000aad0..0x4000d9b0 | 5,600 RTEs | 10,719.9 | 26.21% |
| Eight-track delay, 0x400031a0..0x4000385a | 5,600 | 7,664.5 | 18.74% |
| Sample analysis, 0x40098388..0x400985ac | 1,362 | 5,642.5 | 13.80% |
| Voice renderer, 0x40007960..0x40008f82 | 86,848 | 5,605.3 | 13.70% |
| Correlation search, 0x4009871c..0x40098a2c | 307 | 2,195.9 | 5.37% |
| Unattributed remainder | — | 9,074.5 | 22.19% |

These ranges do not overlap, so their counts are exclusive. The ISR has
direct and indirect calls. A PC histogram cannot assign their time to the
ISR, reconstruct nested call costs, or prove which task owned a function
when it ran. The table is therefore **not** an inclusive interrupt versus
background partition. The sample-analysis path is reached from the task
routine at 0x40098a5c through the wrapper at 0x400985ac;
correlation is called at 0x40098b46. Delay and voice work must remain
separate until call-stack or execution-context attribution is added.
The 22.19% remainder must remain visible rather than being distributed
among named routines.

### Controlled no-effects workload comparison

The four stock profiles in
out/optimization/workloads/initial/manifest.json use zero live FX1/FX2
IDs and 0, 1, 4 or 8 active FLEX tracks. Each short profile covers only
1,400 frames. Exclusive instructions per frame:

| Active tracks | ISR body | Delay routine | Voice renderer | Sample analysis |
| ---: | ---: | ---: | ---: | ---: |
| 0 (idle) | 10,706.7 | 7,438.0 | 0.0 | 0.0 |
| 1 | 10,712.2 | 7,438.0 | 675.3 | 1,181.7 |
| 4 | 10,728.5 | 7,438.0 | 2,701.3 | 4,726.8 |
| 8 | 10,750.2 | 7,438.0 | 5,402.5 | 9,173.0 |

This shows persistent delay and ISR work even with all live effect IDs
zero, while voice and analysis work scale with active tracks. In the
separate long no-effects FLEX-8 stock run
out/optimization/aba-no-fx-flex8-5600/stock-a.json (5,600 frames),
the corresponding values are 10,717.79, 7,437.25, 5,602.98 and
5,253.29. The large change in analysis between short and long windows
shows that a 1,400-frame rank is sensitive to observation phase.
Persistent execution is **not** proof that delay work can be skipped:
ring history, effect tails, future parameter transitions and state
updates need direct equivalence tests. These are emulator instruction
counts, not cycle or hardware headroom measurements.

## Hot subranges and next instruction-level targets

These subranges sit inside the exclusive scopes above and must not be added
to their parent percentages.

| Subrange | Observed work | Mechanism and locality | Bounded experiment |
| --- | ---: | --- | --- |
| ISR 0x4000cc02..0x4000cc26 | 1,681 instructions/frame; loop tail at 0x4000cc22/24 runs about 120 times/frame | Repeated EMAC arithmetic, packing and stores to a frame buffer; this is ISR body work. An exact-byte instruction at 0x4000cc08 is not decoded by this objdump, so its semantics need a separate check. | Try a factor-two unroll of the 6/9-iteration inner loop, retaining the original operations and memory order. The decrement/branch pair could save at most about 120 instructions/frame (0.29% total) before dispatch, cave and cache costs. |
| Delay 0x400036aa..0x400036ee | 2,688 instructions/frame; 128 iterations/frame | The selected filter path executes one stereo sample 16 times on each of eight tracks. EMAC accumulation and postincrement reads/writes touch the delay scratch/history. | Try a factor-two unroll with one decrement/branch per two samples. A two-instruction loop-control saving per pair has a ceiling of 128 instructions/frame (0.31% total). Preserve accumulator state, aliasing, DMA order, and final flags. |
| Delay 0x40003738..0x4000377a | 2,816 instructions/frame; 128 iterations/frame | Per-sample gain/mix recurrence and ramp updates with four accumulators and stores. | A second, separate factor-two unroll has a similar 128 instructions/frame upper estimate; the ramp and ring write order make its proof harder. |
| ISR 0x4000ce60..0x4000ceda | 2,044 instructions/frame; about 120 iterations/frame | Branches on signed packed control values, EMAC and two stores; several paths have different lengths. | Candidate only after exact branch/path-state tests; loop overhead alone is unlikely to clear 0.5% total. |
| Analysis 0x40098494..0x400984be | 2,048 instructions/frame; about 186 iterations/frame | EMAC recurrence, already patched in the pilot. | The existing patch saves 251.2 instructions/frame total on this fixture. Do not count it as a new opportunity. |
| Correlation 0x40098908..0x4009892c | 1,616.6 instructions/frame | Fixed 31-iteration EMAC inner loop, called from a background task. | Possible later candidate, after the pending overload workload identifies whether this task runs near the deadline. |

Priority for the next code pass: first the ISR inner loop at
0x4000cc02..0x4000cc26 because it runs in the interrupt body; second the
delay filter loop at 0x400036aa..0x400036ee because it runs 128 times every
frame; third the delay mix loop at 0x40003738..0x4000377a. These are
investigation priorities, not predictions of hardware savings. The first
two single-loop upper estimates are each below the plan's 0.5%
whole-workload triage preference. Combining both delay loops would have a
mechanical upper estimate near 256 instructions/frame (0.63%), but doubles
the state surface and ROM footprint. Do not enlarge a patch just to cross
the threshold. A stronger transformation would have to eliminate repeated
arithmetic or memory work and demonstrate exact EMAC, register, memory,
audio and transition equivalence; none is established here.

## Frame percentiles are constrained by the emulator clock

The configured ColdFire cadence is 3,990 executed instructions per audio
sample; sixteen samples give 63,840 instructions per frame period.
Rtos::stepOnce advances its sample clock by 1/3,990 after each guest
instruction. At the main spin PC it instead advances to the next expiry
without counting the skipped guest idle instructions. The frame latch is
cleared and frameCount increments when vector 0x41 is **acknowledged**,
not when the edge first becomes pending. WorkProfile::note attaches each
next pre-step PC to the current acknowledgement count. Thus a bucket is
ack-to-ack execution and can shift work between adjacent edge periods;
interrupt delivery latency and nested tasks can move it beyond 63,840.

Among 5,599 complete buckets, 1,346 (24.0%) contain at least 63,800
instructions; 638 reach or exceed 63,840. Stock p95 is 63,845, p99
63,849 and max 63,951. Many other buckets cluster around 31,9xx
instructions because emulated idle time was fast-forwarded. The p95/p99
values close to 63,840 are largely a property of this configured clock
and bucketing. Their lack of movement in the pilot patch does not prove
unchanged ISR duration, missed-deadline rate, or physical headroom.
Likewise the 0.614% reduction in total instructions was concentrated in
the background analysis path; it is not a CPU cycle saving measurement.

For a deadline-oriented follow-up, add a minimal observer at frame-edge
assertion, vector-0x41 acknowledgement, ISR entry and final RTE, recording
sample timestamp, PC, task/TCB, and guest instruction count. Track nesting
and a late/pending edge explicitly. Report edge-to-ack latency, ISR
entry-to-exit instructions and any intervening preemption separately from
ack-to-ack work and backlog. The observer should write host-side data only.
Negative controls are stock with profiling off versus a no-op observer and
stock A/A with the full observer: exact audio, guest state and PC totals
must match. Varying the emulator --ips setting can test whether the p95
cluster follows the configured budget, but that is a model sensitivity
experiment, not a new hardware measurement.

## DSP polling and idle accounting

The two DSPs have independent budgets and their instruction counts must
not be added to ColdFire counts. In the stock run, core 0 has 362,944,139
interpreter-work counts and 9,789,187 separately skipped idle counts;
core 1 has 196,331,752 work and 176,401,574 skipped. Work plus skipped
is 372,733,326 for **each** core, near the configured
5,600 × 16 × 4,160 budget after partial boundaries. The per-PC work map
still includes executed polling: core 0 P:004b..0053 contributes
173,568,245 counts (47.82% of its recorded work), and core 1 P:0057
contributes 47,819,237 (24.36% of its work). The former repeatedly
reads/tests DSR2; the latter polls port readiness. Neither number is
useful signal-processing load or a recoverable saving by itself.

DSP idleStep advances the hardware-model instruction counter, and the
profiler subtracts that skipped part. REP iterations and interrupt-entry
increments are charged to the interpreter-entry PC. A DSP instruction
table is therefore a locator for investigation, not an exact
instruction-by-instruction timing trace. No DSP saving follows from the
ColdFire analysis patch.

## Bounded follow-up and stopping gate

Wait for assignment B's representative overload and control-change
fixtures, then run the same hashed stock image and profiler over each.
Preserve exclusive scopes, an unattributed remainder, per-frame
distributions and audio/activity checks. Add the host-side ISR observer
above before ranking deadline opportunities. For either small loop
candidate, use isolated differential state tests across every loop
length/path and stress values, then one stock/candidate/stock run on the
same fixture. Include relocated cave PCs in the candidate count and verify
audio and guest-state neutrality. Proceed to hardware timing only if the
candidate produces a repeatable relevant saving with no state regression.
If these loops remain below 0.5% total and do not improve measured
ISR-specific work, stop and look for a larger verified invariant.
