# CPU optimization: hardware acceptance protocol (draft)

Status: preparation only. No Octatrack is currently available, and the
`stock-analysis-fast` saving has **not** been measured on hardware. This is a
measurement design, not permission to flash a unit. The operator must review
the build, recovery path and measurement setup before a trial.

## Before choosing an observer

Record the exact Octatrack model/revision, firmware version, recovery and
backup procedure, available audio interface, MIDI clock source, and whether
debug/trace or spare GPIO access actually exists. Use one or more copies of
real overload projects in addition to the controlled workloads. Freeze the
projects, samples, event schedule, audio gain and sample rate; hash every
input, image and measuring executable. Retain failed and interrupted runs.

Do **not** assume a DMA timer is spare. Stock MIDI RX uses the counter at
`0xfc07000c` to timestamp MIDI Clock bytes (see [MIDI.md](MIDI.md)); PIT0 is
the scheduler timer and PIT1 is used by storage (see [KERNEL.md](KERNEL.md)).
Merely reading a known monotonically advancing counter may be feasible, but
resetting/reconfiguring one, claiming a different timer free, or inserting a
GPIO toggle needs a separate ownership audit and a readback/hardware test.
No CPU timer frequency or cycles-per-instruction conversion is assumed here.

## A meter that needs no timer: CF BURN

The CF BURN module (`modules/cfburn/`) avoids the timer question. It is a
knob-set spin of known length at the end of the stock delay routine, at
IPL 5: 640 instructions per BURN step and 10 per FINE step. Under the port
it is proven inert and exact against stock. Swept on the unit until the
audio breaks, it gives the spare level-5 time in a project. Two things
follow from that:

- **A patch's saving.** The difference in the ceiling between images A
  and B is the patch's saving on the hardware.
- **A feature's cost.** The ceiling drops by what a new feature costs.

For the DSP cores, SEND's page-2 BURN plays the same role. The
`bamsep26-burn` remix carries both. The meter is in burn-loop units:
cycles, if the loop runs at one cycle per instruction, which is inferred.
It cannot show a starved background task, or a deadline at a different
point in the frame. Not swept on hardware yet.

## Paired images and observer checks

Build stock A and single-candidate B from the same frozen source and
toolchain. The two images must differ only by the optimization and any
unavoidable placement effects; if an observer is needed, use the *same*
minimal observer in A and B. Save a binary-diff/placement explanation and
run every relevant software gate first. Give each packaged image an
unambiguous identifier. Raw `MAIN_OS` images are not flashable updates;
follow [FLASHING.md](../remixer/FLASHING.md) and verify the package before
considering use on hardware.

Before treating an observer as neutral, check that it does not change audio,
MIDI-clock interpretation, scheduling, interrupt priority, DMA, ring state,
or the optimization's live registers/flags. Measure its overhead and counter
wrap behavior, including nested interrupts and preemption. A control build
with the observer on/off should quantify observer perturbation. If these
checks fail, use an external trace/debug method or report that exact timing
is unavailable; do not disable interrupts for cleaner numbers.

## Run and acceptance

Use A/B/A in alternating order over identical event schedules, with warm and
cold runs and repeated loops/trigs/FX transitions. Capture at least:

- Exclusive target-routine time and invocations, distinguishing ISR time
  from preemptible background time.
- Frame service entry-to-exit time, arrival-to-service latency, missed/late
  frames and backlog; median, p95, p99 and maximum with sample counts.
- Audio and behavior, including tails, MIDI-clock response and state at
  transitions. Establish analog A/A capture repeatability before setting
  an audio tolerance; analog audio need not null byte-for-byte.

Keep CPU and DSP measurements separate. An emulator instruction reduction
does not establish a hardware cycle saving or extra DSP headroom. Report
uncertainty, observer overhead, frequency and units, run-to-run variance,
small-workload regressions, and any dropped/invalid samples. Accept a patch
only if the saving is repeatable above measurement noise with no correctness
or deadline regression. Otherwise record **not established** (or reject a
regression), even if the emulator's mean instruction count fell.

No hardware acceptance can be completed until the operator and instrument
are available. The current pilot is a software result only; see
[STOCK_PROFILE.md](STOCK_PROFILE.md).
