# Building a remix, step by step

Every image is built on your own computer from your own copy of Octatrack
OS 1.40C. Nothing built here may be shared: a built `.bin` or `.syx`
contains Elektron's OS.

Pick a remix from [README.md](README.md). The commands below use `ok-ms`
(Octakit + MIDI SCENES, the interim-share image); substitute any remix
name.

## 0. What you need

- A Mac with [Homebrew](https://brew.sh), or Linux / WSL2 ([docs/WSL.md](../WSL.md)).
- `git`, `python3` (3.10+; stdlib only, no packages), `cmake` (`brew install cmake`).
- An Octatrack MKI or MKII on OS 1.40C. The stock 1.40C image is one file
  for both marks; octabam's own effects have only been tested on an MKII,
  and the DRAM platform has run on both (MKI: octalab, 11 Sep 2026; MKII:
  OKMS1, 14 Sep 2026).
- A CompactFlash card in the unit (the fast flashing path).
- For recovery only: a 5-pin DIN MIDI interface and an app that sends
  `.syx` files (SysEx Librarian on macOS). USB-MIDI to the OT's own USB
  port does not work for OS upgrades.

## 1. Get the repository and the toolchain

```bash
git clone --recurse-submodules https://github.com/sambanks/octabam
cd octabam
make setup
```

`--recurse-submodules` fetches the module authors' repositories
(`modules/octakit/upstream`, `modules/midi-scenes/upstream`, and
`timhastie/octatrick-modules` under `modules/synth`, `modules/quantizer`
and `modules/direct-jump`) at the pinned commits. If you cloned without
it: `git submodule update --init`.

`make setup` installs `binwalk`, `radare2` and `m68k-elf-gcc` with
Homebrew, checks out three pinned vendored tools (`vendor/`), applies the
local patches and builds them. Re-running it is safe. It ends with
`setup complete`.

## 2. Get the stock OS

```bash
make os
make recon
```

`make os` downloads `OCTATRACK_OS1.40C_dist.zip` from Elektron's site into
`downloads/` and prints its SHA256 (expected
`370c55a3dad3996b8e4b46400a205066fdaf185ad4d0255a3a3f835060573ff0`).
`make recon` unpacks it to `out/raw/section_3_MAIN_OS.bin`, the file every
build reads. Both directories are gitignored.

## 3. Build the image

```bash
make image REMIX=ok-ms BUILD=1
```

Output:

```
out/OCTATRACK_OCTABAM1.bin            the card image
out/OCTATRACK_OS1.40C_OCTABAM1.syx    the MIDI image
```

`BUILD` is a one- or two-digit number of your choosing. It becomes the
unit's OS version string (`OCTABAM1`) and the suffix on any octabam
effect's name, so a unit can always be traced to the build it runs. Bump
it every time you flash. `VERSION=<up to 10 chars>` overrides the version
string (`OKMS1` was built that way).

The build prints what it did: every module placed, every hook wired,
every identity checked against the author's own build, and the byte
count changed. It refuses, with the reason, rather than write an image it
cannot prove.

### Optional: run the gates

```bash
make emu-cf                 # builds the local ColdFire emulator (cmake) and boots stock in it once
make check REMIX=ok-ms      # build + every gate + boot under the emulator
```

`make check` is two halves: `make check-shared` (the ledger selftest,
which builds every remix in turn, the docs, the knob census and the module
gates that build their own image) and `make check-remix` (the selected
remix's build, cycles and its own gates). Measured on one machine, 27 Sep
2026, over all 25 remixes of the day: 475 s for the shared half, 223 s per
remix on average (`lofi-amf-fix` 51 s, `bottleservice` 1,143 s). Without
`make emu-setup` (the `.venv`) the label gates (`verify_labels`,
`verify_modenames`, `verify_hidden`) report `[SKIP]`; without `make
emu-cf` the set gates do. Run from a fresh clone on 16 Sep 2026:
`scripts/setup.sh` → `make os` → `make recon` → `make check
REMIX=bamsep26` (that day's rig remix; `bottleservice` is its successor)
green with exactly those SKIP lines (Homebrew tools already installed on
that machine; the `brew install` branch was not exercised).

## 4. Back up

Flashing the OS does not touch the CF card. Back it up anyway (USB DISK
MODE, copy everything). Any remix carrying **Octakit** migrates Parts into
Kits on project load; going back to stock can lose Kit data (Em's
warning).

## 5. Flash from the card

1. On the unit: **PROJECT → SYSTEM → USB DISK MODE → YES**. The card mounts
   on the computer.
2. Copy `out/OCTATRACK_OCTABAM1.bin` to the **root** of the card.
3. Eject the card on the computer, then leave USB DISK MODE on the unit.
4. **PROJECT → SYSTEM → OS UPGRADE → YES** and confirm.
5. Wait for the unit to finish and restart. **Power-cycle it once more
   before judging anything**: an OS upgrade does not clear DSP RAM, and
   twice the first boot has played garbled audio that a reboot cleared.

The boot screen and **SYSTEM STATUS → OS VERSION** now read `OCTABAM1`. If
it still says `1.40C`, the stock OS is running.

## 6. If it goes wrong

The Startup Menu lives in flash the OS upgrade never touches, so the unit
can always be returned to stock:

1. Power off. Hold **FUNC** and power on → **STARTUP MENU**.
2. **TRIG 3 → MIDI UPGRADE** → "READY TO RECEIVE MIDI UPGRADE".
3. Send `downloads/extracted/OCTATRACK_OS1.40C.syx` (the stock OS, from
   `make os`) from your SysEx app over DIN MIDI.
4. Wait through PREPARING FLASH → UPDATING FLASH. Do not power off.

`TRIG 2 → EMPTY RESET` clears battery-backed RAM and settings, not the
card. [docs/remixer/FAILURE_MODES.md](../remixer/FAILURE_MODES.md) is the
register of what has gone wrong on a unit and why.

## 7. Going back to a different remix

Build and flash another image the same way; `restock` is the stock
chooser with nothing added. After any remix that changes an effect's
parameter layout (the rig family), stamp every project before playing:
`python3 tools/hw/ot_project.py stamp-defaults <project dir on the card> <remix>`.

## 8. Your own remix

A remix is one directory, `remixes/<name>/`: `remix.py` holds the
selection, `README.md` says what is in it and where it has run. The
registry discovers every `remixes/*/remix.py` and `remixes/test/*/remix.py`;
nothing else registers it. A remix that carries one module for that
module's gates goes in `remixes/test/<name>/`; names are unique across
both, and every tool takes the bare name (`make check REMIX=miniverb`).

Two ways to write one:

- **`make remix`**, the TUI (`docs/remixer/REMIXER.md`; needs `make
  emu-setup`): `l` loads an existing remix or `stock`, `enter` adds and
  removes modules, `1` gives an effect an FX1 row, `s` writes
  `remixes/<name>/remix.py` and a README stub. The written file carries
  `name`, `doc`, `modules`, `fallback` and, when it differs from stock's,
  `fx1`.
- **Copy an existing `remix.py`** and edit it. `remixes/bus/remix.py` is
  a bus image, `remixes/test/euclid/remix.py` an insert beside the stock
  effects, `remixes/ok-ms/remix.py` two ColdFire mods and no DSP code.

```python
from remix.schema import Proof, Remix

REMIX = Remix(
    name="mine",                       # == the directory name
    doc="One line: what is in it.",
    family="effects",                  # index section: rig, effects, mods, reference, probes
    proof=Proof.CHECK,                 # CHECK, RENDER, PORT, HARDWARE
    proof_note="make check, 28 Sep 2026",
    modules=("REVERB SERVER", "DELAY SERVER", "SEND", "TEMPO SYNC",
             "FILTER", "LO-FI"),       # the FX2 chooser, in row order
    fallback="SEND",                   # or "NONE"
    # fx1=("FILTER", "EQUALIZER", "SPECTRUM"),   # the FX1 chooser; omitted = stock's ten
)
```

- `modules` is the FX2 chooser in row order. A key is a module's `key`
  (`make modules` prints them) or a stock effect's name: FILTER,
  EQUALIZER, DJ EQ, PHASER, FLANGER, CHORUS, SPATIALIZER, COMB FILTER,
  COMPRESSOR, LO-FI, DELAY, PLATE REV, SPRING REV, DARK REV. A module with
  no chooser row (a ColdFire mod, a bridge, TEMPO SYNC) sits anywhere in
  the list. A stock effect on neither chooser keeps its code and
  descriptor (an old project still runs it) and its words become room for
  modules; the three reverbs are the default room, 2,724 words. The build
  refuses a listed stock effect whose words a placed module reached, and
  an overrun by payload: `payload B: SPECTRUM overruns the region (3599 >
  2724 words)`.
- `fallback` is where an FX2 id the image does not implement dispatches,
  id 0 of a fresh part included: `"SEND"` for a remix with a bus server
  (the track becomes a send), `"NONE"` for one without (the firmware's
  own NONE). `NONE` beside a bus server is refused.
- `fx1` is the FX1 chooser in row order; omitted, FX1 stays stock's ten.
  Only a buffer-free insert may take a row; the build refuses the rest by
  name. A row costs no words and does cost cycles: four more slots per
  core.
- `family`, `proof`, `proof_note` are the columns of the remix index.
  Without them the remix lists under Reference with proof `?`.
- Seven FX2 rows fit in place; up to 32 go to a longer list, whose
  scrolling on the panel is inferred from stock's fifteen-row list, not
  measured.
- Two selected modules that claim one address, id, hook or buffer are
  refused by name; `make modules` prints the pairwise matrix.
- `hidden`, `named`, `grains`: `docs/remixer/MODULES.md`.

Then:

```bash
make docs                       # re-render docs/remixes/README.md (make check refuses a stale index)
make check REMIX=mine           # build + cycles + every gate + boot under the port
make image REMIX=mine BUILD=2   # -> out/OCTATRACK_OCTABAM2.bin
```

`make check` also refuses a remix directory without a `README.md`. A remix
whose parameter layout differs from the one a project was saved under
needs the stamp before play (§7).
