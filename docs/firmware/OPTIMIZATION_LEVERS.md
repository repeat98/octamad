# Stock optimization: more levers (23 September 2026)

This adds to [OPTIMIZATION_PLAN.md](OPTIMIZATION_PLAN.md) and
[OPTIMIZATION_ATTRIBUTION.md](OPTIMIZATION_ATTRIBUTION.md). It is a
read-only pass over the stock profiles those documents already hashed. It
made no new emulator runs and no firmware changes. The profiles are:

| name here | profile (ignored `out/`) | frames | fixture |
| --- | --- | ---: | --- |
| idle | `out/optimization/workloads/initial/idle/profile.*` | 1,400 | all FX ids 0, no active tracks |
| FLEX-1 | `out/optimization/workloads/initial/flex-1/profile.*` | 1,400 | FX ids 0, one FLEX track |
| no-FX FLEX-8 | `out/optimization/aba-no-fx-flex8-5600/stock-a.*` | 5,600 | FX ids 0, eight FLEX tracks, TSTR OFF |
| pilot | `out/stock-profile/aba-fixed-5600/stock-a.*` | 5,600 | FX1 FILTER ×8, DELAY T1–T7, PLATE T8 |

All image hashes are those in the parent documents. The numbers are
**executed emulator instructions per 16-sample frame, not cycles**. Status
markers are as in `CHIP.md`. ✅ means read from our image or counted in these
profiles. 🟡 means inferred and not yet proven by a harness.

The pass found four exact fast paths on the deadline path. On the no-FX
eight-track fixture they are worth about 5,900 instructions per frame, 15%
of all ColdFire work. The attribution audit's loop unrolls are worth
120–256. The biggest one is in the stock delay, which runs its full
filter/mix path on every track even when no track has DELAY selected.

## 1. Which work sits on the frame deadline

The parent documents rank exclusive PC ranges. They leave open which
context each range runs in. For headroom, context matters most:
work at interrupt level 5 competes with the frame interrupt. Background
task work only uses time left over.

- ✅ **The stock delay runs inside an interrupt.** `0x40004840..0x40004bd0`
  is the ColdFire→DSP frame-transfer handler on DMA channel 0
  (`RECORDER.md`). It ends in `rte` and steps an eight-state machine at
  `0x46104d3e`. Its sixth state does `move #0x2500,sr` / `jsr 0x400031a0`
  / `move #0x2700,sr` (`0x40004b0e..0x40004b16`). The whole eight-track
  delay therefore runs at IPL 5, and the level-5 frame interrupt (vector
  `0x41`, `KERNEL.md`) cannot start until it returns.
- ✅ **Voice rendering runs inside the frame ISR.** The ISR's per-track
  loop `0x4000d3fc..0x4000d55e` calls each track's machine builder through
  the RAM tables `0x400d61d0` / `0x400d61f0`. The tables hold
  `0x400047f0` until a machine is loaded. FLEX, STATIC and PICKUP use
  `0x40004008` (`REPITCH.md`). `0x40004008` calls the renderer at
  `0x400041c4`. The same loop calls `0x400068e4` twice per track, at
  `0x4000d340` and `0x4000d36c`.
- ✅ **Sample analysis and the correlation search are background work.**
  Both are called from the priority-1 task `0x40098a5c` (`KERNEL.md`), at
  `0x40098cac` and `0x40098b46`. That task loops back at `0x40098cda`.

Instructions per frame on those two paths:

| scope | idle | no-FX FLEX-8 | pilot |
| --- | ---: | ---: | ---: |
| frame ISR body `0x4000aad0..0x4000d9b0` | 10,707 | 10,718 | 10,720 |
| + ISR callees verified above (builders, renderer, `0x400068e4`, the 64-entry LFO waveform table `0x400d6210` → `0x4000385c..0x40003b8e`) | 2,554 | 8,973 | 8,949 |
| + transfer handler `0x40004840..0x40004bd2` | 265 | 265 | 265 |
| + delay `0x400031a0..0x4000385a` (inside that handler) | 7,438 | 7,437 | 7,664 |
| **level-5 total, verified callees only** | **20,963 (94%)** | **27,393 (71%)** | **27,598 (67%)** |
| background: analysis + correlation (task `0x40098a5c`) | 0 | 7,313 (19%) | 7,838 (19%) |
| not assigned | 1,428 | 4,084 | 5,466 |

What this means:

- Any ColdFire delay effect runs inside the delay routine, so it spends
  the same level-5 budget as the frame ISR. The sum of the two has to fit
  in one frame. Every level-5 saving, whether in the ISR or in the stock
  delay, is room for delay development. Background savings are not. The
  only bracket on that budget so far is the Tape Echo freezes
  (`FAILURE_MODES.md`, "Freeze without an exception screen…").
- Which budget a new feature spends depends on where it runs:

  | feature | runs in | budget |
  | --- | --- | --- |
  | modulation (LFOs, mod matrix, morphs) | frame ISR, every frame. Stock's 24 LFOs (`0x4000cf84` loop) cost ~2,355 per frame, ~100 per LFO. Parameter smoothing and scene/crossfader morph run there too (`MIDI.md`) | level 5 |
  | ColdFire audio FX | delay routine, inside the transfer interrupt | level 5 |
  | MIDI FX on incoming MIDI | UART RX ISR → parser task → MIDI-in task `0x40005540` (priority 6) → main task (`MIDI.md`) | task time, per event. Level 5 only for a generator driven from the frame ISR |
  | DSP audio FX | DSP cores | DSP cycles (§3). No CPU lever buys them unless §3's coupling is measured |

  L1–L4 pay for modulation and ColdFire FX. On the no-FX fixture they free
  about 60 stock-LFOs' worth of time. Background savings (L5,
  `stock-analysis-fast`) pay for task-side work such as MIDI FX.
- `stock-analysis-fast` saves background work. Its 0.614% is real capacity
  but does not buy frame-deadline headroom, as `STOCK_PROFILE.md` already
  warns. Rank the next candidates by level-5 work.
- The "not assigned" column may hold more level-5 callees, such as
  `0x40020898` (a copy) and `0x40006820`. The verified sum is a floor.

## 2. New CPU levers: exact fast paths on the level-5 path

Each lever below takes a shortcut only when a precondition checked in
registers or memory proves the shortcut gives the same bits as stock. If the
check fails, the lever runs the original instructions. Each saving is an
instruction-count estimate. The shortcut's own cost is subtracted, but hook
and cave overhead are not. On hardware, only an A/B/A timing counts
(`HARDWARE_OPTIMIZATION_MEASUREMENT.md`).

| | lever | site | cost it targets (idle / no-FX FLEX-8 / pilot) | estimated saving 🟡 | applies when |
| --- | --- | --- | --- | --- | --- |
| L1 | delay: dry-only track fast path | seam `0x4000361a..0x4000377a` | 5,832 / 5,832 / 5,832 | ~500 per qualifying track: **~4,000 / ~4,000 / ~500** | a track's send, wet and feedback gains are zero at both ends of the ramp, both tap buffers are zero, and the filter state is a zero-input fixed point (in practice, any track whose FX2 is not DELAY) |
| L2 | renderer: unity-ratio phase step | `0x40008890..0x400088a6` (+ reverse twin) | 0 / 1,183 / 1,183 | **~1,000** with eight unity-rate voices | ratio == modulo (64-bit) and 0 ≤ phase < modulo on entry |
| L3 | builder: division loop that returns its own input | `0x4000416a..0x40004170` | 0 / 384 / 384 | **~290** | `a3@(4) == 0` path, divisor > 0, product in range |
| L4 | per-track slot check: hoist the early exit | `0x400068e4..0x40006b9e` | 1,136 / 1,136 / 1,110 | **~570** | the common exit to `0x40006b60` with `fp@(2) == 0` |

Combined estimate (instructions/frame, level-5):

| workload | L1 | L2 | L3 | L4 | total | share of all work | share of level-5 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| idle | ~4,000 | 0 | 0 | ~570 | **~4,570** | 20% | 22% |
| no-FX FLEX-8 | ~4,000 | ~1,000 | ~290 | ~570 | **~5,860** | 15% | 21% |
| pilot (7× DELAY) | ~500 | ~1,000 | ~290 | ~550 | **~2,340** | 5.7% | 8.5% |
| custom ColdFire delay on all 8 tracks 🟡 | 0 | ~1,000 | ~290 | ~570 | **~1,860** | — | — |

These estimates overlap nothing: L1 is inside the delay; L2 and L3 are in
the renderer and the builder; L4 is its own function. They can be added up.
The unrolls in the attribution audit also target different loops.

The last row assumes unity-rate FLEX voices. L1 applies only to tracks
that take the stock path with no delay, so it gives nothing when every
track runs custom code. Each track that does not saves ~500.

**The budget for delay development 🟡.** One figure from the Tape Echo
freeze reports is inferred: seven instances with every control moving
froze. That is ~29,300 instructions in the routine (PR #357's per-instance
figures) plus ~20,000 on the ISR side with eight FLEX voices, so
**~49,000 level-5 instructions per frame** is the rough ceiling. If it
holds:

- The delay routine today has ~29,000 to spend on all eight tracks. Stock
  uses 7,400 of it and a custom delay could use ~21,500 more, about 2,700
  per track above stock.
- L2–L4 add ~1,900 to that. L1 adds ~500 for each track not running a
  delay.
- Fewer voices leave more: the renderer and builder cost ~950 per FLEX
  voice.

The ceiling comes from one user's project and images, and the instruction
counts are not cycles. §4 proposes measuring it directly.

### L1 — the stock delay does its full work for tracks with no delay ✅ measured, 🟡 lever

**Measured.** The delay's per-track seam costs **729 instructions per
track per frame in every profile**: 5,832 per frame in idle (all FX ids 0),
no-FX FLEX-8, FLEX-1 and the pilot. Seven tracks with active DELAY cost the
same as zero. For each of the eight tracks, every frame runs:

- the 16-sample filter loop at `0x400036aa`, 21 instructions × 16;
- the 16-sample mix loop at `0x40003738`, 22 × 16;
- the setup between them.

The loops always run. The only thing FX2 changes is the gains. For a track
whose FX2 id is not 8, or whose byte `sp@(108)` is 7, `0x40003554..0x4000355c`
sets the four targets:

- dry `d7 = 0x7fffffff`,
- send `d6 = 0`,
- wet `fp = 0`,
- feedback `sp@(52) = 0`.

The previous values are loaded into `sp@(56/60/64/68)` from the state
record at `0x40003478..0x400034a0`, and the new targets are stored at
`0x40003562..`. With the send, wet and feedback ramps at zero, the mix loop
does three things:

- the output is the dry ramp × input only: `acc2/acc3`, then `movclr`;
- the ring write is `in×0 − tap×0 = 0`;
- the filter output is multiplied by zero before the mix, so it never
  reaches the output.

**The fast path**, at the seam Tape Echo already uses (`0x4000361a`),
checks four things for each track:

1. The send, wet and feedback ramps are zero at both ends: `d6 == sp@(60)
   == 0`, `fp == sp@(64) == 0` and `sp@(52) == sp@(68) == 0`. The dry
   ramp may move.
2. Both tap buffers are zero: tap A is 32 longwords at `a0+160`, and tap B
   is 32 longwords at `a0`. The filter reads tap B in place and overwrites
   it.
3. One zero-input step of the filter leaves the four state words at
   record `+28..+40` unchanged. The state is `x = d2·x`, `y = d1·y +
   d0·(x′ − x)`, computed with the stock EMAC operations. By induction the
   whole loop then leaves them unchanged.
4. Nothing else: the TAPE on/off byte does not matter, because both loop
   variants multiply zero taps.

If all four hold, the fast path runs only the dry multiply with the stock
ramp and the same `macl`/`movclr` pair, under the routine's MACSR `0xa0`.
It then advances `0x80006180` by 68 and continues at `0x4000377a`. The
buffer at `a0[0..31]` ends as zeros, which is what stock's ring write
leaves there, because tap B was already zero. The DMA reads, the prefetch,
the `0x800000e8` toggle and the commit do not change.

**Why the condition says "fixed point" and not "zero".** The EMAC
truncates towards −∞ (MACSR `0xa0`: fractional, saturating, R/T = 0).
Take a one-pole filter with 0 < d2 < 1 and x = −1 LSB. `floor(d2 × −1)`
is still −1, so it never decays. A track that ever ran a delay with
signal can keep a −1 state forever. "State == 0" would miss those tracks.
"State unchanged by one zero-input step" catches them, and is exact.

**Estimate 🟡.** The fast path should cost about 230 instructions against
729:

- about 10 for the gain checks;
- about 72 for the tap check (eight `movem.l` plus `or.l`);
- about 20 for the fixed-point step;
- about 112 for the dry loop at ~7 per sample;
- about 10 to exit.

That saves ~500 per qualifying track: ~4,000 per frame with no DELAY
anywhere, 10% of no-FX FLEX-8 and 18% of idle. On the pilot only T8
qualifies, saving ~500.

**Risks and obligations.**

- The fast path must leave `acc0..acc3` at 0, as stock's final `movclr`s
  do. MACSR's flag bits may differ in between. The routine restores MACSR
  on exit (`0x4000384e`), and the harness must show that nothing reads the
  flags before that.
- Tape Echo owns the same seam, and two detours at one site are refused by
  the build. So the fast path has to be the stock fallback *inside* Tape
  Echo's hook. For remixes without Tape Echo, a standalone owner of the
  site works. Tape Echo's decline path already costs +264 per frame on
  eight stock tracks. Routing it through L1 would make its non-TE tracks
  cheaper than stock.
- Oracle: Tape Echo's complete-routine harness (`COLDFIRE_DELAY.md` §3),
  with the transitions this lever creates:
  - DELAY→off with a live tail;
  - off→DELAY;
  - a state stuck at −1;
  - taps that turn nonzero partway through the ring;
  - freeze;
  - the TAPE byte both ways.

  Compare audio, ring bytes, the 68-byte records, `0x80006180` and EMAC
  state after every track.
- Negative control: fill one tap longword with 1 and require a mismatch
  when the check is removed.

### L2 — the renderer's phase accumulator at unity rate ✅ measured, 🟡 lever

**Measured.** The loop `0x40008890..0x400088a6` iterates once per output
sample per voice: 128 iterations per frame with eight voices. It subtracts
the 64-bit ratio, adds the modulo while the phase is negative, and bumps
the position. This is `TIMESTRETCH_PIPELINE.md`'s phase accumulator; add
`0x400` to that document's addresses. It costs 1,183 instructions per frame
in no-FX FLEX-8 and the pilot, from 15.5 entries per frame. The wrap
instruction at `0x40008898` executes exactly as often as the subtraction
(128 each), so every sample wrapped exactly once. Every voice in these
fixtures runs at unity rate.

**Lever.** If ratio == modulo (hi and lo) and 0 ≤ phase < modulo on entry,
each iteration takes the phase negative once and restores it exactly. After
`n` iterations, the phase is unchanged and `a2@(68)` has grown by `n`. The
fast path does three things:

- one `add.l` to the position;
- the same phase words stored back;
- the loop's exit state reproduced: `d4 = −1` via a final `subq` from
  0, which also sets X as stock leaves it, plus `d0..d3`.

On any other input it runs the stock loop. The reverse-direction twin
(`TIMESTRETCH_PIPELINE.md` `0x40008a42`, here `0x40008e42`) takes the
same change.

**Estimate 🟡.** About 12 instructions per entry, so ~1,000 saved per frame
with eight unity-rate voices, inside the frame ISR. A general closed form
for non-unity 32-bit ratios is possible but needs a 64-bit product and a
divide. Call that L2b: prove L2 first.

**Coverage the fixtures lack:** non-neutral pitch, reverse, TSTR
NORMAL/BEAT (ratio from project/sample tempo), retrigs and slices. A voice
start may enter with phase ≥ modulo, which is why the precondition checks
the range and does not assume it.

### L3 — a division loop that recomputes the count it was given ✅ measured, 🟡 lever

**Measured.** In `0x40004008`, when `a3@(4) == 0` (taken on all 15.5 entries
per frame), three steps run:

1. `0x40004126` loads `d6 = sp@(44)`, the chunk's sample count.
2. `mulu.l` makes it `count × d5`, where `d5 = a3@(28)` is the tempo
   `<< 4`.
3. `0x4000416a..0x40004170` counts subtractions of `d5` until `d6 ≤ 0`.

For a positive count and divisor without overflow, the answer is `count`,
with a final `d6` of 0. The loop costs 384 instructions per frame on
eight tracks: 3 × 128 iterations.

**Lever.** Guard on `d5 > 0`, `1 ≤ count` and a range that keeps
`count × d5` below 2³¹. The chunk is at most 16 samples, and the tempo
word's range is to be proven. When the guard holds, set `a0 = count` and
`d6 = 0`. Otherwise run the loop. It saves ~290 per frame, inside the frame
ISR. The oracle is exhaustive over `count` 0..16 and a sweep of `d5`,
including values with bit 31 set, comparing `a0`, `d6`, CCR and memory.

### L4 — `0x400068e4` computes everything before taking its usual exit ✅ measured, 🟡 lever

**Measured.** The ISR calls `0x400068e4` 16 times per frame, twice per
track. That is 1,136 instructions per frame in idle and in no-FX FLEX-8,
and 1,110 in the pilot. Every profiled call does the same three things:

- saves 11 registers;
- runs 53 instructions that compute addresses, including five `muls.l`,
  a table lookup through `0x100b14cf`/`0x46c82456`, and three stack
  locals;
- takes the branch at `0x400069a2` to `0x40006b60`.

The code at `0x40006b60` is 18 instructions. When `fp@(2) ≤ 1`, it clears
bytes `+1` and `+2` of the `0x800049d8 + 168·track` record, then returns
−1 through `0x40007954`. `a2` and `fp` are two 84-byte per-track records,
each in one of two banks chosen by bit `track` of `0x80004f18`. On that
path only `fp` and the argument are read. `sp@(48)` is read only if
`fp@(2) != 0`, at `0x40006b9e`, and that address never executes in these
profiles.

**Lever.** Compute `a2` and `fp` first, about 12 instructions. If
`a2@(2) != 1` and `fp@(2) == 0`, do the `0x40006b60` block and return −1
without the 11-register save. Otherwise run the original. That saves ~35
instructions per call, ~570 per frame, in the frame ISR. Skipping two
11-register `movem`s saves more in cycles than the instruction count
shows.

**Obligation:** prove the skipped reads have no side effects:
`0x100b14cf` is outside SDRAM (`0x40000000..`) and on-chip SRAM
(`0x80000000..`). Compare the return value, both records and the
stack-frame words the caller reads.

### L5 — background: the analysis task runs with TSTR OFF ✅ measured, 🟡 investigation

The analysis/correlation pair costs 1,182 + 286 per active FLEX track per
frame in FLEX-1, and 7,313 per frame in no-FX FLEX-8. **Every fixture here
has TSTR OFF.** What the task computes, and who reads its results, is not
established (`EMU.md`). If its output is unused while TSTR is OFF, gating
it would be the largest single CPU saving in this pass, 19% of all work.
But it is background: it frees capacity for tasks, not deadline headroom.

First step: find the consumer of the task's outputs with a write watch
under the port, then run a TSTR NORMAL/BEAT fixture. Do not grow
`stock-analysis-fast` further until that is known.

### Examined and not recommended (so nobody re-derives them)

- **LFO depth-0 skip**, loop `0x4000cf84..0x4000d09a`: 2,120 per frame
  plus ~235 in the waveform callees, 24 LFOs. The apply step reads out the
  accumulator under MACSR `0x60`. In fractional mode, S/U means 16-bit
  rounding on read-out (see `CLAUDE.md`). The step also clamps twice with
  `sats` against two accumulator-held bounds, so depth 0 does not make the
  stored word an identity. Random waveforms may carry state in their
  callee. Skipping the phase advance is never exact. What remains is a few
  instructions per LFO: not worth a hook.
- **Parameter-frame smoothing memo**, `0x4000cbfc..0x4000cc62` and
  `0x4000ce5a..0x4000cefc`: 4,057 per frame, constant. The first loop's
  coefficient word is itself advanced every block, `a2@ += (rate × tempo)
  << 3` at `0x4000cc36..0x4000cc4c`. "Inputs unchanged since the last
  frame" therefore needs a zero rate, proven for every writer first. The
  attribution audit's unroll (≤120) stays the bounded experiment.
- **The copy at `0x40020898`** (718 per frame in no-FX FLEX-8) is already a
  four-way unrolled longword copy.

## 3. DSP levers

The same profiles carry per-core DSP PC counts. Core 0 runs payload A;
its poll is `P:0x4b..0x53` (DSR2). Core 1 runs payload B; its poll is
`P:0x57` (port ready). Disassembly: `tools/build/dsp_disasm_all.py` into
`out/dsp/payload_{A,B}.asm`.

| instructions / frame | idle | FLEX-8 (short) | no-FX FLEX-8 | pilot |
| --- | ---: | ---: | ---: | ---: |
| core 0 non-poll | 12,308 | 12,604 | 12,691 | 33,817 |
| core 1 non-poll | 7,954 | 8,177 | 8,285 | 26,520 |

- ✅ **Stock's resident DSP work barely depends on activity.** Eight
  playing tracks add ~3–4% over an idle project on each core, so an
  idle-skip cannot help a busy project. On hardware, stock's own share is
  ≈1,410 of 4,532 cycles per sample per core (`CHIP.md` §2, burn-probe
  measured). That share is fixed cost as far as this data shows.
- ✅ **Idle tracks take a *more* expensive path than playing ones.**
  Core 0 `P:0x6cc` and its twin at core 1 `P:0x48c` run only in idle: a
  16-sample, 15-instruction polynomial loop per track, entered when the
  track's first state word at `x:(r5)` is ≤ 0 (`P:0x6bc`). It costs ~967
  per frame per core with four idle tracks, and 0–1 when they play.
  Playing tracks take the 2-instruction loop at `P:0x6e1` instead. What it
  computes is not established. If its output is a pure function of state
  that does not change while idle, a memo is exact. That would recover up
  to ~60 instructions per sample per core in sparse projects.
- ✅ **FX1 FILTER is the largest stock DSP cost in a normal project.** In
  the pilot, four FILTERs per core add ~18,200 instructions per frame on
  core 1, which carries no PLATE. That is ~285 per sample per instance in
  the emulator, against 192 cycles per sample measured on hardware
  (`CHIP.md`). The extra is dominated by 16-sample loops: payload B
  `P:0x74b`, `0x75a`, `0x78c` and `0x79d`. There are also two
  straight-line blocks at `P:0x71b..0x73a` that run 64 times per frame.
  First map whether those blocks recompute values that stay constant
  while the knobs rest; that would be the only exact skip. Beyond that, a
  cheaper bit-identical FILTER would be a port-grade rewrite. The schema
  refuses stock ids by design (`CLAUDE.md`, "An FX2 id is also an FX1
  id"), so this needs a decision before any code.
- 🟡 **Host-port waits may tie CPU lateness to DSP time.** Core 0 spins at
  `P:0x97` on `HSR_HTDE`: 70 per frame in idle, 37 in FLEX-8. Core 1 spins
  at `P:0x8d` on `y:$ffffd3` bit 1: 252 and 153. In the lock-step emulator
  these are small. On hardware they depend on when the ColdFire services
  the transfer, and the delay routine runs inside that handler. **Until a
  hardware burn sweep shows it**, assume no CPU lever creates DSP headroom
  (`CHIP.md`'s rule). The sweep is the burn knob on core 0: stock delay
  against eight Tape Echo instances. If the ceiling moves, the two budgets
  are coupled, and L1–L4 help the DSP too.
- Do not touch: the polls, the per-sample SRC/FIR blocks (`P:0x25d..0x28e`
  on core 0), cross-core handshakes (assignment I).

## 4. Order of work

1. **L1 before the delay unroll (assignment E).** It is exact, 15× larger
   and on the level-5 path. Build it as the stock fallback inside Tape
   Echo's seam hook, then as a standalone module for remixes without Tape
   Echo. Keep the unroll as a fallback.
2. **L2, L3, L4 as assignment D's candidates**, one at a time. Each has a
   small, exhaustively testable state contract. They are the levers that
   still help when every track runs a custom ColdFire delay.
2a. **A ColdFire burn knob, to measure the level-5 budget directly.**
   Built on 23 Sep 2026 as the CF BURN module
   ([modules/cfburn](../../modules/cfburn/README.md)). The remixes are
   `cfburn` (stock) and `bamsep26-burn` (the rig, beside SEND's DSP BURN).
   - **What it is:** a register-only spin at the end of the delay routine,
     640 instructions per BURN step. Under the port it is proven inert and
     exact over the complete routine.
   - **How to use it:** sweep it on the unit until the audio breaks. That
     gives the spare level-5 cycles in a given project. The difference
     between two images is each lever's real saving, with no timer or GPIO
     needed.
   - **What it does not replace:** the ISR observer. But it answers "how
     much room is there for delay code" directly; every other number here
     only estimates that.
   - **Not yet swept on hardware.**
3. **Fixtures B needs for these levers:**
   - non-unity pitch, reverse, TSTR NORMAL/BEAT;
   - DELAY with SEND 0;
   - a track switched DELAY→off with a live tail (the −1 fixed point);
   - Tape Echo ×6 plus two stock tracks;
   - an ISR-observer run (the attribution audit's edge→ack / entry→exit
     observer), so level-5 savings can be shown as ISR duration, not
     only as totals.
4. **L5's consumer hunt** (read-only, port write watch) before more work
   on `stock-analysis-fast`.
5. **DSP:** one hardware burn sweep for the coupling question (§3) before
   any DSP patch. Then the idle-path semantics (`P:0x6cc`) if sparse
   projects matter.

What would falsify this ranking:

- a hardware timing showing the host-DMA handler runs in a context where
  the frame interrupt can preempt it;
- an ISR observer showing the level-5 paths are not where frames overrun;
- a Tape Echo freeze that persists when the per-frame work is cut.
