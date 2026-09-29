"""midi-scenes -- MIDI SCENES alone.

One ColdFire module, no DSP, no menu row: the reference minimal build of
the DRAM platform with a real mod on it. Unflashed on its own (ok-ms, which
carries it, has run on hardware).
"""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="midi-scenes",
    family="mods", proof=Proof.CHECK, proof_note="on hardware inside `ok-ms`",
    doc="Reference minimal build: the MIDI SCENES ColdFire patch, alone.",
    modules=("MIDI SCENES",),
    fallback="NONE",
)
