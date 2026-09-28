"""Standalone native Analog BD machine with stock track effects."""
from remix.schema import Remix, Proof
REMIX=Remix(name="analog-bassdrum", family="mods", proof=Proof.PORT,
    proof_note="source audio on both cores and machine chooser under the port; not flashed",
    doc="Analog BD source machine, switchable 808/909, stock AMP and FX.",
    modules=("ANALOG BD", "FILTER", "EQUALIZER", "DJ EQ", "PHASER",
             "FLANGER", "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR",
             "LO-FI", "DELAY", "PLATE REV", "DARK REV"),
    fallback="NONE")
