# Machinedrum Machine: implementation plan

Status: revised proposal, 23 September 2026. Based on the local Octamad
checkout at `3b5a2eb66930225f914a369fbfd499dd763d7dcd`. No Machinedrum
engine has been extracted, ported, benchmarked, or hardware-qualified by
this work. Phase 0 (inputs and subsystem map) is recorded in section 12.

## 1. Confirmed target

Add one **MACHINEDRUM** audio-machine choice to Octamad, delivered as
`modules/machinedrum/` and selected by `remixes/machinedrum.py`.

**Every OT track assigned MACHINEDRUM hosts an independent, complete
16-part Machinedrum sound module.** Each internal part can select from the
full supported MD engine catalog and has its own parameters, voice state,
level, pan, mute, and modulation. All 16 parts can sound within that single
OT track. Two internal parts may use the same engine with different settings.

Incoming MIDI must be able to trigger individual internal parts. The user
initially selected direct OT sequencing and is now considering an embedded
16-part sequencer. **The sequencing choice is open; the recommendation is an
embedded 16-part pattern sequencer synchronized to OT clock/transport.**
Section 6 compares both approaches. The instance produces a stereo mix that
enters its parent OT track's normal processing and routing.

The user permits a limit on simultaneously assigned MACHINEDRUM machines to
fit CPU/DSP resources. The initial experimental remix should allow at most
one instance; that is a development cap, not evidence that even one complete
instance fits. Increase it only after measuring the full workload. There is
no requirement for eight simultaneous Machinedrum instances.

### Decisions (23 September 2026, the user)

- **One Machinedrum per OT Part.** At most one track of a Part is
  MACHINEDRUM. It may be any track, and it may be a different track in
  another Part. A Part change moves the instance; its voices restart, as
  they do on any machine change. Because either core can host it, both
  cores must afford an MD track. The code lives in the shared window, which
  both cores reach, so only the voice state moves.
- **The Machinedrum remix drops the bus servers** (BusVerb, BusDelay and
  the SEND clients) to free the shared window for MD code and state. The
  stock FX1/FX2 effects stay. Composing with every other remix is not a
  goal.
- **The MD master effects are out of scope**: the delay, reverb, EQ and
  dynamics that CTR-RE/GB/EQ/DX drive. The parent track's OT FX process the
  instance's stereo mix. Per-part processing (the MD FX page) stays.

For example, T1 can host MD instance A with a kick on internal part 1, snare
on part 2, and hats on parts 3/4. T2 can host an independent instance B only
if the qualified instance cap and resource placement permit it.

The intended result is original MD behavior. Direct reuse of original DSP
routines/subsystems is the first route. Approximate recreations require a
separate scope decision.

## 2. Sound-module coverage

The first firmware target is MD OS 1.63. Inventory every engine, parameter,
table, sample asset, initialization path, and shared dependency.

| Family | Sound machines | Available to |
|---|---:|---|
| TRX | 14 | Every internal part of every instance |
| EFM | 8 | Every internal part of every instance |
| E12 | 16 | Every internal part of every instance |
| P-I | 9 | Every internal part of every instance |
| GND | 3 | Every internal part; EMPTY is separate |

These 50 core sound engines form the initial synthesis catalog. They are
choices for 16 independently configured parts, not 50 mandatory concurrent
voices. The counts and IDs are read from the OS 1.63 descriptor table
(section 12); an earlier draft said TRX 13 and 49 engines, ❌.

A complete sound-module target also covers MD per-part processing, routing,
LFOs and mute/trigger relationships. They belong to each instance. The MD
master effects (delay, reverb, EQ, dynamics) are out of scope (section 1,
decisions); the per-part delay/reverb sends on the ROUTE page have no
destination and are hidden. The OT's own FX slots
process the resulting stereo mix and remain available within the qualified
budget. A synth-only milestone must be labelled as such.

Track UW ROM/RAM, input-processing, MIDI/control machines, and unofficial
firmware engines separately in a compatibility matrix. Identify their
additional data, routing, and state requirements explicitly; completing the
50-engine catalog alone does not establish a complete MD UW implementation.
The sequencing options and their tradeoffs are recorded in section 6.
Reproducing MD song mode and the original panel workflow is outside the
current scope.

## 3. Existing foundations and evidence

**Checked in the local checkout:**

- `modules/poly-machine/manifest.py` adds a selectable, persisted machine
  with raw type 5, aliases it to FLEX at stock configuration boundaries, and
  hooks rendering/retriggering. Its docs report emulator qualification with
  hardware qualification pending. Reuse its registration and persistence
  knowledge; MD has its own part allocator and rendering behavior.
- The MD 1.63 update SysEx exists in
  `base_firmware/Elektron_SPS1-1UW_OS1.63/`; OT 1.40C is also present.
  Presence does not establish completeness of MD code or sample assets.
  Section 12 records what the update does and does not contain.
- The remixer provides linked ColdFire units, DSP placement, symbol-based
  detours, collision checks, DSP rendering, and the full OT emulator.
  It has no general nested-instrument or runtime instance-admission API.
- `docs/firmware/PARAM_PAGES.md` documents six playback destinations in
  the stock step-lock/scene format. Playback setup parameters follow a
  separate path. Those six slots cannot by themselves represent locks for
  16 internal parts, even before adding MD parameters 7 and 8.
- `docs/firmware/CHIP.md` records local hardware timing and memory evidence.
  The ColdFire DRAM reserve is not directly addressable DSP memory. Historical
  headroom from an effects remix does not establish MD capacity.

**Checked in the supplied emulator repositories:**

- Gearmulator runs original firmware on emulated processors. The MD fork
  models a ColdFire CPU and two DSP56303s with a producer/mixer pipeline.
  OT uses two cores of a DSP56721. Related instruction sets make native
  reuse plausible; peripheral, memory, and calling conventions need proof.
- `source/elektron/md/mdLib/`, especially `mdhardware.*`, `mddsp.*`,
  `mdautomation.*`, and the firmware tests provide reference/instrumentation
  entry points. Compare extraction of individual kernels with rehosting a
  larger MD voice/mixer subsystem; a full 16-part instance may benefit from
  preserving its original shared processing.
- The inspected `mdromloader.cpp` requires a fingerprinted complete 8 MiB
  MD image. Do not equate the local update SysEx with that image. Resolve
  the required reference inputs and asset availability first.

## 4. Panel behavior

Distinguish the **parent OT track**, its **MD instance**, the selected
**internal MD part**, and the Octatrack's existing **Part** preset structure.

### Part selection and performance

With an MD track selected, an MD PART mode maps TRIG 1-16 to internal parts
1-16. Pressing a pad selects that part and auditions it in performance mode.
The LCD identifies the parent track, selected MD part, engine, and edit page;
LEDs distinguish selection, mute state, and activity.

Selection changes the edit focus only. Other parts continue sounding with
their own settings. Keep a separate non-auditioning selection gesture for
editing during playback; validate its exact binding against existing panel
chords before fixing the UI ABI.

### Engine assignment

An explicit ENGINE action opens the selected part's assignment overlay.
LEFT/RIGHT changes family; TRIG 1-16 chooses an engine in that family.
YES auditions, NO closes. Empty keys are inactive. Engine assignment affects
only that part; initialize it from original defaults, with explicit reset
and a documented restore policy for previously edited engines.

### Grid recording

Grid mode keeps TRIG 1-16 as OT sequencer steps. The screen shows which
internal part is being edited; toggling a step changes that part's hit in
the step's trigger mask. Other internal parts' hits at that step remain.
This is the direct-OT-event editor in option A; option B instead edits the
selected internal part's own pattern lane. Both need an MD PART selection
overlay reachable during grid recording, then
return to the same OT step page and retain the newly selected internal part.

Handle press/release ownership and held trigs/scenes explicitly. Pad
selection, engine assignment, performance audition, and grid editing must
never accidentally run each other's event handlers. Their exact shortcut
bindings are a UI milestone, not claimed existing firmware behavior.

## 5. Eight encoders adapted to six

The six OT encoders edit the currently selected internal part. Split each
eight-parameter MD group into two views while preserving its original order:

| View | OT A | OT B | OT C | OT D | OT E | OT F |
|---|---|---|---|---|---|---|
| SYN 1 | Synth 1 | Synth 2 | Synth 3 | Synth 4 | Synth 5 | Synth 6 |
| SYN 2 | Synth 7 | Synth 8 | unused | unused | unused | unused |
| MD FX 1 | FX 1 | FX 2 | FX 3 | FX 4 | FX 5 | FX 6 |
| MD FX 2 | FX 7 | FX 8 | unused | unused | unused | unused |
| ROUTE 1 | Route 1 | Route 2 | Route 3 | Route 4 | Route 5 | Route 6 |
| ROUTE 2 | Route 7 | Route 8 | unused | unused | unused | unused |

Provide explicit group/view navigation inside the MD editor. Keep MD FX
pages distinguishable from the parent OT track's FX1/FX2 pages. Add dedicated
views for MD LFO settings. Sparse engines show
only meaningful controls. For TRX-BD, SYN 1 is
`PTCH DEC RAMP RDEC STRT NOIS`; SYN 2 is `HARM CLIP`.

Use explicit parameter addresses:
`instance + internal_part + parameter_group + parameter_index`.
Master parameters use an instance-level address. Engine metadata supplies
names, ranges, defaults, formatting, and modulation eligibility.

Locks, scenes, and LFO destinations refer to those addresses, never to
whichever part happens to be selected on screen. Changing selection/page
must not retarget stored automation. Engine reassignment must validate the
affected part's parameter bindings and stored values.

All eight synthesis parameters require equal editing and automation
support. Extend the host's destination and lock resolution for the complete
nested parameter space. Mirroring six visible controls into stock slots is
only a UI adapter if their target identity is preserved; it is not sufficient
persistent storage.

Follow the measured stock ordering of locks, scenes, and OT LFO modulation,
and document its relationship to native MD modulation. Clamp/quantize by
metadata and never interpolate engine IDs. Preserve original live-parameter
response rather than applying unconditional smoothing.

## 6. Sequencing choice and MIDI integration

### Option A: direct OT step events (initial choice)

Each parent OT step stores an MD event with a **16-bit internal-part trigger
mask** plus addressed parameter locks and any supported per-part overrides.
One step can trigger a kick, snare, and hats together. An OT step is active
while it contains a normal hit or appropriate MD event; removing one part
must not clear remaining parts' events.

Reuse the parent OT track's timing, length, scale, swing, conditions,
microtiming, and retrigger scheduling. Specify which properties apply to the
whole step and expose per-part variants only through explicit extension
fields. There is one OT clock and pattern lifecycle; no hidden child
sequencer or independently advancing MD pattern.

Resolve event locks for the addressed parts before their triggers. Deliver
timestamped or sample-offset events through a bounded queue that can carry
simultaneous hits and repeated triggers. A single last-value trigger flag
cannot represent this workload. UI part selection has no role in playback
routing. Define mute/trigger relationships within the instance.

### Option B: embedded 16-part pattern sequencer (recommended, not yet selected)

Each MD instance owns a pattern with 16 internal drum lanes and their
parameter locks. It consumes the OT timing and transport service; it does
not run an unsynchronized tempo source. Selecting an internal part exposes
that part's step lane on the 16 trig keys, with the usual step-page control.
This makes complete kits and per-drum locks easier to edit than a single OT
lane carrying many addressed events.

The parent OT track controls the whole instance: master mute/level, kit and
pattern selection, and explicit start/restart or gate events. Ordinary
parent trigs must not implicitly restart the child pattern every step.
Define these event types before reusing stock playback controls. Pattern
changes commit at an OT boundary, with documented reset/continue behavior.
The OT remains responsible for global tempo, start/stop, and synchronization;
internal hits and locks are scheduled against that clock.

Prefer one internal pattern selection associated with each parent OT pattern
for the first version. Define length, scale, swing, launch/reset, and
condition semantics once; avoid silently applying both host and child swing
or conditions to the same hit. MIDI can continue to play individual parts
over the running sequence. Stop, mute, and release-tail rules must be explicit.

This adds pattern storage, editor state, event scheduling, and lifecycle
work. It does not increase the number of DSP voices relative to the same
16-part sounding workload. Its incremental CPU and memory cost still needs
measurement. Rehosting the original MD firmware sequencer is a separate
feasibility question; an embedded pattern model does not require running the
complete MD OS or emulating its processors on the OT.

Choose one sequencing architecture before implementing pattern persistence
and the grid editor. Do not build two independent sequencers for the same
instance by default. Option B is currently a recommendation, not a confirmed
change to the user's initial choice.

### MIDI and modulation shared by both options

For MIDI, use the parent OT track's configured receive channel plus an
explicit note-to-internal-part map. Validate the exact note defaults against
the reference. Velocity and note-off behavior follow the appropriate MD
engine contract. Separate instances use unambiguous channel mappings;
auto-channel dispatch follows the selected parent OT track. Preserve
unrelated OT MIDI behavior and test simultaneous MIDI/sequencer events.

Provide address-aware OT scene and LFO destinations across the internal
parts and master controls. Native MD LFOs retain independent per-part state.
Three OT track LFOs remain three host modulators; they are not silently
multiplied into 16 sets.

## 7. Runtime ownership and resource limits

An instance owns 16 part configurations, live voice/envelope/filter/RNG
state, per-part processing and modulation, its mixer,
event queues, and persistent kit state. Share immutable engine code, tables,
and sample assets where safe; mutable state must remain private even when
two parts or instances choose the same engine.

The render path is:

```text
OT step events / MIDI
        |
        v
MD instance: 16 internal parts -> MD mixer/master processing -> stereo
        |
        v
parent OT track processing -> routing / recording / outputs
```

Test both a one-core renderer and a split-core renderer if necessary.
A complete MD instance may require both DSP cores. The parent's normal
track-to-core assignment does not prove that its 16-part synth must fit on
that core. Any split-core design needs measured transport, latency, and
synchronization and must deliver exactly one output stream to the parent.

The module manifest/remix should declare a **maximum MD instance count**
and qualified resource profile. Start at one for development. Add runtime
admission checks to assignment, project load, Part changes, paste, and undo,
in addition to build-time placement checks.

- Reserve resources before committing an assignment. At the cap, reject the
  new assignment with a clear explanation and retain the previous machine.
- Loading an over-cap project must not allocate past the limit or reinterpret
  MD state as another machine. Preserve the data and require an explicit
  resolution; inactive/unavailable instances produce silence.
- Muting an instance does not release its reservation. A later unmute must
  be safe. Release resources only after unloading and finishing the chosen
  bounded tail policy.
- Price worst-case 16-part activity, per-part processing, master effects,
  parent OT FX, other tracks, storage activity, and transition overlap.
  Idle voices are an optimization, not the admission budget.
- Enforce both total and per-core/buffer constraints. A count cap alone is
  insufficient if changing effects or placement can exceed the qualified
  envelope; declare/enforce supported combinations and refuse unsupported
  resource increases.
- Do not reduce part count or silently steal voices across MD instances to
  make an advertised full instance fit.

Measure code/table/state sizes before choosing residency. Prefer resident
code. If overlays are required, preload all engines needed by the admitted
instances outside the audio ISR and prove that code replacement cannot race
another part. No card reads, allocation, decoding, or relocation in the ISR.
Large E12 assets may need a measured ColdFire-to-DSP feeding path.

Retain original 44.1 kHz timing and fixed-point behavior where applicable.
Record initialization dependencies, registers, scratch space, gain staging,
and saturation. Qualification must check the stereo mix as well as isolated
engines, including all-part peaks and feedback tails.

## 8. Machine integration and persistence

Factor reusable chooser/type-validation/descriptor/dispatch hooks out of
POLY's registration assumptions. Preserve POLY type 5; assign MD its own
stable serialized ID after auditing bounds and table capacity. Introduce
machine-ID claims and a shared dispatcher or named compatibility bridge.
Refuse unresolved hook collisions.

A versioned project extension stores, for every parent OT track and OT Part:

- The instance's 16-part kit, engine assignments, parameter groups, modulation,
  routing, master settings, and applicable persistent assets.
- Sequencing data for the chosen architecture: OT step trigger masks and
  addressed locks (A), or per-instance 16-lane patterns and their locks with
  parent-pattern associations (B).
- Scene assignments and extended OT LFO destinations.

Transient oscillator/envelope histories and live queues have defined reset
semantics; do not serialize arbitrary pointers. Working/saved OT Part copies,
reload, undo, copy/paste, track reassignment, pattern operations, and project
Save As must preserve the correct ownership. Copying an MD track copies its
whole sound module and relevant events, subject to destination capacity.

Use project identity, format version, generation checks, range validation,
and a verified temporary-write/rename or equivalent commit protocol. Resolve
missing/truncated/mismatched extension files without out-of-range dispatch.
Do not reuse undocumented stock padding. An Octakit bridge must define Kit
ownership before that combination is supported. Provide a defined export or
downgrade path because stock firmware cannot interpret the raw MD machine ID.

Keep source/asset extraction reproducible from user-supplied firmware, with
input hashes and relocation recipes. Host emulator code remains a separate
reference dependency with its own license. Follow Octamad's existing rule
that Elektron code/data and built images are derived locally, never committed.

## 9. Implementation sequence

| Phase | Work | Exit evidence |
|---|---|---|
| 0. Inputs and subsystem map | Pin reference revisions; validate firmware/assets; inventory engines, part processing, mixer/master dependencies | Reproducible coverage and dependency map, including present/missing assets |
| 1. Direct-port proof | Isolate GND-SN/TRX-BD or a bounded original voice subsystem; compare native relocation with the MD reference | Original behavior reproduced at a defined boundary without relying on an unported MD OS scheduler |
| 2. One instance, multiple parts | Add OT machine registration and private part states; start with kick/snare/hats, then exercise 16 concurrent parts | Independent parts mix into one OT track; no cross-part state corruption; initial placement and timing report |
| 3. Sequencing/MIDI and editor | Confirm A or B; add its pattern/event model, MIDI map, part pads, engine assignment, 6+2 views, scenes/LFO destinations, and save/load | Simultaneous parts follow OT timing; UI selection cannot retarget playback/locks; all eight synth controls work |
| 4. Complete sound module | Finish all core engines and native per-part/master processing; characterize E12 data delivery | Every declared feature passes reference comparisons and contributes to measured worst-case budgets |
| 5. Admission and qualification | Enforce the instance cap and resource profile; qualify one full instance before attempting two | Assignment/load/paste limits hold; full-load hardware deadline and soak evidence determines the supported cap |

Every milestone remains a module/remix in Octamad. The first useful vertical
slice is **one OT track running kick, snare, and hats as separate MD parts**,
including simultaneous OT-synchronized hits and MIDI, pad selection,
independent edits, an MD parameter-7/8 lock, and save/reload. A one-engine
extraction is an earlier technical proof, not the corrected product target.

Whether even one full instance fits remains unmeasured. If direct reuse pulls
in most of the MD runtime, document the dependency graph and reassess
subsystem boundaries before choosing another execution route. Do not quietly
replace original engines with approximations or redefine the instance as a
single drum voice.

## 10. Proposed files

Only this proposal is updated in this planning task.

```text
modules/machinedrum/
  manifest.py                  machine/hooks, resources, supported profile
  README.md                    coverage and qualification evidence
  engines.py                   stable engine and parameter metadata
  instance.s                   instance admission, ownership, lifecycle
  control.s                    OT/MIDI events and addressed parameter routing
  sequencer.s                  internal pattern scheduling if option B is selected
  ui.s                         internal-part pads, engine picker, edit views
  persistence.s                kits, masks, locks, scenes, project lifecycle
  dsp/adapter.asm              part dispatch, private state, parent output
  dsp/mixer.asm                adapter around native MD mixing/processing
  extraction.py                firmware/subsystem relocation recipes
remixes/machinedrum.py          initial single-instance composition
docs/remixes/machinedrum.md     inputs, controls, limits, compatibility
tools/harness/md_reference/     pinned host-side reference runner
tools/harness/benchmark_md.py   full-instance and mixed-load measurements
tools/verify/verify_md_*.py     extraction, audio, events, UI, persistence, cap
out/machinedrum/                ignored generated payloads/assets/evidence
```

Extend remixer schema/registry/ledger/build only where needed for native
machine registration and declared resource profiles. Runtime admission is
additional code, not a capability automatically supplied by the build ledger.

## 11. Validation and completion

- Extraction: firmware hashes, complete dependencies, relocation checks,
  disassembly, no unresolved absolute references or peripheral waits.
- Audio: deterministic reference comparisons at dry-engine and complete
  instance boundaries; align RNG state or use declared repeatable metrics.
  Compare original per-part/master processing and mixed peaks separately.
- Isolation: start from garbage state; use the same engine on multiple parts
  and instances with different values; check RNG, feedback buffers, mutes,
  retriggers, reassignment, tails, and teardown for leakage.
- Events/UI: simultaneous 16-part hits, repeated events, microtiming,
  conditions, MIDI velocity, page/part changes with held trigs/scenes, and
  real panel-to-renderer parameter delivery.
- Persistence: round-trip kits and addressed events through all supported
  project operations; invalid data and over-cap projects cannot over-allocate.
- Admission: selecting, loading, pasting, or unmuting cannot bypass capacity;
  count reservations consistently across transitions and inactive tracks.
- Regression: save the refhash baseline before shared build changes; run
  `scripts/refhash.sh check`, `make check REMIX=machinedrum`, and checks for
  each other touched remix. Keep unrelated machine behavior intact.
- Performance: measure worst-case 16-part processing and complete-instance
  transitions alongside the qualified OT workload. Distinguish emulator
  instruction counts from real cycles; qualify actual deadline margin and
  any cross-core transport on hardware before increasing the instance cap.

Completion means a parent OT track really hosts the declared 16-part MD sound
module: its parts independently select from the complete supported engine
catalog, can sound together through OT-synchronized sequencing and MIDI,
retain their own controls
and automation, survive project operations, and stay within an enforced,
measured instance/resource limit.

## 12. Phase 0 findings (23 September 2026)

Reproduce with `python3 modules/machinedrum/extraction.py --wav`: it reads
the user's own update from `base_firmware/`, refuses any input or section
whose SHA-256 differs from the pinned values, and writes everything to
`out/machinedrum/os163/` (gitignored), including `inventory.json`. ✅ marks
a measurement from the file; *inferred* marks what is not.

### Inputs

- ✅ `Elektron_SPS1-1UW_OS1.63.syx`, SHA-256 `a58cd61f…42cabd5`: 14,684
  data messages of 112 bytes, a short end message and a `7F` trailer.
  Each message carries 64 bytes as 2+7+7 packed 16-bit words, addressed
  by a 6-nibble counter from flash offset `0x4000`; the trailer's total,
  939,744 bytes, equals the decoded length. The vendored
  `elektron-firmware-tool` already decodes this "pre-ELE" container and
  its aPLib-variant sections. All checksums verify.
- ✅ Five sections:

| # | Content | Bytes | Notes |
|---|---|---:|---|
| 0 | ColdFire MAIN OS | 404,766 | linked at `0x200000`: startup sets SP `0x300000`, copies 2,466 data bytes to internal SRAM `0x01000088`, clears BSS `0x262400..0x2b7148`, `jmp 0x213a0c` |
| 1 | DSP load image | 750,369 | engines + sample block, below. *Inferred* to be the voice producer |
| 2 | DSP load image | 56,469 | P 18,489 words. *Inferred* to be the mixer |
| 3 | factory data bank | 524,288 | names such as `TRX MD`; *inferred* kits/patterns |
| 4 | factory data bank | 524,288 | names such as `TRX UW BET…`; *inferred* UW factory content |

- ✅ The DSP images are little-endian 24-bit words: header `3 0x24 4 0`,
  then `(space, address, count, words…)` records (space 0/1/2 = P/X/Y), and
  a closing `3 0x24` pair. Both parse exactly to their last word.
- ✅ The reference runs. A full 8 MiB flash dump
  (`base_firmware/elektron_sps1-1uw_os1.63.bin`, gitignored; SHA-256
  `68542e30…4fbca44c8`) matches the fingerprint the reference emulator
  requires (FNV-1a `33b7c1a9e29f43fd`). The decoded update stream sits in
  it byte-identical at `0x4000`, and the dump adds the bootloader
  (`0x0000–0x3fff`) and 6.75 MiB of data at `0x100000–0x7c0000`. The
  emulator is at `vendor/gearmulator-md-mm` (`release/md-mm-alpha`,
  pinned `8cea052`, 21 Sep 2026; cloned by hand, not by
  `scripts/setup.sh`). Its headless `mdAudioFirmwareTest` builds with the
  plugin and the other synths off (`build-headless/`, about 1 min) and
  passes against the dump: both DSPs boot, and the MD 1.63 audio soak
  passes in 5 s. `vendor/mc68k` is already `joelanders/mc68k-md-mm`, the
  same author's ColdFire core. The MAIN OS carries its own aPLib depacker
  at `0x248394`; its caller is not yet located.
- ✅ Clocks as the reference models them: each MD DSP56303 runs at
  101.6064 MHz, which is 2,304 cycles per 44.1 kHz sample. The OT has 4,532
  per core, of which `CHIP.md` counts 3,120 as usable.

### Engine catalog

✅ An 86-byte descriptor per machine at MAIN OS offset `0x4ef55`, 135 of
them: a 24-bit handler pointer into the OS, the machine ID, the family and
name, eight 4-character parameter names, eight defaults and eight flag
bytes. The core synthesis catalog has 50 engines, not 49:

| Family | IDs | Machines |
|---|---|---|
| GND | `0x00–0x03` | EMPTY, SN, NS, IM |
| TRX | `0x10–0x1d` | BD SD XT CP RS CB CH OH CY MA CL XC B2 S2 (14) |
| EFM | `0x20–0x27` | BD SD XT CP RS CB HH CY (8) |
| E12 | `0x30–0x3f` | BD SD HT LT CP RS CB CH OH RC CC BR TA TR SH BC (16) |
| P-I | `0x40–0x48` | BD SD MT ML MA RS RC CC HH (9) |
| INP | `0x50–0x55` | GA GB FA FB EA EB |
| MID | `0x60–0x6f` | 01–16 |
| CTR | `0x70 0x71 0x78–0x7b` | AL 8P RE GB EQ DX (RE/GB/EQ/DX drive the master effects) |
| ROM / RAM | `0x80–0xbf` | ROM 01–48, RAM R1–R4 and P1–P4 (user sample slots) |

TRX-BD's parameters are `PTCH DEC RAMP RDEC STRT NOIS HARM CLIP`, as in
section 5.

### Assets

- ✅ Section 1 carries a 207,174-word block at `P:1028c0–135205` whose words
  decode as pairs of signed 12-bit samples. That is 414,348 samples, 9.40 s at
  44.1 kHz, with 20 sharp onsets and silent gaps between them. It is
  *inferred* to be the E12 sample ROM: nobody has listened to it
  (`e12_candidate_region.wav`), and no E12 machine has been mapped to an
  offset yet. The first ~6 K words may be tables rather than samples.
- ROM and RAM machines play user samples. Those are user data, so they are
  not in the update.

### What the sizes mean for the OT

These are ✅ sizes from the load maps, set against `docs/firmware/CHIP.md`.

- The OT's DSP56721 has 92 K words private per core plus a 64 K shared
  window, and stock uses most of it. The sample block alone is 207 K words,
  so **E12 cannot be DSP-resident on the OT**. It would have to live in the
  ColdFire's 128 MB SDRAM, behind a streaming path that has not been
  measured.
- The producer's P content outside the sample block is about 27.5 K words
  (`P:0–3e1`, `P:100000–1028b9`, `P:142100–145d37`, `P:147200–1475ff`). That is
  an upper bound, because tables are not yet separated from code. X holds
  13.1 K words and Y 1.9 K. The mixer is 18.5 K words of P. The OT's
  default memory map gives P 8 K words, and payload A's code already ends at
  `0x1fdf`. The memory-map switch is ruled out: it halves Y memory, and
  stock uses all 48 K words of it (`CHIP.md`). ❌ "Hosting either image
  needs … a much smaller extracted subset": the image sizes are not code
  sizes. The executed code is ~6.9 K words on the voice DSP and ~2.3 K on
  the mixer (below), which fits the shared window.

### Measured in the reference (23 September 2026)

The tools are `tools/harness/md_reference/md_profile.cpp`, a JIT build of
the reference with `tools/patches/gearmulator-md-exechook.patch`, and
`md_analyze.py`. The profiler boots the user's dump and runs the OS's
first-run UW initialization and PREPARING FLASH. It then assigns a machine
to a track with SysEx `0x5B` and presses TRIG keys. It records cycles per
JIT block on both DSPs.

The cycle figures come from **the emulator's cycle model, not hardware**.
Code sizes are estimates: each executed block is walked through the
disassembly to its first flow change.

- ✅ Section 1 is the voice DSP (the producer) and section 2 the mixer: each
  runs code that only its own image contains.
- ✅ Most of the voice DSP's time is waiting. A two-`nop` delay loop inside
  nested `do` loops (`P:100092–100098`) and a port-C poll (`P:bb–bf`)
  take 2,240 of its 2,304 cycles per sample at idle. The mixer's wait is a
  DMA poll at `P:3c–44`.
- ✅ Work, meaning every cycle outside those waits, per sample:

| scenario | voice DSP, avg | voice DSP, busiest 10 ms | mixer, avg |
|---|---:|---:|---:|
| idle | 61 | 89 | 1,846 |
| one engine on track 1, 8 hits in 2 s | 74–182 | 102–212 | 1,846–1,850 |
| 16 tracks together: the 16 heaviest engines | 1,590 | 1,651 | 1,849 |
| 16 tracks together: an all-TRX kit | 1,536 | 1,590 | 1,849 |
| 16 tracks together: an all-E12 kit | 1,484 | 1,508 | 1,849 |

- ✅ All 50 core engines sound when triggered alone. TRX-S2 is nearly
  silent at its defaults (RMS 0.00004).
- ✅ The mixer's ~1,850 cycles are constant: independent of voices and of
  engines. *Inferred*: most of it is the master effects this plan drops.
  The mixing share is not yet separated out.
- Estimated code, executed on the voice DSP beyond idle: 6,815 words for
  all 50 engines. By family: TRX 2,758, P-I 3,789, EFM 152, E12 159,
  GND 142. EFM and E12 run a shared voice routine plus a handful of words
  each. Everything the voice DSP executed in any scenario, framework
  included, is ~6,946 words; the mixer's is ~2,296. Section 12's earlier
  "~27.5 K words of P" was the whole image, including tables, the
  ROM/RAM/INP/MID machines and loaders. It is superseded as the code
  estimate.

What this means for the OT (*inferred*, from the numbers above):

- **Code.** The full voice code, ~7 K words, fits the shared window with
  room to spare; no overlays are needed.
- **Cycles.** A full 16-voice instance's voice work peaks near 1,650
  cycles per sample. That fits one OT core's ~3,120 usable and leaves
  roughly 1,470 for the other three tracks on that core. This holds only
  if the OT core runs this code at the reference's cycle counts.
  Shared-window placement and DSP5636x timing are unmeasured.
- **Still open:** the data (X/Y tables and per-voice state the engines
  touch), E12's sample reads (the 207 K-word block cannot sit on the OT
  DSP), the mixing cost without the master effects, and the ColdFire→DSP
  command protocol.

### Open for Phase 1

1. Profile data accesses (X/Y) per engine, which gives the tables and
   per-voice state an extracted engine needs.
2. Split the mixer's constant ~1,850 cycles into master effects and
   mixing.
3. Decode the ColdFire→DSP command stream for a trigger and a parameter
   change. The profiler already drives both.
4. Map E12 machines to sample offsets, and listen to the block.

## References

- Local [POLY implementation](../../modules/poly-machine/manifest.py) and
  [qualification notes](POLY_MACHINE.md).
- Local [module contract](../../CONTRIBUTING.md),
  [module guide](../remixer/MODULES.md), and [placement](../remixer/PLACEMENT.md).
- Local [parameter/storage map](../firmware/PARAM_PAGES.md),
  [LFO routing](../firmware/LFO.md), [DSP interface](../firmware/DSP.md), and
  [chip/timing evidence](../firmware/CHIP.md).
- [MD Gearmulator fork](https://github.com/joelanders/gearmulator-md-mm),
  especially [MD hardware](https://github.com/joelanders/gearmulator-md-mm/blob/release/md-mm-alpha/source/elektron/md/mdLib/mdhardware.h),
  [DSP setup](https://github.com/joelanders/gearmulator-md-mm/blob/release/md-mm-alpha/source/elektron/md/mdLib/mddsp.cpp),
  and [ROM validation](https://github.com/joelanders/gearmulator-md-mm/blob/release/md-mm-alpha/source/elektron/md/mdLib/mdromloader.cpp).
- [Upstream Gearmulator](https://github.com/dsp56300/gearmulator).
- [Elektron MD OS 1.63 manual](https://www.elektron.se/wp-content/uploads/2024/09/machinedrum_manual_OS1.63.pdf),
  Appendix A (machines/parameters) and Appendix C (machine IDs).