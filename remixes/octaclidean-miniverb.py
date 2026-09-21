"""OCTACLIDEAN6: the OCTACLIDEAN5 selection with Mini Verb replacing Dark.

Keeps Octapitch2, Euclid, CPU Tape Echo and the original FX1 chooser.
The accepted Mini Verb voice occupies DARK REV's FX2 id; DJ EQ, stock
Spring Reverb and stock Plate Reverb remain omitted as in the base.
"""
from remix.schema import Remix

REMIX = Remix(
    name="octaclidean-miniverb",
    doc="OCTACLIDEAN5 plus Mini Verb replacing Dark Reverb.",
    modules=("REPITCH", "PREVIEW VOL", "FORCE FILENAME BPM", "EUCLID",
             "TAPE ECHO", "FILTER", "EQUALIZER", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR",
             "LO-FI", "DELAY", "MINIVERB"),
    fx1=("EUCLID", "FILTER", "EQUALIZER", "PHASER", "FLANGER", "CHORUS",
         "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI"),
    fallback="NONE",
)
