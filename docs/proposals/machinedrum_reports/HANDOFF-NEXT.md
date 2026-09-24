# Next Machinedrum work prompt — 24 September 2026

Continue the Machinedrum remix in `/Users/jannikassfalg/coding/octamad`,
branch `machinedrum` in the main checkout. Do not create a worktree. Commit
and push only to `origin` (`repeat98/octamad`), never `upstream`. Nothing
goes to hardware without the user.

Read `CLAUDE.md`, `docs/proposals/MACHINEDRUM_WORKPACKETS.md` §0–§1 and
its status table, then `docs/proposals/machinedrum_reports/HANDOFF-UI.md`
and `WP-C3.md`. Inspect `git status --short --branch` before editing.
Use this environment for every gate:

```sh
export MD_EMU=$PWD/out/machinedrum/isolated/emu/ot_emu
export OT_PROJECT=out/machinedrum/testset_nofx/OCTABAM/RIG
# RIG with T1's FX2 set to 0x08; the old RIG stores 0x1e and hid a
# dispatch bug until 25 Sep (WP-C3)
```

## State to inherit

- `make verify-md-kit CASES=all` passed all 450 cases and is recorded in
  `WP-C4.md`.
- C3 now stores a FLEX type plus `MD\x01` signature. The repeatable
  `python3 tools/verify/verify_md_ui.py` gate uses `md_panel.py` and RAM
  assertions: SRC SETUP selects MD on T1 while preserving T2's FLEX
  slot; attempted second MD on T2 and assignment on T5 are refused.
  `python3 tools/verify/verify_md_c3.py` separately proves T1 SRC A/B/F
  edits leave T2 unchanged.
- The editor is a separate compiled C unit (`md_ui.c` → `md_ui.s`). The
  panel gate proves track-held TRIG 2 selects part 2, page-1 A changes
  that part's SYN 1, REC+TRIG 5 records step 5 in both MD and OT masks,
  and SRC page-2 A changes part 1 SYN 7 in the kit and correct FLEX slot.
  It also reads VOL/ENG descriptor names and `P02 TRX-SD` from RAM.
  A plain page-2 E encoder turn did not change ENG, so trace the stock
  choice interaction. The post-command LCD capture method produced
  inconsistent or blank frames; do not use those screenshots as proof.
- The first grid probe trapped at `0x40060cea` because `md_trig_key`
  padded its eight-byte detour to ten and destroyed the next stock
  instruction. `pad_to=8` fixes this; the complete panel gate passes.
- After the latest page-2 gate change, `verify-md`, both gain probes,
  `verify-md-transport`, `verify-md-seq`, and
  `make check REMIX=machinedrum` all passed. Logs are under ignored
  `out/mdverify/post_ui_page2/`. The panel gate's captures are under
  ignored `out/mdverify/ui_gate/`.

## Continue in this order

1. Close the remaining editor controls: trace ENG selection and verify it
   by RAM; determine a reliable in-process LCD proof or leave D6's visible
   presentation unchecked. Keep D4/D5/D6 status honest in the table.
2. WP-E1 persistence: implement a versioned project extension for the
   64 kits and 256 patterns, with card round-trip and validation. The
   current `md_kit` is one 192-byte kit and `md_patterns` is 98,304 bytes
   of zeroed runtime storage; both are lost on reload. `WP-D2.md` defines
   the persistent contents; `docs/firmware/STORAGE.md` §1 maps the card
   primitives. Read-only research this turn found stock buffered file
   open/read/seek/write/close at `0x40016864/0x40016564/0x4001660c/
   0x400166b8/0x4001677c`, current project directory at `0x40025230`,
   and project store call sites `0x40085642`, `0x400856dc`, `0x40085780`.
   The full project load call sites to `0x400905d4` are `0x40084d60`,
   `0x400853d8`, `0x40085452`. These are leads from the stock disassembly,
   not yet validated as safe MD hook sites. Octakit's
   `modules/octakit/upstream/runtime/persistence.c` and
   `persistence_v3_abi.S` show existing file ABI and lifecycle handling;
   use them as reference without modifying that submodule.
3. WP-E2 MIDI, then WP-A6 cycles and WP-B5 image and notes. A6 is marked
   blocked on the A5/D1 decisions, and B5 depends on A6. The user flashes
   any image; do not flash hardware.

After each source change, rerun `make verify-md`,
`python3 tools/verify/verify_md_image.py --gain-probe`,
`python3 tools/verify/verify_md_image.py --gain-queue-probe`,
`make verify-md-transport`, `make verify-md-seq`, and
`make check REMIX=machinedrum`. Run long jobs in the background. Do not
edit sources while any of those gates is building. Record results in the
relevant packet and status table, commit the focused change, and push
only `origin machinedrum`.
