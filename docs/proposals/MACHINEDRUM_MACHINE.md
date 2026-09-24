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
initially selected direct OT sequencing. **On 23 September 2026 the user
chose the embedded 16-part pattern sequencer (option B), synchronized to OT
clock and transport** (section 1, decisions). Section 6 keeps both options
for the record. The instance produces a stereo mix that
enters its parent OT track's normal processing and routing.

The user permits a limit on simultaneously assigned MACHINEDRUM machines to
fit CPU/DSP resources. The initial experimental remix should allow at most
one instance; that is a development cap, not evidence that even one complete
instance fits. Increase it only after measuring the full workload. There is
no requirement for eight simultaneous Machinedrum instances.

### Decisions (23 September 2026, the user)

- **One Machinedrum per OT Part, on tracks 5–8 only** (narrowed later the
  same day, after the memory measurement in section 12). At most one track
  of a Part is MACHINEDRUM. It may be a different track among 5–8 in
  another Part. Tracks 5–8 run on core 0 (payload A; `CLAUDE.md`, "the
  track↔core mapping"). Tracks 1–4 (core 1) stay fully stock in memory and
  cycles. The layout keeps code and tables shared in the window and
  per-instance state per core, so a core-1 instance can be added later if
  the cycle measurements allow it. Core 1 was the technical recommendation:
  - core 1 has 608 words of private P free, core 0 has 33 (`DSP.md` §3);
  - core 0 carries stock's non-effect work: the mixdown, the voice
    playback engine, and the delay's return at `X:0x4400`.

  The user chose core 0. So the driver and every engine run from the
  window and pay its fetch cost, and core 0's own stock share is probably
  larger (*inferred*: the ~3,120 usable was measured on one core). A Part change moves the instance; its voices
  restart, as they do on any machine change. ❌ "Because either core can
  host it, both cores must afford an MD track": superseded by the core-1
  limit.
- **The Machinedrum remix drops the bus servers** (BusVerb, BusDelay and
  the SEND clients) to free the shared window for MD code and state. The
  stock FX1/FX2 effects stay. Composing with every other remix is not a
  goal. (Measured later the same day: four tracks' FX2 slots also live in
  the window, and one instance needs more than the window holds. The
  placement is open again; see section 12, "Memory one instance needs".)
- **The MD master effects are out of scope**: the delay, reverb, EQ and
  dynamics that CTR-RE/GB/EQ/DX drive. The parent track's OT FX process the
  instance's stereo mix. Per-part processing (the MD FX page) stays.
- **Sequencing is option B, the embedded 16-part pattern sequencer**
  (section 6). Its pattern plays whenever the OT transport runs, with one
  MD pattern per OT pattern. Only its editing view is entered and left,
  through the OT's own grid recording (section 4, "Entering and leaving the
  MD sequencer").

### Decisions (24 September 2026)

- **The MD runs on core 1, on tracks 1–4** (24 Sep, later the same day). This
  supersedes "tracks 5–8 only (core 0)" above, and the voice-home sign-off
  below. The user had core 0 and core 1 swapped (core 0 is payload A,
  T5–T8). What the user wants is that T5–T8 stay stock and T1–T4's FX may be
  limited. The rule for choices like this (the user): take the option that is
  best for the architecture, for efficiency and for parity with the stock OT
  firmware. Core 1 wins on all three:
  - architecture: it is the only placement that fits (section 12, "Which
    space the MD reads its data through");
  - efficiency: core 1 has 608 free private P words to core 0's 33, and does
    not carry the stock mixdown and voice playback;
  - parity: T5–T8 keep all of their FX.
  The layout (WP-A2) is redone for core 1. The core-0 findings stay as the
  record of why.
- **Voice home A** (the user): the MD voice records live at `X/Y:0x3400–0x37ff`,
  and core 0's FX1 slot there (`0x3400–0x3fff`) is given up. Options B and C in
  `layout.py` are not taken.
- **B2 packing: option A, the packed split** (decided by the agent; the user
  delegated it). Code and tables are packed into the MD's share of the window
  and into private memory. A table read in one space only goes to private
  memory: Y-only tables to `Y:0x4000–0x85ff` as proposed, X-only tables to
  core 0's free private X (section 12, "Diagnosis of the A3 gate"). Tables read
  in more than one space, and all code, stay in the window. Option B, "a
  separate 32K shared span", does not exist: the sine fills core 0's half and
  the rest of the window is already claimed.
- **Tracks 1–4 may lose or limit their FX; tracks 5–8 must stay close to stock**
  (the user). In the window, that frees core 1's half (`0x38013–0x3ffff`,
  T3/T4's FX2 storage, 32,749 words) and keeps T7/T8's (`0x30048–0x37fff`).
  *inferred* Core 1's private memory (T1/T2 FX2, its FX1 slots, its P) is
  reachable only from core 1. Under the core-0 decision it frees nothing for
  the MD. See section 12, "What the T1–T4 decision frees".
- Still open for the user: the stock storage the window proposal takes away
  (core 0's T7/T8 FX2 storage and core 1's half, `0x38013–0x3ffff`, which
  conflicts with "tracks 1–4 stay fully stock in memory" above), and the cap of
  six P-I voices.

For example, T5 can host the Part's MD instance with a kick on internal part
1, snare on part 2, and hats on parts 3/4. A second instance in the same
Part is not planned (section 1, decisions).

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

### Entering and leaving the MD sequencer (decided 23 September 2026)

The MD pattern is not a mode that runs; it plays whenever the OT transport
runs. Only its editing view is entered and left, and that view rides on the
OT's own grid recording:

- **Playing:** OT PLAY/STOP start and stop the MD pattern, and the OT
  tempo drives it. It changes with the OT pattern (one MD pattern per OT
  pattern). Muting the MD track mutes the whole instance.
- **Entering:** select the MD track (its T5–T8 key), then press RECORD
  (●). On an MD track, grid recording shows **the selected part's lane** on
  TRIG 1–16, not the OT track's steps. The LCD info box names the part
  being edited (e.g. `P05 E12-SD`), so the MD view is always recognisable.
- **Switching parts:** hold the MD track's key. The LCD lists the 16 parts
  with their engines, and the trig LEDs show which parts have steps.
  TRIG 1–16 picks one, and releasing the track key returns to that part's
  lane on the same step page. This works while the pattern plays.
- **Step pages and locks:** PAGE pages through lanes longer than 16 steps.
  Holding a step and turning A–F locks that part's parameter, as on the OT.
- **Leaving:** RECORD again ends grid recording, as on the OT, or select
  another track. The MD pattern keeps playing; only the view closes.
- **The MD track's own OT lane** is a 17th entry in the part selector
  (`TRK`). It is for OT-level events: restart trigs, scene and pattern
  locks.
- **Open:** whether "hold track key + TRIG" is free in stock OS 1.40C. The
  track keys take part in other chords (FUNC for mute, CUE for cue), and
  the panel handlers are not checked yet. If it is taken, the fallback is
  FUNC + track key held.

Handle press/release ownership and held trigs/scenes explicitly. Pad
selection, engine assignment, performance audition, and grid editing must
never accidentally run each other's event handlers. Their exact shortcut
bindings are a UI milestone, not claimed existing firmware behavior.

## 5. Eight encoders adapted to six

**Proposed page mapping (23 September 2026, not yet decided).** It stays on
the stock page machinery (descriptors, four-character names, the knob
drawer) as far as possible:

| OT control | On an MD track (T5–T8) |
|---|---|
| SRC | the selected part's synth parameters 1–6 on A–F |
| FUNC+SRC (SRC setup) | synth parameters 7–8, engine choice, part level and pan |
| AMP, LFO, FX1, FX2 | the OT track's own, acting on the instance's stereo mix |
| LEVEL | the OT track's level |
| info box | part and engine (e.g. `P05 E12-SD`), where stock shows the sample |

The user's concept mockup (an image generated outside this repo, kept
locally, not committed) shows all eight parameters as knobs on one screen,
with a kit/part/engine box and a level meter. That would need a drawer of
our own on the 128 × 64 surface (`docs/firmware/PANEL.md` has the
primitives), with the eight knobs still on six encoders. Open:
- six knobs per page (stock drawer) or eight on one screen;
- whether per-part level and pan live on the setup page;
- the mix itself: a simple per-part level/pan in the driver, or the MD
  mixer's own per-voice section.

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

### Option B: embedded 16-part pattern sequencer (chosen, 23 September 2026)

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
instance by default. (Superseded: the user chose option B on 23 September
2026. The rest of this paragraph is the earlier wording.) Option B was then a recommendation, not a confirmed
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

- ✅ **The E12 sample ROM is the 201,804-word block at `P:103dba–135205`.**
  Its words decode as pairs of signed 12-bit samples.
  - It is 21 samples laid back to back. Each is followed by `0x88` words
    that no descriptor length covers.
  - The 21 descriptors sit just below it, at `P:103d7b`, as triples of
    `[start word, length in samples, 0]`. Each start equals the previous
    start plus length/2 plus `0x88`, and the last one ends at `0x135206`
    exactly.
  - The descriptor lengths total 397,896 samples, 9.02 s at 44.1 kHz.
  - The E12 engines read the samples through these descriptors. A
    relocated replay that moved the first 774 words of the block with the
    code broke E12 slots (section "Relocating to OT addresses").
  - Nobody has listened to the samples yet (`e12_candidate_region.wav`),
    and the machine-to-sample mapping is not read yet.
- ❌ Two earlier boundaries are retracted:
  - "200,006 words at `P:1040c0`, 9.12 s": the first sample starts 774
    words lower, where the descriptors say.
  - "207,174 words at `P:1028c0`, 9.40 s": that run's first ~6 K words
    are code. The voice DSP executes blocks up to `P:103c71`, among them
    its hottest per-sample loop.
- ROM and RAM machines play user samples. Those are user data, so they are
  not in the update.

### What the sizes mean for the OT

These are ✅ sizes from the load maps, set against `docs/firmware/CHIP.md`.

- The OT's DSP56721 has 92 K words private per core plus a 64 K shared
  window, and stock uses most of it. The sample block alone is 200 K words,
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
  sizes. The executed code is ~10.5 K words on the voice DSP and ~2.3 K on
  the mixer (below). ❌ "which fits the shared window": that counted code
  only; with the tables it reads, one instance needs about 71–76 K words
  ("Memory one instance needs").

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
- Estimated code, executed on the voice DSP beyond idle: 10,326 words for
  all 50 engines. By family: TRX 3,843, P-I 3,969, EFM 1,841, E12 1,413,
  GND 142. Everything the voice DSP executed in any scenario, framework
  included, is ~10,459 words; the mixer's is ~2,296. ❌ These were 6,815
  and ~6,946 (EFM 152, E12 159, "a shared voice routine") until the code
  at `P:1028c0–103c7x` was disassembled; it had been skipped as sample
  data. Section 12's earlier
  "~27.5 K words of P" was the whole image, including tables, the
  ROM/RAM/INP/MID machines and loaders. It is superseded as the code
  estimate.

What this means for the OT (*inferred*, from the numbers above):

- **Code.** The full voice code, ~10.5 K words, fits the shared window with
  room to spare; no overlays are needed.
- **Cycles.** A full 16-voice instance's voice work peaks near 1,650
  cycles per sample. That fits one OT core's ~3,120 usable and leaves
  roughly 1,470 for the other three tracks on that core. This holds only
  if the OT core runs this code at the reference's cycle counts.
  Shared-window placement and DSP5636x timing are unmeasured.
- **Still open:** the data (X/Y tables and per-voice state the engines
  touch), E12's sample reads (the 200 K-word block cannot sit on the OT
  DSP), the mixing cost without the master effects, and the ColdFire→DSP
  command protocol.

### The ColdFire→voice-DSP interface (23 September 2026)

This comes from the same profiler: its `trace=<id>` scenario and
`tools/patches/gearmulator-md-hosttrace.patch`. For TRX-BD and GND-SN on
track 1 it logs every host-port word through an assign, a trig, encoder A
+10 and a second trig.

- ✅ Every packet to the voice DSP is host command vector `0x12` followed by
  data words.
- ✅ An idle voice gets `1 0 0 <addr>`, where `addr` = `0x840 + 0x40·voice`.
  The ColdFire cycles through the 16 voices at about 1,800 packets a second.
- ✅ A voice with news gets a record: `<n> <trig> <params…> … <addr>`. Its
  length depends on the engine: TRX-BD sends 16 words with `n` = 13;
  GND-SN sends 7 with `n` = 4. The trigger flag appears on the trig packet
  only (TRX-BD `0x11`, GND-SN `0x02`). The ColdFire resends the record
  about 114 times a second while the voice sounds.
- ✅ Values arrive mapped for the DSP. Ten detents of encoder A move TRX-BD
  word 4 from `b54` to `c29` in uneven steps (PTCH as a frequency-like
  word), and GND-SN word 2 from `bd50` to `10b60`. Other words stayed
  constant in this test.
- ✅ The voice DSP's writable footprint across a scenario is 300–370 words:
  `X:700–7ff` (256), `Y:20–3f`, a 32-word block near `Y:801`, and a few
  scattered words. Tables it only reads are not seen by a write diff.
- ✅ The mixer gets its own stream: vectors `0x12` (10, 11, 12, 13 or 22
  words) and `0x10` (1–3 words), about 10,000 packets a second. Not
  decoded.
- *Inferred*: the ColdFire does all control-rate work: knob→DSP mapping,
  and plausibly envelopes and LFOs. The descriptor's handler pointer (for
  example TRX-BD `0x20122a`) is where each engine's record is built. A port
  is therefore two halves:
  1. the voice DSP code, in the shared window;
  2. the MD's per-engine ColdFire handlers, run on the OT's ColdFire as a
     DRAM runtime. Both CPUs are ColdFire, but the ISA subset still needs
     checking.

  The two halves meet in these records, delivered over the OT's host port.

### Record words and the ColdFire handlers (23 September 2026)

- ✅ This comes from `md_profile map=<id>` and `md_mapsummary.py`, run on all
  50 engines. For each of encoders A–H: 8 detents, a trig, and the record
  carrying the trigger compared with a baseline trig. **325 of the 352
  named parameters move a record word**, usually one word per parameter.
  Some rows also list a word that drifted between trigs (E12's word 4);
  the first word listed is the parameter's own.
- Two engines sent no trigger record in this harness: GND-NS and TRX-S2.
  Their trigger must travel another way.
- The other 19 unmapped parameters: GND-IM UVAL, TRX-BD RAMP, TRX-CP HARD,
  EFM-BD MFB, EFM-XT CLIC, EFM-CP MDEC, EFM-HH FB, EFM-CY HPF, E12-OH DEC,
  E12-SH DEC, E12-BC BC, the P-I HARDs (BD, MT, ML), P-I-SD RVOL, and the
  P-I RC/CC/HH AG.
  *Inferred*: they act over time or at control rate rather than in the
  trigger record.
- ✅ Every core engine's descriptor handler is a pure function
  `f(record*, params*)`, 44 distinct ones in 32–586 bytes (about 11 KB in
  all). It reads eight 16-bit parameters and writes the record's 32-bit
  fields with shifts, `mulu.w`/`muls.l` and lookups in about ten tables at
  `0x2462e8–0x24da14` of the OS image. The disassembly
  (`m68k-elf-objdump -m m68k:5206e`) shows no calls, no MAC/EMAC
  instructions and no hardware access. The MD's CPU is an MCF5206e (ISA_A,
  per the reference) and the OT's an MCF54454 (ISA_B). *Inferred*: the
  handlers run on the OT unchanged, with their table addresses relocated.
  That makes the ColdFire half of the port a copy, not a rewrite.
- Not yet located: the caller that runs a handler, adds modulation and
  serializes the record into the host packet; and where the trigger word
  (`0x11`/`0x02`) comes from.

### The handlers' caller (23 September 2026)

- ✅ How it was found: `md_profile trace=<id>` with the ColdFire hook
  (`g_ucExecHook`, in `gearmulator-md-hosttrace.patch`) records every entry
  into the handler region together with its return address. TRX-BD and
  GND-SN show **one caller**, returning to `0x20b398+2`. It calls the
  empty machine's handler (`0x201128`) about 3,270 times in the run: once
  per visit to each of the 15 empty tracks.
- ✅ The caller is a per-frame voice update, `0x20ad9a` to about `0x20b600`
  (~2 KB), a loop over the 16 tracks (`d7` = 0–15). Per track it:
  1. computes shared values with multiplies (level, pan and similar;
     *inferred* from the arithmetic);
  2. calls the track's handler through a RAM pointer table at `0x29f27c`,
     filled when a machine is assigned. Arguments: an output record at
     `0x010015b4 + 84·track` in internal SRAM, and a parameter block that
     steps 48 bytes per track;
  3. does trigger bookkeeping (a per-track flag at `0x01001510`).

  It also calls OS functions at `0x2069bc`, `0x204c94` and `0x209e52`
  (unidentified; *inferred* modulation or LFO) and four routines in
  internal SRAM.
- ✅ The internal SRAM code (2,466 bytes, copied there at boot) includes
  interrupt handlers (`rte`) that access `0x600004`, the voice DSP's host
  port. *Inferred*: packets are pushed from interrupts, not from the
  update loop.
- For the port this means three different treatments:
  1. The handlers copy over unchanged.
  2. The voice update's per-track computation is ported with its tables
     and the three unidentified functions.
  3. The MD's interrupt-driven host-port plumbing does not port. The OT's
     own per-frame host path carries the records instead.

### The voice update's helpers (23 September 2026, from disassembly, *inferred*)

- `0x204c94`, **the per-track LFO tick**. It keeps per-track state in
  internal SRAM (`0x01000f8e`, 36 bytes per track) and calls two waveform
  generators through an 8-entry function table at `0x2523ee`, one per
  shape (the MD LFO's SHP1/SHP2). It also handles restart on trigger.
- `0x2069bc`, **applying an LFO value to its destination**. It reads the
  destination track and parameter from the live kit
  (`0x700022`/`0x700023`), then writes `value >> 7` into that track's live
  parameter array at `0x2ad8a6 + 24·track`. MIDI machines get a second
  copy in SRAM. Modulation therefore acts on parameters *before* the
  handler builds the record, so the handler sees modulated values.
- `0x209e52`, **a kit load**. The voice update calls it after the track
  loop only when a kit change is pending (`0x261a3e` ≥ 0). It copies a
  1,120-byte (`0x460`) kit into the live kit at `0x70000a`, whose machine
  IDs sit at `0x7001aa`. It has no role on the OT, where kits are Part
  persistence.
- The MD's SRAM host-port sender does not port (see above), so its packet
  format needs no decode beyond the traced stream.

### The voice DSP's output: the Phase 1 boundary (23 September 2026)

- ✅ The voice DSP sends the mixer **16 words per sample period** over the
  inter-DSP ESSI0 link. `md_profile trace=<id>` logs it
  (`g_linkTraceHook`, `gearmulator-md-hosttrace.patch`): 1,354,752 words
  in 84,672 samples.
- ✅ The stream is block-structured with a **512-word period, 32 samples ×
  16 voices, voice-major**: each voice's 32 samples go out contiguously, and
  track 1 is words 0–31 of every period. With only track 1 playing, no
  other position is ever non-zero.
- ✅ Track 1's words, read as a mono 44.1 kHz signal, are the two TRX-BD
  hits of the trace scenario, at 0.50 s and 1.41 s. The second is higher
  (~56 → ~62 Hz, by zero-crossing count) after PTCH +10.
- So each voice leaves the voice DSP separately, and the mixer applies
  level, pan and sends. *Inferred* from the per-voice stream. The Phase 1
  proof compares at this boundary: a voice record in, that voice's
  32-sample blocks out. The mixer, and therefore the MD master effects,
  are outside it.

### Phase 1: the voice DSP runs outside the Machinedrum (23 September 2026)

- ✅ **The voice loop** (`P:64–e7`, read from the disassembly): once per
  32-sample period it walks the 16 slots. For slot `v`:
  1. Its record is at `Y:0x800 + 0x40·v`, and the slot's current engine
     is at `y:$153+v`.
  2. A non-zero word 0 is a trigger carrying the DSP-side engine number
     (TRX-BD `0x11`). If that engine differs from the current one, the
     loop first calls **init** from a table at `0x145af5`. It then calls
     **trigger** from `0x145bb6` and clears word 0.
  3. Every period it calls **render** from `0x145c77`, which writes 32
     samples into a double buffer (`Y:0x100`/`0x120`, `m7 = $1f`). DMA0
     then sends that buffer to the link.
  4. After slot 0's render, the loop waits for the frame sync on port C
     bit 1 (`P:bb–bf`). It then re-arms DMA2 to receive from ESSI0 into
     an X ring at `x:$243` (`m0 = $ff`, `P:c0–cb`). At the end of the
     pass it stores DMA1's position in `x:$256` (`P:e2`). Earlier text had
     the wait before the render.
  5. The loop also writes its slot to the host every fourth slot (`P:73`).

  Host packets are `[destination][count−1][words…]`, fed through DMA5 by
  the host-command handler at vector `0x12` (`P:12` → `P:e8`). The
  destination word is written before the command; the earlier grouping
  that attached it to the previous packet is corrected here.
- ✅ **`md_replay`** (`tools/harness/md_reference/md_replay.cpp`, built by
  `md_profile.cmake`) runs this without the Machinedrum:
  - a bare DSP56303, the fork's `dsp56kEmu` configured as `md::Dsp` does;
  - loaded from an `md_profile capture=<id>` snapshot: the producer's
    memory and registers at a slot-0 loop head;
  - before each slot it writes what the host sent since the previous
    slot, decoded from the capture's host stream, then runs the original
    loop to `P:b5` and compares the 32 rendered words;
  - it resumes past the frame-sync poll and the DMA wait by setting the PC,
    and drains the host-port writes;
  - no host port traffic, no ESSI link, no ColdFire.
- ✅ **TRX-BD capture** (a trig, encoder A +10, a trig, 2.2 s): **33,513 of
  33,513 blocks bit-identical** across all 16 slots, re-measured under the
  host-stream replay described in "Relocating to OT addresses". The first
  measurement (33,502 of 33,502) wrote all 64 of each slot's words from
  the log. That also overwrote voice state, so it could hide errors.
  Slot 0, track 1, is non-zero in 1,268 of its 2,094 blocks and peaks at
  full scale.
- ✅ **The comparison catches real changes.** Altering the pitch word in all
  1,428 slot-0 records changes 1,249 of slot 0's blocks, from the first
  trigger on; the other slots stay identical. So render reads the record
  every block. Altering only the trigger record changes nothing: the next
  record restores the value before the voice sounds.
- What this proves: an engine's inputs are its record (word 0 plus
  parameters) and the voice DSP's resident state. Its output is 32 samples
  per call. The MD's host, DMA, ESSI and frame-sync paths are not needed.
- Running at other addresses, and engines beyond TRX-BD, are in the next
  subsection.

### Relocating to OT addresses: the inventory (23 September 2026)

This is from `tools/harness/md_reference/md_addrs.py` and the same
executed-code set as above (all 50 engines plus the 16-voice loads).

- ✅ **The engine code lives only in the external regions**,
  `P:100000–103c7x` and `P:142100–1475ff`. It never calls into low P;
  only the MD main loop and vectors, `P:0–e7`, are there, and they are
  replaced. No PC-relative branch crosses between the two regions, so each
  can move by its own offset.
- ✅ **Every external-address operand is a long form**, meaning the address
  sits in the instruction's second word. That covers:
  - 112 distinct jump/call/loop targets;
  - table bases with a register offset (`0x140000`, `0x141000`,
    `0x145xxx`, `0x148xxx`);
  - 61 immediates in `0x100000–0x14ffff`, all `#>` forms.

  All of them can be patched in place without changing any instruction's
  length.
- ✅ Some of those immediates point at memory the load images do not fill:
  - `0x103d7b–0x103db7`: tables between the code and the samples;
  - `0x12e70c` and `0x135600`: inside the sample block, so E12 sample
    addresses;
  - `0x148000` and `0x14a000`: past everything loaded, *inferred* to be
    runtime working buffers in the MD's external RAM. Their size is to be
    measured.
- ✅ **The engines' own low memory:**
  - short-form (one-word, 6-bit) operands on `X:0–0x27` and `Y:0–7` at
    hundreds of sites, which cannot be repointed without changing
    instruction lengths;
  - long-form operands on `X:0x66–0xff`, `Y:0xfa–0xff` and
    `Y:0x140`/`0x142`;
  - the records at `Y:0x800–0xbff`, reached through `r6`.

  On the OT, `X:0` is the audio block and stock effects scratch
  `X:0x20–0xff` every call.

**Design, from these facts:**

1. Copy the MD's external code and data regions into the OT's shared
   window, one offset per region. Keep each region's alignment, in case the
   code uses modulo buffers.
2. Patch every external-address extension word in place, plus the three
   routine tables (`0x145af5`, `0x145bb6`, `0x145c77`, 193 entries each)
   and any other pointer data found.
3. **Swap low memory rather than relocate it.** Around the batch of 16
   voice renders, save the OT's `X:0–0xff` and `Y:0–0xff`, load the MD's
   image of them, and after the batch store the MD image and restore the
   OT's. That is about 1 K moves per 32 samples, roughly 30–60 cycles per
   sample: *estimated*, not measured.
4. Replace the MD main loop with an OT-side driver that calls init,
   trigger and render per slot, with the records filled from the ColdFire.
5. Validate each step with `md_replay`: the relocated image at the new
   addresses, the external range left empty, and the swap emulated. It
   must still be bit-identical. Then run under `dsp_host`.

Space: about 46 K words if both external regions keep their full extent,
within the 64 K window. Stock's own runtime use of the window
(`0x30000–0x30047` every frame, the `0x38000` entry stub and what it
calls) has to be placed around.

### Relocation: measured (23 September 2026)

- ✅ **`md_relocate.py` moves both code regions and every capture still
  renders bit-identically.** The move:
  - `P:100000–103db9` goes to `0x3b000`, and `P:140000–147fff` to
    `0x30000`. Both are in the emulator's bridged external RAM, where P,
    X and Y alias as they do in the OT's shared window;
  - the old regions are then filled with `0xa5a5a5`;
  - it patches 987 words: 342 loop ends, 425 routine-table entries, 113
    displacement operands, 104 `#>` immediates, one absolute operand and
    two jump targets;
  - the recursive descent finds 13,712 instructions (15,753 words) from 206
    entry points. It covers all 10,449 words the Phase 0 profiles
    executed in the code regions (`cat`, `load`).

  Results (blocks bit-identical to the reference, plain replay and
  relocated replay):

  | Capture | Machines | Plain | Relocated |
  |---|---|---|---|
  | c10 | TRX-BD | 33,513 / 33,513 | 33,513 / 33,513 |
  | c10_3 | TRX-BD, TRX-S2, PI-CC | 33,508 / 33,508 | 33,508 / 33,508 |
  | c01_16 | GND ×3, TRX-BD…TRX-B2 | 33,513 / 33,513 | 33,513 / 33,513 |
  | c37_16 | E12 ×9, P-I ×7 | 33,504 / 33,504 | 33,504 / 33,504 |
  | c1d_16 | TRX-S2, EFM ×8, E12 ×7 | 31,555 / 33,506 | same blocks |
  | c47_2 | PI-CC, PI-HH | 33,415 / 33,502 | same blocks |

  All 50 engines ran in these captures. The two partial captures differ
  only in slot 0, and identically with and without relocation: TRX-S2 and
  PI-CC on track 1. The same two engines are exact on tracks 2 and 3
  (c10_3).
  - *Inferred* cause: the host's packet for slot 0 arrives while slot 0
    renders, and these two engines read a record word late enough in the
    render to see it. The replay applies host writes only between slots.
  - That is the MD's host timing, which an OT driver writing records
    between batches does not have. Replaying the writes at their cycle
    would test the inference.
- ✅ **Three corrections came out of the relocation runs:**
  1. **The code region ends at `0x103dba`, not `0x1040c0`.** The E12
     samples begin there ("Assets"). Moving their first 774 words with the
     code broke the E12 voices, since the samples are read through
     descriptors that stay put.
  2. **No live pointers were found in the working RAM at `0x148000`.** A
     value scan there "found" 60 words pointing into the code regions. They
     were two smooth ramp tables (step `0x63c`) that happen to cross those
     ranges, and patching them corrupted single samples. The scan is gone.
     A value test cannot tell a pointer from data, so any live-state patch
     is a guess until a replay confirms it. The X/Y scan still patches up
     to 35 words per capture (c47_2: `Y:0x4e`, `Y:0xa0–0xbf` and two
     voice-record words), and the replays pass with them.
  3. **The record's 64 words mix host input and voice state, per engine.**
     Engine `0x44` keeps its sample pointer in word 12, inside what looked
     like the host's 16 words. The replay therefore takes the host's
     writes from the host stream the capture now logs (`C`/`W` lines),
     never from the reference's record. Earlier replays overwrote state and
     reported the TRX-BD relocation clean when it was not.
- Not tested yet: the low-memory swap (step 3 of the design), and the OT's
  own window layout. The new addresses here are a test placement, not the
  OT's.

### Memory one instance needs (23 September 2026)

Measured with `md_replay` on the six captures of the relocation table
(all 50 engines):
- `MD_REPLAY_FOOTPRINT` lists the words that change between 32-sample
  periods;
- `MD_REPLAY_POISON` fills ranges with garbage at every period boundary,
  or once at the start, and a capture that stays at its baseline shows
  the range carries nothing the engines read.

| What | Words | Where it comes from | |
|---|---:|---|---|
| Engine code | 15,621 | `P:100000–103db9` 9,746, `P:140000–147fff` 5,875 (recursive descent) | ✅ |
| Tables read inside the code regions | 23,186 to 28,061 | loaded X data (`0x140000–0x1420ff`, `0x146000–0x1471ff`), P data, and the routine tables | ✅, per gap |
| Sine table | 32,768 | built at boot by `P:100069–10008d` | ✅ every 256-word chunk is read |
| P-I delay buffers | 1,536 per P-I voice, up to 24,576 | `0x135600 + 0x600·slot`, zeroed at boot | ✅ |
| Voice blocks | 1,024 X + 1,024 Y | `0x800 + 0x40·slot` in both spaces, through `r6` only | ✅ |
| Low-memory state | 36 | `X:0xa0–0xbf`, `Y:0x1e–0x21` | ✅ |
| Scratch within a period | 256 X + 320 Y | the rest of `X:0–0xff` and `Y:0–0x13f` | ✅ |

- **Low memory is scratch apart from 36 words.** Poisoning all of
  `X:0–0xff` and `Y:0–0x13f` at every period boundary except `X:0xa0–0xbf`
  and `Y:0x1e–0x21` leaves every capture at its baseline. Without that
  exception, PI-CC and TRX-S2 break. So the swap of design step 3 is 36
  words, not 512.
- **Nothing else in internal memory is read**, apart from the loop's own
  words: `X:0x100–0x7ff`, `Y:0x140–0x7ff` (including the 1,603 loaded Y
  words), and X/Y `0xc00–0x1fff` all poison clean.
- **The sine is the MD's own arithmetic, not image data.** The init seeds
  0 and `0x648` (sin(2π/32768)), then runs a 48-bit recurrence for `0x7ffe`
  steps. The "ramps" the retracted live-pointer scan found were this sine
  near its zero crossings. It is read through `x:(rN+$148000)` (32 sites)
  and `y:(rN+$148000)` (8 sites). That works on the MD because its
  external RAM is one memory.
- **The P-I buffers are used only by P-I voices.** The init writes three
  0x200-word sub-buffer pointers into voice words `0x14–0x16`, based on
  `#>$135600` (8 sites).
- **The tables split by family.** Of the per-gap results:
  - `0x140000–0x1420ff` (8.4 K) is read by every capture with GND, TRX,
    EFM, E12 or P-I voices;
  - `0x142291–0x144efb` (about 8.5 K in seven gaps) is read only by c37_16
    (E12 and P-I);
  - `0x100885–0x101881` and `0x101ba2–0x101e9f` (4.9 K) only by c01_16
    (GND, TRX).

  The per-gap granularity overstates the tables: a gap counts as read if
  one word is. The one-shot tests ran 4,000 blocks, which covers the first
  trigger but not the encoder change, so they can also understate.
- **Unused:** 4,629 words of gaps (`0x100000–0x10008d`,
  `0x100635–0x10074b`, `0x1025c5–0x1025ff`, `0x146e24–0x1471ff`,
  `0x147213–0x1473ff`, `0x147414–0x147e7f`).

**Against the OT (`docs/firmware/CHIP.md` §3, `DSP.md`):**
- One instance needs about 71–76 K words, before any P-I buffer:
  15.6 K code, 23–28 K tables and the 32 K sine.
- The shared window is 64 K, and it is not free ground. The FX2 allocator
  hands out `0x30000` and `0x34000` (and core 1's `0x38000`/`0x3c000`) as
  FX2 slots, so four of the eight tracks' FX2 slots live in it.
- ❌ Two earlier statements are retracted:
  - section 1's "dropping the bus servers frees the shared window" holds
    only if those four tracks' FX2 is never a memory-hungry effect;
  - "fits the shared window" (section 12, "What the sizes mean") counted
    code only.
- Private Y per core: `0x795–0xfff` is free (2,155 words), and the rest is
  FX1 and FX2 slots. Private P is full. The engine code has to run from
  the window, which costs one wait state per fetch as P and zero as X or
  Y. What that does to the ~1,650 cycles/sample is *unmeasured*.

### Cycles when the code runs from the window (23 September 2026)

- ✅ **The DSP5672x has no instruction cache.** Code executed from the
  shared window pays one wait state per program fetch (NXP AN3653 §2.4–2.5:
  "zero wait states as X or Y memory and one wait state as P memory …
  Instructions may be executed from shared memory but the hardware has not
  been optimized for doing so"; "there is no instruction cache support in
  the Symphony DSP5672x").
- ✅ **Counted, not estimated.** `md_replay` built with the emulator's
  interpreter (`out/md_reference_interp`, `DSP56K_FORCE_INTERPRETER=ON`) and
  `MD_REPLAY_FETCH=1` counts every program word fetched from the engine
  regions:
  - a `rep` fetches once, as on the chip;
  - a `do` body is fetched once per iteration.

  The empty slot's render (`P:10008f–10009a`: 32 zeros and a busy-wait of
  ~3,200 fetches, the MD's pacing) is left out, since an OT driver does not
  call it. Worst 10 ms, per sample:

  | Capture | Engine cycles | Words fetched | With +1 per fetch |
  |---|---:|---:|---:|
  | c10 (TRX-BD) | 142 | 74 | ~215 |
  | c10_3 (BD, S2, PI-CC) | 329 | 241 | ~570 |
  | c01_16 (GND ×3, TRX ×13) | 966 | 807 | ~1,770 |
  | c37_16 (E12 ×9, P-I ×7) | 1,131 | 996 | ~2,130 |
  | c47_2 (PI-CC, PI-HH) | 1,215 | 988 | ~2,200 |
  | c1d_16 (S2, EFM ×8, E12 ×7) | 1,263 | 1,021 | ~2,280 |

  So running from the window adds about 80 % to the engine's cycles.
  ❌ "PI-HH alone is ~900 cycles/sample": c47_2 assigns only tracks 1–2,
  so its other 14 voices are the default kit's. It costs ~1,215 from its
  first block, before any trigger, while the 16-voice all-P-I kit (PI-HH
  included) costs 1,436. The c47_2 figure is unexplained, not a PI-HH
  property. The Phase 0 profile's heaviest
  16-voice load (~1,650) would come to ~3,000, beyond core 0's ~3,120
  usable once T5–T8 have any FX.
- ⚠ The interpreter build is not bit-identical to the reference on
  c01_16 and c1d_16 (the JIT build is). The counts come from the same
  code paths, but the interpreter/JIT discrepancy is unexplained.
- ✅ **The fetches are concentrated.** In each capture the hottest
  1,024 words of code carry 89–94 % of the fetches, and the hottest 2,724
  carry 97–100 %. The union over the six captures of each one's hottest
  code for 80 / 90 / 95 % of its fetches is 1,900 / 2,764 / 4,820 words.
  All executed engine code across them is 11,392 words.
- **The lever:** payload A's donor region, `P:0x1000–0x1aa3` (PLATE,
  SPRING and DARK, 2,724 words, `build_bus.PP`), is core 0's own P with no
  wait state. Removing those three reverbs from payload A takes them from
  T5–T8 only; payload B keeps its copies for T1–T4. The hot code (about
  2.7 K words for 90 % coverage in these captures) would bring the window
  penalty down to about a tenth, so a 16-voice kit costs roughly 1,050–1,400
  cycles/sample (*estimated* from the counts above).
- ✅ **Moving hot code into private P works bit-identically.**
  `md_relocate.py --hot <captures>` splits the code into 239 units that can
  move on their own:
  - consecutive instructions stay together unless the first ends the path;
  - a one-word relative branch joins its source and target;
  - two-word relative branches (target = own address + word B; for `dor`
    the loop's last word) get their displacement recomputed.

  It then packs the units greedily into 2,724 words at `P:0x1000`,
  minimising the sum of squared remaining fetches across the captures. It
  chose 32 units and re-pointed 22 displacements. The region copies it left
  behind are wiped. All six captures replay identically to the plain
  replay. Window fetches, worst 10 ms per sample:

  | Capture | Engine cycles | Window words before → after | Total before → after |
  |---|---:|---|---|
  | c01_16 | 966 | 807 → 520 | 1,773 → ~1,490 |
  | c37_16 | 1,131 | 996 → 502 | 2,127 → ~1,630 |
  | c1d_16 | 1,263 | 1,021 → 359 | 2,284 → ~1,620 |
  | c47_2 | 1,215 | 988 → 246 | 2,203 → ~1,460 |

  About 1,500 of core 0's ~3,120 stay for T5–T8's FX with these kits.
  - The limit is unit size: the largest unit is 788 words, a long
    straight-line routine of which only part is hot. Splitting inside one
    needs an inserted jump, which is not done.
  - Checked against six new 16-voice kits: all P-I, EFM ×2, all E12,
    TRX-heavy, and two random mixes (`out/md_profile/cap5`). All replay
    bit-identically with the hot split. But the P-I kit kept 1,160 of its
    1,245 window words: the six-capture hot set held little P-I code.
  - ✅ **Retrained on all twelve kits** (23 units), every kit stays
    bit-identical. Engine cycles plus remaining window words, worst 10 ms
    per sample:
    - all P-I 1,436 + 842 = ~2,280 (worst);
    - TRX-heavy 1,170 + 746 = ~1,920;
    - EFM ×2 ~1,790, all E12 ~1,780;
    - the mixes and the first six ~1,470–1,740.

    Add the driver's low-memory swap (~40–70, *estimated*). That leaves
    about 800 cycles/sample of core 0's ~3,120 for T5–T8's FX in the worst
    kit measured.
  - Taking CHORUS as well (`0x0eb7`, 329 words, adjacent to the donor
    region) would add room, at the cost of that effect on T5–T8.

### The OT-side driver (23 September 2026)

`modules/machinedrum/md_driver.asm` replaces the MD's voice loop. It is
assembled per layout by `tools/harness/md_reference/md_driver.py`, which
disassembles the result back and refuses mis-encodings and label prefixes.
`md_replay --driver` runs it in place of the MD loop, which is filled with
`0xa5a5a5`, and compares every voice's blocks with the reference.

- ✅ **Step 1:** the loop's logic without its I/O. Bit-identical on all 12
  kits, both at the MD's addresses and relocated with the hot split.
- ✅ **Step 2:** each slot renders into its own 32 words, kept for the mix.
  The loop's Y words (`y:$140–142`, `y:$153+slot`) move out of OT system Y
  (`md_relocate --loopvars`), patching 13 engine operands (3 × `y:>$140`,
  10 × `y:>$142`); the engines touch no other loop word. Bit-identical on
  all 12.
- ✅ **Step 3:** the frame driver, one call per 16-sample OT frame:
  - it renders 8 slots per call, alternating halves;
  - it saves the OT's `X:0–0xff`/`Y:0–0x13f` around the batch and carries
    only the MD's 36 words;
  - it zeroes empty slots' buffers rather than calling the MD's 3,200-fetch
    pacing routine (81 of 193 engine numbers render through it).

  The replay fills low memory with garbage between calls, as the OT's own
  code would leave it. Bit-identical on 10 of 12 kits. The other two differ
  in 1–2 blocks of ~33,500, all TRX-S2's first block after a trigger: that
  render reads scratch it never wrote, so on the MD it depends on other
  voices' leftovers.
  - Carrying the whole low image (576 words each way, ~70 cycles/sample
    more, *estimated*) fixed c1d_16 but not c10_16.
  - The rest is *inferred* to come from the replay's still-armed MD
    interrupt handlers running at other moments relative to the swap, a
    harness effect. It is left as a documented deviation.
- `dsp_asm` (the shared build, still at pin `c051afad`: the main checkout
  was not rebuilt after the 22 Sep repin) does not take the MD loop
  verbatim:
  - no `move m0,mN`;
  - no backward `bcc`;
  - `jmp`/`jcc` only in the short form, below `$1000`;
  - `cmp a,b` comes out as `max a,b`.

  Each is written around and noted in the source.
- Not yet: the stereo mix, and the OT placement (addresses, the hook in
  core 0's dispatcher). The per-voice X and Y blocks (1 K words each, at
  the same address in both spaces through `r6`) are the open placement
  question.

### Core-0 memory ledger (23 September 2026)

- ✅ The ColdFire-port wordmap ran for 1,000 frames on four stock-project
  configurations. The union classifies every word of core-0 X
  `0x0000–0x8fff`, Y `0x0000–0xbfff`, and the shared window for both cores;
  the exact contiguous ranges and epoch evidence are in
  [`CORE0_MEMORY.md`](../firmware/CORE0_MEMORY.md) and the two generated
  ledgers in `machinedrum_reports/WP-A1-ledger-{all,noreverb}.txt`.
- ✅ The no-reverb B+C ledger confirms `Y:0x795–0xfff` as 2,155 free words.
  Core-0 X `0x2840–0x3fff` is untouched in all four runs, while the frame
  contexts occupy `0x1fff–0x283f` and `0x3fff–0x483f`.
- ✅ In the core-0 shared-window view, `0x30000–0x30047` is per-frame state,
  `0x38000–0x3800f` is read every frame, and `0x38013–0x3ffff` is untouched
  in these configurations. The all-effects ledger records the effect-slot
  ownership that must not be treated as free space.
- ❌ `DSP.md` §7's old `X:0x01d9f–0x0483f` PLATE/DARK delay-region claim is
  retracted and now points here. The heavier eight-track slice/recorder
  acceptance run was attempted twice and the isolated emulator exited `-11`
  before writing a wordmap, so the `0x2840–0x3fff` result remains 🟡 for
  that workload and WP-A1 is blocked pending a working fixture or emulator
  fix.

### WP-D1 track key plus TRIG (23 September 2026)

- ✅ The panel map sends track keys `0x10–0x17` to `0x40040250` and gives
  them the held-key sub-map at `0x400d164a`; that sub-map has no trig
  entries. `0x40060ce0` therefore receives a trig `(code, down)` and only
  branches on grid-recording state `0x460d1736`, to `0x40060b58` or
  `0x400501d8`.
- ✅ The disassembly of both targets contains no read of the panel row state
  or held-track map. `0x40060b58` reads current part/track and mode state;
  `0x400501d8` dispatches on `0x460d16f0` and selected-track/mode globals.
- *inferred* The stock OS 1.40C does not claim “hold track key + TRIG”. The
  MD page should use FUNC + track as the fallback. This is a static result;
  no hardware behavior was changed or tested.

### WP-A2 proposed core-0 layout (23 September 2026)

- ✅ The input budgets are the measured values above: 15,621 engine words,
  2,724 hot words, up to 28,061 table words, a 32,768-word sine, 1,536
  words per P-I voice, and a 192-word current driver assembly. The overlap
  checker is [`modules/machinedrum/layout.py`](../../modules/machinedrum/layout.py).
- *inferred* The proposal uses `X/Y:0x3400–0x37ff` for the 1K voice/state
  block and records, with hot code in `P:0x1000–0x1aa3`. It budgets the
  shared window as sine `0x30000–0x37fff`, packed code/tables
  `0x38000–0x3d9ff`, six P-I buffers `0x3da00–0x3fdff`, and 512 words of
  driver code `0x3fe00–0x3ffff`. Y-only tables get `Y:0x4000–0x85ff`.
  The code/table capacity is 40,960 words against the 40,958-word maximum
  after the hot split, leaving two words before future alignment padding.
- ✅ The internal driver addresses are concrete and non-overlapping:
  loop words `Y:0x0c00–0x0c1f` (`HALF=0x0c03`, `TMP=0x0c04`), `OUTBUF`
  `Y:0x0d00–0x0eff`, `MDSAVE` `Y:0x0f20–0x0f43`, and `STASH`
  `Y:0x1800–0x1a3f`.
- 🟡 The proposal conflicts with stock ownership in exactly the places
  listed in the layout file: payload-A frame state and T7/T8 FX2 storage in
  the shared window, payload-B entry/read and loaded/effect words there, the
  `0x3400` FX1 slot, both private T5/T6 FX2 slots used for Y-only tables,
  and the PLATE/SPRING/DARK donor P span. These are layout-review costs, not
  silently accepted collisions.
- *inferred* The selected six-P-I cap is a fit budget, not a qualification
  result. The user must choose the stock-slot sacrifices and one of the
  voice-home options in `layout.py` before WP-A2 can leave `review`.

### WP-R3 interpreter/JIT mismatch (24 September 2026)

- ✅ The normal JIT replay remains bit-identical on `cap4/c01_16`:
  `33513 identical, 0 differ`. The existing interpreter replay reports
  `30873 identical, 2640 differ (first difference at block 2340)`.
- ✅ On `cap4/c1d_16`, the normal JIT has the known TRX-S2 residual:
  `31555 identical, 1951 differ (first difference at block 2288)`; the
  interpreter reports `31218 identical, 2288 differ (first difference at
  block 2272)`. Both commands used the existing binaries and no vendor
  rebuild.
- ✅ A block-boundary probe isolates the same operation in both captures.
  In `c01_16`, `P:0x10078e` is `move b1,r3` and `P:0x10078f` is `add x,b`;
  with `MD_REPLAY_BLOCK_SIZE=18` the JIT reports 4 differences from block
  2340, while size 19 reports 0 through block 2399. In `c1d_16`, the
  corresponding pair is `P:0x102d80` / `P:0x102d81`; sizes 8 and 9 move the
  first JIT difference from block 2272 to the known block 2288 residual.
- *inferred* This is an old JIT block-boundary/register-allocation parity
  problem around `ADD X,B`, not evidence that the standalone opcode decoder
  is wrong. The newer shared vendor/toolchain is required to establish the
  corrected implementation; the stale pin was not changed overnight.
- **blocked:** WP-R3 needs the user to rerun `scripts/setup.sh` (WP-R4) and
  then repeat this parity check against the repinned vendor. No firmware,
  sample or extracted bytes were added.

### WP-R5 c47_2 default-kit cost (24 September 2026)

- ✅ A temporary per-slot diagnostic around the existing interpreter replay
  measured `c47_2`'s first 2,094 periods without changing the capture,
  driver or toolchain. The clean replay still reports `1,212.1` mean cycles
  and `985.8` engine words per sample, with a worst 10 ms window of `1,214.7`
  cycles and `987.7` words.
- ✅ The two assigned voices settle to DSP-side current values `0x48` and
  `0x49` (the capture's P-I-CC and P-I-HH assignments). The untouched
  default voices are, by track, EFM-SD `2,881` cycles / `2,219` words,
  EFM-XT `2,431` / `1,828`, EFM-CP `2,525` / `1,904`, EFM-RS `3,433` /
  `2,620`, **EFM-CB `3,946` / `2,983`**, EFM-HH `3,099` / `2,388`, EFM-CY
  `3,073` / `2,739`, then E12-BD through E12-CB at `1,392–1,803` cycles /
  `1,254–1,636` words per render. The full per-slot table is in
  [`WP-R5.md`](machinedrum_reports/WP-R5.md).
- *inferred* The current-value sequence is one above the catalog/SysEx
  machine number in this capture: the assigned `0x47`/`0x48` values become
  `0x48`/`0x49`, and the default `0x26` therefore identifies catalog engine
  `0x25`, EFM-CB. Track 7's EFM-CB is the default-kit voice that costs the
  anomaly; this is emulator measurement, not a hardware qualification.

### WP-R2 TRX-S2 residual (24 September 2026)

- ✅ The clean JIT replay of `cap4/c1d_16` remains at `31,555` identical and
  `1,951` different blocks, with the first difference at block `2,288`.
  The first differing output is slot 0, one word in the block; this is the
  known first render after the TRX-S2 trigger.
- ✅ At `P:0x102d49`, the watched entry has `R7=0x100` and `R3=0x40`.
  The first `macr -y1,x1,b x:(r7)+,b y:(r3)+,b` therefore reads the low
  scratch words `X:0x100` and `Y:0x40`. After `move b1,r3; add x,b; and
  #>$7fff,b`, the loop reads the sine table at `Y:0x148000+R3` at
  `P:0x102d8d` and `P:0x102db2`.
- ✅ The block-numbered watch at the divergent block recorded
  `B=0x0612c1e0000000`, `R7=0x100`, `R3=0x40`, `X:0x100=0`,
  `Y:0x40=0xf81a02`, and `Y:0x148040=0x01921d` at entry. The later
  table reads used `R3=0x7bcc` and `0x1f00`, with table values
  `0xe5d061` and `0x7fd885` respectively.
- ✅ Narrow poison reruns of `Y:0x40–0x41` and `X:0x100–0x101` left the
  first mismatch at block `2,288`. The reads are established, but those
  reruns do not prove either one word is the sole cause.
- *inferred* The residual is a per-call carry-in from low scratch and the
  accumulator state, which is why the driver preserves `B` around the
  render. The existing 36-word swap is the measured minimum for the normal
  low-memory state, not a complete first-render reproduction.
- ✅ The existing full-image A/B remains: carrying `X:0–0xff` and
  `Y:0–0x13f` (576 words each way) fixes `c1d_16` but not `c10_16`; the
  extra cost is `~70` cycles/sample, *estimated* rather than hardware
  measured.
- **review / D3:** the user must choose the current 36-word swap, which
  retains the `c1d_16` one-block and `c10_16` two-block residuals, or the
  full low image, which costs about 70 estimated cycles/sample and still
  leaves `c10_16` for further harness investigation.

### WP-R1 E12 sample delivery (24 September 2026)

- ✅ The 21 triples at `P:0x103d7b` decode to descriptor starts and sample
  lengths. They cover `397,896` samples and the `201,804`-word block
  `P:0x103dba–0x135205`; the last descriptor ends at `P:0x135206`.
  The complete table and extraction command are in
  [`WP-R1.md`](machinedrum_reports/WP-R1.md).
- ✅ In the full `cap4/c37_16` interpreter replay, the six executed
  `x:(r3)+` sites that point into the descriptor-defined sample block were:
  `P:0x1038c2/0x1038c3` (`331,398` reads each),
  `P:0x103bd3/0x103bd4` (`264,894` each), and
  `P:0x103bf3/0x103bf4` (`94,520` each). The totals agree with the
  corresponding `fetch.txt` instruction counts: `1,381,624` 24-bit P-word
  reads over `2,093` rendered periods.
- ✅ Sample traffic appeared in `1,952` periods (period tags `143–2094`),
  with `272–884` reads per 32-sample period, median `680`, and mean `707.8`
  reads over active periods (`660.1` including the quiet opening). The
  maximum observed rate is `884/32 × 44.1 kHz = 1,218,263` P words/s;
  the active-period mean is `975,436` P words/s, about `2.93 MB/s` packed
  24-bit data. These are emulator measurements, not a ColdFire bus result.
- ✅ The observed addresses range from `P:0x103dba` through `P:0x1351c1`.
  Within a period, `1,361,306` of `1,379,672` address deltas are `+1`
  (`98.67%`); the remaining jumps are between sequential bursts. The
  sequential runs have median and maximum length `68` words. This is a
  bursty sequential stream with per-voice/sample-boundary jumps, not a
  random-access workload.
- *inferred* A bounded cache needs at least the observed `884` words for
  one maximum-read period before look-ahead and underrun margin; the full
  `201,804`-word sample block cannot be resident. The proposed A2 shared
  window is already fully allocated (`0x30000–0x3ffff`), so a cache needs a
  layout trade-off before it has a home.
- **review / D4:** the user must choose either (A) a ColdFire SDRAM →
  shared-window streaming ring sized for at least the measured active mean
  and maximum rates, or (B) a per-kit cache of sequential bursts, which
  requires surrendering or relocating part of the proposed shared-window
  code/table/P-I budget. Hardware latency, DMA setup cost, and underrun
  margin remain unmeasured.

### WP-A3 layout-driven relocation and driver (24 September 2026)

- ✅ `md_relocate.py` and `md_driver.py` now import the plain address book in
  [`modules/machinedrum/layout.py`](../../modules/machinedrum/layout.py).
  The source spans land at `P:0x38000` and `P:0x30000`, hot units at
  `P:0x1000`, loop words at `Y:0x0c00`, scratch at the proposed addresses,
  and the driver at `P:0x3fe00`. The relocator also emits the proposed
  `X/Y:0x3400` voice-home move and translates host record writes.
- ❌ The earlier A3 report claimed a passing gate while the driver still used
  the replay placeholder voice base `0x800`; that was not a test of the A2
  proposal and is retracted. The actual `0x3400` voice-home gate is not
  qualified: c01_16 ends at `22,526/10,987`, c10 at `32,262/1,251`, and
  c10_3 at `32,257/1,251`, versus exact or known-residual baselines. The
  complete table and the two diagnostic attempts are in [`WP-A3.md`](machinedrum_reports/WP-A3.md).
- ✅ `MD_REPLAY_STATEDIFF` confirms the first c10 divergence begins after the
  relocated voice record is used (`r6=0x3400`); it does not silently fall
  back to the old `0x800` block. c37_16 and c47_2 retain their prior exact
  and known-residual results, so the failure is kit/path dependent rather
  than a parser crash.
- ❌ (superseded 24 Sep, see "Diagnosis of the A3 gate" below) *inferred* The
  proposed `0x3400` home changes a state or address-dependent path in most kits; the current evidence does not establish whether the
  cause is an additional absolute dependency or a stock FX1 collision.
  This is precisely the A2 voice-home decision cost, not permission to pick
  another home overnight.
- **blocked:** the user must choose the selected `A_move_base_fx1` home or
  one of `B_swap_pi_x_words` / `C_batch_overwrite_curve_table`, then the
  relocator/driver gate must be rerun. All A3 results are pending the user’s
  sign-off.

### WP-A4 relocated boot init (24 September 2026)

- ✅ The relocator now descends from the MD boot sequence at `P:0x100057`
  and patches its voice-record, P-I base/count, and sine-base immediates.
  `md_replay --init` zeroes the proposed destinations, calls the relocated
  sequence, and compares its sine, six-voice P-I span, and X/Y voice blocks
  with the capture snapshot.
- ✅ On c10 and c37_16 the init check reports `sine 32768/32768`,
  `pi 9216/9216`, `voice-X 1024/1024`, and `voice-Y 1024/1024`. This validates
  the six-voice proposal’s initialized span; the stock routine’s original
  `0x6000` zero count is layout-relocated to `0x2400` because the proposed
  map caps P-I storage at six voices.
- *inferred* This does not prove that nine/16 stock P-I buffers fit the
  proposed shared window. The count reduction and the shared-window stock
  conflicts remain part of the user’s layout sign-off.
- **review:** the init harness passes its proposed six-voice acceptance
  check, pending the A2 voice-home and window decisions. It must not be
  treated as an OT image qualification while A3 is blocked.

### WP-A6 cycle report at the proposed addresses (24 September 2026)

- ✅ The rebuilt interpreter ran `MD_REPLAY_FETCH=1` with `--reloc --driver`
  on eleven kits. Its fetch hook counts shared-window code and the relocated
  driver at `P:0x3fe00`; private hot-P fetches are intentionally outside that
  hook. The successful measurements are:

  | Capture | Mean cycles/sample | Worst 10 ms cycles/sample | Shared words/sample at worst 10 ms | Adjusted worst (`cycles + words`) |
  |---|---:|---:|---:|---:|
  | cap4/c01_16 | 1,074.1 | 1,142.6 | 907.2 | *inferred* 2,049.8 |
  | cap4/c10 | 326.3 | 333.0 | 207.5 | *inferred* 540.5 |
  | cap4/c10_3 | 498.5 | 518.0 | 348.0 | *inferred* 866.0 |
  | cap4/c1d_16 | 1,365.5 | 1,439.8 | 617.4 | *inferred* 2,057.2 |
  | cap4/c37_16 | 1,209.6 | 1,307.6 | 545.0 | *inferred* 1,852.6 |
  | cap4/c47_2 | 1,388.5 | 1,391.1 | 533.4 | *inferred* 1,924.5 |
  | cap5/c10_16 | 1,309.1 | 1,346.0 | 995.5 | *inferred* 2,341.5 |
  | cap5/c20_16 | 1,666.3 | 1,683.3 | 373.4 | *inferred* 2,056.7 |
  | cap5/c24_16 | 1,256.9 | 1,515.5 | 609.4 | *inferred* 2,124.9 |
  | cap5/c30_16 | 1,064.4 | 1,670.5 | 373.0 | *inferred* 2,043.5 |
  | cap5/c42_16 | 1,462.1 | 1,498.1 | 575.0 | *inferred* 2,073.1 |

  The adjusted column applies the documented one-wait-state-per-shared-fetch
  model to the measured worst window. It already includes the current driver
  and its 36-word MD-state carry in the measured emulator cycles; it does not
  include the unresolved stereo mix.
- ✅ The driver disassembly at `P:0x3fe00` has 192 words. Its eight `do` loops
  execute 1,224 word copies per 16-sample call: 576 X/Y words stashed out,
  36 MD words saved, 36 restored, and 576 X/Y words restored. The two loads or
  stores per copied word are 2,448 move instructions per call, or 4,896 per
  32-sample period. The resulting cycle conversion is *inferred* from the
  instruction count; the hardware wait and parallel-move timing is unmeasured.
- ✅ `MD_REPLAY_FETCH=2` measured about 201.4–201.9 shared driver words per
  sample on the eleven completed kits. The full low-image alternative would
  add 540 saved/restored words in each direction per call; the existing report
  keeps its earlier `~70 cycles/sample` cost as *estimated*, not hardware
  measured.
- 🟡 c40_16 failed twice to produce a fetch table. The interpreter reached
  the relocated driver and then exited `139` after invalid DSP memory reads;
  the retry reproduced `rc=139`. Its cycle row is therefore omitted rather
  than copied from a stale ignored `fetch.txt`.
- 🟡 The D1 stereo mix is not implemented. Option A would read the 16 × 32
  slot words and write 16 interleaved stereo frames per 32-sample period;
  its cycle cost is unmeasured. The packet cannot claim the `~2,500` limit
  until the user selects D1 and WP-A5 supplies the mix measurement.
- All A6 measurements are **pending the user's sign-off** on A2 and D1.

### WP-B1 module and remix skeleton (24 September 2026)

- ✅ `modules/machinedrum/manifest.py` is discoverable as the `MACHINEDRUM`
  `CF_PATCH` skeleton. Its plain `RESOURCE_CLAIMS` are derived from
  `layout.py`: payload A's `P:0x1000–0x1aa4` PLATE/SPRING/DARK donor span and
  the contiguous shared allocations `0x30000–0x40000` for sine, code/tables,
  the six-voice P-I range, and the driver.
- ✅ `remixes/machinedrum.py` omits BusVerb, BusDelay, SEND and TEMPO SYNC,
  keeps the non-reverb stock inserts plus DELAY, and uses the safe no-bus
  `NONE` fallback. `make modules` lists the module and remix, and
  `make bus REMIX=machinedrum` completes its registry, placement, and
  collision path.
- 🟡 The current generic ledger does not arbitrate physical shared-window
  ranges, so these are declarations for B2 to consume, not yet a proof that
  the native image owns those ranges. The current build consequently leaves
  the donor words as stock and reports `used 0`; no native DSP bytes are
  claimed until the user's build-time extraction is wired in WP-B2.
- 🟡 `make remix REMIX=machinedrum` cannot run in this non-terminal session;
  the target exits with `the remixer needs a terminal`. The non-interactive
  `make modules`/`make bus` checks passed. A control `make check REMIX=bus`
  reached its existing DSP dirtystate gate but all 24 renders failed at
  `dsp_host`'s `MmuHelper: shm_open failed, err 1`, including with the
  interpreter environment override; this is an environment/JIT limitation,
  not a B1 build collision.
- All B1 declarations and the resulting no-bus remix are **pending the user's
  sign-off** and remain a skeleton until B2 supplies the extracted DSP.

### WP-B2 build-time extraction audit (24 September 2026)

- ✅ `modules/machinedrum/extraction.py` accepts only the pinned OS 1.63
  update (`sha256 a58cd61f…cabd5`). Section 1 contains 135 load records and
  `234,714` P, `13,130` X and `1,868` Y words; the extraction inventory and
  all derived files stay under ignored `out/machinedrum/os163/`.
- ✅ The standalone `tools/build/md_payload.py` audit consumes those records,
  the common measured hot split of 27 units / `2,724` words at `P:0x1000`,
  the layout-driven relocation, and the `192`-word driver at `P:0x3fe00`.
  The twelve existing plans have the same hot-line signature. No derived
  payload, firmware byte, sample or image was committed.
- ✅ The pinned source's external span `0x140000–0x147fff` has `29,760`
  loaded words and `3,008` gaps. This is the source-load inventory, not a
  claim that the span is free in the OT.
- 🟡 The current A2 map is not emit-safe: the replay proof's
  `M 140000 148000 030000` puts those source words in the proposed sine
  allocation `0x30000–0x37fff`, while relocated init writes all `0x8000`
  words there. The source Y alias `0x147e00–0x147f07` adds a second stage
  distinction: 264 pre-boot words are present, and 201 differ from the c10
  post-boot P view. The audit therefore writes no `payload_A.mem` or
  manifest and leaves B2 blocked.
- ❌ A provisional uncommitted audit output that compared this broad test
  placement to the post-boot c10 snapshot at `P:0x37e00` is retracted. The
  final tool fails closed until the source/window split and alias load policy
  are user-approved.
- 🟡 The follow-up static packing audit counts 15,813 reachable code words,
  including 132 words in the existing low-P loop. The external source set is
  15,681 words; after the measured 2,724-word hot split, 12,957 remain.
  Adding the existing 28,061-word maximum table estimate gives 41,018 words
  against 40,960 proposed shared plus Y-only words, a conservative 58-word
  shortfall. This corrects an initial audit that counted the 132 low-P words
  in the packed area and overstated the shortfall as 190 words. The older
  15,621-word engine estimate is 60 words lower than this static external set;
  classify that difference and resolve the alias policy before claiming fit.
- **blocked / layout review:** the user must choose whether to (A) add an
  alias-aware packed code/table relocation across the proposed shared and
  Y-only ranges, whose earlier engine-only budget is up to `40,958` words in
  `40,960` words with only two words of slack but whose conservative static
  audit is 58 words over, or (B) reserve a separate 32K
  shared source span and surrender/relocate another owner. All B2 results are
  **pending the user's sign-off**.

### Diagnosis of the A3 gate (24 September 2026)

- ✅ The A3 failure does not depend on the voice home. On c20_16, with the
  committed hot plan and driver, voice home `0x1000` and voice home `0x3400`
  both give `8,253 identical, 25,246 differ`. With the voice block left at
  `0x800` (no `Q` lines, driver `VOICE = 0x800`) it still fails:
  `9,424 identical, 24,075 differ (first difference at block 2240)`. The
  plain replay is `33,499/0`.
- ✅ The MD itself does not use `X/Y:0x3400–0x37ff`: the c20_16 snapshot is
  zero there and the plain replay writes nothing there. (The `0x34xx` runs in a
  capture's `written.txt` come from the overnight relocated run; every replay
  rewrites that file.)
- ✅ The cause: `md_relocate.moved()` sends the sine base `0x148000` to the
  sine allocation `0x30000`, and `REGIONS` sends the `0x140000–0x147fff` table
  span to the same `0x30000`. 44 engine reads have the form
  `x:(rN+$148000)` (32) or `y:(rN+$148000)` (12), counted in a linear
  disassembly of both code regions (for example, `P:0x1000c6`,
  `0x100794`, `0x102f38`, `0x103468`), plus `#>$148000` at `0x102c6d` and
  `0x1033f8`; after relocation, they read the table span instead of the sine.
  The 8 `#>$135600` P-I base loads (`0x14210d` … `0x145855`) point at
  `0x3da00`, where the replay has no P-I data. This is the same collision
  WP-B2 reported for the build. No voice home can pass the gate until the sine
  and the tables have separate homes.
- ✅ The sine is read through both X and Y (the 44 sites above), so it must
  stay in the shared window (or be held twice, 64K words, which does not fit).
- ✅ The four `#>$800` immediates are not all voice-block bases. Only
  `P:0x100057` (boot init, patched) and `P:0x64` (the loop, replaced by the
  driver) are. `0x10365c` (`add #>$800,b` under `ifge`) and `0x10368a`
  (`mpyi #>$800,x0,a`) are arithmetic. No snapshot word in `X/Y:0–0x1fff`
  points into `0x800–0xbff`, apart from the loop word `Y:0x141`.
- *inferred* Capacity for the packed split, after the 32K sine in
  `0x30000–0x37fff`: the window's other half holds the 12,957 post-hot code
  words, the 192-word driver and 9,216 words of P-I buffers, which leaves
  about 10,400 words for tables. Private Y `0x4000–0x85ff` holds 17,920.
  Core 0's free private X (`CORE0_MEMORY.md`) adds about 9,870 more:
  `0x2840–0x33ff` (3,008, 🟡 under the heavy fixture), `0x3800–0x3ffe` (2,047,
  🟡 likewise), `0x5840–0x60ff` (2,240), `0x7a92–0x7fff` (1,390),
  `0x8343–0x857f` (573) and `0x8d98–0x8fff` (616). Against the 28,061-word
  maximum table estimate, that leaves about 10K words spare, if enough tables
  are read in one space only. That is not measured yet.
- Next: (1) measure which space (P, X, Y) each table span is read through,
  across the twelve kits; (2) replace the two whole-span moves with per-table
  moves to those homes, and place the sine and P-I data in the replay where
  the patches point; (3) rerun the twelve-kit gate at voice home `0x3400`.

### What the T1–T4 decision frees (24 September 2026)

- *inferred* from the measured sizes: in the window the MD needs at least the
  sine (32,768, read through X and Y) plus the post-hot code (12,957) and the
  driver (192), fetched as P. That is 45,917 words against the 32,749 in core
  1's half. On core 0, the remaining ~13.2K words have to come from T7/T8's
  FX2 window storage, since core 0's private P is full apart from the donor
  span.
- ✅ (`CHIP.md`, `CORE0_MEMORY.md`) The sine cannot be one contiguous 32K run
  in either half as stock stands. `0x30000–0x30047` (72 words, per-frame
  parameter staging, read by both cores) and `0x38000–0x38012` (19 words,
  payload B's entry and per-frame words) are live. That leaves 32,696 and
  32,749 words, both short of 32,768. Placing the sine needs one of: a stock
  patch that moves those words, or a measurement showing that part of the
  sine's index range is never read.
- *inferred* What T5–T8 still lose on core 0 under this decision: the FX1
  memory at `0x3400` (agreed), the three stock reverbs PLATE/SPRING/DARK
  (their P code is the donor span for the hot MD code), about 13K of one of
  T7/T8's FX2 slots, and, unless the access audit places more tables in
  private X, part of T5/T6's private FX2 Y.

### Which space the MD reads its data through (24 September 2026)

Measured with `tools/harness/md_reference/md_reads.sh` (an isolated
interpreter build of `md_replay` with a read hook) on the twelve kits, plain
replay, and classified with `md_reads.py`. Six kits match the reference
exactly or at their known baseline. c01_16, c1d_16, c10_16, c20_16, c24_16
and c42_16 diverge from about block 2,300 on (the WP-R3 interpreter
mismatch), so their late reads come from a slightly different run.

- ✅ Tables (maximal runs of loaded, non-code words in the two source spans,
  30,070 words): **X only 23,000** (18 runs), **X and Y 4,122** (3 runs),
  **Y only 1,706** (13 runs), never read 1,242 (5 runs). The largest X runs
  are `140000..1420ff` (8,448 words), `146000..146dff` (3,584),
  `143f54..1449c8` (2,677) and `1436d4..143d1c` (1,609); the X-and-Y run
  is mainly `100885..101881` (4,093).
- ✅ Several runs are read sparsely (`140000..1420ff`: 92 words read in 71
  separate places), in the pattern of parameter-indexed lookups. A word no
  kit reads is not proof the table is unused, so the classes above keep each
  run whole.
- ✅ The sine `148000..14ffff` is read in full, all 32,768 words, through
  both X and Y.
- ✅ The P-I buffers `135600..13b5ff` are read through X only: 16,905 of
  24,576 words, which is more than eleven voices' 1,536 each. The kits play
  more P-I voices at once than the proposed cap of six.
- ❌ The layout's `y_only_tables` (17,920 words of T5/T6's private FX2 Y)
  assumed that much of the table data could live in Y. Only 1,706 words are
  Y-only.
- *inferred* On core 0 the window must hold the sine, the post-hot code, the
  driver and the X-and-Y tables: 50,039 words. The X-only tables and the P-I
  buffers (23,000 + 1,536 per voice) exceed core 0's ~9,870 free private X
  by 13,130 + 1,536 per voice. With the whole window (65,445 usable) the MD
  fits with at most one P-I voice. With only core 1's half (32,749) it does
  not fit at all. Keeping T5–T8's FX memory and running the MD on core 0
  are incompatible.

### Core 1's memory and the MD's full footprint (24 September 2026)

- ✅ Core-1 ledger (`machinedrum_reports/WP-A2-ledger-core1.txt`; the A1
  configurations A–D rebuilt from Template Live, `core0_wordmap.sh`, 1,000
  frames each, `core0_ledger.py --core 1 --payload B`). Free private X:
  13,837, of which 11,222 is in spans of at least 256 words (`0x2840–0x3eff`
  5,824, `0x5840–0x5fff` 1,984, `0x7a92–0x803f` 1,454, `0x8858–0x8fff`
  1,960). Free private Y beyond the FX slots: 2,139 at `0x07a5–0x0fff`.
  T1–T4's FX memory (FX1 `Y:0x1000–0x3fff`, FX2 `Y:0x4000–0xbfff`) adds
  about 45K words once T1–T4's FX are limited.
- ✅ Stock FX2 footprints in a 16K slot, from the same maps (core 0, T5–T8):
  DARK up to offset 15,779, PLATE 14,336, SPRING 9,523, FLANGER 8,709,
  COMB 3,084, CHORUS 3,070; FILTER, LO-FI, DJ EQ and COMPRESSOR touch
  nothing; DELAY touches nothing (its line runs on the ColdFire). Only the
  top ~600 words of T7/T8's slots are free when a reverb runs there.
- ✅ The sine's X read at `P:0x102ca8` is `x:(r2+n2)` with `m2 = $7fff`: a
  32K modulo buffer. Its base must be 32K-aligned, so the sine can live only
  at `0x30000` or `0x38000` in the window. The shipping BusDelay already
  overwrites `0x38000–0x38012` (its LineL covers all of `Y:0x38000–0x3ffff`),
  so those 19 stock words are dead after boot in practice.
- *inferred* Private P is 8K words per core (`0x0000–0x1fff`): NXP gives the
  DSP56721 248K words of RAM, which is 64K shared + 2 × (36K X + 48K Y + 8K
  P). Payload B tops out at `P:0x1d9f`, so core 1 can give 608 words plus
  its stock FX code (at most 6,158, all thirteen effects): about 6.8K.
- ✅ Executed MD code, union of the twelve kits: 11,394 words (static
  reachable: 15,681). Per kit: up to 7,321 code words, 23,972 X-table words
  (c42_16) and 16,384 P-I buffer words (c20_16, c40_16).
- *inferred* A full MD (sine 32.8K, code 11.4–15.7K, tables 30K, 16 P-I voices
  24.6K, voice records 2K) is about 105K words. Core 1 alone offers about
  97K without touching T5–T8, in the wrong proportions (only 11K of it is X,
  and the sine takes a whole window half). Full fidelity therefore needs part
  of T7/T8's window half.

**Direction (decided on architecture, efficiency and parity):**

1. MD on core 1 (T1–T4). T1–T4 give up their stock FX, both code and memory.
2. Sine at `0x38000` (the only aligned half not already owned by T5–T8).
3. Hot and as much other code as fits in core 1's private P (about 6.8K);
   no window fetch penalty for that part.
4. Tables and P-I buffers read through X move to core 1's private Y by
   flipping those reads from X to Y in the relocated code, where the
   instruction form allows it. That puts them in T1–T4's former FX memory.
5. Only the rest (code beyond private P, the X+Y tables, anything that can't
   be flipped) goes in **T8's FX2 window slot** (`0x34000–0x37fff`). T8's FX2
   is then limited to effects that use no slot memory (FILTER, EQ, DJ EQ,
   PHASER, LO-FI, COMPRESSOR, DELAY). T5, T6 and T7, and every FX1, stay
   stock.

The next measurement is the flip audit: for each table and P-I read, the
instruction and whether its X form has a Y twin (a dual X:Y parallel move
cannot be flipped on one side). If too little can be flipped, the fallback
is T7's slot as well.

### Open for Phase 1

1. Profile data accesses (X/Y) per engine, which gives the tables and
   per-voice state an extracted engine needs.
2. Split the mixer's constant ~1,850 cycles into master effects and
   mixing.
3. Confirm the LFO reading at run time (set an LFO, watch `0x2ad8a6`), and
   trace the 27 unmapped parameters over time rather than at the trig.
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
