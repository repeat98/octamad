"""dynload-stock -- the stock effects, every DSP effect loaded on demand.

The tester image for DSP dynamic loading: the fourteen stock effects on both
menus, exactly as stock offers them, with no stock DSP effect built into the
image; the loader (DSP DYNLOAD STOCK) uploads each into its arena when a
selection, a Part or a project needs it. Nothing else. It should play and
switch as stock does; what it frees is the program space every other remix
takes from a stock effect.
"""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="dynload-stock", family="mods", proof=Proof.PORT,
    proof_note="port qualification in progress; not yet on hardware",
    doc="The stock effects, each DSP effect loaded on demand: stock behaviour, stock program space freed.",
    modules=("DSP DYNLOAD STOCK", "DSP DYNLOAD STOCK B",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS", "SPATIALIZER",
             "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
