"""scenes -- the MIDI SCENES family, no effects of ours.

MIDI SCENES + the LO-FI AMF fix + CC MAP. No octabam DSP; every stock
effect stays and the chooser is stock's. Unflashed.
"""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="scenes",
    family="mods", proof=Proof.PORT, proof_note="",
    doc="All the firmware mods of the MIDI SCENES family, no effects: scenes "
        "over MIDI, the LO-FI AMF fix, CC to page 2.",
    modules=("MIDI SCENES", "LOFI AMF FIX", "CC MAP"),
    fallback="NONE",
)
