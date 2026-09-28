"""The initial Machinedrum machine remix envelope.

This keeps stock inserts and DELAY in the chooser for unaffected tracks,
omits BusVerb/BusDelay/SEND, and gives payload B's effect code (T1-T4's FX,
core 1) to the native Machinedrum. The MD DSP id is placed but hidden from
the FX2 chooser; machine type 6 selects it in the frame builder.
"""

from remix.schema import Remix


REMIX = Remix(
    name="machinedrum",
    doc=("Machinedrum machine on T1-T4, hidden DSP dispatch, stock inserts "
         "on the unaffected tracks."),
    modules=(
        "MACHINEDRUM",
        "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
        "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
    ),
    hidden=("MACHINEDRUM",),
    fallback="NONE",
)
