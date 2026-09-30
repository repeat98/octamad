# `usb-audio-out-tracks-main-cue` — USB AUDIO OUT TRACKS MAIN CUE

The unit as a USB audio input (UAC2, 44.1 kHz, 24-bit), twenty channels.
Needs USB MIDI: the audio function is added to its composite device.

| USB speed | channels | content |
|---|---|---|
| high | 1–16 | track N's L/R on 2N−1/2N, post-FX, pre-fader |
| high | 17–18 | MAIN L/R |
| high | 19–20 | CUE L/R |
| full | 1–2 | the stereo sum of the eight tracks |

Channels 1–16 are taken before track LEVEL, the crossfader, MAIN volume
and the master effects. MAIN and CUE are the words sent to the DACs, so
they include all of those.

Based on markandrus's proof of concept
([octemu](https://github.com/markandrus/octemu) `custom/usb-audio.py` +
`custom/coldfire/usb-audio.s` at `6a9ff68`, MIT): the shims, producer,
packet builder, rate servo and UAC2 replies are his. MAIN/CUE on 17–20 are
Bryan T's (25 Sep 2026).

## Measured

Under the port, `verify_usb` (in `make check REMIX=usb-audio`) runs with no card and
silent tracks. It checks:

- EP `0x83` is isochronous, 960 bytes, bInterval 2.
- AS_GENERAL has 20 channels; FORMAT_TYPE_I has subslot 4 and 24 bits.
- A second open with the first poll held back 600 frames: `anchor` within
  that gap and `lastfill` at 512 ± 64; over the next 400 polls the fill
  holds the servo band's floor (384) with no underrun.
- Taps: with the read-back arena and MAIN/CUE re-poked before every poll
  with words that name their source, side and frame, channel N carries
  only its own source (tracks 1–8 L/R, MAIN L/R, CUE L/R), each seen.
- Full speed after re-enumeration: 1 ms packets of 44/45 8-byte frames.
- 880/960-byte packets at the 250 µs cadence, none empty after the first
  ten.
- Every subslot's low byte is zero, with 0 underruns and 0 overruns.
- After alt 0, every poll is empty.

A build with `MAIN_CUE_BASE` pointed at a frame- and channel-coded pattern
streamed 8,709 frames: every channel 17–20 subslot held the expected word
in order, and channels 1–16 were untouched.

The USBSIG tone project (`tools/harness/usb_sig_project.py`) on a card
under the port:

- **High speed.** All sixteen track channels carry their tone at the
  expected frequency, and 95.2–99.8% of samples have non-zero low 8 bits.
- **Full speed.** 360-byte packets at bInterval 1: the left sum carries
  every left tone, the right sum every right tone.

Overruns under the port follow the bench host's skipped polls, not the
device. The port logs them as `iso poll(s) with no IN waiting`.

The port cannot see the producer's timing against the eDMA's bank swap:
the emulator runs the frame interrupt and the eDMA in lock-step.

### MAIN/CUE against the tracks

The producer reads channels 1–16 from the read-back arena's previous bank
and 17–20 from the mixdown buffer's current pull. Measured under the port
(`tools/harness/usb_align.py`, 28 Sep 2026: the tone project on a staged
card, the producer's ring dumped at the end of the run, each tone's phase in
its track channel against MAIN): MAIN lagged the tracks by 16 samples, one
block, on every tone that reached MAIN (T8 both sides 15.95 / 16.03, T6
16.02 / 15.96, T3 15.91 / 16.09, T1 R 15.72; residues modulo periods from
42 to 126 samples, so 16 is the only lag under 882 that fits). Bryan T heard
MAIN lag on his unit (25 Sep 2026), the same direction. Since 28 Sep the
producer writes MAIN/CUE into the ring slot `MAIN_CUE_LAG_BLOCKS` = 1 block
behind the tracks' slot (the consumer runs 512 frames behind, so the slot is
unread), and `verify_usb_align` reads 0 under the port. The size of the lag
on hardware is inferred from the port's structure, not measured on a unit.

## On the unit

**24-bit, 16 channels (image 69, Sam's MKII, 25 Sep 2026).** macOS lists a
16-channel 44.1 kHz input. Two takes with `tools/rec`, with the counters
read before and after each:

| take | project | length | tones | samples with non-zero low 8 of 24 bits | underruns / overruns / reprimes | events after 0.76 s |
|---|---|---|---|---|---|---|
| 1 | USBSIG | 60 s | all 16 at their frequency, −27.0 dBFS | 97.1–100% per channel | 0 / 0 / 0 | 0 |
| 2 | USBLOAD (locks every step, 200 BPM) | 120 s | all 16, −19.3 dBFS | 97.1–100% | 0 / 0 / 0 | 0 |

`lastn` 11 and `lastfill` 512–576 after each take.

**20 channels (`usb-out-tracks-main-cue` image 90, Bryan T's MKII, 25 Sep 2026).**
Channels 17/18 carried MAIN and 19/20 CUE: an uncued track was on MAIN
and a cued track on CUE.

**16-bit, octemu's format (image 64, Sam's MKII, 25 Sep 2026).** Four
USBSIG takes and one USBLOAD take, 9.6 minutes in total. Every channel
carried its track's tone, and there were no discontinuities after the
first 1.6 s of any take. Underruns and overruns stayed at 0, and
`bankdup` did not move. Takes 4 and 5 ran with 7,170 and 7,950 USB-MIDI
messages a second coming in (125 s and 185 s), with no stall and no
change in the stream. octemu's own image (image 65, `USBAUDIO.BIN` on
the card root) enumerated as the MIDI composite only; its payload never
installed. So there was no A/B against his build.

### CUE against MAIN with MASTER TRACK on

With MASTER TRACK on, CUE led MAIN by 32 samples (two blocks); with it off
they are sample-aligned. Measured on Bryan T's MKII (29 Sep 2026: a
transient on a track sent to both, recorded over USB in Logic; master off
0, master on CUE 43976 vs MAIN 44008). The cause is the mixdown, not USB:
payload A tests bit 10 of `x:(X:$207+$7e)` at `P:0x257` and on the master
path (`P:0x292`) builds the cue bus from slots 0-6 of this frame's blocks
but MAIN from slot 7 alone, track 8's output of the mix it was sent two
frames earlier. The ColdFire sets that bit from the MASTER TRACK byte
`0x80000034` (the frame record builder, `0x4000498c`). The read-back's two
packs (`P:0x2df` MAIN, `P:0x2e2` the cue bus) read the same ring half and
samples, so the offset is already in the words.

The producer writes CUE `CUE_MASTER_LAG_BLOCKS` = 2 blocks ahead of MAIN's
slot while `0x80000034` is nonzero, and in MAIN's slot otherwise (channels
19/20 here, 3/4 in OUT MAIN CUE). After it, on the same unit, CUE and MAIN
land on the same sample with the master on and with it off. With the
master on, CUE keeps its alignment with MAIN and leaves the tracks' by 32
samples; MAIN itself sits 32 samples behind the tracks, which
`MAIN_CUE_LAG_BLOCKS` does not cover. No gate covers the master-on case:
`usb_align.py` stages the tone project with `MASTER_TRACK=0`, as
`verify_set` does ([tools/emu/README.md](../../tools/emu/README.md)). With
the master off the producer's words are unchanged and `verify_usb_align`
reads 0. Toggling the master leaves up to 32 frames of stale CUE in the
ring once.

## Open

- **A burst of reordered samples 0.5–1.5 s after a host opens the
  stream**, then in order for good; no frames are lost. At 24 bits it is
  on the right channel of every pair only. It was absent on one take in
  five. Whether it is the device's queue at stream start or the host's
  stream start is not known. `docs/contributing/FAILURE_MODES.md` has the
  entry.
- Not measured: Windows and Linux hosts; USB controller load from the
  250 µs packet rate beyond the takes above.
- The first-poll anchor on a unit: `anchor` over `usb_counters.py` after
  an open (expected about 460 on macOS), and the two rings' `lastfill` sum
  with USB AUDIO IN beside it (expected about 896, was about 1,355).
- `minfill`/`maxfill` on a unit under a busy project and DISK MODE churn:
  the host poll jitter the OUT ring absorbs, which is the floor for a
  lower `AUD_TARGET`.

## Gates

- `verify_usb` (`make check REMIX=usb-audio`): the checks under *Measured*.
- `tools/verify/verify_usb_align.py` (the manifest's gate): MAIN/CUE against the tracks.

## Variants

`usbaudio.s` is assembled three ways, one module each; a remix carries one
(they take the same hook sites, and the build refuses two by name):

| module | `USB_LAYOUT` | high speed | full speed |
|---|---|---|---|
| USB AUDIO OUT TRACKS MAIN CUE (this) | 0 | 20 channels: tracks 1–16, MAIN, CUE | the tracks' stereo sum |
| [USB AUDIO OUT TRACKS](../usb-audio-out-tracks/README.md) | 1 | 16 channels: the tracks | the tracks' stereo sum |
| [USB AUDIO OUT MASTER](../usb-audio-out-master/README.md) | 2 | 2 channels: track 8's L/R | track 8's L/R |

The layout is a `.set` in the `remix.inc` each module's `Linked` unit
writes. Every `USB_LAYOUT = 0` path is the source as it was; this module's
image is byte-identical to the one built before the variants (27 Sep 2026).

## How it works

- **Source, tracks.** The read-back arena at SRAM `0x80003190`. The eDMA
  writes every track's post-FX pre-fader block there each frame, in
  ping-pong banks. The stock delay and Tape Echo read the same memory.
- **Source, MAIN/CUE.** Core 0's mixdown packs ESAI TX slots 2/3 (MAIN)
  and 0/1 (CUE) into the host read-back (`P:0x2df`, `P:0x2e2`). The frame
  ISR's eDMA chain ch1 → ch6 → ch7 lands them at `0x80005e60` (MAIN) and
  `0x80005ee0` (CUE), 16 × (L,R) each. The stock recorder reads the same
  buffer for SRC3 = MAIN / CUE.
- **Producer.** Runs from the frame interrupt's last instruction
  (`0x4000d9a0`), every 16-sample block, whether or not a host is
  listening. It reads the previous bank, keeps the top 24 bits of each
  32-bit sample, and writes one 80-byte slot per frame (20 channels × 4
  bytes) into a 1,024-frame ring, plus an 8-byte stereo sum into a second
  ring for full speed.
- **Endpoint.** EP3 IN, isochronous, asynchronous, bInterval 2 (250 µs).
  Packets carry 11 or 12 frames, at most 960 bytes, one high-speed
  transaction. A rate servo moves the packet size ±0.1 frame against a
  512-frame target fill, so the stream is a gap-free copy of the ring.
  Four transfer descriptors are kept queued (1 ms of polls). The frame
  interrupt (every 363 µs) is the only context that queues packets.
- **The first poll sets the cushion.** SET_INTERFACE alt 1 queues four
  packets and then nothing more until one has retired, the controller's
  own record that the host polled. At that block the consumer is set 512
  frames behind the producer and the frames produced in between are
  skipped once (`anchor` in the counters). A host that starts polling late
  (macOS: about 460 frames after alt 1, Bryan T's unit, 27 Sep 2026) had
  otherwise started the stream that much further behind for good, since
  the servo holds whatever fill it finds.
  Full speed: the stereo sum, 44 or 45 frames per 1 ms packet.
- **Descriptors.** Two functions under interface associations: the MIDI
  function, then a UAC2 AudioControl with a fixed 44.1 kHz clock source
  and an AudioStreaming interface 4 (alt 0 idle, alt 1 streaming). USB
  MIDI's descriptor unit generates this configuration when this module is
  in the remix. The clock source's CUR/RANGE/validity requests are
  answered by a shim on the stock "unknown request" STALL tail.
- **DMA memory.** The USB controller does not snoop the data cache, so the
  four dTDs and four 960-byte packet buffers are read and written only
  through the uncached SDRAM alias (address + `0x08000000`,
  `docs/contributing/PLACEMENT.md`).
- **Placement.** A DRAM unit: the loader places it in the platform reserve
  and zeroes its data, and every hook is a build-time detour. The unit is
  running before a host can enumerate, so no re-plug is needed. octemu's
  card-loaded payload, page allocator and runtime hook installer are not
  used. The ISR site is USB MIDI's; this module's shim retires EP3
  completions and chains to USB MIDI's by symbol (`Override`).

## Counters

A vendor control request (bmRequestType `0xc0`, bRequest `0x55`) returns
fifteen counters as 60 big-endian bytes: consumed, acc, overruns,
underruns, lastn, lastfill, lastbank, bankdup, lastsamp, srcjump,
reprimes, minfill, maxfill, anchor, produced. minfill/maxfill are the
ring's low and high water at packet builds since the host's first poll of
this open; anchor is the frames skipped at that poll.

- `tools/hw/usb_counters.py [--watch 1]` reads them from a unit
  (`brew install libusb`, `.venv/bin/pip install pyusb`).
- `usb_host.py … counters` reads them under the port.
- `verify_usb` checks them after its stream.

## Ground

| what | where |
|---|---|
| code | DRAM unit `usbaudio` |
| rings | 1,024 × 80 B (20 channels) + 1,024 × 8 B (stereo sum), the unit's data |
| DMA memory | `aud_dtds` + `aud_bufs`, 4 × 32 B + 4 × 960 B, through the uncached alias (+`0x08000000`) |
| hooks | `0x4001dd04` SET_INTERFACE, `0x4001d824` GET_INTERFACE, `0x4001de64` class requests, `0x4001d4b2` EP0 page fix, `0x4000d9a0` producer, `0x4001e606` USB ISR (USB MIDI's, overridden) |
| poke | `0x400e2004` device class → `ef 02 01` |
| descriptors | USB MIDI's `usbmidi_cfg` unit, generated with the audio function when this module is in the remix |
