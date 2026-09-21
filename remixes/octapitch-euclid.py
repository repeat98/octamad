"""Octapitch2's improvements plus Euclid in both FX slots.

DJ EQ, Spring Reverb and Plate Reverb are omitted by request. All other
stock effects, including Chorus and Dark Reverb, remain available.
The repitch remix was rebuilt byte-for-byte against OCTAPITCH2 before
composing this variant: REPITCH, PREVIEW VOL and FORCE FILENAME BPM.
"""
from remix.schema import Remix

REMIX = Remix(
    name="octapitch-euclid",
    doc="Octapitch2 plus Euclid; all stock effects except DJ EQ, Spring Reverb and Plate Reverb.",
    modules=("REPITCH", "PREVIEW VOL", "FORCE FILENAME BPM", "EUCLID",
             "FILTER", "EQUALIZER", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "DARK REV"),
    fx1=("EUCLID", "FILTER", "EQUALIZER", "PHASER", "FLANGER", "CHORUS",
         "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI"),
    fallback="NONE",
)
