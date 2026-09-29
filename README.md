# octabam

[![CI](https://github.com/sambanks/octabam/actions/workflows/ci.yml/badge.svg)](https://github.com/sambanks/octabam/actions/workflows/ci.yml)

An unofficial community remixer for the Elektron Octatrack's operating
system, not affiliated with Elektron: pick the modifications you want and
build them into one firmware image from your own copy of OS 1.40C.

A modification is a **module** (`modules/<name>/`), a selection of modules
is a **remix** (`remixes/<name>/remix.py`), and `make image REMIX=<name>` composes
a remix into a card-flashable image: placing code, wiring hooks by symbol,
refusing collisions by name, and proving every ported module against its
author's own build byte for byte. No firmware is distributed here; every
image is derived from the user's own 1.40C on the user's machine.

Every module is contributed by its author and credited in the table
below. Pull requests are accepted: a module, a port of an existing mod, a
fix, a doc correction (`CONTRIBUTING.md`, `docs/remixer/MODULES.md`).
Issues are disabled and there is no request queue. The licence is MIT; a
fork that takes requests and tracks issues is allowed.

**[docs/remixes/BUILDING.md](docs/remixes/BUILDING.md)** is the step-by-step
guide from a fresh machine to a flashed unit; its §8 is how to write a
remix of your own.
**[docs/remixes/README.md](docs/remixes/README.md)** lists every remix with
its contents and how far it has been proven; each remix's own README is
beside its selection in `remixes/<name>/`.

## What it carries

Every module, with its author. Those with a repository are built from it.
The table is rendered from the manifests (`make docs`; `make check` refuses
a stale copy). `make modules` prints the same index with the compatibility
matrix (which ColdFire modules can share an image, from the same check the
build makes; `✓*` is a pair that needs the named bridge) and every remix.
The last column is how far the module has been proven: `make check`
(builds and boots under the port), a local render, port-gated (a gate
under the ColdFire port pins its behaviour), or on hardware, with the
unit, image and date.

<!-- modules:begin -->

### Effects: the bus

| module | author | what it does | proof |
|---|---|---|---|
| [**DELAY SERVER**](modules/busdelay/README.md) | [sambanks](https://github.com/sambanks) | Multi-mode delay: CLEAN / pitched GRAIN cloud / REVERSE, tape wow. | on hardware: Sam's MKII |
| [**REVERB SERVER**](modules/busverb/README.md) | [sambanks](https://github.com/sambanks) | Eight-line FDN reverb: ROOM/PLATE/BIG, shimmer, gate, mid/side width. | on hardware: Sam's MKII |
| [**MODE DEFAULTS**](modules/mode-defaults/README.md) | [sambanks](https://github.com/sambanks) | A MODE turned on the panel re-defaults the knobs around it (the manifests' ModeViews), on FX1 and FX2. | on hardware: Sam's MKII (images 26/27, 15 Sep 2026) |
| [**RIG HOSTS**](modules/rig-hosts/README.md) | [sambanks](https://github.com/sambanks) | A new part is born hosted: T1 FX2 = BusDelay, T5 = BusVerb, T8 = the stock DELAY, the rest SEND. | port-gated: a new project born hosted under the port |
| [**SEND**](modules/send/README.md) | [sambanks](https://github.com/sambanks) | Bus client: DEL into the delay, REV into the reverb, from any track. The default effect. | on hardware: Sam's MKII |
| [**TEMPO BUS**](modules/tempo-bus/README.md) | [sambanks](https://github.com/sambanks) | The TEMPO window lists and edits BusDelay's and BusVerb's knobs (UP/DOWN = row, A or B = value, LEFT/RIGHT = engine, FUNC + LEVEL = 0.1 BPM). | port-gated: `verify_set`; nothing on hardware |
| [**TEMPO SYNC**](modules/tempo-sync/README.md) | [sambanks](https://github.com/sambanks) | ColdFire caves: publishes the held MIDI note to BusDelay, and draws BusDelay TIME as a tempo division. | on hardware: Sam's MKII |

### Effects: on a track

| module | author | what it does | proof |
|---|---|---|---|
| [**CHARACTER**](modules/character/README.md) | [sambanks](https://github.com/sambanks) | BamSep26 station: fold, saturation, tilt, compressor, width. | on hardware: Sam's MKII |
| [**EUCLID**](modules/euclid/README.md) | [repeat98](https://github.com/repeat98) | Euclidean LP/BP/HP/amp sequencer: swing, envelope, gate, random and loop. | local render: its own render gates; not on hardware |
| [**MINIVERB**](modules/miniverb/README.md) | [repeat98](https://github.com/repeat98) | Modulated diffused FDN reverb; independent FX2 buffers, smoothed controls. | local render: `make verify-miniverb`; not flashed |
| [**MODULATION**](modules/modulation/README.md) | [sambanks](https://github.com/sambanks) | BamSep26 station: a modulation pedal -- Juno, Dimension, flanger, phaser, comb; FX1 only. | on hardware: Sam's MKII |
| [**SPECTRUM**](modules/spectrum/README.md) | [sambanks](https://github.com/sambanks) | BamSep26 station: a filter pedal -- the Moog ladder, SEM (LP -> BP -> HP by SHPE), Airwindows Capacitor2, formants; ENV and LFO onto the cutoff; width. | on hardware: Sam's MKII |
| [**TAPE ECHO**](modules/tapeecho/README.md) | [repeat98](https://github.com/repeat98) | Economy CPU tape echo: two biquads, simple FREE slew, snapped BEAT TIME and page-1 AGE. | on hardware: the author's unit (OCTACLID4): six instances run, a seventh freezes it, open |

### Machines and the sequencer

| module | author | what it does | proof |
|---|---|---|---|
| [**ANALOG BD**](modules/analog-bassdrum/README.md) | [repeat98](https://github.com/repeat98) | Analog BD track machine: switchable 808/909 circuit-informed synthesis. | port-gated: source/AMP/main on both cores and chooser/MODEL gates; hardware matching pending |
| [**DIRECT JUMP**](modules/direct-jump/README.md) | [timhastie/octatrick-modules](https://github.com/timhastie/octatrick-modules) | CHAIN AFTER: DIRECT (its unused value 1) -- a pattern change lands at the next step, the step count continuing (A4/Rytm direct jump). | on hardware: `octatrick-usb` on his MKI, 26 Sep 2026 (OCTATRICK9) |
| [**MACHINEDRUM**](modules/machinedrum/README.md) | [repeat98](https://github.com/repeat98) | Machinedrum on T1-T4 (FLEX plus signature): a 16-part kit and an embedded 16-lane sequencer on the parent track's grid. | port-gated: the MD gates under the ColdFire port (`make verify-md*`, `verify_md_persist`); not flashed |
| [**SCALE QUANTIZER**](modules/quantizer/README.md) | [timhastie/octatrick-modules](https://github.com/timhastie/octatrick-modules) | PROJECT > CONTROL > SEQUENCER > SCALE: the PTCH knob and CHROMATIC trig keys quantize to a scale (24 scales, OFF = stock); > GLIDE: the synth's glide time (OFF, 1..127) and 303-style legato on the chromatic keys; polyphonic chromatic keys on a synth track whose VOIC is 2..4. | on hardware: `octatrick-usb` on his MKI, 26 Sep 2026 (OCTATRICK9) |
| [**REPITCH**](modules/repitch/README.md) | [repeat98](https://github.com/repeat98) | Adds TSTR REPITCH (STATIC/FLEX and the sample's own TIMESTRETCH): project-tempo following by playback speed, without grains; PTCH off. | on hardware: an MKII, 16 Sep 2026 (OCTABAM81); `verify_repitch` |
| [**RLEN PLEN**](modules/rlen-plen/README.md) | [sambanks](https://github.com/sambanks) | ColdFire cave: RLEN value PLEN (past MAX) = one loop of the track's pattern on its own scale, so TRIG ONE + QREC PLEN records the next pass and stops. | port-gated: 26 Sep 2026 |
| [**SYNTH MACHINE**](modules/synth/README.md) | [timhastie/octatrick-modules](https://github.com/timhastie/octatrick-modules) | A FLEX track whose sample is named SYNTH* plays a two-operator FM voice (STRT/LEN/RTRG/RTIM = ratio/index/feedback/decay); the DSP shapes and effects it as a sample. Its PLAYBACK page reads RATO/INDX/FDBK/DEC with icons and the title FM SYNTH. | on hardware: `octatrick-usb` on his MKI, 26 Sep 2026 (OCTATRICK9) |

### Parts, Kits and scenes

| module | author | what it does | proof |
|---|---|---|---|
| [**KITS RELOAD**](modules/kits-reload/README.md) | [sambanks](https://github.com/sambanks) | The bridge that lets MIDI SCENES' Part Reload run beside Octakit's kit reload (her caller check, his post-reload restore). | on hardware: `ok-ms`, 14 Sep 2026 |
| [**MIDI SCENES**](modules/midi-scenes/README.md) | [bkkbrls-del/midisc](https://github.com/bkkbrls-del/midisc) | MIDI-driven scene locks (hold/morph/save/reload/clear/copy/paste), built from bkkbrls-del/midisc as linker-placed units. | on hardware: `ok-ms` on his unit, 14 Sep 2026 |
| [**OCTAKIT**](modules/octakit/README.md) | [emuyia/ems-octakit](https://github.com/emuyia/ems-octakit) | Em's Octakit: 256 Kits per Project instead of 64 Parts, built from her repo (submodule) as a loader-appended DRAM runtime. | on hardware: her build reproduced byte for byte; `ok-ms` on midisc's author's unit, 14 Sep 2026 |
| [**SCENES KITS**](modules/scenes-kits/README.md) | [sambanks](https://github.com/sambanks) | The bridge that lets CC MAP and Octakit share the CC dispatch (MIDI SCENES needs no bridging since 1.40MSCN6). | port-gated: in `kits` and `bottleservice` |
| [**SCENES P2**](modules/scenes-p2/README.md) | [sambanks](https://github.com/sambanks) | Scene locks and the crossfader on FX1/FX2 page 2 (hold a scene, turn a page-2 knob). | port-gated: 26 Sep 2026 |
| [**SCENES P2 KITS**](modules/scenes-p2-kits/README.md) | [sambanks](https://github.com/sambanks) | The bridge that lets SCENES P2 and Octakit share the page-2 editor entries. | port-gated: 26 Sep 2026 |

### MIDI and USB

| module | author | what it does | proof |
|---|---|---|---|
| [**CC FEEDBACK**](modules/cc-feedback/README.md) | [sambanks](https://github.com/sambanks) | Every knob value change is transmitted as its CC (page 1: 16-45; page 2: CC MAP's 62-73), so a controller's encoders follow the unit. | port-gated: `verify_ccfeedback` (Unicorn) and `verify_set` (the port's MIDI OUT bytes) |
| [**CC MAP**](modules/cc-map/README.md) | [sambanks](https://github.com/sambanks) | MIDI CC 62-67 drive the FX2 engine's page-2 slots 6-11; CC 68-73 the FX1 station's. | on hardware: Sam's MKII (tag 13) |
| [**USB AUDIO EXTENDED**](modules/usb-audio-extended/README.md) | [markandrus/octemu](https://github.com/markandrus/octemu) | Twenty 24-bit channels over USB (UAC2): the tracks post-FX pre-fader, MAIN, CUE; the stereo sum at full speed (markandrus/octemu). | on hardware: Sam's MKII (image 64, 25 Sep 2026); Tim's MKI (OCTATRICK9, 26 Sep 2026) |
| [**USB AUDIO FULL**](modules/usb-audio-full/README.md) | [markandrus/octemu](https://github.com/markandrus/octemu) | Sixteen 24-bit channels over USB (UAC2): the tracks post-FX pre-fader, no MAIN/CUE; the stereo sum at full speed (markandrus/octemu). | port-gated: `verify_usb` under the port (27 Sep 2026); this build not on hardware (image 69 ran the 16-channel layout from earlier source) |
| [**USB AUDIO MASTER**](modules/usb-audio-master/README.md) | [markandrus/octemu](https://github.com/markandrus/octemu) | Track 8's L/R over USB (UAC2, 2 channels, 24-bit): the master track, post-FX pre-fader; USB AUDIO EXTENDED's source, the T8 variant Sam Banks's. | port-gated: `verify_usb` under the port (27 Sep 2026); not on hardware |
| [**USB MIDI**](modules/usb-midi/README.md) | [markandrus/octemu](https://github.com/markandrus/octemu) | Class-compliant USB-MIDI in and out on the OT's own USB port, mirroring the DIN ports (markandrus/octemu). | port-gated: enumerates, receives and transmits under the port (`verify_usb`); not on hardware |

### Fixes

| module | author | what it does | proof |
|---|---|---|---|
| [**FLEX SEEK BIND**](modules/flex-seekbind/) | [sambanks](https://github.com/sambanks) | ColdFire cave: a same-slot/type/generation FLEX re-bind takes the bind's same-sample path (DSP seek) instead of becoming a new note. | on hardware: OCTABAM83, 12 Sep 2026 |
| [**FLEX SEEK BIND CTR**](modules/flex-seekbind-ctr/) | [sambanks](https://github.com/sambanks) | ColdFire cave: on a same-sample FLEX re-bind, do not bump the voice's per-bind counter (pairs with FLEX SEEK BIND). | on hardware: OCTABAM83, 12 Sep 2026 |
| [**LOFI AMF FIX**](modules/lofi-amf-fix/README.md) | [bryantysinger/octa-bt-pt](https://github.com/bryantysinger/octa-bt-pt) | Fixes stock LO-FI's AMF knob: mpysu -> mpyuu, both payloads. Ported from bryantysinger/octa-bt-pt. | `make check`: both words disassembled against stock |
| [**RECORDER HOLD**](modules/recorder-hold/README.md) | [sambanks](https://github.com/sambanks) | ColdFire cave: a recorder-buffer FLEX voice reading one sample past its recording repeats the last sample instead of reading zero. | port-gated: 26 Sep 2026 |
| [**RECORDER SPACING**](modules/recorder-spacing/README.md) | [sambanks](https://github.com/sambanks) | ColdFire cave: a fixed-RLEN recording is exactly as long as the gap to the next arm, derived from the current arm -- no lane, no stored state. | on hardware: OCTABAM83, 12 Sep 2026 |

### Reference

| module | author | what it does | proof |
|---|---|---|---|
| [**CF METER**](modules/cfmeter/README.md) | [sambanks](https://github.com/sambanks) | Probe: frame-interrupt duration and (with CF METER IDLE) idle time, printed as audio on T8's FX2. | port-gated: the readout chain and the interrupt timing under the port; the numbers need the unit |
| [**CF METER IDLE**](modules/cfmeter-idle/README.md) | [sambanks](https://github.com/sambanks) | Probe: main's idle loop timed, for CF METER's idle-time slot. | `make check`: boots under the port; does not load a project there (the port's clock) |

<!-- modules:end -->

## Quick start

```bash
git clone --recurse-submodules https://github.com/sambanks/octabam
cd octabam
make setup                          # toolchain (macOS + Homebrew; docs/WSL.md for Linux)
make os && make recon               # your own 1.40C -> out/raw/section_3_MAIN_OS.bin
make image REMIX=ok-ms BUILD=1      # -> out/OCTATRACK_OCTABAM1.bin
```

`make check REMIX=<name>` runs every gate and boots the image under the
local ColdFire emulator. `make remix` opens the TUI remixer
(`docs/remixer/REMIXER.md`).

## How it works

```
modules/<name>/manifest.py   what a module is and what it claims (yours, or a pointer into an author's repo)
remixes/<name>/remix.py      which modules, in which chooser order; README.md beside it
remixes/test/<name>/         a remix of one module, for that module's gates
tools/remix/ledger.py        refuses two modules that claim one address, hook, id or buffer, by name
tools/build/build_bus.py     the build: assembles, links, places, wires, verifies -> out/mainos_bus.bin
tools/verify/*               the gates: oracles, the boot under the ColdFire port, menu, cycles, identity
```

A module's code lands in one of three places; the build decides which bytes
go where, and a module declares what it is, not an address:

| class | declared as | where |
|---|---|---|
| ROM cave | `CavePatch`: a `.s` source, or ratified hex | one of the OS image's free zero runs, ~8 KB total shared by everyone |
| DRAM unit | `Linked(..., dram=True)`: a GNU-as unit | linked with every other DRAM unit in the remix into one runtime, packed, appended behind octabam's loader, depacked at boot into a 10 MB reserve carved off stock's 85.5 MB sample/recorder pool |
| appended runtime | `Runtime`: a recipe (Octakit's `firmware.json`) | its own reserve of the same pool, as a second payload of the same loader |

The OS-image edits every class needs — a detour at a stock instruction, a
poke, a grown table — are `Detour`, `Poke`, `TableGrow`, wired by symbol and
asserted against stock before a byte is written. `docs/remixer/PLACEMENT.md`
is the map of what is free and what was measured.

**A port is a proof.** The build re-links every unit at the author's own
address and compares, rebuilds Octakit's runtime to the identities her
recipe pins, and refuses on any drift. `CONTRIBUTING.md` is the contract;
`docs/remixer/MODULES.md` the guide to writing a module.

**Where a module's state lives.** An effect's twelve knobs are Part
parameters and stay in the Part. Personal material (Octakit's Kits,
octalab's grooves) is in files the module owns and formats. A module's
settings (how it behaves or looks: menu options, a USB profile) have no
shared home yet: Octakit and octalab each write their own files, and the
other modules keep none. The shared settings store for all modules, OTX
(`otx.work` / `otx.strd` in the project folder, one record per module,
unknown records preserved byte for byte by any firmware that saves), is
specified in
[`docs/proposals/OTX_PROJECT_PROPOSAL.md`](docs/proposals/OTX_PROJECT_PROPOSAL.md)
(nordseele, draft 2, 26 Sep 2026) with author-facing
[guidelines](docs/proposals/OTX_MODULE_GUIDELINES.md);
not implemented. `docs/remixer/MODULES.md` "Settings on the card" says
what a module declares under it.

## Checking without a flash

The DSP side renders locally on the assembled instruction stream (`make
render`, `make render-rig`; `docs/remixer/HARNESS.md`). The whole machine
— ColdFire, both DSP cores, the card, the panel, MIDI, USB — runs under a
port of it (`tools/emu/ot_emu`, `make emu-cf`):

```bash
make check REMIX=<name>             # boots the image under the port; OT_PROJECT=<dir> adds a real project
make reach                          # the gates this branch's diff reaches, in order; RUN=1 runs them
make panel REMIX=<name>             # the virtual front panel with sound at localhost:8563 (tools/panel/README.md)
make emu-live REMIX=<name>          # the screen and keys in a window, no sound
```

`docs/remixer/EMU.md` covers all of them and the Unicorn routes the
label gates use. CI (`.github/workflows/ci.yml`, `make ci`) runs the checks that
need no firmware; `CONTRIBUTING.md` says what those cover and what they
cannot. What the emulators cannot see — caches, the recorder,
cross-core timing — is listed beside every gate that is blind to it.

## Before you flash anything

**Writing a non-official OS to an Octatrack can leave it unusable and puts
your warranty in question.** Nothing here is endorsed by, supported by, or
affiliated with Elektron. `docs/remixer/FLASHING.md` has the recovery path;
`docs/remixer/FAILURE_MODES.md` is the register of what has gone wrong on a
unit and why. Back up projects before flashing anything that changes them
(Octakit migrates Parts to Kits on load; downgrading may lose Kit data).

MKI and MKII run the same 1.40C image (hash-verified). sambanks's effects
have only been tested on an MKII; the DRAM platform has run on an MKI
([octalab](https://github.com/nordseele/octalab-notes), 11 Sep 2026;
`octatrick-usb` on Tim Hastie's, 26 Sep 2026) and on midisc's author's
unit (`ok-ms`, 14 Sep 2026).

**No Elektron binary is redistributed here, and none may be.** A built
`.bin` or `.syx` contains Elektron's OS: do not share built images. Share
the repo; everyone builds their own.

*Octatrack* and *Elektron* are trademarks of Elektron Music Machines MAV
AB, used here only to identify the hardware this project targets.

## Repository layout

```
CONTRIBUTING.md    your first PR, the module contract, the oracle rule, the gates, what CI checks
AGENTS.md          instructions and traps for coding agents (CLAUDE.md imports it)
.github/           CI (Ubuntu + macOS, SHA-pinned actions), the PR template
modules/           the contributions, one directory each
remixes/           one directory per remix: remix.py (the selection, in chooser order) and README.md
remixes/test/      the one-module remixes, for their modules' gates (make check REMIX=<name>)
docs/remixes/      the build guide and the rendered remix index
tools/remix/       the toolkit: schema, registry, ledger, the loader, the DRAM platform, the TUI
tools/build/       the image build (build_bus.py) and the tools that understand the OS layout
tools/verify/      the gates
tools/harness/     hear and measure the DSP side locally (dsp_host, send_probe, rig_render)
tools/emu/         the ColdFire emulators: the headless port (ot_emu) and the Unicorn bring-up
tools/panel/       the virtual front panel over the port, with sound (tools/panel/README.md)
tools/hw/          the unit and its card: MIDI control, capture, project files, MIDI flashing
tools/patches/     local patches to the vendored toolchains
scripts/           toolchain setup, vendored pins (vendor.sh), OS fetch and recon, the bit-identity gate
dsp/               shared DSP infrastructure: the null stub and the probes
docs/remixer/      using and extending the remixer: MODULES, PLACEMENT, REMIXER, TOOLING, EMU, HARNESS, ACCEPTANCE, FLASHING, FAILURE_MODES
docs/firmware/     the firmware, reverse-engineered: ARCHITECTURE, KERNEL, DSP, CHIP, TABLES, PARAM_PAGES, MAINMENU, PANEL, MIDI, LFO, LEVEL_LAW, COLDFIRE_DELAY, COLDFIRE_PORT, RECORDER, RECORDER_CLICK, REPITCH, SAMPLE_SAVE, STORAGE; CONTRIBUTIONS is the dated index of what each contributor sent
docs/effects/      the effects: XBUS (the bus), REVERB, MASTER, PORTS
docs/proposals/    technical propositions: OTX_PROJECT_PROPOSAL + OTX_MODULE_GUIDELINES (the settings store), MULTITRACK_TO_CARD
```

## Credit

**Em** ([emuyia](https://github.com/emuyia)) designed Octakit and the
loader-appended DRAM runtime octabam adopted as its large-payload placement;
`tools/remix/loader.S` is derived from hers with attribution. Her repository
invites use as a submodule to combine with other efforts.

This began as a fork of [mxldyn/octamax](https://github.com/mxldyn/octamax)
by Maxolydian, whose reverse engineering of the OS format, memory map and
parameter tables made any of this reachable; the upstream history is in
this repository's log.

`vendor/` pulls in [dsp56300](https://github.com/dsp56300/dsp56300),
[mc68k](https://github.com/joelanders/mc68k-md-mm) and
[elektron-firmware-tool](https://github.com/mischa85/elektron-firmware-tool).

## License

[MIT](LICENSE) for this repository's own code and documentation. It does
not extend to Elektron's firmware, which is not distributed here, nor to
the repositories referenced as submodules, which remain their authors'
under their own terms.
[THIRD_PARTY.md](THIRD_PARTY.md) lists every transcribed DSP source
(Airwindows, JClones, Mutable Instruments, ChowDSP, jpcima, audiojs), the
submodules and the vendored tools, each with its licence.
