# Upstream PR readiness — 28 September 2026

The current audition is locally tested, not hardware-qualified. See [CPU.md](CPU.md)
for the corrected stock comparisons, all 15 complete firmware load scenarios,
measurement limits and the existing fully-wet PLATE fixture issue. The DSP
scheduling optimization preserves exact kick output/state, and the build now
preserves the shared DARK routine inside the harvested SPRING region. Keep both
new identity gates when transferring the module; the old audition image fails
the stock DARK comparison.

## Focused branch

Do not open an upstream PR directly from the development branch. At inspection,
HEAD was `1cfd91e1667254ff02120b8b6798adf4c7d6a55a`, 113 commits ahead of current
upstream main `e15d081b3d3be9e7a257a78a5525684527b521f0`, including unrelated
Machinedrum work. The Analog BD implementation itself is largely untracked.
Prepare a fresh isolated branch and transfer only the module, remix, DSP build
integration, relevant gates, documentation and reproducible benchmark tooling.
Push that branch to `origin` (repeat98/octamad); the PR targets sambanks/octabam.

`tools/build/ab_image.py` imports `md_image`, which does not exist on upstream
main. Extract the small payload-record/read/write helpers it needs into focused
shared or Analog BD build code; do not bring the Machinedrum integration along.
Pin image identity before/after that extraction. The local DSP opcode-cache
bounds fix was needed even for stock boot; split it into a prerequisite fix or
explain and independently test it if included.

Exclude unrelated working changes, `.gradle`, proprietary SDK/install files,
Drumazon exploration utilities not needed by the shipped gates, and all generated
firmware, binaries and captures. Keep the original fitted coefficients and their
provenance. The legacy ColdFire synth is still linked for shared defaults/helpers
and the old fallback/reference paths; separate those small shared functions from
the retired synthesis implementation as part of scope cleanup if it can be done
without changing the proven image behavior.

## Budget and acceptance

The DSP source engine is integrated through a CF_PATCH module. Generic
`make cycles` and acceptance `pressure_profile()` currently inspect `Module.dsp`
and miss this work. Do not cite their zero/N/A result as load coverage. Review
source-engine registration/claims and connect explicit source-load evidence to
the acceptance report (or explicitly report this gap). The new 808/909 instruction
ceilings guard code growth but cannot certify chip timing.

Keep the two-instance limit. Before claiming hardware safety, test two 909s on
T1/T2 and T5/T6, then split cores, with dense retriggers, parameter locks, the
remaining tracks streaming/timestretching, and the heaviest allowed FX layouts.
Use the repo's documented hardware burn/headroom procedure. Firmware execution
on the host cannot price real contention or guarantee physical deadlines.
Resolve or explicitly qualify the fully-wet PLATE reference fixture; the passing
PLATE chain measurements are at MIX 64, not 127. DARK and the heaviest measured
stock effect, DJ EQ, were exercised successfully in the full firmware.

## Gates on the final upstream base

After the focused branch is based/rebased on current main, run the exact list
from `make reach BASE=upstream/main`, including acceptance with a local stress
project. Current development results are not post-rebase results. Build changes
also require the trusted refhash matrix and per-remix image identity; any retained
emulator fix requires its emulator gates. List each actual command/result in the
PR and retain PORT proof until hardware evidence exists. No rebase, focused
commit or upstream PR was performed as part of this benchmark run.
