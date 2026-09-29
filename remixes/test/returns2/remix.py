"""returns2 -- scratch: the master strip beside both servers (the reverb on core 0, the delay on core 1)."""
from remix.schema import Proof, Remix

REMIX = Remix(
    name="returns2",
    family="reference", proof=Proof.CHECK, proof_note="",
    doc="Scratch: strip + both servers + SEND (MIXER.md section 20).",
    modules=("MIXDOWN COPY", "MASTER STRIP", "OXIDE", "REVERB SERVER", "DELAY SERVER", "SEND",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "LO-FI"),
    fx1=("FILTER", "EQUALIZER", "DJ EQ", "PHASER", "LO-FI"),
    fallback="SEND",
)
