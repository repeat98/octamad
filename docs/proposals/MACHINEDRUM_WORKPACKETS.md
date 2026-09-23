# Machinedrum machine: work packets

This plan breaks the Machinedrum (MD) machine into packets that one agent
can finish on its own. The design and the evidence live in
`MACHINEDRUM_MACHINE.md` (section 12 holds the measurements). Read its
section 1 decisions and section 12 before starting any packet.

**Goal.** An MD instance plays on the Octatrack:
- one instance per OT Part, on tracks **T5–T8 only** (core 0);
- all 50 synthesis engines (GND 3, TRX 14, EFM 8, E12 16, P-I 9);
- an embedded 16-part sequencer (option B), edited through OT grid
  recording;
- saved with the project.

**Milestones.**
- **M1**, a flashable proof: T5 plays MD voices from a fixed kit, with no
  UI.
- **M2**, playable: the ColdFire drives the records, the parameters work,
  and the machine can be selected.
- **M3**, the sequencer and UI.
- **M4**, persistence, MIDI and qualification.

---

## Status

This table is the single place that says what is done. When you **start**
a packet, set its row to `claimed`, with the branch and the date, commit
that alone, and push or merge it, so no one else picks the same packet.
When you **finish** one, set it to `done` (or `blocked`), with the commit
and a link to your report. Edit only your own packet's row. Other rows
change only through a merge.

The report goes in `docs/proposals/machinedrum_reports/<packet>.md`. Copy
`machinedrum_reports/TEMPLATE.md`; one file per packet, so agents working
in parallel never edit the same file. New measurements still go into
`MACHINEDRUM_MACHINE.md` section 12, and the report links to them.

Statuses:
- `todo`: nobody is on it;
- `claimed`: someone is working on it;
- `blocked`: waiting on a packet, a user decision, or the hardware (say
  which in the Notes);
- `review`: finished, waiting for the user's decision or sign-off;
- `done`: its acceptance check passed and the output is in the report.

| Packet | Status | Branch | Commit | Date | Report | Notes |
|---|---|---|---|---|---|---|
| WP-00 Phase 0/1 and the driver in the replay | done | `machinedrum` | `f4a93d8` | 2026-09-23 | `MACHINEDRUM_MACHINE.md` §12 | replay, relocation, hot split, driver steps 1–3 |
| WP-A1 Core-0 memory ledger | todo | | | | | first packet to hand out |
| WP-A2 The layout | todo | | | | | decision gate: user sign-off |
| WP-A3 Layout-driven relocation and driver | todo | | | | | |
| WP-A4 Boot-time init on the OT | todo | | | | | |
| WP-A5 The stereo mix | blocked | | | | | decision D1 |
| WP-A6 The cycle report at OT addresses | todo | | | | | |
| WP-B1 Module and remix skeleton | todo | | | | | |
| WP-B2 Build-time extraction | todo | | | | | |
| WP-B3 The dispatcher hook | todo | | | | | |
| WP-B4 The fixed trigger path | todo | | | | | |
| WP-B5 Gates and the M1 image | todo | | | | | the user flashes |
| WP-C1 The record transport | todo | | | | | |
| WP-C2 Port the parameter handlers | todo | | | | | |
| WP-C3 Machine registration | todo | | | | | |
| WP-C4 Kits and parameters | todo | | | | | |
| WP-D1 Is the chord free? | todo | | | | | may start now |
| WP-D2 The sequencer data model | todo | | | | | user sign-off on the spec |
| WP-D3 The sequencer engine | todo | | | | | |
| WP-D4 Grid-record view | todo | | | | | |
| WP-D5 Parameter pages | blocked | | | | | decision D2 |
| WP-D6 The info box | todo | | | | | |
| WP-E1 Persistence | todo | | | | | |
| WP-E2 MIDI | todo | | | | | |
| WP-E3 Admission | todo | | | | | |
| WP-E4 Qualification | todo | | | | | hardware |
| WP-R1 E12 sample delivery | todo | | | | | decision D4 follows it |
| WP-R2 The TRX-S2 residual | todo | | | | | decides D3 |
| WP-R3 The interpreter/JIT mismatch | todo | | | | | |
| WP-R4 The stale toolchain | blocked | | | | | the user reruns `scripts/setup.sh` |
| WP-R5 The c47_2 anomaly | todo | | | | | |
| WP-R6 The MD mixer's per-voice section | blocked | | | | | only if D1 = B |

---

## 0. Rules for every packet

0. **Commit and push to octamad; never to octabam.** `origin` is
   `github.com/repeat98/octamad`, and every commit goes there:
   `git push origin machinedrum`. `upstream` is `sambanks/octabam`.
   **Never push to `upstream`.** That is the one git prohibition. The
   unattended overnight goal is `MACHINEDRUM_OVERNIGHT.md`.
1. **Work in the main checkout** (`/Users/jannikassfalg/coding/octamad`),
   on the branch `machinedrum`. This is the user's decision for the
   Machinedrum work (23 Sep 2026), and it overrides `CLAUDE.md`'s worktree
   rule here: no worktrees under `.claude/`, which is gitignored and
   hidden from the user. The MD builds and captures live in the main
   checkout's `out/`. Never `git stash` (other sessions share the stash
   list), and leave files outside the Machinedrum alone.
2. **Never commit an Elektron byte**: no firmware, snapshot, extracted
   blob, sample or `.syx`. Everything derived from the user's firmware is
   built into `out/` (gitignored) at build time.
3. **Measure, don't infer.** Mark claims ✅ (measured), 🟡 or *inferred*,
   and ❌ (retracted, kept beside the correction). A packet is done only when
   its acceptance check has been run and its output pasted into the
   packet's report.
4. **Long jobs run in the background, with progress lines.** Estimate the
   runtime first. Anything over about a minute goes to the background, and
   you say what is running. Never block the session on a silent loop. When
   you kill a job, kill its children too: `pkill -P <pid>`, then the parent.
5. **Disassemble what you assemble.** `dsp_asm` has mis-encoded
   instructions before (`CLAUDE.md`, "The assembler mis-encodes").
   `md_driver.py` already refuses `max`, `dc` and `illegal` in its output,
   and labels that are prefixes of other labels. Do the same checks for any
   new DSP source.
6. **Commits** end with `Co-Authored-By: <model> <noreply@anthropic.com>`.
   Every new measurement goes into `MACHINEDRUM_MACHINE.md` section 12, in
   the same style, and every retraction is propagated.
7. **Stop and report** when an acceptance check fails for a reason the
   packet does not cover. Do not widen the scope yourself.
8. **Keep the status honest.** Claim before you start, and finish with
   the row, the report and the section 12 update in the same commit. A
   packet left `claimed` for more than a day without a commit is free
   again: say so in its Notes.

---

## 1. Tools you will use (all in `tools/harness/md_reference/`)

| Tool | What it does |
|---|---|
| `md_profile` | Runs the MD reference emulator on the user's flash dump. `capture=<ids>` writes a snapshot, a log and the host stream for `md_replay` |
| `md_replay` | Runs the MD voice DSP alone from a capture and compares every voice block with the reference |
| `md_relocate.py` | Moves the MD code and tables and patches every reference; writes `reloc.txt` |
| `md_driver.py` | Assembles `modules/machinedrum/md_driver.asm` for a layout and checks the result |
| `md_dis` | Disassembles the P ranges of a snapshot |
| `kits.txt` | The validation kits |

**Build.** Already done in the main checkout's `out/`. Rebuild only
after changing the tools. The patches in `tools/patches/gearmulator-md-*.patch`
must already be applied in `vendor/gearmulator-md-mm`. Configure with:

```
cmake -S vendor/gearmulator-md-mm -B out/md_reference -DCMAKE_BUILD_TYPE=Release \
  -DDSP56K_FORCE_INTERPRETER=OFF -Dgearmulator_BUILD_JUCEPLUGIN=OFF -Dgearmulator_BUILD_JUCEPLUGIN_CLAP=OFF \
  -Dgearmulator_SYNTH_OSIRUS=OFF -Dgearmulator_SYNTH_OSTIRUS=OFF -Dgearmulator_SYNTH_VAVRA=OFF \
  -Dgearmulator_SYNTH_XENIA=OFF -Dgearmulator_SYNTH_NODALRED2X=OFF -Dgearmulator_SYNTH_JE8086=OFF \
  -DCMAKE_PROJECT_gearmulator_INCLUDE=$PWD/tools/harness/md_reference/md_profile.cmake
```

Then build with
`cmake --build out/md_reference --target md_profile md_replay md_dis -j8`.
The same configure with `-DDSP56K_FORCE_INTERPRETER=ON` into
`out/md_reference_interp` builds the replay that counts fetches: it is
needed only for `MD_REPLAY_FETCH` and is not bit-identical on every kit.

**Captures** take about 30 s per kit, so run them in the background. The
firmware is `<main checkout>/base_firmware/elektron_sps1-1uw_os1.63.bin`.

```
out/md_reference/md_profile <firmware> out/md_profile/cap4 capture=0x10 capture=0x10,0x1d,0x47 \
  capture=0x01,0x02,0x03,0x10,0x11,0x12,0x13,0x14,0x15,0x16,0x17,0x18,0x19,0x1a,0x1b,0x1c \
  capture=0x1d,0x20,0x21,0x22,0x23,0x24,0x25,0x26,0x27,0x30,0x31,0x32,0x33,0x34,0x35,0x36 \
  capture=0x37,0x38,0x39,0x3a,0x3b,0x3c,0x3d,0x3e,0x3f,0x40,0x41,0x42,0x43,0x44,0x45,0x46 capture=0x47,0x48
out/md_reference/md_profile <firmware> out/md_profile/cap5 $(grep -v '^#' tools/harness/md_reference/kits.txt | awk '{printf "capture=%s ", $2}')
```

**The twelve-kit gate.** Every change to the driver, the relocator or the
layout must pass it:
1. For each of the 12 capture dirs, get the baseline with
   `md_replay <dir>`.
2. Relocate with
   `md_relocate.py --hot <all 12 dirs, comma-separated> --loopvars <base> <dir>`,
   assemble with `md_driver.py <dir> --reloc`, and replay with
   `md_replay <dir> --reloc --driver`.
3. The `blocks:` line must equal the baseline on all kits except the two
   known TRX-S2 residuals: c1d_16 +1 block and c10_16 2 blocks. Any other
   difference fails the gate.

Useful `md_replay` switches:
- `MD_REPLAY_OUTDIFF=n` and `MD_REPLAY_STATEDIFF=n` print the first
  differing blocks and records;
- `MD_REPLAY_BLOCKS=n` stops early;
- `MD_REPLAY_WATCH=pc[,pc]` dumps registers at a block entry, and
  `MD_REPLAY_WATCH_DUMP` also writes memory;
- `MD_REPLAY_POISON`, `MD_REPLAY_FOOTPRINT` and `MD_REPLAY_FETCH=1|2` are
  the memory and cycle measurements.

**Replay traps already paid for:**
- A stop address is seen only at a JIT block start. Put a branch before
  every label the replay stops at.
- Never write the reference's record words into a run: they hold voice
  state. Replay the host stream (`C`/`W` lines) instead.
- A value scan cannot tell a pointer from data.

---

## 2. Where things stand (23 September 2026, branch `machinedrum`)

- ✅ The voice DSP runs outside the MD, bit-identical (`md_replay`).
- ✅ It is relocated (two code regions, 987 patches) with the hottest
  2,724 words split into private P (`P:0x1000`, the size of payload A's
  PLATE/SPRING/DARK donor region). Bit-identical on 12 kits.
- ✅ The driver (`modules/machinedrum/md_driver.asm`, commit `f4a93d8`):
  - one call per 16-sample frame, 8 slots per call;
  - the low-memory swap, per-slot output buffers, and the loop words
    moved;
  - bit-identical on 10 of 12 kits; the other two are the TRX-S2
    residuals.
- ✅ **The needs, measured:**
  - code: 15.6 K words;
  - tables: 23–28 K;
  - the sine: 32 K, built at boot by the MD's own init at
    `P:100069–10008d`;
  - P-I buffers: 1.5 K per P-I voice;
  - voice blocks: 1 K of Y, plus about 17 X words per P-I slot at the same
    address;
  - the MD's own low-memory state: 36 words.
- ✅ **The cycles on core 0**, worst kit (all P-I): ~2,280 per sample of
  ~3,120 usable, with the hot split. The window costs +1 cycle per program
  word fetched, and there is no instruction cache.
- ⚠ **E12 samples** (201,804 words at `P:103dba–135205`) cannot live on
  the OT DSP. M1 excludes E12; see WP-R1.
- **Open decisions for the user** (packets that need one say so):
  - D1, the mix: a simple level/pan per part (A, recommended) or the MD
    mixer's per-voice section (B);
  - D2, six knobs per page or the eight-knob custom page;
  - D3, whether to carry the full low image (fixes one TRX-S2 residual,
    ~70 cycles/sample);
  - D4, how E12 samples are delivered.

---

## 3. Packets

Each packet lists its dependencies, what to do, what "done" means, and its
traps. The order within a phase is the dependency order.

### Phase A: finish the DSP side in the replay (toward M1)

**WP-A1 Core-0 memory ledger.** *Depends: none. Static work plus one run
under the port.*
- **Do:**
  1. From payload A's load map (`docs/firmware/DSP.md` §3, `out/dsp/payload_*.asm`,
     `tools/build/dsp_disasm_all.py`), list every X, Y and P range stock
     loads on core 0.
  2. Under the ColdFire port (`ot_emu`, `docs/remixer/`), run a real project
     for about 1,000 frames and record every X and Y word core 0 writes.
     Use the port's existing watch options; if none fits, add a write
     bitmap to the vendored emulator in an isolated tree, never in the
     shared `vendor/`.
  3. Write `docs/firmware/CORE0_MEMORY.md`: a table of ranges marked
     *static table / runtime scratch / runtime state / free*, each with its
     evidence.
- **Done when:** every word of X `0–0x8fff` and Y `0–0xbfff`, plus the
  shared window, is classified, and `Y:0x795–0xfff` is confirmed free or
  corrected.
- **Traps:**
  - `dsp_host` is not the dispatcher (`CLAUDE.md`), so measure under the
    port.
  - A write watch on one alias is blind to the other.

**WP-A2 The layout (a decision gate).** *Depends: WP-A1.*
- **Do:** propose concrete core-0 addresses for:
  - the hot code: donor region `P:0x1000–0x1aa3`;
  - window code and tables, the 32 K sine, and the P-I buffers (1.5 K ×
    at most N P-I voices);
  - the voice Y blocks, 1 K, plus the P-I X words at the same base;
  - the loop words, `STASH` (576 words), `MDSAVE` (36), `OUTBUF` (512),
    `HALF` and `TMP`;
  - the driver code.

  Put the layout in one file, `modules/machinedrum/layout.py`, as a plain
  dict. List every conflict with stock that WP-A1 found. If the voice
  X/Y problem has no free home, write out the three options from section
  12, "The OT-side driver" (move the base, swap the P-I X words, or
  overwrite a read-only stock table during the batch), with their costs,
  and stop for the user.
- **Done when:** the layout has no overlap (checked by a script), and the
  user has accepted it.

**WP-A3 Layout-driven relocation and driver.** *Depends: WP-A2.*
- **Do:** make `md_relocate.py` and `md_driver.py` take their addresses
  from `layout.py`, instead of the replay placeholders (`0x3b000`/`0x30000`
  regions, `--loopvars 0xe00`, `OUTBUF 0xc00`, `STASH 0x1800`,
  `MDSAVE 0x1c00`). `md_replay` needs X/Y writes above `0x20000` to alias
  P as on the OT; the emulator's bridge does this already.
- **Done when:** the twelve-kit gate passes at the OT addresses.
- **Trap:** the voice-block base moves with `r6` only. Check with
  `MD_REPLAY_STATEDIFF`.

**WP-A4 Boot-time init on the OT.** *Depends: WP-A3.*
- **Do:** at DSP boot (or on first MD selection), run the MD's own init
  steps that build the sine (`P:100069–10008d`) and zero the P-I buffers
  and voice records (`P:10005f–100067`, `P:100057–10005e`), relocated. Do
  not port them by rewriting: call the relocated code, with its `#>`
  immediates patched by the relocator.
- **Done when:** a test harness (a new `md_replay --init` mode) runs the
  relocated init on zeroed memory, and the sine and buffers equal the
  snapshot's word for word.

**WP-A5 The stereo mix.** *Depends: WP-A3, decision D1.*
- **Do (option A):** after each call's 8 renders, mix the 16 slot buffers
  of the previous complete period into 16 stereo frames at `X:0`, the
  interleaved L/R audio block the dispatcher passes as `r0 = 0`. Use a
  per-part level and pan read from a 16 × 2-word table in the layout.
  Latency is one period (32 samples).
- **Done when:** a new replay check mixes the reference's per-voice blocks
  in Python with the same law and compares it with the driver's output.
  Bit-exact, or within ±1 LSB with the rounding documented.
- **Trap:** watch for A2 staleness and `mpy` operand order (`CLAUDE.md`).
  Disassemble.

**WP-A6 The cycle report at OT addresses.** *Depends: WP-A5.*
- **Do:** rerun `MD_REPLAY_FETCH=1` (interpreter build) with the final
  layout on all 12 kits. Add the swap and the mix, counted from the
  driver's disassembly or measured. Record the worst kit against core 0's
  ~3,120.
- **Done when:** the table is in section 12 and the worst kit is at or
  below ~2,500, leaving FX room. If it is not, report the options: take
  CHORUS's 329 words, cap the P-I voices, or retrain the hot set.

### Phase B: the OT image (M1)

**WP-B1 Module and remix skeleton.** *Depends: WP-A2.*
- **Do:** `modules/machinedrum/manifest.py` and `remixes/machinedrum.py`,
  following `docs/remixer/MODULES.md` and `CONTRIBUTING.md`. The remix:
  - omits the bus servers (BusVerb, BusDelay, SEND);
  - claims payload A's PLATE/SPRING/DARK donor region;
  - claims the window ranges from the layout.
- **Done when:** `make modules` lists it, `make remix REMIX=machinedrum`
  composes it, and the build's collision checks pass.

**WP-B2 Build-time extraction.** *Depends: WP-B1, WP-A3.*
- **Do:** the build takes the MD code and tables from the user's MD update
  (`modules/machinedrum/extraction.py`, which already pins SHA-256s),
  applies the relocation from `layout.py`, and places:
  - the hot units in payload A's donor region;
  - the rest in the window's load records;
  - the driver.

  Nothing derived is committed. Follow the `.incbin`-from-the-user's-image
  pattern.
- **Done when:** the build is reproducible from the pinned inputs, and a
  dump of the built payload matches the relocated words `md_replay` used,
  checked by a script.

**WP-B3 The dispatcher hook.** *Depends: WP-B2.*
- **Do:**
  1. Find the core-0 dispatcher site where a track's audio block is ready
     before FX1 (`docs/firmware/DSP.md` §5–6, `P:0x41e` module, the FX1
     call `P:0x4c8–0x4d7`).
  2. Add a hook that calls the driver when the track is the Part's MD
     track. The track index comes from the per-track record; how
     ColdFire marks the MD track is WP-B4.
  3. Preserve every register the dispatcher relies on (`CLAUDE.md`: "AN
     EFFECT'S init MUST PRESERVE r1"; r7 bumps).
- **Done when:** under the port (`ot_emu --dsp-pcwatch`), the driver runs
  once per frame on the MD track and never on the others.
- **Trap:** measure the dispatcher under the port; never model it in
  `dsp_host`.

**WP-B4 The fixed trigger path (proof only).** *Depends: WP-B3.*
- **Do:** with no ColdFire MD code yet:
  - when the MD track's OT trig fires, which is visible in its per-track
    record at `X:0x080`, set slot 0's record to a fixed TRX-BD trigger
    record taken from `c10`'s `log.txt`;
  - set slots 1–3 to fixed records too;
  - document which record word carries the trig.
- **Done when:** under the port, with a test project, trigs on T5 produce
  MD audio on T5's output (`make check` with `OT_PROJECT`, its main-out
  capture).

**WP-B5 Gates and the M1 image.** *Depends: WP-B4, WP-A6.*
- **Do:**
  - `make check REMIX=machinedrum`;
  - boot under the port;
  - `dsp_host` renders;
  - a cycle burn measurement if the tooling allows it;
  - write the flash notes: what to press, what to expect, what failure
    looks like, per `docs/remixer/FAILURE_MODES.md`.
- **Done when:** every gate is green and the user has an image in the
  root `out/`, following the user's release convention (firmware for the user goes in the repository root's `out/`). The user
  flashes; you record the hardware result in section 12.

### Phase C: the ColdFire side (M2)

**WP-C1 The record transport.** *Depends: WP-B3.*
- **Do:** add an MD block to core 0's per-frame host transfer
  (`DSP.md` §6c): 16 records × the words the host writes (see section 12,
  "The ColdFire→voice-DSP interface"). The DSP side writes them into the
  voice blocks with the MD's own semantics: word 0 is a trigger.
- **Done when:** a ColdFire test feeds `c01_16`'s host stream through the
  transport under the port, and the driver's voice blocks match the
  replay's.

**WP-C2 Port the parameter handlers.** *Depends: WP-C1.*
- **Do:** the 44 descriptor handlers in the MD OS are pure ISA_A
  functions (about 11 KB, plus about 10 tables), called from the voice
  update at `0x20ad9a`. Link them as a ColdFire unit, relocated from the
  user's MD OS at build time, per the ColdFire module rules in `CLAUDE.md`.
  Do not rewrite them.
- **Done when:** for every engine's `map=` output from `md_profile`, the
  ported handlers produce the same record words from the same parameter
  values. Byte-compare over all 50 engines.

**WP-C3 Machine registration.** *Depends: WP-C2.*
- **Do:** a new machine type, following POLY's registration (`modules/poly-machine`,
  on its own branch; `MACHINEDRUM_MACHINE.md` §8). MD is allowed only on
  T5–T8 and at most once per Part; enforce both.
- **Done when:** under the port, selecting MD on T5 runs the driver, and
  selecting it on T1 or on a second track is refused with a message.

**WP-C4 Kits and parameters.** *Depends: WP-C3.*
- **Do:** 16 parts, each with an engine and its parameters. Parameter
  changes go through the WP-C2 handlers, and the records through WP-C1.
- **Done when:** changing a part's engine and parameters under the port
  changes the rendered audio as `md_profile` does for the same edits.

### Phase D: sequencer and UI (M3)

**WP-D1 Is the chord free?** *Depends: none. Static read.* Is "hold track
key + TRIG" unused in stock OS 1.40C? Read the panel handlers
(`docs/firmware/PANEL.md`, `MAINMENU.md`). Report the answer and the
fallback (FUNC + track key).

**WP-D2 The sequencer data model.** Option B: 16 lanes per MD pattern,
with locks, one MD pattern per OT pattern, and length/scale/swing
semantics decided once (`MACHINEDRUM_MACHINE.md` §6). Write the spec
first, and have the user sign it off.

**WP-D3 The sequencer engine.** It schedules lane hits and locks against
the OT clock and transport into the WP-C1 records. Test under the port
with a fixed pattern.

**WP-D4 Grid-record view.** RECORD on the MD track shows the selected
part's lane; hold the track key to select a part; `TRK` is the 17th entry;
PAGE and locks work (§4, "Entering and leaving").

**WP-D5 Parameter pages.** SRC gives parameters 1–6; FUNC+SRC gives 7–8,
the engine, and level/pan (§5 proposal). Use the stock descriptors. The
eight-knob page is decision D2.

**WP-D6 The info box.** It shows the part and engine (e.g. `P05 E12-SD`),
using the `PANEL.md` primitives.

### Phase E: completion (M4)

- **WP-E1 Persistence:** a versioned project extension (§8), with a
  round-trip test.
- **WP-E2 MIDI:** a note-to-part map on the parent track's channel (§6).
- **WP-E3 Admission:** the instance cap, per-core limits, and Part changes
  (§7).
- **WP-E4 Qualification:** full-load cycles on hardware, a soak test, and
  the A/B against the reference renders.

### Research packets (may run in parallel)

- **WP-R1 E12 sample delivery (decision D4):**
  - measure how E12 renders read samples: rate, and random or sequential
    access (`fetch.txt`, and the descriptors at `P:103d7b`);
  - design a ColdFire SDRAM to DSP streaming path, or a per-kit sample
    cache in the window.

  Until then, E12 engines are refused at assignment.
- **WP-R2 The TRX-S2 residual:** its first render after a trigger reads
  scratch it never wrote. Find the words, with a register and memory watch
  at `0x102d49` and after, and decide D3.
- **WP-R3 The interpreter/JIT mismatch:** the interpreter build differs
  from the JIT on c01_16 and c1d_16. Find the instruction.
- **WP-R4 The stale toolchain:** the main checkout's `vendor/dsp56300` is
  still at `c051afad` (before the 22 Sep repin), so `cmp a,b` assembles
  as `max`. Ask the user to rerun `scripts/setup.sh` in the main checkout.
  Do not rebuild the shared `vendor/` yourself: other sessions use it.
- **WP-R5 The c47_2 anomaly:** ~1,215 cycles/sample from the first block,
  with only 2 tracks assigned. Find which default-kit voice costs it.
- **WP-R6 The MD mixer's per-voice section (if D1 = B):** locate level and
  pan in the mixer DSP (section 2 of the update) and separate them from
  the master effects.
