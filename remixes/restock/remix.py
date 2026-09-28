"""restock -- all fourteen stock FX2 effects, nothing placed.

Absent ids resolve to the firmware's own NONE, which costs one chooser row
and no words, so all three reverbs survive. For undoing a remix without
reflashing the stock OS. Unflashed.
"""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="restock",
    family="reference", proof=Proof.CHECK, proof_note="",
    doc="every stock FX2 effect, all fourteen: put my unit back.",
    modules=("FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
