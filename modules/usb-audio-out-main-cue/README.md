# `usb-audio-out-main-cue` — USB AUDIO OUT MAIN CUE

The unit as a USB audio input (UAC2, 44.1 kHz, 24-bit), four channels:
MAIN L/R on channels 1/2 and CUE L/R on 3/4, the DAC feed itself, at high
speed. Full speed carries MAIN alone. Needs USB MIDI.

[USB AUDIO OUT TRACKS MAIN CUE](../usb-audio-out-tracks-main-cue/README.md)'s source,
`usbaudio.s` (markandrus/octemu, MIT), assembled with `USB_LAYOUT = 3`.
The variant is Bryan T's (27 Sep 2026), from usbin-test's `AUD_IN4`:

- **Producer.** Reads MAIN's and CUE's words straight from `MAIN_CUE_BASE`
  (`0x80005e60`, the same buffer OUT TRACKS MAIN CUE's channels 17-20 read and the
  stock recorder's MAIN/CUE sources read) and writes one 16-byte slot per
  frame into a 1,024-frame ring. `MAIN_CUE_BASE` is not ping-ponged, so there is
  no bank bookkeeping; no track is read and there is no stereo sum.
- **CUE with MASTER TRACK on** is written two blocks later than MAIN, so
  the two stay sample-aligned: the mixdown's master path gives CUE a
  32-sample lead
  ([OUT TRACKS MAIN CUE](../usb-audio-out-tracks-main-cue/README.md#cue-against-main-with-master-track-on)).
- **High speed polls every 250 µs**, as OUT TRACKS MAIN CUE and OUT TRACKS do (not
  OUT MASTER's 1 ms): 11.025 frames × 16 bytes a packet, at most 12 frames =
  192 bytes.
- **Full speed carries MAIN alone**, two channels, 44/45 frames × 8 bytes
  every 1 ms, into the same `aud_sum` ring OUT TRACKS MAIN CUE and OUT TRACKS use for their
  stereo sum (skipped at high speed as theirs is). Every layout sends two
  channels at full speed; MAIN is the natural pair here.
- **Descriptors.** USB MIDI's descriptor unit (`HS_LAYOUT`) declares four
  channels and 192-byte packets at bInterval 2; bmChannelConfig 0 as
  OUT TRACKS MAIN CUE and OUT TRACKS; 24-bit samples in 4-byte subslots, a fixed 44.1 kHz
  clock.
- It takes the same hook sites as OUT TRACKS MAIN CUE, OUT TRACKS and OUT MASTER, so a remix
  carries one of the four.

## Measured

Under the port, `verify_usb` with `REMIX=usb-out-main-cue` (27 Sep 2026), all checks passing:

- EP `0x83` isochronous, 192 bytes, bInterval 2; AS_GENERAL 4 channels.
- Packets of 10-12 frames × 16 bytes at high speed, none empty after the
  first ten; every subslot's low byte zero; the vendor counters read back
  with no overrun.
- Taps: with `MAIN_CUE_BASE` re-poked before every poll with words that name
  their source, side and frame, channels 1-4 carry MAIN L, MAIN R, CUE L,
  CUE R, each only its own source's words.
- Full speed: 352/360-byte packets (44/45 two-channel frames), none empty
  after the first ten.

## On the unit

Build 16, `usb-io` (this layout beside USB AUDIO IN), Bryan T's MKII and
Mac, 27 Sep 2026: macOS lists the four inputs; MAIN L/R and CUE L/R reach
the Mac on channels 1-4; the vendor counters show no underrun while
streaming. At the start of a session the ring's fill was above its band
(884), and the servo had it back inside (632) within a second.
Overruns were counted only when macOS closed the stream (USB AUDIO IN's
README, *Latency*, has the trace).

## Open

- Full speed on a unit.
- What the full-speed packets contain. The gate checks their size only
  (it checks content for OUT MASTER alone, as for OUT TRACKS MAIN CUE and OUT TRACKS), so
  "full speed carries MAIN" is from the source, not a measurement.
- The producer's cost per block. It reads 64 words a block (4 per frame),
  where OUT TRACKS MAIN CUE reads the same 64 plus 256 track words; instructions not
  counted.
- USB AUDIO IN beside OUT TRACKS or OUT TRACKS MAIN CUE's larger packets on one bus.

## Gates

- `verify_usb` (`make check REMIX=usb-out-main-cue`).

## Why it exists

usbin-test (Bryan T, 26 Sep 2026) put the host -> A-D
stream (USB AUDIO IN) beside a MAIN+CUE-only input by forcing the
twenty-channel build down to four channels with an `AUD_IN4` flag: the
producer still made all twenty and the packet builder copied out the last
16 bytes of each slot. This module is that four-channel input as a layout
of its own, so USB AUDIO IN can be paired with it, or with OUT TRACKS or
OUT TRACKS MAIN CUE, independently. Only the four-in/four-out combination has run on
hardware, and there as the slice, not this producer.
