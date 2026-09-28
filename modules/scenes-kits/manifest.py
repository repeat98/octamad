"""SCENES KITS -- the bridge that lets CC MAP and Octakit share the MIDI CC
dispatch entry (0x400d64a0).

Her recipe installs her handler there; CC MAP repoints the entry to its
cave. With the bridge, the cave keeps the entry and its fall-through
(CC_NEXT) becomes her handler, which falls through to stock's: CCs 62-73
ours, then hers, then stock's. Declared as an Override: the build skips her
recipe write at the site and defines CC_NEXT as the target it carried.

Measured under the port (docs/remixer/PLACEMENT.md). Not measured: MIDI
CCs through the chained dispatch on hardware.
Part Reload beside her kits is a separate collision with its own bridge,
modules/kits-reload (14 Sep 2026).
"""

from remix.schema import Category, Proof, Kind, Module, Override


MODULE = Module(
    name="scenes-kits",
    key="SCENES KITS",
    kind=Kind.CF_PATCH,
    category=Category.PARTS, author="sambanks", author_url="https://github.com/sambanks",
    proof=Proof.PORT, proof_note="in `kits` and `bottleservice`",
    doc="The bridge that lets CC MAP and Octakit share the CC dispatch "
        "(MIDI SCENES needs no bridging since 1.40MSCN6).",
    overrides=(
        Override(0x400D64A0, "OCTAKIT",
                 write="midi-control-parameter-000-at-400d64a0", defsym="CC_NEXT"),
    ),
)
