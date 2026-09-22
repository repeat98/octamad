"""Stock effects plus the four-voice render-path prototype."""

from remix.schema import Remix

REMIX = Remix(
    name="polyphony-proto",
    doc="stock effects with four untimestretched render voices per audio track.",
    modules=("POLYPHONY PROTO", "FILTER", "EQUALIZER", "DJ EQ", "PHASER",
             "FLANGER", "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR",
             "LO-FI", "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
