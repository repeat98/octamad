"""usb -- the rig plus USB MIDI on the OT's own USB port.

The rig's selection (bottleservice without USB AUDIO and Octakit) with USB MIDI (markandrus/octemu's completion of the
firmware's dormant USB-MIDI half) on the DRAM platform: the unit appears
to a host as a composite mass-storage + MIDI class device, and the MIDI
function mirrors the DIN ports. Nothing else changes.
remixes/usb/README.md has the build and use steps.
"""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="usb",
    family="rig", proof=Proof.CHECK, proof_note="",
    doc="The rig + USB MIDI (class-compliant, mirrors DIN).",
    modules=("REVERB SERVER", "DELAY SERVER", "SEND",
             "SPECTRUM", "CHARACTER", "MODULATION",
             "TEMPO SYNC", "CC MAP", "MODE DEFAULTS", "RIG HOSTS",
             "USB MIDI"),
    fallback="SEND",
    hidden=("REVERB SERVER", "DELAY SERVER"),
    named=("REVERB SERVER", "DELAY SERVER"),
    locked=("REVERB SERVER", "DELAY SERVER"),
    fx1=("SPECTRUM", "CHARACTER", "MODULATION"),
)
