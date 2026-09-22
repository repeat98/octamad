"""CC PAGE 2 -- MIDI CC 62-67 reach the FX2 effect's page-2 slots 6-11, CC 68-73
the FX1 effect's.

Stock incoming CC reaches only FX2 page 1 (CC 40-45; the handler admits
cc-16 < 30, docs/firmware/MIDI.md appendix A). The MIDI dispatch table entry
0x400d6474[0xB] (the CC vector) is repointed from the stock handler
0x4000e79c to the cave. The cave reads the CC number; anything but 62-73
tail-calls CC_NEXT (stock, or Octakit's handler under the SCENES KITS
bridge) with the argument intact. For 62-67 it rebuilds the channel->track
map, gates on AUDIO CC IN, and writes page-2 slot (cc-62) on every audio
track whose trig channel matches: Part, live byte and mirror, the stores
the page-2 editor 0x4003a474 makes (traced; it does not touch TRACKB). For
68-73 it writes the FX1 page-2 slot the same way the FX1 page-2 editor
0x4003abe4 does (Part +0x8f07e, shadow 0x100a51cc, lane +0x32, the four
dirty flags), clamped by the FX1 descriptor's min/count; count 0 (NONE)
writes nothing. Selects are clamped to their count: an over-count stored
value is used as an index and stalls the sequencer.

Source is the truth: the build assembles and links cc_page2.s where the
cave floats; `legacy_bytes()` is the hand-assembled oracle the linked
source is compared against (CavePatch.reference, and
tools/verify/verify_ccpage2.py, which also proves the write for all eight
tracks in the emulator against the firmware editor)."""

import pathlib

from remix.schema import CavePatch, Kind, Module

# Page-2 clamp counts, slots 6..11: selects carry their count, knobs 128.
# Must match modules/busverb and modules/busdelay.
VERB_COUNTS = bytes((3, 128, 128, 4, 128, 128))   # MODE, (blank), DIFF, SHFT, GATE, (blank; RATE until 15 Sep 2026)
DLY_COUNTS = bytes((3, 128, 128, 4, 128, 128))  # MODE, SCAT, DENS, SIZE(select), PTCH, WOW (FRZE until 20 Sep 2026)

# The CC dispatch vector (status>>4 == 0xB) and its stock target.
DISPATCH_CC = 0x400d64a0
STOCK_CC = 0x4000e79c
STOCK_RTS = 0x40027e1a           # a bare `rts` in stock (the tail of 0x40027e00)

# The hand-assembled form of cc_page2.s, with 0x40bad000/4 placeholders
# for its two count tables; legacy_bytes(addr) patches them in. The oracle
# the linked source is compared against every build.
CODE = bytes.fromhex(
    "206f000470001028000104800000003e720bb280650260064ef94000e79c4fefffe448d7"
    "04fc28002448263946104cf44eb9400018547a001a2a000202850000007f4a3980000049"
    "67287000101202800000000f41f946c7febe2e300c007c007001eda8c087670261125286"
    "7008b0866eee4cd704fc4fef001c4e757206b2846f000114203946c82456720012398000"
    "0003263c000018b24c031000d0812040d1fc0008ed88d1c6700010107206b28067107207"
    "b28067024e7543f940bad000600643f940bad00472001231480053812405b4816f022401"
    "203946c824567200123980000003263c000018b24c031000d0817200d0812040d1fc0008"
    "f0842206761e4c031000d1c1d1c410822040d1fc0008f084d1c1d1c41082220676484c03"
    "100041f980000810d1c1d1fc00000038d1c410822606721e4c013000220092b946c82456"
    "d2830681100a51d22041d1c4108272001239800000037601e3ab207946c824562248d3fc"
    "000950481211828312811239100b145e828313c1100b145ed1fc0009b3327201208123c1"
    "100f8598610000ea4e75203946c824567200123980000003263c000018b24c031000d081"
    "2040d1fc0008ed80d1c672001210670000ba43f9400d5f5822711c00260441f13c002228"
    "009a2628006ad28353812405b4836c022403b4816f0224012206761e4c03100026045d83"
    "2040d1c1d1c3d1fc0008f07e1082224093f946c82456d3c1d3c3d3fc100a51cc12827200"
    "1239800000037601e3ab207946c824562248d3fc000950481211828312811239100b145e"
    "828313c1100b145ed1fc0009b3327201208123c1100f8598220676484c03100026045d83"
    "41f980000810d1c1d1fc00000032d1c31082610000284e754feffff048d7047024442806"
    "7a001a39800000034eb940027e1a4cd704704fef00104e754feffff048d704702a045d85"
    "244528067a001a39800000034eb940027e1a4cd704704fef00104e75"
)

VCOUNT_MARK = bytes.fromhex("40bad000")
DCOUNT_MARK = bytes.fromhex("40bad004")


def legacy_bytes(addr):
    """CODE at `addr` with its two placeholders patched to the appended
    tables: the oracle for the linked source. The build never writes these
    bytes itself."""
    code = bytearray(CODE)
    vcount_at = addr + len(code)
    dcount_at = vcount_at + len(VERB_COUNTS)
    for mark, target in ((VCOUNT_MARK, vcount_at), (DCOUNT_MARK, dcount_at)):
        i = code.find(mark)
        assert i >= 0, "placeholder %s missing" % mark.hex()
        assert code.find(mark, i + 4) < 0, "placeholder %s not unique" % mark.hex()
        code[i:i + 4] = target.to_bytes(4, "big")
    return bytes(code) + VERB_COUNTS + DLY_COUNTS


def emit(addr):
    """No cave bytes (the linked source supplies them); only the dispatch
    repoint."""
    pokes = ((DISPATCH_CC, STOCK_CC.to_bytes(4, "big"), addr.to_bytes(4, "big")),)
    return b"", pokes


MODULE = Module(
    name="ccpage2",
    key="CC PAGE 2",
    kind=Kind.CF_PATCH,
    doc="MIDI CC 62-67 drive the FX2 engine's page-2 slots 6-11; CC 68-73 the FX1 station's.",
    cf_patches=(CavePatch(
        label="CC->FX2/FX1 page-2 cave + dispatch repoint",
        cave_addr=None,                 # floats in the ColdFire free region
        pinned=b"",                     # the linked source is the bytes
        source="modules/ccpage2/cc_page2.s",
        cpu="5407",
        reference=legacy_bytes,         # checked at whatever address it floats to
        # Where other CCs go: stock's handler, or Octakit's when the
        # SCENES KITS bridge overrides it (the oracle is then skipped).
        # CC_MODEDEF2 / CC_MODEDEF1: a stock `rts` unless MODE DEFAULTS is in
        # the image, whose unit exports them (the oracle is set aside then).
        defsyms=(("CC_NEXT", STOCK_CC), ("CC_MODEDEF2", STOCK_RTS), ("CC_MODEDEF1", STOCK_RTS)),
        emit=emit,
        report_note=" (CC 62-67 reach FX2 page 2, CC 68-73 FX1 page 2)",
    ),),
)
