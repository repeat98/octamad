"""bamsep26 -- the rig: the bus, three stations, the stock delay.

FX2 rows: BusVerb (hosted on one of tracks 5-8), BusDelay (tracks 1-4),
SEND (the fallback: one AUX knob), stock DELAY (ColdFire DMA, costs the DSP
nothing). FX1 rows: NONE + the three stations, each on the id of the stock
effect it replaces (Spectrum = FILTER 0x04, Character = LO-FI 0x1c,
Modulation = CHORUS 0x12) and FX1-only; a station named on FX2 runs dry.
Each station defaults to a bit-exact passthrough, so a saved part that
chose the stock effect still plays.

The bus is one aux: SEND -> BusDelay -> BusVerb, each engine's wet printed
on the track that hosts it (20 Sep 2026; until then a return on T8 through
Character). TEMPO SYNC makes BusDelay's TIME read divisions; CC
PAGE 2 puts CC 62-67 on the host engine's page-2 slots; MODE DEFAULTS
re-defaults a mode's knobs when MODE is turned on the panel.

Every other stock effect is harvested: 13 effects, 6,158 words per payload
in one run; a saved part naming one gets silence (the null stub).

On Sam's unit. Worst core priced 3,657 cycles (four Characters beside the
reverb, `make cycles`, 20 Sep 2026) against 3,120 usable -- inside the
counter's error margin, settled by the hardware burn sweep.
"""

from remix.schema import Remix

REMIX = Remix(
    name="bamsep26",
    doc="The rig: bus (BusVerb + BusDelay) + three stations + the stock delay.",
    modules=("REVERB SERVER", "DELAY SERVER", "SEND", "DELAY",
             "SPECTRUM", "CHARACTER", "MODULATION",
             "TEMPO SYNC", "CC PAGE 2", "MODE DEFAULTS"),
    fallback="SEND",
    fx1=("SPECTRUM", "CHARACTER", "MODULATION"),
)
