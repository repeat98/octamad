"""Minimal eight-instance reverb development image; unflashed."""
from remix.schema import Remix
REMIX = Remix(name="miniverb", doc="Minimal allocator-owned FDN reverb.",
              modules=("MINIVERB",), fallback="NONE")
