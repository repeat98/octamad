# `pmap-probe` — the 16K program map, tested on the unit

The image for [PMAP PROBE](../../../modules/pmap-probe/README.md): both DSP cores switch to the 16K
program map at boot, test it, and play the verdict on MAIN (L core 0, R core 1; 882 Hz pass,
110 Hz fail). Stock FX1/FX2 effects beside it; the three reverbs give up their words and are not
selectable, so no buffer reaches past the new Y ceiling. Not a user image.

## Status

`verify_pmap_probe` passes under the port, where the answer is pass by construction. Not flashed.
