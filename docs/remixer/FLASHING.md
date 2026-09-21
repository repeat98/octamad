# Flashing

How to get an octabam image onto an Octatrack, and how to get back off it.
[`docs/remixes/BUILDING.md`](../remixes/BUILDING.md) is the shorter
walk-through for a first build.

> **This is not official Elektron firmware.** Flashing a modified OS can
> leave the unit unusable until you recover it, and puts your warranty in
> question. Nothing here is endorsed by, supported by, or affiliated with
> Elektron. You flash at your own risk.
>
> **Do not redistribute images you build.** A built `.bin`/`.syx` contains
> Elektron's copyrighted OS. Everyone builds against their own copy
> (`make os`).

**Learn how to recover before flashing.** A brick here is soft and
recoverable: the Startup Menu (bootloader) lives in a region the OS update
does not touch, so the unit can always be returned to the official OS over
MIDI. Read §1 first.

## 0. What you need

- An Octatrack on OS 1.40C. Elektron's MKI and MKII download pages serve
  the byte-identical file (SHA256 `370c55a3…`, compared 19 Aug 2026).
  octabam's own effects have only been tested on an MKII; the DRAM platform
  has run on an MKI (octalab, 11 Sep 2026) and on midisc's author's unit
  (`ok-ms`, 14 Sep 2026). The updater's error −5 "MK1 not allowed" compares
  the incoming file's version code against "0156", i.e. it rejects
  pre-unification MK1-era OS files (inferred); octabam images keep 1.40C's
  internal code 0178.
- **The built image**: `make image REMIX=<name> BUILD=<nn>` produces
  `out/OCTATRACK_OCTABAM<nn>.bin` (card path) and
  `out/OCTATRACK_OS1.40C_OCTABAM<nn>.syx` (MIDI path). `<nn>` is one or two
  digits; bump it every flash so the unit's version string maps to a
  commit.
- **The official rescue firmware**: `downloads/extracted/OCTATRACK_OS1.40C.syx`,
  present after `make os`.
- For the MIDI path and for recovery: a 5-pin DIN MIDI interface into the
  Octatrack's MIDI IN and an app that sends `.syx` files (SysEx Librarian
  on macOS), or `make midi-flash`. The MIDI upgrade does not work over
  USB-MIDI to the OT's own USB port.
- Stable power; do not move the unit during flashing.

The register of hardware failure modes (symptom → cause → fix) is
[`FAILURE_MODES.md`](FAILURE_MODES.md).

## 1. The recovery path

If the unit shows a "Z" screen, will not boot, or hangs:

1. Power off.
2. Hold **[FUNC]** and power on → the **STARTUP MENU**.
3. **[TRIG 3]** → **MIDI UPGRADE** → "READY TO RECEIVE MIDI UPGRADE…".
4. Send the official OS (`downloads/extracted/OCTATRACK_OS1.40C.syx`) from
   your SysEx app, or `make midi-flash PORT=<port> SYX=downloads/extracted/OCTATRACK_OS1.40C.syx`.
5. Wait through "PREPARING FLASH" → "UPDATING FLASH". Do not power off.

This menu works even if the OS is corrupt: it is the bootloader, and a
normal OS update never touches it. [TRIG 2] = EMPTY RESET clears the
battery-backed RAM and settings, not the CF card.

## 2. Backup

Flashing the OS does not touch the CF card. Back it up anyway (USB DISK
MODE, copy everything), or at least the projects that matter. Any remix
carrying Octakit migrates Parts into Kits on project load; going back to
stock can lose Kit data.

## 3a. Flash from the CF card (recommended)

Manual §8.5.2: seconds rather than minutes.

1. Connect the OT over USB, select **USB DISK MODE**, press **[YES]**. The
   card appears as a drive.
2. Copy `out/OCTATRACK_OCTABAM<nn>.bin` to the **root** of the card, not
   inside any folder.
3. Eject the card on the computer, then leave USB DISK MODE on the OT.
   Skipping the eject can leave the write in cache and the OT reads a
   truncated file.
4. **PROJECT → OS UPGRADE → [YES]**, confirm the prompt. The active project
   is synced to the card first.
5. **Power-cycle the unit before judging anything.** Garbled audio straight
   after an upgrade has happened twice, cleared by a reboot both times. The
   mechanism (inferred from the code, not measured): an OS upgrade rewrites
   program memory but does not clear DSP state RAM, and an engine whose
   tagged warm-up counter survives with a valid tag (BusVerb `$2c0000` at
   `r7+$82`, BusDelay `$2e0000`, Nimbus `$2d0000` at `r7+$31`) skips its
   warm-up and runs on whatever is in its buffers. A power cycle clears the
   tag.

This path needs a unit that boots; otherwise §3b.

`tools/build/make_bin.py` builds the `.bin`; `tools/build/bin_decode.py`
decodes the official file and validates its checksum, and round-trips ours.

## 3b. Flash over MIDI

1. Your interface's MIDI OUT → the Octatrack's **MIDI IN** (DIN, not USB).
2. In your SysEx app, choose the output port connected to the OT and load
   `out/OCTATRACK_OS1.40C_OCTABAM<nn>.syx`.
3. On the Octatrack: power off, hold **[FUNC]**, power on → **STARTUP MENU**.
4. **[TRIG 3]** (MIDI UPGRADE) → "READY TO RECEIVE MIDI UPGRADE…".
5. Send the file; the [TRIG] lights come on one by one. From this repo:
   `make midi-flash PORT=A SYX=<file.syx>` (`tools/hw/midi_flash.py`) paces
   the ~7,460 messages at the DIN rate through a named MIDI destination.
   FILTER MIDI CLOCK on that port. Retry-safe: on a lost send, re-enter the
   Startup Menu and run it again (`--ms 60` to slow it). If a SysEx app goes
   too fast and the OT loses sync, increase the pause between messages
   (100–300 ms).
6. "PREPARING FLASH", then "UPDATING FLASH". Do not power off or disconnect
   during "…FLASH".
7. The OT may update its bootstrap after flashing. Wait for it to finish
   booting, then power-cycle (§3a step 5).

## 4. After the flash

1. **Version string.** The boot screen and **SYSTEM STATUS → OS VERSION**
   read `OCTABAM<nn>`. If it still says `1.40C`, the official OS is running.
2. **Stamp projects** after any remix that changes an effect's parameter
   layout (the rig family): `python3 tools/hw/ot_project.py stamp-defaults
   <project dir on the card> <remix>` before pressing play. A part saved
   under an older layout feeds the new one its old bytes; a select whose
   stored value is outside its count is used as an index and the sequencer
   stalls on the first play. Re-selecting the effect on one track is not
   enough: the sequencer runs every track of the part.
3. **The bus (rig remixes):** BusVerb runs on tracks 5–8 (payload A),
   BusDelay on tracks 1–4 (payload B); a host on the wrong bank falls back
   to a SEND (`ot_project.py stamp-defaults` warns per part). Test the
   reverb on track 5. SEND's SEND knob is the one send; each engine's wet
   comes out on the track that hosts it.
4. **A new module:** check the two things no local test can see — that each
   page-2 select draws as a select (a formatter outranks the value count
   beside it), and that every knob reaches the DSP (a slot can draw a knob
   and publish nothing; `dsp_host` pokes `r6` directly).

## 5. Reverting to the official firmware

Reflash following §3 with `downloads/extracted/OCTATRACK_OS1.40C.syx`
(MIDI) or the official `.bin` from Elektron's zip (card). The card and
projects are not affected.

## Risk

- Everything checkable without hardware is checked (`make check`, the
  verify gates, the local renders), but the emulator's two cores run
  lock-step or under a guessed interleave, so no local test can show a
  cross-core bus timing defect absent. Emulator green is necessary, not
  sufficient.
- The only delicate moment is "UPDATING FLASH": do not cut power there.
- A hard (unrecoverable) brick: the rescue bootloader is not touched in a
  normal OS update.
