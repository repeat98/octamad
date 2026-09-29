"""mixer -- the extended mixer: a master strip with two inserts, two return channels, sends.

MASTER STRIP (two insert slots on the summed MAIN, the RETURN A and RETURN B strips, the sends
and the MIXER pages, the Part's cells and MIDI CC 74..107), MIXDOWN COPY (the stock mixdown it
grows from), OXIDE (the insert and a return effect), the two bus servers (the reverb on core 0
is RETURN B's effect, the delay on core 1 is RETURN A's) and SEND. FX1 is cut to five stock
effects so CHORUS, FLANGER and SPATIALIZER give up their words; COMPRESSOR and COMB FILTER stay
stock. docs/proposals/MIXER.md sections 11-22 say what each part is and what was measured.

Not flashed. Tracks are not hosts: a project whose FX2 slots are BusVerb or BusDelay hosts would
run the server twice (the role lock makes the second a dry pass); the sends are the MIXER's.
"""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="mixer",
    family="reference", proof=Proof.PORT,
    proof_note="the strip, RET A / RET B (0 LSB at every hop with OXIDE as the effect, the reverb runs and warms), "
               "the RETURN pages, the Part's cells and MIDI CC under the port (29 Sep 2026); not flashed",
    doc="The extended mixer: master inserts, RETURN A on the delay (core 1) and RETURN B on the reverb "
        "(core 0), sends per source, pages, Part storage and MIDI CC.",
    modules=("MIXDOWN COPY", "MASTER STRIP", "OXIDE", "REVERB SERVER", "DELAY SERVER", "SEND",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "LO-FI"),
    fx1=("FILTER", "EQUALIZER", "DJ EQ", "PHASER", "LO-FI"),
    fallback="SEND",
)
