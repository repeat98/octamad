"""kits -- the Octakit family, no effects of ours.

Octakit + the LO-FI AMF fix + CC MAP, with SCENES KITS bridging CC MAP
and Octakit at the CC dispatch entry. No octabam DSP. Unflashed.

Octakit migrates Parts into Kits on load: back up projects first.
"""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="kits",
    family="mods", proof=Proof.PORT, proof_note="",
    doc="All the firmware mods of the Octakit family, no effects: 256 Kits, "
        "the LO-FI AMF fix, CC to page 2.",
    modules=("OCTAKIT", "LOFI AMF FIX", "CC MAP", "SCENES KITS"),
    fallback="NONE",
)
