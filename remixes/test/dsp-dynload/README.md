# DSP dynamic loading test remix

Real ColdFire allocation, DMA upload and DSP dispatch binding for stock EQ,
Phaser, Compressor and Character. Existing stock controls remain unchanged.
Both cores retain static implementations as rollback/fallback storage; their
original code is not yet reclaimed. Emulator only, not a flash candidate.

See [the runtime module](../../../modules/dsp-dynload/README.md) for the
precise admission boundary and tests. This remix is isolated from Analog BD.
