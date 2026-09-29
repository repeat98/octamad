"""strip -- the master strip on MAIN: OXIDE inline after the mixdown.

MIXDOWN COPY (the stock mixdown from a placed copy, which exits into the
strip's site), MASTER STRIP and the insert it runs, OXIDE, beside the stock
effects without the three reverbs (their words are the region the bodies go
in). The remix tools/verify/verify_strip.py, verify_mixerpages.py and verify_stripstore.py build
(docs/proposals/MIXER.md, step 2). Not flashed.
"""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="strip",
    family="reference", proof=Proof.PORT,
    proof_note="`verify_strip`: the main out, the phones and the recorder/USB pack carry OXIDE's model of "
               "the stock MAIN under the port, with and without the metronome and from dirty RAM; the "
               "ColdFire's slot record reaches MAIN on a frame boundary; `verify_mixerpages`: the MIXER "
               "window's MASTER page draws, pages and edits the record as locked, and a slot's SETUP "
               "chooses its effect with stock EFFECT 2 SETUP's knob grid (29 Sep 2026); `verify_stripstore`: "
               "the Part keeps the strip: a poked window is adopted, an edit lands in the window, its "
               "SRAM twin and the stock dirty marks (29 Sep 2026)",
    doc="Two insert slots on the summed MAIN, inline after the mixdown: the master strip, step 2.",
    modules=("MIXDOWN COPY", "MASTER STRIP", "OXIDE", "FILTER", "EQUALIZER", "DJ EQ",
             "PHASER", "FLANGER", "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR",
             "LO-FI", "DELAY"),
    fallback="NONE",
)
