# `mixer` — the extended mixer

The image `docs/proposals/MIXER.md` builds toward: a master channel with two inserts, two stereo
return channels you send T1–T8 and the inputs to (and each return to itself and to the other, and
to the cue out for hardware feedback chains), each return running an effect chosen from its core's
pool, all of it set on the MIXER window's pages and by MIDI CC and kept in the Part.

## What is in it

- **MASTER STRIP** (`modules/strip`) — two inserts on MAIN; RETURN A and RETURN B strips (rows: the
  effect, sends T1–T6, sends T7…RET B, output level and CUE send); the Part's cells; MIDI CC 74–107.
- **OXIDE** — an insert and a return effect. **REVERB SERVER** (core 0) is RETURN B's effect,
  **DELAY SERVER** (core 1) RETURN A's; **SEND** the bus client that keeps stock projects sounding.
- **MIXDOWN COPY** — the stock mixdown from a placed copy, the site the strip grows from.
- Stock FILTER, EQUALIZER, DJ EQ, PHASER and LO-FI on FX1; CHORUS, FLANGER and SPATIALIZER give up
  their words (COMPRESSOR and COMB FILTER stay stock).

## Status

Measured under the ColdFire port only: `verify_strip`, `verify_aux`, `verify_return`,
`verify_mixerpages`, `verify_retstore` and `verify_mixcc` (MIXER.md sections 11–22). Not on a unit.
Not shown: a track's audio into the sends (no track reaches the mixdown under the port), the reverb
and delay as returns beyond "run and warm" unless `verify_return --long` says so, the cores' real timing.
