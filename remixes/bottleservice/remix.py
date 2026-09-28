"""bottleservice -- the rig plus USB MIDI, USB AUDIO MASTER and Octakit.

the rig's selection (the bus, three stations, hosts, TEMPO SYNC, CC MAP, CC FEEDBACK, MODE
DEFAULTS, TEMPO BUS, SCENES P2; `bamsep26` until 27 Sep 2026) with USB MIDI and
USB AUDIO MASTER (two channels: track 8, the master track, post-FX
pre-fader) on the DRAM platform and Em's Octakit (as `rig-kits`, with
SCENES KITS bridging CC MAP and Octakit on the CC dispatch). On Sam's MKII
since image 88 (27 Sep 2026).
"""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="bottleservice",
    family="rig", proof=Proof.HARDWARE, proof_note="Sam's MKII, image 88, 27 Sep 2026",
    doc="The rig + USB MIDI + USB AUDIO MASTER (T8 over USB) + Octakit.",
    modules=("REVERB SERVER", "DELAY SERVER", "SEND",
             "SPECTRUM", "CHARACTER", "MODULATION",
             "TEMPO SYNC", "CC MAP", "CC FEEDBACK", "MODE DEFAULTS", "RIG HOSTS", "TEMPO BUS",
             "USB MIDI", "USB AUDIO MASTER",
             "OCTAKIT", "SCENES KITS",
             "SCENES P2", "SCENES P2 KITS"),
    fallback="SEND",
    hidden=("REVERB SERVER", "DELAY SERVER"),
    host_slots=(("DELAY SERVER", 2), ("REVERB SERVER", 2)),
    locked=("REVERB SERVER", "DELAY SERVER"),
    fx1=("SPECTRUM", "CHARACTER", "MODULATION"),
)
