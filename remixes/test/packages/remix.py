"""Every insert module the loader can carry, beside every stock effect.

Six modules as packages in the stock loader's catalog (build_bus.LOADABLE):
none of their code is resident, each is uploaded into the arena when a Part
selects it, like the fourteen stock effects, which all keep their ids and
rows. Spectrum and Modulation are FX1-only stations, so they take an FX1
row and no FX2 row.
"""
from remix.schema import Proof, Remix

_FX1_STOCK = ("FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
              "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI")

REMIX = Remix(
    name="packages", family="reference", proof=Proof.RENDER,
    proof_note="verify_module_packages; not on hardware",
    doc="Six modules and all fourteen stock effects, all loaded on demand.",
    modules=("SPECTRUM", "MODULATION", "TAPE ECHO", "MINIVERB", "EUCLID", "CF METER",
             *_FX1_STOCK, "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fx1=("SPECTRUM", "MODULATION", "EUCLID", *_FX1_STOCK),
    fallback="NONE",
)
