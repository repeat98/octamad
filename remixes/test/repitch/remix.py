"""Stock effects plus the REPITCH TSTR firmware modification."""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="repitch",
    family="mods", proof=Proof.HARDWARE, proof_note="repeat98's MKII, 16 Sep 2026 (OCTABAM81)",
    doc="stock effects with variable-speed REPITCH in the TSTR selector.",
    modules=("REPITCH", "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
