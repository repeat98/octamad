"""gloamverb -- the DARK REV replacement, alone.

Gloam owns the core-private FX2 buffer region Y:0x4000-0x87FF, so it is one
instance per core and cannot share an image with a server (BusVerb's tank)
or with Nimbus, or with the seven stock effects that allocate a buffer.
Unflashed; for local A/B against stock DARK REV (which is what it replaces),
render it from here and stock DARK REV from a remix that still lists
"DARK REV" (e.g. `restock`).
"""

from remix.schema import Remix

REMIX = Remix(
    name="gloamverb",
    doc="Gloam, the DARK REV replacement, alone.",
    modules=("GLOAMVERB",),
    fallback="NONE",
)
