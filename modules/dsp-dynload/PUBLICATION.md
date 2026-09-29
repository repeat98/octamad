# DSP dynamic loading: publication guards (experimental)

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
| Chain restart on STOP | `0x400a11ba` | Stock stores `chain[0]` as the running pattern (`0x400a11c6`) before requesting it, so the request guard is too late. The chain branch is admitted whole: ready (resident, or prefetched as the queued next pattern) runs stock unchanged; otherwise STOP stops on the current pattern with running/next pairs and chain position untouched, and the UI replays stock's chain branch (`0x400a11ba`-`0x400a1292`, store for store) once `chain[0]`'s Part is prepared. Dropped if the sequencer restarts, the chain clears or changes, or a newer request supersedes it (a second STOP does). |
| PASTE / RELOAD / RESET Part | `0x40029a4c`, `0x4004aab4`, `0x4004a9d0` | Only the active Part publishes at once; an inactive Part is data, which the pattern guards capture again before any later use. Target: the pasted image, the saved copy when its saved-valid flag is set (`bank+0x9b312+part`; stock changes nothing otherwise), or stock's defaults (FX1 from `0x400d47ad`, FX2 from `0x400d4ad1`: ids 4 and 8, both pinned). A deferred call replays the stock routine; PASTE replays from a private snapshot because its caller consumes the clipboard, and a deferred RELOAD reports success to its caller. |

The sequencer callback never allocates, performs file I/O, waits, or transfers
code. UI owns those operations. A phase-5 admission is valid only for that exact
prepared set and cannot outlive cancellation. A retiring set is not readiness;
the committed set of a transaction that is retiring its outgoing code is (it
stays bound). A deferred stopped request is dropped as superseded when the
queued pair changed after it was deferred: before 29 Sep 2026 the transport
start's own request, deferred during the load's retirement, replayed after
PLAY as a queued change and overwrote a chain's next pattern.
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

## Tripwire: `dl_unguarded`

Every UI tick the manager checks that each managed id in the live arrays
(`0x80000ec4` FX1, `0x80000ecc` FX2) runs bound relocated code: a committed
placement that is not being retired, or an acknowledged target of a ready
transaction (a guarded route publishes before its commit). Each distinct live
set that fails counts once. A set that appears and goes again between two
ticks is not seen, and the check says nothing while residency is disabled.
Positive control: `verify_runtime`'s `automatic-apply` publishes around every
guard and must trip it; its six guarded cases, the project load, the Part edits,
the stopped requests and every chain case must read 0. Zero on every route is
the condition for reclaiming the originals; the observer remains the fallback.

## Measured 29 Sep 2026 (port): a queued Part change does not re-apply FX

With the chain fixture (every track's source byte 1), residency disabled, the
Part index follows the pattern link (`0x400621e2`, sys task) but nothing
rewrites the live FX arrays: a write-watch on both saw only the project load's
`apply_part` (`0x40009384`/`0x4000938e`), and a DSP PC watch on core 1 saw
0 calls of EQ's proc while Part 2 (EQ on T1-4) was active and Character's proc
(Part 1) on T1 FX1 to the end. The sys handler's per-track routine
`0x400972fc` applies a track (`0x40001f18`, which writes both arrays) only when
that track's source byte in the new Part is 4. So the queued-pattern audio
gates never exercised an FX change (both runs kept Part 1's FX), and a queued
transaction's commit never arrives in the port: it stays armed until cancelled
(a chain boundary cancels it; stopped play keeps it). Falsified by a port or
hardware run where the arrays change at a queued change on a track whose
source is not 4. Whether hardware re-applies FX there is not measured.

## Remaining routes — originals must stay

Closed since the first audit: the chain restart and PASTE/RELOAD/RESET (above).

The live arrays have writers no guard covers. `docs/firmware/PARAM_PAGES.md`
§5d counts nine sites; besides `apply_part`, the FX selectors (guarded) and the
frame builder (a reader), they are the per-track apply `0x40001f18`
(`0x40002216`/`0x4000222a`) and inline per-track copies at `0x40094012`,
`0x400941c4`, `0x40096c14`, `0x40096e2a`, `0x40043d26` and `0x40028526`,
reached from per-track machine operations and from `0x400972fc`'s source-4
Part change. Census by writer is the complete list; the first audit went by
user action and missed these. Background bank reload (`0x40085418`, the
engine case that runs the bank loader `0x400905d4`, which requests and applies)
and the project paths at `0x40025770`/`0x40025848` also remain open, as does the
lifetime of an armed transaction whose publication never comes.

Recommendation (inferred, not built): before reclaiming the originals, make an
unbound managed id dispatch to a bypass stub instead of its original entry.
Then a route nobody guarded costs one dry slot for the few frames the observer
needs, instead of a jump into reclaimed memory, and reclaiming stops depending
on a perfect census.

## Reproducible gates

- `python3 -m tools.experimental.dsp_dynload.verify_controller`: actual C
  code on host; late boundary, stale metadata/request, deferred replay, memory
  refusal, cancelled/retiring readiness, malformed/truncated/duplicate metadata.
- `OT_PROJECT=<owned fixture> python3 -m tools.experimental.dsp_dynload.verify_project_publication`:
  actual admitted LOAD PROJECT, exact relocated words/dispatch on both cores,
  admission and completion counters, no chooser calls.
- `OT_PROJECT=<owned fixture> python3 -m tools.experimental.dsp_dynload.verify_publication_guards`:
  stopped-pattern admission and real pattern/project capacity refusal. Snapshots
  include the complete bank, live IDs, running/active selectors and project name.
- `OT_PROJECT=<owned fixture> python3 -m tools.experimental.dsp_dynload.verify_chain_stop`:
  a real sequencer plays a real chain (stock chain-add routine); STOP with the
  first Part cold (deferred, replayed, final state identical to static
  placement), over capacity (refused, nothing changes), prefetched (stock path),
  and a double STOP (the second request supersedes the deferred restart).
- `OT_PROJECT=<owned fixture> python3 -m tools.experimental.dsp_dynload.verify_part_edits`:
  PASTE (source overwritten after the call: the replay uses the snapshot),
  refused PASTE, RELOAD of a saved copy, RESET onto the predicted defaults, and
  an inactive RELOAD that opens no transaction; each against static placement.
- `OT_PROJECT=<owned fixture> python3 -m tools.experimental.dsp_dynload.verify_pattern_audio`:
  real MIDI queued change and all eight stereo chains/main against static audio.
  The Part index changes; the FX do not (above), so this is not an FX-change test.
- `OT_PROJECT=<owned fixture> python3 -m tools.experimental.dsp_dynload.verify_pattern_refusal`:
  over-capacity queued change against a no-change audio oracle.

Generated images, original bytes, fixture copies, captures and reports remain in
ignored `out/dsp-dynload/`. Compilation alone is not qualification. Full
`make check REMIX=dsp-dynload` remains the floor for a passing change.
