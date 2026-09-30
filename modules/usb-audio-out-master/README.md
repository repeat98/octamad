# `usb-audio-out-master` — USB AUDIO OUT MASTER

The unit as a USB audio input (UAC2, 44.1 kHz, 24-bit), two channels:
track 8's L/R, post-FX, pre-fader, on channels 1/2 at both USB speeds.
With MASTER TRACK on, track 8 is the mix through T8's effects, before T8's
LEVEL and MAIN volume. Needs USB MIDI.

[USB AUDIO OUT TRACKS MAIN CUE](../usb-audio-out-tracks-main-cue/README.md)'s source,
`usbaudio.s` (markandrus/octemu, MIT), assembled with `USB_LAYOUT = 2`.
The variant is Sam Banks's (27 Sep 2026):

- **Producer.** Reads T8's two read-back words per frame (the same words
  as OUT TRACKS MAIN CUE's channels 15/16, the same 24-bit format) and writes one
  8-byte slot per frame into a 1,024-frame ring. No other track, no
  MAIN/CUE, no stereo sum.
- **Both speeds send the same ring.** High speed polls every 250 µs
  (bInterval 2) like the other out layouts: 11/12 frames, at most 96 bytes;
  full speed every 1 ms: 44/45 frames, at most 360 bytes. Until 28 Sep 2026
  high speed polled every 1 ms too (360-byte packets, the form on Sam's MKII
  as image 88); the 250 µs cadence is what lets a USB AUDIO IN module take
  this stream as its implicit-feedback source. Not on a unit at 250 µs.
- **Descriptors.** USB MIDI's descriptor unit declares a two-channel input
  with bmChannelConfig front left + front right (`0x3`, the standard stereo
  cluster) in the input terminal and AS_GENERAL, at both speeds; 24-bit
  samples in 4-byte subslots, a fixed 44.1 kHz clock, as OUT TRACKS MAIN CUE.
- It takes the same hook sites as OUT TRACKS MAIN CUE and OUT TRACKS, so a remix carries
  one of the three.

## Measured

Under the port, `verify_usb` with `REMIX=usb-out-master` and `REMIX=bottleservice`
(27 Sep 2026):

- EP `0x83` isochronous, 96 bytes, bInterval 2; AS_GENERAL 2 channels,
  bmChannelConfig `0x3`.
- 88/96-byte packets at high speed, none empty after the first ten;
  every subslot's low byte zero; counters: 0 overruns, 0 underruns.
- Taps: with the read-back arena re-poked before every poll with words that
  name their source, side and frame, channel 1 carries T8 L and channel 2
  T8 R, only those, at high speed and at full speed.

## On the unit

Image 88 (Sam's MKII, 27 Sep 2026) carried the 1 ms high-speed form (above); nothing about the stream was
measured there. The 250 µs form: not flashed.

## Open

- Which channels an iOS app records by default. The descriptor declares a
  plain two-channel front L/R input; an app that takes the first two
  channels gets T8.
- Full speed on a phone: whether an iPhone or its adapter connects at high
  or full speed. Both carry T8.

## Gates

- `verify_usb` (`make check REMIX=usb-out-master`, `REMIX=bottleservice`).

## Per block and per millisecond

Counted from the source, instructions executed (not cycles):

| | OUT TRACKS MAIN CUE | OUT MASTER |
|---|---|---|
| producer, per block (16 frames) | ~2,710 | ~180 |
| read-back words read per block | 320 | 32 |
| packets built per ms (high speed) | 4 | 4 |
| bytes copied into packets per ms | ~3,530 | ~353 |
| packet builder + copy per ms | ~750 | ~250 |

`modules/cfmeter` (CF METER) measures the frame interrupt's duration and
main's idle time on a unit; the port's `--profile` samples every 64
instructions and gives no exact count.
