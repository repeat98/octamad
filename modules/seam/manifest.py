"""MIXER SEAM -- a hook on the seam after the stock mixdown, doing nothing.

Payload A's mixdown ends at P:0x2d5, where both mixdown paths (plain and
MASTER TRACK) meet and the block is packed for the recorder and USB audio and
mixed into the cue bus. A master strip belongs exactly there: the summed MAIN
is in the ring and nothing has read it yet (docs/proposals/MIXER.md).

This module is the empty hook: a `jsr` over the two-word `move x:>$206,r0`
to a body that replays that instruction and returns. It is the identity the
strip grows from, and the proof of the asm-body path of schema.DspSite (the
mixdown copy exercises the copy path). It composes with MIXDOWN COPY, whose
copy exits into stock at this very address.

The two replaced words are pinned by hash, read from the user's own image at
build time; the manifest holds no Elektron byte.
"""

from remix.schema import Category, DspSite, Gate, Kind, Module, Proof

MODULE = Module(
    name="seam",
    key="MIXER SEAM",
    kind=Kind.DSP_SITE,
    category=Category.REFERENCE,
    author="repeat98", author_url="https://github.com/repeat98",
    proof=Proof.PORT,
    proof_note="`verify_dspsite`: byte-identical to the image without the jump under the port (29 Sep 2026); not flashed",
    doc="An empty hook on the seam after the stock mixdown (payload A, P:0x2d5): "
        "where a master strip goes.",
    dsp_sites=(
        DspSite(
            label="seam",
            site=0x2d5,
            words=2,                       # `move x:>$206,r0`, replayed by the body
            stock_sha256="ec029b6c32da3745b6cfe7e781e84050214454fcaa3f9e5db0f52f1bbe77e971",
            kind="jsr",
            payloads=frozenset({"A"}),
            asm="modules/seam/seam.asm",
            identity=True,
        ),
    ),
    gates=(Gate("tools/verify/verify_dspsite.py"),),
)
