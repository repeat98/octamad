# WP-E1 Persistence: report

- **Status:** review (octemu and the port; not on hardware)
- **Branch and commit:** `machinedrum` @ this commit
- **Date:** 25 September 2026
- **Agent:** Claude (Opus 5.5)

## What was done

The MD's kits and patterns now persist the way stock persists a bank,
through the same four stock steps (`modules/machinedrum/md_persist.c`,
`md_persist_tail.s`):

- **Kits follow the OT Part.** There are 64 kits (`md_kits`), one per Part
  (bank × 4 + part), in place of the single `md_kit`. The active kit is
  set once a frame from the resident bank (`0x80000002`) and the active
  Part (`0x100b14cf`). A Part's first MD assignment still gets the
  default kit (`md_kit_empty`). The 256 patterns were already one per OT
  pattern.
- **SRAM.** The resident bank's MD slice (4 kits, 16 patterns: 6,912
  bytes) lives in battery-backed SRAM at `0x100fa000`, with a magic word,
  the bank and a hash of the project path. It is copied whole after stock
  copies a bank into SRAM (`0x4000faf0`: bank change, project load) and
  refreshed 128 bytes a frame from the ISR (a full pass every 54 frames).
- **The card.** `machinedrum.work` (32-byte header, 64 kits, 256 patterns,
  FNV-1a sum; 110,628 bytes) is written after every stock bank save
  (`0x400917c8`: SYNC TO CARD, SAVE, a bank change). It is read after
  every stock bank load (`0x400905d4`) for the banks in the load's mask.
  At boot the mask excludes the resident bank, so that bank comes from
  SRAM when the block is this project's, as stock's does. A damaged file
  is copied to `machinedrum.bad` and loads as empty.
- **SAVE / RELOAD.** Stock's file copy (`0x40016388`) of `markers.*`
  (`.work → .strd` and back) copies `machinedrum.*` with it.

Each detour keeps the caller's return address, puts its own continuation
in that slot and runs stock on the caller's untouched frame. Stock's
project load takes four arguments, and a first draft that re-pushed
three stalled every load.

Two defects fixed on the way:
- **Zeroed patterns hold 64 bogus locks** (step 1, part 1, SYN 1 = 0),
  because a free lock is `part = 0xff`. 🟡 From `md_ctl.c` `fire()` (a
  lock applies when its part is under 16, its step is the step and its
  parameter under 10), every image before this one played part 1's trig
  on step 1 with SYN 1 at 0; inferred from the code, not measured as
  audio. Every load now frees the locks of the banks it sets.
- **The editor's page follows the kit index**, not only the Part index, so
  a bank change shows the new kit.

## Acceptance check

The port (`MD_EMU` = the isolated port, `OT_PROJECT` =
`out/machinedrum/testset_nofx/OCTABAM/RIG`):

```
$ python3 tools/verify/verify_md_persist.py
load: machinedrum.work -> kit 0 (TRX-RS, VOL 99, PAN 30), pattern A01 (steps 1/5/9, a lock); SRAM mirrors bank 1
damaged: the sum refuses it; the banks load empty and the MD gets its default kit
verify_md_persist: PASS
```

octemu (isolated build), three runs on one writable card
(`out/mdverify/e1/run.sh`). Breakpoints are over the gdbstub
(`out/mdverify/bp/bplog.py`).
- **A** (fresh NVRAM):
  - assign MD, ENG to TRX-XT, PAN 44, REC steps 3 and 7;
  - PROJECT › SYNC TO CARD shows "NOW SAFE TO EJECT!", `banksave` is hit,
    and `machinedrum.work` appears on the card;
  - then one more ENG detent (TRX-CP), not synced.
- **B** (A's NVRAM): SRC SETUP shows TRX-CP's page 2 (RSIZ, RTUN) and
  PAN 44. The unsynced edit came back, which only the SRAM block can
  provide.

The card A wrote:

```
$ python3 tools/verify/verify_md_persist.py --card out/mdverify/e1/card.img "Set 260922/PROJECT 260922"
card: machinedrum.work 110628 bytes, sum sound; non-empty kits [0]
  kit 0 (bank 1 part 1): 12/v100/p44 11/v100/p64 16/v100/p64 17/v100/p64 13/v100/p64 14/v100/p64 15/v100/p64 18/v100/p64 00/v100/p64 ...
  pattern 0 (bank 1 01): lanes [(0, [3, 7])] locks 0
verify_md_persist --card: PASS
```

- **C** (fresh NVRAM, A's card): T1 came back STATIC. That is stock's
  own behaviour: the clean NVRAM holds a valid SRAM bank, and stock
  restores the resident bank from SRAM, not from the card. The file
  read is proven by the port gate instead.

Every MD gate passes on this image, with `testset_nofx`:
- the new `verify_md_persist.py`;
- `verify_md_ui.py` and `verify_md_c3.py`;
- `verify-md`, `--gain-probe` and `--gain-queue-probe`;
- `verify-md-transport`, `verify-md-seq` and `verify-md-kit`;
- `make check REMIX=machinedrum`.

The kit and sequencer gates now poke `md_kit` / `md_patterns` with
`--poke` (after the load) instead of `--poke-early`, because the load now
sets them.

## Measured

- ✅ The boot order (octemu breakpoints):
  1. the SRAM restore `0x40025770`;
  2. the project load `0x400905d4(ctx, 0xfffe, …)` about 3 s later, with
     every bank but the resident one.
- ✅ A bank change A→B runs `0x4000faf0(1)`, then `0x400917c8(ctx, 1)`.
- ✅ SAVE runs `project.work`, then `markers.work`, then the bank save,
  then `0x40016388(dst, src, 0)` per file.
- ✅ Stock's project load takes four arguments (callers pop 16, 28 or
  20 bytes including earlier pushes; the body reads `sp@(344)`). Its bank
  save takes four as well, the last two optional callbacks.
- ✅ The buffered file object: fd, buffer, size, position, flushes, mode.
  - `read(fobj, dst, len)` returns 1 ok, 0 EOF, negative on error.
  - `write` returns 1 or a negative flush error.
  - Stock files keep their exact length.
- 🟡 SRAM `0x100f859c..0x100ffeff` is free. No instruction operand of the
  OS references it (census of every `0x100xxxxx` operand), and a used
  session's NVRAM is zero there. Inferred, not a stock map; the block
  carries a magic word and project hash so that a stale or foreign block
  is ignored.
- The port cannot write files from `--call` (stock's own bank save runs
  away in its memcpy there), and its panel walk did not reach the PROJECT
  menu. The write is therefore measured in octemu, not in the port.

Section 12 of `MACHINEDRUM_MACHINE.md` has these under "25 September 2026:
persistence".

## Retracted

Nothing. One defect was found rather than a claim: a zeroed `MdLock` is a
live lock (part 1, SYN 1 = 0, step 1); see above (🟡, from the code) and
section 12.

## Open and handover

- **Saved Part copies.** RELOAD PART / RELOAD BANK restore the Part's page
  bytes, and so the selected MD part's SYN/VOL/PAN/ENG through the
  editor's mirror, but not the other fifteen parts of the kit. A saved
  kit per Part would double the kits (another 12 KB and 12 KB of file).
- **SAVE TO NEW.** It writes `markers.work` into the new project through
  another routine (`0x40090448`) and is not hooked, so a project saved
  that way starts without `machinedrum.work` until its first sync.
  Untested.
- **The file is written in place**, as stock writes its `.work` files. A
  power cut during the ~110 KB write leaves a file the sum refuses; it is
  kept as `machinedrum.bad`.
- **Not on hardware.** The SRAM block's address is the one choice here
  that only the unit can fully clear.
