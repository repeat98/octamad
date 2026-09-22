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
(`modules/octakit/upstream`, `modules/midi-scenes/upstream`) at the pinned
commits. If you cloned without it: `git submodule update --init`.

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

`make check` builds every remix in turn, so it takes several minutes.
Without `make emu-setup` (the `.venv`) the four firmware-label gates report
`[SKIP]`; without `make emu-cf` the set gates do. Run from a fresh clone on
16 Sep 2026: `scripts/setup.sh` → `make os` → `make recon` →
`make check REMIX=bamsep26` green with exactly those SKIP lines (Homebrew
tools already installed on that machine; the `brew install` branch was not
exercised).

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
