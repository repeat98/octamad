# MIDI SCENES

MIDI-driven scene locks, built from
[bkkbrls-del/midisc](https://github.com/bkkbrls-del/midisc) (submodule
`upstream/`, tracking `1.40MIDISC8.2`). `Kind.CF_PATCH`: twelve linker-placed
units in DRAM, 38 detours, four pokes. No DSP code, no menu row.

## What it does

Stock 1.40C has no per-scene parameter lock over MIDI: XF morph reads one live
8×30 lock table that only the panel writes. midisc adds a second, addressable
table (`MSC`, `scene<<8 | track<<5 | flat`, 4 KB) and rewires scene hold, XF
morph, part save/reload and the scene clear/copy/paste rows to read and write
it when a MIDI event is driving. The panel path is untouched. His README
(`upstream/README.md`) is the behaviour list.

Not carried: his MIDI → CONTROL CC48/55/56 tick rows (UI-table pokes, not a
cave; off in his own builds since 8.1); CCs behave as stock in an octabam
image. His `voice_reload` cave has no caller since 8.2 and is not linked.

## How it is built

His caves are written in his Python encoder (`tools/ot3_asm.py`) and placed
at fixed addresses by his `build.py`. His `tools/gas_port.py` drives the same
builders with an encoder subclass that records one GNU-as line per
instruction, writes `gas/*.s`, then assembles and links every region at his
address and compares. Cross-cave references are linker symbols, so octabam
places each unit where it chooses: every unit is `dram=True`, linked into the
platform runtime, appended behind octabam's loader and depacked at boot into
the arena reserve (`docs/remixer/PLACEMENT.md`). Inside the OS the module
changes only the detour and poke sites, plus the boot redirect when no other
module supplies it.

## Measured

- `tools/verify/verify_midiscenes.py` (in `make verify`): every region
  assembles and links to his encoder's bytes at his addresses, and the
  committed `gas/*.s` are what `gas_port.py` regenerates.
- Under the ColdFire port: the boot detour reaches the loader, the loader's
  hash gates pass, the window reads back equal to the linked image except his
  own state words, i.e. his code ran from DRAM during boot. Arms the control
  fixture's five tracks.
- The submodule pin is his `main` at `63ca127` (his PR #6, merged): his
  8.2 (`8cba0fa`) plus two gas commits, the 1.40MIDISC8 `gas_port.py`
  (region table checked against his image) and a regeneration for 8.2 that links `cc_gate` only while his
  CONTROL filter is on, as his `build.py` does. His `build.py` at `8cba0fa`
  stops at `SAFE_CAVE overrun 2068` (`SAFE_CAVE_END` allows 2060): the 8.2
  `xf_mix` probe adds 12 bytes. The linked units are unaffected (DRAM).
- His own `1.40MIDISC8` image fails project load under the port: his CAVE2
  (`0x400d2ee6`, 308 bytes) overruns the enable words (`0x400d3014/18`) of a
  stock descriptor at `0x400d2e8a` that the loader reads; stock also writes
  `0x400d2e84..89`, where his VOICE_RELOAD_CAVE starts. This build links
  every unit into DRAM and is immune. Told him.
- **On hardware 14 Sep 2026** as `OKMS1` (remix `ok-ms`, with Octakit),
  confirmed working by him on his own unit.

## Open

- The apply_part entry (`0x40009094`) stays stock since his 1.40MSCN6 (his
  earlier wrapper hung project load on hardware), so Octakit owns it alone
  and nothing bridges the two. What his Part save/reload hooks mean against
  her LOAD/SAVE KIT menus is not measured; the Kit write protocol
  (`gk_workspace_*`, `modules/octakit/README.md`) is the remaining piece.
- His MIDI CONTROL tick rows, if wanted, need a menu-table mechanism.
