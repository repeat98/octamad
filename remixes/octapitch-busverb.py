"""Hardware-test image: the OCTAPITCH base (REPITCH, PREVIEW VOL, FORCE
FILENAME BPM) with BusVerb (+ BusDelay, SEND, tempo sync) in place of
Vintage Verb -- the A/B partner to ``octapitch-vintageverb``.

BusVerb and BusDelay each own the per-core FX2 buffer region (one on
payload A, tracks 5-8; one on payload B, tracks 1-4), so together they take
both cores' buffer memory -- same exclusion as ``bus``/``bamsep26``: no
FLANGER, CHORUS, SPATIALIZER, COMB FILTER, PLATE REV, SPRING REV or DARK
REV here. FILTER, EQUALIZER, DJ EQ, PHASER, COMPRESSOR, LO-FI and DELAY
carry no buffer claim and stay, as in ``octapitch-vintageverb``. Needs
``make bus`` (XBUS=1 SPEC=1), not ``make check`` alone -- BusVerb is a
bus_role=SERVER module.
"""

from remix.schema import Remix

REMIX = Remix(
    name="octapitch-busverb",
    doc="the OCTAPITCH base (REPITCH, PREVIEW VOL, FORCE FILENAME BPM) with "
        "BusVerb + BusDelay replacing Vintage Verb.",
    modules=("REPITCH", "PREVIEW VOL", "FORCE FILENAME BPM",
             "REVERB SERVER", "DELAY SERVER", "SEND", "TEMPO SYNC",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER",
             "COMPRESSOR", "LO-FI", "DELAY"),
    fallback="SEND",
)
