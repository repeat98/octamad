# DSP loader transfer probe (experimental)

This module lives on `codex/dsp-part-loader`, outside the Analog BD PR.
It exercises firmware transport and bounded staging. It is not a finished
loader, does not execute staged words, and is not a flash candidate.

The general manager targets stock and new effects/engines. Stock candidates
come from the user's image (`tools/experimental/dsp_part_loader/stock_catalog.py`),
with per-payload native addresses and explicit adapter requirements. Fixed
system code, tables and unaudited shared routines remain resident. No stock
code is checked into the repository.

## Transport and staging

The firmware's state-7 eDMA extension writes a 64-halfword packet to each
core at idle bank +0x320, then reads 32-halfword status at +0x360. Frame-head
hooks validate magic, checksum, opcode, count and staging bounds. Replies
carry the request sequence and core tag. There are two diagnostic opcodes:

- PROBE validates the packet and acknowledges it.
- STAGE reconstructs 24-bit words and writes exactly 24 words into the
  module's 128-word P table. The destination is a checked offset, never a
  caller-supplied absolute address. The build owns and places this table.

The test reads the actual P memory through the emulator and compares every
staged word plus the untouched remainder. That is not DSP-side readback or
an execution admission mechanism. There is no EXEC/COMMIT opcode or dispatch
change. A checksum is transport error detection, not authentication.

Idle frames issue no additional DMA transfers. Consumed mailbox magic is
cleared. The native controller rejects stale replies, wrong-core tags and
errors, times out missing replies and skips sequence zero on wraparound.

The interrupt must acknowledge channel 1, restore its original NBYTES, and
restore the host core selector to core 0 before unmasking the next frame.
The stock frame interrupt sends its first command without selecting core 0.
Missing that restore sent the frame command to core 1 and stopped both DSPs
after three frames. The repaired probe passed both-core acknowledgements
and continued frame execution in the emulator. No hardware test occurred.

## UI and remaining integration

The UI-task hook displays `DSP MEMORY FULL`, `DSP OVERLOAD` or `DSP LOAD FAILED`
through the stock message function. Uppercase is required by the stock font;
lowercase initially produced a popup showing only `DSP`, caught by inspecting
the LCD capture. The DMA interrupt only queues a reason; it never draws.

The existing FX1/FX2 setters and manual Part selector now have before-write
guards, using the diagnostic resident-only backend described below. The
resource-admission planner is not connected to them yet. Dispatch staging, coordinated activation, outgoing state/tail
retention, crossfades and audible-switching qualification remain unimplemented.

## Ownership and tests

Packet mailboxes are X:0x2320..0x235f / 0x4320..0x435f; status mirrors are
X:0x2360..0x237f / 0x4360..0x437f, private to each core. The isolated remix
uses no USB input or Analog BD module. Existing detour claims reject their
conflicting hooks; a shared scheduler and a general X ownership declaration
are still needed before composing this with other modules.

Generate ColdFire assembly with `python3 modules/dsp-loader-transfer/generate.py`;
`--check` verifies reproducibility. `make check REMIX=dsp-loader-transfer`
runs the native controller gate and, with `OT_PROJECT` or `DL_CARD`, the port
gate. The native test covers successful, stale and wrong-core replies,
timeouts, UI deferral and 65,536 sequence transitions. The port gate snapshots
the built image, queues PROBE and STAGE on both cores, compares P memory,
checks continued frames and calls the deferred memory message.

Passing these gates does not qualify seamless switching or hardware timing.

## Existing-control guards

The guard changes no menu or control. It intercepts FX1 at `0x400526e4`, FX2
at `0x40052474`, and manual Part selection at `0x4004a8a4`, before those
functions mutate the working Part, SRAM shadow, pattern linkage or live lanes.
The request carries all sixteen target FX IDs and eight source-machine types.
The backend can accept, wait, or refuse. Waiting leaves the stock setter
unexecuted. The UI tick replays it only when the backend reports readiness and
the bank, pattern, Part, track, cursor, effect IDs and source types still match.
A changed context cancels the token; a repeated identical request is coalesced.
The wrapper notifies commit only after the original stock setter returns. That
notification does not establish a shared DSP activation boundary or safe tail
retirement.

`selection_probe.c` is explicitly a diagnostic backend. It admits only the
stock effects resident in this test remix. Its emulator-controlled result
exercises memory/processing refusal and deferred readiness; it does not perform
allocation or load an engine. Do not reuse this adapter for nonresident code.
The asynchronous interface still needs the real loader's reservation, readiness,
commit and retirement contract before it can manage memory.

`verify_selection.py` forks one loaded fixture into nine cases: refusal on
both FX slots, immediate/deferred acceptance, cancellation, and the equivalent
manual-Part cases. It compares the working Part, SRAM shadow, live IDs, parameter
lanes, pattern/Part link and active-Part byte. This is a before-write and replay
proof, not an audio-continuity or memory-exhaustion measurement.

### Other Part paths still to cover

Hooking the engine's `0x40009094(bank, part)` alone is too late: several callers
have already copied project state or changed pattern linkage. The manual path
above was moved earlier for that reason. `0x40029a4c(src, part)` copies the Part
to working and SRAM storage before tail-calling the engine apply when active.
`0x4004a908` saves a Part; `0x4004a9d0` resets one; both may re-apply after writes.
Other direct apply calls occur at `0x40025830`, `0x40025b30`, `0x4002b59a`,
`0x4002b8f8` and `0x400907e4`. The engine also has apply variants at
`0x40009848` and `0x40009e00`. These are inspected addresses, not qualified
admission seams. Automatic pattern changes, project load/reload and copy/paste
are not guarded by this slice. The dynamic backend must remain disabled until
those paths are handled; otherwise it could leave UI/storage and audio in
different Parts after a refusal.
