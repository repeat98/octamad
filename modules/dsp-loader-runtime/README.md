# Experimental DSP residency runtime

Separate experiment on `codex/dsp-part-loader`; excluded from the Analog BD PR.
Emulator qualification only. This is not a flash candidate or a replacement for
stock's full DSP allocator.

## What actually runs

The freestanding ColdFire allocator reserves code once per algorithm/core,
shares it across tracks, retains outgoing allocations through acknowledged
unbind, and refuses a target or transition that cannot fit. Its arena is the
build-owned 1,408-word P table on each core: 64 words retain original dispatch
entries and 1,344 words hold code. No undeclared DSP addresses are used.

The UI task submits immutable upload descriptors. The frame ISR sends at most
24 program words per participating core per transaction. The DSP bounds-checks
the write, reads the chunk back, and returns its 24-bit sum. Only acknowledged
uploads can be bound into the stock init/proc table. Bind/unbind runs before that
core's effect calls; the controller keeps memory reserved if unbind fails.
The gate also compares every uploaded word through the emulator's P memory dump.

The catalogue currently adapts stock EQUALIZER, PHASER and COMPRESSOR and the
unchanged Character module. Stock packages are generated from the user's image
into the build's ignored `remix.inc`; no stock words are checked into Git.
DO loop ends and external relative helper branches are relocated explicitly.
The other stock algorithms in this remix remain pinned. The DSP receiver and
system helpers always remain resident.

FX1/FX2 and manual Part selection use the existing before-write guards and info
modals. Queued sequencer changes and stopped pattern requests now prepare before
publication. LOAD PROJECT is deferred before its command is posted: read-only
metadata admission and verified uploads run on the UI task. The engine command
entry rejects a load without that admission. No new chooser or controls are added.

## Critical current boundary

**Static originals are still resident.** These guards cover the qualified routes,
not every firmware mutation. The post-publication observer remains for uncovered
paths: chain restart/stop, Part copy/reload/reset, background bank reload and new
project creation still require separate before-write guards and qualification.
No original algorithm span has been reclaimed. Do not remove it on the strength
of the pattern/project tests. See `PUBLICATION.md` for exact seams and limitations.

A queued target that is not ready at its deadline leaves the old pattern running;
the UI requeues it after preparation. Capacity refusal leaves the old pattern and
Part selected. Stopped requests are similarly deferred. Project admission rejects
missing/ambiguous metadata and a STATE.PART that disagrees with the pattern link.
It uses a private uncached file buffer; it does not change the saved project.
If the stock loader fails after starting, both code sets stay reserved until a
restart. Recovery from a partially loaded project is not implemented.

Rebinding an identical algorithm preserves its stock r7 state and needs no
crossfade or extra algorithm instance. Processing is already charged to the
stock scheduling path; the P allocator does not establish a new processing
allowance. Loader overhead, hardware timing, seamless changes between different
sounds, and retained tails still need separate qualification. A finite arena
cannot promise arbitrary instantaneous swaps without transition headroom.

`dl_residency_enabled` is a test/control bypass, default enabled. Disabling it is
valid only while the static originals are retained. It is not a user control.

## Verification

- `python3 -m tools.experimental.dsp_part_loader.verify_controller`: native
  firmware code, genuine capacity refusal, sharing, cancellation, delayed commit,
  failed-unbind retention, readback failure, chunking and sequence wrap.
- `python3 -m tools.experimental.dsp_part_loader.verify_runtime_audio`: 72 exact
  stereo comparisons against original placements, both cores, three sub-block
  lengths and three parameter sets per algorithm.
- `DL_CARD=<empty-FX fixture> python3 -m tools.experimental.dsp_part_loader.verify_runtime`:
  actual ColdFire/DSP uploads, dispatch, selection and automatic apply. The gate
  also accepts `OT_PROJECT`, normalizing an owned fixture copy.
- `OT_PROJECT=<fixture source> python3 -m tools.experimental.dsp_part_loader.verify_project_publication`:
  actual LOAD PROJECT with managed effects already saved, exact code/dispatch
  on both cores, no chooser calls or effect injection after loading.
- `OT_PROJECT=<fixture source> python3 -m tools.experimental.dsp_part_loader.verify_live_audio`:
  continuous eight-track THRU input and four Part applications, compared with
  the same firmware's static placement. Failure is an audio discontinuity lead,
  never grounds for relaxing the comparison.

All static/global C state is explicitly initialized. The platform loads binary
bytes but does not initialize trailing BSS; the first firmware test caught that
state overlapping its compressed stage. `generate.py` now rejects BSS/common
symbols in these units. Allocator byte copies also keep source and destination
accesses separate: the port gate caught shifted copies from the compiler's
combined same-base postincrement/displacement MOVE; native host tests alone
could not expose it. This is a workaround, not a claim about silicon semantics.

Queued-pattern evidence: `OT_PROJECT=<fixture> python3 -m tools.experimental.dsp_part_loader.verify_pattern_audio` sends a MIDI program
change to the running sequencer. Both the pattern and Part must actually change.
The eight stereo chains and main capture matched static execution exactly over
8,192 frames, with no residency/transport errors. This exercises the normal
queued pattern path; the new guard prepares before publication and defers the
change if preparation misses its deadline.

Verification before the publication guards (29 September 2026):

- `OT_PROJECT=out/analog-bassdrum/ui-fixture DL_CARD=out/analog-bassdrum/ui-gate/card.img make check REMIX=dsp-loader-runtime`: passed all runnable shared/remix checks and the four initial image gates (runtime audio, real allocation/dispatch, saved-project loading, continuous Part-apply audio).
- `OT_PROJECT=out/analog-bassdrum/ui-fixture .venv/bin/python3 -m tools.experimental.dsp_part_loader.verify_live_audio --pattern`: passed the queued-pattern comparison. The same entry point is now registered as the fifth image gate through `verify_pattern_audio.py`.
- `OT_PROJECT=out/analog-bassdrum/ui-fixture DL_CARD=out/analog-bassdrum/ui-gate/card.img make check-remix REMIX=dsp-loader-transfer`: passed the original transport remix regressions, including both image gates and all nine selection scenarios. Shared gates were covered by the full runtime check above.
- `python3 -m tools.experimental.dsp_part_loader.verify_controller`: passed all four native firmware test binaries and generated-assembly check.
- `python3 -m unittest tools.experimental.dsp_part_loader.test_loader`: 12 passed.
- `python3 tools/verify/verify_docs.py`: 48 modules, 38 remixes, zero problems.

Logs: `out/dsp-part-loader/runtime-full-check.log` and
`out/dsp-part-loader/pattern-audio-check.log`, plus
`out/dsp-part-loader/transfer-regression-check.log`. Generated firmware and stock-derived
packages remain local, ignored build output.

## Publication-guard verification (29 September 2026)

- `OT_PROJECT=out/analog-bassdrum/ui-fixture DL_CARD=out/analog-bassdrum/ui-gate/card.img make check REMIX=dsp-loader-runtime`: passed, seven image gates, no skipped gate. Log: `out/dsp-part-loader/publication-full-check.log`.
- `OT_PROJECT=out/analog-bassdrum/ui-fixture .venv/bin/python3 -m tools.experimental.dsp_part_loader.verify_publication_guards`: passed again with allocator-failure counters added. Both full-capacity cases record exactly one real residency failure, zero transport errors and unchanged state. Log: `out/dsp-part-loader/publication-capacity-proof.log`.
- Six native C test binaries and generated assembly check passed. The 72 DSP render comparisons and eight-track/main audio comparisons remain exact. Superseded stopped requests do not replay.

Normal queued/stopped requests and LOAD PROJECT now prepare before publication.
This is a partial route closure, **not permission to reclaim the originals**:
chain restart, Part copy/reload/reset, background bank reload, new-project paths
and pending stopped-Part retirement are listed in [PUBLICATION.md](PUBLICATION.md).
Nothing from this experiment was pushed to the Analog BD PR.
