# CF BURN — the ColdFire cycle-burn knob

The ColdFire twin of the DSP rig burn (`CHIP.md` §2, "The burn knob is a
cycle meter"). It is an FX2 effect with no sound of its own. Its two
page-1 knobs set how long a register-only loop spins at the end of the
stock eight-track delay routine. That routine runs at IPL 5 inside the
ColdFire→DSP transfer interrupt, so it shares the frame deadline with the
frame ISR and every ColdFire effect (`OPTIMIZATION_LEVERS.md` §1). Sweep
the knob on the unit until the audio breaks. The setting just below the
break is that project's spare level-5 CPU.

| | |
|---|---|
| FX2 id | `0x1f`, row "CF BURN" (abbr `CPUB`) |
| hook | `0x40003826`: displaces `lea 116(%sp),%a2` / `moveq #3,%d1`, then continues at `0x4000382c` |
| knobs | **BURN**: 64 iterations per step. **FINE**: 1 iteration per step. Every track carrying CF BURN adds its own |
| one iteration | 10 instructions: 8 register `add.l`, `subq`, `bne`. No memory access and no EMAC |
| one BURN step | 640 instructions; ~640 cycles if the loop runs at one cycle per instruction (🟡 V4e timing, not measured) |
| cost when idle | +75 instructions per frame with no CF BURN track, +5 per CF BURN track (✅ port) |
| DSP side | a five-word passthrough; the stock delay treats the id as "no delay" |

## What is proven, and what is not

`tools/verify/verify_cfburn.py` runs in `make check`. It executes the
complete stock delay routine on the built image and on pristine stock,
frame by frame, with live DELAY tracks beside the burn. ✅ under the port:

- **Identical to stock.** On-chip SRAM, the stack, every ring word written
  and every returned register are the same. This holds with and without
  CF BURN tracks, and for knobs from 0 to 127 on any track.
- **Exact cost.** The routine costs exactly `75 + 5·tracks + 10·N` more
  instructions than stock, where `N = Σ(BURN·64 + FINE)`. Only the current
  control snapshot counts, and only each knob's high byte.
- **The checks can fail.** The comparison reports a single flipped state
  bit, and stock-against-stock fails the count.

A staged-project integration check (23 Sep 2026) used the stress fixture under the ColdFire port for 100 frames. BURN=10 executed 62,080 loop iterations (97 active frames × 10 steps × 64 iterations); BURN=0 executed none. This checks project loading, control staging and the hook together. The first three frames preceded the active effect state.

Not measured: cycles. The port has no caches, bus timing or DMA timing.
The knob measures only when it is swept on the unit. Both the ColdFire
clock (264 MHz, `CHIP.md` §1) and the loop's cycles per instruction are
inferred.

## Images

```bash
make image REMIX=cfburn BUILD=N              # stock + CF BURN: the base firmware's margin
make burn-image REMIX=bamsep26-burn BUILD=N  # the rig + SEND's DSP BURN + CF BURN
```

- `cfburn` keeps every stock effect except DARK REV, whose DSP words hold
  the passthrough. A project under test must not use DARK REV.
- `bamsep26-burn` is `bamsep26` plus one CF BURN row. `make burn` adds the
  SEND page-2 BURN on both DSP cores.
- `make check REMIX=<name>` first. Flash as `docs/remixer/FLASHING.md`
  says.

## Measuring a project (the stress procedure)

For the rig's stress project (`tools/harness/STRESS_PROJECT.md`), use the
`bamsep26-burn` image:

1. Generate a measurement copy: `python3 tools/harness/cfburn_stress.py --burn 0 --out out/cfburn-stress/project`. The ordinary stress project locks and modulates T8's FX2 slot 0; that would drive BURN even when its saved value is zero. The copy removes those overrides, assigns CF BURN to T8's FX2, and keeps its other LFOs active. Core 0 keeps its SENDs on T6 and T7. Put every burn knob at 0. Do not save the project with a burn knob up.
2. **ColdFire.** Play the pattern. Raise BURN one step at a time and
   hold each step for a few seconds. At each step, switch patterns (A01 to
   A04) and turn a knob, because edits are the expensive case. Stop at the
   first artifact: a click, dropout, stutter, UI stall or freeze. Call
   that value B. Return to B−1, then raise FINE the same way until the
   artifact returns, at F.
   - **Margin** = (B−1)·640 + F·10 burn instructions.
   - A freeze means the setting was past the ceiling. Power-cycle.
3. **DSP.** Put CF BURN back to 0. Sweep SEND's page-2 BURN on T2 (core 1)
   and then on T6 (core 0), one at a time. Each step is 24 cycles per
   sample on that core, so the spare is 24 × the last clean value
   (`CHIP.md` §2).
4. Write down the image, the project, the pattern, both values and the
   symptom. Repeat each sweep: one sweep is not a measurement.

**Using the numbers for a new feature.** Measure the ceiling with and
without the feature, on the same project and image family. The drop is
the feature's real cost on that processor. A feature *survives* the
stress project if the ceiling with it stays above zero. It survives
*comfortably* if some margin is left for what the stress project does not
cover: recording, card streaming, long runs.

**Predicting before flashing** (🟡 calibration, not yet done):

- Run the same project under the port with `ot_emu --work-profile` to get
  its level-5 instruction count.
- Then `cycles per instruction ≈ (frame cycles − margin) / level-5
  instructions`, where a frame is ≈ 95,800 cycles if the core runs at
  264 MHz.
- A new feature's instruction count from the port, times that ratio,
  predicts its cycles. Confirm with a sweep.

## Limits

- **The burn runs at the end of the delay routine.** It measures room for
  more level-5 work. Frame-ISR work (modulation) competes for the same
  frame. But if the binding deadline turns out to be the DSP transfer
  rather than the frame, a burn here would read differently from the same
  work in the frame ISR. That is not measured. A second site would settle
  it.
- **It burns every frame, whatever else happens.** Features whose cost
  spikes under edits need the sweep done while editing (step 2).
- **Audio breakup cannot show a starved background task.** A starved UI or
  MIDI task makes the unit sluggish without clicks, so watch for that
  separately.
- **CF BURN takes one FX2 slot**, and its hook adds 75 instructions per
  frame.
