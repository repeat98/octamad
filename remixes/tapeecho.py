"""tapeecho -- the Spring Reverb replacement, alone.

Tape Echo owns the core-private FX2 delay buffer, so this deliberately does
not combine it with BusVerb, BusDelay, Nimbus or Vintage Verb.  Select it in
FX2 where SPRING REV normally appears.
"""

from remix.schema import Remix

REMIX = Remix(
    name="tapeecho",
    doc="Tape Echo replacing Spring Reverb, alone.",
    modules=("TAPE ECHO",),
    fallback="NONE",
)
