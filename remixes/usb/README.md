# `usb` and `usb-audio` — the rig over the OT's own USB port

Two remixes of the rig (the effects and hosts of [`bottleservice`](../bottleservice/README.md), without Octakit and the scene modules), with USB functions added on the DRAM platform:

| remix | adds | the unit appears to a host as |
|---|---|---|
| `usb` | USB MIDI | card storage + a class-compliant MIDI port that mirrors the DIN ports |
| `usb-audio` | USB MIDI + USB AUDIO EXTENDED | the above + a 20-channel 44.1 kHz 24-bit audio input (tracks 1–16, MAIN 17–18, CUE 19–20) |

USB AUDIO has three builds of one source, one module each: EXTENDED (the
twenty channels above), FULL (the sixteen track channels, remix
`usb-full`) and MASTER (track 8's L/R, remixes `usb-master` and
`bottleservice`).

## What is in it

- **USB MIDI** (markandrus, [octemu](https://github.com/markandrus/octemu), MIT) — MIDI in and out over USB. Incoming messages take the same path as DIN MIDI IN; everything the unit sends on DIN is also sent over USB. [`modules/usb-midi/README.md`](../../modules/usb-midi/README.md).
- **USB AUDIO EXTENDED** (markandrus, octemu, MIT; `usb-audio` only) — at USB high speed, track N's post-FX, pre-fader L/R on channels 2N−1/2N. At full speed, the stereo sum of the tracks. Track LEVEL, the crossfader, MAIN volume and the master effects are not in the stream. [`modules/usb-audio-extended/README.md`](../../modules/usb-audio-extended/README.md).
- The rig's effects and hosts as in [`bottleservice`](../bottleservice/README.md): the bus, the three stations, TEMPO SYNC, CC MAP, MODE DEFAULTS, RIG HOSTS; `usb-audio` also carries TEMPO BUS and CC FEEDBACK (every knob value change transmitted as its CC, `modules/cc-feedback`).

## Status

- `usb-audio` at 16 bits on Sam's MKII as image 64 (25 Sep 2026): enumerates on macOS as "Elektron Octatrack DPS-1" (16-channel input + MIDI port). Every channel carried its track. 9.6 minutes recorded with no discontinuities after the first 1.6 s of each stream. Device counters 0 underruns, 0 overruns. USB MIDI in took 7,950 messages/s for 185 s without a stall.
- Open: a burst of reordered samples 0.75–1.5 s after the host opens a stream, on four of five takes (`docs/remixer/FAILURE_MODES.md`).
- `usb-audio` at 24 bits on Sam's MKII as image 69 (25 Sep 2026): 16 channels at 24 bits, every channel its track's tone, 3 minutes recorded (USBSIG 60 s, USBLOAD 120 s) with no discontinuities after 0.76 s; counters 0 underruns, 0 overruns. The start burst is on the right channels only. `modules/usb-audio-extended/README.md` has the numbers.
- 20 channels (MAIN on 17–18, CUE on 19–20) on Bryan's MKII as `usb-lean` image 90 (25 Sep 2026): MAIN and CUE on their channels, level changes follow. `usb-lean` is stock effects + USB MIDI + USB AUDIO, for testing the stream without the rig.
- `usb` alone has not been flashed. Its module is the one that ran inside image 64.
- Not measured: USB MIDI timing against DIN, DISK MODE entered with a MIDI or audio session open, Windows, Linux hosts.

## Build and flash

1. Set up the repository and the stock OS: [BUILDING.md](../../docs/remixes/BUILDING.md) §1–2 (`make setup`, `make os`, `make recon`).
2. Build:

   ```bash
   make image REMIX=usb-audio BUILD=1    # or REMIX=usb
   ```

   Optional first: `make emu-cf` then `make check REMIX=usb-audio`. `verify_usb` enumerates the image under the emulator and streams from it.
3. Back up the card and flash from it: [BUILDING.md](../../docs/remixes/BUILDING.md) §4–5. Recovery: §6.
4. Old projects: [`bottleservice` — How to flash](../bottleservice/README.md#how-to-flash) (`ot_project.py host` and `stamp-defaults`).

OS upgrades still need DIN MIDI or the card. They do not work over USB MIDI.

## Using it (macOS)

1. Connect the unit to the computer over USB.
2. **Audio MIDI Setup** lists "Elektron Octatrack DPS-1": a 20-channel 44.1 kHz input (`usb-audio`, `usb-lean`) and a MIDI port (both remixes). If it does not show: `system_profiler SPUSBDataType | grep -A12 Octatrack`.
3. In a DAW, select that device as the input. Channels 1–2 are track 1, 3–4 track 2, … 15–16 track 8.
4. Record from the command line, 60 s, all twenty channels:

   ```bash
   sox -t coreaudio "Elektron Octatrack DPS-1" -c 20 -r 44100 -b 24 take.wav trim 0 60
   ```

5. Device counters (`usb-audio` only): `brew install libusb`, install `pyusb`, then `tools/hw/usb_counters.py --watch 1`. The Mac-specific Python setup is in the script's header. `python3 tools/harness/click_scan.py take.wav` lists discontinuities per channel.
