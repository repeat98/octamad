"""Machinedrum on core 1 (payload B, tracks 1-4): the M1 proof path.

The FX2 chooser carries MACHINEDRUM (id 0x1e). On core 1 the id runs
md_glue.asm, which writes the ColdFire's record packets into the voice
records (WP-C1: md_xport.s adds a block to the host-transfer chain), runs
the relocated MD voice DSP through md_driver.asm and mixes the sixteen
slots into the track (tools/build/md_image.py). Until a packet has
arrived it triggers slot 0 with a fixed TRX-BD record on the track's OT
trig instead. On core 0 the same id is a passthrough stub. The MD's code
and tables come from the user's pinned MD OS 1.63 update at build time
(tools/build/md_payload.py); no firmware byte enters the repository.

Not yet: machine registration, the live record producer (the transport
is fed by a test stream only), the sequencer, persistence, MIDI, E12
sample delivery and the hardware qualification
(docs/proposals/MACHINEDRUM_WORKPACKETS.md).
"""

from pathlib import Path
import runpy

from remix.schema import (BusRole, Claims, DspSection, Formatter, Kind, Linked,
                          MenuEntry, Module, Param, SymbolRef, YBase)


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
    doc=("Machinedrum voice DSP on core 1 (T1-T4, FX2 slot): fixed TRX-BD "
         "trigger on the OT trig, 16-slot mix. M1 proof path."),

    menu=MenuEntry(
        # 0x1e: not stock's and claimed by no other module (the registry
        # refuses a duplicate). An FX2 id is also an FX1 id; FX1's chooser
        # does not list it.
        fx2_id=0x1e,
        donor_desc=0x400d58b8,        # DARK REV, as HELLO WORLD
        abbr=b"MD",
        fullname=b"MACHINEDRUM",      # 11 of 13 bytes
        build_tag=False,
    ),

    params=(
        # ---- page 1 -------------------------------------------------------
        Param(b"VOL", 100, 128, active=True, formatter=Formatter.PLAIN,
              doc="the sixteen-slot mix's level, val/128"),
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
        # Generated under out/ from the user's pinned MD OS before linking.
        # Labels expose each descriptor's unchanged ISA_A handler.
        Linked("mdhandlers", "out/machinedrum/handlers.s", cpu="5206e",
               dram=True),
    ),
    symbol_refs=(
        SymbolRef(0x400ab62e, 0x40004aaa, "mdxport", "md_xport",
                  note="host-transfer chain state 5 -> the MD block first"),
    ),
)
