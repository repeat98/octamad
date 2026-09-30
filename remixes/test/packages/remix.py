"""Every insert module the loader can carry, beside the stock effects.

Six modules as packages in the stock loader's catalog (build_bus.LOADABLE):
none of their code is resident, each is uploaded into the arena when a Part
selects it, like the stock effects. The four that `replace` a stock effect
take its id and row (FILTER, CHORUS, SPRING REV, DARK REV); the rest of the
stock effects keep theirs.
"""
from remix.schema import Proof, Remix

REMIX = Remix(
    name="packages", family="reference", proof=Proof.RENDER,
    proof_note="verify_module_packages; not on hardware",
    doc="Six modules and the stock effects, all loaded on demand.",
    modules=("SPECTRUM", "MODULATION", "TAPE ECHO", "MINIVERB", "EUCLID", "CF METER",
             "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "SPATIALIZER", "COMB FILTER",
             "COMPRESSOR", "LO-FI", "DELAY", "PLATE REV"),
    fallback="NONE",
)
