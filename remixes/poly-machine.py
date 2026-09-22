"""Stock effects plus the selectable four-voice Poly Machine."""

from remix.schema import Remix

REMIX = Remix(
    name="poly-machine",
    doc="stock effects with an experimental selectable four-voice POLY machine.",
    modules=("POLY MACHINE", "FILTER", "EQUALIZER", "DJ EQ", "PHASER",
             "FLANGER", "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR",
             "LO-FI", "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
