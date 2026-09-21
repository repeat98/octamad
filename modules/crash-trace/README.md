# Crash trace — diagnostic firmware only

`octapitch-euclid-debug` adds MIDI diagnostics to the Octapitch2 + Euclid
selection. Build 108 keeps Dark Reverb, excludes DJ EQ/Spring/Plate, and
retains REPITCH, preview volume, filename BPM and the Euclid changes.
This is instrumentation, not a fix for the reported blackout.

## Capture through the Scarlett

Connect **OT MIDI OUT → Scarlett MIDI IN**, Scarlett USB → Mac. For this
session use MIDI OUT only for capture: a checkpoint occupies about 29 ms
of MIDI wire time. It is skipped when either transmit queue is occupied,
when output is disabled, or during an open SysEx. Queuing can still delay
musical messages arriving immediately afterward. The audio path never
waits for MIDI and never writes to the CF card.

List inputs, then start the passive recorder from the repository root:

```sh
python3 tools/hw/ot_crashlog.py --list
python3 tools/hw/ot_crashlog.py --port 'Scarlett 18i8 USB' --out out/crashtrace/session.jsonl
```

Use a new filename for each run. Start capture before switching on the OT.
The recorder sends nothing, saves raw MIDI plus decoded reports, flushes
lines immediately and syncs to disk once a second. Keep the Mac awake.
Ctrl+C closes the log. Do not route the diagnostic input back to MIDI OUT.
Capture works only while this process and the Scarlett remain connected.
An existing build without CRASH TRACE cannot produce diagnostic packets.

With build 108, look for `checkpoint` rows, build 108, roughly once per
second. If they are absent, recording has not yet been verified—absence
alone does not prove a crash. A `checkpoint_gap` is emitted after six
seconds without a previously received checkpoint. It may also mean MIDI
congestion, a disconnected cable/interface or a host delay. A
`capture_overflow` explicitly marks incomplete host evidence.

When the crash occurs, note the wall-clock time and photograph the LEDs.
Leave the recorder running through a normal reboot attempt if practical,
then stop it and retain the complete JSONL. Do not repeatedly flash while
the unit is failing to boot reliably. A known-good compatible supply and
stock-firmware comparison remain useful independent diagnostic controls;
the owner recalls similar symptoms before custom firmware.

## What the evidence means

- `checkpoint`: audio frame count, raw sequencer clock, transport state,
  tempo, skipped checkpoint count, current task, both effect IDs on all
  eight tracks. Frame seconds measure engine progress, not wall uptime.
- `exception`: raw CPU exception frame, decoded vector/SR and saved PC,
  plus last frame count. It is emitted before the existing panel printer;
  this is useful when the display/link cannot show the exception.
- Checkpoints continuing during a screen blackout show that the hooked
  audio-control path and MIDI output still run. They do not prove every
  task or DSP is healthy.
- Abrupt silence without an exception cannot distinguish lost power,
  CPU lockup, MIDI failure or a diagnostic-path failure by itself.

The exception report is best effort. It needs a valid saved stack frame
and at least one successful checkpoint since boot (UART initialization).
It cannot report early boot failures, every exception source, invalid
memory that prevents the hook running, or loss of power. A single total
poll budget bounds its UART wait. It then continues the original exception
handler, whose own panel waits may hang. No recovery behaviour is changed.

## Ground and validation

MIDI UART0 is `0xfc060000`. The stock sender at `0x40010bc8` and ISR at
`0x400106ec` establish the 4096-byte descending queue, producer index
`0x400b9678`, count `0x400b967c`, priority count `0x400b9688`, disabled flag
`0x460ba978`, and running-status cache `0x460ba988`. The diagnostic enqueue
is atomic, fixed-size, only into an empty validated ring; F7 updates the
running-status cache. Interrupt priority and registers are restored.

The default exception trampoline `0x40000d74` masks interrupts and passes
the saved frame to `0x4003af94`. Our ROM-resident detour reports its first
eight bytes before replaying that printer's prologue. It does not depend
on the Euclid DRAM loader or introduce a filesystem call.

Protocol: `F0 7D 4F 54 44 01 6C type`, eight nibbles per big-endian raw
word, XOR of bytes after F0 up to checksum, `F7`. Type 1 has ten words;
type 2 four. System realtime may interleave. The capture parser bounds its
buffer and rejects malformed lengths/checksums. `7D` is an experimental
identifier, with `OTD` distinguishing this protocol.

`verify_crashtrace.py` executes actual linked code, checks queue wrap,
register/CCR preservation, skip conditions, cadence, injected exception
frames, a stuck UART, and the parser. `verify_euclid.py` additionally
checks actual MIDI output from full firmware playback when CRASH TRACE
is selected. Emulator UART transmission is instantaneous: these checks
do not certify real MIDI scheduling or diagnose the physical failure.
