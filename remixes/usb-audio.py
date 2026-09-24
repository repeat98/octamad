"""usb-audio -- the rig plus USB MIDI and sixteen channels of USB audio.

`usb` with USB AUDIO (markandrus/octemu's UAC2 proof of concept) on the
DRAM platform: at USB high speed the unit is also a 16-channel 44.1 kHz
16-bit audio input, track N's post-FX pre-fader L/R on channels 2N-1/2N;
at full speed the stereo sum of the tracks. Nothing on hardware yet.
"""

from remix.schema import Remix

REMIX = Remix(
    name="usb-audio",
    doc="usb + USB AUDIO: sixteen channels of the tracks over USB (UAC2).",
    modules=("REVERB SERVER", "DELAY SERVER", "SEND",
             "SPECTRUM", "CHARACTER", "MODULATION",
             "TEMPO SYNC", "CC PAGE 2", "MODE DEFAULTS", "RIG HOSTS",
             "USB MIDI", "USB AUDIO"),
    fallback="SEND",
    hidden=("REVERB SERVER", "DELAY SERVER"),
    named=("REVERB SERVER", "DELAY SERVER"),
    locked=("REVERB SERVER", "DELAY SERVER"),
    fx1=("SPECTRUM", "CHARACTER", "MODULATION"),
)
