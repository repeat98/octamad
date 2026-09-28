"""usb-master -- stock effects plus USB MIDI and USB AUDIO MASTER, nothing else.

usb-lean with track 8's two channels only (the master track, post-FX
pre-fader). For testing USB AUDIO MASTER on a unit that runs stock
projects. Local test remix (27 Sep 2026).
"""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="usb-master",
    family="mods", proof=Proof.PORT, proof_note="",
    doc="stock + USB MIDI + USB AUDIO MASTER (2 ch: track 8).",
    modules=("USB MIDI", "USB AUDIO MASTER",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
