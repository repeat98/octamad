"""oxide -- the OXIDE tape insert alone, for its gates and for listening.

Absent ids resolve to the firmware's own NONE. OXIDE is written for the
master; until a post-mix insert point exists it runs as an FX1 or FX2
insert on any track.
"""
from remix.schema import Proof, Remix

REMIX = Remix(
    name="oxide",
    family="effects", proof=Proof.PORT, proof_note="verify_oxide: the render is held to its integer twin at 0 LSB",
    doc="The OXIDE tape insert, alone.",
    modules=("OXIDE",),
    fallback="NONE",
)
