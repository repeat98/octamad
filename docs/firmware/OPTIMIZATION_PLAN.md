# Firmware optimization: subagent execution plan

Prepared 23 September 2026. This is a future-work plan, not authorization to
start agents, flash hardware, publish firmware, or change upstream repositories.
The coordinator should dispatch the bounded assignments below when work resumes.

## Objective and starting evidence

Complete the original milestone: a representative stock-firmware profile
identifying three actionable costs, then one behavior-preserving patch with a
hardware-measured saving. Optimize the base firmware without removing features,
lowering audio quality, changing block size, or reducing modulation resolution.

Read [STOCK_PROFILE.md](STOCK_PROFILE.md) first. Its corrected-emulator pilot
establishes the following for ONE eight-track FLEX/TSTR-OFF workload:

| Exclusive CPU scope | Instructions/frame | Share |
| --- | ---: | ---: |
| Frame/control ISR | 10,719.9 | 26.21% |
| Eight-track delay | 7,664.5 | 18.74% |
| Sample analysis | 5,642.5 | 13.80% |
| Voice renderer | 5,605.3 | 13.70% |

The existing opt-in `stock-analysis-fast` candidate saves 0.614% of total CPU
instructions in that fixture. The corrected-model A/B/A captures are identical;
18,456 loop-state cases pass. Hardware saving is unknown. The emulator needed
an integer-mode accumulator-extension restoration fix before that comparison
passed. The full repository gate still has Octakit assembler failures and
missing-environment skips; see the report for exact details.

**Update, 23 September 2026:** [OPTIMIZATION_LEVERS.md](OPTIMIZATION_LEVERS.md)
finds that the stock delay runs inside the ColdFire→DSP transfer interrupt
at IPL 5, and that voice rendering runs inside the frame ISR. It also finds
that the analysis candidate's work is in a priority-1 background task. It
adds four exact fast paths on the level-5 path, estimated at ~5,900
instructions per frame (15%) on the no-FX eight-track fixture:

- L1: the delay's dry-only track;
- L2: the renderer's unity-rate phase step;
- L3: a division loop that returns its input;
- L4: an early exit in `0x400068e4`.

It also adds a DSP map. Assignments D and E below take those as their
first candidates.

Planning hypothesis: aim for about 5% total CPU instruction reduction, investigate
3–8%, and treat 10–15% as a stretch—not measured potential, a promise, or a quota.
Do not manufacture savings to meet a target. Actual deadline headroom outranks
average instruction reductions. CPU savings do not imply DSP savings.

## Coordinator rules and concurrency

Use at most three workers plus the coordinator. Follow current repository
instructions, starting with `PLAN.md`, `CLAUDE.md`, `CONTRIBUTING.md`, and the
relevant sections of `docs/remixer/MODULES.md` and `PLACEMENT.md`.

- Resolve the real checkout: currently `/home/jannikassfalg/octamad` in Ubuntu
  WSL, also reachable as `\\wsl.localhost\Ubuntu\home\jannikassfalg\octamad`.
  Do not assume the Windows desktop's nominal cwd is the active repository.
- Preserve the existing dirty working tree. The pilot's new files are partly
  untracked: HEAD alone is NOT the baseline. Inventory and hash tracked edits,
  relevant untracked sources, firmware, emulator, compiler and fixture inputs.
  Do not reset, stash, overwrite, or commit the user's work automatically.
- Assign disjoint source ownership explicitly. The coordinator alone edits
  shared integration files (`Makefile`, CMake targets, common profiler interfaces,
  and shared registry/self-test expectations), unless ownership is handed off.
- **Only one build owner at a time.** `make bus`, `make check`, CMake builds and
  several verification scripts overwrite shared `out/mainos_bus.bin`, linked
  units, runtimes, or emulator executables. A unique log directory does not
  isolate those writes. Workers request a build slot; the coordinator builds
  and snapshots the exact image, executable, symbols and placement map for them.
- Agents may analyze immutable snapshots concurrently. Never rebuild a binary
  while another agent is using it as its reference. Use new run directories
  such as `out/optimization/<task-id>/<run-id>/`; refuse accidental overwrites.
  Keep resource-intensive emulator runs serial initially.
- Every new emulator-semantic fix gets a failing regression, a separate review,
  and a fresh baseline. Do not compare A on one model with B on another.
- Never commit or upload Elektron binaries, extracted routines, firmware slices,
  or disassembly dumps. Keep generated firmware-derived evidence in ignored
  `out/`; record addresses, hashes, descriptions and original patch sources.
- Do not edit `modules/*/upstream/` or move submodule pins as a local workaround.
  Escalate an upstream change through the repository's contribution process.
  No external PR, message, release, or flash is implied by this plan.

## Execution order

| Wave | Workers | Completion gate |
| --- | --- | --- |
| 0 | Coordinator freezes the pilot baseline and assigns file ownership | Reproducible source/artifact identity |
| 1 | A: validation; B: workloads; C: profiling audit | Trusted model, explicit fixtures, verified rankings |
| 2 | D: control-path candidate; E: delay candidate; F: analysis candidate | At most one independently tested candidate per worker |
| 3 | G: independent reviewer; coordinator integrates candidates individually | Correctness, system A/B/A, relevant full-suite gates |
| 4 | H: hardware measurement specification, then operator-assisted tests | One accepted hardware-measured saving |
| 5 | Coordinator decides whether to expand; optional I: DSP investigation | Evidence justifies next work, or stop |

H's read-only measurement specification can be prepared in an available slot
before hardware is available. Wave-2 agents may map code early, but performance
verdicts depend on Wave 1. Do not delay the first hardware test to chase a large
bundle of speculative optimizations. The existing analysis candidate can go to
G/H first if it passes the expanded software gates.

## Dispatchable assignments

Each brief below is a bounded task. Append the common handoff contract at the
end of this document when dispatching it. Proposed new file names are ownership
boundaries, not a requirement to create empty scaffolding.

### A — Establish trustworthy validation and remove gate blockers

**Mission:** reproduce the corrected pilot and distinguish environmental,
emulator, candidate and unrelated-module failures.

Read the pilot report, `tools/emu/ot_emu/test_emac.cpp`, `v4e.cpp`, the analysis
probe/gate, and `out/stock-profile/make-check.log` when available. Own new
validation notes/tests under an assigned `validation` namespace; request
exclusive ownership before editing emulator semantics or setup scripts.

1. Reproduce the four emulator gates, eight new EMAC assertions, accounting
   tests and 18,456 analysis-loop cases on the frozen source snapshot.
2. Add targeted save/restore and preemption tests for all four accumulators,
   extensions, MACSR, MASK, CCR/X and saved registers. Exercise integer and
   fractional modes and nonzero extension bits; compare actual guest execution,
   not only a host-language arithmetic rewrite.
3. Reproduce the Octakit one-byte branch displacement failure in isolation.
   Record assembler identity and flags; determine whether the supported
   toolchain solves it. Do not bypass the gate, relax expected bytes, or edit
   upstream sources to make the suite green. Request coordinator approval for
   a narrowly scoped setup/build fix. Build-system changes require the existing
   reference-hash workflow and review of any changed artifact identities.
4. Resolve missing `.venv` checks using the documented setup if authorized and
   feasible; otherwise report them as SKIP, never PASS. Rerun the full selected
   remix gate once blockers are resolved.

**Deliverable:** failure/pass/skip inventory, minimal reproductions, regression
tests, toolchain identity and a trustworthy baseline recipe. Stop expanding
into unrelated emulator features. An unresolved gate is a recorded blocker,
not grounds to weaken acceptance.

### B — Build a controlled, representative workload suite

**Mission:** stop optimizing a single inherited template by accident.

Own proposed `tools/harness/stock_workloads.py` and its dedicated tests. Reuse
the existing project/card helpers, but work only on new copies and reread the
effective project state after transport starts. Some firmware paths reapply
saved FX settings; stored bytes alone are not sufficient evidence of workload.

Define named cases with explicit machine, FX1/FX2, Part, sample format, rate,
pitch, TSTR, track level, master, scene/LFO and input settings. Hash the resulting
card, sample assets, event schedule and relevant source project files.

Minimum staged coverage (not a full Cartesian product):

- Preserve the exact pilot card as a regression fixture, including its seven
  DELAY slots and T8 PLATE REV. Separately create an explicitly no-effects case.
- Idle/no active voices and 1/4/8 active FLEX tracks, with TSTR OFF.
- Matched FLEX and STATIC playback; verify that the intended storage path
  actually runs and label missing ATA/DMA behavior as a model limitation.
- TSTR NORMAL/BEAT, both stereo and mono, forward/reverse and non-neutral
  pitch/rate, representative sample formats, loop/slice boundaries and retrigs.
- Controlled delay fixtures: dry and wet, feedback/tails, freeze and live
  parameter/tempo changes. Include transitions from nonzero history.
- Live controls: LFOs, parameter locks, scene/crossfader movement, Part/pattern
  changes and external MIDI clock/events with reproducible event timing.
- Recorder/Pickup concurrency where the model supports it, plus a copy of the
  user's actual overload project once supplied. Never mark unavailable cases
  tested; name them as pending.

Use a short smoke tier, a >=30-second musical regression tier and a >=5-minute
soak tier for finalists, subject to measured host cost. Test multiple trigger,
loop and pattern boundaries. Scale coverage in stages rather than launching
every combination immediately.

**Deliverable:** fixture generator/tests and a workload manifest with explicit
expected activity checks. No firmware optimization edits and no source-project
mutations. Silence cases need expected state/activity checks; a zero WAV is not
evidence that a playback path worked.

### C — Audit attribution and rank real opportunities

**Mission:** produce an address-verified, workload-specific cost map and
separate average work, critical-path work, polls and scheduling artifacts.

Own a new profiling findings document and proposed profiler extensions only
after coordinator handoff. Read `profile_stock.py`, `work_profile.h`, RTOS and
DSP accounting, and `STOCK_PROFILE.md`'s address corrections.

1. Verify instruction boundaries against the exact image. Frame ISR:
   `0x4000aad0..0x4000d9b0`; delay: `0x400031a0..0x4000385a`; analysis:
   `0x40098388..0x400985ac`; renderer: `0x40007960..0x40008f82`.
   Labels/decompiler output are hypotheses, not boundary authority.
2. Profile B's cases. Report exclusive counts separately from inclusive costs
   and preserve an unattributed remainder. Partition ISR versus background
   task work, repeated arithmetic, memory/packing work and polling.
3. Audit the frame statistics: the model advances time per instruction, and
   `3990 * 16 = 63,840`, close to the observed CPU p95/p99. Determine how this
   configured cadence, interrupt entry and idle skipping constrain buckets.
   Do not present an emulator-imposed ceiling as measured execution time or
   unchanged p95 as proof of unchanged physical deadline margin.
4. For deadline analysis, distinguish per-frame total work from ISR entry-to-
   exit work, preemption, late service and backlog. Propose minimal observers
   and negative controls; prove profiling-on/off guest-state/audio neutrality.
5. Include relocated cave instructions and REP accounting. Separate executed
   polling from skipped idle on each DSP core; CPU/DSP counts are different
   units and must not be added together.

**Deliverable:** three prioritized actionable costs PER workload family, each
with verified scope, call frequency, locality, possible removable work, risk,
and a conservative whole-workload estimate. Use `scope share * local saving`
as an estimate only; a large routine is not automatically optimizable.

### D — One frame/control-path optimization candidate

**Mission:** reduce repeated address/setup or packing work while preserving
every parameter update and interpolation step.

Start with the frame ISR and `0x4000cc6c..0x4000cf3e`. Own a new opt-in module
`modules/stock-control-fast/`, matching remix and dedicated probe/gate. Coordinate
hook ownership with other modules; request shared integration edits from root.

First produce a block/state contract and measured hotspot justification. Then
implement at most ONE small transformation: address hoisting, redundant
load/setup removal, or carefully bounded loop unrolling. Do not introduce
parameter caching or event-driven recomputation in this first task without
separately proving all writers and invalidation paths.

First candidates (23 Sep 2026): L2, L3 and L4 in
[OPTIMIZATION_LEVERS.md](OPTIMIZATION_LEVERS.md) §2. Each is an exact
fast path with a local, checkable precondition in the frame ISR's call
tree, estimated at 290–1,000 instructions per frame each. None caches
anything across frames. That document also records why an LFO depth-0
skip and a smoothing memo are not exact.

Test all tracks/Parts, dirty initial state, control extrema, LFOs, locks, scene
movement, live MIDI changes and ISR preemption. Compare outgoing parameter
frames, voice/control state, registers/flags and persistent state—not just audio.

**Deliverable:** one reviewable candidate or a documented no-go. Report mean
work, critical-path work, code size and worst tested cases; identify any small-
workload regression. No UI/features, relaxed arithmetic or sample-rate changes.

### E — One stock-delay optimization candidate

**Mission:** reduce instruction overhead in the original CPU delay without
changing its sound, history or DMA interactions.

Read `docs/firmware/COLDFIRE_DELAY.md`, the stock routine and the existing
Tape Echo probes as test-infrastructure examples—not substitute algorithms.
Own `modules/stock-delay-fast/`, matching remix and dedicated probe/gate.

Start with loop/address overhead around `0x400036xx..0x400037xx`. Preserve
operation order, fixed-point truncation/saturation, channel ordering, ring
wrap and state updates. A dry/bypassed track is not necessarily inactive:
do not omit history writes or calculations that later become audible.

First candidate (23 Sep 2026): L1 in
[OPTIMIZATION_LEVERS.md](OPTIMIZATION_LEVERS.md) §2, ahead of the unroll.
Every track pays the full 729-instruction seam per frame, DELAY or not.
A track qualifies when three things hold:

- its send, wet and feedback ramps are zero;
- its taps are zero;
- its filter is at a zero-input fixed point.

For such a track, the shortcut still does every ring write, DMA and
state update, and computes only the dry product. It gives the same bits
and saves ~500 per track. It shares Tape Echo's seam, so it must be that
hook's stock fallback, not a second detour.

Test zero/DC/impulse/noise/full-scale inputs, stereo asymmetry, all ring edges,
feedback and freeze transitions, parameter/tempo movement, dry-to-wet changes,
tails, disabled/re-enabled tracks and recorder/DMA contention where modeled.
Compare audio and ring/state memory; bound missing hardware coverage explicitly.

**Deliverable:** one local optimization with executable equivalence evidence,
or a no-go explaining why apparent overhead is semantically necessary. Do not
replace the delay engine, reduce its rate or truncate tails.

### F — Harden and evaluate the existing analysis candidate

**Mission:** determine whether `stock-analysis-fast` deserves the first hardware
trial before growing it into a larger optimization project.

Own the existing module plus its dedicated analysis probe/gate, after the
baseline is frozen. Do not simultaneously edit files owned by A or B.

1. Preserve the existing eight-way candidate as the immutable reference.
   Test the complete analysis routine and caller interactions, not only the
   recurrence loop. Include output state, scratch/guard memory and preemption.
2. Cover lengths 0..768 and caller-side clamping, all relevant source formats,
   coefficient/table selections, dirty histories and exact accumulator modes.
   Use explicit initial state and saved RNG seeds.
3. Run B's supported scenarios, emphasizing TSTR variants, retrigs and long
   sample-analysis activity. Determine whether reduced work is background
   capacity or actually lies on the overload-critical path.
4. Only if justified, compare bounded unroll factors (e.g. 2/4/8) or one other
   local transformation. Count hook/tail overhead and cave size; tiny lengths
   may lose. Choose one candidate, not a collection of unreviewed variants.

**Deliverable:** accept/adjust/reject recommendation for the first hardware
test, complete-routine equivalence evidence and whole-workload results.
Do not present the loop's 12.3% saving as total CPU headroom.

### G — Independent adversarial validation and composition review

**Mission:** challenge a candidate's correctness and measurements without being
its author. Review one candidate at a time; do not rewrite it during the review.

Use immutable source/image snapshots. Verify instruction encodings, hook
boundaries, fallthrough/return addresses, ABI, CCR/X, EMAC state, aliasing,
interrupt assumptions, scratch ownership, placement and declared claims.

Require a negative control: a deliberately incorrect scratch candidate or
test input must make the relevant gate fail. Do not mutate the shipping image
or weaken the oracle. Classify any audio/state mismatch before accepting a
model fix; rebaseline after a proven semantic-model change.

Run candidate-specific state tests, B's relevant cases, non-silent A/B/A audio,
and explicit silence-state cases. Use multiple recorded seeds/event schedules;
repeating one deterministic run proves repeatability, not broad coverage.
Compare stock with one patch first; then test the composed set and each
candidate's marginal contribution. Never add isolated percentage savings.

**Deliverable:** findings with reproductions and severity, precise PASS/FAIL/
SKIP/PENDING matrix, and an accept/reject recommendation. Full `make check`
for every touched remix remains required; known failures remain visible.

### H — Hardware measurement design and operator-assisted acceptance

**Mission:** turn the instruction-count result into a physical measurement.
Initially this is a read-only measurement specification; the operator is away
and no timing harness or device access is assumed available.

Confirm model/revision, recovery path, backups, available debug/trace/audio
access and representative projects when the user is available. Audit possible
CPU timer/trace facilities and existing ownership before proposing any hook.
Do not commandeer a timer/GPIO, disable interrupts to make numbers look better,
or substitute the DSP burn knob for a CPU measurement.

After the specification is reviewed and the user explicitly authorizes the
hardware trial, prepare distinguishable paired builds with identical minimal
measurement hooks. Verify the firmware payload difference and packaging,
counter frequency/wrap, hook overhead, preemption accounting and sample count.
Follow `docs/remixer/FLASHING.md`; raw MAIN_OS files are not update files.

Collect A/B/A over repeated musical workloads: exclusive routine time, frame
service time, median/p95/p99/max, late/missed deadlines, audio and behavior.
Record cold/warm cases and long runs. Measure analog A/A capture repeatability
before choosing audio tolerances; analog captures need not null bit-for-bit.

**Deliverable:** raw local observations, equipment/settings, uncertainty and
an acceptance verdict. Accept only repeatable savings above measurement noise,
with no correctness or deadline regression. If the gain is indistinguishable
from overhead/cache variation, report “not established,” not a rounded win.

### I — Optional, separate DSP opportunity map

**Mission:** only after CPU profiling is sound, identify useful DSP processing
costs on both cores and distinguish them from waits and hardware pacing.

Read `docs/firmware/DSP.md`, `CHIP.md` and current DSP-accounting limitations.
Use explicit core/track/FX-slot workloads and validated instruction encodings.
Start read-only; deliver a cost map and one bounded proposed experiment.
Do not remove polling loops, change cross-core handshakes or rewrite DSP
algorithms in this assignment. Require independent DSP hardware measurement
before claiming DSP headroom; CPU work is not evidence for it.

## Common handoff contract

Every worker returns the following, including for a failed/no-go experiment:

```text
Task ID / hypothesis / scope:
Baseline: commit + dirty-source manifest, firmware/emulator/toolchain hashes
Ownership: files changed; shared changes requested; artifacts created
Workload: card/sample/event hashes; settings; activity checks; seed; duration
Candidate: exact hook/cave changes; placement map; code/RAM cost; image hash
Correctness: oracle, cases, negative control, mismatches, missing coverage
Performance: units, denominator, exclusive/inclusive scope, mean/tails,
             polls/idle/preemption treatment, per-workload results
Reproduction: exact commands, exit codes, logs, result paths
Verdict: pass / fail / inconclusive / pending hardware (with reasons)
Next bounded action or specific coordinator/user dependency:
```

Do not silently change the baseline, fixture or statistic after seeing the
result. Retain failed runs. Never relabel a skipped check as a successful one.

## Selection and stopping rules

- Prefer candidates with a plausible >=0.5% whole-workload instruction saving
  or a specifically demonstrated critical-path improvement. This is a triage
  preference, not a correctness waiver or a guarantee of hardware benefit.
- Report EACH workload; never average away regressions using an arbitrary
  workload mix. Explicitly justify any proposed tradeoff to the user.
- If a task cannot establish its state contract, finds new unbounded coupling,
  or needs substantial algorithm changes, stop that candidate and report a
  smaller next experiment. A rigorous no-go is a useful completed task.
- If hardware is unavailable, finish the software evidence and measurement
  specification, then mark physical acceptance pending. Do not keep generating
  speculative patches to pretend the original milestone is complete.
- After one hardware-validated patch, reassess whether the measured gain buys
  useful module capacity. Only then consider selective decompilation of the
  next evidenced hotspot; no whole-firmware decompilation project by default.

## Coordinator's first dispatch

When the user asks to begin execution: freeze the current dirty pilot baseline,
give A the validation audit, B the controlled fixture suite, and C the profiling
audit. Keep build ownership at the coordinator. Request the overload project
and hardware details asynchronously when practical; synthetic software work
can proceed without them, but cannot stand in for their eventual validation.
