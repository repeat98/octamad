"""usb-full -- stock effects plus USB MIDI and USB AUDIO FULL, nothing else.

usb-lean with the sixteen track channels only (no MAIN/CUE): the layout
image 69 ran. For testing USB AUDIO FULL on a unit that runs stock
projects. Local test remix (27 Sep 2026).
"""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="usb-full",
    family="mods", proof=Proof.PORT, proof_note="",
    doc="stock + USB MIDI + USB AUDIO FULL (16 ch: the tracks).",
    modules=("USB MIDI", "USB AUDIO FULL",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
