# MIXDOWN COPY

Payload A's summing mixdown (P:0x238..0x2d4) run from a copy placed in the
harvested region, reached by a `jmp` over the two words at P:0x238. No
audible change, by construction and by measurement: the first user of a
DSP site (`schema.DspSite`), and the identity a new mixer is compared with
(`docs/proposals/MIXER.md`).

- **What it places.** 157 words (the stock span, three operands fixed) and
  overwrites two stock words with `jmp >body`. The build report prints
  `DSP SITE P:0x00238+2 -> jmp P:0x0...`.
- **What is pinned.** The two replaced words and the whole span by SHA-256,
  read from the user's own image at build time; the manifest holds no
  Elektron byte.
- **What is measured.** `tools/verify/verify_dspsite.py` (built as the `dspsite` remix): the built words
  are the stock words plus exactly the declared fixes, the copy's
  disassembly differs from stock's in the address operands only, and under
  the port (with `OT_PROJECT`) core 0's TX0 and every host-port block match
  the same image with the jump removed. `docs/proposals/MIXER.md` §9 has
  the figures (839 vs 838 instructions per frame, about 52 a sample).
- **What it does not show.** Track audio through the copy on a real
  sample-playing project, and anything on the unit (`docs/proposals/MIXER.md`).
