# The card, the project files and the slots

OS 1.40C, ColdFire side, above the ATA stack (`ARCHITECTURE.md` §5): the
filesystem vtable, the sample-slot loader and its status records, where a
Part lives, and what the unit writes to the card. Read by nordseele for
octalab ([`nordseele/octalab-notes`](https://github.com/nordseele/octalab-notes),
MIT, findings only; read here 13 Sep 2026 at commit `40ffa53`) on an
Octatrack MKI, and re-read here where marked.

Status key as `CHIP.md`: ✅ measured on their MKI or read from our image ·
🟡 adopted on their evidence.

## 1. The filesystem layer (`FS_LAYER.md`) ✅

A 23-slot FS vtable `0x46c823fa..0x46c82452`, three implementations
installed by `0x40014524` / `0x40014636` / `0x40014750`, variant B runs
(the load path's open `0x4001b724` in slot 0); `0x46c8242a` `open(path,
mode) → fd`, `0x46c823fa` existence probe, `0x46c8241e` file size;
`0x46c82456` is the bank pointer, not a slot. `0x40090a14` = recursive
directory walker `walk(path, *dirs, *files, mode, progress)`, stacks
`0x46070e44`/`0x46038e40`; 🟡 `mode == 0` calls `0x46c8241a` per file and
`0x46c8243a` per directory (unlink/rmdir; never call mode 0 on a card you
care about); it enumerates a whole directory before the callback.
Buffered primitives `0x40016864` open, `0x400166b8` write, `0x4001677c`
close (the `.wav` writer above them is `SAMPLE_SAVE.md`).

## 2. Slot loading (`SLOT_LOADING.md`, MKI) ✅

`0x40093980(slot, keep_trim)` has one caller (case 1 of `0x4008445c`),
followed by post-load (`0x40099148(0, slot)` / `0x40099680`),
`0x40093468(-1)` (re-arm eight tracks' voices) and `0x4009da20(-1)`
(refresh); the loader alone gives a slot that shows name and size, no
BPM, no preview, no trig. Status record `0x46c90a78 + slot*0x2c` (`+0x08`
state 0/2/3, `+0x0c` code, `+0x24` handle; `-0x10` INVALID FILENAME,
`-0x1e` INVALID FILETYPE). CLEAR SLOT `0x40025288(kind, slot)` =
`0x40093814(slot)` then zero the 0x448 record (skipping the first leaks
the handle: MAX OPEN FILES). STATIC settings `0x100d5b30`, FLEX
`0x100b14f0`, stride `0x448`.

## 3. A Part lives three times (`FINDINGS.md`, MKI) ✅

Working `bank + 0x8ed80 + part*0x18b2`, saved `bank + 0x9504a + …`, SRAM
`0x100a4ece + part*0x18b2` (the copy that survives a power cycle;
patterns' at `0x1001614e`). A bank write alone is lost at boot.
`0x40029a4c(src, part)` writes both, sets `bank + 0x95048` / `0x100b145e`,
and re-applies with `0x40009094(bank, part)` (also copies scenes A/B at
`part + 0x10/0x11` into `0x80000ed4`). The page arrays inside a Part are
`PARAM_PAGES.md` §5.

## 4. The card from the host (`PROJECT_FILE.md`, MKI) ✅

`PATH=` bare, no quotes; the unit writes nested STATIC paths itself (❌
retracted 13 Sep 2026: "a STATIC PATH must be bare, `../AUDIO/…` loads
empty" — the empty slot is one with no `markers.work` record).
`TRIM_BARSx100 = 100 × 2^round(log2(seconds × tempo24 / 24 / 240))`,
capped 3200 (🟡 cap from one point), never cloned. `markers.work`: 16-byte
header `FORM 00000000 DPS1SAMP`, 264 records × 784 B (136 flex incl. 8
recorders, then 128 static), 8-byte trailer ending in `sum(body) &
0xffff`; STATIC slot n at `16 + (136 + n − 1) × 784`, frame count at `+10`
(4 bytes BE). A slot with no record falls back to 64 frames, writes
`TRIM_BARSx100=0` on the next save, shows the minimum tempo, and neither
trigs nor previews. The unit auto-saves the loaded project continuously
and its RTC runs behind wall clock (compare content, not mtimes).
`project.work` has no checksum; bank files do. octalab's `[META]` signs
`OS_VERSION=R0178     OLAB<n>`. `tools/hw/ot_project.py` never writes
`markers.work`.
