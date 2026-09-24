# USB AUDIO

The eight tracks over USB as a UAC2 audio input: at high speed sixteen
channels of 44.1 kHz 16-bit PCM, track N's L/R on channels 2N-1/2N, post-FX
and pre-fader; at full speed the stereo sum of the tracks. markandrus's
proof of concept ([octemu](https://github.com/markandrus/octemu),
`custom/usb-audio.py` + `custom/coldfire/usb-audio.s` at `6a9ff68`, MIT),
carried onto octabam's DRAM platform. Needs USB MIDI: the audio function is
added to its composite.

## What it is

- **Source.** The read-back arena at SRAM `0x80003190`: the eDMA deposits
  every track's post-FX pre-fader block there each frame (the same memory
  the stock delay and Tape Echo read). The producer runs from the frame
  interrupt's last instruction (`0x4000d9a0`), reads the previous
  ping-pong bank, shifts 32-bit samples to s16 with saturation and writes
  one 32-byte slot per frame into a 1,024-frame ring (plus a stereo-sum
  ring for full speed). Track LEVEL, the crossfader, MAIN volume and the
  master effects are downstream of the tap and not in the stream.
- **Endpoint.** EP3 IN, isochronous, asynchronous, bInterval 3 (a 500 µs
  poll), 22 or 23 frames per packet. Two transfer descriptors so a packet
  is always queued behind the one in flight. A rate servo nudges the
  packet size ±0.1 frame against a 512-frame target fill, which is "send
  what is produced": the stream is a gap-free copy of the ring. Underruns
  (nothing to send) and overruns (the host stopped draining) are counted
  in the unit's data (`usbaudio_underruns`, `usbaudio_overruns`).
- **Descriptors.** Two functions under interface associations, the shape
  macOS accepts (his measurement against a Digitone): the MIDI function,
  then a UAC2 AudioControl with a read-only 44.1 kHz clock source and an
  AudioStreaming interface 4 (alt 0 idle, alt 1 streaming). The clock
  source's CUR/RANGE/validity class requests are answered by a shim on
  the stock "unknown request" STALL tail.
- **DMA memory.** The USB controller is a bus master that does not snoop
  the data cache, so the two dTDs and two 736-byte packet buffers live in
  cache-inhibited memory at `0x4ec94a00..0x4ec95000`, between the
  firmware's endpoint list and its own dTD pool (his scan: referenced by
  nothing in the image; his measurement: per-line cache pushes did not
  work, moving the structures did).

His card-loaded payload, page allocator, self-relocating entry, stage-2
hook installer, trampoline, on-screen reporter and hook guard are not
ported: the loader places the unit, the rings are its zeroed data, every
hook is a build-time detour, and the unit is up before the host can
enumerate, which is also why his "re-plug the cable" caveat does not
apply. The ISR site is USB MIDI's; this module's shim retires EP3
completions and chains to USB MIDI's by symbol (`Override`).

## Measured (25 Sep 2026, under the ColdFire port; nothing on hardware)

`make check REMIX=usb-audio`, `verify_usb` with the frame engine on and no
card (silent tracks, a live stream):

- five interfaces, 250-byte configuration, device class EF/02/01, EP 0x83
  iso 736 bytes bInterval 3; CS_SAM_FREQ_CONTROL CUR answers 44100;
- SET_INTERFACE 4 alt 1 → GET_INTERFACE reports 1; 400 polls at the
  device's 500 µs cadence carry 704/736-byte packets (22/23 frames), none
  empty after the first ten; alt 0 → every poll empty.

With a project playing (the eight-track stress project of
`tools/harness/stress_project.py`, `--sequencer`, 2.0 s drained at the
500 µs poll): 4,000 polls, none empty, 88,200 frames; eight distinct
stereo pairs, T1 −34 dBFS through T3 −23 dBFS, no two channels equal,
the largest sample step on T1 L 2,031 against a 99th percentile of 121
(the loop's own transients).

The port's host polls on the device's own clock (`tools/emu/ot_emu/usb.h`
`isoPoll`), which is what keeps the servo at 22/23: an unpaced drain
starved the ring and read as 21/22.

What the port cannot see: the producer's race against the read-back bank
swap, his open hypothesis for the clicks he hears on hardware (the
`usbaudio_bankdup` counter is in the unit's data for a hardware read-back).
A lock-step emulator serialises the frame interrupt and the eDMA.

## The counters, from a host

The unit answers a vendor control request (bmRequestType 0xc0, bRequest
0x55) with its twelve counters as 48 big-endian bytes: consumed, acc,
overruns, underruns, lastn, lastfill, lastbank, bankdup, lastsamp,
srcjump, reprimes, produced. `tools/hw/usb_counters.py [--watch 1]` reads
them on a unit (`brew install libusb`, `.venv/bin/pip install pyusb`); the
port's bench reads them with `usb_host.py … counters`, and `verify_usb`
checks them after its stream (under the port: 0 underruns, 0 overruns,
bankdup 2 at the frame engine's start).

## Hardware test (image 64, the first flash)

The question is his mid-stream clicks: not packet loss on his unit
(0 overruns, 0 steady-state underruns), so either the producer reads a
read-back bank twice or skips one (`bankdup` moves) or the fault is on the
host side (`bankdup` stays). One flash, one recording.

1. `make image REMIX=usb-audio BUILD=64` → `out/OCTATRACK_OCTABAM64.bin`
   to the card root, PROJECT → SYSTEM → OS UPGRADE; the rig modules are
   bamsep26's, so the current project plays as before.
2. USB to the Mac. Audio MIDI Setup should list the unit as a 16-channel
   input at 44.1 kHz (the MIDI Studio shows its MIDI port too). If it does
   not enumerate, `system_profiler SPUSBDataType | grep -A12 Octatrack`.
3. `tools/hw/usb_counters.py` once: produced counts up while idle (the
   producer runs from the frame interrupt whether or not anyone listens);
   underruns, overruns and bankdup should sit at 0 while nothing streams.
4. Record while the project plays, 60 s, all sixteen channels:
   `sox -t coreaudio "Elektron Octatrack" -c 16 -r 44100 -b 16 out/usb_take1.wav trim 0 60`
   (the exact device name is in `sox -V6 -n -t coreaudio /dev/null 2>&1 | grep -i octa`
   or Audio MIDI Setup), with `tools/hw/usb_counters.py --watch 5` in a
   second terminal from before the recording starts to after it stops.
5. Read the take: `python3 tools/harness/click_scan.py out/usb_take1.wav`
   lists per-channel sample steps above 8× the channel's 99th percentile
   with their times; line them up against the counter watch.

Outcomes: bankdup increments during the take → the producer (the frame
interrupt's read of the previous bank lands against the eDMA's swap; the
fix is a copy taken at a proven-safe point, the shape of #397). bankdup
still, underruns still, clicks present → the host or the cable; try a
second host and USB port before touching the unit. Clicks absent → his
caveat does not reproduce here. A freeze, a hang or a wedge on plugging
in: power off, recover per `docs/remixer/FLASHING.md`, and the FAILURE_MODES
entry gets the symptom.

## Ground

| what | where |
|---|---|
| code | DRAM unit `usbaudio`, 1,792 B text |
| rings + state | 36,948 B of the unit's data (1,024 × 32 B + 1,024 × 4 B + counters) |
| DMA window | `0x4ec94a00..0x4ec95000` (1,536 B, cache-inhibited; no ledger claim type for it yet) |
| hooks | `0x4001dd04` `0x4001d824` `0x4001de64` `0x4001d4b2` `0x4000d9a0` `0x4001e606` (USB MIDI's, overridden) |
| poke | `0x400e2004` device class → `ef 02 01` |
| descriptors | USB MIDI's `usbmidi_cfg` unit, generated with the audio function when this module is in the remix |
