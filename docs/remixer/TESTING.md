# How the testing works

Every claim in this repository is checked on the developer's machine,
without hardware, against the developer's own copy of OS 1.40C. This page
is the whole mechanism: what runs, what each gate proves, how a change is
routed to the gates it can affect, how the gates are made fast, how to
write one, and what none of it can see. `CONTRIBUTING.md` is the contract
a pull request signs; this page is how it is met.

```
make check REMIX=<name>          one remix: build, cycles, the shared gates, the remix's own gates
make reach [RUN=1] [FULL=1]      the gates this branch's diff reaches, in order; RUN=1 runs them; quick unless FULL=1
make accept REMIXES="..." ...    the same gates under a strict runner that writes a JSON report
make test-acceptance             the runner's, the classifier's and the shard runner's own tests (no firmware)
make identity                    which remixes' images this branch moved, byte for byte
scripts/refhash.sh check         a build change produced bit-identical artifacts and reports
make ci                          what GitHub Actions runs (no firmware, so no remix)
```

## 1. The instruments

| instrument | what it runs | built by | used by |
|---|---|---|---|
| **the build** (`tools/build/build_bus.py`) | assembles every selected DSP module, links every ColdFire unit, places both, writes `out/mainos_bus.bin` and a build report; refuses on a collision, an overrun or oracle drift; round-trips every assembled DSP word through the disassembler | `make setup` | every gate |
| **`dsp_host`** (`tools/harness/dsp_host/`) | the assembled DSP code on the dsp56300 emulator: renders audio, meters instructions per block, polices memory (`-guard`, `-dirty`), both cores in one process with the shared window (`-memB`), instruction interleave fuzz (`-skew`) | `make setup` | render gates, bit-identity gates, the knob census, the dirty-state gate |
| **the port** (`tools/emu/ot_emu`) | the whole machine: the ColdFire firmware booting the built image, a staged CF card with a real project, the sequencer, both DSP cores, MIDI in and out, USB device and a scripted host, the panel link | `make emu-cf` (per worktree, ~1 min) | the DRAM boot, the set gates, USB, every ColdFire module's behaviour gate |
| **Tier-0** (`tools/emu/emu_bringup.py`, Unicorn with the EMAC patch) | boots the firmware to its scheduler handoff and calls its draw and formatter routines directly | `make emu-setup` (the `.venv`) | label gates, CC MAP, CC FEEDBACK, REPITCH's page gate |

Inputs every gate assumes: `out/raw/section_3_MAIN_OS.bin` (`make os && make
recon`, from your own 1.40C), the submodules (`git submodule update
--init`), and for the set gates a real project directory in `OT_PROJECT`
or `~/.octabam_project`. `docs/remixer/HARNESS.md` is `dsp_host` in depth,
`docs/remixer/EMU.md` the port and Tier-0.

**The verdict vocabulary.** A gate prints `[ok]`/`[PASS]` per check and
exits non-zero on any `[FAIL]`. `[SKIP]` means an instrument, a project
or a toolchain is missing: `make check` still exits 0, `make accept`
refuses the run. `[ -- ]` or `[N/A]` means the gate's subject is not in the
remix (a MODE DEFAULTS gate on a remix without MODE DEFAULTS): passed, not
skipped.

## 2. `make check`: the two halves

`make check REMIX=<name>` is `bus`, `cycles`, then `verify`, and `verify`
is two halves (`Makefile`: `verify-shared`, `verify-remix`). There is no
default remix.

**The shared half** (`make check-shared REMIXES="a b c"`) does not depend
on which remix is selected, so a run over several remixes does it once:

| step | proves |
|---|---|
| `tools/remix/selftest.py` | the ledger refuses every collision it claims to (FX2 id, cave, hook, detour, poke, runtime write, private Y word, FX2 buffer region, DSP hook site), every shipped remix is clean, the placer fills non-contiguous runs in both payloads |
| `verify_slots` | no dead store in BusVerb's per-instance state block |
| `verify_replaces --static` | a declared replacement names a real stock effect and carries its id (the registry only) |
| `verify_docs` | the README module table and the remix index match the manifests and selections (`make docs`); every remix has a README |
| `tools/build/label_fmt.py` | the select formatter caves re-derive from their sources (with `m68k-elf-as` on PATH) |
| `verify_knob_clicks` | the knob census: every continuous knob of the fixture remix's DSP modules moved mid-render, the block-rate step in dBFS; a garbage start stays quiet |
| `module_gates.py --shared` | every manifest gate declared `remix_arg=False` by a module in the selection, once for the union |

**The per-remix half** (`make check-remix REMIX=<name>`), in recipe order:

| step | proves | needs |
|---|---|---|
| `bus`, `cycles` | the image builds; static per-sample cycles of every module and the worst load one core can be asked for, against the measured wall | |
| `verify_dirtystate` | each DSP module rendered from a garbage-filled instance block on silence is silent or identical to the zeroed render | `dsp_host` |
| `verify_initregs` | no module's `init` writes r1/n1/m1 (the dispatcher keeps the effect id there) | |
| `verify_dram_boot` | the image boots under the port; the loader runs once, its `fatal` never, every DRAM window reads back equal to the linked runtime | port |
| `verify_labels`, `verify_modenames`, `verify_hidden` | the firmware's own formatter code prints each select's words; the MODE formatter renames its neighbours; a hidden engine is placed, dispatched, off the chooser and draws nothing | `.venv` |
| `module_gates.py --stage isolated --remix-only` | the manifest gates declared `remix_arg=True` | per gate |
| `verify_menu` | the FX1/FX2 choosers and every cloned descriptor against the chooser logic decompiled from the firmware: row order, formatter vs value count, name-field lengths, link bits | |
| `verify_replaces --image` | on this image, every stock effect id is stock's or declared by `replaces`, on both menus (until 29 Sep 2026 the shared half built all 35 remixes for this: 41 s warm, 402 s on a cold build memo) | |
| `verify_set` | a real project on the image under the port: the load completes, live ids equal the part's, page-2 lanes reach the DSP record, every track with audio has chain output, CCs over MIDI IN move the right bytes, CC FEEDBACK's wire and cache, the load rewrote no project file, the firmware's log is clean | port, `.venv`, project |
| `verify_usb` | the image enumerates under the port with the descriptors its USB modules declare; the streams run at their cadence; mass storage still answers | port |
| `module_gates.py --stage image` | the manifest gates that read the finished image | per gate |

`make bus` runs again between steps that leave a probe build at
`out/mainos_bus.bin` and at the end, so the shipping image is on disk after
a green run.

## 3. Every gate

### Run by `make check` for every remix

The two tables above.

### Declared by modules (`schema.Gate`), run only for remixes that carry the module

| gate | owners | half | proves | needs |
|---|---|---|---|---|
| `verify_twocore` | REVERB SERVER, DELAY SERVER | shared | the servers on their real cores render bit-identical to the one-core DEV hatch, and under four interleave skews; fixture `remixes/test/bus` | `dsp_host` |
| `verify_onebus` | REVERB SERVER, DELAY SERVER | shared | both sends on both cores: each host's wet print, WET passthrough sample-exact, the T8 refusal, stored old bytes inert, four skews | `dsp_host` |
| `verify_grains` | DELAY SERVER | per remix | `Remix.grains` changes GRAIN only: the pricer sees it, every other case bit-identical | `dsp_host` |
| `verify_tempo` | DELAY SERVER | per remix | the delay's tempo snap lands on the tempo word the frame builder publishes | `dsp_host` |
| `verify_burn` | SEND | per remix | the RIG BURN probe image is the shipping one plus an inert, exact knob | `dsp_host` |
| `verify_character`, `verify_spectrum`, `verify_modulation` | the three stations | shared | each station against arithmetic you can predict or a float reference: bypass bit-exact, every mode, bounded resonance, the FX1-only promise | `dsp_host` |
| `verify_miniverb` | MINIVERB | image | eight instances isolated, dirty memory, buffer guards, audio gates | `dsp_host` |
| `verify_euclid` | EUCLID | image | control math, the ColdFire hooks, DSP renders, playback under the port | `.venv`, port, project |
| `verify_tapeecho_cpu` | TAPE ECHO | image | the C reference against the compiled ColdFire port, through the stock delay routine and its DMA protocol | `.venv`, `cc`, port |
| `verify_modedefaults` | MODE DEFAULTS | per remix | a MODE turn through the panel's editor, and a MODE over CC MAP, lands that mode's view in the live lane (one boot, `--step`) | port, project |
| `verify_scenesp2` | SCENES P2 | per remix | page-2 scene locks reach the DSP frame through the crossfader (snap for a select, lerp for a knob); a page-2 turn with a scene held writes the pool, not the Part (one load, four forked scenarios, `--scenario`) | port, project |
| `verify_tempobus` | TEMPO BUS | image | the TEMPO key opens the bus window, its rows edit the hosts, LEVEL and FUNC + LEVEL set the BPM, the window closes clean (a panel script, `--live-script`, on the image and card `verify_set` stages; `verify_set --stage-only` stages them without running) | port |
| `verify_repitch` | REPITCH | per remix | the hook contracts, the page (Tier-0), and playback pitch and position speed through a live tempo change, seven cases | port, `.venv`, project |
| `verify_ccmap` | CC MAP | shared | the CC cave re-assembles to its pinned bytes; CC 62-73 write page 2 and clamp to the count; page-1 CCs reach stock | `.venv` |
| `verify_ccfeedback` | CC FEEDBACK | shared | the knob-change sweep enters the stock CC emitter once per changed byte, gated as stock gates | `.venv` |
| `verify_midiscenes`, `verify_octakit` | MIDI SCENES, OCTAKIT | shared | the two port oracles: the author's own build reproduced byte for byte | submodule, m68k toolchain |
| `verify_usb_in` | USB AUDIO IN AB, CD, ABCD | image | the host's channels land bit-exact on their RX slots, the others stay the jacks', the recorder ring fills, the jacks return at alt 0 | port, `.venv` |
| `verify_usb_align` | USB AUDIO OUT TRACKS MAIN CUE | image | MAIN and CUE are in phase with the tracks in the twenty-channel stream (lag 0) | port, `.venv` |

`verify_repitch_ui` is called by `verify_repitch`; `verify_repitch_reference`
is an offline specification test nothing runs.

### On demand (own `make` target, not in `make check`)

| target | proves |
|---|---|
| `make verify-bus` (`SAVE=1` first) | a bus-layout change is behaviour-preserving over every layout in its case list: stamp, edit, compare |
| `make verify-delay CAND=...`, `make verify-roll CAND=...` | an alternate delay or reverb engine is bit-identical to the shipping one |
| `make verify-ident MOD=<station>`, `make verify-spectrum-ident` (`SAVE=1` first) | a rewritten station is bit-identical across a knob matrix |
| `make verify-midi` | the note to PITCH path, through a build override |
| `make verify-twocore`, `make verify-onebus`, `make verify-knobs`, `make verify-miniverb` | the gates of the tables above, alone |

### The port's own tests

`tools/emu/ot_emu` carries unit tests (`ctest --test-dir out/emu`): `emac`
(both ACCext layouts, the fractional modes, MAC-with-load), `periph`, and
three that read the stock OS (`rtos`, `dsp`, `repitch-stock`/`-patch`).
`make ci-emu` runs the two that need no firmware.

## 4. Module gates: a module carries its own tests

A module declares its gates in its manifest:

```python
gates=(Gate("tools/verify/verify_character.py", remix_arg=False),          # shared half, once
       Gate("tools/verify/verify_grains.py"),                              # per remix, gets the remix name as argv[1]
       Gate("tools/verify/verify_euclid.py", venv=True, stage="image"),    # per remix, after the image is final
)
dear={"DRV": 127, "FOLD": 127, "COMP": 127, "MIX": 127, "WDTH": 127, "SAT": 0},
```

- `remix_arg=False`: the gate builds its own fixture (`registry.fixture`,
  the smallest remix carrying what it needs) and runs once in the shared
  half. `True` (the default): it takes the remix name and runs in the
  per-remix half.
- `stage="isolated"` (default) runs before the menu and set gates;
  `"image"` runs last, on the finished `out/mainos_bus.bin` (and after
  `verify_set` has staged its card).
- `venv=True` runs it under `.venv/bin/python3` when the venv exists.
- A missing script is `[FAIL]`. The same script may not be listed twice.
- `dear` is every knob at its dearest setting by name; the stress fixture
  and the pressure render read it, and `make accept` is blocked by name for
  a DSP module without it.

## 5. Writing a gate

1. **Say what it proves and what it cannot see** in the docstring's first
   paragraph and a closing "What it cannot see" line. The catalogue above
   is built from those.
2. **Print a verdict per check** (`[ok]`/`[FAIL]`), a summary line, and
   exit non-zero on any failure. `[SKIP]` only for a missing instrument,
   project or toolchain, naming what to install; `[ -- ]` when the subject
   is absent from the remix.
3. **Pin arithmetic you can predict.** A render gate compares against a
   number derived from the algorithm or a float reference, never against
   "it sounds right". Prove the gate can fail: a positive control that
   makes the forbidden write, or an input that must change the output.
4. **Build into your own scratch** (`tempfile.mkdtemp` or `out/<gate>/`),
   never fixed `/tmp` names: two builds on one machine read each other's
   files (AGENTS.md).
5. **Under the port, load as few times as you can.** An Octakit project
   load is ~32 s emulated, about a minute of wall time. Three port features
   exist so a gate pays for one:

| need | option | example |
|---|---|---|
| several calls, pokes and memory dumps on one load | `--step FRAME:call\|poke\|dump:SPEC`, repeatable; `-` = after the load before the transport, `N` = frame N after the transport start | `verify_modedefaults`: two editor calls, their lane dumps and a MIDI case on one load |
| a panel sequence (keys, encoders, the level pot) | `--live-script FILE`: lines of `<emulated ms> key\|enc\|pot\|midi\|poke\|quit ...` (`poke ADDR=BYTE[;...]` is `--poke` at that time, since 29 Sep 2026), transport stopped, applied at emulated times | `verify_tempobus`: 65 panel lines, 7.1 s emulated, no wall-clock sleeps, the same on a loaded machine |
| several runs that each need the machine exactly as it was after the load | `--scenario "LOG ARGS..."`, repeatable, `--scenario-jobs N` (default 3): the port loads once and forks one child per scenario; each child writes its stdout to LOG and takes ARGS as its post-load options (`--sequencer`, `--frames`, `--step`, `--poke`, `--call`, `--midi`, `--mem-dump`, `--live-script`, ...) | `verify_scenesp2`: three frame runs and the editor pass from one load |

   Boot-time options (`--dsp`, `--audio-in`, `--audio-out`'s capture, the
   image, the card) belong in the shared part of a `--scenario` command,
   not inside a scenario. `--block-dump` is opened at boot: the scenario
   that names the same path keeps writing it, every other child closes its
   copy. A scenario inherits the DSP cores: a panel-only run forked from a
   `--dsp` load emulates both cores throughout, which cost more than a
   separate load for `verify_tempobus` (measured 29 Sep 2026, 115 s against
   109 s), and detaching the cores after the fork stalls the frame engine. The fork is the snapshot: after `fork()` the port
   copies the DSP cores' shared memory into private objects
   (`unshareRanges` in `tools/emu/ot_emu/main.cpp`; the vendored DSP memory
   is a `shm` object mapped several times, which forked children would
   otherwise share), so each child starts from the identical loaded state
   and none sees another's writes.
6. **Declare it** in the owning module's manifest (`Gate(...)`), or, for a
   gate every remix needs, in the Makefile's `verify-shared` or
   `verify-remix` recipe. `make reach` and `check_shards --by-gate` read
   both; `test_check_shards` refuses a recipe script the shard runner does
   not cover.

## 6. `make reach`: which gates a change reaches

**Two tiers.** The default is QUICK, for working without losing the
machine: a module change checks the remixes users flash that carry it
(`remixes/`), or the smallest test remix when only test remixes do; the
floor for tool and build changes is the one cover remix carrying the most
modules; a build change runs refhash but not `make identity`; no
`make accept`; two shards; every command at nice 10 (the performance cores,
below the desktop; measured on the M3: a CPU task 2.8 s at nice 0 and at
nice 10, 19.9 s under background QoS, `taskpolicy -b`). `FULL=1` is everything below at
full speed. What QUICK gives up: the pressure stages (the dearest layouts
priced and rendered, which catch a module that overruns beside others),
identity's image comparison, and the test remixes and other cover remixes
a change also reaches. `FULL=1` is a manual choice, never required: use it
when you want those, before a flash for instance.

`tools/verify/reach.py` reads the branch's diff against `origin/main`
(`BASE=` for another base) and prints the gates in run order. `RUN=1` runs
them, `KEEP=1` runs every one and prints a table instead of stopping at
the first failure, `JOBS=n` runs the per-remix work over n worktrees. It
refuses a tree that is not rebased onto the base, and before running it
rebuilds `out/emu/ot_emu` when a source under `tools/emu/ot_emu` is newer
than the binary.

| changed | reaches |
|---|---|
| `modules/<name>/` | `make check` and `make accept` for every remix that carries the module |
| `modules/<name>/README.md`, or a manifest edit to display fields only (`doc`, `proof`, `proof_note`, `author`, `author_url`, `category`, docstrings) | `verify_docs` |
| `remixes/<name>/remix.py` (or `remixes/test/...`) | `make check` and `make accept` for that remix; a README alone reaches `verify_docs`; a removed remix the selftest and `verify_docs` |
| the build (`build_bus.py`, `cycle_count.py`, `dsp/`) or anything it imports | `scripts/refhash.sh check`, `make identity`, `make test-acceptance`, `make check-shared` for the cover |
| a gate of the shared half | `make check-shared` for the cover |
| a gate of the per-remix half | `make check-remix` for the cover |
| a manifest gate | its owners' remixes |
| the acceptance runner, the stress generator, `pressure.py` | `make test-acceptance`, the cover, `make accept` on the cover |
| `tools/harness/dsp_host/`, `tools/patches/`, `scripts/setup.sh`, `scripts/vendor.sh` | `make ci-dsp`, then the cover (rebuild the toolchain first) |
| `tools/emu/ot_emu/` | `make ci-emu`, `make emu-cf`, the cover's per-remix half |
| `Makefile` | by target: the check graph reaches identity, the cover and `make ci`; the runner targets `test-acceptance`; others nothing |
| `*.md`, `docs/` | `verify_docs` |
| `.github/` | `make ci` |
| a file no gate depends on | nothing, and the listing says so |

Files under `tools/` are placed by dependency: the Python imports and the
`tools/x/y.py` paths the code runs or reads form a graph; a path in a
comment, docstring or message is not an edge.

**The cover** is the fewest remixes that between them carry every module,
computed from the registry each run (9 of 35 on 29 Sep 2026: bottleservice,
cfmeter, euclid, miniverb, mods, tapeecho, usb-io-main-ab,
usb-io-main-cue-abcd, usb-io-tracks-ab). `REACHARGS=--all` makes the floor
every remix.

**Identity** (`make identity`, `tools/verify/image_identity.py`) builds
every remix from the merge-base (a kept worktree under `out/identity/base`)
and from this tree with the shipping flags and compares image and report
byte for byte. With `RUN=1`, the remixes whose bytes moved are planned into
the same accept line and the same shards as the rest.

With `STRESS_SOURCE=<a local project>` the accept lines run and replace the
check lines for the same remixes. Without it, accept is listed as blocked
and the check lines stay.

## 7. Parallel runs: shards

`tools/verify/check_shards.py` (`make check-remixes REMIXES="a b" JOBS=4`,
and what `make reach JOBS=4` uses) runs each remix's per-remix half in its
own worktree under `out/shards/<i>`: a detached checkout of HEAD with this
tree's uncommitted diff applied, `vendor/` and `.venv/` symlinked, the
stock slice copied in, submodules initialised, its own port built. Shards
are kept between runs and refreshed in place (seconds; `--fresh`
recreates, `--rm` removes). Remixes are handed out from one queue. Logs:
`out/check_shards/<remix>.log`.

**The long pole is split.** A remix whose half would set the wall time
runs as its gate jobs in the same queue as the other remixes' whole
halves, and the queue runs longest first. check_shards records every job's
duration in `out/check_shards/times.json` after each run; `--split auto`
(the default) splits a remix whose last time exceeds both 300 s and the
run's total over the shard count, and with no record the remixes carrying
OCTAKIT. `--split none` or `--split a,b` overrides. Measured on the cover
with three shards (29 Sep 2026): 681 s whole, 574 s split, for 1,621 s of
work (the floor for three shards is 540 s). The image-stage module gates
then became their own job (`verify_set.py --stage-only` stages the image and
card without running; TEMPO BUS reads its host ids from its own run): 530 s
for 1,585 s of work, at the three-shard floor of 528 s.

`make check-remix-gates REMIX=<name>` (`--by-gate`) splits one remix's
half into one job per gate over the shards and prints each gate's time:
the instrument for finding the expensive gate.

**Cores.** The development Mac has four performance cores. Four port
boots at once contend and run slower than three (measured 28 Sep 2026);
`JOBS=3` is the better default when another run shares the machine.

## 8. `make accept`: the strict runner

`make check` tolerates a missing instrument. `make accept`
(`tools/verify/acceptance.py`) runs the same gates and refuses missing
evidence: any `[SKIP]`, a swallowed non-zero exit, a timeout or an
over-budget cycle count fails or blocks the run, and it writes a versioned
JSON report (`out/acceptance/<timestamp>/`, schema
`docs/remixer/acceptance.schema.json`).

```bash
make accept REMIX=bottleservice STRESS_SOURCE=<a local project>       # a fixture generated for the remix
make accept REMIX=bottleservice OT_PROJECT=<a project you prepared>
make accept REMIXES="a b c" STRESS_SOURCE=<dir> JOBS=3                # shared half once, per-remix halves over three shards
```

Stages per remix: preflight (provenance, instruments, the pressure
profile), fixture (`tools/harness/stress_project.py` from `STRESS_SOURCE`,
or `OT_PROJECT` fingerprinted), `check_shared` (once for every remix in
the run), `check_remix`, cycles (a static estimate above the wall fails),
pressure price (every selectable per-core layout against the wall),
pressure render (the dearest six and four random layouts per core on all
eight tracks under `dsp_host -guard -dirty`, metered). A failed or blocked
stage leaves its dependents `not_run`. Every report carries
`hardware_validated: false`. `docs/remixer/ACCEPTANCE.md` has the report
fields; `tools/harness/STRESS_PROJECT.md` the generated project.

## 9. Bit-identity: proving a change changed nothing

- **`scripts/refhash.sh save` then `check`**: 24 build configurations of
  `remixes/test/bus` (the shipping flags, the plain build, the DEV hatch,
  the probes, the overrides); every artifact and every build report
  hashed. Save on main, check on the branch. A path in the report is part
  of the report. Two cases (`plain`, `marker`) refuse to build and the
  refusal is pinned the same way.
- **`make identity`**: every remix, base against head.
- **`make verify-bus`, `verify-ident`, `verify-roll`, `verify-delay`,
  `verify-spectrum-ident`**: a rewrite against a saved reference.

## 10. What it costs

Measured on the development Mac (8 cores, 4 of them performance cores),
with the load average noted because it moves every number:

| run | wall |
|---|---|
| `make check-shared` for a cover | 250-375 s |
| per-remix half, a USB test remix | 115-260 s |
| per-remix half, bottleservice | 468 s (29 Sep 2026, 3 shards; 788 s before the scenesp2 fork, 1,143 s on 27 Sep) |
| per-remix half, mods | 432-627 s (2,580 s before `verify_repitch` stopped loading seven times) |
| the cover's per-remix halves, `JOBS=3` | 530 s (574 s before the image job was split out, 681 s whole, 986 s before the scenesp2 fork) |
| `verify_scenesp2` on bottleservice, quiet machine | 109-111 s one load per run, 73-74 s one load and forked scenarios |
| `verify_tempobus`, quiet machine | 49 s wall-clock paced, 34 s scripted |

Typical changes (with `JOBS=4`, kept shards):

| change | remixes | wall |
|---|---|---|
| a module README or a manifest's display fields | none | seconds (`verify_docs`) |
| one USB IN or OUT module | its few `usb-io-*` remixes (+ bottleservice if it carries it) | 5-15 min |
| USB MIDI (every USB remix) | ~24 | 15-20 min, floored by bottleservice |
| the build | the cover + identity's moved remixes | 25-40 min |

The floor of most runs is bottleservice's half, and inside it the Octakit
project loads (`verify_set`, `verify_tempobus`, `verify_modedefaults`,
`verify_scenesp2`).

## 11. What GitHub Actions checks

`.github/workflows/ci.yml` runs on every PR, on `main` and by hand, on
Ubuntu and macOS, with no Elektron bytes (`make ci` runs the same four):

| job | target | proves |
|---|---|---|
| gates the PR reaches | `make reach` (dry run) | the diff classifies and the branch is rebased |
| acceptance runner tests | `make test-acceptance` | the runner refuses skipped, failed, incomplete and over-budget evidence; `reach` routes as documented; the shard runner covers the recipe |
| dsp56300 + our patch | `make ci-dsp` | the vendored DSP emulator at its pin takes our patch, builds, passes upstream's runner; `dsp_asm` emits the one-word displaced move |
| ColdFire port unit tests | `make ci-emu` | `ot_emu` builds on both hosts (the fork unshare has a macOS and a Linux path) and passes `emac` and `periph` |

**A green CI run says nothing about a remix.** Building, booting and
playing one needs 1.40C; that is why the gates run on your machine and
their results go in the PR body.

## 12. What none of this can see

- **Hardware timing between the two DSP cores.** `dsp_host` runs them
  lock-step or under a chosen interleave; a clean result under every skew
  is not evidence a race is gone. A local red is a defect.
- **The cycle budget.** The emulator renders an engine the chip cannot
  afford; `make cycles` bounds it statically (instructions, no contention).
  Hook-only DSP sections (USB AUDIO IN's inject) are not in the price.
- **The dispatcher's facts.** `dsp_host` hands each effect an r7 and r6 it
  computes; logic keyed on them is measured under the port
  (`--dsp-pcwatch`).
- **The panel against the DSP.** `dsp_host` pokes knob values directly; a
  slot can draw a knob and publish nothing. `verify_menu` and the Tier-0
  gates cover the descriptor side, `verify_set` the delivery.
- **Stored project data.** A part saved under an older layout feeds the new
  one its old bytes. Stamp projects after a layout change.
- **The port's audio and DMA gaps.** The stock DELAY's rings and the
  recorder's DMA are not modelled; the port's main mixdown reads a gain of
  0, so playback gates skip their audio checks (`docs/remixer/EMU.md`).
- **The bench's clock under load.** `verify_usb` and `verify_usb_in` count
  overruns and underruns against a scripted host; with shards and another
  run on the machine the host falls behind and a remix fails that passes
  alone. Rerun a USB red alone before believing it.
- **Whatever the metric cannot represent.** A harmonic metric cannot see
  an inharmonic block-rate step; an AC-coupled capture cannot see DC; a
  reverb smears a per-sample fault. Ask what the instrument cannot see
  before trusting a null result.
- **Ears.** GRAIN's right-channel hiss passed every gate and was found by
  listening (`docs/remixer/HARNESS.md`, the listening protocol).

`docs/remixer/FAILURE_MODES.md` is the register of what has gone wrong on a
unit; `AGENTS.md` the traps that produced clean assembly of wrong machine
code.

## 13. Before a pull request

```bash
git fetch upstream && git rebase upstream/main
make reach BASE=upstream/main RUN=1 KEEP=1                                          # quick, while working
STRESS_SOURCE=<a local project> make reach BASE=upstream/main FULL=1 RUN=1 KEEP=1 JOBS=3   # optional: everything, at full speed
```

Paste each command and its result into the PR body (the template asks for
them). A DSP module without `dear` makes `make accept` report `blocked`;
say so. A build change adds `scripts/refhash.sh check` with the baseline
saved on main. Then flashing, on your own unit, with `BUILD` bumped so the
version string maps to a commit (`docs/remixer/FLASHING.md`).
