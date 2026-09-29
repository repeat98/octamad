# USB AUDIO OUT MAIN

MAIN L/R from the unit to the host (UAC2, 44.1 kHz, 24-bit), two channels,
a front left / front right cluster. Needs USB MIDI.

[USB AUDIO OUT TRACKS MAIN CUE](../usb-audio-out-tracks-main-cue/README.md)'s
source, `usbaudio.s` (markandrus/octemu, MIT), assembled with
`USB_LAYOUT = 4`:

- **Producer.** Reads MAIN's words from `MAIN_CUE_BASE` (`0x80005e60`, the
  buffer the stock recorder's MAIN source reads; not ping-ponged, so no bank
  bookkeeping) and writes one 8-byte slot per frame into a 1,024-frame ring.
  Both speeds send that ring (the USB AUDIO OUT MASTER shape): no stereo sum,
  no per-block speed test.
- **High speed polls every 250 µs** (bInterval 2): 11.025 frames × 8 bytes a
  packet, at most 12 frames = 96 bytes. That cadence is what lets USB AUDIO
  IN use this stream as its implicit-feedback source; with USB AUDIO IN AB
  the unit is a two-in, two-out interface (remix `usb-io-main-ab`).
- **Full speed**: 44/45 frames × 8 bytes every 1 ms, at most 360 bytes.
- **Descriptors.** USB MIDI's descriptor unit (`HS_LAYOUT`) declares two
  channels, 96-byte packets at bInterval 2, `bmChannelConfig` front L/R,
  24-bit samples in 4-byte subslots, a fixed 44.1 kHz clock.
- It takes the same hook sites as the other out layouts, so a remix carries
  one of the five.

## Measured under the port

`verify_usb` (`make check REMIX=usb-out-main`): EP 0x83 isochronous, 96
bytes, bInterval 2; AS_GENERAL two channels, front L/R; packets at the
250 µs cadence; the counters after the stream. Not on a unit.

## Ground

| what | where |
|---|---|
| code | DRAM unit `usbaudio` (`USB_LAYOUT = 4`) |
| ring | 1,024 × 8 B, the unit's data |
| source | `MAIN_CUE_BASE` `0x80005e60`, MAIN at +0 |
| hooks | USB AUDIO OUT TRACKS MAIN CUE's six detours |
