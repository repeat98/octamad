"""Analog BD, every stock effect, Tape Echo, Miniverb and Euclid.

The stock loader (added to every image) serves the fourteen stock effects;
Tape Echo, Miniverb and Euclid are packages in its catalog; Analog BD's
engines sit at the top of the effect block. No DSP effect is resident.
"""
from remix.schema import Remix, Proof

_FX1_STOCK = ("FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
              "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI")

REMIX = Remix(
    name="abd-packages", family="mods", proof=Proof.RENDER,
    proof_note="built and package-gated locally; not on the port or hardware",
    doc="Analog BD, all 14 stock effects, Tape Echo, Miniverb and Euclid, every DSP effect loaded on demand.",
    modules=("ANALOG BD", "TAPE ECHO", "MINIVERB", "EUCLID",
             *_FX1_STOCK, "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fx1=("EUCLID", *_FX1_STOCK),
    fallback="NONE",
)
