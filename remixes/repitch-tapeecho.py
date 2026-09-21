"""Hardware-test image: the OCTAPITCH base (REPITCH, PREVIEW VOL, FORCE
FILENAME BPM) plus Tape Echo.

Tape Echo runs on the ColdFire using the stock per-track delay rings. Keep
the stock DELAY available alongside it for A/B listening and fallback.
"""

from remix.schema import Remix

REMIX = Remix(
    name="repitch-tapeecho",
    doc="the OCTAPITCH base with Tape Echo in FX2.",
    modules=("REPITCH", "PREVIEW VOL", "FORCE FILENAME BPM", "DELAY", "TAPE ECHO"),
    fallback="NONE",
)
