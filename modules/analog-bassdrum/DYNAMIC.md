# Part-resident engine loader (experimental)

The engine catalogue lives in the platform's reserved SDRAM. A Part chooses
which engines each DSP core needs. The planner shares code/tables between
tracks using the same engine, allocates different engines consecutively, and
uploads them through spare words in the ordinary source-control records.
No engine code or engine-specific tables are resident in the boot upload.
The browser and saved 808/909 ids are unchanged.

This is a loader foundation with the existing two engines, not hardware
qualification or an external plugin/file format. It does not enlarge DSP RAM.

## Memory

- The platform reserves 10,487,808 bytes from the sample/recorder arena.
  The current combined runtime is about 16 KB. The two DSP boot uploads and
  their packed staging buffers remain separately declared allocations.
- The engine catalogue is 15,544 bytes at `0x40c00000`; packed staging is at
  `0x40d00000`. Each has a 1 MiB cap and is checked against the complete
  platform layout. About 7.58 MiB remains above the highest current allocation;
  this is SDRAM, not DSP-executable memory.
- Each core retains a 385-word dispatcher/loader/shared desk in SPRING's
  existing donor. There are 643 words for active engine code. The preserved
  35-word stock reverb helper remains outside that pool. No additional stock
  effect is harvested.
- The 808 takes 246 program / 1,024 table words; the 909 takes 377 / 1,425.
  Both fit together, leaving 20 program words. Repeated instances share code
  and tables; four different engines would each occupy code/table space.
- Private X holds 768 common table words at `0x2840`, a 3,008-word engine-data
  pool at `0x2b40`, four 64-word voice blocks at `0x3700`, and eight loader words
  at `0x3800`. No shared FX window is claimed.
- The current ABI allows 48 voice-state words, 12 controls and a trigger word
  per track. The catalogue/planner support 128 engine ids and four distinct
  engines per core, subject to the sum fitting both pools. Only the 808 and
  909 are presently implemented and exposed in the browser. Future engines
  need a package builder, controls/UI integration, and their own sound gates.
  A library can exceed the active code pool; the builder checks individual
  packages, while the Part planner checks combinations.

## Transfer and activation

A change in bank/Part identity or any track's selected engine invalidates the
plans. Ordinary parameter changes do not reload code. The current prototype
reloads the whole affected Part selection rather than retaining individual
cached packages. T1–T4 use core 1; T5–T8 use core 0. Only selected synth tracks
carry transfer packets, so a core with fewer synth tracks loads more slowly.
A core with no synth tracks has no executable synth calls; its old bytes may
remain as unreachable cache until the next load overwrites them.

BEGIN mutes that core's synth source calls and clears the transfer checksum.
Packets then write at most 16 words to bounded P/X destinations, carry increasing
sequence numbers, and accumulate a 24-bit checksum over headers and payloads.
Initial voice states and four per-track entry pointers follow the code/tables. COMMIT enables synthesis
only after the sequence and checksum agree. A malformed transfer locks the
core muted until a new BEGIN. Ordinary sample sources and the stock AMP/FX
chain still run. P writes cannot reach the resident loader or reverb helper;
X writes cannot reach common tables or loader status.

Measured packet counts are 99 for an 808-only core, 133 for 909-only and
213 for the mixed set, including state and dispatch initialization. At one
packet per selected synth track per 16-sample frame this is approximately
36/48 ms with one synth track, or 9.1/12.3/19.6 ms with four. These are
protocol frame counts, not measured hardware load latencies.

Loading is currently driven by source rendering. There is no separate idle-time
prefetch and no guarantee of a seamless Part transition. One pending trigger per
track is retained during loading and emitted at offset zero once ready; multiple
hits while loading collapse into that one pending hit. Already-running voices
are reset on a Part/engine-set change. Activation is per core, not an atomic
cross-core musical boundary. These are explicit prototype limitations.

Code packages are assembled at a reference address and checked at a second P
and X origin. Only additive relocation sites are accepted. Resident desk calls
stay fixed per core. The library is generated from our source; it contains no
copied stock firmware or reference samples. The platform checks the library's
preboot hash before the renderer can use it.

## Evidence

- The native ColdFire gate emits real transfer packets for 808-only, mixed,
  909-only and reordered Parts on both cores; unchanged Parts do not reload.
  It checks invalid/oversized selections stay muted and queued triggers survive.
- The DSP loader gate consumes those tagged packets through the real source
  seam, checks every relocated code/table word and shared dispatch entry,
  protects resident/stock P and common tables, and rejects bad counts, sequence
  numbers, out-of-range and in-range wrong destinations, data and commit checksums on both cores.
- The dynamic audio gate compares both models at different P/X placements on
  both cores: 16 cases / 3,670,016 frames, every output sample and every
  block-boundary state word identical to the existing implementations.
- The full-image port gate verifies the actual ColdFire-to-DSP transfer,
  deferred initial hit, source reference, stock AMP/FX and MAIN output.

No timing or safe live code replacement on hardware has yet been established.
The loader uses stock-precedented P-store and indirect-call instruction forms;
that does not qualify the new scheduling/protocol on a real unit. Keep using
the previously tested image for hardware until this prototype is qualified.

Four 900-frame full-chain cases with eight synth tracks and sixteen DJ EQ
instances passed on this image. Peaks (executed instructions/sample over the
whole four-track loop): eight 808s 3938.625 / 3939.9375; mixed 808/909
3785.8125 / 3787.125, cores 0 / 1. Loading defers first attacks and changes
voice alignment, so these mixed-case peaks are not a sound-preserving CPU
speedup comparison with the older timing. The known eight-909/heavy-FX limit
remains; these runs do not establish arbitrary eight-engine combinations.

The native ColdFire planner gate measured peak instructions per call: 282 for
a resident selection, 819 for BEGIN/planning, 2,113 for relocated P packets,
600 for X packets, and 307 for COMMIT. These are emulator instruction counts,
not hardware cycle measurements. Synthesis itself runs on the DSP.

## Validation of this prototype

Based on upstream `68f7fc78` with its default QUICK test policy:

- `scripts/refhash.sh check`: all 24 configurations bit-identical.
- `make bus REMIX=analog-bassdrum`: pass.
- `OT_PROJECT=out/analog-bassdrum/ui-fixture make check REMIX=analog-bassdrum`:
  all runnable checks passed, including all six module image gates. This is
  the default check, not a claim that the optional FULL suite ran.
- `.venv/bin/python tools/verify/verify_analog_bassdrum_cf.py`: pass, including
  the final planner instruction-count instrumentation.
- Four `benchmark_analog_bd.py` cases (`eq-808eight-core0`,
  `eq-808eight-core1`, `eq-mixedeight-core0`, `eq-mixedeight-core1`): pass.
- `python3 tools/verify/verify_docs.py`, generated-source `--check`, and
  `git diff --check`: pass.

Frozen local image: `out/analog-bassdrum/dynamic/final.os`, SHA-256
`4519406f07dd21ff70e3f15f6bce0ce9e3d51940fd9a5ad1dc2a33f693caf3a7`.
