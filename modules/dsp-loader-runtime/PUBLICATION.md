# Publication guards (experimental)

The runtime branch is isolated from the Analog BD PR. No original DSP code has
been reclaimed. All evidence below is emulator-only.

## Implemented seams

| Path | Before-write seam | Preparation and refusal |
| --- | --- | --- |
| Queued sequencer change | `0x400a406e`, `0x400a44a0` | UI prefetches pending bank/pattern's linked Part. Boundary admits only acknowledged residency; otherwise keeps the current pair and leaves a single-word mailbox for UI retry. |
| Stopped pattern request | `0x400a0570` | Captures all five arguments; UI prepares and replays the original body. A replaced request cancels its predecessor. |
| LOAD PROJECT request | `0x40023c7c` | Read-only `project.work`/bank metadata, capacity admission and verified uploads before posting the stock command. |
| LOAD PROJECT engine entry | `0x40085336` | Unauthorised command/name is refused through stock completion before loader side effects. |
| LOAD PROJECT completion | `0x4008540e` | Commit only after successful loader result and matching live IDs. Partial failure retains old and new allocations. |

The sequencer callback never allocates, performs file I/O, waits, or transfers
code. UI owns those operations. A phase-5 admission is valid only for that exact
prepared set and cannot outlive cancellation. A retiring set is not readiness.
Normal stock timing housekeeping still runs when a queued target is deferred.
The short pending-pair/mailbox writes mask interrupts; no allocation or file I/O
runs inside that critical section. Pinned-only sets require no DSP handshake.

Stock stopped-pattern selection can change the displayed Part before updating
live FX records. The stopped gate compares with a static-code control and checks
that dispatch is prepared; outgoing memory remains reserved until those live
records catch up. This pending transaction can still delay further selection;
resolving that lifetime is part of the remaining retirement work.

Project metadata is read through the filesystem vtable with a private, aligned,
uncached sector buffer; it does not borrow stock's global buffered-file scratch.
The parser scans the whole project file, rejects missing/duplicate/invalid state
keys, validates bank and Part tags, checks read bounds, and requires STATE.PART
to agree with the pattern-linked Part. Projects with differing links are refused
before loading until multi-target staging is implemented. The card must remain
unchanged between admission and the stock loader's reads; snapshotting/locking
that source is not implemented.

Project requests cancel outstanding pattern preparation before using the arena.
After a partially failed stock load, the manager retains both sets and refuses
further dynamic admissions until restart. Cancelling at that point would risk unbinding
code the loader already published. This is safe retention, not project rollback.

## Remaining routes — originals must stay

A census of direct stores to the running bank/pattern found a separate chain
restart store at `0x400a11c6`; it precedes a call through the normal pattern
request and needs its own guard. Do not infer coverage from the request detour.

Part copy (`0x40029a4c`), reset (`0x4004a9d0`), reload (`0x4004aab4`), background
bank reload (`0x40085418`) and new/reset project (`0x40025848`) can change the
set before applying it. They remain outside this qualification. The live-set
observer is still a fallback for these paths. Other indirect stores and apply
callers require an audit before the originals can be released.

## Reproducible gates

- `python3 -m tools.experimental.dsp_part_loader.verify_controller`: actual C
  code on host; late boundary, stale metadata/request, deferred replay, memory
  refusal, cancelled/retiring readiness, malformed/truncated/duplicate metadata.
- `OT_PROJECT=<owned fixture> python3 -m tools.experimental.dsp_part_loader.verify_project_publication`:
  actual admitted LOAD PROJECT, exact relocated words/dispatch on both cores,
  admission and completion counters, no chooser calls.
- `OT_PROJECT=<owned fixture> python3 -m tools.experimental.dsp_part_loader.verify_publication_guards`:
  stopped-pattern admission and real pattern/project capacity refusal. Snapshots
  include the complete bank, live IDs, running/active selectors and project name.
- `OT_PROJECT=<owned fixture> python3 -m tools.experimental.dsp_part_loader.verify_pattern_audio`:
  real MIDI queued change and all eight stereo chains/main against static audio.
- `OT_PROJECT=<owned fixture> python3 -m tools.experimental.dsp_part_loader.verify_pattern_refusal`:
  over-capacity queued change against a no-change audio oracle.

Generated images, original bytes, fixture copies, captures and reports remain in
ignored `out/dsp-part-loader/`. Compilation alone is not qualification. Full
`make check REMIX=dsp-loader-runtime` remains the floor for a passing change.
