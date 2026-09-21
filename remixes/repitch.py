"""Octapitch: stock effects, the REPITCH TSTR mode, sample previews at a
fixed AMP VOL, and FORCE FILENAME BPM."""

from remix.schema import Remix

REMIX = Remix(
    name="repitch",
    doc="stock effects with variable-speed REPITCH in the TSTR selector; "
        "previews ignore the track's AMP VOL; a PERSONALIZE checkbox "
        "enforces the filename's tempo.",
    modules=("REPITCH", "PREVIEW VOL", "FORCE FILENAME BPM",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
