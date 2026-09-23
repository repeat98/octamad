# Validation gate audit (23 September 2026)

Baseline: `ccb11fb2b4f54634bff42f635b467a6321ac4659` in the Ubuntu WSL
checkout. This audit did not run a shared `make bus`, `make check`, CMake build,
or emulator workload. The gate inventory below is from the committed pilot's
ignored logs; the assembler reproductions were run separately under
`out/optimization/validation/`.

## Gate inventory

| Gate | Evidence | State |
| --- | --- | --- |
| Candidate image build / cycle report | `out/stock-profile/make-check.log` lines 1–56 | Passed; image composed, 437 changed bytes |
| Dirty-state DSP verification | Same log, lines 57–61 | Passed with zero renders because this remix has no added DSP effect |
| Tape Echo CPU / Miniverb gates | Same log, lines 62–65 | Skipped because those modules are absent |
| Remixer selftest, slot and initialization checks | Same log, lines 66–224 | Passed |
| Replacements check | Same log, lines 225–265 | Failed in six Octakit-carrying remixes; non-Octakit remixes passed |
| EMAC, peripherals, RTOS, DSP CTest | `out/stock-profile/emulator-tests-fixed.log`: 4/4 | Previous pass; not rerun in this audit |
| Analysis differential | `out/stock-profile/differential-gate.log`: 18,456 loop cases across four MACSR modes; register, EMAC, guarded RAM comparison | Previous pass; not rerun |
| Profile accounting | `docs/firmware/STOCK_PROFILE.md`: four tests | Previous pass; not rerun |
| `make check REMIX=stock-analysis-fast` | `out/stock-profile/make-check.log` | Failed in `verify_replaces`: six Octakit-carrying remixes cannot assemble the unchanged Octakit runtime |
| Firmware label check | Same log, line 181 | Skipped because `.venv` is absent |
| labels / mode names / CC page 2 / hidden engines | `Makefile` lines 190–199 | Not reached after the earlier failure; would skip with absent `.venv` |

The CTest log does not establish the whole gate as passing. There are also
separate workload and physical timing gaps in `STOCK_PROFILE.md`.

## Isolated Octakit failure

The installed `m68k-elf-as` is a symlink to Ubuntu's
`m68k-linux-gnu-as` (GNU binutils 2.46). The installed cross GCC reports
15.2.0 and targets `m68k-linux-gnu`; the Octakit recipe pins GCC 16.1.0,
and its README records a byte-identical build with Homebrew 16.2.0.

The runtime builder invokes:

```
m68k-elf-as -march=cfv4e -I modules/octakit/upstream/runtime \
  -I modules/octakit/upstream/runtime -o OBJ \
  modules/octakit/upstream/runtime/runtime.S
```

The same command with an object under `out/optimization/validation/`
reproduces:

```
runtime.S:438: Error: value of fffffbbe too large for field of 1 byte at 00000441
```

The line is `bne.s gk_copy_payload_long_loop`. The loop label is globally
exported but only six bytes behind the branch. The tiny
`tools/harness/validation_branch_global.s` reproduces the failure when that
exported label is at section offset `0x436`: the assembler attempts an
offset near `-0x43c`, as though the target were zero. The otherwise identical
`tools/harness/validation_branch.s` places a local alias at the same address
and branches to it; binutils 2.46 succeeds and emits `66fa` (`bnes` back
six bytes). Thus the behavior is sensitive to target symbol binding in this
installed assembler; its attempted negative offset tracks the section
position rather than the six-byte branch distance. The minimal source also
assembles with the global target at section offset zero. We have not isolated
the precise assembler pass responsible or proven which other versions behave
the same way. The loop itself is short enough for the one-byte displacement.

Reproduce in the checkout without touching the shared build:

```
mkdir -p out/optimization/validation
m68k-elf-as -march=cfv4e -o out/optimization/validation/global.o \
  tools/harness/validation_branch_global.s  # expected failure on binutils 2.46
m68k-elf-as -march=cfv4e -o out/optimization/validation/local.o \
  tools/harness/validation_branch.s         # expected success
m68k-elf-objdump -m m68k:cfv4e -dr out/optimization/validation/local.o
```

The supported Homebrew toolchain has **not** been tried in this WSL checkout,
so we cannot say whether it solves the issue. Recommended first action is to
use a toolchain/version whose target and runtime build identity match the
documented oracle, then rerun Octakit's own byte-for-byte verifier. If that
toolchain still fails, propose the local branch alias to Octakit upstream;
after an upstream release, update the submodule pin and prove raw runtime,
packed runtime, append, and reference hashes identical. Do not silently
rewrite the upstream source in this checkout or relax identity checks.

## Environment skip

There is no `.venv` in the checkout and `uv` is unavailable on this WSL PATH.
`make emu-setup` is `uv sync --extra emu`, so it cannot complete in the current
environment. Provision `uv` through the documented host setup, run
`make emu-setup`, and then rerun the four conditional ColdFire gates. Until
they actually execute, report them as skipped. The Python 3.14.4 system
interpreter and C++ emulator do not substitute for those Unicorn checks.

## Next validation pass

After the coordinator releases the shared build slot and the toolchain is
resolved, rerun the four CTest gates, the analysis differential gate,
`python3 -m unittest tools.harness.test_profile_stock`, and
`make check REMIX=stock-analysis-fast`; preserve exact versions and full logs.
Add a guest-executed save/restore and interrupt-preemption regression covering
all four accumulators, both extension pairs, MACSR, MASK, CCR/X and saved
registers before treating emulator state equivalence as exhaustive. Existing
integer-mode assertions cover two accumulator indices and one extension
write/read pair at a time; they do not cover full ISR preemption.
