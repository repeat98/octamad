# `flex-seekbind-ctr` — FLEX SEEK BIND CTR

A ColdFire code cave, no DSP code, paired with
[FLEX SEEK BIND](../flex-seekbind/README.md): on a same-sample FLEX re-bind
the voice's per-bind counter is left alone, so the frame builder does not
re-send the voice to the DSP as new and the read pointer is not reset.

Without it, FLEX SEEK BIND's seek path still bumped the counter and every
pass carried a ±1.5-sample seam at the loop point. The loop click and its
four fixes:
[`recorder-hold`](../recorder-hold/README.md#the-loop-click-what-it-is-and-how-to-test-it).

## On the unit

- On hardware as OCTABAM82/83 (Sam's MKII, 12 Sep 2026), stacked with FLEX
  SEEK BIND and RECORDER SPACING: the seam is gone.

## Open

- This cave alone, or without FLEX SEEK BIND: not measured (it has no
  effect on a bind that takes the stock "different" path).

## Gates

Pinned bytes in `manifest.py`; `seekbind_ctr.s` is the source the build
re-assembles and compares.

## The cave

The counter is `+0x90` in the voice record; the store at `+0x98` is always
replayed. Hook: `0x4000f834` (`addql #1,(144,a2)` / `movel a0,(152,a2)`, 8
bytes, replayed). Reads the same stack verdict FLEX SEEK BIND reads
(`(59,sp)` at this depth).
