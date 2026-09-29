# DSP dynamic loading test remix

Real ColdFire allocation, DMA upload and DSP dispatch binding for stock EQ,
Phaser, Compressor and Character. Existing stock controls remain unchanged.
Both cores retain static implementations as rollback/fallback storage; their
original code is not yet reclaimed. An unbound managed id runs a dry copy of
stock's null stub (never its original) once the first managed code has loaded.

Where it has run: the port (`make check REMIX=dsp-dynload`, ten image gates).
A first hardware test image, `DSP_Dynload_T1` (unit shows `DYNLOAD1`), was
prepared on 29 Sep 2026 and has not run on a unit yet. It keeps every static
original, so a failure costs a dry slot or a transport error, not a missing
effect. Do not combine it with USB IN: both own the frame DMA hook.

See [the runtime module](../../../modules/dsp-dynload/README.md) for the
precise admission boundary and tests. This remix is isolated from Analog BD.
