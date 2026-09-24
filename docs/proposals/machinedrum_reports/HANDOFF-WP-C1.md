# Handoff: WP-C1 record transport (24 Sep 2026, historical WIP)

**Superseded:** [WP-C1.md](WP-C1.md) records the completed full-stream gate.
The 15-block residual was traced to the reference JIT's 48-bit X/DO-loop
behavior; the interpreter reference matches all 33,503 available blocks.
The idle-prefix edit described below as rejected was actually present in
commit 1f2245b. Its stalled stepping loop has now been fixed.

Branch `machinedrum`, main checkout. Push to `origin` only, never `upstream`. No firmware bytes in Git.
Leave `modules/octakit/upstream` (dirty) and `base_firmware/` alone. Commits end with the Co-Authored-By line.

## State
Core-1 MD image (WP-B2/B3/B4) is pushed (6daafd6). This commit adds WP-C1, **uncommitted-before, unproven**:
- `modules/machinedrum/md_xport.s` (new, ColdFire DRAM unit): adds one eDMA burst to core 1 before stock state 5 of the host-transfer chain (0x40004aaa). Repointed by a `SymbolRef` at 0x400ab62e in manifest.py. Sends a block to X:0x7d40; payload B masks it to X:0x3d40/0x5d40 (the `mbox_a`/`mbox_b` allocations in layout.py). Block = seq, flags(bit0 sync), npkt, then packets [dest][count][hi lo]*. Test feed only: `md_feed` points at a stream (0xffff npkt ends). **Must save/restore TCD NBYTES around the burst** (stock state 5 reuses it; without this the frame engine dies after one frame). Done.
- `md_glue.asm`: applies the block at gfxproc (label `xpos`..`xnone`), new counters LSEQ NAPPLY NWORDS SLIPS GAPS BAD, clears both mailboxes in gboot, label `gdone` for sampling, fixed trigger only until the first block arrives. `md_image.py` fills the new placeholders. Glue is 324 words.
- `tools/verify/verify_md_transport.py` (new): replays c01_16's host stream (one chunk per OT frame, PAD=4 empty chunks first) through the image under the port and compares core 1's voice blocks with `md_replay --reloc --driver --boot`.
- `tools/harness/md_reference/md_replay.cpp`: `--boot` mode and `MD_REPLAY_OUT=<file>` block dump (rebuilt OK, out/md_reference).
- `tools/emu/ot_emu/main.cpp`: `--load-file addr=path[;...]` (port rebuilt in the isolated tree).
- Missing: a `make verify-md-transport` Makefile target, docs (MACHINEDRUM_MACHINE.md section, WORKPACKETS row, README, WP report), refhash and `make check REMIX=machinedrum` reruns.

## Result (300 frames, stress-project, isolated port)
Transport works: every block sent and taken in order, all words written, no refusals. 2481 of 2496 voice blocks bit-identical. **15 differ**: slot 4 from period 146 to 155, slot 8 from period 151 (the first non-silent period for each: 145 / 151; hits are word0 0x12 to slot 4 at period 144, 0x16 to slot 8 at period 147). So a later-triggered voice diverges from its trigger onward. Slot 0 and other slots match.

## Next step I was about to try (edit rejected, not applied)
Core 1 renders 3 idle driver calls (no writes) before the first block; the replay renders none. Hypothesis: driver/voice state (e.g. the half toggle, or state carried by idle empty-slot renders) differs. Add `MD_REPLAY_BOOT_IDLE=<n>` to md_replay --boot (n idle driver calls, then reset HALF to 0) and see whether the 15 blocks then match. Also consider: engine init for slots 4/8 is triggered later than for slot 0, so check whether core 1's state at that time (P-I buffers, X:0xa0-bf/Y:0x1e-21 MDSAVE) differs from the replay's. Both MDSAVE seeds are zero (checked).

## How to run
```
S=<scratchpad>/iso/emu/ot_emu   # port built from repo pin 8ccdd843 + tools/patches/dsp56300.patch (isolated; the vendor/ one is stale)
MD_EMU=$S OT_PROJECT=out/stress-project python3 tools/verify/verify_md_transport.py --frames 300   # ~45 s; omit --frames for the whole stream (~4190 frames, long)
```
Other gates still to rerun after glue changes: `tools/harness/md_reference/md_gate.sh`, `md_init_gate.py`, `make verify-md` (same MD_EMU), `tools/verify/verify_dram_boot.py`, `scripts/refhash.sh check` (24), ctest. `make check` fails on 6 Octakit remixes at the previous commit too (dirty submodule; pre-existing).

## Still open after WP-C1
WP-C2 parameter handlers (ColdFire), C3 machine registration (T5-T8 rule is superseded: MD is on T1-T4 core 1), C4, D sequencer/UI, E persistence/MIDI, E12 sample delivery, full-kit cycle budget (WP-A6), hardware qualification (user flashes), WP-R4 (user reruns scripts/setup.sh), stock-cost and D1 mix sign-offs. Scope reminder from the user: engines only, no MD master FX/mixer.
