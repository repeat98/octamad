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
   Part-stored block is still to do.

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
   2026): the record is built (§12); the MIXER pages, the SETUP window and Part storage
   are next, in that order.
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

**Not shown:** anything on a unit; the page that edits the model and the Part that
stores it (next); a record lost in transit on the unit (the DSP would keep the previous
frame's slots).

