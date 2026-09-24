# WP-C1: ColdFire record transport

- **Status:** done (emulator acceptance); unflashed.
- **Branch and commit:** `machinedrum` @ this commit.
- **Date:** 24 September 2026.
- **Agent:** Codex, main checkout, WSL.

## What was done

Completed the transport gate added by WIP commit `1f2245b`. The ColdFire
unit inserts an MD burst before stock host-transfer state 5; the core-1
glue takes packets from the current mailbox bank and writes the relocated
voice records. Word 0 retains the MD's trigger semantics. The test producer
feeds the captured host writes; live parameter production is still WP-C2/C4.

Added `make verify-md-transport`, a reference interpreter mode, and a
firmware-free arithmetic reproducer. The gate verifies complete reference
coverage and distinguishes post-feed rendering from repeated application
of the last chunk. It rejects an old replay binary lacking interpreter
mode and ignores ambient MD_REPLAY diagnostic overrides.

## Acceptance check

The port was rebuilt in `out/mdverify/isolated/emu` from DSP pin
`8ccdd843adda9c18fc232a2ca50d6caccbf3cb1e` with
`tools/patches/dsp56300.patch`, and mc68k pin
`4a6d0d17a1f2b30077ab726c27fe9bb770fa0456`.
The shared stale DSP vendor was not changed.

```
$ MD_EMU=$PWD/out/mdverify/isolated/emu/ot_emu OT_PROJECT=out/stress-project make verify-md-transport
T1 FX2 = MACHINEDRUM (0x1e) in 8 parts x 16 bank(s), page 1 [100, 0, 0, 0, 0, 0]
  [ok] load: the project loaded and the frames ran  frames 4200/4200
  [ok] xport: every chunk sent, none dropped  4192 of 4192 blocks sent (4 empty first), 0 dropped, feed ended
  [ok] glue: every stream block taken once, in order, every word written  chunks 0..4187 of 4188, 19335/19335 words, 1 gap(s) in the padding, refused 0, sync slips 1
  [ok] owner: the instance is T1's  owner offset 0x0
  [ok] voices: core 1's blocks equal the replay's  33503 of 33503 blocks bit-identical (20544 non-silent), 2094 of 2094 periods
  reference vs the Machinedrum's own output (c01_16): 31011 identical, 2492 differ (first difference at block 2)
  verify_md_transport: PASS
```

The capture ends without an output for its last slot 15. The comparison
covers every available reference block; it does not claim that missing
block. One empty startup chunk is lost before the glue begins, and one
sync mark resets the initial driver half. Neither occurs in the stream.

## Measured

✅ The complete stream traverses the image's ColdFire-to-DSP path:
4,188 stream chunks, 19,335 record words, 33,503 bit-identical blocks,
20,544 non-silent blocks. Evidence: `out/mdverify/full-transport.log`;
raw port samples and the replay dump are under `out/mdverify/xport/`.

✅ The initial 15 audio differences were not fixed by adding three idle
driver calls. Zero and three idle calls produced identical reference
audio. The idle diagnostic itself needed a fix: repeatedly stopping at
the same slot PC without executing could never reach the idle PC.

✅ The reference fork at `1378c430` miscomputes a firmware-free 48-bit
X/DO-loop probe. The expected sum follows directly from integer arithmetic.
Build the reproducer with:

```
cmake --build out/md_reference --target md_replay md_phase_probe -j2
out/md_reference/md_phase_probe --interpreter
out/md_reference/md_phase_probe --single-step
out/md_reference/md_phase_probe --jit
```

The first two exit 0 with `001800:000000`. Normal JIT exits 1 with
`0000c0:000000`. Its implementation defect has not been repaired here.
This confirms arithmetic failure in the region already isolated by WP-R3;
it does not close that packet's broader parity work.

✅ All 33,503 full-capture boot-replay blocks matched between the reference
interpreter and single-instruction JIT during diagnosis. The transport gate
uses the interpreter explicitly. Normal capture audio is not its oracle:
startup state and the affected JIT account for the reported 2,492 captured
output differences (slot 2: 142; slot 4: 698; slot 8: 1,652).

These measurements are also recorded in MACHINEDRUM_MACHINE.md section 12,
“WP-C1 record transport.”

## Other validation

- ✅ `sh tools/harness/md_reference/md_gate.sh`: all twelve relocated kits
  equal their plain JIT baselines. This is the historical relocation
  consistency check, not independent hardware-correctness evidence.
- ✅ `python3 tools/harness/md_reference/md_init_gate.py`: zero initialization
  differences on all twelve captures.
- ✅ `bash scripts/refhash.sh check`: all 24 cases bit-identical to the
  saved baseline. The script emits its existing GNU/BSD sed warning;
  the artifact/report manifests still compare equal.
- ✅ `ctest --test-dir out/mdverify/isolated/emu --output-on-failure`:
  9/9 tests pass; the REPITCH-patch test skips internally for a non-REPITCH
  image.
- ✅ `MD_EMU=$PWD/out/mdverify/isolated/emu/ot_emu OT_PROJECT=out/stress-project
  make verify-md`: 700 frames, 171/171 reference periods equal, 694/694
  non-silent audio read-back blocks match the glue.
- ✅ `MD_EMU=$PWD/out/mdverify/isolated/emu/ot_emu REMIX=machinedrum
  python3 tools/verify/verify_dram_boot.py`: loader once, fatal path zero;
  runtime bytes, sampled core-1 code and dispatcher entries match.
  The boot gate now honors MD_EMU for this remix.
- 🟡 `make check REMIX=machinedrum` builds the MD remix but stops in the
  global remix selftest on the six existing dirty-Octakit failures:
  kits, mods, octakit, ok-ms, rig-kits and rig-mods. All report
  `modules/octakit/upstream/runtime/runtime.S:438: value of fffffbbe too
  large for field of 1 byte`. The same failures were recorded before
  this work in HANDOFF-WP-C1.md. The remaining generic recipe steps were
  not reached; the MD and boot gates above were run separately.

Local logs: `out/mdverify/{full-transport,relocation-gate,init-gate,refhash,
ctest,image-gate,boot-gate,make-check}.log`. All generated firmware and
captures remain ignored.

## Retracted

❌ The old handoff's implication that the 15 differing blocks demonstrated
a transport/voice-state defect is superseded by the arithmetic reproducer
and the complete interpreter comparison.

❌ The transport gate's old description that capture-output differences
are only due to initial snapshot state was incomplete: the capture JIT
also changes the affected voices.

## Open and handover

- WP-C2/C4 must replace the test stream with the live record producer.
  `md_feed` currently points into the reserved DRAM arena; `--load-file`
  stages the fixture before the frame engine starts.
- The transport saves/restores eDMA NBYTES around its extra burst because
  stock state 5 reuses the previous state's value.
- Four empty startup chunks keep initial loss outside the fixture stream.
  Production startup synchronization and recovery are not qualified.
- This gate covers the captured valid packets, not malformed packet
  fuzzing, sequence-number wrap, or an unbounded live producer.
- The added FlexBus burst's hardware timing, full-kit budget, E12 samples,
  D1 mix decision and hardware qualification remain open.
- WP-R3's vendor JIT fix and WP-R4's shared-toolchain repin remain open.
  No shared vendor source, firmware bytes, samples or flash image was
  committed. The dirty Octakit submodule and base_firmware were untouched.
