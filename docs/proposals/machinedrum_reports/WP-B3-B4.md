# WP-B2 (image side), WP-B3 and WP-B4: the Machinedrum on core 1 in an OT image: report

- **Status:** review. Every gate passes under the port on the repo's
  dsp56300 pin. It needs the user's decisions below and a flash.
- **Branch and commit:** `machinedrum` @ this commit
- **Date:** 24 September 2026
- **Agent:** Claude (Opus 5.5), main checkout, WSL

## What was done

`make bus REMIX=machinedrum` now builds an image that loads the relocated MD
voice DSP into core 1 at boot and runs it as the FX2 effect MACHINEDRUM
(id 0x1e) on T1–T4. `tools/build/md_image.py` runs last in `build_bus.py`
and does five things:

1. It patches both payloads.
2. It builds one combined core-1 upload: payload B's own records, then the
   MD's records from `payload_B.mem` (without the sine), then the glue, then
   B's terminator.
3. It carries that upload as a new **pre-boot** payload of octabam's loader.
   `loader.S` depacks it before the boot-continue call.
4. It repoints the boot's `pea 0x400f59ef` (0x40001ed4) at the upload's
   uncached copy.
5. It assembles and disassembles the core-1 host,
   `modules/machinedrum/md_glue.asm`. The host holds:
   - the MD's boot (`gboot`);
   - the dispatch entries (`gfxinit`/`gfxproc`);
   - the fixed trigger;
   - the 16-slot mix;
   - core 0's narrowed clear (`gaclr`).

On core 0 the id runs a passthrough stub (`md_stub.asm`).

The port gains `--dsp-sample`, a per-arrival memory sampler. Its stall check
now counts sequential RAM reads as progress, which the loader's 300 KB hash
needs. `verify_dram_boot.py` checks the pre-boot payload, and
`tools/verify/verify_md_image.py` (`make verify-md`) is the end-to-end gate.

## Acceptance check

End to end on the stress project, with the port built from the repo's pin
(`8ccdd843`) plus `tools/patches/dsp56300.patch`, in an isolated tree:

```
$ OT_PROJECT=out/stress-project MD_EMU=<isolated>/ot_emu make verify-md
T1 FX2 = MACHINEDRUM (0x1e) in 8 parts x 16 bank(s), page 1 [100, 0, 0, 0, 0, 0]
  [ok] load: the project loaded and the frames ran  frames 700/700
  [ok] glue: gfxproc ran every frame  1052 calls
  [ok] owner: the instance is T1's (gfxinit on T1's FX2)  owner offset 0x0
  [ok] trigger: the OT's trigs on T1 reached slot 0 as TRX-BD  3 trig(s), slot 0 engine 0x11
  [ok] reference: slot 0 == the MD's own render until the OT retriggers it  171 of 171 periods bit-identical (.../iso/emu/ot_emu)
  [ok] audio: T1's post-FX2 read-back is the Machinedrum mix  694 of 694 non-silent read-back blocks are glue output blocks
  verify_md_image: PASS
```

The same gate on the main checkout's port (vendored dsp56300 still at
`c051afad`, WP-R4):

```
  [FAIL] reference: slot 0 == the MD's own render until the OT retriggers it  25 of 171 periods bit-identical (/home/jannikassfalg/octamad/out/emu/ot_emu)
```

The boot (`make check REMIX=machinedrum` runs this):

```
$ REMIX=machinedrum python3 tools/verify/verify_dram_boot.py
  [PASS] verify_dram_boot: machinedrum boots to the handoff; loader ran 1x, its fatal hang 0x
  [PASS] verify_dram_boot: core 1 P:00591 == the core-1 upload (64 word(s))
  [PASS] verify_dram_boot: core 1 P:01f00 == the core-1 upload (64 word(s))
  [PASS] verify_dram_boot: core 1 P:34000 == the core-1 upload (64 word(s))
  [PASS] verify_dram_boot: core 1 P:36000 == the core-1 upload (64 word(s))
  [PASS] verify_dram_boot: core 1 dispatch init == the core-1 upload (1 word(s))
  [PASS] verify_dram_boot: core 1 dispatch proc == the core-1 upload (1 word(s))
```

The build:

```
$ make bus REMIX=machinedrum
  machinedrum: core-1 upload 300,282 B (stock B 77,061 + MD 18 records + glue 960 words), packed 155,204 B; the sine record is dropped (gboot builds it); glue 160 words at P:36000 (gboot 36086, gaclr 36097); fixed trigger: c10 TRX-BD, 14 words
    P:00046 06cf00 000049 5e5c00 5e5d00 -> 0bf080 036097 000000 000000  A boot clear -> jsr gaclr (keeps 0x34000-0x37fff: the MD's window code)
    P:0009b 60f400 038000 -> 60f400 036320  A per-frame read of X:0x38000-f -> the glue's zero words (the sine lives there)
    X:0025c 034000 -> 030000  A slot table: T8's FX2 takes T7's base (0x34000 is the MD's)
    P:00047 06cf00 00004a 5e5c00 5e5d00 -> 0bf080 036086 000000 000000  B boot clear -> jsr gboot (the MD's init; its Y and the sine are not cleared)
    X:00215/00235 core 1 dispatch: id 0x1e -> 36000/36005, the other 31 ids -> the null stub 00588/00589 (T1-T4's effect code is the MD's)
    poke 0x40001ed4: 400f59ef -> 48b00000  DSP boot: payload B's upload reads the combined core-1 blob
    poke 0x4000050c: 4eb940001e50 -> 4eb94010fdf0  boot -> octabam loader
  platform loader: payloads machinedrum core-1 upload, append 155,576 B at 0x4010fdf0
out/mainos_bus.bin: 1,268,136 bytes, 329 changed (+155,576 B octabam loader + payloads (machinedrum core-1 upload) appended)
```

The other gates, run on this commit:

- `make check REMIX=machinedrum`: every gate passes except the six
  Octakit remix builds (kits, mods, octakit, ok-ms, rig-kits, rig-mods).
  Those, and `verify_octakit`, fail with `modules/octakit/upstream/runtime/
  runtime.S:438: Error: value of fffffbbe too large for field of 1 byte`.
  The error is identical when built from the previous commit's build files,
  so it predates this commit: that submodule is checked out at a commit
  other than the recorded one and was left alone. `make verify` stops at
  that gate, so the gates after it were run one by one: all exit 0.
- `sh tools/harness/md_reference/md_gate.sh`: exit 0, all twelve moved
  results equal their plain baselines. `md_init_gate.py`: exit 0, zero
  differences on all twelve.
- `scripts/refhash.sh`, baseline from the previous commit's `build_bus.py`,
  `loader.S` and `platform_build.py` with this commit's module set: **ALL
  24 CASES BIT-IDENTICAL**. Against the previous commit as a whole, every
  case differs by the new module's registration only: MACHINEDRUM joins
  "not in this remix", and its id 0x1e aliases to the remix's fallback (11
  bytes per image). Every new module has done the same.
- The port's own tests (`ctest` in `out/emu`): 9 of 9 pass.

## Measured

All of these are under the ColdFire port. None is hardware. Section 12,
"Core 1 in the OT image", holds the same list.

- ✅ **Payload B's startup clears the MD's ground.** P:0x40–0x4a zeroes
  Y:0x4000–0xbfff and 0x38000–0x3ffff (the window, through Y) after the
  upload. That range holds the MD's Y tables, the P-I buffers, the driver
  state and the sine. Read from `out/dsp/payload_B.asm`; the glue's `gboot`
  replaces the loop.
- ✅ **Payload A clears 0x30000–0x37fff after B's upload.** A's window code
  waits for a host word (`brclr #HSR_HRDF` at P:0x30010) before jumping to
  its P:0x40 clear. B's entry at 0x38000 calls A's 0x3008a and 0x30082,
  so the ColdFire must send that word after B has booted. Measured under the
  port: before the narrowing, the window read all zero after boot; after
  it, core 0 P:0x34000 holds the MD's code at the handoff.
- ✅ **0x38000–0x3800f is a per-frame core 1 → core 0 mailbox.** Payload B's
  frame loop re-enters P:0x4b every frame: it parks its Y:0x280 words there,
  waits for core 0, and restores the saved words at P:0x172. Core 0 copies
  X:0x38000–f to its Y:0x280 at P:0x9b and mixes it with an input gain.
  Stock core 0 read zeros on 305 of 305 frames (`--dsp-sample 0:9b`). The
  MD now points that read at 16 zero words. The sine's first 16 words, lost
  in the boot handshake, are restored once by `gfxproc`.
- ✅ **The OT trig on a core-1 track** is bit 16 of word $1e of the track's
  state block (`x:(x:$419)+$1e`). Bits 8–11 are the trig's sample offset.
  Measured with `--dsp-sample 1:198` over 1200 frames: T1–T3 set it on
  frames 3, 347, 692 and 1036; T4 on frames 3, 347 and 1036.
  **It marks a sample voice starting**: a T1 with no staged sample never
  sets it (0 trigs). The fixed trigger therefore needs a sample on the
  MD track.
- ✅ **Bit-exact against the MD reference.** With the repo's dsp56300
  pin, slot 0's 32-sample blocks equal c10's own slot-0 output for 171
  consecutive periods (5,472 samples). They diverge at period 171, where the
  OT's second trig retriggers slot 0 and c10 does not.
- ✅ **A stale emulator mis-renders the MD.** The port built from
  `c051afad` (the main checkout's vendor, WP-R4) diverges at period 25,
  sample 27. It renders the exact negation of the reference (0xbf5fc0 for
  0x40a054) until period ~31, and again from period 48. The following were
  checked and are not the cause:
  - low-memory garbage: the c10 replay with X:0–0xff and Y:0–0x13f
    poisoned, except the MD's 36 words, gives 3400/0;
  - the other slots: c10 triggers only slot 0 before block 3400, and its
    ENG and persistent words start at zero, as ours do;
  - the replay's interpreter: 4200/0.

  *Inferred:* one of the upstream dsp56300 fixes between the two pins,
  probably the CCR overflow flags, given the sign flip. Not bisected.
- ✅ **T1's audio is the MD mix.** All 694 non-silent T1 post-FX2
  read-back blocks are blocks the glue left in X:0.
- ✅ **Cost** (instructions from the interpreter, not cycles; the window's
  +1 cycle per fetched word is not modelled):
  - `gfxproc` (driver plus mix, one TRX-BD voice and 15 empty slots): mean
    3,276, max 5,401 per call.
  - The driver alone: 5,261 on a frame that renders slot 0, 3,200 on the
    other half.
  - Core 1 per frame (P:0x167 → P:0x34e): **11,642** mean, 12,370 max,
    against 22,890 for the skeleton on the same project (stock FX running
    on T1–T4).
  - A full 16-voice kit is not measured here (WP-A6).
- ✅ **The pinned `dsp_asm` also drops a parallel move.** It encodes
  `mac y0,x0,a x:(r1)+,x0 y:(r4)+n4,y0` as the single word 0x012685,
  losing the parallel move entirely. It refuses `clr a` with an XY move.
  The glue keeps ALU ops and moves apart; `md_image.py` refuses
  max/dc/illegal and any su/uu `mac`/`mpy` in the disassembly.

## Retracted

- ❌ "0x38000–0x38012 is payload B's entry, dead after boot" (`layout.py`'s
  stock costs). The entry is dead, but 0x38000–0x3800f is the live
  per-frame mailbox above. Corrected in `layout.py`.
- ❌ "T8's FX2 limited to memoryless effects". T8's FX2 now shares T7's base
  (0x30000), so two memory effects on T7/T8 share one buffer. That is
  audible, not a crash.

## Open and handover

- **Decisions for the user:**
  - Sign off the stock costs in `layout.py`: T7/T8 FX2 share a buffer;
    T1–T4 have no stock FX; core 0's narrowed clear.
  - **D1**, the mix: `gfxproc` implements option A's shape with fixed gains
    of 1/4 and L = R. No level or pan per part yet.
  - **WP-R4**: rerun `scripts/setup.sh` in the main checkout, or the port
    there renders the MD wrongly from period 25 on.
- **Hardware:** unflashed. The pre-boot payload adds 155,576 B to the image
  and about 100,000 words to core 1's boot upload. Whether the unit's
  bootloader and upload timing accept that is unmeasured.
- **The trigger is a proof, not the design.** It keys on a sample voice
  starting on the MD track and plays one fixed TRX-BD record. WP-C1 (the
  record transport) replaces it.
- **Not done:** machine registration (WP-C3); the ColdFire parameter
  handlers (WP-C2); the sequencer, persistence and MIDI; the E12 sample
  delivery (WP-R1); the full-workload cycle report (WP-A6); the hardware
  qualification.
- **MD on two core-1 tracks:** the last track to init owns the instance,
  and the other runs its audio through untouched. Admission (WP-E3) is not
  done.
- **Inputs the build needs:**
  - `out/machinedrum/build/payload_B.mem`, from the user's MD update;
  - c10's `log.txt`, for the fixed record.

  `make bus REMIX=machinedrum` stops with a message without them.
