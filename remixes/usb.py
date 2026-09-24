"""usb -- the rig plus USB MIDI on the OT's own USB port.

bamsep26's selection with USB MIDI (markandrus/octemu's completion of the
firmware's dormant USB-MIDI half) on the DRAM platform: the unit appears
to a host as a composite mass-storage + MIDI class device, and the MIDI
function mirrors the DIN ports. Nothing else changes.
"""

from remix.schema import Remix

REMIX = Remix(
    name="usb",
    doc="bamsep26 + USB MIDI (class-compliant, mirrors DIN).",
    modules=("REVERB SERVER", "DELAY SERVER", "SEND",
             "SPECTRUM", "CHARACTER", "MODULATION",
             "TEMPO SYNC", "CC PAGE 2", "MODE DEFAULTS", "RIG HOSTS",
             "USB MIDI"),
    fallback="SEND",
    hidden=("REVERB SERVER", "DELAY SERVER"),
    named=("REVERB SERVER", "DELAY SERVER"),
    locked=("REVERB SERVER", "DELAY SERVER"),
    fx1=("SPECTRUM", "CHARACTER", "MODULATION"),
)
