# `strip` — the master strip on MAIN

The remix `tools/verify/verify_strip.py` builds: step 2 of `docs/proposals/MIXER.md`.

## What is in it

- **MASTER STRIP** — OXIDE on the summed MAIN, inline after the mixdown, parameters
  fixed at 0 dB. `modules/strip/README.md`.
- **OXIDE** — the insert the strip runs; it stays in the FX chooser too.
  `modules/oxide/README.md`.
- **MIXDOWN COPY** — the stock mixdown from a placed copy, whose exit lands on the
  strip's site. `modules/mixdown/README.md`.
- The stock effects except the three reverbs, whose words are the region the bodies go in.

## Status

Under the ColdFire port the main out, the phones' MAIN share and the recorder/USB pack
carry OXIDE's model of the stock MAIN, with and without the metronome, and every other
output word and host-port block is stock's (`docs/proposals/MIXER.md` §11). Not flashed;
nothing here is measured on a unit.
