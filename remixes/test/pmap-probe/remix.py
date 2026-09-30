"""pmap-probe -- the 16K program map, tested on the unit: PMAP PROBE beside the stock effects.

The three stock reverbs give up their words (the default harvest) and are not
selectable, so no stock FX2 buffer reaches past Y:0x9FFF (the new ceiling) or
the probe's word at the top of core 1's shared half. Not a user image.
"""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="pmap-probe",
    family="probes", proof=Proof.CHECK,
    proof_note="builds; under the port it passes by construction; the unit is the measurement",
    doc="Hardware probe for the DSP's 16K program map (MAIN L core 0, R core 1: 882 Hz pass, 110 Hz fail).",
    modules=("PMAP PROBE", "PMAP PROBE B", "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY"),
    fallback="NONE",
)
