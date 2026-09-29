"""returns -- scratch: the master strip, the reverb server and SEND, stock effects trimmed."""
from remix.schema import Proof, Remix

REMIX = Remix(
    name="returns",
    family="reference", proof=Proof.CHECK, proof_note="",
    doc="Scratch: strip + reverb server + SEND (MIXER.md section 19).",
    modules=("MIXDOWN COPY", "MASTER STRIP", "OXIDE", "REVERB SERVER", "SEND",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER",
             "LO-FI", "DELAY"),
    fx1=("FILTER", "EQUALIZER", "DJ EQ", "PHASER", "LO-FI"),
    fallback="SEND",
)
