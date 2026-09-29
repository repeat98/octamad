# Tempo sync

Feeds the held MIDI note to BusDelay and draws BusDelay's TIME knob as a
tempo division. Two ColdFire code caves.

**The note cave** hooks the per-frame voice-record writer, replays the
instruction it displaced, and for a track whose FX2 is BusDelay stores the
held MIDI note into the low byte of record halfword 13 (`r6+$1` bits 8-15
on the DSP, under TIME's knob field).

**The formatter cave** draws BusDelay's TIME knob: the division name while
the DSP's sticky snap holds one, milliseconds otherwise.

The tempo itself is stock's: the writer stores tempo24 into halfword 31 of
every track's record (`0x40004d6a`) and BusDelay reads it at `r6+$13`,
deriving samples per MIDI clock on the DSP.

`NOTEMPO=1` installs neither (no note reaches the DSP; TIME draws in
milliseconds). `TEMPOCAVE=replay` installs a cave that only replays the
displaced instructions, isolating the hook mechanism from the store.

## On the unit

Since 24 Aug 2026 as a tempo/period/fader/note publish into
halfwords 18-21; note-only since 15 Sep 2026 (image 24): halfwords 18-20
are the FX1 instance's page 2 and 21 the AMP page 2's first halfword, so
on a delay or reverb host every FX1 effect's page 2 read the tempo bytes
(`docs/remixer/FAILURE_MODES.md`, "An FX1 station's page 2 does not reach
the DSP on a bus host").

## Open

The note cave filters on FX2 id 6, compiled into the pinned bytes. A
module that changes its id must re-assemble and re-pin this cave.

Background: [`docs/firmware/DSP.md`](../../docs/firmware/DSP.md) §6c,
[`docs/firmware/PARAM_PAGES.md`](../../docs/firmware/PARAM_PAGES.md) §7,
[`docs/firmware/MIDI.md`](../../docs/firmware/MIDI.md).
