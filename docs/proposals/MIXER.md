# The mixer: master inserts, two returns, sends on the tracks

A proposal (29 Sep 2026, Jannik Aßfalg / repeat98 with Claude). Nothing here is
built. Status key as `docs/firmware/CHIP.md`: ✅ read from our image or measured ·
🟡 measured under the port or the harness only · ❓ inferred, with what would
falsify it.

## 1. The ask

1. Two insert effects on the master, without turning T8 into a master track
   (Oxide, `modules/oxide` on branch `oxide`, is the first candidate).
2. Two separate return channels, each able to host digital effects.
3. A return is fed by **per-track sends** (set on the tracks, not on the mixer
   page) and/or by the physical inputs A/B and C/D.
4. A return can send to itself, for hardware effect loops now and a 100 % wet
   delay later.
5. Stay inside the processing limits. Expected side effect: less DSP, because
   the expensive effects (reverb) stop running as inserts.

## 2. What the firmware already has

✅ = read off `out/dsp/payload_A.asm` on 29 Sep 2026 unless marked.

- **A 10 × 2 mixer.** Core 0's mixdown, P:0x238–0x2d4, sums ten stereo
  sources (T1–T8 plus the two input pairs) into two buses, CUE (`Y:0x40 + 20j + k`
  gains) and MAIN (`Y:0x4a + 20j + k`), 16 samples per frame, about 50
  instructions per sample. Track k's block is `X:$204 + 32k`, L and R interleaved
  (`docs/firmware/COLDFIRE_PORT.md` O23, ✅ under the port). One mono gain per
  source per bus per sample, ramped across the frame from the ColdFire's values;
  pan is upstream, in the block.
- **Two paths, one exit.** The plain path (P:0x259) and the MASTER TRACK path
  (P:0x292, bit 10 of `x:(r6+$7e)`: T1–T7 summed into `X:0x4278..` for T8 to
  process, main = slot 7) both end at **P:0x2d5**.
- **After the exit:** P:0x2d5–0x2eb packs the main pair and the input pairs into
  `X:0x4700..` (the recorder's sources, and where USB audio reads);
  P:0x2ec–0x309 mixes a 16-word block from `Y:0x280` into both buses with two
  gains that it squares (words `+0x32`/`+0x33` of the r4 block) and then the cue
  mix follows (P:0x30a–0x359).
- ❓ **`Y:0x280` is the core 1 → core 0 mailbox.** Payload B parks its `Y:0x280`
  words at `X:0x38000–0x3800f` every frame and core 0 copies them back
  (`docs/proposals/MACHINEDRUM_MACHINE.md`, "0x38000–0x3800f is a live
  core 1 → core 0 mailbox", 🟡 under the port: stock reads zeros). That the
  block is the metronome click and that the two gains are the metronome
  CUE/MAIN volumes is the leading reading, not settled: `LEVEL_LAW.md` §3 (28 Sep)
  says the bytes could equally be the LEVEL knobs. Falsifier: poke either pair
  under the port and see which output moves.
- **Timing.** ✅ Under the port the mixdown lands about half a sample before the
  output DMA enters the half it wrote; every effect and voice call runs after it,
  for the next frame (O23: DSR2 `0x807d`/`0x807a`, 1,748 / 522 / 1,690 / 509 of
  4,469 frames). That margin is the reason a master insert cannot run inline.
- **The stock DELAY is not on the DSP** (`COLDFIRE_DELAY.md`): it runs over
  SDRAM rings after the read-back, so nothing placed on the DSP hears it.

## 3. The design

```
sources                                       buses
T1..T8 (after FX2, LEVEL, mute)  ─┐
IN AB, IN CD                     │
RET A, RET B                     ├─▶ MAIN ─▶ [INS 1]▶[INS 2] ─▶ MAIN VOL ▶ out   (core 0, one frame late)
click / MD  (the P:0x2ec path)   │
                                 ├─▶ CUE  ─▶ cue out   (hardware send)
                                 ├─▶ AUX A ─▶ RET A [FX1][FX2]   (core 1)
                                 └─▶ AUX B ─▶ RET B [FX1][FX2]   (core 0)
```

- **The mixer becomes 12 sources × 4 buses.** Track sends are the track rows into
  AUX A and AUX B; input sends are the IN rows; the CUE bus keeps its role
  (hardware send / cue mix). A source's send into a bus is one more gain in the
  same ramp the stock mixer already runs.
- **A return is 100 % wet.** No dry path, no MIX knob. The dry stays on the track.
  A return's own send into its AUX is the feedback path: a delay on RET A with
  RET A → AUX A raised is a dub loop independent of the delay's FDBK.
  Delay into reverb is RET A → AUX B.
- **Hardware loops** need no new mechanism: source → CUE → the user's pedal → IN
  CD → back in. IN CD's own CUE gain is the feedback control (levels: the
  stock law `(L/128)²` per stage, `LEVEL_LAW.md` — a loop closed through one stage
  at 127 loses 0.136 dB per pass).
- **Effects on a strip.** A strip's chain is a normal effect chain (same calling
  convention, same modules) on the strip's own core. It can only use effects built
  into that core's program (`SPEC=1`).
- **The master inserts run one frame late.** The mixer stores the MAIN sum for
  the inserts, takes the previous frame's insert output to the output, and the
  inserts run after T8's effects like any effect call: 16 samples (0.36 ms). Inline
  they would race the output DMA inside the half-sample margin above, and
  the harness cannot show that race.
- **Return latency (❓ estimates):** RET B on core 0 adds one frame; RET A on core 1
  is a one-writer/one-reader hand-off each way through rotating buffers, about
  7 blocks (~2.5 ms). A delay on RET A can subtract it from TIME.
- **The click / MD path survives** as a source with its own gains.
- **MASTER TRACK.** With MASTER TRACK on, fall back to the stock path (P:0x292)
  for T1–T7 → T8 and keep the strips working on top. ❓ untested.

## 4. What it replaces

The current bus (`docs/effects/XBUS.md`) exists because many writers on both cores add
into shared buffers that are also cleared, which produced its three cross-core
defects. In this design summing happens on one core in one place, and the only
cross-core traffic is two finished blocks each way.

Retired: the SEND client on every FX2, the auto-gain count, the housekeeping
election, core 1's rotation tracker, the host guard and the hosts' dry-plus-wet
output, and the refused send on T8. New: sends see exactly what the dry path sees,
including the ColdFire delay pass, so a stock DELAY or Tape Echo on a track now
reaches the reverb (ruled out today, `DSP.md`).

## 5. Budget

Cycles per sample, 3,120 usable per core (✅ burn sweeps, `CHIP.md` §2). Prices are
the pricer's static counts unless marked.

| | core 0 (T5–T8 + mix) | core 1 (T1–T4) |
|---|---|---|
| widened mixer, 12 × 4 instead of 10 × 2 | ❓ +60–100 | — |
| returns | reverb ~1,650 (✅ measured on the unit) | delay 476 CLEAN / 1,191 GRAIN |
| master inserts | Oxide 164; Character 639 | — |
| left for FX1/FX2 on the tracks | ~1,200 with Oxide only; ~600 with Character too | ~2,640 / ~1,930, shared with the MD |

The returns cost about what the hosts cost today: the win is routing, a free FX2 on
T1 and T5, and a smaller bus, not a smaller total. The master chain is the tight
part; if core 0 fills, the master strip can move to core 1 through the same
hand-off at about 2.5 ms of main-out latency (❓).

Program and X memory are the other limit: core 0 must hold the mixer, the reverb,
the master modules and whatever T5–T8 run, from the donor pool (2,724 words by
default, up to 6,158). ❓ Not counted; the first build's free-word ledger is the
answer.

## 6. Traps visible before writing any code

1. **A master compressor's drive could follow the MAIN volume** if the MAIN
   volume is folded into every source's gain (O23's level path scales by "the two
   master squares"). Which of the two bytes is MAIN is open (§2). MAIN has to be
   applied after the inserts either way.
2. **Feedback runaway.** A loop gain of 1 or more pins the output at full scale;
   the 6 Sep master loop silenced the unit (`FAILURE_MODES.md`). Each AUX input needs
   a soft clip and the self-send range a cap.
3. **The MASTER TRACK path must keep working** (see §3).
4. **The MD's route into the mix** must survive the replacement.
5. **One mixer, two hooks.** Replacing P:0x238–0x2d4 changes code the recorder,
   USB audio and the MD read the outputs of. Bit-identity at unity (§8 step 1) is
   the gate that says they still get the same words.

## 7. Open decisions (the user's)

1. **Where the per-track sends live.** (a) Two parameter slots on a track page
   (P-locks, scenes and LFOs then work; AMP is full, so FX2 page 2 slots 10 and 11,
   and a stock FX2 has no sends); (b) a new per-track SEND window on the ColdFire
   (cleaner, but locks and scenes are extra work). Proposed: (a).
2. **Storage.** Per Part (`machinedrum.work` is the precedent) or per project (OTX,
   not built). Proposed: per Part.
3. **Pre- or post-fader sends.** Proposed: post-fader.
4. **Core split.** Reverb on core 0, delay on core 1.
5. **The MIXER page layout.** Not designed.

## 8. Order of work

Each step is flashable and checkable on its own.

1. **A mixer that matches stock exactly.** Our code replaces P:0x238–0x2d4.
   Gate: main, cue and every read-back word bit-identical to stock on a real
   project under the port (`make check` with `OT_PROJECT`), plus a burn knob inside
   the mixer to measure the real DMA margin on the unit (the one number the port
   cannot give).
2. **Master strip, Oxide as INS 1.** Gate: bypassed, output equals stock delayed by
   exactly 16 samples; a recording of MAIN includes the insert.
3. **AUX B and RET B** (BusVerb as a pure-wet strip). Gate: a runaway test with
   the self-send raised.
4. **AUX A and RET A on core 1.** Gate: `verify-twocore` with the cores skewed;
   on the unit, the track × delay-mode sweep used for the bus.
5. **UI and storage on the ColdFire.** Until then a test remix drives the gains
   from a control page.
6. **The 100 % wet delay as a ColdFire return** (Tape Echo over SDRAM, seconds of
   delay at little DSP cost). Needs AUX A delivered to the ColdFire and the result
   back.

Before any step is merged: `make check REMIX=<name>`, and
`scripts/refhash.sh check` if the build changed (`AGENTS.md`).
