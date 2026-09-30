# `flex-seekbind` — FLEX SEEK BIND

A ColdFire code cave, no DSP code: a FLEX re-bind onto the same sample
slot, type and generation takes the bind's same-sample path, so the DSP
seeks the running voice instead of starting a new note.

On a recorder-buffer voice re-trigged every bar, stock treated every bar as
a new note and the DSP re-primed the voice: a chirp, then hash at 140 % of
the signal for about 300 samples. Pairs with
[FLEX SEEK BIND CTR](../flex-seekbind-ctr/README.md): the seek path alone
leaves the voice's per-bind counter incrementing, which the frame builder
reads as a new voice. The loop click and its four fixes:
[`recorder-hold`](../recorder-hold/README.md#the-loop-click-what-it-is-and-how-to-test-it).

## On the unit

- On hardware as OCTABAM81/82/83 (Sam's MKII, 12 Sep 2026), stacked with
  FLEX SEEK BIND CTR and RECORDER SPACING: the bar-boundary chirp is gone
  (the captures: [`recorder-hold`](../recorder-hold/README.md#measured-on-the-unit-and-not)).

## Open

- This cave alone: not measured. The three recorder caves have only been
  tested stacked.

## Gates

Pinned bytes in `manifest.py`; `seekbind.s` is the source the build
re-assembles and compares.

## The cave

The bind routine (`0x4000f450`) decides at its tail whether a re-bind is
the same sample (return 0) or a new one (return `0x100`). It has a
slot/type/generation verdict on the stack (`sp@55`) and then compares the
play position against a settings field (`0x4000f8cc..0x4000f8ea`). On a
recorder-buffer voice re-trigged every bar the verdict holds and the
position compare fails.

The cave is hooked on the verdict test. When the verdict holds it takes the
same-sample continuation with result 1; otherwise it takes the stock
"different" path. The position reset and everything else stay stock.

Hook: `0x4000f8cc` (`tstb (55,sp)` / `beqs 0x4000f8ea`, 6 bytes,
replayed).
