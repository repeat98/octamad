# Review follow-up, 29 September 2026

Rebased from the reviewed `2fbc9981` onto `2a7082bc` before validation.
The PR is intended for review and merging; the earlier draft wording was stale.

## Fixture independence

The previous UI gate fails with `sample pool opened` after changing its input
fixture to THRU and moving the selected track/bank. The selection had never
landed. Both gates now prepare their own project copy: machine types, routing,
main/cue levels, mute/solo masks, scene mute state, AMP/LFO settings, transport
and trig masks are explicit. The input project is never modified. The panel
gate starts with ordinary FLEX and must select Analog BD through panel events.
It checks the signature before reporting a browser failure. LEFT from the engine
pool returns to the stock machine chooser on ANALOG BD; RIGHT opens the engine
pool again. Both sides use the stock header chevrons. The panel gate also
visits FLEX through the same horizontal navigation.

The reviewer's exact silent-main fixture was unavailable. The adversarial
fixture did not reproduce that original failure, so its cause is not claimed
as located. The new gate reads the actual stereo MAIN pair (ESAI channels 2/3),
after transport starts, instead of accepting any nonzero byte in the complete
capture. Both MAIN channels and T1/T5 post-FX output pass on the prepared copy.

## DSP forms and retired synthesis

The 808's repeated shift is now stock `asl #$10,a,a`; its accumulator loop
uses stock `do a`. The desk harness uses `do n7` directly. Exact-render output
and block-state hashes pass all eight cases (1,835,008 frames). No reference
hash was updated. Combined engine/glue size is 992 words.

The unused ColdFire oscillator/noise/filter implementation, tables and its
800-sample comparison tests are removed. ColdFire retains descriptor defaults,
LPF labels and control transport. All eight tracks now send DSP records; the
native gate exercises both ping buffers and every sample-offset split.

## Loader buffers

`platform_build.preboot_layout` records each actual pre-boot destination and
packed staging extent in `layout.json`, normalizes cached/uncached aliases,
and rejects overlap with the linked runtime, packed runtime, other pre-boot
buffers, or the arena boundary. Five unit tests cover these refusals and the
unchanged no-preboot case. The 24 refhash configurations are bit-identical to
the rebased upstream baseline; all 35 other remix images are identical.

## Source signature audit

The stock source renderer table at `0x400d6434` dispatches STATIC, FLEX and
PICKUP to `0x40004008`, THRU to `0x40004424`, NEIGHBOR to `0x4000466c`, and
the inactive source to `0x400047f0`. All source records begin with four
32-bit header fields; arbitrary audio follows them.

The decisive second signature half is DSP word 2: the **high half of the
ring-start field**, not sample data. FLEX's producer writes its modulo-64
ring position at `0x4000411e`; THRU uses its bounded ring position, and
NEIGHBOR/inactive write zero. Consequently this word cannot be `0x0909`
for a valid stock record. FLEX's first field also packs segment lengths
(`0x40004246`/`0x40004252`), so the old claim that its high half is always
zero was too strong and has been removed. This audit concerns valid stock
source records, not already-corrupted transport memory or future modules
that deliberately adopt a conflicting record format.

## Stock project load and emulator claim

A disposable AB project loaded under pristine 1.40C with DSP enabled. Stock
kept FLEX and `AB\x01`, but clamped the setup values to stock FLEX ranges
(ACCNT/LPF/LOW/HIGH: 1/1/1/3 in the fixture). This is not lossless backward
compatibility; keep a separate project copy for firmware without the module.

On macOS, stock boot and a complete project load/panel script also passed
with the opcode-cache bounds guard removed and out-of-range writes logged.
None occurred. The old crash claim is retracted and the unrelated emulator
change removed. No failing platform/configuration has been reproduced.

## Hardware and eight-track scope

The MK1 report applies to the exact earlier ANALOGBD1 hash in README.md.
It reports successful parameter tweaking without audible glitches, not an
eight-voice/every-effect qualification. The new full-height engine browser
and eight-track admission require fresh hardware testing. CPU.md records the
local eight-voice successes and the all-909/double-DJ-EQ failure explicitly.
