"""dspsite -- the stock chooser plus the two DSP-site modules, both identities.

Every stock effect except the three reverbs (their words are the region the
bodies are placed in, as in every remix that carries code of its own),
MIXDOWN COPY (the stock mixdown run from a placed copy) and MIXER SEAM (an
empty hook on the address the copy exits into). Nothing audible changes. The
remix the DSP-site gate builds (tools/verify/verify_dspsite.py) and the one a
new mixer grows from (docs/proposals/MIXER.md). Not flashed.
"""

from remix.schema import Remix

REMIX = Remix(
    name="dspsite",
    doc="The stock effects (no reverbs) and the stock mixdown and seam through DSP sites.",
    modules=("MIXDOWN COPY", "MIXER SEAM", "FILTER", "EQUALIZER", "DJ EQ", "PHASER",
             "FLANGER", "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY"),
    fallback="NONE",
)
