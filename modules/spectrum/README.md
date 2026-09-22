# SPECTRUM

A filter pedal on stock FILTER's id 0x04. FX1 only: an FX2 instance runs as
a dry pass (`Claims(fx1_only=True)`, `verify_spectrum.py`); the FX2 chooser
hides the row.

| page 1 | FREQ ⌐RES · ENV · LDP ⌐LSP · WDTH |
|---|---|
| page 2 | MODE (LADR LP BP ISO VOWL) · — · — · — · — · — |

- **LADR** — the linear zero-delay Moog transistor ladder (audiojs/filter
  moogLadder, MIT), 24 dB/oct; RES 127 is the edge of self-oscillation,
  bounded there.
- **LP / BP** — a driven Oberheim SEM zero-delay SVF (Zavalishin's
  trapezoidal form, audiojs/filter oberheim, MIT); the cutoff ramps per
  sample across the block.
- **ISO** — an isolator (Airwindows Capacitor2; `capacitor2_ref.py` is the
  float reference). In ISO FREQ is LOW and RES is COLR, the dielectric colour.
- **VOWL** — a three-formant bank (constant-peak-gain resonators) morphed
  across A E I O U by FREQ; RES (SHRP) narrows the bands. Formants are
  Peterson & Barney (1952) male means; bandwidths 90 / 110 / 170 Hz.

FREQ is exponential, 60 Hz → 15 kHz, an equal step per detent (a 33-word
P table interpolated per block). ENV (a block-peak follower, instant attack,
LSP = release) and LDP (an LFO, LSP = speed ~0.08–9 Hz) both move the
cutoff. WDTH is mid/side width on the output. TAME (the filters' state
saturation, 14 Sep 2026) is gone since 15 Sep 2026 -- Sam: "tame should be
gone"; the removal is bit-identical to TAME 0 and frees the two `div`-fed
per-block words and six 28-word calls per channel pair.

Defaults are a bit-exact passthrough (FREQ 127, RES 0, ENV 64, LDP 0): the
engine detects that block and copies nothing, because every part that chose
FILTER runs this on FX1. A part's stored bytes are stock FILTER's until
`ot_project.py stamp-defaults` writes ours.

Every mpy is `mpy x0,y1`, the audited-signed form; every clip is the store
limiter.

## Measured

- `tools/verify/verify_spectrum.py`: defaults bit-exact on a full-scale
  ramp; LP slope, HP/BP at DC → 0, VOWL A vs I distinct, every knob at both
  extremes renders; an FX2 instance is a bit-exact dry pass.
- `tools/verify/verify_spectrum_ident.py ref/check`: 26 hashes across every
  MODE and the extremes, for any rewrite to hold bit-identical.
- `verify_dirtystate` (in `make verify`): init zeroes every persistent slot
  the loop reads. Before it did, filter B's frozen HP poles held a stale
  value and put up to a full-scale DC on a station's output, which surfaced
  on hardware as the master compressor collapsing the right channel.
- Cost: 1,040 words; 290 cycles/sample (`make check`, 20 Sep 2026; 954 /
  369 before TAME came and went).
- `verify_menu`, `verify_replaces`, `verify_labels` pass on the rig.

On Sam's unit since flash 4; the LADR voicing (PR #254) since image 21.

## Open

- A parallel-move relayout of the sample loop (coefficients contiguous in
  X, state in Y, walked by r3/r4) would roughly halve the loop; the identity
  gate above is the check. No consumer for the cycles yet.
