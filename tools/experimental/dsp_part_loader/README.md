# Part-scoped DSP loading: host-side foundation

This is a separate experiment on `codex/dsp-part-loader`. It is not imported by
any shipping build and is not part of the Analog BD PR. The separate
`dsp-loader-transfer` test remix exercises firmware DMA and a bounded P staging
area; it does not switch or execute uploaded code. The earlier source-packet loader remains on `codex/analog-bd-dynamic-engines`.
Do not merge that loader into the Analog BD PR or use it as a general FX ABI.

## Implemented

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
  text; the isolated firmware transport probe has a UI-task modal, but no chooser admission hook yet.
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
python3 -m unittest tools.experimental.dsp_part_loader.test_loader -v
python3 -m tools.experimental.dsp_part_loader.build_candidates
python3 -m tools.experimental.dsp_part_loader.verify_audio
```

Generated packages are under `out/dsp-part-loader/`. They contain assembled
module code, never copied stock firmware. The candidates have UNKNOWN processing
bounds, and the planner deliberately refuses their admission. A few test renders
or instruction counts must not become a claimed worst-case hardware cycle bound.
The test suite uses clearly synthetic budgets and algorithms to exercise policy.
The audio verifier rebuilds ordinary insert images and compares every mode on
both payloads against two relocated copies. Its P origins are emulator test
locations, not proposed hardware allocations. It never rewrites running code.
Run it serially with other builds in this worktree; it restores the prior image.

## Transition contract

1. Validate the requested Part, package identities, slot support and resource
   evidence. Account for any dependencies before allocating.
2. Check steady fit, then retain all outgoing allocations and fit the incoming
   code/tables/state in the remaining holes. Never compact live code or delay
   lines. Current first-fit placement is conservative and can reject a layout
   that a more expensive packer could fit.
3. A future transport uploads and verifies staged data without overwriting live
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

## Next steps before firmware integration

- Measure and declare resident P/X/Y ranges and cycle reserves on both cores;
  stock memory that merely looks empty at boot is not an available pool.
- Measure worst-case processing for candidates, including all modes, parameters,
  sample-block splits and instance positions. Preserve existing sound oracles.
- Verify relocation through execution on both payloads, preserving r7 state and
  firmware register contracts. Four assembly origins are useful evidence, not
  proof that every address is executable or every absolute dependency relocated.
- Implement a general transfer/dispatch protocol outside source-render calls,
  with bounded per-block transfer work, integrity checks, cancellation, rollback
  and a coordinated activation handshake. Model acknowledgement alone does not
  prove an atomic cross-core hardware switch.
- Add the ColdFire selection guard and info modal before changing a saved/live
  Part. Include project load, Part copy/reload and both FX chooser paths.
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

Logs and generated JSON/audio evidence: `out/dsp-part-loader/`. No native
ColdFire planner, live transfer, modal or hardware switch has been implemented
or measured in this first slice.

## Firmware transport probe

`modules/dsp-loader-transfer/` appends transfers to the firmware frame-DMA
state machine, on both cores. `make check REMIX=dsp-loader-transfer` includes
its native controller and (with OT_PROJECT or DL_CARD) port gates. The port
must acknowledge PROBE and STAGE on both cores, keep advancing frames, show
a deferred UI message, and contain the exact staged words with the rest of
the reserved table unchanged. A P dump is an emulator observation; the DSP
does not yet perform independent readback verification before execution.
No EXEC/COMMIT opcode exists. These tests do not prove seamless effect changes.

## Stock candidates

`python3 -m tools.experimental.dsp_part_loader.stock_catalog` extracts all 13
stock DSP algorithms separately for A and B (6,158 P words per core), checks
their native init/proc entries, and writes the generated candidates only under
ignored `out/`. DELAY is marked ColdFire. These candidates are deliberately
not admitted as relocatable v1 packages: their X/Y tables, instance buffers,
shared helpers and native P placement need adapters. PLATE/DARK conservatively
retain SPRING as a dependency; a future helper-level split can reduce that
reservation once qualified. This prevents a new module from silently taking
memory that a selected stock effect still uses.
