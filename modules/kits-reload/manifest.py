"""KITS RELOAD -- the bridge that lets MIDI SCENES' Part Reload run beside
Octakit's kit reload.

THE COLLISION IS NOT A BYTE. midisc's `reload` stub sits on the two stock
`jsr 0x4004aab4` sites (Part Reload from the menu, 0x4002dd56; FUNC+CUE,
0x4005e05a), swaps the site's return address for `rel_after` -- his
post-reload MSC restore -- and jumps into the stock reload. Octakit's
replacement of that routine (`gk_stock_part_saved_to_working_reload`,
part_save_clear_reload.S) reads the return address off the stack and
accepts only the two stock sites' own (0x4002dd5c, 0x4005e060; abi.inc
GK_STOCK_PART_RELOAD_*_RETURN); anything else is her `illegal` trap. Every
byte either mod writes is disjoint from the other's, so the ledger saw
nothing, and the image ran until the first Part Reload:

    EXCEPTION SSP:4 VEC:04 ADDR:45D167E0 D0:40A96F54     (his unit, 14 Sep 2026)

ADDR = gk_stock_part_saved_to_working_reload_report_fatal in her runtime
as this build links it; D0 = rel_after in ours -- the value her check
loaded. His 1.40MIDISC8.1 alone and her ot-26913 alone reload cleanly:
the fault is the composition's (remix ok-ms, OKMS1, sha256 96a2edd9...,
rebuilt bit-identical to resolve the two addresses).

THE BRIDGE keeps the stock jsr at both sites (his two detours are
overridden) so her caller check passes, and moves his post-work to the
RETURN sites, where the stack is what `rel_after` expects -- the part
index at (sp), `apply_ret` naming the continuation:

  * 0x4002dd5c (menu): jmp `menu_after`; rel_after, then the displaced
    `addq.l #4,sp` / `lea 0x40013a08,a0`, then 0x4002dd64.
  * 0x4005e05a (FUNC+CUE, the call): `shortcut_call` parks the part index
    stock pushed and calls her with the site's own return address. Stock
    pops the index at 0x4005e060 before the return site, and the reload
    moves the byte it came from (0x80000003: his apply bridge rewrites it
    from the engine's part on the way -- 0 -> 1 on the port's RIG
    fixture), so it is parked before, not re-read after.
  * 0x4005e062 (FUNC+CUE, the return): the site is hers -- her
    `reload-shortcut-format` write jumps there to draw the result -- so
    the Override skips her write and `shortcut_after` pushes the parked
    index, runs rel_after, pops it and jumps to her routine
    (RELOAD_FMT_NEXT) exactly as her write did.

d0 (her reload's result, tested at both sites) survives: rel_after saves
and restores it. d1 is dead at both continuations.

The ledger sees this class now: a Runtime declares the return addresses
its replacements validate (`Runtime.pinned_returns`, derived from her
abi.inc), a Detour says when its stub returns the callee somewhere else
(`Detour.subst_return`), and the pair is refused by name unless a bridge
overrides the detour.

MEASURED: the bytes at all four sites (stock jsr kept, the two return-site
jumps, her write replaced) and the boot under the port
(verify_dram_boot). NOT measured: a Part Reload on hardware -- the port
has no panel, so rel_after running after her reload is inferred from the
stack shape, not seen.
"""

from remix.schema import Category, Proof, Detour, Kind, Linked, Module, Override

H = bytes.fromhex

MODULE = Module(
    name="kits-reload",
    key="KITS RELOAD",
    kind=Kind.CF_PATCH,
    category=Category.PARTS, author="sambanks", author_url="https://github.com/sambanks",
    proof=Proof.HARDWARE, proof_note="`ok-ms`, 14 Sep 2026",
    doc="The bridge that lets MIDI SCENES' Part Reload run beside Octakit's "
        "kit reload (her caller check, his post-reload restore).",
    linked=(Linked("reload", "modules/kits-reload/reload.s", dram=True),),
    detours=(
        Detour(0x4002DD5C, H("588f41f940013a08"), "reload", "menu_after",
               "Part Reload returned (menu): his MSC restore, then stock", pad_to=8),
        Detour(0x4005E05A, H("4eb94004aab4"), "reload", "shortcut_call",
               "Part Reload (FUNC+CUE): park the part index, call her with the stock return"),
        Detour(0x4005E062, H("220e0681ffffffe0"), "reload", "shortcut_after",
               "Part Reload returned (FUNC+CUE): his MSC restore, then her format", pad_to=8),
    ),
    overrides=(
        Override(0x4002DD56, "MIDI SCENES"),          # his reload stub, menu path
        Override(0x4005E05A, "MIDI SCENES"),          # his reload stub, FUNC+CUE path
        Override(0x4005E062, "OCTAKIT", write="reload-shortcut-format",
                 defsym="RELOAD_FMT_NEXT"),
    ),
)
