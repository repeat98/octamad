# Changelog

One entry per image that reached a unit, newest first; `Unreleased` is what
main carries beyond the last flashed image. The version the panel shows is
`BUILD` (`make image BUILD=N`); a git tag `OCTABAM<N>` marks the commit each
flashed image was built from.

## Unreleased (main after image 43)

- `make reach` is QUICK by default (29 Sep 2026): the remixes users flash
  that carry the change, one floor remix for tool and build changes, no
  identity, no `make accept`, two shards, background priority on macOS
  (`taskpolicy -b`). `FULL=1` is the previous behaviour, a manual choice
  that nothing requires. A USB MIDI change:
  26 commands full, 2 quick.

- Analog BD: engine selection now lives only in the pool-style browser; the
  former SRC SETUP MODEL control and its encoder editing path are removed.
  The 808 receives a fixed post-desk output trim so default hit energy matches
  the 909 within 0.03 dB over 500 ms. The 909 and both engines' internal states
  are unchanged; the 808 trim adds three DSP instructions per sample.

- The image-stage gates on their own shard (29 Sep 2026): `verify_set
  --stage-only` stages the image and card without running; the image-stage
  module gates (TEMPO BUS reads its host ids from its own run now) are one
  shard job apart from verify_set's. The cover over three shards: 574 s to
  530 s, at the floor of 528 s for its 1,585 s of work. `ot_emu --scenario`
  keeps a boot-time `--block-dump` in the one child that names it.

- The long pole split (29 Sep 2026): check_shards runs a remix that would
  set the wall time as its gate jobs beside the other remixes, longest first,
  from the durations it records in `out/check_shards/times.json`. The cover
  over three shards: 681 s to 574 s, for 1,621 s of work.

- The fork is the snapshot (29 Sep 2026): `ot_emu --scenario "LOG ARGS..."`
  loads a project once and forks one child per run, each from the identical
  loaded machine. The vendored DSP memory is a `shm` object mapped shared
  several times, so each child copies it into private objects first
  (`unshareRanges`, macOS and Linux paths). `verify_scenesp2` runs its three
  frame runs and its editor pass from one load: 109-111 s to 73-74 s on a
  quiet machine. `docs/remixer/TESTING.md` rewritten in full: every gate,
  how to write one, the port features gates use, what it costs.

- Panel scripts at emulated time and fewer boots (28 Sep 2026, second cut):
  `ot_emu --live-script FILE` applies panel lines at emulated times;
  `verify_tempobus` drives the TEMPO window with it instead of a FIFO and
  wall-clock sleeps (the key sequence is 7.1 s emulated). `verify_scenesp2`
  runs both editor cases on one boot (two serial editor boots before).
- USB AUDIO OUT: the consumer is anchored at the host's first EP3 IN poll
  rather than at SET_INTERFACE (28 Sep 2026), so a host that starts
  polling late (macOS, about 460 frames) streams 512 frames behind the
  producer instead of 512 plus that gap; with USB AUDIO IN beside it the
  round trip should fall from about 1,355 frames to about 896, unmeasured
  on a unit. The `0x55` counters gain minfill, maxfill and anchor (fifteen
  longs); `verify_usb` holds the bench's first poll back and checks the
  anchor.

- One boot per gate (28 Sep 2026): `ot_emu --step FRAME:call|poke|dump:SPEC`,
  repeatable, runs a gate's script on one load; `verify_modedefaults` went
  from three Octakit loads to one (38 s with the build on bottleservice).
  `verify_repitch` probes the port's voice silence once and skips the other
  six loads (mods' per-remix half was 2,580 s, the seven loads then skipped
  each playback check).

- The gates, made to fit their changes (28 Sep 2026, #510, #511): a
  manifest edit to the display fields alone, or a module's README, reaches
  `verify_docs`; `make identity`'s moved remixes plan into the accept line
  and the shards instead of serial checks; `make reach` rebuilds a stale
  port; `make accept ... JOBS=n` runs the per-remix halves over shard
  worktrees (23 remixes: 2,930 s wall for 7,877 s of work). The plain
  two-server image stays as `remixes/test/bus`, the fixture `verify_twocore`
  and refhash build: with bottleservice as the fixture the hidden engines'
  host guard passed the delay dry in the DEV hatch.
- The documentation for readers (28 Sep 2026): README opens with where to
  read next; `docs/remixer/TESTING.md` says what every gate proves and what
  none can see; Linux/WSL2 is a section of BUILDING.md; the module pages and
  proof notes were audited against what was measured (image 88 carried
  TEMPO BUS, SCENES P2, RIG HOSTS, the tokened Octakit writer, none
  exercised there); the remix pages say what you get and link the modules.

Image 43 is the last flashed image with an entry of its own. Images built
from main since then that reached a unit, each recorded where it was
measured:

| image | remix | unit | date | record |
|---|---|---|---|---|
| 64 | `usb-audio` (now `test/usb-audio`) | Sam's MKII | 25 Sep 2026 | 16 USB channels at 16 bits, USB MIDI receive at 7,950 msg/s: `remixes/test/usb/README.md` |
| 69 | `usb-audio` | Sam's MKII | 25 Sep 2026 | the same at 24 bits, 3 minutes without a discontinuity after 0.76 s |
| 90 | `usb-out-tracks-main-cue` (Bryan T's build) | Bryan T's MKII | 25 Sep 2026 | MAIN on 17-18, CUE on 19-20 |
| OCTATRICK9 | `octatrick-usb` | Tim Hastie's MKI | 26 Sep 2026 | the synth, the quantizer, direct jump; USB audio on all 20 channels: `remixes/octatrick/README.md` |
| 88 | `bottleservice` at `d6867bd` | Sam's MKII | 27 Sep 2026 | load, play; a fourth MODULATION beside the reverb overran, three fit. It carried TEMPO BUS, SCENES P2 (the twelve-byte detour, before the 28 Sep fix), CC MAP, RIG HOSTS, the tokened Octakit writer and the 20-channel USB AUDIO; which were exercised is not recorded (`remixes/bottleservice/README.md`) |


- bottleservice takes the computer's audio in (28 Sep 2026): USB CROSSBAR +
  USB AUDIO IN CD, the computer's stereo output onto inputs C/D in place of
  the jacks (A/B stay jacks). USB AUDIO OUT MASTER polls every 250 µs at
  high speed (96-byte packets; 1 ms and 360 bytes until now, the form on
  image 88) so a USB AUDIO IN module can take it as its implicit-feedback
  source; the descriptor unit's refusal of IN beside OUT MASTER goes. Port
  only in this form.
- USB AUDIO IN as a stereo feed, placed (28 Sep 2026): Bryan T's USB AUDIO
  OUT / IN (PRs #468, #495: four host channels into inputs A-D, its DSP
  inject poked into SPATIALIZER's stock words) becomes a stereo pair into
  inputs A/B, C/D on the jacks, with the inject a DSP section the build
  places in payload A's donor region and reaches by a hook the ledger sees
  (`schema.DspHook`, `DspSection.hooks`: a section with no chooser row).
  A rig remix carrying it and a server no longer builds an image whose
  dispatcher jumps into the reverb; the ledger refuses the hook site. The
  crossbar setting that cured lost packet tails (SCM BCR, XBS PRS/CRS on
  the SDRAM and SRAM slaves) is its own module, USB CROSSBAR, written at
  the USB controller init instead of at stream-up. Interface 5 is in the
  high-speed configurations only (the unit never served it at full speed);
  GET_INTERFACE(5) answers the alt in force; SET_INTERFACE(5) STALLs an alt
  other than 0/1. The unit's diagnostic scan, per-packet counters and the
  vendor register peek/poke (0x57-0x5b, `usb_reg.py`) are gone; fifteen
  counters stay on 0x56. `Claims.sram` declares the top 1 KB of on-chip
  SRAM the dTDs and packet buffers take. `tools/hw/usb_probe.py` (Bryan T's
  PR #492) runs a host session against a unit and reads both rings'
  counters while the stream is open, with EP3 IN's drain rate as the
  discriminating number for the MKI half-speed report. Remixes `usb-io-<out>-<in>`,
  twelve: the four 250 us out layouts (tracks, tracks-main-cue, main-cue,
  main) by the three IN modules (ab, cd, abcd), each stock - SPATIALIZER +
  USB MIDI + USB CROSSBAR; `usb-out-main-cue` keeps the MAIN + CUE layout. Port only in
  this form. The USB audio modules are named by direction and content:
  USB AUDIO OUT TRACKS (was FULL), OUT TRACKS MAIN CUE (was EXTENDED),
  OUT MASTER (was MASTER), OUT MAIN CUE (was MC), beside USB AUDIO IN;
  remixes `usb-out-tracks` (was `usb-full`), `usb-out-tracks-main-cue`
  (`usb-lean`), `usb-out-master` (`usb-master`), `usb-out-main-cue`
  (`usb-mc`). Earlier entries keep the names of their day. Two more
  modules: USB AUDIO OUT MAIN (MAIN L/R alone every 250 us, the stereo
  pairing for the IN modules; remix `usb-out-main`) and the IN module in
  three widths on one source, USB AUDIO IN AB, IN CD and IN ABCD (host
  channels onto inputs A/B, C/D or A-D; one per remix, shared detour
  sites), each with its own placed inject. `tools/harness/usb_align.py`
  measures MAIN's lag behind the tracks in the twenty-channel stream
  under the port from the tone project's phases: 16 samples, one block,
  on every tone (the tracks come from the previous bank, MAIN/CUE from the
  current pull); the producer now writes MAIN/CUE one block behind the
  tracks' slot and `verify_usb_align` (on the twenty-channel module,
  skips without a source project) reads 0. Heard as MAIN lagging on
  Bryan T's unit; the size on hardware is inferred from the port.
  under the port from the tone project's phases.
  discriminating number for the MKI half-speed report. Remix `usb-io` =
  stock - SPATIALIZER + USB MIDI + USB AUDIO EXTENDED + USB CROSSBAR + USB
  AUDIO IN; `usb-mc` keeps the MAIN + CUE layout. Port only in this form.
- CC FEEDBACK (28 Sep 2026, `modules/cc-feedback`): the OT transmits a
  CC for every live knob byte that changes -- a pattern or part change, a
  project load, MODE DEFAULTS, an incoming CC, a page-2 turn -- so a
  controller's encoders follow the unit; stock echoes page-1 panel turns
  only. One track per UI tick (a detour on the keyrepeat task's loop),
  the live lane against the stock emitter's own last-sent cache
  (`0x46c7bf2c`), page 1 as CC 16-45 and page 2 as CC MAP's 62-73. In
  `bottleservice` and `usb-audio`. `ot_emu --midi-out FILE` dumps UART0's
  transmit bytes; `verify_set` checks them against the lane.
- The port follows a detoured idle park (28 Sep 2026): `Rtos::install`
  reads a `jmp abs.l` at `0x4001fc96` (CF METER IDLE's `m_idle`) and counts
  the loop's first 0x80 bytes as main's park for the idle skip, the burst
  end and run-to-park; a borrowed call still returns to the stock `bras .`.
  `cfmeter`'s set gate passes (card ready, load handled 7.9 s after the
  post; before: never posted).
- SCENES P2's page-2 editor-entry detours displace eight bytes, the span
  Octakit's own entry write takes (28 Sep 2026): at twelve the build
  nopped the stock slot load at entry+8, where her trampoline continues,
  and every page-2 knob turn under Octakit + SCENES P2 (rig-kits,
  bottleservice) halted in `gk_track_setup_byte_fatal`. Measured under
  the port from the panel; never flashed. `verify_modedefaults` and
  `verify_scenesp2` no longer SKIP under Octakit
  (`docs/remixer/FAILURE_MODES.md`).
- `make reach` places a file by what depends on it (28 Sep 2026): the
  Python imports and the `tools/x/y.py` paths the code runs or reads (not
  the ones in comments, docstrings or messages) form a graph over
  `tools/`; a change reaches the gates that transitively depend on it. A
  gate of the shared half reaches `make check-shared` alone (155 s, was
  every remix's per-remix half too); a gate of the per-remix half every
  `check-remix` without the shared half; a file no gate depends on
  (`tools/hw/bcr2000.py`, a render tool) nothing, named as such. The
  Makefile is placed by which targets changed against the base: only the
  check graph, a variable or a define reaches every remix; two new Ghidra
  targets (#483) reach nothing. Before, `tools/harness/`, `tools/hw/`,
  `scripts/` and any Makefile edit reached every remix.
- The build's memo (28 Sep 2026): `tools/remix/runtime_build.py` keeps the
  aPLib packer's output by the sha256 of its input and a `Runtime`'s three
  artifacts (raw, packed, append) plus symbols by the sha256 of the recipe,
  every source file, the stock image, the compiler version and the skipped
  guards, under `out/cache/` (`OCTABAM_CACHE=<dir>`, `OCTABAM_NO_CACHE=1`
  builds cold). A runtime hit is re-verified against the recipe's own
  identities before use. bottleservice: 9 s cold, 1.7 s warm, image and
  report byte-identical; `scripts/refhash.sh check` 24/24 cold and warm.
  Every `make check-remix` builds its image about eight times (the recipe,
  the DRAM boot, the set, the three select probes, the burn) and the
  selftest and `verify_replaces` build every remix; all of it was the same
  bytes. `verify_scenesp2` runs its three boots side by side (83 s wall,
  was 220 s under Octakit; verdicts identical): a pool poked once the
  transport has started never reaches the live lane, with or without a
  transport restart (measured), so the three cannot share a boot.
- The gate run, once each (28 Sep 2026): `make accept REMIXES="a b c"`
  runs the remix-independent half of `make check` once and `make
  check-remix` per remix (report v2: gates `check_shared` and
  `check_remix` where v1 had `check`, reports at `<out>/<remix>/` with
  `summary.json`); it had run the whole `make check` per remix, so a
  `make reach RUN=1` over N remixes ran the shared half N+1 times and the
  per-remix half twice. `make reach` lists one accept line for the
  accepted remixes and, with `STRESS_SOURCE` set, no separate check lines
  for them; `KEEP=1` runs every gate and prints one table; `JOBS=n` runs
  the check-remix lines through `tools/verify/check_shards.py` (`make
  check-remixes`), n detached worktrees of the tree with their own port
  builds, remixes handed out from one queue. `pressure.py render` renders
  its 20 layouts `--jobs` at a time (the cores, at most 8) with both
  payloads dumped once and handed to `rig_render --mem/--memB`; it was
  serial, 9 to 22 minutes of every accept.
- The port's load runs until the engine is idle (28 Sep 2026): LOAD
  PROJECT entered and the engine back at its queue receive with nothing
  queued, reported as `LOAD PROJECT handled, N ms after the post`;
  `--load-ms` is a ceiling (90 s in every harness, was a fixed 20 s run).
  Under Octakit the handler and the command sys queues behind it take
  ~32 s emulated (her persistence work on a fresh card); the fixed run
  started the transport inside it and her page-1 wrapper dropped every CC
  as busy (bottleservice's set gate). ATA latency 8 samples (~180 us per
  data sector, `--ata-latency`) instead of 1: sys consumes the engine's
  reset-time "select bank 0" before the BANK= parse (RTOS_FORK section 7),
  so mods, ok-ms and rig-mods (Octakit + MIDI SCENES) load instead of
  halting in Octakit's activation lifecycle. `docs/remixer/EMU.md`.
- Tape Echo's ColdFire probe (27 Sep 2026): its test vectors are glibc's
  `random()` sequence on every host (macOS's differed, so a failing vector
  here never occurred on the author's Linux), and its host oracle is
  compiled with `-fwrapv`: `modules/tapeecho/cpu.c` lines 251, 303 and
  305 overflow int32 on a steep negative MIX ramp (UBSan), which clang's
  optimiser exploited ("tape output mismatch 3/16 (mode 3)") while the
  ColdFire kernel wraps. The gate is green on this machine; the source
  fix is the author's.
- USB AUDIO in three modules over one source (27 Sep 2026):
  `modules/usbaudio` is `modules/usb-audio-extended` (key USB AUDIO
  EXTENDED, the twenty channels, images byte-identical) and `modules/usbmidi`
  is `modules/usb-midi`. USB AUDIO FULL (`modules/usb-audio-full`, remix
  `usb-full`): the sixteen track channels. USB AUDIO MASTER
  (`modules/usb-audio-master`, remix `usb-master`): two channels, track 8's
  L/R post-FX pre-fader at both speeds, a front L/R stereo input.
  `bottleservice` carries USB AUDIO MASTER; every other USB remix USB AUDIO
  EXTENDED. A remix with two of them is refused by name. USB AUDIO MASTER
  polls every 1 ms at high speed too (bInterval 4, 44/45-frame packets of
  at most 360 bytes); the port's USB bench takes `isohz` so a host script
  polls at the descriptor's rate. Port only.

- `make check` is two halves (27 Sep 2026): `make check-shared
  REMIXES="a b"` runs the gates that do not depend on the remix (the
  ledger selftest, the knob census, the isolated module gates with
  `remix_arg=False`, once for the union of the modules) and `make
  check-remix REMIX=<r>` the rest; `make reach RUN=1` prints and runs the
  shared half once and the per-remix half per reached remix. Running every
  remix on #482 repeated the shared half 25 times.
- The gates follow the modules (27 Sep 2026): a manifest names its own
  verifiers (`schema.Gate`) and its dearest knob settings
  (`Module.dear`, checked against its knobs at load); `make verify` runs
  the shared gates and then `tools/verify/module_gates.py` for the
  selection, so a remix never runs another module's gates and a new
  module needs no Makefile edit. `make accept` takes any remix: the
  pressure stages run when every DSP module declares `dear` and block by
  name otherwise; the stress fixture is derived from the selection
  (servers on their cores' first tracks, the most different FX1 modules
  that fit under the wall). `make reach` classifies the branch's diff
  into the gates it reaches and `RUN=1` runs them; CI prints the list on
  every PR. `pressure.py`'s knob table moved into the manifests. There
  is no default remix any more: `make` and every tool take `REMIX=<name>`
  and refuse without it; the bus, knob-census, Character and CC MAP gates
  ask the registry for the smallest remix carrying what they need
  (`registry.fixture`); refhash names its subject (`bus`) itself. The
  selftest refuses a module no remix carries. `remixes/bamsep26` is
  removed (bottleservice is its strict superset). Running every remix's
  `make check` found: `verify_set` wanted Character's count on an FX1 id a
  remix ran as stock LO-FI (kits, scenes); `generate_cpu.py --check`
  called Tape Echo's cpu.s stale under a gcc other than the one that
  wrote it (it records the gcc and SKIPs under another); `scripts/setup.sh`
  staged `dsp_host` without rebuilding it, so the shared binary had ignored
  `-paramfile` since #388 (verify_miniverb's "MOD residual 0.000", PR
  #356's two reviews); `verify_modedefaults` SKIPs by name under Octakit,
  whose editor wrapper halts a direct call (`gk_track_setup_byte_fatal`).
  selftest refuses a module no remix carries.
  every PR. `pressure.py`'s knob table moved into the manifests.
- Character savings (27 Sep 2026): 355 -> 241 static cycles/sample
  (TAPE 105, TUBE 99, INFL 66 in the SAT fork). Both channels share one
  register for each of FOLD's gq/trim and TONE's k/t; SAT's DRV-0 flag and
  mode are one ring word tested once; the arms reordered so TAPE falls
  through; long immediates moved into ring words; TapeHead's v - v^3 and
  its x0.7 accumulate are `mac`s, g3*trim one exact coefficient; DaTube's
  table split into values then slopes (one index, no mask) with a `mac`
  interpolation; WIDTH hands MIX its outputs in registers (limited as the
  stores were); COMP reads the key's R in TONE. Tilt and level_s states
  moved to $1b..$1d, fold trim to $18, ramp steps to $56..$5b. Payload A
  251 free words, B 855 (on main after #481). Bit-identical: `verify_ident character` 9/9, and
  16 renders moving every knob, DRV to 0 and back, COMP off/on and SAT
  mid-render at -12 dB and a level that drives every clip.
- Spectrum BP into SEM (27 Sep 2026): MODE is LADR SEM ISO VOWL; SEM's SHPE
  sweeps LP (0) -> BP (64) -> HP (127), an equal-power crossfade (a tone at
  the cutoff holds its level within 0.1 dB across the sweep; the notch at
  64 is gone). SHPE draws LP / BP / HP at its stops and the number
  elsewhere (a 89 B formatter cave at 0x400c45b0). SEM at SHPE 64 is
  bit-identical to the old BP; every other mode, and SEM at SHPE 0 and
  127, bit-identical. Saved parts: once per project before play,
  `ot_project.py remap-slot <project> SPECTRUM MODE 2:1,3:2,4:3` (BP ->
  SEM, ISO and VOWL down one; SHPE keeps its value).

- Removed (27 Sep 2026): `PLAN.md` (status as of 21 Sep; its memory
  table is `docs/remixer/PLACEMENT.md`'s), `docs/TIMESTRETCH_PIPELINE.md`
  (every address retracted, superseded by `docs/firmware/REPITCH.md`) and
  `tools/hw/hw_flash7_liveclaim.py` (claims about the retired one-aux
  return). The oracle no longer calls the deleted `oracle.py`; the remix
  READMEs' links follow the directory layout.
- Parallel-move folding (27 Sep 2026): an adjacent move and ALU op with
  no dependency between them become one instruction (the parallel move
  reads its source before the op writes). Only forms the stock payloads
  already run; the audited mpysu orders left alone; no address-register
  write moved closer to its use. BusVerb 36 (1,146 -> 1,090 static
  cycles/sample, payload A 34 -> 70 free words), Spectrum 8, Character 6,
  Modulation 3, BusDelay 1. Bit-identical: BusVerb on ROOM/PLATE/BIG at
  -12 and 0 dBFS sends; BusDelay (3 modes), Spectrum, Character and
  Modulation (every mode) per channel, 25 files.
- BusVerb slot pass (27 Sep 2026): 22 per-sample slots the loop reached
  with two-word displaced moves swapped into the one-word range against
  per-block slots (`_MODE_SLOTS` and `LFOTAB` renumbered with them).
  Bit-identical on every mode, level and track; 1,166 -> 1,146 static
  cycles/sample; payload A 23 -> 34 free words.

- BusVerb wet limiter (27 Sep 2026): a feedback peak limiter on the wet
  before the x2 makeup, ceiling −2 dBFS, attack x0.9 per sample, hold
  between −4 and −2 dBFS, linear release ~150 ms, stereo-linked (the
  right's peak reaches the detector one sample late). At a 0 dBFS send PLATE had railed 7,463 samples on L and
  11,762 on R per 9 s of a drum loop; now 0 on every mode, peaks −1.1 to
  −1.8 dBFS. Bit-identical at a −12 dBFS send. +30 cycles/sample static
  (1,145 -> 1,175); r7 slots $11..$13, with four per-block slots moved
  into the one-word displacement range to keep the RIG BURN probe's words
  (payload A at 23 free). Unheard.

- Modulation cycle pass (27 Sep 2026): LINE 404 → 354, PHSR 394 → 298,
  COMB 339 → 329 words/sample; the rig's priced worst core 2,781 → 2,585.
  Image 88 on hardware overran at the fourth Modulation beside the reverb
  (three fit). Exact rewrites plus two within the reference bars (the
  one-poles as two products, PHSR's stages rolled): LINE renders differ from
  main by ≤ 6 LSB, PHSR by ≤ 1 LSB.

- Removed (27 Sep 2026): the five Mutable-Instruments-flavoured inserts
  WarpFold, Ripple, Rungs, Streamz, BodeShift and their `mutables` remix,
  and the two reference modules HELLO WORLD (`hello`) and HELLO DRAM
  (`hello-dram`) with their remixes and `verify_hello`. None had reached
  hardware. The worked examples are now `modules/character/` (DSP) and
  `modules/repitch/` (ColdFire); the selftest's placer probe uses
  MINIVERB and EUCLID. Every image changes by 36 bytes: FX2 ids 0x0a,
  0x0b, 0x0e, 0x0f, 0x17 and 0x1b are no longer aliased to the fallback
  (descriptor pointer and both payloads' dispatch entries return to
  stock's), so a project that selected one of them runs stock's entry.
- Removed (27 Sep 2026): NIMBUS (Clouds-flavoured granular insert, never
  flashed), its `nimbus` remix, `verify_nimbus` and the `NFRZAT` DEV hook.
  FX2 id 0x1a is free and de-aliased the same way.
- The module table and the remix index are rendered (27 Sep 2026):
  `Module.category`, `author`, `author_url`, `proof`, `proof_note` and
  `Remix.family`, `proof`, `proof_note` in every manifest and selection;
  `make docs` writes README.md's table (by category) and
  docs/remixes/README.md; `verify_docs` in `make check` refuses a stale
  copy, the selftest a module without the fields. A remix is a directory,
  `remixes/<name>/remix.py` + `README.md` (the pages moved from
  docs/remixes/). The remixer's AVAILABLE pane groups by the same
  categories. Eight merged modules had no README row before this.
- RLEN PLEN in `recfix` (26 Sep 2026): RLEN value 65, drawn PLEN, past
  MAX: one loop of the track's pattern on its own scale, so TRIG ONE +
  QREC PLEN records the next pass and stops (RLEN counts master-clock
  16ths and stops at 64 = four bars on a 1/4X track). One cave on the arm
  converter, the setup screen draws PLEN, the part validator's hard-coded
  64 raised to 65. Saved parts keep their meaning. Port-gated only.

- `bottleservice` (26 Sep 2026): the rig + USB MIDI + USB AUDIO + Octakit
  (SCENES KITS bridged). TEMPO BUS and MODE DEFAULTS push Octakit's token
  above the page-1 writer's arguments: her rewrite of the writer's dirty
  store halted the unit on a bare call (found under the port, never
  flashed). Kit save, reload and copy measured intact after it. Tier-0
  maps all 128 MB of SDRAM (her runtime sat in a gap); the port's
  `--interactive` gains `midi <hex>...` and the panel `/midi`.
  `verify_modedefaults` pokes both current-track bytes (`0x80000000`,
  `0x100b14cc`) before its editor call: with one moved, Octakit's editor
  wrapper halts on the disagreement (the FX1 case, T2; T1 was 0 in both).
- SCENES P2 (26 Sep 2026): scene locks and the crossfader reach page 2 of
  FX1 and FX2 (hold a scene, turn a page-2 knob; FUNC + turn removes the
  lock). Locks live in a 144-byte pool inside the Part window (`+0x90522`)
  and follow scene copy / paste / clear / undo. In `bamsep26`; in
  `rig-kits` with the SCENES P2 KITS bridge over Octakit's editor
  wrappers. Refused beside MIDI SCENES (same Part bytes). Port only.

- Knob click census (26 Sep 2026, `make verify-knobs`, in `make check`):
  every continuous knob of the DSP modules moved mid-render; 55 of 134
  cases stepped per block on main, 0 after. Fixed with per-sample ramps
  (Character, Spectrum, Modulation, BusDelay, SEND, BusVerb DEL/DIFF/TIME).
  Known: BusVerb SIZE still steps (integer tank taps). Worst core priced
  2,792 -> 2,836 of 3,120; payload A FREE 415 -> 35 words. Spectrum's
  ENV/LFO-driven cutoff now moves through the same 1/128-per-sample ramp.

- `usb-audio` (26 Sep 2026) follows `bamsep26` again: TEMPO BUS added and
  the host pages draw DEL/REV (`host_slots`) where it had all twelve knobs.

- BusVerb SHFT (26 Sep 2026): six shimmer intervals, low to high: -12, +5,
  +7, +12, +19, +24 (pure ratios 1/2, 4/3, 3/2, 2, 3, 4), default +12. The
  stored index changed meaning (was +12 +19 +7 -12): run `ot_project.py
  remap-slot <project> "REVERB SERVER" SHFT 0:3,1:4,2:2,3:0` once per saved
  project.

- ROUTE A RETIRED (26 Sep 2026): `tools/emu/emu_rtos.py`, `make emu-rtos`,
  `scripts/o6_gate.sh` and `tools/emu/ot_emu/oracle.py` removed. The
  panel runs the port only (`--backend`, `--no-rtc` and `/press` gone;
  `/transport` taps the matrix); `panel_link.py --selftest` boots the
  port; `stage_project` moved to `emu_card`. Tier-0 (`emu_bringup`) stays.
- `ot_project.py migrate-hosts <project>` (26 Sep 2026): carries a project
  saved before image 71 into its host layout, keeping the values: T1 TIME
  slot 1 -> 11, T5's reverb send slot 0 -> REV (slot 1), T5 TIME slot 1 -> 11,
  the new T1 REV and T5 DEL at 0. Once per project. Run on Bottleservice 2026.

- RECORDER HOLD in `recfix` (26 Sep 2026): in sound-on-sound (SRC3 = the
  track) a recorder-buffer voice that reads one sample past its recording
  repeats the last sample instead of playing zero. Port-gated; the click
  Bryan T reported on OCTABAM84 at 128 BPM (`docs/firmware/RECORDER_CLICK.md`
  §5).
- THE HOST PAGES LOOK LIKE THE SEND TRACKS (26 Sep 2026, Sam: "want all
  the tracks to look the same"): BusDelay (T1) and BusVerb (T5) carry
  DEL / REV on page-1 slots 0 / 1 and their pages draw those two only
  (remix `host_slots`); every other engine knob is on the TEMPO window,
  whose labels and the MODE renames live in its own name tables.
  T1's REV (into the reverb) and T5's DEL (into the delay) are new sends,
  SEND's recipe, tapped from the host's dry before its engine; each lands
  bit-identically to a SEND track's on the same core (`verify_onebus`).
  TIME moved to page-2 slot 11 on both engines; BusDelay's WOW is gone
  (at WOW 0 every render is unchanged). Pricer: reverb 1,125 -> 1,145,
  delay 1,041 -> 977 cycles/sample; worst core 2,792 of 3,120.
  STAMP EVERY PROJECT BEFORE PLAY: a part saved before reads its old TIME
  byte as REV and its slot-11 byte as TIME (`stamp-defaults <project>
  bamsep26 --all --keep-mode`, or `ot_project.py host <project>`).

- BusDelay's GRAIN scatter knob (page 2, slot 7) is SCTR, was SCAT (26 Sep
  2026). Name only: slot, count and default unchanged, no stamp needed.
- TEMPO BUS (25-26 Sep 2026): the TEMPO window lists and edits BusDelay and
  BusVerb. UP/DOWN pick the row, A (or B) the value, LEFT/RIGHT the box, LEVEL whole BPM, FUNC + LEVEL 0.1 BPM. A
  mode's `---` rows are left out. Header: `TEMPO 121.2`, then the key
  `◀▲▼▶ A ●`; five rows per box.
- USB AUDIO: MAIN and CUE on channels 17-20 (Bryan T, 25 Sep 2026): the
  high-speed stream is 20 channels, the 16 track channels then MAIN L/R and
  CUE L/R, the words core 0 sends to the DACs (the buffer the stock
  recorder reads for SRC3 = MAIN/CUE, 0x80005e60). 80-byte ring slot,
  <= 960-byte packets. New `usb-lean` remix: stock effects + USB MIDI + USB
  AUDIO, for testing the stream without the rig. On Bryan's MKII as
  `usb-lean` image 90: MAIN on 17/18, CUE on 19/20, levels follow.
- The virtual panel's face is the MKII's (25 Sep 2026): Mark Roberts' octemu
  skin generator (`tools/panel/skin/gen_svg.py`, MIT) in a dark palette,
  served as `/skin.js`; the page's keys, knobs, fader and LEDs sit over it as
  hit areas. PROJ/PART/ARR send FUNC chords while the port runs as an MKI.
- THE VIRTUAL FRONT PANEL (25 Sep 2026), Tim Hastie's, from his fork
  `timhastie/octa-panel` at `be68244`: `make panel REMIX=<name>` runs the
  remix on the port in a browser (LCD, keys, encoders, LEDs, crossfader,
  scenes, sound, takes, the audio pool) on a persistent card
  `out/cards/<project>.img`; `make panel-app` builds his macOS app. His
  port changes are merged into `tools/emu/ot_emu` (`--interactive`,
  pacing, RTC, DMA timers DTIM0-3, bursts, page table, `--dsp-rt`, card
  write-back, memory-to-memory eDMA) and his `--dsp-rt` dsp56300 hunks
  rebased onto our pin (`make dsp-repatch` for an existing tree). Three
  lockstep behaviour changes, each measured by reverting it: the UI tick
  is 120 Hz (132 MHz bus), the firmware mounts the last set at boot, the
  stock delay's eDMA ring copies move data. `--fast` removed (the bursts
  are exact). Nothing on hardware.
- TEMPO BUS (25 Sep 2026):
  - The TEMPO window lists and edits BusDelay's and BusVerb's parameters
    in two boxes, drawn with the stock settings-screen routines: A = row,
    B = value, LEFT/RIGHT = box. LEVEL (BPM) and UP/DOWN (tempo step) are
    unchanged.
  - Edits go through the page-1 writer and the FX2 page-2 stores. A MODE
    change re-defaults its knobs through MODE DEFAULTS.
  - `verify_tempobus` drives it under the port.
  - Nothing on hardware.
- SEND splits into DEL (slot 0, into the delay) and REV (slot 1, into the
  reverb), 25 Sep 2026. A second accumulator (`Y:0xa58..0xad7`) and count
  (`0x983..0x98a`), cleared by the housekeeper with the aux. The chain
  carries `wet × DLY` only; the reverb hears the REV sends plus the chain.
  T1's SEND goes into the delay, T5's into the reverb. `verify_onebus`
  rewritten for it. Stored parts: the send byte becomes DEL; stamp REV.
- DLY on BusVerb's page-2 slot 10 (25 Sep 2026): the delay→reverb chain
  carries `in + wet × DLY`; the delay's WET sets only T1's print. The reverb
  publishes the knob to `Y:0x982`, the delay glides it as WET. Default 127
  = the chain as before; a part saved earlier holds 0 there (stamp or
  `ot_project.py host`). `verify_onebus`: DLY 0 == reverb-only three blocks
  later (−120 dB), T1 bit-identical at DLY 0. Nothing on hardware.
- Image 64 (`usb-audio`) ran on Sam's MKII (25 Sep 2026): enumerates as a
  16-channel 44.1 kHz input and a MIDI port at high speed; every channel
  carries its track's tone; 9.6 minutes of takes with zero discontinuities
  after the first 1.6 s of each host stream, with and without a 7,170
  msg/s USB-MIDI flood and panel load; counters 0 underruns, 0 overruns,
  bankdup unmoved; a fifth take of 180 s on the USBLOAD project (locks on
  every step at 200 BPM, 7,950 USB-MIDI msg/s in, FX knobs turned) clean
  on every channel but the one being turned. One open item: a burst of
  reordered samples in the first 1.5 s of most host streams
  (`FAILURE_MODES.md`). His own image (65, card payload) never installed
  its audio function on this MKII, so no A/B against his build. `usb_counters.py`
  flushes its watch lines. Not tagged: a diagnostic image, the rig modules
  as in image 43.
- MIDI SCENES re-pinned to bkkbrls-del's 1.40MIDISC8.2 (25 Sep 2026):
  MIDI track-1 scene locks no longer reach other tracks (`xf_mix`'s LFO
  probes index `track*32+param`), and an unlocked knob sends its own CC
  again (`write_mix` no longer reloads `d2` from the voice). `gas/*.s`
  regenerated from his 8.2 encoder, every region identical to his bytes;
  `voice_reload` has no caller and is no longer linked (twelve units). His
  own 8.2 `build.py` stops at `SAFE_CAVE overrun 2068`; the linked units
  are placed in DRAM and unaffected. Submodule at his `main` `63ca127` (his
  8.2 plus the gas regeneration, merged as bkkbrls-del/midisc#6). `make check` passes on
  `ok-ms` and `midi-scenes` with OCTABAM89_setgate under the port. Nothing
  on hardware.
- USB AUDIO's counters over a vendor control request (25 Sep 2026,
  `tools/hw/usb_counters.py`, the bench's `counters`, checked by
  `verify_usb`), `tools/harness/click_scan.py`, and image 64 packed from
  `usb-audio` for the first hardware run (the protocol in
  `modules/usb-audio-extended/README.md`). Unflashed.
- USB MIDI and USB AUDIO (25 Sep 2026, markandrus/octemu's work on the
  DRAM platform; remixes `usb` and `usb-audio`): class-compliant USB-MIDI
  mirroring DIN, and a UAC2 sixteen-channel input of the tracks (post-FX
  pre-fader) at high speed, the stereo sum at full speed. Under the port:
  enumeration, MIDI in and out through the firmware's own paths, the
  clock-source requests, a 22/23-frame stream at the 500 us poll. Nothing
  on hardware. DRAM units are now assembled for the chip itself
  (`-mcpu=54455`; every runtime bit-identical), `Linked.include` works
  for DRAM units, and `Override` bridges the shared USB ISR site.
- Route A (`emu_bringup.boot`) folds the OS image's uncached alias at
  `0x48000000` into the same 32 MB as `0x40000000` (25 Sep 2026): octabam's
  loader depacks the DRAM runtime through the alias, so every DRAM remix
  had faulted in that boot (`UC_ERR_WRITE_UNMAPPED`, loader pc
  `0x4010fe92`) and `verify_hidden`'s host-page render drew nothing for
  them. euclid and the USB remixes now reach the handoff there.
- The ColdFire port models the USB device controller and carries a
  scripted host (25 Sep 2026, `ot_emu --usb-host`, `tools/harness/usb_host.py`,
  `verify_usb` in `make verify`): the stock stack enumerates and answers
  mass-storage INQUIRY under the port; octemu's USB-MIDI image built from
  the same stock bytes enumerates with three interfaces and its received
  packets reach the firmware's MIDI FIFO. Off by default, so every earlier
  gate is unchanged. `docs/remixer/EMU.md` "USB".
- The level knobs ramp per sample across each block (23 Sep 2026): the
  reverb's WET, the delay's WET, the delay host's SEND and every SEND
  client's level. Each stepped once per block, the sends with no glide at
  all; a turn on a loud source clicked once per block. dsp_host census on a
  0.3 FS tone, worst step before -> after: a SEND client into the delay
  0.25 -> 0.018 FS, the delay host's SEND 0.185 -> 0.025, the reverb's WET
  0.035 -> 0.003, the delay's WET 0.027 -> 0.002. Knobs still, the renders
  match after the glide-in; `make verify-bus` needs a re-stamp (SAVE=1) on
  this commit. The bus gate also gains three hot chain-hop cases and a
  seven-sender case with the reverb at position 0 (the ninth-instance slot
  at X:0x7a00 is the harness's, and a state slot there renders differently).
- The reverb host's frame bursts (images 58-90, 23 Sep 2026): located to
  the delay's accesses from core 1 into core 0's half of the shared RAM,
  cause open; `docs/remixer/FAILURE_MODES.md` has the table.
- The ColdFire port's EMAC extension-register write knew only the
  fractional layout (23 Sep 2026, from Jannik Aßfalg's stock profile): the
  frame ISR saves and restores ACCext in integer mode every frame, so
  every restore put the saved word's low byte into the accumulator. Fixed
  to the CFPRM/QEMU integer layout, eight assertions in the EMAC gate; the
  set gate's block dump is bit-identical. Docs: `FUN_4000c8a4` is
  mid-operand, the frame builder is inside the frame ISR
  `0x4000aad0..0x4000d9b0`; the stock delay routine ends at `0x4000385a`.
  No image change.
- The efficiency / tech-debt pass (23 Sep 2026), the frame around the five
  per-module entries below: `make verify-bus` grew from 21 to 28 cases
  (GRAIN, REVERSE, PLATE, BIG, the shimmer and the gate had no
  bit-identity case), and `make verify-ident MOD=<station>` is one
  knob-matrix identity gate for any FX1 station (Character and Modulation
  had none). The new GRAIN cases found the two BusDelay record collisions
  in its entry below. SEND's loop multiplies through x0 (its mpysu
  site gone); the rotation flip in all three housekeeping copies cleans A2
  before its store. CLAUDE.md: the r7 block is a per-module census, and
  `move a,b` limits where `tfr a,b` does not. Chip cycles of the rewritten
  loops are unmeasured (the burn sweep on a flashed image is the
  instrument); every number here is the pricer's words or a source census.
- Modulation, the station pass (23 Sep 2026): the allpass stage takes x
  and returns y in x0 (its entry/exit copies and the callers' eight moves
  per channel went, 20 stages per sample), the LFO, LOFI and MIX bodies
  inline, the fixed taps' centre split into i and f per block (`mo_itap`),
  c200 / COMB's period−1 and trim as stream words, mo_herm's index chain,
  six parallel moves with stock precedent. Pricer words per sample LINE
  423 → 372, PHSR 489 → 393, COMB 361 → 321; the rig's priced worst core
  3,121 → 2,737 (four PHSR beside the reverb; 3,120 usable). 13 settings
  bit-identical on the new `make verify-ident MOD=modulation`. An
  accumulator-to-accumulator MOVE limits where TFR does not: `tfr a,b` with
  a parallel store changed the LINE renders and was reverted.
- BusVerb's sample loop on pointers and registers (23 Sep 2026): the u
  vectors, the wet sums and the FWHT walk `$16..$19` / `$3a..$3d` through
  r4/r5/r6; the tank input rides y1 through fbA/fbB, the chain word y1
  through the four diffusers, g y0 through the in-loop allpasses; M/S and
  their high-cut values, the shimmer parks and the allpass phase sit in
  x1/y1/b/n0; the aux write/read pointers in n2/n3. One-word displaced
  accesses per sample 206 → 111, pricer 1,135 → 1,117; 28 bus-gate cases
  bit-identical. Dead code out (two spacing loads, a dead `(r4)+`, two
  redundant m5 writes, the m6 writes around the FWHT). The header's r7 map
  is a census (sixteen free slots; it said full), the state-table
  description matches the code (6 + 2 words per line), the parameter list
  matches the manifest; `REVERB.md`'s TIME law, GATE hold (52–784 ms),
  memory table (bloom allpasses added) and register note follow the code.
- Character efficiency pass (23 Sep 2026): the loop's state pointers go
  through n3 alone (states relaid at `$3e..$45`, the tilt block at r4 +
  n3), COMP's key read from the untouched frame, the tilt's k / TapeHead's
  0.7 / TUBE's R loaded once per sample or from the ring, twelve parallel
  moves, OInflator inlined. Pricer words TAPE 354 → 325, TUBE 339 → 321,
  INFL 268 → 245; 903 → 888 words per payload. Bit-identical on
  `verify-ident` (9 settings) and a T8 GLUE render. Stale header slot map
  and comments (the return, TXTR, the old BUS mode) rewritten.

- BusDelay sample loop on pointers and registers (23 Sep 2026): the aux
  accumulator read through r3, the chain write at `(r3+n3)`, x_in / lag /
  fraction / TIME ramp / crossfeed terms / stage outputs in registers, the
  GRAIN and REVERSE arms after the line writes writing the wet slots
  themselves (the SHIFTED substitution and its per-block flag removed),
  GRAIN's trips with s / frac / gain / t0 in registers, the cursor in r6 and
  the wet sum in n6, REVERSE's lags and windows in registers. Displaced
  moves per sample CLEAN 91 -> 35, GRAIN 294 -> 102, REVERSE 109 -> 39;
  pricer 1,126 -> 1,028 (GRAIN) cycles/sample; 1,354 -> 1,300 words.
  28/28 `verify-bus` bit-identical. Two per-block writes landed in GRAIN's
  records every block: the PITCH decode's park at raw $49 (grain 3's
  line-L scatter word; moved to raw $16) and the SIZE decode's copy of the
  REVERSE lag cap at raw $56 (grain 3's line-R window multiplier; the copy
  is gone, raw $2a holds the cap). Each moves the two GRAIN cases only. `verify-bus` gained seven cases (the
  delay's GRAIN, REVERSE and PING/TONE arms, the reverb's PLATE, BIG and
  GATE) -- until then every case ran CLEAN and the reverb's default mode.
- Spectrum loop pass (23 Sep 2026): one `do n7` per MODE dispatched once
  per block (only the selected mode's stream is built), the input peak /
  LADR's Grun / CAP's rotation count in address registers across the loop,
  CAP's rings set up per block and written in read order, stock-shaped
  parallel moves, `max a,b` for the peak, LADR's dead G' clamp removed
  (G ≤ 0.645 by the table). Pricer words/sample SVF / VOWL / LADR / ISO
  126 / 216 / 238 / 292 → 107 / 170 / 198 / 250; displaced moves per
  sample 9 / 7 / 10 / 17 → 4 / 0 / 0 / 1. `verify-ident MOD=spectrum` and
  `verify-spectrum-ident` bit-identical; payload A FREE 848 → 621.

- Spectrum LADR RES makeup (23 Sep 2026, Sam: "the vol drop desperately
  needs it"): the ladder's output ×M = min(1 + k/2, 2.3), one per-block
  word and one multiply per channel. Loop RMS against dry at RES 64 / 127:
  FREQ 127 −9.4 / −13.5 → −3.5 / −6.3 dB, FREQ 64 −9.1 / −8.6 → −3.1 /
  −1.4; the 0.3 FS noise gate at RES 127 stays off the rails. Every other
  mode bit-identical; VOWL's RES 127 loss is left (no headroom at the
  formant). SEM is flat across RES; ISO within 2 dB open; BP is a bandpass.

- Character DRV drives the curves (23 Sep 2026, Sam: "much too subtle"):
  the saturator's input is x·G with G = 1 + 3·DRV/128 (+12 dB at 127) on
  top of each mode's own law, the output scaled per mode (TAPE ×1, TUBE
  ×(1+d)/G, INFL ×1/G: small-signal +12 / +6 / 0 dB at 127); DRV 0 still
  skips the stage. THD at −20 dBFS, 1 kHz, before → after: TAPE 64
  −40 → −23 dB, TAPE 127 −18 → −11, TUBE 127 −22 → −18, INFL 127 −58 → −37.
  Character 790 → 882 words. Unheard on the unit.

- Disassemble what you assemble, automatically (Jannik Aßfalg, PR #380,
  22 Sep 2026; hygiene pass 23 Sep): every `build_bus.assemble()` compares
  `dsp_asm -list` with `dsp56kDisassemble`'s decode of the same bytes and
  stops on a mnemonic mismatch. Artifacts bit-identical across the 26
  refhash configurations. The `mpy`→`mpysu` sites are counted per module
  in `build_bus.MPYSU_AUDITED` (REVERB SERVER 12 + 9 + 4, SEND 1,
  CHARACTER 1, SPECTRUM 1 per assembly; CLAUDE.md's "23 sites" was stale)
  and a count that differs from the table stops the build with the site
  list, so a clean build prints nothing. `make where A=<addr>` prints every
  doc paragraph citing a ColdFire address plus a disassembly window, by
  scanning the docs on each call; the PR's `firmware/symbols.toml` (a copy
  of every such paragraph, 10,829 lines, append-only) and its seeder are
  not kept. `verify_set` skips the CC-40 check when the fixture's T2 FX2
  id is not a module of the remix and, with Octakit present, expects the
  load to rewrite `kits*` files only, so `make check REMIX=octakit`
  reaches the end.

- Upstream sweep (23 Sep 2026): nordseele's octalab-notes read again at
  `e0dc56d` (nine commits since `40ffa53`) and its findings placed in
  `STORAGE.md` §1 (a FAT directory record's first cluster is the long at
  `+0x11e`, re-read here), `SAMPLE_SAVE.md` §7 (the storage-job entry
  `0x40024168` reads kind/object from `0x460be9e8`/`ec`; a stock save ran on
  his MKI), `RECORDER.md` §2, `MAINMENU.md` §6b, `PANEL.md` §2/§3b,
  `PARAM_PAGES.md` §5g. Octakit's submodule moved to her `c6d3f39` (README
  only; image byte-identical). `verify_menu`'s FX1 chooser check read 0x40
  bytes from `0x400d6060`, four words into the FX2 table the build mirrors
  for Octakit, so `make check` on every Octakit remix had been red since
  15 Sep 2026; the window is the list's 12 words now. Unchanged upstream:
  octemu, dsp56300, octamax, octa-bt-pt, JSFXClones. Moved but not
  re-pinned: midisc 1.40MIDISC8.1 (his CC filter switched off, which this
  module never carried), elektron-firmware-tool (restructured; upstream now
  has `--emit-container`, our patch no longer applies), mc68k-md-mm (an
  HDI08 CVR-read callback).

- Character and Modulation pointer-addressed the same way (22 Sep 2026,
  PRs #377 and #378): displaced moves per sample Character TAPE 79 / TUBE
  74 / INFL 62 → 0 and Modulation LINE 107 / PHSR 136 / COMB 116 → 0, every
  ring a 16-word modulo (stock runs only power-of-two modulos on the chip),
  nine and fifteen renders bit-identical. One documented non-identity:
  Modulation's LOFI latches now clear on a MODE change. Pricer words per
  sample: Character 342 / 327 / 256, Modulation 423 / 489 / 361.

- Spectrum SEM with a SHPE knob (23 Sep 2026): MODE 1 is SEM (was LP), and
  SHPE on page 2 slot 7 is the SEM's mode pot, 0 lowpass, 64 notch (LP +
  HP), 127 highpass, as weights on the SVF's taps computed once per block
  (kHP = min(1, k/64), kLP = min(1, (127 − k)/63)); `---` in every other
  mode. BP stays its own MODE; ISO and VOWL keep their values, so stored
  parts need no re-stamp. Harness: SHPE 127 at DC 0 LSB, 4 kHz +0.2 dB,
  200 Hz −26.9 dB; SHPE 64 cuts its cutoff 28.8 dB and passes DC and
  8 kHz. HP as a sixth MODE (22 Sep 2026, PR #376) lasted a day; MODE is
  back on the five-position tick widget.

- Spectrum's sample loop pointer-addressed (22 Sep 2026): the block's
  coefficients go into streams at r7+$50..$7f once per block and every
  alternative walks them with `(r1)+`, states with `(r2)+`/`(r3)+`, the
  per-sample parks in registers; arithmetic unchanged, six renders across
  every MODE bit-identical. Displaced moves per sample 49 / 78 / 39 / 88
  (SVF / VOWL / LADR / CAP) to 9 / 6 / 9 / 16. Reason: probe 57 (branch
  `probe55`, 22 Sep 2026) timed a one-instruction DO loop on the unit at
  2.00 cycles for a register or pointer move, 3.98 for the one-word
  displaced move, 6.01 for the two-word form; the pricer counts words.

- The DSP core clock measured: 199.9 MHz, 4,532 cycles a sample (probe 55,
  branch `probe55`: timer 0 free-running at CLK/2, the per-frame advance
  printed as an amplitude against a reference, `tools/harness/clock_probe.py`
  on a capture). The rated maximum: no clock headroom. CHIP.md carried
  183.456 MHz / 4,160 until then.

- RIG HOSTS, image 53: a new part's FX1 is NONE (image 52's kept stock's
  FILTER default, which on this image is Spectrum's id with FILTER's page
  bytes: "muted and quiet and modulated" on the unit until re-selected),
  and each track's FX2 page defaults come from that track's own
  descriptor through the id table instead of the stock DELAY's (two more
  detours, 0x40005830 and 0x40005840). Measured under the port on a
  project the firmware created: FX1 0 x8, FX2 6 9 9 9 7 9 9 8, T1's page
  bytes BusDelay's defaults, T5's BusVerb's, T8's the stock delay's.

- Nothing else is selectable on FX2 (image 52, 22 Sep 2026): BusVerb and
  BusDelay are hidden from the chooser (one row, SEND) and keep their
  twelve names on the host page (`named`). RIG HOSTS, a new ColdFire
  module: one detour in the part-defaults initialiser (0x40005688, the
  fourteen bytes that load a track's FX2 default from the stock DELAY
  descriptor's id) writes the id by track instead -- BusDelay on T1,
  BusVerb on T5, the stock DELAY on T8 the master (its beat repeat; Sam,
  22 Sep 2026), SEND elsewhere -- so a project made on the unit hosts
  the bus with no stamp (measured under the port: the ids of a project
  the firmware created read 6 9 9 9 7 9 9 8). `ot_project.py host
  <project>` does the same for an older project. `verify_hidden`'s other
  slot moved from 0x6400 (an FX1 slot since image 48) to 0x6500.

- The bus engines are locked to their host slots (`Remix.locked`, image
  51, 22 Sep 2026): BusDelay runs on T1 and BusVerb on T5, and either is
  an exact dry pass on any other track (the HOSTGUARD body hidden engines
  already took, at proc entry, `r7 == 0x6200`). The stock DELAY row is out
  of the FX2 chooser: every other FX2 is a SEND. `stamp-defaults` warns
  about an engine off its slot. Sam, 22 Sep 2026: a known working
  combination over a free one.
- Character: TXTR (Airwindows Pockey) removed after a high-pitched squeal
  on the unit when it was touched on the master, unreproduced on the
  harness at any value, with garbage RAM or on the GLUE position; WDTH
  takes its page-1 slot 2, page 2 is SAT alone. 304 words per payload
  freed; `pockey_ref.py` and the two codec tables gone.
- Images 44–50: 44 and 45 wedged, 46 washed, 47 and 50 were probes (47:
  the core-1 tracker one ahead on every block; 50: the dispatcher's call
  pattern matches stock's code on a fresh project, no marker). On a fresh
  project on 50 every tested configuration was clean; the THRU-host wash
  of images 40–49 reproduced only in OCTABAM91 and was not bisected
  further.

- The bus no longer needs the cores to agree on the flip's phase (image
  49, 22 Sep 2026): eight accumulator buffers (`Y:0x901..0x980`) and eight
  chain buffers (`Y:0x9d8..0xa57`), a server reads three back, the
  housekeeper clears two on, and a core-1 client counts its own blocks
  from a seed read at init, checked against the rotation once a block
  with a tolerance of one either way (`XBUS.md` "The accumulators",
  "Housekeeping and the rotation"). The per-core tracker, its position-0
  advance and the `T == R + 1` rule are gone. Bus latency 48 samples (32
  before); `verify-bus` reference re-saved for it; the two-core gate
  identical to the one-core control under every skew. BusVerb's SEND
  field moved `0x941` → `0x981`.
- SEND returns at proc entry on an FX1 slot (r7 0x6100/0x6400/0x6700/
  0x6a00, measured under the port; image 48): id 0 is SEND and FX1 NONE is
  id 0, so the client had been running on every FX1 slot with no effect —
  sending from an unseen page byte (audio in the bus with every SEND at 0,
  image 46) and, on core 1, comparing the tracker before position 0's
  advance, which left the core one step ahead whenever core 0's flip
  landed before the 0x6100 call (`XBUS.md` "An FX1 slot is not a client";
  `FAILURE_MODES.md`, the THRU-host wash). 21 words per payload.
- The tracker's self-check of images 44–46 (stamps, hold flag) removed
  (image 48).

Images 44–47 reached the unit and none is a release: 44 and 45 wedged on
the first play (a one-word displaced Y store the chip had never run, then
the self-check's unmasked read of an unseeded slot into a wild Y
address; `CLAUDE.md` for both traps); 46 played with static and the wash
on a T2 THRU host and bled into the bus with every SEND at 0; 47 (branch
`probe47`, a marker tone on a wiped stamp) sounded on every block of plain
play, the measurement behind image 48.

## Analog BD1 — MK1 audition reported 28 Sep 2026

- `OCTATRACK_ANALOGBD1.bin`, SHA256
  `3672634dedb8ce0138d7cf4216bd051a47afac6601dcd2a3c1830def24f39704`.
  mathgonzlez reported that every parameter worked and tweaking caused no
  glitches or unexpected sounds; parameter labels were close to the area edge.
- This is the earlier standalone Analog BD image. The later engine browser,
  horizontal navigation and eight-track admission were not in this report.
  Save/reload, eight simultaneous voices and every FX combination remain
  outside its reported coverage. See `modules/analog-bassdrum/README.md`.

## Image 43 — 21 Sep 2026 (`OCTABAM43`, bamsep26 at b3f6471)

On the unit: the sample-host wash gone (T3 STATIC, a trig every step,
eight loops and a reload clean; the FX2 change on T1 clean). Still
washing: a THRU host past position 0 with a trig on every step
(`FAILURE_MODES.md`, open; not a rig configuration). Not yet heard: the
TIME ramp, the once-per-block glides, the names and `---` per mode,
Character's TONE on page 1, Modulation's five modes.

- The bus participants take a split block's frame offset from `r0` (0 on
  a first call, 2 x split on the a=1 call, as the dispatcher passes it)
  instead of a flag and a split the first call stashed in `$65/$66` for
  the second. Image 42 washed again after a reload and a loop, so PR
  #347's init-store bisect was one lucky run per image; the stash not
  surviving between the two calls on the unit is the reading that fits
  every fact (`FAILURE_MODES.md`). SEND, BusDelay, BusVerb alike; the
  `$65/$66` slots are free. Bit-identical in every gate (dsp_host passes
  the same `r0`); image 43 is the test.

## Image 42 — 21 Sep 2026 (`OCTABAM42`, bamsep26 at d3fceaf)

On the unit: the delay on a trig host clean (T2 THRU and T3 STATIC with a
trig on every step, two loops, OCTABAM91), the fixture that washed on
39, 40 and 41 (all three flashed 21 Sep 2026 without a section here; the
bisect is the first bullet). Not yet heard on the unit: everything else
below (the TIME ramp within the block, the once-per-block glides, the
names and `---` per mode, Character's TONE on page 1, Modulation's five
modes). The image's delay is d3fceaf's; the docs of that commit landed
after the build. Before play: `stamp-defaults <project> bamsep26 --all
--keep-mode` (done on the card for OCTABAM89 and OCTABAM91).

- BusDelay: nothing at `r7+$84` or above. On the unit (21 Sep 2026, images
  40 and 39 alike) the delay on T3 with a sample playing on every step
  printed a white-noise wash from the second pass of the pattern on -- T3's
  LEVEL kills it, FDBK does not touch it, WET scales it, STOP does not end
  it, PLAY does. The delay kept its WET glide state and four per-call words
  at `r7+$84..$88`, the range DSP.md has recorded since 10 Aug 2026 as not
  persisting across calls on hardware; every previous image had the delay
  on T1, a THRU, which plays no voice. The five words moved to raw `$0c $20
  $2a $6d $83` (`r7_latch_slot` 0x86 -> 0x20); bit-identical to image 40's
  engine (`verify_delay`, 28 cases, the reference's latch read at the
  manifest's slot: the manifest is shared, so a reference reading the old
  slot renders garbage and fails, which is what every latch move looked
  like until the marker-fill probe showed the engine writing exactly the
  slots it should). `tools/harness/slot_census.py` is that probe: fill the
  instance block, render, read back which words were written; it found
  GRAIN's pitch words at `$3e/$3f` (spelled `-$b`/`-$a`) under a first
  relocation that a displacement scan had called free. The port cannot see
  the mode (`FAILURE_MODES.md`). Cause inferred from the symptom and the
  record; image 41 is the test.

- BusDelay: the glides run once per block. A trig splits a block into two
  dispatcher calls (a=0 before the trig, a=1 after), and the TIME glide, its
  ramp base and the FDBK/TONE/PING/WET glides ran on both: the ramp
  restarted from last block's state at the trig, a jump of a quarter or
  three-quarters of the glide step (up to ~30 samples on a big TIME move)
  -- a click at every trig while the knob moved, which `dsp_host` cannot
  show (it never splits) and the port does. Gated on the frame offset
  (first call only); the a=1 call keeps the ramp's running value and its
  increment. With it: the 4-sample snap becomes a minimum step of 1/16
  sample per block toward the target, never past it (the last 4 samples
  take 23 ms at a slope of 1/256 instead of one block at 1/4), and the
  glide state is guarded against boot garbage (negative, or past the line:
  start at the target; only an exact 0 was). Bit-identical at rest
  (`verify_delay` against image 39's source, every case); `glide_census`
  0 / 73 / 896 as before; +33 words. Under the port, T1's chain output
  with the sequencer's trigs (`verify_set --midi-file`, spikes per 1,000
  samples > 0.02 FS, `port_click_census.py`): CLEAN
  (`tools/harness/midi/delay_time_clean.midi`, TIME 20 -> 90 -> 20) 22.8 /
  24.3 per window over each glide, max 145 / 164, on image 39's code ->
  1.1 / 3.0, max 7 / 13, the windows at the moves themselves 98 / 127 ->
  0 / 6; REVERSE (Sam's recipe) TIME windows 7.2 / 5.1 (max 51 / 31) ->
  4.1 / 3.0 (max 12 / 10), level with REVERSE's own splice floor. Found
  by the 21 Sep static audit; the census takes its marks from a recipe.

- BusDelay: the four init stores of PR #344 (zeroing the TONE/FDBK/PING/WET
  glide states) are gone: they were the white-noise wash on a host past
  dispatch position 0 with trigs on it, bisected on the unit (38 clean,
  39/40/41 wash, 42 = 41 minus the stores clean; `FAILURE_MODES.md`).
  Mechanism open. The rest of #344 (the audit, the `$85` port measurement,
  the doc corrections) stands.

- Names per mode (Sam, 20 Sep 2026: "size is confusing"): BusDelay's SIZE
  draws GLEN in GRAIN and SLEN in REVERSE; Spectrum's FREQ draws VOWL in
  VOWL (it morphs A E I O U); Modulation's TONE draws BRIT in COMB (the
  string's brightness). Character's TONE is back on page 1 in the return's
  slot 4 and WDTH moves up to page-2 slot 7 (page 1 DRV FOLD TXTR COMP
  TONE MIX, page 2 SAT WDTH); no other effect has an empty page-1 slot.
  Stamp before play: Character slot 4 (TONE 64 over the old RET byte) and
  slot 7 (WDTH 64); CC 38 is TONE, CC 69 WDTH.

- Every knob a mode never reads is named `---` in that mode (Sam, 20 Sep
  2026: "all per-mode knobs ... blank with --- titles, like the others,
  across all effects"), from each engine's reads: BusDelay CLEAN adds SIZE
  and PTCH, REVERSE adds PTCH and PING (the mode pins PING to 0);
  Modulation COMB names RATE, DPTH and WDTH (it has no LFO), PHSR names
  TONE (no line filter). Spectrum (every mode takes the modulated cutoff,
  RES and WDTH), BusVerb and Character have no inert knob. The MODE cave
  renames them, as SCAT/DENS since image 29; `verify_modenames` now checks
  a non-MODE select renames nothing (its own slot's name is the mode's).

- BusDelay: the TIME glide ramps within the block. Sam, 20 Sep 2026 (image
  38): "time and feedback causes crackles on delay ... reverting their
  settings doesn't fix" -- the glide's state moved once per block (up to
  ~17 samples a step) and the loop's tap, REVERSE's heads and GRAIN's read
  base all jumped by the step at every block edge: a click per block for as
  long as the step exceeded a sample (~1 s per big move, in both
  directions, so a revert was another second of it; the exponential tail
  takes ~3 s to settle, which is why it seemed to stay). Measured under
  `dsp_host` (`tools/harness/glide_census.py`: 5,228 / 2,676 / 4,483
  second-difference spikes per mode, 0 / 73 / 896 with the ramp) and under
  the port with the recipe over MIDI (`tools/harness/port_click_census.py`,
  `tools/harness/midi/delay_knob_moves.midi`: 24 -> 6 spikes per 1,000
  samples during the glide in REVERSE, 0 at rest). The loop's Q8 TIME now
  walks from last block's state to this one's a sixteenth of the step per
  sample; REVERSE's lag floor and GRAIN's read base are re-derived per
  sample from it. Bit-identical at rest (`verify_delay`, every case); +28
  words. FDBK and PTCH moves measured clean before and after; the FDBK
  "crackle" was the TIME glide's tail. `dsp_host -sched b:i:s=v` (a knob
  move mid-render) and `-dumpcore`; `verify_set --midi-file` (a CC script
  through the panel's real path).

## Image 38 — 20 Sep 2026 (`OCTABAM38`, bamsep26 at 60f41b0)

On the unit: the reverb on T5 clean (Sam: "verb sounds clean on t5 now")
-- the "less rich / bit-crushed" return of image 35 did not follow the wet
onto the host. Images 33, 34 and 35 were flashed on 20 Sep 2026 without a
section here (the glides; the wow; the RET label); 30-32, 36 and 37 were
built and not flashed. The bullets below are everything since image 29.
Before play: `stamp-defaults <project> bamsep26 --all --keep-mode` (done on
the card for OCTABAM89 and OCTABAM91).

- The bus returns on its hosts (Sam, 20 Sep 2026: the T8 return "has
  proven to be too difficult"; option (b), the chain kept). Each engine
  prints its wet under its host's own dry: T1-4's BusDelay the repeats,
  T5-8's BusVerb the tail (of the sends and the repeats); no return
  anywhere else. Gone: Character's RET (page-1 slot 4 is `---`, a stored
  byte there is never read), `ret_fmt.s`, the position pin's return half
  (GLUE by position stays), the hosts-quiet stamps (`Y:0x9d8/0x9d9`), the
  engines' published stage outputs (`Y:0x9da..0xad9`), the return-station
  liveness stamps (`Y:0x9c4/0x9c5`). The hosts send (a host adds its wet
  in place after its own send tap); the SEND stays refused on T8 (Sam:
  "we still dont want send on t8" -- with MASTER TRACK on its input is the
  mix, the hosts' wet included). Words: Character 1,138 / 1,195 -> 975 / 975,
  BusVerb 1,963 -> 1,914, BusDelay 1,385 -> 1,326; payload A FREE 706 ->
  918, B 1,240 -> 1,519; static cycles reverb 1,159 -> 1,135, delay 1,129
  -> 1,109, Character 639 -> 623. `verify_onebus` rewritten for the host
  prints (T8 still refused; a stored RET byte inert); `verify_set` checks each
  host's chain output and refuses an engine on the wrong core;
  `ot_project.py stamp-defaults` and `ot_spec.py report` warn per part
  about BusVerb on T1-4 / BusDelay on T5-8 (it runs as SEND there). Stamp
  before play (slot 4 127 -> 0). Placement: Modulation moves down on both
  payloads (A 0x17d4, B 0x133b), the shape of OCTABAM5's silence on the
  station banks (`FAILURE_MODES.md`, cause open); if the station banks go
  silent, pad Character back to its previous placement first.

- BusDelay: the tape wow is back and the freeze is gone (Sam, 20 Sep 2026:
  "wow back freeze gone"). WOW on page-2 slot 11 (the freeze's), one depth
  knob, 0 .. ±254 samples, wow 0.8 Hz + flutter 7.3 Hz at an eighth, fixed
  rate, on the loop tap in every mode through the glide's between-samples
  read; WOW 0 is bit-identical to the glide alone (`verify_delay`, every
  case, against image 33's source). The freeze hold, its crossfade, the
  `DFRZ`/`DFRZAT` build hooks and the refhash cases go; CC 67 is WOW. Delay
  1,362 -> 1,385 words. Stamp before play: slot 11 stored 0/1 reads as WOW
  0/1.
- BusDelay (image 33 defect): the glide's fraction slot was raw `$41`,
  inside GRAIN's line-L record (grain 0's window), so in GRAIN the loop tap
  read a window value as its fraction. Found by `verify_delay` when the
  fraction moved: image 33's source differed from itself-with-the-slot-moved
  only in the GRAIN 23 ms +12 case. The lag and fraction are per-sample
  slots `$2b/$2c` now.
- Character RET defaults to 127 and draws as `---` with no value on
  tracks 1-7 (Sam, 20 Sep 2026): a formatter cave
  (`modules/character/ret_fmt.s`) reads the current-track byte and writes
  the descriptor's name field (`RET` on T8, `---` elsewhere, Sam's ask after 35) before
  printing; the build exports every clone's address (`CLONE_<KEY>`) for a
  cave that writes its own descriptor. The DSP already clears the level off
  the master. `verify_labels` reads name and value back from the emulated
  firmware per track; the drawn page is not yet looked at under the port.
- Knob glides against the crackle on knob turns (Sam, 20 Sep 2026: TIME and
  FDBK on the delay brought it back on a clean project): BusDelay reads its
  tap between samples at the glide's fraction and glides FDBK/TONE/PING/WET
  per block; BusVerb glides SIZE (1/64 per block) and TONE/DIFF/SHMR/WET, and
  its init zeroes those slots. Image 33: the crackles gone (Sam, 20 Sep 2026).
- BusDelay: the TIME glide snaps onto its target once within one step. In
  image 33 a TIME increase stopped up to 4 samples short (the /1024 step
  rounds to zero), leaving the tap between samples at rest: a two-sample
  average on every pass round the loop, up to -10 dB at Nyquist per pass.
  Measured: state 600/256 samples below the target stayed there for 2,940
  blocks; with the snap both directions land exactly.
- BusVerb: +6 dB on the wet (WET 127 = ×2); BIG with eight senders at SEND 100
  peaks −8.9 dBFS on the wet alone.
- Modulation: MIX bottom right (page-1 slot 5), LOFI on slot 4 — the wet/dry
  knob sits bottom right on every effect (image 30, on the card).
- MODE top left (page-2 slot 6) on every effect, Character's SAT included;
  page 2 fills from the top left with no gaps: BusVerb `MODE TONE DIFF GATE`,
  Spectrum `MODE`, Character `SAT TONE WDTH`, Modulation `MODE TONE WDTH`.
  `stamp-defaults --all --keep-mode` before play.

## Image 29 — 16 Sep 2026 (`OCTABAM29`, bamsep26 at ed27afe)

On the unit: the link brackets draw, SHFT draws its words on page 1, the
`---` names draw. Before play: `stamp-defaults <project> bamsep26 --all
--keep-mode`.

- The knob pass (Sam, 16 Sep 2026): BusVerb p1 `SEND TIME⌐SIZE SHMR⌐SHFT WET`,
  p2 `MODE TONE DIFF — GATE —`; Character p1 `DRV FOLD TXTR COMP RET MIX`,
  p2 `TONE SAT — — WDTH —`; Modulation p1 `RATE⌐DPTH DLY FDBK MIX LOFI`,
  p2 `— MODE TONE WDTH — —`; links on BusDelay TIME⌐FDBK, SCAT⌐DENS,
  SIZE⌐PTCH and Spectrum FREQ⌐RES, LDP⌐LSP; BusDelay's SCAT/DENS read `---`
  outside GRAIN. `⌐` = the panel's link element (`Param(link=True)`, bit 1 of
  the enable nibble); first use by a module, and the first stepped select on a
  page 1 (SHFT). Renders bit-identical by knob name across the layouts.
  `stamp-defaults --all --keep-mode` before play.
- Modulation: ENS (the Solina) removed; MODE = JUNO DIM FLNG COMB PHSR; FLNG's
  view RATE 8; per-mode output trims (DIM −8, FLNG −7, PHSR −2, COMB −12 dB);
  a LOFI knob on page-2 slot 8 (the delay line clocked coarse and quantised).
  Stored MODE bytes 3..5 read one mode lower: `stamp-defaults` before play.
- BusDelay: the tape wow knobs removed (slots 7/8 are GRAIN's SCAT/DENS).
- BusVerb: MOD / RATE knobs removed, tank modulation pinned; SHMR on page-1
  slot 2 (`stamp-slot <project> busverb 2 0` before play).
- `make check`: the ColdFire-port gates no longer masked as SKIP; the module
  gates (character, spectrum, modulation, nimbus, hello) run; the set gates
  read `~/.octabam_project`; `make image` requires `BUILD=N`.

## Image 28 — 15 Sep 2026 (`OCTABAM28`, bamsep26 at 7b5da98)

- BusDelay: two 32K lines, TIME to 741 ms (1/4 and 1/2T at 121 BPM); a
  stored TIME byte means twice the time.
- Spectrum: TAME removed.
- MODE set over CC 62/68 re-defaults the mode's knobs, as the panel does.

## Images 25–27 — 15 Sep 2026

- 25: the bus engines are add-only pedals with WET knobs; SEND on every
  track; host print only while no return.
- 26: MODE DEFAULTS — a MODE turned on the panel re-defaults its knobs.
- 27: only the MODE select names itself (SIZE / FRZE / SHFT keep their names).

## Image 24 — 15 Sep 2026

- The tempo cave no longer clobbers an FX1 station's page 2 on a bus host
  (note-only cave; the DSP reads tempo from stock).

Earlier images (the 13 Sep 96–100 series, flash 7 = `OCTABAM21`, and before)
are in `docs/remixer/FAILURE_MODES.md`, the module READMEs and the git log
(`git show 3ceba41:docs/history/VOICING.md` for the ear rounds up to 16 Sep 2026).
