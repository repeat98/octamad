"""cfmeter -- octatrick-usb plus CF METER and CF METER IDLE: the ColdFire's
spare time with SYNTH MACHINE voices running, read out over USB audio from
track 8.
DARK REV is off the chooser: its words hold the readout insert."""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="cfmeter",
    family="probes", proof=Proof.PORT, proof_note="the readout chain under the port",
    doc="octatrick-usb + CF METER on T8's FX2: ColdFire idle time and frame-interrupt duration, over USB.",
    modules=("DIRECT JUMP", "SCALE QUANTIZER", "SYNTH MACHINE",
             "USB MIDI", "USB AUDIO EXTENDED", "CF METER", "CF METER IDLE",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV"),
    fallback="NONE",
)
