# STOCK ANALYSIS FAST — experimental, hardware-unmeasured

Opt-in ColdFire patch for the 1.40C sample-analysis recurrence. No new effect,
DSP program, persistent state, or default remix change. This is a candidate,
not a claim of hardware headroom. See [the profile](../../docs/firmware/STOCK_PROFILE.md).

## Contract

The hook at `0x40098494` replaces two complete instructions (8 bytes) with a
jump and NOP. The build places a 378-byte routine in unused image space and
resolves the jump from its linker symbol. It returns at `0x400984be`.
`Linked.reference` checks the entire assembled unit's fingerprint, including
the stock body sourced at build time through `.incbin`; proprietary firmware
bytes are not stored in this repository.

The caller clamps its unsigned length to 768. For each group of eight, seven
counter decrements and branches are amortized. All loads, stores, MAC/MSAC
operations, shifts, XORs, and accumulator reads keep their original order.
The loop body does not read D7. The final decrement/read/branch sequence is
retained to preserve the outgoing CCR, including X. Lengths below eight use
the original recurrence, including its execute-once behavior at zero.

The patch uses no additional registers or stack space. Larger code footprint
and different interrupt interleaving still require system-level and hardware
validation; fewer instructions do not guarantee fewer cycles.

## Software checks

From the repo root, with the operator's own extracted 1.40C image:

```sh
make bus REMIX=stock-analysis-fast
python3 tools/verify/verify_stock_analysis.py stock-analysis-fast
python3 tools/harness/test_profile_stock.py
cmake --build out/emu -j8 --target ot_emu
python3 tools/harness/benchmark_stock_analysis.py \
  --project 'template_project/Drum Template TGM' \
  --frames 5600 --out out/stock-analysis-new-run
```

The new output directory must not already exist. The project is copied,
never edited in place. Effects and other template settings are retained, so
the card hash is part of the workload identity. `--card PATH` instead reuses
an existing `OCTABAM/POLYBENCH` fixture without modifying it.

The differential gate executes the actual linked bytes against stock for
all lengths 0..768, six signal/history patterns, and four MACSR modes:
18,456 cases. It compares D0–D7, A0–A7, SR, raw accumulators/extensions,
MACSR, MASK, and the sample/history buffer with surrounding guard words.
The full-playback runner then requires identical non-silent audio and an
identical stock PC profile in A/B/A. A failing comparison exits nonzero and
retains the evidence; it must not be reinterpreted as a pass.

`out/stock-profile/candidate-raw.bin` is the pristine stock image plus ONLY
this hook and linked unit, extracted and checked against the remixer build.
It is an emulator input, **not an OS-upgrade file**. Ordinary remixer output
also changes chooser/platform metadata; do not use that as an isolated
stock-versus-one-patch benchmark.

Before any hardware trial, resolve the open gates in the profile report and
follow [FLASHING](../../docs/remixer/FLASHING.md). No flashable release or
hardware performance claim is produced by these tests.
