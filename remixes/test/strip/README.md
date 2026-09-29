# `strip` — the master strip on MAIN

The remix `tools/verify/verify_strip.py` builds: step 2 of `docs/proposals/MIXER.md`.

## What is in it

- **MASTER STRIP** — two insert slots on the summed MAIN, inline after the mixdown, their
  effects and knobs sent from a ColdFire model every frame (it starts at OXIDE at 0 dB),
  and a MASTER page in the MIXER window (RIGHT from the stock page) that edits them.
  `modules/strip/README.md`.
- **OXIDE** — the insert the strip runs; it stays in the FX chooser too.
  `modules/oxide/README.md`.
- **MIXDOWN COPY** — the stock mixdown from a placed copy, whose exit lands on the
  strip's site. `modules/mixdown/README.md`.
- The stock effects except the three reverbs, whose words are the region the bodies go in.

## Status

Under the ColdFire port the main out, the phones' MAIN share and the recorder/USB pack
carry OXIDE's model of the stock MAIN, with and without the metronome and from dirty RAM,
and every other output word and host-port block is stock's; edits of the ColdFire's model
mid-run reach MAIN on a frame boundary (`docs/proposals/MIXER.md` §11, §12). The MIXER
window's pages draw and page as locked, their knobs step as stock's and reach the DSP, and
every close leaves nothing registered (§13, `verify_mixerpages`). Not flashed; nothing here
is measured on a unit.
