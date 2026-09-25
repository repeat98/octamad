# Independent review: stock-analysis-fast

23 September 2026. Assignment G, static/read-only pass on checkout baseline
ccb11fb. Reviewed the committed candidate source, stock 1.40C raw image,
linked unit and isolated candidate image; did not build or run an emulator
while another worker owned the shared build slot. The differential-harness
source was being expanded concurrently, so this review treats its new
full-routine and mutation cases as unexecuted until a fresh log records them.
This is software validation only.

## Static byte and control-flow checks

**PASS — stock identity and placement.** The raw MAIN_OS SHA-256 is
164f31224bf61181e3f50e7dec40df9afcae5b16dbf6e4c0d0cc5e986af0a84e.
The compiled unit is 378 bytes with SHA-256
8cfff0df430449efcf006c0b75c590bed38f83cc70954de16ee2cb36c95edc0d,
matching Linked.reference. The ELF symbol analysis_fast is at
0x400d6b80; the cave is 0x400d6b80..0x400d6cfa, all zero in stock.
The isolated candidate has SHA-256
4d4c2b854278643598daf8c2a0c09feaffc6f8a6dfb4831d187e902b0087f740.
Its only differences from stock are inside that cave and the eight-byte
hook at 0x40098494..0x4009849c. The candidate map names the same cave
and validates against that candidate image hash.

**PASS — whole-instruction hook.** V4e objdump decodes the displaced stock
bytes as a four-byte MOVE.L at 0x40098494 and four-byte MSAC.L at
0x40098498. The candidate writes a six-byte absolute JMP to
0x400d6b80 and a two-byte NOP. It therefore overwrites no partial
instruction. The linked routine begins with a D7 length comparison,
copies the original 0x24-byte body from 0x40098494..0x400984b8
through .incbin, reads ACC0 into D1 after each copy, and uses the stock
SUBQ/MOVE-from-ACC/BGT sequence at the end of each group or tail
iteration. Both exits jump to the stock continuation at 0x400984be.
No JSR, stack use, or new D/A register appears in the linked disassembly.

**PASS with a scope limit — loop state reasoning.** The displaced body
does not read D7; its operations are copied in order, including the
history XOR, postincrement load and EMAC operations. Subtracting seven
before a group and one at its end produces the same D7 after eight
iterations as eight separate SUBQs. The final SUBQ precedes the
MOVE-from-ACC and BGT, as stock does. Existing
out/stock-profile/differential-gate.log records 18,456 passing isolated
cases for D/A registers, SR, captured EMAC and guarded scratch RAM.
That result supports the loop's exit-state equivalence in the emulator,
including observed CCR/X. It does not prove identical interrupt
interleaving inside the group.

**PASS — isolated map accounting.** The profile reader checks the candidate
map's image hash and adds PCs inside its 378-byte cave to the sample
analysis scope. This avoids reporting relocated instructions as a
fictional saving. The stock/candidate/stock result for one 5,600-frame
eight-FLEX workload records identical, non-silent audio, a byte-identical
stock replay PC table and 0.614% fewer total CPU instructions. The
runner relies on an earlier manual verify_stock_analysis.py invocation:
an image and matching map from a stale build could still be benchmarked
after source edits. Before each new benchmark, rerun the composition
check and record source, unit, image, map, emulator and fixture hashes.

## Risks and oracle gaps

1. **Medium: concurrent interrupt state.** The patch advances D7 by seven
   early and executes at different addresses for a different number of
   instructions. A preemption between the first and eighth copied bodies
   can expose different intermediate D7 and CCR/X to an interrupt. Stock's
   frame ISR saves/restores registers and EMAC state, but the current
   archived isolated probe did not inject an interrupt. The concurrently
   edited harness now calls selected stock EMAC save/restore instructions
   with a clobber at three instruction offsets, but it has no saved result
   yet and does not model actual interrupt entry, scheduling or every
   possible cut point. It also does not assert that all interrupt code is
   oblivious to shared scratch at 0x8000696c and above. The candidate's
   378-byte instruction footprint can change real cache behavior. These
   are unclosed hardware and model questions, not a demonstrated mismatch.
2. **Medium: full-routine and mutation evidence pending.** The saved
   differential-gate.log contains the 18,456 loop cases only. A concurrent
   uncommitted expansion of stock_analysis_probe.cpp exercises entry at
   0x40098388, 17 boundary/clamped lengths, eight table indices, four
   MACSR modes, three selected preemption offsets and a post-loop-store
   mutation. Its result needs a fresh separate log and source hash. The
   post-loop mutation checks that the full-function oracle notices one
   RAM write; it does not test sensitivity to a wrong instruction
   *inside the relocated loop*.
3. **Medium: captured state is broad but not exhaustive.** The probe
   snapshots D0–D7, A0–A7, SR, four raw accumulator low words plus
   extension pairs, MACSR and MASK. It temporarily sets MACSR to integer
   mode to read low words; in the emulator this is a direct MACSR
   assignment and does not alter the stored accumulators. The full
   function probe compares state, source, scratch and a stack window.
   It does not compare every memory address that the function could
   reach through an unexpected pointer, peripheral effects, or the
   machine's interrupt/RTOS state. Its input SR is fixed at 0x2700, and
   its RNG is deterministic; varied event schedules and initial flags
   remain to be covered.
4. **Low: stale benchmark inputs.** benchmark_stock_analysis.py requires a
   fresh output directory and records source and binary hashes. It checks
   candidate-map against the candidate image when summarizing, but it
   does not itself prove that candidate-raw.bin was just composed from
   the current source. This affects provenance if the manual preflight is
   skipped, not the archived pilot's internally consistent A/B/A result.

## Targeted negative control

Make an in-memory copy of the candidate image inside the differential
test, leave the shipping image and oracle unchanged, and replace the
first relocated MSAC.L at 0x400d6b90..0x400d6b94 with two NOPs. Run a
nonzero, mixed-sign history case with count 8 and MACSR 0x20, then
require the loop-only D/A, SR, EMAC or guarded-RAM comparison to fail.
Repeat at count 9 to exercise group-to-tail transition. This verifies
that the existing loop oracle is sensitive to a defect in the *new*
code, independently of the full-function post-loop-store control.
Neither control should be used as a benchmark candidate. The linked
disassembly verifies that 0x400d6b90 begins a four-byte MSAC.L.

## New workload regression: no-effects FLEX-8

The clean 5,600-frame A/B/A at
out/optimization/aba-no-fx-flex8-5600/result.json **fails strict
whole-capture audio identity**. Stock A and stock B are byte-identical
and each WAV has 986,969 sample frames. The candidate WAV has 986,968.
All 986,968 shared sample frames are byte-identical on all eight
24-bit output channels; there is no first differing PCM sample within
that span. The missing stock frame is index 986,968 and is nonzero on
channels 2–5. Thus this is a one-sample capture-length mismatch, not
evidence of a changed common-prefix sample value.

The explicit post-transport interval [897370, 897370 + 5599 × 16)
contains 89,584 samples in every capture. Its PCM SHA-256 is
16e61c5cab92d1f19797e00b6608d759c68526e225dceb9949cc1fc45658c7cd
for stock A, candidate and stock B. This fixed-window comparison is a
diagnostic PASS and does not waive the full-capture FAIL or establish
hardware equivalence. A fixed observation window and endpoint rule
should be specified before the next A/B/A run.

The candidate saves 1,332,256 CPU instructions (0.613%) in this
workload, but this result is **not accepted as a behavior-preserving
saving** while the capture gate fails. Aggregate PC differences are
almost entirely in sample analysis plus its cave (−1,332,258).
All PCs outside that scope net +2; within them, delay and voice
renderer scopes are unchanged and the ISR body is −3.
Per-frame CPU/DSP buckets first differ at
bucket 33, even though the PCM prefix remains identical. Both runs
reach 5,600 frame acknowledgements; the candidate reports one fewer
core-0 ESAI output frame and its final core-0 DSP instruction counter
is 3,800 lower. The likely cause is model endpoint phase: the run
stops on CPU frame acknowledgement while DSP output advances on its
own clock, and the changed CPU instruction path can stop just before
the next output sample. That is an inference from the existing
artifacts, not a proven emulator fix or a physical timing conclusion.

## Gate status and recommendation

| Gate | Status | Evidence or next action |
| --- | --- | --- |
| Hook, cave, unit fingerprint, image diff, return addresses | PASS | Read-only stock/candidate bytes and V4e disassembly above |
| Isolated loop-state differential | PASS, fresh run | 18,456 cases in out/optimization/validation-f/full-routine.log |
| Full-routine differential including boundary tests | PASS, fresh run | 3,264 cases in the same log |
| Selected guest EMAC save/restore preemption probes | PASS, limited scope | 12 cases at three offsets; synthetic guest save/restore, not full interrupt delivery |
| Post-loop-store and relocated-MAC negative controls | PASS, fresh run | Both detected; relocated MSAC-to-MAC mutation failed at counts 8 and 9 |
| Existing one-fixture non-silent A/B/A | PASS, prior run | out/stock-profile/aba-fixed-5600/result.json; workload-specific |
| No-effects FLEX-8 5,600-frame whole-capture A/B/A | FAIL | out/optimization/aba-no-fx-flex8-5600/result.json; candidate WAV one nonzero sample shorter, stock replay exact |
| Fixed 5,599-frame post-transport PCM window | PASS, diagnostic | 89,584 samples byte-identical across A/B/A; does not replace the failed whole-capture gate |
| Overshot fixed 5,600-frame post-transport PCM window | PASS, separate gate | out/optimization/aba-no-fx-flex8-overshoot-5602/; the 89,600-sample window is non-silent and byte-identical across A/B/A, verified by tools/harness/verify_audio_window.py; whole captures still differ by one terminal sample |
| Multiple seeds, silence-state and live-event schedules | SKIP | Await representative fixtures and a free emulator slot |
| Composed-remix marginal result | SKIP | Need isolated pass first, then composition checks |
| Full make check for stock-analysis-fast | FAIL, known unrelated gate | Octakit assembler failure in out/stock-profile/make-check.log |
| Hardware behavior and timing | SKIP | Operator measurement and recovery setup pending |

**Recommendation: retain this as a proposed hardware-measurement candidate,
but defer the trial and flashing.** The final F run exited zero and
out/optimization/validation-f/full-routine.log records all four fresh
candidate-specific gates above. Its probe source SHA-256 is
4f4e2ca2b28e7f15ff27fb84d212f9c6484e6f3eff2947b4d5bb76f3f2221eb8;
the test executable SHA-256 is
e0c7371e4ea0b9b08441bca860ea5df5783e356a9a026e31f38586e346678b68.
Those results supersede the at-review-start pending evidence described
above. The preemption probe covers only selected synthetic cuts. The
new no-effects workload fails strict whole-WAV identity: the candidate
capture ends one output sample earlier at the CPU-frame stop target.
This is consistent with an endpoint-phase difference in the emulator;
the artifacts do not prove its cause. A separate overshoot run captured
the explicit fixed 5,600-frame post-transport interval:
all eight PCM channels are identical across stock/candidate/stock. This
supports waveform equivalence for that fixture and window, not universal
state equivalence. Composition and the full-check blocker remain open.
No build was run as part of this independent static review, and no
hardware timing claim follows from these emulator results.
