"""octakit -- Em's Octakit alone.

One module, no menu rows, no DSP. Her runtime, writes and append rebuild
byte-identical to the identities her recipe pins (the build prints each).
The image is not identical to hers: octabam writes its own FX2 chooser and
DSP null stubs. tools/verify/verify_octakit.py is the pure statement
(stock + her writes + her append == her output.os).
"""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="octakit",
    family="mods", proof=Proof.CHECK, proof_note="on hardware inside `ok-ms`",
    doc="Em's Octakit alone -- must reproduce her own build byte for byte.",
    modules=("OCTAKIT",),
    fallback="NONE",
)
