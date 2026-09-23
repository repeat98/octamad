# WP-D1 Is the chord free?: report

- **Status:** done
- **Branch and commit:** `machinedrum` @ `d4a626b`
- **Date:** 23 September 2026
- **Agent:** overnight Machinedrum handover

## What was done

Read the panel and main-menu notes and continued the partial keymap read in
`WP-A1.md`. The stock MKII map sends track keys `0x10–0x17` to
`0x40040250`; its track-held sub-map at `0x400d164a` has no trig entries.
The trig handler at `0x40060ce0` tests grid-recording state `0x460d1736` and
dispatches to `0x40060b58` or `0x400501d8`.

The two target routines do not read the panel row state or the held-track
map. The static answer is that stock “hold track key + TRIG” is unclaimed;
the fallback for the MD page is FUNC + track key. No hardware behavior was
changed or tested.

## Acceptance check

The firmware-derived bytes remain in `out/`; the committed check records only
the disassembled addresses and instructions:

```
$ m68k-elf-objdump -D -b binary -m m68k:cfv4e --adjust-vma=0x40000400 out/raw/section_3_MAIN_OS.bin | sed -E 's/^([0-9a-f]+):[[:space:]]+[0-9a-f]+( [0-9a-f]+)*[[:space:]]+/\1: /' | rg '^(400501d8|400501e2|400501ea|400501ee|400501f8|40050206|40050226|40050252|40050278|40050294|400502b4|400502c0|400502c8|400502d4|400502e6|400502f4|40060b58|40060b68|40060b98|40060bd2|40060bec|40060bf8|40060c1c|40060c22|40060c34|40060c80|40060c9c|40060cd4|40060cdc|40060ce0|40060ce8|40060cf0|40060cf4|40060cfc)'
400501d8: movel %d2,%sp@-
400501e2: moveq #1,%d0
400501ea: moveb #5,%d0
400501ee: cmpl 0x460d16f0,%d0
400501f8: movel 0x460d16f0,%d0
40050206: jmp %pc@(0x4005020a,%d0:l)
40050226: tstl 0x80000012
40050252: movel %d2,%sp@-
40050278: movel %d2,%sp@-
40050294: movel %d2,%sp@-
400502b4: movel %d2,%sp@-
400502c0: moveq #1,%d0
400502c8: movel %d2,%sp@-
400502d4: jsr 0x4004581c
400502e6: clrl %sp@(8)
400502f4: rts
40060b58: lea %sp@(-12),%sp
40060b68: moveal 0x46c82456,%a1
40060b98: tstl 0x80000012
40060bd2: movel 0x460d1e04,%d0
40060bec: moveq #15,%d4
40060bf8: mvzb 0x100b14cc,%d1
40060c1c: moveq #4,%d1
40060c22: tstl 0x80000012
40060c34: moveq #1,%d4
40060c80: moveq #2,%d0
40060c9c: movel %d3,%sp@-
40060cd4: moveml %sp@,%d2-%d4
40060cdc: rts
40060ce0: movel %sp@(4),%d1
40060ce8: tstl 0x460d1736
40060cf0: braw 0x40060b58
40060cf4: movel %d0,%sp@(8)
40060cfc: jmp 0x400501d8
```

## Measured

- ✅ Static disassembly of `0x40060ce0`, `0x40060b58` and `0x400501d8`
  produced the acceptance output above from
  `out/raw/section_3_MAIN_OS.bin`.
- ✅ The panel keymap and held-key sub-map facts are recorded in
  `MACHINEDRUM_MACHINE.md` §12 above, with the source notes in
  `docs/firmware/PANEL.md` and `MAINMENU.md`.
- *inferred* No held-track test in either target means the stock chord is
  free; FUNC + track is the fallback. This is a static inference, not a
  hardware measurement.

## Retracted

None.

## Open and handover

- WP-D1 is complete; no user decision is needed for the fallback.
- The proposed MD page should reserve FUNC + track for part selection until
  the user signs off the layout and UI behavior.
