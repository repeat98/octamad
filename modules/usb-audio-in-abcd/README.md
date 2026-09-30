# `usb-audio-in-abcd` — USB AUDIO IN ABCD

Four channels from the host into inputs A-D in place of the jacks
(host channels 1-4 = A, B, C, D). High speed only, 24-bit,
192-byte packets every 250 µs.

The same ColdFire unit as [USB AUDIO IN AB](../usb-audio-in-ab/README.md)
(`usbaudio_in.s`, `IN_CHANNELS = 4`), the same hook sites, the same
counters on vendor request `0x56`; only the DSP inject differs
(`rx_inject_abcd.asm`: all four slots, 49 words; the four-channel form Bryan T's usbin-test ran on his MKII, build 16, 27 Sep 2026, there poked into SPATIALIZER's words). The AB README has the design, the
measurements and the open items; `verify_usb_in` checks this variant's
slots (coded on its own, zero on the others) under the port.

Requires USB MIDI, USB CROSSBAR and a 250 µs USB AUDIO OUT layout. One IN
module per remix (shared detour sites).

## Gates

- `tools/verify/verify_usb_in.py` (the manifest's gate, image stage).
