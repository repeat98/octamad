"""Analog BD with every stock effect kept: the DSP loader serves them all."""
from remix.schema import Remix, Proof
REMIX=Remix(name="analog-bd-dynload", family="mods", proof=Proof.PORT,
    proof_note="port qualification in progress; not yet on hardware",
    doc="Analog BD on all eight tracks and all 14 stock effects, each DSP effect loaded on demand.",
    modules=("ANALOG BD", "DSP DYNLOAD STOCK", "DSP DYNLOAD STOCK B",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS", "SPATIALIZER",
             "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE")
