"""MASTER STRIP -- an insert on the summed MAIN, inline after the mixdown.

The master strip of docs/proposals/MIXER.md, step 2: OXIDE on MAIN, run in
place in the TX ring at the seam (payload A, P:0x2d5) where both mixdown
paths have finished and nothing has read the buses yet. The recorder, USB
audio and the phones' MAIN share all hear it; the metronome click, added
after the pack, is added after the insert. It grows from MIXER SEAM's empty hook, which it replaces
(the ledger refuses the two together).

Three DSP sites. `boot` runs once per DSP boot (P:0x40, the first
instruction after the upload) and initialises the insert's instance block and
the strip's parameter record, so the strip never starts from the unit's
unzeroed RAM. `head` (P:0x2d5) runs the insert on MAIN's sample 0 only, so
stock's tail (the pack, the click, the cue mix) writes sample 0 as early as
stock does: the output DMA reads it about half a sample after the mixdown.
`tail` (P:0x35d, after the cue mix) runs samples 1..15 in order and redoes
what stock's tail made from them: MAIN plus the click, the phones' cue mix,
the MAIN pack. All reach the insert through the stock dispatch tables by its
FX id, as a track slot does.

The parameters are FIXED at OXIDE's 0 dB points (IN 48, OUT 80) until the
ColdFire ships a record per strip (MIXER.md section 7, decision 6). Its
state and record live at X:0x7c00..0x7cff (boot.asm has the map).

The replaced words are pinned by hash, read from the user's own image at
build time; the manifest holds no Elektron byte.
"""

from remix.schema import Category, DspSite, Gate, Kind, Module, Proof

MODULE = Module(
    name="strip",
    key="MASTER STRIP",
    kind=Kind.DSP_SITE,
    category=Category.BUS,
    author="repeat98", author_url="https://github.com/repeat98",
    proof=Proof.PORT,
    proof_note="`verify_strip`: under the port, with and without the metronome, the main out, "
               "the phones' MAIN share and the recorder/USB pack are OXIDE's model of the stock "
               "MAIN at 0 LSB, every other TX0 word and host-port block stock's (29 Sep 2026); "
               "not flashed",
    doc="OXIDE on the summed MAIN, inline after the mixdown (payload A, P:0x2d5 and "
        "P:0x35d): the master strip, parameters fixed at 0 dB.",
    requires=("OXIDE",),
    dsp_sites=(
        DspSite(
            label="boot",
            site=0x40,
            words=2,                       # `move #>$8000,b`, replayed last by the body
            stock_sha256="f801758605f2b681e59a7501b204ad6f708a1c3183e1ec6b9ae8f59549dda1ad",
            kind="jsr",
            payloads=frozenset({"A"}),
            asm="modules/strip/boot.asm",
        ),
        DspSite(
            label="head",
            site=0x2d5,
            words=2,                       # `move x:>$206,r0`, replayed last by the body
            stock_sha256="ec029b6c32da3745b6cfe7e781e84050214454fcaa3f9e5db0f52f1bbe77e971",
            kind="jsr",
            payloads=frozenset({"A"}),
            asm="modules/strip/head.asm",
        ),
        DspSite(
            label="tail",
            site=0x35d,
            words=2,                       # `move x:>$207,r0`, replayed last by the body
            stock_sha256="a0b5ecb722245d0453b9f2a04d507ade10f0a5ca2555f24760312d803f24712b",
            kind="jsr",
            payloads=frozenset({"A"}),
            asm="modules/strip/tail.asm",
        ),
    ),
    gates=(Gate("tools/verify/verify_strip.py"),),
)
