# PMAP PROBE

A hardware probe, one flash: **does the DSP56720 run the 16K program map on the unit?**
It is the question behind DSP dynamic loading's memory plan (`modules/dsp-dynload/README.md`):
the default map gives each core 8K program words; the 16K map (OMR MS = 1, MSW1:MSW0 = 11)
doubles that at the cost of Y above `0x9FFF` (`docs/firmware/CHIP.md` section 3). Stock never
switches it, and nothing here has run it.

## What it does

Both cores, at boot (`P:0x40`, before anything touches Y): set the map, write and read back all
8,192 new program words (`0x2000..0x3FFF`) with two patterns, copy a routine to `P:0x3F00` and call
it there, and keep a verdict. The boot's Y zeroing is shortened to stop at `0x9FFF`, the new
ceiling. Core 1 forwards its verdict to core 0 every frame (`P:0x333`); core 0 adds both to MAIN
after the mixdown (`P:0x2d5`).

## On the unit: what you hear

Flash `make image REMIX=pmap-probe BUILD=<n>`, load any project, listen to MAIN (a tone plays
with nothing on the tracks):

| MAIN L (core 0) / MAIN R (core 1) | means |
|---|---|
| 882 Hz square, -24 dBFS | pass: the 8K new program words hold both patterns and run code |
| 110 Hz square | fail: the map switched but the new words do not hold (or the code there did not run) |
| no tone on that side, the rest of the audio normal | that core's verdict never arrived (R only: core 1's report path) |
| no audio at all, or the unit hangs at boot | the switch itself wedged a core |

Play a pattern with FX1/FX2 effects as usual: every selectable effect's buffer fits under the new
Y ceiling (the reverbs are not in this image). Stock audio sounding normal alongside the tones is
the second answer: the stock program runs unchanged under the switched map.

## Proof

`tools/verify/verify_pmap_probe.py` (port): the hooks are planted and the boot's OMR words are the
three the source names; both cores report pass (0 errors, the routine ran from `P:0x3F00`) and core
0 reads core 1's verdict; every TX0 slot but MAIN and the phones is identical to the same image with
the three sites' stock words back, the phones differ only where MAIN does; MAIN L and R carry the
882 Hz square at exactly ±0x080000 (30 Sep 2026, the user's project).

**The port cannot answer the question**: its DSP emulator does not model the memory switch (the OMR
MS handling is commented out in the vendored `dsp.cpp`), so both cores pass by construction. The fail
tone is untested (reachable only when the test fails). Every instruction form has a precedent on a
unit (stock, or BusVerb's and Spectrum's P reads) except the three OMR moves, which are the question.
