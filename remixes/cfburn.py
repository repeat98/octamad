"""cfburn -- stock 1.40C plus the ColdFire burn knob: the base firmware's spare CPU.

Every stock effect but DARK REV keeps its row; CF BURN adds one FX2 row and
takes DARK REV's DSP words for its few-word passthrough (a stock payload has
no free words; MODULES.md "Keeping stock effects in the chooser"). A project
under test must not use DARK REV. Select CF BURN on a track's FX2 and sweep
BURN, then FINE, until the audio breaks (modules/cfburn/README.md). Without
a CF BURN track the hook costs 75 instructions per frame and changes
nothing else (verify_cfburn.py).
"""
from remix.schema import Remix

REMIX = Remix(
    name="cfburn",
    doc="Stock effects plus CF BURN, a knob that measures spare ColdFire CPU.",
    modules=("CF BURN", "FILTER", "EQUALIZER", "DJ EQ", "PHASER",
             "FLANGER", "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR",
             "LO-FI", "DELAY", "PLATE REV", "SPRING REV"),
    fallback="NONE",
)
