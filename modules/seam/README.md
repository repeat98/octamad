# MIXER SEAM

An empty hook on P:0x2d5 of payload A: the point where both mixdown paths
have finished and the MAIN and CUE buses are in the ring, before the
recorder/USB pack and the cue mix. It replays the instruction it displaced
and returns, so it changes nothing; it exists to prove the asm-body half of
a DSP site (`schema.DspSite`, `identity=True`) and to be the place a master
strip goes (`docs/proposals/MIXER.md`).

Held by `tools/verify/verify_dspsite.py` beside MIXDOWN COPY, whose copy
exits into stock at this same address: the two compose, and under the port
the pair is byte-identical to the image without either jump.
