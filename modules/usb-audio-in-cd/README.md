# `usb-audio-in-cd` — USB AUDIO IN CD

A stereo pair from the host into inputs C/D in place of the jacks
(host channel 1 = C, 2 = D; A/B stay on the jacks). High speed only, 24-bit,
96-byte packets every 250 µs.

The same ColdFire unit as [USB AUDIO IN AB](../usb-audio-in-ab/README.md)
(`usbaudio_in.s`, `IN_CHANNELS = 2`), the same hook sites, the same
counters on vendor request `0x56`; only the DSP inject differs
(`rx_inject_cd.asm`: slots 0/1 of the RX block instead of 2/3). The AB README has the design, the
measurements and the open items; `verify_usb_in` checks this variant's
slots (coded on its own, zero on the others) under the port.

Requires USB MIDI, USB CROSSBAR and a 250 µs USB AUDIO OUT layout. One IN
module per remix (shared detour sites).

## Gates

- `tools/verify/verify_usb_in.py` (the manifest's gate, image stage).
