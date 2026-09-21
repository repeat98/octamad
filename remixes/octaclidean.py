"""OCTACLIDEAN: Octapitch2 + Euclid + CPU Tape Echo.

This is the flashable OCTACLIDEAN selection with the optimized Tape Echo
occupying Spring Reverb's former id. DJ EQ, Spring Reverb and Plate Reverb
remain omitted; Dark Reverb and the other OCTACLIDEAN stock effects remain.
"""

from remix.schema import Remix


REMIX = Remix(
    name="octaclidean",
    doc="Octapitch2 plus Euclid and CPU Tape Echo; DJ EQ, Spring Reverb and Plate Reverb omitted.",
    modules=("REPITCH", "PREVIEW VOL", "FORCE FILENAME BPM", "EUCLID",
             "TAPE ECHO", "FILTER", "EQUALIZER", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR",
             "LO-FI", "DELAY", "DARK REV"),
    fx1=("EUCLID", "FILTER", "EQUALIZER", "PHASER", "FLANGER", "CHORUS",
         "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI"),
    fallback="NONE",
)
