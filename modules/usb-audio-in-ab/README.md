# USB AUDIO IN AB: a stereo feed from the host into inputs A/B

The Mac sends a stereo pair, 24-bit at 44.1 kHz, over UAC2 on EP3 OUT, and
it arrives on the Octatrack's inputs A and B in place of the jacks. Inputs C
and D stay on the jacks. When the stream is closed, A and B are the jacks
again. High speed only.

Bryan T's USB AUDIO OUT (usbin-test, 26 Sep 2026: four channels into A–D,
draft PR #468, then PR #495 as USB AUDIO IN) cut to a stereo pair and moved
onto the build's placed-section path, 28 Sep 2026. The USB endpoint keeps
USB's own host-centric name, EP3 OUT.

## How it works

**Descriptors** (`modules/usb-midi/descriptors.py`, `with_in`):
- AudioStreaming interface 5, alt 0/1, with EP3 OUT: 2 ch × 24-bit in 4-byte
  subslots, front left / front right, 96 B every 250 µs. Iso asynchronous,
  fed by IT `0x13` → OT `0x14` on the one clock.
- EP3 OUT is the only free endpoint (EP1 mass storage, EP2 MIDI, EP3 IN
  audio), so there is none for explicit feedback. EP3 IN is marked as the
  **implicit-feedback** data endpoint (`bmAttributes 0x25`), and the host
  sizes each OUT packet from the IN stream's.
- It needs a 250 µs USB AUDIO layout beside it for that feedback: OUT TRACKS MAIN CUE,
  OUT TRACKS or OUT MAIN CUE. The descriptor unit refuses a remix without one, and one with
  OUT MASTER (a 1 ms stream, untested here).
- The full-speed configurations carry no interface 5: the unit serves the
  stream at high speed only, so a full-speed host is never offered one. One
  clamp (`cfg_len`) covers all four replies: a host asks for a
  configuration's own `wTotalLength`, so the shorter tables' zero pad is
  never requested.

**ColdFire** (`usbaudio_in.s`, a DRAM unit; `IN_CHANNELS` from `remix.inc`, shared with [IN CD](../usb-audio-in-cd/README.md) and [IN ABCD](../usb-audio-in-abcd/README.md)):
- `in_setiface_shim`, a detour after usbaudio's SET_INTERFACE shim:
  interface 5 alt 0 or 1 records the alt setting and ACKs; any other alt
  STALLs. usbaudio.s answers GET_INTERFACE(5) from the same byte
  (`USB_IN` in its `remix.inc`).
- `in_state7_shim`, a detour on the frame-transfer state machine's state 7
  (`0x40004bc0`). It is the one owner of EP3 OUT:
  - brings it up and down;
  - retires completed dTDs into a 1,024-frame ring;
  - self-heals the queue;
  - then runs a **second eDMA transfer** per DSP frame to core 0: 96
    halfwords to `$6320` in the idle bank. Word 0 is 1 while the stream is
    open, then 16 × (A hi, A lo, B hi, B lo), hi = sample[23:8], lo =
    sample[7:0].

  The stock frame-IRQ unmask runs on the second visit, our transfer's
  completion.
- Cushion `IN_TARGET` = 384 frames (8.7 ms).
- The **dTDs and packet buffers are in on-chip SRAM** at `0x80007c00`, and
  the EP0 reply buffer at `0x80007f80`, declared as `Claims.sram`; see
  *SRAM*.
- `in_ctrl_shim`, a detour on the EP0 stall store (`0x4001de6e`), answers
  vendor request `0x56` with the fifteen counters.

**DSP** (`rx_inject_ab.asm`, 33 words on payload A; `rx_inject_cd.asm` writes slots 0/1, `rx_inject_abcd.asm` all four, 49 words):
- Placed by the build in the donor region like any effect, with no dispatch
  entry: P:`0x88`'s `move r2,x:>$204` becomes `jsr >inject`
  (`schema.DspHook`) and the inject replays it. The ledger refuses a second
  section on the site.
- While word 0 is set it writes the pair over slots 2/3 (inputs A/B) of the
  current RX block (`X:$202`); slots 0/1 (C/D) are not touched. Every stock
  reader of the block, the core 0 → core 1 handoff and the read-back the
  recorder takes included, runs after P:`0x88` in the frame, so one inject
  serves both cores and the recorder (`out/dsp/payload_A.asm`).
- Every instruction form has a stock site in payload A, or ran on Bryan T's
  unit in the four-channel inject; the source lists them.

**USB CROSSBAR** is required: without it the controller's 16-byte RX FIFO
loses packet tails under a busy project (`modules/usb-crossbar/README.md`
has the measurement).

## SRAM

`0x80007c00`–`0x80007dff` holds the four dTDs and their 96-byte packet
buffers, `0x80007f80`–`0x80007fbf` the EP0 reply. Evidence that the top
1 KB is free (Bryan T, 26 Sep 2026):
- The stock image's highest static SRAM use is the 768-byte buffer at
  `0x80007574` (`0x40098890`), ending `0x80007874`.
- No module touches anything above `0x80006907`.
- Under the port, nothing touches `0x80007874`–`0x80007fff`: boot, frames
  and USB streaming, and a busy project via `tools/verify/verify_set.py
  --extra "--touch-map 0x80000000,0x8000=…"` plus
  `tools/verify/sram_census.py`.
- RAMBAR1 is `0x80000235`, so the backdoor is on for bus masters.

SRAM is not cached, so no alias is needed. Packet buffers in SDRAM through
the uncached alias (usbaudio's pattern) with USB CROSSBAR on has not been
measured; SRAM alone did not cure the lost tails, the crossbar setting did.

## Counters

Vendor request `0xc0`/`0x56` returns fifteen big-endian longs:
produced, consumed, pkts, lastn, lastfill, underruns, overruns, reprimes,
bad, frames, seconds, minfill, maxfill, err, partial.
`tools/hw/usb_counters.py --in` reads them from a unit; `verify_usb_in`
reads them under the port. `tools/hw/usb_probe.py` reads both rings'
counters through a host session and prints a verdict.

## Verification

- **Under the port:** `tools/verify/verify_usb_in.py`, this module's gate
  (`make check` runs it for any remix that carries it): the host's coded
  samples bit-exact on slots 2/3 of the six completed RX blocks with slots 0/1 zero, in
  consecutive frames, and on the recorder's input ring; the counters over
  `0x56`; word 0 clear and the jacks back after alt 0. EP3 IN's frame size
  comes from the remix's layout, so the gate runs beside OUT MAIN CUE, OUT TRACKS or
  OUT TRACKS MAIN CUE. `verify_usb` checks the six-interface high-speed configuration
  and the five-interface full-speed one. The port does not model SCM or XBS,
  so USB CROSSBAR is measured on a unit only.
- **On hardware:** this stereo form has not been flashed. The four-channel
  form ran on Bryan T's MKII as usbin-test builds 12–16 (26–27 Sep 2026):
  about 5 million packets with `bad`, underruns and overruns 0 after the
  crossbar setting, DISK MODE in and out with the stream back afterwards.
  nordseele's MKI (`OCTABAM94`, the same build) enumerated and lit input A
  from host channel 1, with CoreAudio restarting the IO context hundreds of
  times and playback at about half nominal speed (his review, 27 Sep 2026);
  not reproduced on the MKII. `tools/hw/usb_probe.py` is the instrument:
  its EP3 IN drain rate (`consumed` per second) is the number that
  discriminates.

## Latency, measured on Bryan T's unit (usbin-test build 16, 27 Sep 2026)

Both rings' `lastfill` over the vendor requests (`0x55`, `0x56`), read
once a second:

- **The sum of the two fills is conserved while the streams run**: 1,353 to
  1,360 second by second through a fresh session, about 1,355 in another.
  With implicit feedback the host sends as many frames as it reads, and the
  DSP's frame clock produces into EP3 IN's ring and consumes from this one.
  1,355 frames is about 31 ms, the round trip through the unit before the
  host's own buffers.
- **Where it comes from**: `AUD_TARGET` + `IN_TARGET` (896) plus about 460
  frames EP3 IN gains between the stream starting and macOS polling it
  steadily (INFERRED from two sessions).
- **The split drifts** about 0.5 frames a second (11 ppm, that Mac against
  the unit) from EP3 IN's ring to this one until EP3 IN reaches the bottom
  of its band; this ring plateaued at 969 of 1,024.
- **EP3 IN overruns happen at stream close**, not while running: the host
  stops polling EP3 IN before it sends alt 0. Both rings restart on the
  next open.

So `IN_TARGET` alone does not set the latency. Two levers, both in
`usbaudio.s`:

1. **Anchor usbaudio's consumer at the host's first IN poll** rather than
   at SET_INTERFACE. Done 28 Sep 2026 (`usbaudio_kick`, the `anchor`
   counter over `0x55`; `verify_usb` holds the bench's first poll back 600
   frames and checks the fill lands at 512). Not measured on a unit:
   expected sum of the two `lastfill`s about 896.
2. Lower `AUD_TARGET`, `IN_TARGET` and `AUD_BAND` together, keeping
   `IN_TARGET − AUD_BAND` (this ring's floor) above the jitter the unit
   shows. The OUT ring's own jitter is `minfill`/`maxfill` over `0x55`
   (added with lever 1), unmeasured on a unit; the values follow that
   measurement.

## Open

- This stereo form on a unit: `tools/hw/usb_probe.py` sustained and churn,
  then a host → A/B → recorder take.
- The MKI report above: half-speed playback and CoreAudio restarts, the
  drain rate under `usb_probe.py` on that unit.
- Beside OUT TRACKS or OUT TRACKS MAIN CUE on hardware: before the crossbar setting the
  twenty-channel EP3 IN stream beside EP3 OUT lost packet tails under load;
  the setting cured them with the four-channel pairing and the larger
  pairings have not been run since. `usb-io-tracks-main-cue-ab` pairs it with OUT TRACKS MAIN CUE.
- Packet buffers in SDRAM through the alias with USB CROSSBAR on.
- Latency lever 2 above, after the unit measurement.

## Ground

| what | where |
|---|---|
| code | DRAM unit `usbaudio_in`; DSP section `rx_inject_ab.asm`, payload A's donor region, 33 words |
| hooks | `0x4001dd0a` SET_INTERFACE (after usbaudio's), `0x40004bc0` frame transfer state 7, `0x4001de6e` EP0 stall store; DSP P:`0x88` (`DspHook`) |
| ring | 1,024 × 8 B, the unit's data |
| DMA memory | dTDs `0x80007c00` (128 B), packet buffers `0x80007c80` (384 B), EP0 reply `0x80007f80` (64 B): `Claims.sram` |
| host-port buffer | `in_tx`, 192 B, through the uncached alias (+`0x08000000`) → core 0 X bank +`$320`..+`$380` |
| descriptors | USB MIDI's `usbmidi_cfg` unit, interface 5 in the high-speed configurations |
