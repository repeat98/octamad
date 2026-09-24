# USB MIDI

Class-compliant USB-MIDI in and out on the Octatrack's own USB port,
mirroring the DIN ports. markandrus's work ([octemu](https://github.com/markandrus/octemu),
`custom/usb-midi.py` + `custom/coldfire/usb-midi.s` at `6a9ff68`, MIT),
carried onto octabam's DRAM platform.

## What it is

OS 1.40C ships a complete USB-MIDI transmit encoder (`0x4001d204`: raw
bytes to 4-byte event packets, running status, SysEx spans) and the EP2
primitives, reached by nothing, and no receive decoder. The module:

- grows the configuration descriptors to MSC + AudioControl + MIDIStreaming
  with EP2 bulk in/out (`descriptors.py`, generated per remix into the
  `usbmidi_cfg` unit; `cfg_len` is the length the two clamp shims read);
- brings EP2 up at SET_CONFIGURATION (512-byte packets at high speed),
  answers CLEAR_FEATURE(ENDPOINT_HALT) for it;
- dispatches EP2 completions from the USB ISR: IN completion frees the
  transmit slot and drains the queue, OUT completion runs the receive
  decoder, which feeds `midi_rx_enqueue` (`0x40092bbc`), the byte path DIN
  MIDI uses, then re-primes;
- mirrors both senders into the encoder: `midi_send` (channel messages)
  and the priority byte sender (clock, transport). Messages are queued in
  a 256-byte accumulator behind one transfer; a message that would
  overflow it is counted in `usbmidi_tx_drops`, never sent corrupt.

Seven detours, four descriptor-pointer rewrites, no pokes. The `usbmidi`
unit is his file verbatim, and the build proves it: every build re-links
it at his zone address `0x400d24f0` and compares with the 1,124-byte blob
his `usb-midi.py` produced from our stock bytes (`Linked.reference`, the
port-is-a-proof rule). The clamps are a second unit (`clamp.s`, his
usb-audio.s shims reading `cfg_len`).

## Measured (25 Sep 2026, under the ColdFire port; nothing on hardware)

`make check REMIX=usb`, `verify_usb`:

- enumerates at high speed as Elektron 1935:0002, three interfaces, 124-byte
  configuration; INQUIRY and TEST UNIT READY still answered by the stock
  mass-storage stack;
- two channel messages sent to EP2 OUT → six bytes into the firmware's
  MIDI receive FIFO (`midi_rx_fifo_head` `0x46100b80`, six writes from
  `midi_rx_enqueue`);
- the firmware's own `midi_send` on a note-on → one event packet `09 90 3c 64`
  on EP2 IN.

His build from the same stock bytes, tested first under the port with his
own patch scripts, behaved the same (the ISR shim ran nine times, the
decoder once, the same six FIFO writes).

Not measured: timing on the unit (bulk transfers have no schedule; clock
jitter over USB against DIN), a CC flood against the 256-byte queue,
DISK MODE entered with a MIDI session open, Windows.

## Ground

| what | where |
|---|---|
| code + queues | DRAM unit `usbmidi` (1,124 B, his bytes) + `usbmidi_clamp` in the platform reserve |
| descriptors | DRAM unit `usbmidi_cfg` (4 × 124 B, or 4 × 250 B with USB AUDIO) |
| hooks | `0x4001d9ca` `0x4001daec` `0x4001e606` `0x40010bc8` `0x400108b0` `0x4001d858` `0x4001d896` |
| pointer rewrites | the responder's four `pea` operands `0x4001d882` `0x4001d88a` `0x4001d8c0` `0x4001d8c8` |
| firmware memory it uses | the firmware's own EP2 dQHs, dTDs and buffers (`0x4ec94900..`, `0x4ecc8000`, `0x4ecc9000`) |
