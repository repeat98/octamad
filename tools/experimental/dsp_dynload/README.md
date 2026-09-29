# DSP dynamic loading: experimental tools

This is a separate experiment on `codex/dsp-dynload`. It is not imported by
any shipping build and is not part of the Analog BD PR. The separate
`dsp-dynload-transport` test remix exercises firmware DMA and a bounded P staging
area; it does not switch or execute uploaded code. The separate
`dsp-dynload` remix now connects a real P allocator, verified uploads and
stock dispatch binding for three stock effects and Character. It still retains
static originals as fallback; see the runtime boundary and evidence below. The earlier source-packet loader remains on `codex/analog-bd-dynamic-engines`.
Do not merge that loader into the Analog BD PR or use it as a general FX ABI.

## Package/planner model

This section describes the broader host-side model. The connected firmware
backend is narrower and is documented under Real firmware residency runtime.

- Immutable version-1 packages: 24-bit P/X/Y sections, aligned placement,
  explicit full-word relocations, init/proc offsets, source/content identities,
  per-instance r7 state size and a processing allowance with evidence.
- Buffer-free insert ABI (r7 state only; no per-instance delay lines). Source machines, servers, shared aliases and module-specific
  firmware hooks need separate contracts; they are not silently admitted.
- A two-core planner. Tracks 1–4 belong to core 1, tracks 5–8 to core 0. Each
  core shares a package's code and immutable tables across instances; state and
  processing costs remain per instance. The caller supplies private pool ranges
  and remaining processing allowances after resident system/loader overhead.
  There are intentionally no purportedly safe hardware pool defaults.
- Preparation reserves the entire transition without touching the active Part.
  Unchanged instances retain their code placement and state. A changed continuity
  token requests new state even when the algorithm stays the same.
- Admission distinguishes steady memory exhaustion, steady processing exhaustion,
  temporary transition memory/fragmentation and transition processing exhaustion.
  Refusal leaves the running Part intact. `Refused.modal` supplies proposed UI
  text; the isolated firmware probe has existing-control guards and a UI-task modal, but uses a diagnostic backend.
- Both affected cores must acknowledge preparation before a model commit. A
  cancelled or foreign plan cannot commit. Outgoing allocations remain reserved
  until explicit transition retirement; another transition is refused meanwhile.
  Acknowledgements and retirement are host-model operations, not DSP transport.
- Source-derived relocation candidates for Spectrum and Character. The builder
  keeps the original DSP sources, places their manifest tables in P exactly as
  the ordinary build supports, and uses the existing assembler round-trip audit.
  Relocated packages must match independent assembly at four different origins.
  These are FX1 candidates because those modules intentionally bypass on FX2.

Run from the repository root:

```sh
python3 -m unittest tools.experimental.dsp_dynload.test_loader -v
python3 -m tools.experimental.dsp_dynload.build_candidates
python3 -m tools.experimental.dsp_dynload.verify_audio
```

Generated packages are under `out/dsp-dynload/`. They contain assembled
module code, never copied stock firmware. The candidates have UNKNOWN processing
bounds, and the planner deliberately refuses their admission. A few test renders
or instruction counts must not become a claimed worst-case hardware cycle bound.
The test suite uses clearly synthetic budgets and algorithms to exercise policy.
The audio verifier rebuilds ordinary insert images and compares every mode on
both payloads against two relocated copies. Its P origins are emulator test
locations, not proposed hardware allocations. It never rewrites running code.
Run it serially with other builds in this worktree; it restores the prior image.

## Target transition contract

The firmware backend does not yet satisfy the full pre-publication contract on
all automatic/Part mutation paths; its remaining static fallback is explicit below.

1. Validate the requested Part, package identities, slot support and resource
   evidence. Account for any dependencies before allocating.
2. Check steady fit, then retain all outgoing allocations and fit the incoming
   code/tables/state in the remaining holes. Never compact live code or delay
   lines. Current first-fit placement is conservative and can reject a layout
   that a more expensive packer could fit.
3. Transport uploads and verifies staged data without overwriting live
   allocations. Acknowledgement must cover both code and staged dispatch/state.
4. A future audio scheduler switches affected cores at the same agreed block
   boundary, retaining outgoing instances for the crossfade/tail policy.
5. Retire old allocations only when outgoing processing has actually finished.
   The current planner serializes transitions, including their retirement.

The planner pessimistically sums old/new instance processing during overlap,
counting unchanged instances once. Its available allowance must already reserve
mix/crossfade, transport, interrupts and system overhead. It does not establish
those costs. Tail completion can be arbitrarily long for feedback effects; the
scheduler needs an explicit, bounded policy. No hard live switch is silently
substituted when overlap does not fit.

For an unexpected Part selection that cannot be prepared while playing, retain
the current Part and explain the refusal. A stopped load can be a separate
explicit operation later. Preloading the next Part, or the union of a bank's
Parts when it fits, reduces the number of transitions needing transfers. Neither
strategy guarantees arbitrary instantaneous switches at a full DSP budget.

## Remaining integration requirements

- Measure and declare resident P/X/Y ranges and cycle reserves on both cores;
  stock memory that merely looks empty at boot is not an available pool.
- Measure worst-case processing for candidates, including all modes, parameters,
  sample-block splits and instance positions. Preserve existing sound oracles.
- Verify relocation through execution on both payloads, preserving r7 state and
  firmware register contracts. Four assembly origins are useful evidence, not
  proof that every address is executable or every absolute dependency relocated.
- Extend the implemented bounded P transport to the remaining ABI resources,
  with coordinated activation for different algorithms. Verified per-core
  relocation does not prove an atomic cross-core hardware switch.
- Extend the FX/manual-Part, queued/stopped pattern and project-load guards to
  chain restart, Part copy/reload/reset and background bank reload. The observer
  remains a fallback for those uncovered paths; see the publication route audit.
- Measure dry/main audio during switching, retained tails, repeated edits and
  failed transfers under full audio load; qualify on hardware.
- Extend the ABI with per-instance delay-buffer sizes/alignment and lifecycle
  requirements before admitting reverbs or other buffered inserts.
- Add persistent code caching, explicit dependencies and a single backing-store
  allocator for shared P/X/Y aliases before supporting bus modules. Existing
  module hook/ID conflicts still apply; a big DSP catalogue does not resolve them.

This work can reduce resident DSP memory. Unselected algorithms ordinarily do
not run already; unloading their code by itself saves no processing. Processing
savings require separate measured changes, such as safely skipping inactive
voices after their state and tails settle, or sharing bus processing by design.

## Local evidence (29 September 2026)

- Package/planner unit suite: 12 tests passed, including 200 seeded Part
  transitions, all sixteen FX slots, no overwrite of outgoing allocations,
  per-core limits, alignment, state exhaustion, cancellation and stale plans.
- Candidate assembly: Spectrum 1,391 P words / 11 relocations; Character 932 P
  words / 3 relocations. Both match independent assembly at four origins.
- Audio comparison: 14 cases (four Spectrum modes and three Character modes,
  each on payload A and B), 4,096 stereo frames per case. Both relocated copies
  match the ordinary build exactly. These test addresses are emulator-only;
  this does not qualify them as safe hardware program memory.
- `OT_PROJECT=out/analog-bassdrum/ui-fixture make check REMIX=analog-bassdrum`:
  all runnable baseline gates passed, including all four module image gates.
  This checks the unchanged shipping path; it does not exercise a firmware
  integration of this planner. The default QUICK policy was used.
- `python3 tools/verify/verify_docs.py`: passed.

Logs and generated JSON/audio evidence: `out/dsp-dynload/`. This initial foundation did not include firmware integration. The transport
and selection-guard additions below have since been measured; the native
allocator and runtime additions are described below. Seamless relocation has
emulator evidence; reclaiming original code still requires pre-publication
guards on the remaining automatic and Part mutation paths.

## Firmware transport probe

`modules/dsp-dynload-transport/` appends transfers to the firmware frame-DMA
state machine, on both cores. `make check REMIX=dsp-dynload-transport` includes
its native controller and (with OT_PROJECT or DL_CARD) port gates. The port
must acknowledge PROBE and STAGE on both cores, keep advancing frames, show
a deferred UI message, and contain the exact staged words with the rest of
the reserved table unchanged. A P dump is an emulator observation; the DSP
does not yet perform independent readback verification before execution.
No EXEC/COMMIT opcode exists. These tests do not prove seamless effect changes.

## Stock candidates

`python3 -m tools.experimental.dsp_dynload.stock_catalog` extracts all 13
stock DSP algorithms separately for A and B (6,158 P words per core), checks
their native init/proc entries, and writes the generated candidates only under
ignored `out/`. DELAY is marked ColdFire. These candidates are deliberately
not admitted as relocatable v1 packages: their X/Y tables, instance buffers,
shared helpers and native P placement need adapters. PLATE/DARK conservatively
retain SPRING as a dependency; a future helper-level split can reduce that
reservation once qualified. This prevents a new module from silently taking
memory that a selected stock effect still uses.


## Existing selection paths

The transport test remix now guards the original stock FX1/FX2 and manual
Part-selection setters before they write saved or live state. There are no new
controls. An asynchronous backend interface supports prepare, poll, cancel and a post-setter commit notification;
the current diagnostic adapter only admits the resident stock selection.
Nine port scenarios qualify refusal, deferred replay and stale-context
cancellation, including pattern/Part linkage. See the module README for exact
seams and the automatic/project-load paths still missing. Do not confuse this
adapter with a connected, working dynamic allocator.

### Selection-guard evidence (29 September 2026)

- `DL_CARD=out/analog-bassdrum/ui-gate/card.img make check REMIX=dsp-dynload-transport`: all runnable checks passed, including both image gates and nine selector scenarios. The general `verify_set` gate skipped because no `OT_PROJECT` was supplied; loader gates used the explicit card fixture.
- `python3 -m unittest tools.experimental.dsp_dynload.test_loader`: 12 tests passed.
- `python3 modules/dsp-dynload-transport/generate.py --check`: generated assembly matched.
- `python3 tools/verify/verify_docs.py`: 46 modules, 37 remixes, zero problems.

Full check log: `out/dsp-dynload/selection-final-check.log`. Refusal and
readiness in the selector cases are injected diagnostic results. These results
do not qualify actual allocation, automatic Part changes or audio continuity.

## Real firmware residency runtime

The isolated `dsp-dynload` remix links the freestanding C allocator and
transport backend instead of the diagnostic selector adapter. It allocates code
once per algorithm/core in a build-owned 1,344-word P arena, uploads at most 24
words per transaction, verifies DSP readback sums, then changes init/proc dispatch
at that core's frame head. Outgoing memory remains reserved until unbind is
acknowledged. Failed uploads and cancelled selections drain and roll back;
failed unbinds retain their allocations and retry.

EQUALIZER, PHASER and COMPRESSOR are extracted from the user's stock image at
build time. Character comes from its unchanged source. External relative helper
branches and DO loop endpoints are relocated; their dependencies stay pinned.
Other stock effects remain resident. This runtime does not allocate delay lines,
shared X/Y storage, or new source-engine state. The earlier Python planner's
broader resource model must not be confused with this narrower firmware backend.

Existing FX/manual Part guards use real capacity results. Automatic queued and
stopped pattern requests now prepare before publication, and LOAD PROJECT is
admitted before its command is posted. Capacity refusal preserves the current
pattern/project on those routes. See
[`PUBLICATION.md`](../../../modules/dsp-dynload/PUBLICATION.md) for the seams.

**Static originals remain required for uncovered routes:** chain restart/stop,
Part copy/reload/reset, background bank reload and new project creation. The
observer still follows those routes after publication. This experiment does not
yet reclaim their original spans or permit an arbitrary catalogue size.

Rebinding identical code preserves r7 state and the existing processing schedule.
It needs no extra old/new algorithm instance, and unloading unused code alone
saves no processing. Hardware loader overhead, different-sound transitions and
tail policies remain unqualified. The runtime is not a flash candidate.

Local runtime evidence:

- Native allocator/controller/backend checks cover actual capacity refusal,
  sharing, 2,000 seeded transitions, stale acknowledgements, cancellation,
  readback failures and retaining memory after an unacknowledged unbind.
- 72 exact stereo comparisons: four algorithms, both cores, three sub-block
  lengths and three parameter sets. This caught a missing PHASER external-helper
  relocation before firmware use.
- Seven port scenarios passed: both cores, Character, cancellation, real memory
  exhaustion, manual Part application and automatic application. Uploaded P words
  and dispatch entries are verified, not just the controller's counters.
- Actual LOAD PROJECT populated both cores from saved EQ/Character assignments,
  without chooser calls or effect injection. Exact uploaded code and dispatch
  matched, with no controller or transport errors.
- Continuous eight-track stereo chain output and the main capture matched static
  execution sample-for-sample through four automatic Part applications, including
  upload, binding and retirement (65,760 samples/channel). This qualifies the
  tested relocation paths, not arbitrary seamless algorithm changes.

Run `OT_PROJECT=<fixture> make check REMIX=dsp-dynload`. The gates normalize
owned fixture copies; they never edit the source project. Reports, captures and
logs are under `out/dsp-dynload/`. See
[`modules/dsp-dynload/README.md`](../../../modules/dsp-dynload/README.md)
for the transport, ABI and static-fallback limitations.

Queued-pattern evidence: `OT_PROJECT=<fixture> python3 -m tools.experimental.dsp_dynload.verify_pattern_audio` sends a MIDI program
change to the running sequencer. Both the pattern and Part must actually change.
The eight stereo chains and main capture matched static execution exactly over
8,192 frames, with no residency/transport errors. This exercises the normal
queued pattern path; the new guard prepares before publication and defers the
change if preparation misses its deadline.

Publication-guard follow-up: the full runtime check now passes all seven image
gates, including actual memory-full project/pattern refusal and superseded
stopped requests. The extra refusal run pins allocator failures as well as
unchanged state; logs are `publication-full-check.log` and
`publication-capacity-proof.log` under `out/dsp-dynload/`. See the runtime
module's [route audit](../../../modules/dsp-dynload/PUBLICATION.md) for the
remaining barriers to reclaiming original code.
