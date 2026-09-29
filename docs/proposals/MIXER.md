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
  `X:0x4700..` (the recorder's sources, and where USB audio reads). P:0x2ec–0x309
  adds a mono 16-word block from `Y:0x280` into the ring, `x1·y0` into ring words 0/1
  (the CUE bus) and `y1·y0` into words 2/3 (MAIN), where `x1` and `y1` are the squares
  of `x:(r0+$32)` and `x:(r0+$33)` (the `(L/128)²` law). The cue mix follows
  (P:0x30a–0x359).
- 🟡 **That block is the metronome click, and the two gains are its volumes.**
  Measured under the port on 29 Sep 2026 (`METRONOME_ENABLED=1`,
  `METRONOME_MAIN_VOLUME=127`, `METRONOME_CUE_VOLUME=127`, both DIR at 0, the
  tones on the inputs): TX0 ring words 0–3 carry the click, peak 8,258,048 =
  (127/128)² × 2²³ exactly, one squaring; with the click off and the METRONOME
  volumes at their stock 0/32 nothing does. `LEVEL_LAW.md` §3 left open whether the
  bytes at `0x8000005e/5f` are these volumes or the LEVEL knobs; the code says `+0x32`
  → CUE bus and `+0x33` → MAIN, which is the parse's order (`5e` CUE, `5f` MAIN).
  Not isolated: the path is inferred from the code and from nothing else adding at
  P:0x2ec (a watch on `Y:0x280` would show it). Where the MAIN LEVEL and CUE LEVEL
  knobs enter is still unlocated.
- 🟡 **`Y:0x280` also carries core 1's mailbox** (`X:0x38000–0x3800f`, read at
  P:0x9b; `docs/proposals/MACHINEDRUM_MACHINE.md` on branch `machinedrum`): stock
  reads zeros; the MD fills it.
- **Timing.** 🟡 Under the port the mixdown lands about half a sample before the
  output DMA enters the half it wrote; every effect and voice call runs after it,
  for the next frame (O23: DSR2 `0x807d`/`0x807a`, 1,748 / 522 / 1,690 / 509 of
  4,469 frames). The DMA then reads one sample per 4,160 cycles, so work done in
  order on the ring keeps ahead of it as long as each sample costs far less than that
  (below, §3). Not measured on the unit; the burn knob inside the mixer (§8 step 1)
  is the measurement.
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
- **The master inserts run inline, in place, at P:0x2d5** (`jmp` over its 2-word
  `move x:>$206,r0`, the same shape as the mixdown's own site). MAIN is in the ring at
  that point (words 2/3 of each 8-word sample group); the strip gathers it into a
  contiguous block, runs the insert, and scatters it back, before the pack at
  P:0x2df.. and the cue mix at P:0x30a.., so the recorder, USB audio and the phones'
  MAIN share all hear the inserts. Timing (🟡 arithmetic on O23's phase, unmeasured on
  the unit): the insert costs ~164 cycles per sample (Oxide), the DMA needs sample j at
  about 2,000 + 4,160·j cycles after the mixdown, the insert has it at 164·(j+1), so an
  in-order pass stays ahead by 1,800 cycles at sample 0 and more after. This corrects
  the first version of this document, which put the strip a frame late and called
  the inline pass a race with the DMA: the race only exists if a sample is produced
  slower than it is read. A frame late remains the fallback if the burn knob shows the
  real margin thinner than the port's.
- ✅ **Corrected by the build (§11): that arithmetic counted MAIN's deadline only.**
  Stock's tail after P:0x2d5 also writes sample 0 of the click (into CUE and MAIN) and
  of the phones' cue mix, with the same deadline, and a whole pass ahead of it holds
  them back: under the port the phones' first sample of every frame went out two frames
  stale. The strip is therefore split: the insert runs on sample 0 at P:0x2d5, stock's
  tail runs on time, and samples 1..15 run at P:0x35d, after the cue mix, which redoes
  what the tail made from them (MAIN plus the click, the phones, the recorder's pack).
- **A strip needs what a track has and a strip does not: parameters and state.** An
  effect reads its twelve knobs through `r6` (a track's 84-word record from the
  ColdFire, per core) and keeps its state at `r7` (an instance block). The master strip
  has neither, so it needs a record of its own delivered like a track's (the MD's
  `md_xport.s` adds a block to the host-transfer chain, WP-C1, on branch
  `machinedrum`: the precedent) and an instance block of its own (~0x84 words of Y
  plus the modules' delay lines). Until the ColdFire side exists a test remix stamps
  fixed defaults, which is enough for Oxide's IN/OUT.
- **Return latency (❓ estimates):** RET B on core 0 adds one frame (its wet is computed
  from the previous frame's AUX B); RET A on core 1
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
| master inserts | Oxide 164 (✅ 268 instructions a sample as the strip runs it under the port, §11); Character 639 | — |
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
3. **The MASTER TRACK path must keep working** (see §3). Under the port, with it on,
   nothing reaches TX0 (`verify_set.py` forces it off; unmeasured whether that is the
   port's or the unit's), so nothing here can be gated with it on until that is understood.
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
5. **The MIXER page layout.** Decided 29 Sep 2026 (Jannik, on the painted mockups): the
   stock MIXER page stays; LEFT/RIGHT walk the strips (MIXER, MASTER, RETURN A,
   RETURN B) and UP/DOWN a strip's slots, so the tempo nudge is off while the MIXER is
   open; YES opens a slot's SETUP (effect list and page-2 knobs, drawn like EFFECT 1
   SETUP); values as numbers; LEVEL is the strip's level; the MUTE band stays and the
   trigs keep muting. MIDI CC for these controls later.
6. **Where a strip's parameters and instance block come from** (§3): a record delivered
   like a track's, and Y space for the state. Proposed: the ColdFire ships one record per
   strip on the host-transfer chain, from a Part-stored block. **Built for the master
   strip (§12)**, X space rather than Y (the inserts on its list use no Y); the
   Part-stored block is built (§15).

## 8. Order of work

Each step is flashable and checkable on its own.

1. **A mixer that matches stock exactly.** Our code replaces P:0x238–0x2d4. **Done: as a
   probe (§9) and through the build as a declared DSP site (§10).** Still to do: a burn
   knob inside the mixer to measure the real DMA margin on the unit, the one number the
   port cannot give.
2. **Master strip, Oxide as INS 1, inline at P:0x2d5.** Gate: with the strip's gains at
   unity the output equals stock bit for bit (no delay: it is inline); a recording of
   MAIN includes the insert; the cue pair's main share does too. **Done under the port
   with fixed parameters (§11)**; the gate is Oxide's model rather than stock (Oxide at
   its 0 dB points is not an identity). **The ColdFire record is built (§12)**: two slots,
   their effects and knobs from a model the page will edit.
3. **AUX B and RET B** (BusVerb as a pure-wet strip). Gate: a runaway test with
   the self-send raised.
4. **AUX A and RET A on core 1.** Gate: `verify-twocore` with the cores skewed;
   on the unit, the track × delay-mode sweep used for the bus.
5. **UI and storage on the ColdFire.** Pulled forward for the master strip (29 Sep
   2026): the record is built (§12), the MIXER pages (§13), the slot SETUP (§14) and
   the Part storage (§15); MIDI CC for the page's controls is next.
6. **The 100 % wet delay as a ColdFire return** (Tape Echo over SDRAM, seconds of
   delay at little DSP cost). Needs AUX A delivered to the ColdFire and the result
   back.

Before any step is merged: `make check REMIX=<name>`, and
`scripts/refhash.sh check` if the build changed (`AGENTS.md`).

## 9. Step 1 probe, measured (29 Sep 2026)

`tools/scratch/mixprobe.py patch` copies payload A's P:0x238..0x2d4 (157 words) to
free words of the harvested region (P:0x1020..0x10bc in a `hello` build, whose ledger
says P:0x1000..0x101a used of 0x1aa4), by **word copy, not re-assembly**, with three
operands fixed (the two `do` loop ends, and the exit `bra $2d5`, PC-relative, which
becomes `jmp $2d5` of the same one word) and a long `jmp` over the 2-word first
instruction at P:0x238. The disassembly of the copy differs from stock in five lines,
all address operands or labels.

Under the port (`ot_emu`, the same card, 300 frames after the transport start, both
DIR at 127 and the tones on the inputs so MAIN and CUE are live; stock image vs
patched image):

| | stock | relocated |
|---|---|---|
| TX0 capture of core 0 (`--audio-out`), 902,166 frames × 8 slots | | **byte-identical**, 21,652,028 bytes |
| host-port blocks (`--block-dump`), every class, both cores, both directions | | 0 differing blocks in every class |
| MAIN L/R and CUE L/R, non-zero frames, peak | 4,723 / 4,702, −16.4 / −15.2 dBFS | the same |
| `--dsp-stopwatch 0:238:2d5`, instructions per 16-sample frame (mean / min / max) | 839 / 828 / 839 | 838 / 827 / 838 |

The mixer therefore costs about 52 instructions per sample, and moving it costs
nothing measurable. The meter differs by one instruction between the two images and
the sign flipped between this run (relocated 838, stock 839) and the one in §10
(relocated 839, stock 838), so it is the meter's floor, not the jump's cost: a `jmp`
adds one instruction, which neither run can resolve from the other effects in the
window.

What this does not show: the track slots carry silence (the fixture has no samples; only
the two input pairs and the click are audible), so the copy's arithmetic on track data
is not exercised. It is the same words, so a difference could only come from an address
operand, and the three operands are the ones the diff shows; but a gate on the shipping
path wants audible tracks. And nothing about the unit: whether P-memory execution
from the harvested region costs the same there is the burn knob's question.

Commands: `verify_set.py hello --project P --frames 300` stages the card
(`out/setverify/card.img`); `mixprobe.py patch out/setverify/image.bin out.bin --new
0x1020`; then `ot_emu` on each image with `--audio-out`, `--block-dump` and
`--dsp-stopwatch 0:238:2d5`. The click run is the same with `METRONOME_ENABLED=1`,
`METRONOME_MAIN_VOLUME=127`, `METRONOME_CUE_VOLUME=127` and both DIR at 0 in
`project.work`.

## 10. The mechanism: DSP sites (29 Sep 2026)

The probe was a script. The build now has the mechanism: `schema.DspSite` (kind
`DSP_SITE`, no FX id, no chooser row), placed by `build_bus.py` after the effects into
the harvested region, claimed in the ledger, documented in `docs/remixer/MODULES.md`
("Declaring a DSP site"). Two modules use it, both identities:

- `modules/mixdown` (**MIXDOWN COPY**): the §9 copy, declared: the two replaced words and the
  157-word span pinned by SHA-256 (no Elektron byte in the repo), three operands fixed
  (`loop_end` twice, `bra_to_jmp` once).
- `modules/seam` (**MIXER SEAM**): an `asm` body on P:0x2d5, where the copy exits: a `jsr` over the
  two-word `move x:>$206,r0` to a body that replays it and returns. The empty hook the master strip grows from.

The remix `dspsite` carries both. What was measured (29 Sep 2026, this tree on `origin/main`
`0980fb5`):

| check | result |
|---|---|
| `scripts/refhash.sh check`, the build change against a baseline saved on the untouched tree | all 24 cases bit-identical (artifacts and reports): a remix with no site places what it always did |
| `tools/remix/selftest.py` | 154 pass, including two ledger collisions, one clean composition (a copy that ends where another site begins) and seven refused declarations |
| `verify_dspsite.py`, built image alone | jumps planted (`jmp` at P:0x238 to P:0x1000, `jsr` at P:0x2d5 to P:0x109d); the copy is stock plus exactly the three declared fixes; its 139 instructions disassemble as stock's, differing only at the declared exit; the seam body replays the two displaced words; no other stock P word changed |
| `verify_dspsite.py --selftest` | a bit flipped in a copied word, an unrelated stock word, a loop end, the exit's target, and the replayed displaced word: each caught |
| the port, same card, image vs the same image with both jumps removed | core 0's TX0 byte-identical (21,652,028 bytes), MAIN audible (4,723 frames, so not a comparison of silence), 27 host-port block classes identical |
| the port control: the built image with one instruction of the copy changed | flipping bit 4 of P:0x26e (the input pair's `mac y0,x0,a`, now `mac x0,y1,a`): core 0's TX0 differs, so the comparison can fail. The first control flipped P:0x266, a **track slot's** `mac`, and TX0 stayed identical: the fixture's tracks are silent, so track-slot arithmetic is exactly what this gate cannot see (measured, not only expected) |

Not done, and what it changes: nothing runs on the unit; the copy's arithmetic on track
audio is unexercised while the fixture has no samples (the control above shows a track-slot
error would pass); the pricer (`make cycles`) does not count site bodies, which for the
identities is one `jmp` and one `jsr`; the burn knob is still to build;
`MASTER_TRACK` cannot be gated under the port (§6). The mechanism holds one thing back on
purpose: a site that *changes* the sound has no automatic gate beyond structure, because
the gate compares to "the same image without the jump", which is only the right reference
for an identity. That module's own gate is its job (the mixer's, §8 step 2: unity sends
equal stock bit for bit).

## 11. Step 2: the master strip, measured (29 Sep 2026)

`modules/strip` (**MASTER STRIP**) runs OXIDE on MAIN at its 0 dB points (IN 48, OUT 80,
fixed until §7 decision 6; §12 replaces this), reaching it through the stock dispatch
tables by its id as a track slot does, with its instance block and record at
X:0x7c00..0x7cff (outside every X module; no non-zero write there under the port,
`--dsp-writes`, 900 frames). Three DSP
sites on payload A: `boot` (P:0x40, once per DSP boot: OXIDE's init and the record),
`head` (P:0x2d5) and `tail` (P:0x35d). The remix is `strip`; the gate is
`tools/verify/verify_strip.py`.

**The first version failed its own gate.** It called the insert once per sample for all
16 samples at P:0x2d5. MAIN matched Oxide's model at 0 LSB, but the phones (TX0 slots
4/5) were wrong at the first sample of a frame and nowhere else: 271 of the 293 frame
starts the gate tested on L (the first 16 frames were right), 269 of them
equal to the correct value of the sample 32 earlier (two frames: the ring half's previous
content). ✅ measured under the port. 🟡 Inferred
cause: the pass held stock's click and cue mix back past the output DMA's read of sample
0 (§3's correction). Nothing on MAIN showed it, because the strip writes MAIN itself,
early.

**The split.** `head` gathers MAIN's 16 dry pairs into a buffer, runs the insert on
sample 0 and puts it back; stock's pack, click, gain ramp and cue mix then run as stock
runs them. `tail` runs samples 1..15 in order, one call each: the click is the ring's
MAIN minus the dry sample (stock's click is a plain add), MAIN is the insert's output
plus that click, stored limited; the phones are the cue mix's own arithmetic on its own
ramped gains (Y:0x40 + 2j) and its L/R test word; then stock's pack routine runs again
on the processed buffer at its stock destination.

| check (port, the user's project, 300 frames, built vs the same image with all three sites' stock words back) | tones | tones + click |
|---|---|---|
| TX0 slots other than MAIN and the phones | identical | identical |
| phones: change only where MAIN does, by MAIN's change at the reference's gain | 0 of 4,703 / 4,701 off | 0 of 4,712 / 4,714 off |
| host-port blocks: classes that differ | 1 of 27, the pack | 1 of 27, the pack |
| the pack's CUE half | identical | identical |
| the pack's MAIN (recorder, USB) = `design.fixed()` of the reference's | 0 LSB, 4,800 samples | 0 LSB |
| TX0 MAIN | = `fixed()` of the stock MAIN, 0 LSB, 529,646 samples; IN 49 does not match | = `fixed()` of the pack's MAIN plus the click, 0 LSB; click on 2,227 of 4,800 samples; without the click does not match |
| `--dsp-stopwatch 0:238:35a` (mixdown start to cue mix end), instructions per frame | stock 1,620, strip 1,974 | the same |

The click fixture sets `METRONOME_ENABLED=1`, `METRONOME_MAIN_VOLUME=64` (tones plus click
do not clip) and `METRONOME_CUE_VOLUME=0` (CUE silent, so the phones' gain stays
checkable).

**Cost** (✅ instructions, the port's stopwatch; not cycles): `head` 333 per frame,
`tail` 3,948, so about 268 per sample against OXIDE's 158 in a track slot. The difference
is OXIDE's per-call setup (its two knob tables, sixteen calls a frame) and the strip's
bookkeeping. One call for samples 1..15 would save most of the setup but writes sample 1
only after all fifteen: inside the DMA arithmetic for OXIDE, not for Character. Not done.

**Not shown:** anything on a unit (the DMA margin above is the port's); track audio
(none reaches the mixdown under the port, `docs/remixer/EMU.md`); MAIN plus the click
clipping, where the tail's click (a difference of clipped values) and stock's differ;
the MASTER TRACK path (§6).

## 12. The strip's record: two slots from the ColdFire (29 Sep 2026)

The strip now runs **two slots**, each an FX id and its twelve knob values, from a model
on the ColdFire, `strip_model` in `modules/strip/strip_xport.s` (a DRAM unit). The MIXER
page will edit that model and a Part will store it; this step builds the path from the
model to the samples.

**The transport.** `strip_xport` takes the host-transfer chain's state 3 entry
(`0x400ab626`, stock `0x400049ca`: core 0's 64-word block, which sets its own NBYTES).
The first visit packs the model into 32 halfwords and sends them to core 0 as one more
64-byte burst, then leaves through the chain's exit; the burst's completion re-enters
state 3 and stock runs. The Machinedrum's transport (`origin/machinedrum`,
`md_xport.s`) is the template and takes state 5, so the two stay combinable. The block
goes to X:0x7c80; payload A's host handler (P:0x588) masks it with 0x3fff or 0x5fff,
alternately per frame, so it lands at X:0x3c80 or 0x5c80, the bank the DSP works in the
next frame, `x:$205 + $1480` there. Layout: the magic 0x5354; per slot the id, six page-1
halfwords `v << 8` and three page-2 halfwords `(v << 8) | w`; zeros; a checksum that makes
the 32 halfwords sum to 0 mod 2^16. Each halfword `h` is the record word `h << 8`.

**The apply.** Last in the tail (after the pack), for the next frame: a record whose
magic or sum fails is not used (the bank holds garbage until the first burst; zeros fail
the magic). Otherwise per slot every value is masked to 0..127 and copied to the slot's
record (page 1 at r6+0..5, page 2 at r6+$c..$e), and an id that differs from the one the
slot runs gets that effect's init (r1 the id, r6 the record, r7 the slot's block, as the
dispatcher calls it) and its proc. Id 0 and ids off the strip's list leave the slot dry.
The list is OXIDE: an insert joins it once it is shown to run correctly one frame per call
with no dispatcher state (Character glides its knobs per call and reads X:0x213 at init).
The head and the tail run slot 1 then slot 2 on each sample, with the track slot's
contract, n0 = 1 now set before every call (the head had run on the 1 stock happened to
leave there; OXIDE reads R at `x:(r0+n0)`). `boot` starts the slots where the model
starts, OXIDE at IN 48 / OUT 80 on slot 1 and slot 2 empty.

**Memory.** X:0x7c00..0x7cff the strip's block (saves, the two slots' ids, procs and
records, D and C), X:0x7d00 and 0x7e00 the slots' instance blocks, X:0x3c80/0x5c80 the
record. ✅ No non-zero write in 0x3c00..0x3cff, 0x5c00..0x5cff or 0x7d00..0x7fff under the
port on the user's project before this step (`--dsp-writes`, 300 frames, core 0).

**Measured under the port** (`verify_strip`, the user's project, 300 frames, against the
same image with the three sites' stock words back):

| fixture | result |
|---|---|
| tones | MAIN = `fixed()` at IN 48 / OUT 80, 0 LSB: the record flows every frame and changes nothing |
| dirty (tones, both cores' X/Y filled with garbage before the boot) | the same, 0 LSB |
| click | MAIN = `fixed()` of the pack's MAIN plus the click, 0 LSB |
| record (`strip_model` poked at frames 60, 120, 180, 240) | every pack frame is its phase's model or the next one's, 0 LSB; all four switches, on frame boundaries, three frames after each poke: IN 48 → 96 with OXIDE's state carried, slot 1 → none (dry), back to OXIDE (state from zero), OXIDE on slot 2 as well (on slot 1's output) |

In every fixture the phones differ only by MAIN's change at the cue mix's gain, the pack's
CUE half and every other TX0 word and host-port block are identical (28 classes now: the
record's burst is one, identical in both images). The capture lengths may differ by a
sample: the port stops on the ColdFire's frame count, and where that falls in ESAI time
moves with the DSP's load (the record fixture's built run ended one ESAI frame short with
OXIDE on both slots); the gate compares the common length.

**Cost** (✅ instructions per frame, the port's stopwatch): head 120 with both slots
empty to 602 with OXIDE on both; tail 1,108 to 7,690, the apply included. With both
slots, sample j's writes finish well inside the output DMA's 2,000 + 4,160 j cycles
(§3), by the port's count.

**Not shown:** anything on a unit; the Part that stores the model (the page that edits
it is §13); a record lost in transit on the unit (the DSP would keep the previous
frame's slots).

## 13. The MIXER pages (29 Sep 2026)

`modules/strip/strip_ui.s`, a second DRAM unit, pages the MIXER window in the layout of
§7 decision 5: **LEFT / RIGHT** walk the strips (MIXER, MASTER; the returns join later),
**UP / DOWN** the MASTER strip's slots (INS 1, INS 2), **A–F** turn the shown slot's six
page-1 knobs in `strip_model`, **LEVEL** turns MAIN. The MIXER strip is the stock page
with a ▶ at the right end of its title band; MASTER keeps the frame, the title band
(◀, "MASTER") and the MUTE band, and redraws the three boxes above the band as two: MAIN
as a number over a speaker, and the slot, its name down the side and its effect's knobs
as numbers, named and formatted by the effect's own descriptor. A slot with no effect, or
a knob the effect does not draw, shows an empty cell and turns nothing.

**Three detours**, all in the stock window (`0x4007c458..0x4007d478`): the opener's
`LPUSH` of its input layer (`0x4007d41c`) also pushes ours, a key layer for the four
arrow keys, on top; the close's `LPOP` (`0x4007d2a4`) takes ours (and the knobs' layer,
when MASTER registered it) off first; the draw's entry (`0x4007c458`, which the opener,
every stock knob, the mutes and FUNC call) runs the stock draw and then the page. Every
close is the window's close routine `0x4007d274` (MIXER's release, NO, FUNC + UP/DOWN,
and the window manager, which holds it as the window's callback), and the one `LPOP` of
the window's layer is in it. Every drawing call is one the stock draw makes, in the shape
it makes it (the title `0x400570b8`, boxes, fills, dotted rules, the icon routine,
labels `0x40013904`, values `0x400479b4` with flags 6 as MAIN, CUE and the GAINs are).

**The knobs** take a stock knob's step: on MASTER a layer of seven encoder records
(A–F and LEVEL) goes on top, and before it does, each of A–F gets the tails a stock page
gives its knobs (`0x40032784` with the effect's minimum and maximum, from its descriptor's
`MINS` and `COUNTS`); the handler steps with `0x400328e4` and clamps to the parameter's
range, so `strip_model` never holds a value outside its count (the DSP only masks to
0..127). LEVEL is the stock A handler (`0x4007d03c`, MAIN), called with LEVEL's index.
An edit sets the window's edited flag as a stock knob does (MIXER's release closes on it).
**The tempo nudge**: LEFT / RIGHT are the nudge on the stock MIXER page while the
transport runs; with the pages they are the strips', the choice made on 29 Sep 2026.

**Measured under the port** (`tools/verify/verify_mixerpages.py`, the user's project,
MKI keymap, against the same image with the three detour sites' stock bytes back):

| case | result |
|---|---|
| MIXER | the stock page but for the ▶: 15 pixels differ, all inside the arrow's box |
| MIXER, RIGHT, LEFT; MIXER, RIGHT, MIXER, MIXER | the MIXER page again, 0 pixels differ |
| MIXER, RIGHT | the MUTE band and the frame below the boxes are stock's, 0 pixels differ; ◀ and no ▶; both boxes lit, the stock boxes' edges inside box 2 gone (62 lit on stock, 0 here); OXIDE's IN and OUT drawn, its four undrawn cells empty |
| DOWN | INS 2 (empty): six empty cells; beyond them only the side label's digit changes |
| a trig on MASTER | the mute toggles, the page above the band is unchanged |
| A +10, +40; B −5, −20; LEVEL +10, +40 on MASTER | IN +49, OUT −24, MAIN +49: exactly what A moves MAIN (+49) and LEVEL moves MIX (−24) by on the stock page; only the three value cells redraw; slot 2 untouched |
| DOWN, A +10, UP, A +10 | nothing on the empty INS 2; IN +9 on INS 1 |
| with the DSP: MASTER, A +10 | core 0's slot 1 record (X:0x7c20) holds `57 << 16`, `80 << 16`: the page's edit reaches the DSP |
| MIXER, NO, or FUNC + UP from MASTER | the handle is 0; no layer of the unit or the window is left registered |
| layers while open | MIXER: the stock layer, then ours, no knobs' layer; MASTER: then the knobs' layer, last |

**What the gate cannot see:** the unit's LCD (the port composites the firmware's window
planes); the MKII keymap (the MKI's boots under the port; the arrow keys, MIXER, FUNC and
the trigs have the same codes); a real encoder's acceleration beyond the port's one delta
per event; anything on a unit. Not flashed.

**Next:** the SETUP window (YES on a slot: its effect list and page-2 knobs; built, §14),
Part storage of `strip_model` (built, §15), then MIDI CC for the page's controls.

## 14. The slot SETUP (29 Sep 2026)

**YES on MASTER** opens the shown slot's SETUP, "INS 1 SETUP" or "INS 2 SETUP", as the
locked mockup draws it: the window stock's EFFECT 2 SETUP opens (115 × 64, the same
calls: `0x4005829c`, the plane clear, the title), the strip's list down the left and
the slot's effect's page-2 knobs in the 3 × 2 grid on the right. **UP / DOWN** move the
cursor (held, they repeat at stock's delay and rate), **YES** puts the cursor's effect on
the slot, **NO** closes the SETUP back onto the MASTER page, **A–F** turn the page-2
knobs. The keys are stock's SETUP layer's records with our handlers (UP / DOWN repeat at
its delay 15 and rate 4). The list is NONE and the effects core 0 runs on the strip (`tail.asm`'s list:
OXIDE). OXIDE has no page 2, so its grid is empty, as NONE's is. The list's names are the
descriptors' full names, as stock's list prints them ("Oxide Tape", not the mockup's
capitals).

**Drawn and turned as stock's.** The draw is stock's `0x40037590` step for step (fill,
rule, rows through the list widget `0x4007ec60..0x4007edb0`, the scroll arrows, the
slot's effect's row inverted, the cursor boxed, the dotted grid, each knob by its
descriptor's widget with its formatter, names by `0x40013904`) with our list and
`strip_model` where stock reads the track's FX2. A knob is stock's page-2 editor
`0x4003a9dc` over the model: the descriptor's stepper or `0x4003240c`, clamped to
`MINS`/`COUNTS`, then the encoder's activity set to 20 (`0x4003256c`) so the knob lifts
and shows its value. The tails are staged as stock's opener stages them (`0x400326d4`,
page 2) on every open and every YES. The lift decays on the tick at `0x4005213c`, which
redraws the MIXER while it is open; the MIXER's draw (our detour) redraws the SETUP over
it. YES writes the chosen id and, for every knob the effect draws, its descriptor's default
(P + 0x5e, the table stock's select `0x40052474` reads too; 0 for the rest); core 0
takes it in the next frame's record.

**One window above the MIXER.** `0x4005829c` closes every window at the new one's level
or above (and calls their close routines), so stock's level 1 took the MIXER down under
it: the SETUP opens at level 2, which stock uses too (`0x400647be`, `0x40080eb2`). Its
close routine (the manager's callback, NO, and the MIXER's own close, which calls it
first) destroys the window, pops its key layer and redraws the MIXER when it is still
open. A stock window at level 1 or 2 opening over it would close it the same way (read
from `0x4005829c`, not exercised).

**Measured under the port** (`verify_mixerpages`, the user's project with DELAY on every
track's FX2 in every part of every bank, MKI keymap, against the image with the three
detour sites' stock bytes back and its stock EFFECT 2 SETUP from FUNC + FX2):

| case | result |
|---|---|
| YES on MASTER | INS 1 SETUP over the open MIXER window; the list is `SU_IDS` = NONE, 0x1f (tail.asm's list); OXIDE's row inverted (258 of 343 lit), NONE's not (43); the SETUP's key layer registered last, after the MIXER pages' two; the grid equals NONE's, 0 pixels differ |
| slot 1 poked to DELAY (0x08); A–F −127 each; then +3, +4, +2, +1, +5, +1; A–F +127; then LOCK +5, 200 ms later | against stock's SETUP after the same turns: 1,013 pixels differ, all in the title band and the list, 0 in the grid (frame, rule, the six knobs, their names, the lift and LOCK's "ON" included); the model holds DELAY's range ends (0 ×6; 1, 1, 127, 1, 1, 1) |
| UP, YES; then NO | NONE on INS 1: its row inverted, the model's slot 1 all 0; NO closes the SETUP and its layer onto the MIXER's INS 1 page, now empty: 9 pixels differ from INS 2's empty page, all in the side label's digit |
| DOWN, YES, DOWN, YES; then NO | OXIDE on INS 2 at its defaults (IN 48, OUT 80, the rest 0): INS 1's SETUP but for the title, 9 pixels; NO: INS 2's page differs from INS 1's only in the digit |
| NO, NO / MIXER / FUNC + UP from the SETUP | both windows closed, no layer of the unit left |
| YES, NO, YES | the SETUP again, 0 pixels differ |
| YES, NO, then A +10, +40 | IN +49, as before the SETUP opened |
| with the DSP: A +10, then OXIDE onto INS 2 | X:0x7c10 = `1f 1079 1f 1079` (slot 2 runs OXIDE, slot 1's proc); X:0x7c30 = `48 << 16`, `80 << 16` |
| with the DSP: NONE onto INS 1 | X:0x7c10 = 0 0 0 0: slot 1 dry; its record 0 |

**A harness finding on the way.** With this build `verify_strip`'s phones check failed
on every fixture while the strip's DSP code was unchanged: the port's TX0 capture now
frames the phones pair one sample behind MAIN's, and the reference (stock's code at the
sites) shows the same lag in the same run, where the previous build's capture showed none
(measured on the kept runs: phones / MAIN steadiest at lag 1 here, lag 0 before). The
check now reads the lag off the reference and holds the built run to it: 0 of every
fixture's samples off the gain, at lag 1 here and lag 0 on the previous build's runs. The
lag moves with the ColdFire side's timing (inferred: only ColdFire code changed), not
with the strip.

**What the gate cannot see**, beyond §13's: a list longer than the window (one insert:
the scroll arrows and paging are stock's widget's paths, not exercised here); the lift's
timing on a unit (the port's tick is emulated time).

## 15. The strip in the Part (29 Sep 2026)

**Each Part keeps the strip.** The two slots, 32 bytes, live in every Part window at
bank + `0x904e2` (Part offset `0x1762`): the audio LFO designer's shapes **T7 and T8**.
A slot is stored as `strip_model` holds it but for its three spare bytes: byte 0 the
effect id, byte 1 the tag `0x53`, byte 2 the checksum that makes the sixteen sum to 0
mod 256, byte 3 the version `1`, then the twelve values. The Part is the truth and
`strip_model` its cache. `strip_sync` (in the host-transfer chain's ISR, once a frame,
before the record is packed) reads the window of the part the panel edits (`0x100b14cf`)
in the resident bank (`0x46c82456`); a window that differs from the one adopted and has
held still for two frames is adopted: both slots valid (tag, version, sum, an id on the
strip's list) is the model, anything else (a Part nobody wrote, a designer shape drawn
over it) is the boot default. So a Part Save, a Part Reload, a part change, a bank change
and a project load need no hook of their own: each changes the window, and the strip
follows. `strip_store`, called after each of the MIXER page's three edits (a page-1 knob,
YES on the SETUP's list, a SETUP knob), writes the slots into the working window, into
the part's SRAM twin (`0x100a4ece` + part × `0x18b2`, the copy that survives a power
cycle) and sets the marks the FX2 page-2 editor sets after its store (`0x4003aab6..
0x4003aae4`: the part's bit in the bank at `+0x95048` and in `0x100b145e`, the bank's
edited word `+0x9b332` and `0x100f8598`, then `0x40027e00`), holding the ISR's look off
while it writes. A panel part that is not one of stock's four (an Octakit kit's window)
keeps the model to itself.

**Why those bytes, and what it costs (measured from the image and the project, not on a
unit).** No byte of a Part is spare. Stock addresses the tail of the window at three
bases: `+0x1702 + 16 n` and `+0x1792 + 16 n` (`n` 0..7; the LFO designer's shapes, audio
and MIDI, copied by apply-part into the LFO engine when a WAVE of 11 + n is chosen: the
audio loop at `0x400092ea..0x40009328`, the MIDI base from `LFO.md` section 7), the words
between them (`+0x1782 + 2 n`, the shapes' interpolation bits, `0x80001508 + 2 i`), and
`+0x1832 + 16 k` (`0x400260d0` writes it, `0x400799e6` clears a byte of it; what it is
was not established). In the user's project all 128 Part records (16 banks, the working
and the saved copies) are 0 at `0x1702..0x1822`, `0xff` at `0x1822..0x1832` and 0 at
`0x1832..0x18b2`: no shape is drawn. The strip takes T7 and T8 of the audio LFO: at
worst a project that chooses DSGN T7 or T8 on an LFO plays the strip's bytes as that
shape's steps, and drawing over them resets the strip to its boot default (the tag,
version, sum and id are checked before any byte is used). It is one run of the window that
both midi-scenes (a freeze twin at `0x90492..0x90522`) and scenes-p2 (a pool at
`0x90522`) already use, but on the bytes scenes-p2 does not take; the ledger refuses the
strip with midi-scenes by name (`Claims.part_window`) and accepts it beside scenes-p2.
**A side finding, not changed here:** the same census puts midi-scenes' 288 bytes and
scenes-p2's 144 on stock's designer shapes (T2..T8 audio and the MIDI shapes), which
`schema.py`'s comment calls "known free"; they are free while no shape is drawn.

**Measured under the port** (`verify_stripstore`, the user's project on the same staged
card as `verify_mixerpages`, one load, a panel script per case; `poke` is `--poke` at an
emulated time, so the window changes while the unit runs, as a Part Reload changes it):

| case | result |
|---|---|
| nothing written or edited | the model is the boot default (OXIDE IN 48, OUT 80, slot 2 empty); both windows and twins zero; the edited words 0 (the part's dirty bit is 1 from the load itself) |
| MIXER, RIGHT, A +10 | IN 48 → 57; the window is `[31, 83, 4, 1, 57, 80, 0, ..]` then `[0, 83, 172, 1, 0, ..]` (decimal bytes), both slots valid; the SRAM twin and `strip_seen` the same; the two edited words 1; part 1's window and twin untouched; `strip_lock` 0 |
| NONE onto INS 1 in the SETUP | the model's slot 1 is 0; the window keeps it, valid |
| a valid record (OXIDE IN 20 / OUT 100; slot 2 NONE) poked into the window | the model is the record, spare bytes 0; the window is left alone; no twin write, no mark (a read writes nothing) |
| the same with one value changed (checksum stale); a designer's shape | the boot default; the window left as poked |
| the record, then zeros (a Part Reload to a blank Part) | the model follows the record, then the default again |
| part 1's window poked with a record and the panel's part set to 1 | the model is part 1's; an edit lands in part 1's window and twin, sets bit 1 of `+0x95048` and `0x100b145e` and the edited words, part 0's bit and window as the load left them |
| the panel's part set to 4 | the edit reaches the model (IN 20 + the stock step 9) and no window, twin or mark; `strip_lock` 0 |
| with the DSP: the record poked into the window | X:0x7c20 = `140000 640000` (IN 20, OUT 100, `v << 16`); X:0x7c10 = `1f 1079 0 0`: slot 1 runs OXIDE, slot 2 nothing |

**What the gate cannot see.** A Part Save or Reload through the panel: the port writes no
card and did not reach the PART menu, so the poke of the window stands in for what stock's
routines do to it (copy the whole Part), and the bank file itself (stock's save writes
the window as it writes every Part byte) is read, not run. A part change through the panel
(the panel's part byte is poked). The Octakit's kit operations, which copy the window
whole (`modules/scenes-p2/README.md`; `part 4` is only the guard). Which part is meant when
the panel's part and the playing pattern's differ (a pattern edited while another plays):
the strip follows the panel's, as the FX editors' stores do (inferred). The ISR's cost
(about a hundred instructions a frame when nothing changed, counted from the code, not measured). What a
project's own designer shape on T7 or T8 looks like on a unit after the strip took it.

**Open.** What a Part nobody wrote gives: the boot default, OXIDE at 0 dB on slot 1, is
right for the test remix and wrong for a shipping one, where an empty strip (both NONE,
dry) is the transparent start. It is one macro (`BOOT_MODEL` in `strip_xport.s`) and
`boot.asm`'s record. The strip's MAIN level is stock's and is not stored here.


## 16. Returns: the call site and the plan (29 Sep 2026)

Nothing here is built. ✅ is read off `out/dsp/payload_A.asm` of this tree; the rest is ❓.

**A frame on core 0, as the image has it.** The mixdown (P:0x238..0x2d5) reads the track
blocks the previous frame's effects wrote; then the per-track loop (P:0x385..0x53c, four
iterations, `x:$418` stepping 0x20 to 0x80) runs each track's FX1 and FX2 through the two
`jsr (r2)` pairs at P:0x4be/0x4d7 and P:0x4f4/0x50d; then P:0x53e..0x558 rotates two
buffer pointers and copies five words, and `jmp`s to P:0x4a, the poll loop. Nothing branches
into P:0x53e (the disassembly names no label there), and every register that code reads it
has written first (a, b, x0, r6, r7), so a `jsr` over P:0x53e's two-word `move x:>$415,a`
(the seam's shape, §10) is a place where **all** registers are free and every track's effect
of this frame has run. Whatever it computes reaches MAIN at the next frame's head, at the
same age as an FX2 host's wet.

**What that gives a return.** A "hostless" RET B: the strip calls BusVerb there as a track
slot would, with its own record (r6), its own instance block (r7, X:0x7f00 is unused under the
port), `r0` a block of 16 silent pairs, `n7` = 16, `a` = 1 (the dispatcher's call flag); the
block comes back as `wet × WET` alone, and the next head adds it into D before the inserts.
T5's FX2 stops being a host. Its sends are today's SEND accumulators, so tracks keep their
`REV` knob.

**What has to be true, and is not yet checked.**
1. The server's guard and locks. With the strip as the only instance, the REVERB role lock
   (`Y:0x9c2`) is claimed by its r7 every block; the housekeeping is elected among the SEND
   clients, which run earlier in the frame. A remix that hides the engine gets `HOSTGUARD`
   (r7 == 0x6200) at the top of `proc`, which the strip's r7 would fail: the guard must let
   the strip's r7 through. ❓ falsified by the server rendering dry under the port.
2. Cost. The reverb prices ~1,650 cycles a sample (§5) at the frame's end instead of in the
   loop; that is inside the effect phase, not the mixdown's DMA window. ❓ no burn measurement.
3. `b` at the call: the dispatcher passes `x:$41c` / `x:$41e` in `b` (P:0x4d5, P:0x50b);
   whether the server reads it is not checked.
4. A record: BusVerb reads twelve knobs from r6 (page 1 `+0..+5`, page 2 `+$c..+$e`).
   The strip's model already ships records this way (§12); a return is one more, with
   the reverb's ids and knobs on a RETURN B page (§7 decision 5).
5. Storage: one 16-byte slot in the Part window, on the designer shape T6 (`+0x1742`),
   beside the master strip's T7/T8 (§15); RETURN A would take T4/T5. ❓ same census caveats.

**Measured the same day: the words are the first limit (§5's open item).** Built
(`make bus`, `MASTER STRIP` + `OXIDE` + `REVERB SERVER` + `SEND` beside stock effects, a scratch
remix, not committed): payload A's default donor pool is 2,724 words (PLATE, SPRING, DARK) and
the reverb server, its LFO table and SEND take 2,449 of them; the strip takes 581 (boot 34,
head 113, tail 277, the mixdown copy 157) and OXIDE 272. Together 3,302, so **the build refuses**
("MASTER STRIP's `boot` does not fit ... 3 words at most", and the mixdown copy needs 157). It builds when
CHORUS and COMPRESSOR are taken off both menus (`Remix.fx1` without them, and no FX2 row): the
region is CHORUS + the three reverbs + COMPRESSOR, 3,233 words, **88 free**, with the mixdown copy
left out (needed only for the 12 × 4 mixer, §3; with it in, FLANGER's 289 words would go too). The
hostless call's body is of the order of 40 words (register setup, a 32-word block clear as a `do`
loop, the `jsr`, and the wet's add in the head), so it fits, thinly. Payload B is not the problem:
the delay server, SEND and OXIDE use 2,007 of the same 3,233 there. What the user gives up is
stock CHORUS and COMPRESSOR on FX1 and FX2 in any image that carries the reverb server and the strip;
a listed effect with an instance buffer (FLANGER, CHORUS, SPATIALIZER, COMB) is refused beside the
servers, so those four cannot be kept in the FX2 chooser anyway.

**What it does not do.** No per-track send knobs beyond SEND's, no AUX A (the delay is on
core 1: a hostless call there is the same shape at payload B's own frame end, not
examined), no retirement of the SEND bus (§4). It is the step that frees T5's FX2 and
puts a reverb on its own strip; the 12 × 4 mixer of §3 stays the destination.
