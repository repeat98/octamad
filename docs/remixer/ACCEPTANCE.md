# Module acceptance evidence

`make check REMIX=<name>` is the development floor. It can skip checks
when local prerequisites are absent. `make accept` is the stricter
evidence-producing workflow: a nonzero command, failure marker, timeout,
missing prerequisite, or applicable `[SKIP]` prevents acceptance.
A verifier's explicit `[N/A]` means the tested behavior is absent, not
that its tools or fixture are missing.

## Run locally

Use your own stock 1.40C, initialized submodules, the documented assembler
toolchain, DSP host, emulator venv and a worktree-local `make emu-cf`
build. Nothing flashes hardware. Any remix:

```sh
make accept REMIX=<name> STRESS_SOURCE="/path/to/local/project"
# Several remixes in one run: the remix-independent half of make check once
make accept REMIXES="<name> <name> ..." STRESS_SOURCE="/path/to/local/project"
# Or supply a project you prepared for this remix:
make accept REMIX=<name> OT_PROJECT="/path/to/local/project"
# Optional fresh destination and per-command timeout:
make accept REMIX=<name> OT_PROJECT="/path/to/local/project" \
  ACCEPTARGS='--out out/acceptance/review-1 --timeout 3600'
```

`STRESS_SOURCE` names a locally saved project whose `.work`/`.strd`
files seed the fixture; `tools/harness/stress_project.py` derives the
placement from the remix's selection and writes eight FLEX tracks, three
LFOs per track, dense parameter locks and four Parts/patterns
([STRESS_PROJECT](../../tools/harness/STRESS_PROJECT.md)). FX2 slot 0
on T2 and on every server's track carries no lock or LFO: `verify_set`
sends CC 40 there and reads the value back. The generated fixture is the
pressure fixture: a remix with no DSP module of ours has nothing to
place, and one whose profile is blocked (below) has a module with no
`dear` to place it at, so either takes the source project as-is (the
report says so). Only the generator is
distributed; project bytes stay local. The sample path is
project-relative, so `verify_set` can find and stage the generated audio.

Acceptance runs these stages, serially:

1. `preflight`, per remix: prerequisites and the pressure profile (below).
2. `fixture`, per remix: generate or fingerprint the project fixture.
3. `check_shared`, ONCE for every remix past stage 2: `make check-shared`,
   the remix-independent half of `make check` (the ledger selftest, the
   knob census, the isolated module gates that build their own image);
   its one result is every report's `check_shared` gate and its log sits
   above the reports.
4. `check_remix`, per remix: `make check-remix` with the exact remix, build
   and project (its build, cycles, dirty state, init regs, DRAM boot,
   labels, its own module gates, menu, the set under the port, USB);
   refuse missing evidence even when a verifier returns zero.
5. `cycles`: save the restored shipping image's fingerprint and price the
   selected remix. Reject a static estimate above its declared DSP wall.
6. `pressure_price`: price the selection's layouts; reject any layout
   over the wall.
7. `pressure_render`: render the six dearest and four seeded random
   layouts per core using deterministic input on all eight tracks, dirty
   memory and write guards, `--jobs` layouts side by side (the cores, at
   most 8; the meter is an instruction count, so a loaded machine changes
   no result). Record the per-layout flags and instruction meters.

A failed stage stops that remix's dependent stages, which stay `not_run`
in its report; a failed or skipped `check_shared` stops every remix. Use
a fresh output directory for each run; old output is never accepted as
new evidence. Existing checks and pressure tools still use their
worktree's `out/`, so run one acceptance job per worktree.

## Coverage is explicit

The pressure stages (5, 6) and the fixture's knob values read each
module's dearest settings from its manifest (`schema.Module.dear`: the
mode the pricer calls the worst loop, work-gating knobs at maximum,
checked against the module's own knobs when the manifest loads). The
profile is **ready** when every DSP module in the selection declares
one, **blocked** with the missing modules' names otherwise (the check,
cycles and project stages still run and their evidence is in the report;
the two pressure stages are recorded `blocked` by name), and
**not applicable** for a selection with no DSP module (the image, oracle
and project gates still apply). A module is never rendered at default
settings and called covered; a module PR that wants the pressure stages
adds `dear` beside its gates.

Declared on 27 Sep 2026: SEND, DELAY SERVER, REVERB SERVER, CHARACTER,
SPECTRUM, MODULATION. Blocked until their authors declare one: MINIVERB,
TAPE ECHO, EUCLID, CF METER.

A generated project's automated playback checks A01 through the existing
`verify_set`. A02-A04 exist for further testing; this workflow does not
claim automated pattern/Part transitions, long soaks, or recording/storage
stress. Operator-supplied projects are fingerprinted but their workload
coverage is the operator's responsibility.

A result below the static DSP wall is not proof of real-time headroom.
The counter omits contention and has known error. ColdFire instruction
counts, DSP static costs and emulator meters are different measurements.
No calibrated CPU deadline or storage budget is introduced by this PR.

`passed` means the required local stages passed for these inputs.
It does not mean safe on every combination or verified on hardware.
Reports always carry `hardware_validated: false` and the known
limitations. Hardware captures, listening and timing remain separate
evidence; unresolved upstream burst failures are not waived.

## Report v2

A run of one remix writes `out/acceptance/<timestamp>/report.json`, logs
and local artifacts; a run of several writes
`out/acceptance/<timestamp>/<remix>/report.json` each, the shared half's
`check_shared.log` beside them and `summary.json` (remix to status) over
all. [acceptance.schema.json](acceptance.schema.json) defines the
versioned interchange envelope. Consumers must check `schema_version`
before reading it: v1 had one `check` gate where v2 has `check_shared`
and `check_remix`.

- `status`: `running` until finalization, then `passed`, `blocked`, or
  `failed`. A pass is published only after the measurement files validate.
- `gates`: command, exit code, elapsed time, log references, skip/N/A
  messages and one of `passed`, `failed`, `blocked`, `not_applicable`,
  `not_run`. Stages without a command carry their reason instead.
- `provenance`: repository revision, dirty state, source/diff hashes,
  submodule revisions, tool fingerprints, Python/platform, stock and
  tested image hashes. Uncommitted source is identifiable too.
- `modules`: selected keys, kinds and manifest hashes.
- `fixtures`: relative filenames and hashes, never project/audio bytes.
  Referenced samples outside the project (including their `.ot` metadata)
  are fingerprinted too; missing referenced files have null hashes.
- `parameters`: build/bank and pressure sampling settings.
- `measurements`: existing cycle/price/render JSON, preserving its units
  and per-layout findings rather than translating it to a CPU percentage.

Firmware, generated projects, audio and raw logs remain local in ignored
`out/`. Do not attach the output directory to a PR. Review reports/logs
before sharing: filenames and paths can reveal local project information.

## PR checks

`make test-acceptance` runs firmware-free negative controls: successful
commands that skip, stderr skips, swallowed failures, timeouts, a module
without `dear`, missing prerequisites, stale destinations, absent
meters, incomplete sampling and budget overruns; and the `make reach`
path classifier against a fake registry. The CI job tests this machinery
only; a green job does not replace a local acceptance report. CI also
prints `make reach`'s gate list for every pull request.

Submit the command, source revision, report status, coverage, skipped or
blocked stages, and outstanding hardware evidence with a module PR.
A new module's gates, `dear` and behavioral tests belong in that same PR.
