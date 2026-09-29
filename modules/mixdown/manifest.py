"""MIXDOWN COPY -- the stock mixdown, run from a copy the build places.

The first user of schema.DspSite and the reference every later mixer is
measured against: payload A's summing mixdown (P:0x238..0x2d4, 157 words,
ten stereo sources into the CUE and MAIN buses) is copied word for word into
the harvested region and a `jmp` at P:0x238 reaches it. The copy exits back
into stock at P:0x2d5, the seam the effect and master work will hook.

It changes nothing audible, and that is the point: under the port the main
out and every host-port block are byte-identical to the image without the
jump (tools/verify/verify_dspsite.py, remix `dspsite`). It costs 157 words of the region and
one long jump.

Three operands name an address and are fixed for the move; the span and the
two words at the site are pinned by hash, so nothing of Elektron's is stored
here (the hashes were taken from OS 1.40C's payload A).
"""

from remix.schema import Category, DspSite, Gate, Kind, Module, Proof, SiteFix

MODULE = Module(
    name="mixdown",
    key="MIXDOWN COPY",
    kind=Kind.DSP_SITE,
    category=Category.REFERENCE,
    author="repeat98", author_url="https://github.com/repeat98",
    proof=Proof.PORT,
    proof_note="`verify_dspsite`: byte-identical to the image without the jump under the port (29 Sep 2026); not flashed",
    doc="The stock mixdown (payload A, P:0x238..0x2d4) run from a placed copy: "
        "the identity a new mixer is measured against.",
    dsp_sites=(
        DspSite(
            label="mixdown",
            site=0x238,
            words=2,                       # `move x:>$205,r0`, the copy's first instruction
            stock_sha256="b4e3834a7b693146bce6c765ac8573c9e8c13ebe08360997b7cb18a11c34ff11",
            kind="jmp",
            payloads=frozenset({"A"}),     # payload B has no mixdown; its P:0x238 is other code
            copy=(0x238, 0x2d5),
            copy_sha256="c9c70ac654cac4fb13b8d5680b344ec89ca22d6c906d43c586082c118b531928",
            fixes=(
                SiteFix(0x25c, "loop_end"),                  # do #16,... the plain path's sample loop
                SiteFix(0x29d, "loop_end"),                  # do #16,... the MASTER TRACK path's
                SiteFix(0x291, "bra_to_jmp", target=0x2d5),  # the plain path's exit into stock
            ),
        ),
    ),
    gates=(Gate("tools/verify/verify_dspsite.py"),),
)
