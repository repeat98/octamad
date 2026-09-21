"""tapeecho -- the Spring Reverb replacement, alone.

Tape Echo runs on the ColdFire in the stock per-track delay rings and owns
no DSP tape buffer. Select it in FX2 where SPRING REV normally appears.
This minimal remix is the CPU engine in isolation; repitch-tapeecho adds
the OCTAPITCH base and the stock DELAY for comparison.
"""

from remix.schema import Remix

REMIX = Remix(
    name="tapeecho",
    doc="Tape Echo replacing Spring Reverb, alone.",
    modules=("TAPE ECHO",),
    fallback="NONE",
)
