# MASTER STRIP

An insert on the summed MAIN, run inline after payload A's mixdown: the master strip of
`docs/proposals/MIXER.md` (step 2, §11). The insert is OXIDE, at its 0 dB points (IN 48,
OUT 80). The main out, the recorder and USB audio (stock's pack) and the phones' MAIN
share all hear it; the metronome click, which stock adds to MAIN after the pack, is
added after the insert and is not processed.

## How it runs

- **At boot** (a `jsr` over P:0x40, the first instruction after the upload) it calls
  OXIDE's init on the strip's own instance block and writes the strip's parameter record,
  then replays the displaced instruction. The unit's RAM is not zeroed, so nothing here
  trusts what X held before.
- **Head, every frame** (a `jsr` over P:0x2d5, MIXER SEAM's site): gathers MAIN's 16 dry
  pairs, runs OXIDE on sample 0 only and puts it back in the TX ring. Stock's tail (the
  pack, the click, the gain ramp, the cue mix into the phones) then writes sample 0 about
  as early as stock does: the output DMA reads it about half a sample after the mixdown.
- **Tail, every frame** (a `jsr` over P:0x35d, after the cue mix): samples 1..15 in order,
  one call each. The click is the ring's MAIN minus the dry sample; MAIN becomes OXIDE's
  output plus the click; the phones are recomputed with the cue mix's own gains; then
  stock's pack routine runs again on the processed samples, so the recorder and USB audio
  get them.
- OXIDE is reached through the stock dispatch tables by its FX id, as a track slot reaches
  it. The strip needs OXIDE in the remix (`requires`); OXIDE also stays in the FX
  chooser.
- Every register the bodies write that stock might read afterwards is saved and put back.
- Its state, buffers and record are at X:0x7c00..0x7cff (`boot.asm` has the map).

Why split: the first version ran all 16 samples at P:0x2d5, and under the port the phones'
first sample of every frame went out two frames stale, because the pass held stock's cue
mix back past the DMA (MIXER.md §11).

## Not yet

- The parameters are fixed. The ColdFire record per strip (MIXER.md §7, decision 6) is
  the next step, and with it a MIXER page.
- One insert only; the strip's own gain and the second insert are not built.
- `make cycles` does not price site bodies. Under the port the strip runs about 268
  instructions per sample (head 333 and tail 3,948 per 16-sample frame), against OXIDE's
  158 in a track slot.
- Where MAIN plus the click clips, the tail's click (a difference of clipped values) is not
  stock's.
- Nothing is measured on a unit, including the DMA margin.

## Proof

`tools/verify/verify_strip.py`, under the ColdFire port against the same image with all
three sites' stock words put back, on two fixtures (the input tones on MAIN; the tones
plus the metronome on MAIN): core 0's TX0 MAIN pair equals `modules/oxide/design.py`'s
`fixed()` of the reference's MAIN (plus the click), sample for sample; the phones differ
only by MAIN's change at the cue mix's gain, first sample of each frame included; the
recorder/USB pack's MAIN half is `fixed()` of the reference's and its CUE half is
identical; every other TX0 word and host-port block is identical. The fixtures' MAIN
carries the input tones: under the port no track reaches the mixdown yet
(`docs/remixer/EMU.md`).
