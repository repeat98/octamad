# Handoff: the Machinedrum editor, 24 September 2026 (evening)

Written for the next agent, who continues the Machinedrum work on branch
`machinedrum` in the main checkout. Read `CLAUDE.md`,
`MACHINEDRUM_WORKPACKETS.md` §0–§1 and this file before you touch anything.

## Where things stand (all under the port, nothing on hardware)

**Done and committed in this commit:**
- **WP-C4 (kit and producer).** `modules/machinedrum/md_ctl.c` is C,
  compiled by `generate_ctl.py` into the checked-in `md_ctl.s`; storage is in
  `md_ctl_tail.s`, with no `.bss`. It runs the MD's own handlers per part,
  sends trig records and VOL/PAN gain pairs, and refreshes one part per
  frame. `md_xport.s` calls `md_ctl_chunk` once a frame.
  - The MD send path is decoded in `MACHINEDRUM_MACHINE.md` §12, "How the MD
    sends a record".
  - Gate: `make verify-md-kit [CASES=all]`: all 450 cases PASS (finished
    after the handoff commit).
- **WP-D2 (spec, review)** and **WP-D3 (sequencer).** One MD pattern per OT
  pattern, 16 lanes × 64 steps and 64 locks, on the parent track's clock,
  length, scale and swing.
  - The PLAY anchor detours are the same two sites as Euclid's.
  - The default kit is 8 TRX voices and 8 empty parts.
  - Gate: `make verify-md-seq`, PASS: lanes within 0.6 frames of the grid,
    SYN and VOL locks, audio on T1.
- **Regressions**, all PASS with this state: `verify-md`, `--gain-probe`,
  `--gain-queue-probe`, `verify-md-transport` (33,513/33,513 blocks) and
  `make check REMIX=machinedrum`.

The command environment every gate here used:

```
export MD_EMU=$PWD/out/machinedrum/isolated/emu/ot_emu   # the port on the repo's dsp56300 pin (shared vendor/ is stale, WP-R4)
export OT_PROJECT=out/machinedrum/testset/OCTABAM/RIG    # copy of out/mdverify/tree/OCTABAM (SINE440 on T1); gitignored
```

The MD flash dump is at `base_firmware/elektron_sps1-1uw_os1.63.bin`.
`md_handler_cases.py` now accepts that path. The handler captures are in
`out/machinedrum/c2_maps`, taken with the rebuilt `out/md_reference/md_profile`.

## THE BUG TO FIX FIRST (WP-C3 is now `blocked`)

C3 stores an MD track as **raw machine type 6** in the Part. About 48 stock
sites index a Part's page stores by `type × 6`: page 1 at
`part + 0x2a + t·30 + 6·type`, page 2 at `part + 0x1da + …`. The page-1
writer `0x40054d5c` is one of them. So **turning a SRC knob on the MD track
writes T2's FLEX slot.** Measured under the port with
`drafts/explore_src.py`: after A +10, B +5 and F +3 on T1 = MD, T2's FLEX
page 1 read `73 5 0 127 0 82`.

**The fix is drafted, not built:** `drafts/md_machine_v2.s`, which replaces
`modules/machinedrum/md_machine.s`. The Part stores **FLEX (1)**, and the MD
identity is a signature `'M','D',1` in that track's **NEIGHBOR page-1 slot**
(`part + 0x2a + t·30 + 18`, working Part plus the SRAM copy
`0x100a4ece + part·0x18b2`). NEIGHBOR has no parameters, so stock never
touches those bytes, and the Part saves, reloads and copies them. Stock sees
a FLEX track everywhere, and stock firmware opens the project as FLEX.

What the draft contains:
- **Commits.** `md_main_commit` (`0x4007981c`) and `md_src_commit`
  (`0x4005a616`): row 6 → admit, write the signature, store FLEX; any other
  row → clear the signature. The SRC path also sets the cursor
  `0x460d5c30` to 1.
- **Admission and dispatch.** `md_admit` and `md_pack_fx2` test the
  signature (`md_sig_check`).
- **New detours.** Each is a `jmp` over the displaced bytes; the draft's
  comments give the exact displaced instructions.

  | label | site | displaced | what it does |
  |---|---|---|---|
  | `md_name_a` | `0x4003d718` | `lea 0x400a78c8,a0` | name lookup |
  | `md_name_b` | `0x4004c36a` | `lea` | name lookup |
  | `md_setup_row` | `0x4003c980` | 6 B | SRC SETUP list box |
  | `md_chooser_row` | `0x400786c8` | 6 B | main chooser box |
  | `md_resolve_pb` | `0x40031e74` | 8 B, pad 2 | the resolver returns the MD page for the MD track and stock FLEX `0x400d31ae` for every other FLEX track |
  | `md_trig_key` | `0x40060ce0` | 8 B, pad 2 | MD track key held + TRIG selects a part (`md_ui_select`) |

  They read `md_ui_md_type` and `md_ui_md_track`, which `md_ui.c` publishes.
- **Manifest changes needed:**
  - drop the detours `md_config_type` (`0x4000C0D6`) and `md_live_type`
    (`0x4000BFE8`);
  - replace the two `kind="lea"` detours at `0x4003D718` and `0x4004C36A`
    with the jmp detours above; keep the `0x4003C928` lea (the list rows);
  - revert these pokes to stock: `0x4000244E`, `0x40002454`, `0x4000C02C`,
    `0x400971BE`, `0x400D5F50` (table[6] back to NEIGHBOR `0x400D34D2`, so
    the MACHINEDRUM row never stages into T2), `0x400D644C`, `0x400D646C`,
    `0x4003D712` and `0x4004C364`;
  - keep the row-count and bound pokes: `0x40079248`, `0x400585FA`,
    `0x4003C950`, `0x40078678`, `0x400786CE` and `0x40079904`.
- The draft **assembles** (`m68k-elf-as -mcpu=5407`). Nothing else is
  tested.

## The editor draft (WP-D4/D5/D6): `drafts/md_ui.c`

The idea is **the stock UI is the editor, and the MD state is mirrored in
and out once a frame** (`md_ui_frame`, to be called from `md_ctl_chunk`
before `apply_kit`):
- **Page (D5).** It copies FLEX's descriptor at run time (`0x400d3176`, 0x1ca
  bytes, so no Elektron byte is in the repo) into `md_ui.desc`, then patches
  it:
  - names from the selected part's engine;
  - every slot 0..127, formatter 0 and widget 0;
  - page 2 = SYN7, SYN8, VOL, PAN, ENG (formatter `md_eng_fmt`, 4 characters
    such as `T-BD`), `---`.

  It publishes `md_desc_p`. `md_resolve_pb` serves it by track, and the
  table entry `0x400d5f38[1]` is swapped while the UI track is the MD
  track. Values go both ways through the track's FLEX slot: page 1
  `+0x2a + t·30 + 6`, page 2 `+0x1da + t·30 + 6` (**the page-2 offset is
  not measured: verify it**), the SRAM copy, and the live lane
  `0x80000810 + 72·t` (+0..5 and +0x20..0x25).
- **Lane (D4).** The MD track's OT trig mask in the UI pattern,
  `[0x46c82456] + pattern·0x8ed8 + t·0x91a`, 8 bytes big-endian with step s
  = bit s, always shows the selected lane. Stock grid and live recording,
  the LEDs and PAGE edit it, and the draft copies edits back into
  `md_patterns`. **The mask's RAM offset is inferred from `ot_project.py`:
  verify it.**
- **Info (D6).** `md_ui_name` = `"P05 TRX-SD"`, shown by the name
  detours.

**To build it** (not done):
1. Add `MdUi` to `md_ctl.h`, sized to the draft's static assert:
   ```c
   typedef struct {
       uint8_t sel, shown_sel, shown_track, shown_part, shown_engine, desc_engine;
       uint8_t lane_sel, lane_track, lane_bank, lane_pattern;
       uint8_t snap[12], lane_snap[8];
       ...                                  /* pad to 40 */
       uint8_t desc[MD_DESC_BYTES + 2];     /* MD_DESC_BYTES = 0x1ca */
   } MdUi;
   ```
   Add these externs: `md_ui`, `md_desc_p`, `md_ui_md_track` (u32, −1 when
   none), `md_ui_md_type`, `md_ui_name[12]`.
2. Add `char name[6]` (for example `"TRX-BD"`) to `MdEngine`, which becomes
   52 bytes: update `handler_build.py engine_table` and the static assert.
3. Initialise `shown_*` and `lane_*` to 0xff and `md_ui_md_track` to −1.
   Mind the zeroed-storage trap: `parent_age` was exactly that bug today.
4. In `md_ctl.c`, take the parent track from `md_ui_frame()` (the signature
   scan) instead of `md_parent_track`.
5. Make `generate_ctl.py` compile `md_ui.c` into its own `md_ui.s` (a
   separate `Linked` unit: two gcc outputs in one file clash on `.L`
   labels).
6. Build a UI gate with `tools/harness/md_panel.py`, a FIFO-scripted panel
   under `ot_emu --live`:
   - select MD on T1 through the chooser and check the signature and FLEX
     type, and that T2's slot is unchanged;
   - hold T1 (key `0x10`) + TRIG 2 → `md_ui.sel = 1`;
   - turn A → `md_kit.part[1].syn[0]`;
   - REC + TRIG 5 → lane bit;
   - an LCD png shows the names.

   Only the last `--mem-dump` is written per run.

## Traps found today

- **A startup hold.** Blocks sent before the DSP's frame dispatch runs are
  lost, so the producer holds its first 16 frames (`MD_START_FRAMES`).
- **Zeroed storage means "seen".** `parent_age` = 0 read as "MD track seen"
  and activated the producer in every FX2 gate. Fixed: 0 now means never.
- **Handler history.** Some handlers keep state in the record (TRX-CP
  computes only on a trig). Some captured "cases" are non-trig updates with
  eased parameter values. The expected words are `map.txt`'s trig packets.
- **Symbol names.** `md_seq` is taken by `md_xport.s`; the sequencer state
  is `md_lanes`.
- **Linking.** DRAM units link as 5407: compile C with `-mcpu=5407`.
- **Concurrent edits.** Never edit sources while a gate or `make check` is
  building: "runtime linked differently the second time" was caused by that.

## Still open after the editor

- WP-E1 persistence. Kits and patterns are lost on reload. The card
  primitives are in `STORAGE.md` §1.
- WP-E2 MIDI, WP-E3 admission and cycle caps, WP-A6 the full-kit cycle
  cost, WP-B5 the flash image and notes.
- WP-D2 needs the user's sign-off.
- OT p-locks on the mirrored steps are not converted into MD lane locks
  yet. The step records are at `TRAC + 0x78 + s·0x20` (RAM, 🟡).


## 24 September 2026 checkpoint (Codex)

- The 450-case C4 rerun passed and is recorded in `WP-C4.md`.
- C3's drafted machine source and manifest changes are built. The signed
  fixture's SRC edits change T1's FLEX slot, leaving T2 unchanged
  (`tools/verify/verify_md_c3.py`). All six required post-C3 regressions
  passed after a narrow `verify_hidden.py` fix; see `WP-C3.md`.
- The page-2 offset is confirmed by the stock writer in
  `docs/firmware/PARAM_PAGES.md`. The trig mask was verified under the
  port *after* `--sequencer` selected pattern 0: T1 RAM at DB+0 matched
  file mask `0000000000010001`; T2 at DB+0x91a matched
  `0000000100000000`. A load-only probe showed zero masks before
  pattern selection. Probe output is in ignored `out/mdverify/mask/`.
- `md_ui.c` is copied into the module and compiled separately into
  `md_ui.s`; `make bus REMIX=machinedrum` succeeds. The C3 SRC isolation
  gate also passes with this editor build.
- **Unfinished:** the full UI panel gate and the post-editor six-gate
  regression have not run. A first double-SRC exploratory panel script
  delivered all events but did not enter the chooser (Part type remained
  0; cursor 0). Determine the correct chooser gesture, then verify the
  selection, part pad, parameter edit, REC grid bit and LCD names. Review
  the editor's runtime behavior before marking D4/D5/D6 complete.
- E1 persistence, B5 image/notes, E2 MIDI and A6 cycles were not started.
  B5 depends on A6, which remains blocked on the documented A5/D1
  decisions. No hardware action.

## 24 September 2026 panel RAM checkpoint (Codex)

- The repeatable panel gate is `MD_EMU=$PWD/out/machinedrum/isolated/emu/ot_emu
  OT_PROJECT=out/machinedrum/testset/OCTABAM/RIG python3
  tools/verify/verify_md_ui.py`. It stages fresh test cards under ignored
  `out/mdverify/ui_gate/`, sends FIFO events with `md_panel.py`, and asserts
  RAM rather than a post-command LCD screenshot.
- FUNC+SRC, six DOWN presses, YES assigns a signed FLEX MD on T1. The
  chooser leaves T2's FLEX slot unchanged. The same action on T2 with T1
  already assigned, and on T5, is refused. All panel events were delivered.
- Holding T1 and pressing TRIG 2 sets `md_ui.sel=1`. A +5 changes part 2's
  SYN 1 from 64 to 69 and T1's FLEX slot to 69. REC+TRIG 5 sets bit 4 in
  `md_patterns[0].trig[1]` and the OT track trig mask. The live descriptor
  has VOL and ENG on page 2, and `md_ui_name` is `P02 TRX-SD`. This proves
  the string and descriptor in RAM; the LCD presentation remains unverified.
- The first grid attempt trapped at `0x40060cea`: `md_trig_key` had
  `pad_to=10`, overwriting the first two bytes of stock's six-byte `tst.l`
  following its eight displaced bytes. `pad_to=8` fixed it. The panel
  gate and the required post-fix `verify-md`, both gain probes,
  `verify-md-transport`, `verify-md-seq`, and
  `make check REMIX=machinedrum` passed.
- Next: WP-E1 persistence. Page-2 knob and engine-choice actions, and an
  actual LCD render of the info name, remain editor acceptance work.
