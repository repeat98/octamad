"""octapitch-vintageverb -- the OCTAPITCH base (REPITCH, PREVIEW VOL, FORCE
FILENAME BPM) plus Vintage Verb replacing DARK REV.

Vintage Verb owns the core-private FX2 buffer region (Claims.owns_fx2_buffers),
so it cannot share an image with a stock effect that takes an instance buffer
through the host's allocator: FLANGER, CHORUS, SPATIALIZER, COMB FILTER,
PLATE REV and SPRING REV (tools/remix/stock.py's buffer=True effects) --
the ledger refuses that combination. Those six are left out here, alongside
DARK REV itself; FILTER, EQUALIZER, DJ EQ, PHASER, COMPRESSOR, LO-FI and
DELAY carry no buffer claim and stay. Vintage Verb itself is unflashed
(gated locally only, no hardware pass yet) -- see modules/vintageverb/README.md.
"""

from remix.schema import Remix

REMIX = Remix(
    name="octapitch-vintageverb",
    doc="the OCTAPITCH base (REPITCH, PREVIEW VOL, FORCE FILENAME BPM) with "
        "Vintage Verb replacing DARK REV.",
    modules=("REPITCH", "PREVIEW VOL", "FORCE FILENAME BPM", "VINTAGEVERB",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER",
             "COMPRESSOR", "LO-FI", "DELAY"),
    fallback="NONE",
)
