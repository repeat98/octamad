"""Octapitch: stock effects, the REPITCH TSTR mode, and sample previews at a
fixed AMP VOL."""

from remix.schema import Remix

REMIX = Remix(
    name="repitch",
    doc="stock effects with variable-speed REPITCH in the TSTR selector; "
        "previews ignore the track's AMP VOL.",
    modules=("REPITCH", "PREVIEW VOL", "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
