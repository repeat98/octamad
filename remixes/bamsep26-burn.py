"""bamsep26-burn -- the rig plus CF BURN, for measuring the stress project.

bamsep26's modules unchanged, plus a CF BURN FX2 row. Build with
`make burn REMIX=bamsep26-burn` (or `make burn-image ... BUILD=N`) and one
image carries both meters:

- DSP: SEND's page-2 BURN (24 cycles/sample/step) on the core of the track
  it is turned on: T2-T4 core 1 (payload B), T6-T8 core 0 (payload A).
- ColdFire: CF BURN's BURN/FINE on the track whose FX2 is CF BURN (T8 in the
  stress procedure, replacing that track's SEND; core 0 keeps SENDs on T6/T7).

The image differs from bamsep26 by the SendBurn splice, one chooser row and
the CF BURN hook (~75 instructions per frame with the knobs at zero).
"""
from remix.schema import Remix

REMIX = Remix(
    name="bamsep26-burn",
    doc="The rig plus CF BURN: measure spare DSP (SEND BURN) and ColdFire (CF BURN) on the stress project.",
    modules=("REVERB SERVER", "DELAY SERVER", "SEND",
             "SPECTRUM", "CHARACTER", "MODULATION",
             "TEMPO SYNC", "CC PAGE 2", "MODE DEFAULTS", "RIG HOSTS",
             "CF BURN"),
    fallback="SEND",
    hidden=("REVERB SERVER", "DELAY SERVER"),
    named=("REVERB SERVER", "DELAY SERVER"),
    locked=("REVERB SERVER", "DELAY SERVER"),
    fx1=("SPECTRUM", "CHARACTER", "MODULATION"),
)
