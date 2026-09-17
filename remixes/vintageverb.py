"""vintageverb -- the DARK REV replacement, alone.

Vintage Verb owns the core-private FX2 buffer region Y:0x4000-0x9851, so it
is one instance per core and cannot share an image with a server (BusVerb's
tank), Nimbus, or the seven stock effects that allocate a buffer.
Unflashed; for local A/B against stock DARK REV (which is what it
replaces), render it from here and stock DARK REV via
`tools/remix/audition.py dark ...` with this module's directory renamed to
start with `_` (the registry's own skip convention -- see the module
README for why that matters).
"""

from remix.schema import Remix

REMIX = Remix(
    name="vintageverb",
    doc="Vintage Verb, the DARK REV replacement, alone.",
    modules=("VINTAGEVERB",),
    fallback="NONE",
)
