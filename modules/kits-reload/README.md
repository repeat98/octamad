# `kits-reload` — KITS RELOAD

Lets MIDI SCENES (bkkbrls-del) and Octakit (Em) share a
Part Reload. `Kind.CF_PATCH`: one DRAM unit (`reload.s`), three detours,
three `Override`s. Nothing of its own to use; it exists so the pair does
not trap.

## Measured

Port (`ot_emu --call`, added for this: a firmware routine called as main
on the loaded project -- the port has no panel), `dram_card.img`, set
`OCTABAM`, project `RIG`:

- ✅ **Reproduced**: the OKMS1-equivalent image (no bridge), `--call
  0x4002dd50` (the menu Part Reload handler): `unimplemented opcode 4afc
  at 45d167e0`, D0 = 0x40a96f54 -- the unit's screen. Watch trail: his
  stub 0x40a9703a → her entry with (sp) = rel_after → the trap, 14
  instructions.
- ✅ **Fixed, menu path**: same call on the bridged image: her entry with
  (sp) = 0x4002dd5c, her kit transaction ran and returned 0, back to
  `menu_after`, `rel_after` (58,727 instructions), `menu_cont`,
  0x4002dd64 with d0 = 1 and a0 = 0x40013a08; the handler returned to
  main with d0 = 1.
- ✅ **Fixed, FUNC+CUE path**: `--call 0x4005e038`: `shortcut_call`, her
  entry with (sp) = 0x4005e060, transaction, `shortcut_after`,
  `rel_after`, `shortcut_cont`, her formatter, 0x4005e09c, the handler's
  `unlk/rts`; no trap.

## On the unit

✅ `OKMS2` (this bridge in `ok-ms`) flashed 14 Sep 2026 and works; Part
Reload no longer traps.

## Open

- Whether rel_after's restore is the right thing after a KIT reload (his
  semantics under her kits -- the same code his own build runs after a
  stock reload). Not measured on its own.

## Gates

`verify_dram_boot`: ✅ both windows read back equal to the linked runtimes.

## The collision is not a byte

Every byte either mod writes is disjoint from the other's, so the ledger
saw nothing, and the first composed image (`ok-ms`, OKMS1, 14 Sep 2026)
ran on his unit -- scenes following kits -- until the first Part Reload:

```
EXCEPTION SSP:4 VEC:04 FS:0 SR:2000
ADDR:45D167E0   D0:40A96F54   SP:460D8D24
CFW:26914-011006
```

VEC:04 is `illegal`. ADDR resolves, in Octakit's runtime as this build
links it, to `gk_stock_part_saved_to_working_reload_report_fatal` (an
`illegal` she plants); D0 resolves, in octabam's platform runtime, to
midisc's `rel_after`. Rebuilt from the same tree, the image is
bit-identical to the one on his unit (sha256 96a2edd9…), so both
addresses are his image's.

The mechanism, from the two sources:

* midisc's `reload` stub (code2.s) sits on the two stock `jsr 0x4004aab4`
  sites -- Part Reload from the menu (0x4002dd56) and FUNC+CUE
  (0x4005e05a) -- parks the site's return address in `apply_ret`, puts
  `rel_after` (his post-reload MSC restore) on the stack in its place,
  and jumps into the stock reload.
* Octakit's replacement of 0x4004aab4 (`gk_stock_part_saved_to_working_
  reload`, part_save_clear_reload.S) reads the return address off the
  stack and accepts only the two stock sites' own -- 0x4002dd5c and
  0x4005e060 (abi.inc `GK_STOCK_PART_RELOAD_*_RETURN`) -- and traps on
  anything else. His `save` and `clr_pt` stubs do their work first and
  tail-jump into her routines with the stock return intact, which is why
  Part Save and Part Clear work in the same image and Reload does not.

His 1.40MIDISC8.1 alone and her ot-26913 alone reload cleanly (his
report); the fault is the composition's.

## The bridge

The stock `jsr` stays at both sites (his two detours are overridden), so
her caller check passes, and his post-work moves to the return sites,
where the stack is what `rel_after` expects -- the part index at (sp),
`apply_ret` naming the continuation.

| site | stock | bridge |
|---|---|---|
| 0x4002dd56 menu `jsr 0x4004aab4` | kept | (his detour overridden) |
| 0x4002dd5c menu return: `addq.l #4,sp; lea 0x40013a08,a0` | jmp `menu_after` | rel_after, replay both, jmp 0x4002dd64 |
| 0x4005e05a FUNC+CUE `jsr 0x4004aab4` | jmp `shortcut_call` | park the pushed index in `reload_arg`, `pea 0x4005e060`, jmp 0x4004aab4 |
| 0x4005e062 FUNC+CUE return: `move.l fp,d1; addi.l #-32,d1` (her `reload-shortcut-format` jumps here) | jmp `shortcut_after` (her write overridden, its target = `RELOAD_FMT_NEXT`) | push `reload_arg`, rel_after, pop, jmp her formatter |

The FUNC+CUE index is parked before the call rather than re-read after
it: stock pops it at 0x4005e060 (two bytes, unhookable before her site),
and the byte it came from (0x80000003) moves during the reload -- his
apply bridge rewrites it from the engine's part on the way (0 → 1 on the
port's RIG fixture, `--watch-mem 0x80000003,1`). The menu path's index
is still on the stack at its return site.

d0 (her reload's result, tested at both continuations) survives:
rel_after saves and restores it. d1 is dead at both continuations (the
menu path never reads it before 0x4002dd68 sets d0; her formatter
recomputes from fp).

## What the ledger sees now

A `Runtime` declares the return addresses its replacements validate
(`Runtime.pinned_returns`, read from her abi.inc's `*_RETURN` equates --
90 of them); a `Detour` says when its stub returns the callee through a
continuation of its own (`Detour.subst_return`: his `reload` ×2 and
`apply_bridge` ×4). A substituting detour of a `jsr` whose return is
pinned is refused by name unless a bridge overrides it:

```
pinned return: octakit and midi-scenes both claim 0x4002dd5c -- octakit's callee
validates the return address of the jsr at 0x4002dd56 and traps on any other;
midi-scenes's stub (Part Reload, menu path) returns it through its own -- bridge the site
```

His `apply_bridge` sites are not pinned (her part-load entry checks its
caller only while her lifecycle state is not active), so they pass.
