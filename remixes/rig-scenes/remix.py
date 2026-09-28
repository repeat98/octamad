"""rig-scenes -- the rig + MIDI SCENES.

No LO-FI AMF fix: the Character station replaces LO-FI, so its code is
harvested. Unflashed.
"""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="rig-scenes",
    family="rig", proof=Proof.CHECK, proof_note="",
    doc="The rig + MIDI SCENES.",
    modules=("REVERB SERVER", "DELAY SERVER", "SEND", "DELAY",
             "SPECTRUM", "CHARACTER", "MODULATION",
             "TEMPO SYNC", "CC MAP",
             "MIDI SCENES"),
    fallback="SEND",
    fx1=("SPECTRUM", "CHARACTER", "MODULATION"),
)
