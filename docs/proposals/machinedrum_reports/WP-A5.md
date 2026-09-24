# WP-A5 — OT-side stereo mix

24 September 2026, branch `machinedrum`. In progress; no hardware run.

`md_glue.asm` now accumulates each of the sixteen voice blocks into separate
left and right outputs. The per-part Q23 gains are at `X:0x36340–0x3634f`
(left) and `X:0x36350–0x3635f` (right). Both default to `0x200000` (1/4),
preserving the earlier centered proof mix. This uses the existing 32-sample
stereo mix buffer. The DSP change adds eight glue words; it does not load
the original MD mixer DSP or its track effects.

The isolated Octemu build against DSP pin `8ccdd843` ran 700 frames with
the centered gains: the MD voice reference matched 348/348 periods and
694/694 non-silent post-FX2 readback blocks matched the glue output. For an
independent-channel check, a temporary build set every right gain to zero.
Across 698 sampled glue calls, left output had 11,119 nonzero samples and
right output had zero. The normal centered gain was restored and the image
rebuilt. No temporary right-mute change is committed.

The mailbox parser now accepts a gain packet with destination `0xc00–0xc1f`,
maps it to the X gain tables, and keeps the fixed trigger active if no voice
record has arrived. The focused `--gain-probe` gate sent a right-zero update
through the ColdFire host-transfer chain: the DSP right gain became zero,
11,119 left samples were nonzero, all sampled right samples were zero, and
348/348 voice periods remained bit-identical. A second packet crossed the
`0xc1f` gain boundary and was refused (BAD=1) without stopping playback.
The full c01_16 record stream
also passed after this parser change: 4,194/4,194 transport blocks sent,
19,663/19,663 record words accepted, and 33,513/33,513 voice blocks
bit-identical.

The kit producer must still translate each part's VOL/PAN to those gain
words and send live updates. The full sixteen-part stereo mix must be priced
at OT addresses and checked against a reference mix before this packet is
done.
