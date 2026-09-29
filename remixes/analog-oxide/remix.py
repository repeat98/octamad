"""Analog BD (808/909) beside the OXIDE tape insert, for listening in octemu.

ANALOG BD's engines occupy SPRING REV's harvested DSP region and the build
refuses anything else placed inside it. OXIDE needs words of its own, so
PLATE REV's code (the 594 words in front of SPRING's) is given up here and
OXIDE is packed there. Everything else of the analog-bassdrum remix is
unchanged.
"""
from remix.schema import Proof, Remix

REMIX = Remix(
    name="analog-oxide",
    family="mods", proof=Proof.CHECK, proof_note="builds and boots under the port; auditioned in octemu only",
    doc="Analog BD 808/909 with the OXIDE tape insert and the stock effects.",
    modules=("ANALOG BD", "OXIDE", "FILTER", "EQUALIZER", "DJ EQ", "PHASER",
             "FLANGER", "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR",
             "LO-FI", "DELAY", "DARK REV"),
    fallback="NONE",
)
