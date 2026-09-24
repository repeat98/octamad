"""Machinedrum on core 1 (payload B, tracks 1-4): machine registration proof.

The Part stores FLEX (type 1) with an MD signature in its NEIGHBOR page slot.
Type 5 is reserved for POLY.
The FX2 id 0x1e is hidden from its chooser and selected in the transient DSP
frame when that machine is active. On core 1 the id runs
md_glue.asm, which writes the ColdFire's record packets into the voice
records (WP-C1: md_xport.s adds a block to the host-transfer chain), runs
the relocated MD voice DSP through md_driver.asm and mixes the sixteen
slots into the track (tools/build/md_image.py). Until a packet has
arrived it triggers slot 0 with a fixed TRX-BD record on the track's OT
trig instead. On core 0 the same id is a passthrough stub. The MD's code
and tables come from the user's pinned MD OS 1.63 update at build time
(tools/build/md_payload.py); no firmware byte enters the repository.

The ColdFire control engine (md_ctl.c, compiled to md_ctl.s) holds the
kit and the embedded 16-lane sequencer: it runs the MD's own handlers for
each part and plays the lanes on the parent track's step grid (WP-C4,
WP-D3). Not yet: the editor (part selection, grid view, pages),
MD-specific persistence, MIDI, E12 sample delivery and the hardware
qualification (docs/proposals/MACHINEDRUM_WORKPACKETS.md).
The MD's eight per-track effects and original mixer DSP are excluded from
the target; the current payload already loads only the voice DSP.
"""

from pathlib import Path
import runpy

from remix.schema import (BusRole, Claims, Detour, DspSection, Formatter, Kind,
                          Linked, MenuEntry, Module, Param, Poke, SymbolRef,
                          YBase)

H = bytes.fromhex
U32 = lambda value: value.to_bytes(4, "big")


_LAYOUT = runpy.run_path(str(Path(__file__).with_name("layout.py")))
LAYOUT = _LAYOUT["LAYOUT"]


def _allocation(name):
    return next(region for region in LAYOUT["allocations"]
                if region["name"] == name)


def _span(name):
    region = _allocation(name)
    return {
        "name": name,
        "space": region["space"],
        "start": region["start"],
        "end": region["start"] + region["words"],
        "words": region["words"],
    }


# B1's resource declaration is deliberately plain data.  It is derived from
# layout.py so a later extractor cannot quietly acquire a second address book.
# The generic remixer ledger does not yet arbitrate the shared physical window;
# B2 is where these claims become build placement and collision checks.
RESOURCE_CLAIMS = {
    "payload": "B",
    "donor": {
        "name": "payload-B stock effects and the P above them",
        "space": "P",
        "start": _allocation("hot_code")["start"],
        "end": (_allocation("driver_code")["start"]
                + _allocation("driver_code")["words"]),
        "words": (_allocation("hot_code")["words"]
                  + _allocation("driver_code")["words"]),
    },
    "shared": tuple(_span(name) for name in (
        "window_code", "window_tables", "e12_tail",
        "sample_meta", "window_tables_b", "sine", "glue")),
    # WP-C1's mailbox, core 1's private X (both host banks).
    "private": tuple(_span(name) for name in ("mbox_a", "mbox_b")),
}


def _check_claims():
    spans = [RESOURCE_CLAIMS["donor"], *RESOURCE_CLAIMS["shared"]]
    for left, right in zip(sorted(spans, key=lambda item: item["start"]),
                           sorted(spans, key=lambda item: item["start"])[1:]):
        if left["space"] == right["space"] and left["end"] > right["start"]:
            raise ValueError(
                f"Machinedrum resource claims overlap: {left['name']} and "
                f"{right['name']}")


_check_claims()


MODULE = Module(
    name="machinedrum",
    key="MACHINEDRUM",
    kind=Kind.HYBRID,
    doc=("Machinedrum on T1-T4 (FLEX plus signature): a 16-part kit and an "
         "embedded 16-lane sequencer on the parent track's grid."),

    menu=MenuEntry(
        # Internal DSP dispatch id, hidden from FX2 by the remix. The
        # machine's transient frame selects it without changing the Part's
        # own FX2 setting. FX1's chooser does not list it either.
        fx2_id=0x1e,
        donor_desc=0x400d58b8,        # DARK REV, as HELLO WORLD
        abbr=b"MD",
        fullname=b"MACHINEDRUM",      # 11 of 13 bytes
        build_tag=False,
    ),

    params=(
        # ---- page 1 -------------------------------------------------------
        Param(b"VOL", 100, 128, active=True, formatter=Formatter.PLAIN,
              doc="reserved proof descriptor; machine glue uses fixed gain"),
        Param(), Param(), Param(), Param(), Param(),
        # ---- page 2: none ---------------------------------------------------
        Param(), Param(), Param(), Param(), Param(), Param(),
    ),

    dsp=DspSection(
        asm="modules/machinedrum/md_stub.asm",
        priority=17,                  # after every existing module
        bus_role=BusRole.NONE,
        ybase=YBase.NEVER,
        r7_latch_slot=None,
        gate_label=None,
    ),

    # Payload B's thirteen stock effects are the MD's hot code now: on core 1
    # every stock id runs the null stub (tools/build/md_image.py).
    claims=Claims(gives_up_payload_fx=("B",)),

    # WP-C1, the record transport: one more burst in the host-transfer chain,
    # to core 1, before stock state 5 (docs/firmware/DSP.md section 6c).
    linked=(
        Linked("mdxport", "modules/machinedrum/md_xport.s", dram=True),
        # WP-C4: the kit and its record producer, C compiled to md_ctl.s
        # (generate_ctl.py). md_xport asks it for a chunk once a frame.
        Linked("mdctl", "modules/machinedrum/md_ctl.s", dram=True),
        Linked("mdui", "modules/machinedrum/md_ui.s", dram=True),
        Linked("mdmachine", "modules/machinedrum/md_machine.s", dram=True),
        # Generated under out/ from the user's pinned MD OS before linking.
        # Labels expose each descriptor's unchanged ISA_A handler.
        Linked("mdhandlers", "out/machinedrum/handlers.s", cpu="5206e",
               dram=True),
    ),
    symbol_refs=(
        SymbolRef(0x400ab62e, 0x40004aaa, "mdxport", "md_xport",
                  note="host-transfer chain state 5 -> the MD block first"),
    ),
    detours=(
        Detour(0x400334D8, H("2f02222f0008"), "mdmachine", "md_machine_name",
               "format raw machine type 6 as MACHINEDRUM"),
        Detour(0x4003C928, H("4bf9400a78c8"), "mdmachine", "md_src_names",
               "point SRC SETUP at seven machine names", kind="lea"),
        Detour(0x4003D718, H("41f9400a78c8"), "mdmachine", "md_name_a",
               "main page name lookup for the signed MD track"),
        Detour(0x4004C36A, H("41f9400a78c8"), "mdmachine", "md_name_b",
               "second main page name lookup for the signed MD track"),
        Detour(0x4003C980, H("71104fef0018"), "mdmachine", "md_setup_row",
               "SRC SETUP row highlights MD on a signed FLEX track"),
        Detour(0x400786C8, H("7110b480"), "mdmachine", "md_chooser_row",
               "main chooser row highlights MD on a signed FLEX track"),
        Detour(0x40031E74, H("710541f9400d5f38"), "mdmachine", "md_resolve_pb",
               "resolve the signed track's MD page without changing other FLEX tracks", pad_to=10),
        Detour(0x40060CE0, H("222f0004202f0008"), "mdmachine", "md_trig_key",
               "held MD track key and trig select a part", pad_to=8),
        Detour(0x4007981C, H("77101084d081"), "mdmachine", "md_main_commit",
               "admit one MD instance on T1-T4 at main chooser commit"),
        Detour(0x4005A616, H("2239460d5c30"), "mdmachine", "md_src_commit",
               "admit one MD instance on T1-T4 at SRC SETUP commit"),
        Detour(0x4000D146, H("30eb0020d5fc0000003a"), "mdmachine", "md_pack_fx2",
               "select MD DSP dispatch from the machine byte in transient frame setup",
               pad_to=10),
        # WP-D3: the lanes restart on PLAY at stock's anchor (as Euclid's do;
        # the two modules therefore never share a remix).
        Detour(0x4009c3d4, H("23c0800065b8"), "mdctl", "md_start_hook",
               "restart the MD lanes at the stock PLAY anchor"),
        Detour(0x4009c4d4, H("23c0800065b8"), "mdctl", "md_resume_hook",
               "restart the MD lanes on the second PLAY path"),
    ),
    pokes=(
        Poke(0x40079248, H("48780005"), H("48780007"),
             "machine chooser has seven rows including type 5 reserve and MD"),
        Poke(0x400585FA, H("48780005"), H("48780007"),
             "SRC SETUP selector has seven rows"),
        Poke(0x4003C950, H("7204"), H("7206"),
             "SRC SETUP name lookup admits MD"),
        Poke(0x40078678, H("7004"), H("7006"),
             "machine chooser draws MD"),
        Poke(0x400786CE, H("7004"), H("7006"),
             "machine chooser highlights MD"),
        Poke(0x40079904, H("7604"), H("7606"),
             "machine chooser persists MD"),
    ),
)
