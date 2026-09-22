# Tape Echo

`TAPE ECHO` replaces FX2 **SPRING REV**. It is a mono three-head tape echo
with stereo dry output, based on the compact, Space-Echo-inspired algorithm
in DJ-Mixer's `fx-dsp` project.

The port keeps one record head, playback heads at 1.00 / 1.97 / 2.96 times
the base repeat time, filtered feedback, a DRIVE-scaled cubic record curve,
a final safety limiter and one slow +/-8-sample wow oscillator. Selected
heads are power-normalised, so adding heads changes rhythm rather than level.
FREE and BEAT times share a tape-motor inertia model: changing TIME or SYNC
glides the playback heads into place instead of moving them instantaneously.

## Controls

The first page follows the stock Delay pattern: performance controls stay on
the normal FX page, with MIX in the final bottom-right position. Character
controls live on the FX setup/detail page.

| Page | Control | Meaning |
| --- | --- | --- |
| 1 | TIME | 46-231 ms in FREE; musical divisions in BEAT |
| 1 | FDBK | Regeneration; the tape curve and limiter keep overload bounded. |
| 1 | WOW | Slow common transport wobble; 0 is static. |
| 1 | HEADS | `1`, `2`, `3`, or the available combinations. |
| 1 | SYNC | `FREE` continuous time, or `BEAT` tempo-quantised time. |
| 1 | MIX | Dry/wet crossfade; 0 is exact dry. |
| Detail | DRIVE | Strength of the cubic record curve; 0 is clean. |
| Detail | AGE | Repeat bandwidth; fresh/bright at 0, worn/dark at 127. |

In `BEAT`, TIME selects eight divisions from `1/64` through `1/8` (including
triplet and dotted values). The stock frame builder already publishes
`tempo24` to `r6+$13`, so no tempo cave is required. The first head is capped
at 11,000 samples in this mode: the third head must fit in the same 32K word
line, so long divisions at slow tempos stop at roughly 249 ms.

## Deliberate constraints

This is not a line-by-line desktop port. The compact motor model uses Q15.8
head positions, derives velocity from the remaining error once per block, and
moves every head on every audio sample. Linear interpolation between adjacent
tape samples removes integer stepping; the motor settles with roughly a
1.5-second time constant. The desktop model's
second flutter oscillator, head bump, hiss and dropouts remain omitted. DRIVE
scales a compact cubic tape curve, while AGE sweeps the existing one-pole loss
filter. That keeps the four-insert budget practical without flattening the
character into one fixed voicing.

The effect owns `Y:0x4000..Y:0xBFFF`, the core-private FX2 buffer. Put it in a
dedicated remix; it is incompatible with any other buffer-owning FX2 effect
on the same core.

## Local gates and audition

`python3 tools/verify/verify_tapeecho.py` rebuilds the dedicated remix and
checks dry passthrough, head positions, detail controls and beat timing. It
also writes `out/tapeecho-technical-audition.wav`: four generated chord
strikes through all heads, wow and feedback, with no external dependency.
