# `usb-crossbar` — USB CROSSBAR

The USB controller bursts over the crossbar and is served first on the
SDRAM and SRAM-backdoor slaves. Written once at the stock USB controller
init (`0x4001e030`) and left on.

| register | stock | this module | meaning |
|---|---|---|---|
| SCM BCR `0xfc040024` | `0` (reset; nothing sets it) | `0x3ff` | USB bursts to and from every slave |
| XBS PRS2 / PRS4 | `0x65403210` (USB level 6 of 7) | `0x60504321` (USB level 0) | master priority on SDRAM (slave 2) and the SRAM backdoor (slave 4) |
| XBS CRS2 / CRS4 | `0x110` (round robin) | `0x10` (fixed, park on last) | arbitration mode |

## Measured

The boot-time write has run under the port only (the port does not model SCM or XBS registers).

## On the unit

Bryan T's MKII, usbin-test builds 12-14, 26 Sep 2026. Same busy project, one minute per row unless stated:

| setting | bad OUT packets |
|---|---|
| stock | 1,189 / min |
| BCR 0x3ff | 5-11 / min |
| BCR 0x3ff + USB first (this module's values) | 0 in 10 min, no audible or UI change |

Ruled out on the way: the cable and port, USBMODE.SDIS, RXPBURST 1-8 (16
exceeds the FIFO), packet buffers in SRAM alone, a four-channel IN stream
alone, bit errors.

In those builds the registers were written when the host opened the
stream, from the frame-transfer interrupt, and never restored; DISK MODE
and a further session ran under them (build 16, 27 Sep 2026). This module
writes the same values at boot instead, so the setting does not depend on
which module opens a stream.

## Open

- CAPTURE and card writes under this priority on a MKI (nordseele's review
  of PR #468, 27 Sep 2026).
- The stock DELAY on eight tracks with Flex playback (SDRAM-heavy DMA)
  under USB-first arbitration.

## Why

In device mode the controller has one 16-byte RX FIFO (MCF54455RM 10.4.3),
about 270 ns of slack at 480 Mbit/s. With BCR 0 it is emptied one beat at a
time; under a busy project it overflowed near the end of an isochronous OUT
packet and the controller flagged a transaction error (CRC), 2 to 12 bytes
short. Stock's own USB traffic is bulk and retried, so stock never showed
it.

## Ground

| what | where |
|---|---|
| code | DRAM unit `usbcrossbar`, 10 instructions |
| hook | `0x4001e030`, the USB controller init's `movel #0x08000000,%d0`, replayed |
