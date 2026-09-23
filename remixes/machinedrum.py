"""The initial Machinedrum remix envelope.

This is the no-bus skeleton: it keeps the ordinary stock inserts and DELAY,
omits BusVerb/BusDelay/SEND, and gives the three reverb spans to the native
Machinedrum payload-A donor claim.  The native DSP extraction is WP-B2.
"""

from remix.schema import Remix


REMIX = Remix(
    name="machinedrum",
    doc=("Machinedrum core-0 skeleton: no bus servers, stock inserts, and "
         "the proposed payload-A native-machine envelope."),
    modules=(
        "MACHINEDRUM",
        "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
        "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
    ),
    fallback="NONE",
)
