"""The initial Machinedrum remix envelope.

This is the no-bus skeleton: it keeps the ordinary stock inserts and DELAY,
omits BusVerb/BusDelay/SEND, and gives payload B's effect code (T1-T4's FX,
core 1) to the native Machinedrum donor claim.  The native DSP extraction is
WP-B2.
"""

from remix.schema import Remix


REMIX = Remix(
    name="machinedrum",
    doc=("Machinedrum core-1 skeleton: no bus servers, stock inserts, and "
         "the proposed payload-B native-machine envelope."),
    modules=(
        "MACHINEDRUM",
        "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
        "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
    ),
    fallback="NONE",
)
