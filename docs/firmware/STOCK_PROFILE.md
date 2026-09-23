# Stock-firmware performance pilot — 23 September 2026

Status: software profiling and an opt-in optimization candidate; the milestone
is NOT complete until behavioral acceptance and a hardware-measured saving.
The operator was away from the instrument. No hardware was flashed or measured.

## Reproducible workload and measurement

Use `tools/harness/benchmark_stock_analysis.py` after the module's differential
gate, as documented in [STOCK ANALYSIS FAST](../../modules/stock-analysis-fast/README.md).
The checked fixture is `out/polyphony-benchmark-1100/mono.card.img`, set
`OCTABAM`, project `POLYBENCH`: eight FLEX tracks, a looping 440 Hz stereo
sample, TSTR OFF, neutral pitch, forward rate, 120 BPM, trigs on steps 1–4,
master disabled. Inherited FX2 settings are DELAY on T1–T7 and PLATE REV on
T8; this is not a no-effects fixture. Other template parameters are retained.
It does not cover STATIC streaming, Pickup/recorders, TSTR NORMAL/BEAT,
scene morphs, parameter changes, or the user's overload project.

The long window is 5,600 16-sample frames (~2.032 seconds) after a 20-second
emulated project-loading phase. Hardware-equivalent long-duration stress is
still required. An earlier 1,400-frame pilot was too short to catch a model bug.

`ot_emu --work-profile PREFIX` emits exact ColdFire PC counts, per-core DSP
PC counts, and per-frame accounting. Boot/loading are excluded. Both boundary
buckets are conservatively excluded from percentiles (5,599 complete buckets).
The table reader checks frame/PC totals, contiguous frame IDs, and the frame
denominator. P95/P99 use nearest rank. Total instructions / requested frames
and the mean of complete buckets are deliberately reported separately.

These are **instructions, not CPU/DSP cycles or utilization**. The emulated
cadence is assumed: 3,990 CPU instructions/sample and 4,160 DSP
instructions/sample. Do not convert it using the hardware clock in
[CHIP](CHIP.md). Caches, bus contention, and physical deadlines are not modeled
faithfully enough for a headroom claim.

DSP accounting separates idle fast-forward, but still counts executed polls.
For example, payload A `P:004b..0053` repeatedly reads/tests DSR2; payload B
`P:0057` polls its port-ready bit. They dominate raw profiles without being
equivalent to useful signal-processing cost. REP work and interrupt-entry
counter increments are attributed to the interpreter-entry PC; the region
map is a locator, not a DSP cycle meter. No DSP saving is claimed for a CPU patch.

## Address confidence

Ranges are half-open, exclusive of callees, and verified in the extracted
1.40C disassembly. The frame ISR is `0x4000aad0..0x4000d9b0` (ends in RTE).
The older documentation's `FUN_4000c8a4` label points inside that ISR, even
inside an operand at that exact address; it is not a valid function boundary.
The profiler intentionally does not turn nearby documentation names into
function boundaries. Voice rendering is `0x40007960..0x40008f82`.

The candidate's relocated instructions must be included in sample analysis:
use `--candidate-map out/stock-profile/candidate-map.json`. Comparing only
the old address range would falsely report work as removed when it moved.

## Three actionable CPU costs

The corrected emulator gives the following exclusive costs. These are
workload-specific candidates, not universal firmware rankings or estimates
of how much of each routine can safely be removed.

| CPU scope | Instructions / frame | Share of CPU instructions |
| --- | ---: | ---: |
| Frame/control ISR | 10,719.9 | 26.21% |
| Eight-track delay | 7,664.5 | 18.74% |
| Sample analysis | 5,642.5 | 13.80% |
| Voice renderer (comparison) | 5,605.3 | 13.70% |
| Correlation search (comparison) | 2,195.9 | 5.37% |

Analysis only narrowly outranks voice rendering in this window. The shorter
pilot had more analysis activity, illustrating why the ranking depends on
the workload and observation window.

1. Frame/control ISR: inspect repeated parameter-frame packing and control
   interpolation at `0x4000cc6c..0x4000cf3e`. Candidate approach: remove
   repeated address/setup work while preserving each interpolation step.
   Caching requires correct invalidation for LFOs, scenes and live controls;
   skipping unchanged-looking values is not yet established as safe.
2. Eight-track delay, `0x400031a0..0x4000385a`: the inner sample loops at
   `0x400036xx..0x400037xx` dominate this fixture. Candidate approach:
   amortize loop/address overhead or specialize an exactly equivalent mode.
   Do not skip dry/bypassed tracks without proving delay-history, feedback,
   tails, DMA ordering and future parameter transitions remain unchanged.
3. Sample analysis, `0x40098388..0x400985ac`: recurring analysis work with a
   tractable MAC recurrence at `0x40098494..0x400984be`. This is the first
   implemented candidate because its state contract can be tested directly,
   not because all analysis work is removable. Background work reduction
   need not improve the audio interrupt's worst-case deadline.

## Candidate result (corrected emulator)

| CPU metric | Stock | Candidate |
| --- | ---: | ---: |
| Total instructions | 229,054,472 | 227,647,854 |
| Total / 5,600 frames | 40,902.58 | 40,651.40 |
| Complete-frame mean | 40,902.99 | 40,651.76 |
| Complete-frame p95 | 63,845 | 63,845 |
| Complete-frame p99 | 63,849 | 63,849 |
| Largest observed frame | 63,951 | 63,914 |

The patch removes about **251 instructions/frame, 0.614% overall** in this
fixture. Sample-analysis work including the relocated code falls from
5,642.5 to 5,391.1 instructions/frame (~4.46%). The isolated recurrence test
uses 12.297% fewer instructions across its exhaustive length/pattern matrix;
that is not the whole firmware's saving. Short lengths pay extra dispatch
overhead. Unchanged p95/p99 do not support a worst-case headroom claim.

Stock DSP interpreter-work means are 64,811.6 and 35,059.4 per frame for cores
0 and 1; separately skipped idle means are 1,747.3 and 31,499.5. These still
include executed polling and must not be reported as useful-load percentages.

Evidence is local and ignored by Git:

- Corrected A/B/A: `out/stock-profile/aba-fixed-5600/` (`result.json`, per-PC
  tables, complete-frame tables, summaries, logs, eight-slot WAV captures).
- Earlier, invalidated-model run: `out/stock-profile/aba-5600/`.
- Failing model regression: `out/stock-profile/emac-before-fix.log`.
- Corrected emulator gates: `out/stock-profile/emulator-tests-fixed.log`.
- Loop-state gate: `out/stock-profile/differential-gate.log`.

The completed A/B/A comparison passed: all three captures have identical
non-silent bytes across all eight emulator output slots, and the second
stock run reproduces the entire CPU PC-count table exactly. Both acceptance
flags in `result.json` are true.

Provenance (SHA-256):

```text
stock MAIN_OS  164f31224bf61181e3f50e7dec40df9afcae5b16dbf6e4c0d0cc5e986af0a84e
candidate     4d4c2b854278643598daf8c2a0c09feaffc6f8a6dfb4831d187e902b0087f740
card image    0c2cfde19ad942503b4dcaf8e05ad9f256e37c908ced943e3c915bf889d10c94
emulator      4fdcca2094ff91107e22042e91da985a0e8c179291512913e7ba4235ec9be749
audio         c278951ad964d63724e84689a7bcd26447f6710bd7ad15794ec0fd0046d9dae9
```

`result.json` records exact commands, source hashes at run start, the working
tree's base commit, image hashes and individual profiles. No Elektron image,
disassembly slice, or generated audio is checked into the repository.

## Validation discovery: the emulator was corrupting saved accumulators

The first uncorrected long A/B/A run repeated stock exactly but produced an
audio mismatch after about 1.63 seconds with the candidate. Its apparent
0.612% instruction reduction was not accepted as a validated optimization.
The 18,456 isolated loop cases and the short audio comparison alone were
insufficient.

A separate regression found that `accExtWrite` always used the fractional
extension-register layout. In integer mode, writing extensions changed
`ACC0`'s low bits from `0x12345678` to `0x123456ab`; reading the extensions
back returned `0xfe008900` instead of `0xfedc89ab`. Stock's frame interrupt
saves at `0x4000ac98` and restores at `0x4000d968` with MACSR=0, so this is a
real validation-path defect, independent of the proposed firmware change.

The fix preserves the integer accumulators' low 32 bits and writes the two
16-bit high halves, including signed extension. It matches the separate
integer/fractional layouts in [QEMU's EMAC helpers](https://kernel.googlesource.com/pub/scm/virt/kvm/qemu-kvm/+/refs/heads/memory/dma/target-m68k/helper.c).
Eight new assertions fail before the fix and pass afterward. The old and new
run evidence is kept in separate directories; do not mix emulator versions.

## Gates and remaining limitations

Passed: four emulator core gates (EMAC, peripherals, RTOS, DSP), including
the eight new EMAC assertions; 18,456 loop-equivalence cases; four Python
accounting tests; module build/fingerprint; remixer self-test; chooser and
slot verification. The initial profiling-on/off comparison matched exact
CPU PC counts and audio; the observer itself does not write guest state.

`make check REMIX=stock-analysis-fast` was attempted, but the cross-remix
`verify_initregs.py` stage fails while assembling unchanged Octakit
`modules/octakit/upstream/runtime/runtime.S:438` (one-byte branch displacement
overflow) for kits, mods, octakit, ok-ms, rig-kits and rig-mods. This is NOT a
full-suite pass. Firmware label checks also report SKIP because `.venv` is
absent. See `out/stock-profile/make-check.log`; fix the toolchain/source
compatibility and rerun the complete gate before treating this as releasable.

Still pending: representative real-world overload projects, additional
machine/TSTR/scene/recording workloads, extended playback, hardware behavior,
and actual hardware timing. Emulator equivalence on this fixture is not a
proof for every project or interrupt interleaving.

## Hardware acceptance — pending

No hardware CPU timing harness is claimed ready. First confirm MKI/MKII,
firmware revision, recovery path, and available measurement access. The
repository's DSP burn test is not a CPU cycle meter for this patch.

After software gates pass, use the same project and raw A/B images, with
only the reviewed hook/cave difference. Packaging must retain those image
identities; never flash a raw MAIN_OS file. Keep rescue firmware and project
backups, and follow [FLASHING](../remixer/FLASHING.md).

For an actual CPU saving, use an audited free-running timer or verified
hardware trace around the analysis work and the frame interrupt. Any timing
hooks must be identical in A and B; measure their overhead, counter wrap and
interrupt inclusion. Do not commandeer an unidentified timer/GPIO. Separate
exclusive processing time from time spent preempted. Collect A/B/A runs,
warm/cold behavior, median/p95/p99/max, missed deadlines and long audio captures
for the baseline fixture and the user's real overload project.

Audio recording alone checks behavior, not CPU savings. Analog captures will
not null bit-for-bit: align them and establish tolerance from stock A/A
repeatability before comparing B. Accept only a repeatable time saving above
measurement uncertainty, no deadline regression, and no behavioral regression.
Until then, keep the module opt-in and do not invest in broad decompilation
based on this small instruction-count result.
