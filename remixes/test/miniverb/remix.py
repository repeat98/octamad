"""Minimal eight-instance reverb development image; unflashed."""
from remix.schema import Proof, Remix
REMIX = Remix(family="effects", proof=Proof.RENDER, proof_note="`make verify-miniverb`", name="miniverb", doc="Minimal allocator-owned FDN reverb.",
              modules=("MINIVERB",), fallback="NONE")
