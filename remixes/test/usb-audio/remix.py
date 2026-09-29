"""usb-audio -- the rig plus USB MIDI and twenty channels of USB audio.

The rig (the TEMPO window, host pages DEL/REV) with USB MIDI and USB
AUDIO (markandrus/octemu's UAC2 proof of concept) on the DRAM platform: at USB high speed the unit is also a 20-channel 44.1 kHz
24-bit audio input, track N's post-FX pre-fader L/R on channels 2N-1/2N,
MAIN L/R on 17/18 and CUE L/R on 19/20;
at full speed the stereo sum of the tracks. The 16-bit stream was on
hardware as image 64 and the 24-bit one as image 69 (25 Sep 2026).
remixes/usb/README.md has the build and use steps.
"""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="usb-audio",
    family="rig", proof=Proof.HARDWARE, proof_note="Sam's MKII, image 64, 25 Sep 2026",
    doc="usb + USB AUDIO: the tracks, MAIN and CUE over USB (UAC2, 20 channels).",
    modules=("REVERB SERVER", "DELAY SERVER", "SEND",
             "SPECTRUM", "CHARACTER", "MODULATION",
             "TEMPO SYNC", "CC MAP", "CC FEEDBACK", "MODE DEFAULTS", "RIG HOSTS", "TEMPO BUS",
             "USB MIDI", "USB AUDIO OUT TRACKS MAIN CUE"),
    fallback="SEND",
    hidden=("REVERB SERVER", "DELAY SERVER"),
    host_slots=(("DELAY SERVER", 2), ("REVERB SERVER", 2)),
    locked=("REVERB SERVER", "DELAY SERVER"),
    fx1=("SPECTRUM", "CHARACTER", "MODULATION"),
)
