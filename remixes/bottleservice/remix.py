"""bottleservice -- the rig plus USB MIDI, USB audio out (the master track) and in (a stereo pair onto C/D), and Octakit.

the rig's selection (the bus, three stations, hosts, TEMPO SYNC, CC MAP, CC FEEDBACK, MODE
DEFAULTS, TEMPO BUS, SCENES P2; `bamsep26` until 27 Sep 2026) with USB MIDI and
USB AUDIO OUT MASTER (two channels: track 8, the master track, post-FX
pre-fader), USB AUDIO IN CD (the computer's stereo pair onto inputs C/D in
place of the jacks; A/B stay jacks) with USB CROSSBAR, on the DRAM platform,
and Em's Octakit (as `rig-kits`, with
SCENES KITS bridging CC MAP and Octakit on the CC dispatch). On Sam's MKII
since image 88 (27 Sep 2026).
"""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="bottleservice",
    family="rig", proof=Proof.HARDWARE, proof_note="Sam's MKII, image 88, 27 Sep 2026",
    doc="The rig + USB MIDI + USB AUDIO OUT MASTER (T8 to the computer) + USB AUDIO IN CD (the computer onto inputs C/D) + Octakit.",
    modules=("REVERB SERVER", "DELAY SERVER", "SEND",
             "SPECTRUM", "CHARACTER", "MODULATION",
             "TEMPO SYNC", "CC MAP", "CC FEEDBACK", "MODE DEFAULTS", "RIG HOSTS", "TEMPO BUS",
             "USB MIDI", "USB AUDIO OUT MASTER", "USB CROSSBAR", "USB AUDIO IN CD",
             "OCTAKIT", "SCENES KITS",
             "SCENES P2", "SCENES P2 KITS"),
    fallback="SEND",
    hidden=("REVERB SERVER", "DELAY SERVER"),
    host_slots=(("DELAY SERVER", 2), ("REVERB SERVER", 2)),
    locked=("REVERB SERVER", "DELAY SERVER"),
    fx1=("SPECTRUM", "CHARACTER", "MODULATION"),
)
