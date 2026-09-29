# USB AUDIO OUT TRACKS

The unit as a USB audio input (UAC2, 44.1 kHz, 24-bit), sixteen channels:
track N's L/R on channels 2N−1/2N, post-FX, pre-fader. MAIN and CUE are
left out. Full speed: the stereo sum of the eight tracks. Needs USB MIDI.

[USB AUDIO OUT TRACKS MAIN CUE](../usb-audio-out-tracks-main-cue/README.md)'s source,
`usbaudio.s` (markandrus/octemu, MIT), assembled with `USB_LAYOUT = 1`:
the producer skips the MAIN/CUE reads and writes a 64-byte slot per frame;
packets are 11/12 frames, at most 768 bytes, every 250 µs. Everything else
(the shims, the rate servo, the counters, the descriptors' shape) is that
module's. It takes the same hook sites, so a remix carries one of the three
audio modules.

## Hardware precedent

Image 69 (Sam's MKII, 25 Sep 2026) ran sixteen channels at 24 bits, every
channel its track's tone, 0 underruns / overruns
([USB AUDIO OUT TRACKS MAIN CUE](../usb-audio-out-tracks-main-cue/README.md) "Measured on
hardware"). This build is not that one: it is the current source, which
has since gained MAIN/CUE (#435) and lost dead diagnostic code (#446), with
the MAIN/CUE reads assembled out. It has not run on a unit.

## Measured under the port

`verify_usb` with `REMIX=usb-out-tracks` (27 Sep 2026):

- EP `0x83` isochronous, 768 bytes, bInterval 2; AS_GENERAL 16 channels.
- 704/768-byte packets, none empty after the first ten; every subslot's
  low byte zero; counters: 0 overruns, 0 underruns.
- Taps: with the read-back arena re-poked before every poll with words that
  name their source, side and frame, channels 1–16 carry tracks 1–8 L/R,
  each only its own.
- Full speed: 1 ms packets of 44/45 8-byte frames.

## Per block

The producer runs 16 frames per frame interrupt. Instructions executed per
block at high speed, counted from the source (not cycles):

| module | per frame | per block | read-back words read per block |
|---|---|---|---|
| OUT TRACKS MAIN CUE | 167 | ~2,710 | 320 (256 track + 64 MAIN/CUE) |
| OUT TRACKS | 146 | ~2,370 | 256 |
| OUT MASTER | 10 | ~180 | 32 |

The port's `--profile` samples the PC every 64 instructions and gives no
exact per-block count; cycles on the chip depend on memory timing the port
does not model. `modules/cfmeter` (CF METER) measures the frame
interrupt's duration and main's idle time on a unit.
