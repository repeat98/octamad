# `dspsite` — the stock mixdown and its seam, through DSP sites

The remix `tools/verify/verify_dspsite.py` builds, and the one a new mixer grows
from (`docs/proposals/MIXER.md`). Nothing audible changes.

## What is in it

- **MIXDOWN COPY** — payload A's summing mixdown (P:0x238..0x2d4) run from a copy the
  build places in the harvested region, reached by a `jmp` over two stock words.
  `modules/mixdown/README.md`.
- **MIXER SEAM** — an empty hook on P:0x2d5, the address the copy exits into: a `jsr` to a
  body that replays the displaced instruction and returns. `modules/seam/README.md`.
- The stock effects except the three reverbs, whose words are the region the bodies go in.

## Status

Under the ColdFire port the pair is byte-identical to the same image without the two
jumps (core 0's TX0 and every host-port block, with MAIN audible). Not flashed; nothing
here is measured on a unit.
