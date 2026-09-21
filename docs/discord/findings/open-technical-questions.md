# open-technical-questions — extracted findings

Source: `Octahackers - OCTATRACK - open-technical-questions [1542740659419488376].txt` (505 messages, 28 Aug – 18 Sep 2026). Participants of technical substance: **bamshanks** (sambanks/octabam), **bryant12345** (Bryan T, ukulele owner), **ribon3000**, **plentynights**, **exit_planet_dust**, **maxolydian**, **zackyoti_98392**, **kjnilsson**, **buma2855**, **.reliktfarn**, **mishandchips**, **sdkboi**, **anglingar**.

Convention below: **[measured]** = disassembled/tested against real firmware or hardware; **[inferred/guess]** = stated as theory, guess, or LLM-derived without independent verification; **[retracted]** = an earlier claim in this same thread that was corrected later in the thread.

---

## 1. Dead code / abandoned features in stock firmware

- **28 Aug, bryant12345**: found remnants of a **NOISE effect in LO-FI**, with what looks like a **hidden noise table**. bamshanks confirmed: "looked like an abandoned poc... There were a couple of those hiding in there... There was a whole effect." **[measured — found in disassembly, not just a guess]**, but no further detail on which table/address, and the thread doesn't return to it later in this file. No list of all Octatrack DSP tables existed at that point; bryant12345 started one (see §3, table atlas work).

---

## 2. Control-frame timing (16 samples vs 64 samples) — resolved in-thread

This is the most rigorously worked-out thread in the file, with an explicit retraction structure.

- **28 Aug, bryant12345** (opening question): unclear which OT subsystems run at audio rate vs a slower control rate. Believed the sequencer ran in **64-sample chunks**, but found evidence LFOs update at sample rate — surprising, and possibly a misinterpretation.
- **28 Aug, ribon3000** [inferred, from own investigation into audio/MIDI sequencer relative delay]: "frames are 16 samples — that frame interrupt also clocks the sequencer."
- **28 Aug, ribon3000** relayed a "fable" analysis, presented as **settled/measured from firmware static analysis**:
  - OT control frame = **16 samples = 2756.25 Hz**, proven two ways:
    1. The tempo accumulator is an exact identity: frame = 16/44100 s for every BPM (tempo cancels out of the math).
    2. A per-track loop clamps trigger offsets to a 16-sample window.
  - The ColdFire control frame and the DSP's 16-sample audio block are **the same period, 1:1 — no divider**.
  - The "64" number is **eDMA NBYTES = 64 bytes of DSP status data per frame**, not samples — likely the source of the historical "64-sample" belief.
  - Native LFOs are computed **once per frame on the CPU** (2756.25 Hz control rate), not per-sample, for every LFO until a later date (see CLAUDE.md's own Nimbus/grain-window note about "a1" reads — separate topic, not directly about this).
  - Internal grid is 96 PPQN with sub-frame-accurate trigs.
  - Detail: sequencer accumulator advances by **tempo_raw × 16 per frame** (`lsll #4` at **`0x4000ad46`**), tempo stored as **BPM × 24**, clamped **[720, 7200] = 30–300 BPM**. One MIDI-clock tick costs **2,646,000 units** = 44100 × 60 (samples/minute) — setting units/minute equal on both sides makes tempo cancel, giving frame period = 16/44100 s for any BPM.
  - A per-track loop at **`0x4000aef2`** (`moveq #16,%d6`) computes each track's next-event distance in samples and clamps into a 0–16-sample window — writing sub-frame trigger offsets. This is how the OT achieves sample-accurate timing within a 16-sample control frame.
- **28 Aug, ribon3000**, architecture diagram (from same fable session):
  ```
  DSP core                              ColdFire (CPU)
  process 16 samples of audio using the CURRENT parameter frame
    → finishes block → raises IRQ → frame interrupt (0x4000aad0)
       → swap parameter double-buffer (front = DSP reads, back = CPU writes)
       → advance sequencer phase accumulator
       → compute this frame's per-track params (base + LFO + scene + p-lock)
       → DMA into DSP's buffer
  process NEXT 16 samples from the freshly-filled buffer ... repeat, 2756/sec
  ```
  Named routines: **`FUN_4000c8a4`** = frame builder; **`FUN_4000c11a`** = one modulated value per param per frame (LFO/scene morph/p-lock); **`FUN_4003f1b4`** = `muls.l` interpolation for crossfader scenes.
- **29 Aug, bryant12345**: confirms the 16-sample-chunk model is consistent with his own sound-on-sound clickless-loop equation ("16 sample chunks definitely seems to work... that's awesome").
- **20 Aug (thread continued 5 Sep), bryant12345**: recalled sezare56 (elektronauts) once said "**64 samples is the minimum playback length, that is sure**" — asked whether that's a misunderstanding or a separate real limitation.
- **Resolved 2 Sep, bamshanks (PR #52 write-up, see §4)**: RLEN's **64-sample floor is real and separate from the 16-sample control frame** — it equals **four frames** (4 × 16). So both numbers are correct, describing different things: 16 samples = control-frame/DSP-block period; 64 samples = a floor on recorder loop length (four such frames).

**Cross-check flag**: this 16-sample-frame architecture (frame interrupt `0x4000aad0`, frame builder `FUN_4000c8a4`, per-track parameter DMA) lines up with the "per-frame timing byte advanced 8 per 16-sample frame" language already in CLAUDE.md's ColdFire EMAC trap, and with the general model of a double-buffered parameter frame referenced throughout the project's own dispatcher/param-page traps. Worth cross-checking against `docs/firmware/PARAM_PAGES.md` and `docs/remixer/FAILURE_MODES.md` for consistency of the 16-sample-frame number and address `0x4000aad0`/`0x4000c8a4` if those addresses are already used anywhere in-repo.

---

## 3. DSP table atlas (Bryan T's mapping effort, 29–30 Aug)

- **29 Aug, bryant12345**: attempted to reverse-engineer effect algorithms from DSP tables + code via three separate methods: (1) hardware testing with test signals + knob turning — "worked well, but not always conclusive"; (2) poking parameters directly in memory; (3) asking Claude to recover algorithms "just" from tables and code — **explicitly reported as unproductive**: "felt like that went in circles, even for simple things like the EQ." **[firsthand-tested negative result — LLM-assisted static table/code analysis alone did not recover effect algorithms.]**
- Produced screenshots/attachments of table regions: `x06c00_tail`, `x00438_segments`, `x04840_curvebank`, a deinterleaved table atlas, and a table atlas overview, plus a revised `TABLE_ATLAS.md` (30 Aug). Comment: "Some of the tables are pretty wild... stuff you'd expect (sine, exponential, saw), but then some I can't imagine a use for. I think some are typically used in pairs." These files were shared but not further discussed/verified in this channel.

**Cross-check flag**: this directly overlaps with the project's own documented stock-table addressing trap ("AN ABSOLUTE STOCK-TABLE ADDRESS IS RIGHT IN PAYLOAD A AND 13 WORDS OFF IN B") — the curve-bank address `0x438`/`0x42b` mentioned in CLAUDE.md may be the same curve bank as Bryan's `x00438_segments`/`x04840_curvebank` screenshots. Worth reconciling addresses if these table atlas files get ingested.

---

## 4. Delay / recording-buffer architecture

- **28 Aug, bamshanks + bryant12345**: **[measured by bryant12345]** each delay reserves **4 seconds of audio** buffer on the ColdFire side; found by tracking down the buffer reservation. Each track gets **reserved RAM** to allow un-synced delay with time cranked to max — i.e., hidden per-track recording-buffer-like allocations. bryant12345 believes the delay does **interpolation that the plain recording buffer does not** — unconfirmed at that point, described as "not sure how much shared code" exists between the two.
- **29 Aug, bryant12345** shared `octatrack-delay-architecture.md` and (separately) `timestretch.md` (ribon3000) noting the **timestretch algorithm is entirely CPU-side (ColdFire)**, matching how the delay works — i.e., not DSP-resident. ribon3000 flagged that **TSNS** (a timestretch-related parameter) was still unexplained at that point.
- **1 Sep, bryant12345**: shared `octatrack-recorder-architecture.md` — a first pass at recorder/recording-buffer architecture.
- **2 Sep, bamshanks — major verification pass against the same firmware image, posted as PR #52 (github.com/sambanks/octabam/pull/52), "Ingest Bryan T's recorder control-path doc; fix part/pattern labels"**. All items below are **[measured]** (disassembled against the shared reference image) unless noted:
  - **`remsl` mystery resolved**: it's actually a **signed divide**, and the *quotient* is what's kept. Feeding the assembler `divs.l %d2,%d1` produced byte-identical output to what objdump was labelling `remsl` — the name is just objdump's ambiguous mnemonic choice for one opcode. So **`[0x80001820]`** is confirmed to be **the negative reciprocal of the tempo**.
  - **Units are samples**: `[0x80001814]` was independently measured on hardware as **BPM × 24** (the project's own tempo-sync cave hangs off it). Plugging that into Bryan's RLEN math gives: **length = (RLEN + 1) × (samples in one 16th-note step at 44.1 kHz)**. So RLEN is measured in steps, lengths are in samples, and **the 64-sample floor is exactly four 16-sample frames**.
  - **The `992250` table** is the **FIN/FOUT display ladder itself**, not merely fade-shaped: 113 entries; read as sixteenths of a step it is exactly the series `0, 0.063, 0.125, … 64`. The doubling and the round-and-halve at **`0x40005ff0`** cancel out, so that code path is just FOUT converted to samples.
    - **Caveat explicitly flagged as unverified at the time**: "this only works if the EMAC is in fractional mode, which fits but we haven't read MACSR." **[inferred, not measured, as of 2 Sep]**
    - **Cross-check flag — likely later resolved**: this is almost certainly the same MACSR question that CLAUDE.md's ColdFire trap section now answers definitively: *"STOCK UNICORN HALVES EVERY ColdFire FRACTIONAL-MODE MULTIPLY... firmware runs its EMAC in fractional mode (MACSR = 0x20)"* and *"MACSR S/U IS BIT 6... selects 16-bit rounding on the accumulator read-out"* (both dated 7–8 Sep 2026, after this PR #52 message). If so, the FIN/FOUT table math above is confirmed fractional-mode EMAC, and the "haven't read MACSR" caveat from 2 Sep can be considered closed by the later work — worth a note in whichever doc houses the FOUT table finding.
    - Still an open mystery as of this message: **why a pickup-arm reads the FOUT slot** at all.
  - **Part vs pattern labels fixed**: `0x80000003` and `0x100b14cf` are the **current part** (Bryan was right). The writer at **`0x40062120`** reads the part out of the **current pattern's** record; `[0x80000004]` is the **pattern**. Sizes reconcile exactly: 16 patterns × `0x8ed8` = `0x8ed80`, which is precisely where the `0x18b2`-stride part records start. Both sides had mislabelled this as "pattern."
  - **Trig/voice bit meanings** (from the trig→voice side): **`0x80` = start**, and **`0x10` / `0x8010` / `0xf010` = one-shot / hold / stop / retrig**. Explicitly flagged: **"Our labels, not verified, but same bits"** — i.e., agreement between both parties' independent guesses, not an independently confirmed ground truth.
  - The **`0x460d17ce`** queue's consumer also handles **RELOAD BANK** (opcodes `0x14` and `6`) — two more of "the 46" (engine dispatcher opcodes) accounted for.
  - Still explicitly open on both sides after this pass: **the actual audio write path**, and **where the recorder buffers live**.

- **5 Sep, bamshanks — session 5 re-verification (long message)**, re-checking Bryan's recorder doc revision:
  - **[measured]** Everything load-bearing in the recorder doc's §14 disassembles **byte-identical**: pool init, the `(track+2) × 14602` rows, the segment builder, the pack loop, `clrl %fp@(24)` at the loop point, the 16-sample extension, the rounding converter, and Bryan's `andil #-16` negative.
  - **[measured, corrects Bryan's guess]** §13.2's **DMA channel 0 ISR at `0x40004860`** is **not control-surface polling** — it is the **ColdFire→DSP audio frame transfer**: a 7-step state machine at **`0x46104d3e`**, TCD **`0xFC045000`**, DSP host port **`0x2000001c`**, **336-word per-track records per ping**. Explicitly noted as measured, not inferred: *"We've been feeding effect parameters through it for months, so this one is measured, not inferred."*
  - **[measured]** UI tempo mapping formula: **`tempo24 = 24·bpm + (23·tenths + 4) / 9`, truncating**, at **`0x4009c7c4`**. Tenths 0–9 map to 24ths `0 3 5 8 10 13 15 18 20 23`, so a displayed `.5` tenths is actually **+0.5417 BPM**, and naive `round(BPM × 24)` is **wrong for 7 of 10 tenths values**.
    - **[retracted, same day]**: "I first claimed they didn't [reproduce]; that was my rule being wrong, retracted the same day." — explicit example of the project's measured-vs-inferred discipline being applied live in this thread. Under the corrected mapping, Bryan's 5,279 / 2,017 counts reproduce exactly.
  - **[measured]** The **16-sample limit extension is arm-time, not per-wrap**: it lives at **`0x40006e2a`**, in the arm-calling converter between the length computation and its `jsr arm` at **`0x40006edc`**, operating on the same per-track record. The segment builder's wrap path is inline arithmetic and never reaches it — **a LOOP=ON buffer armed once sees the 16-sample extension once.** This closes §14.7 of Bryan's doc and "removes the last way 16 could quantise a loop."
  - **On Bryan's "16-sample confusion"**: bamshanks concluded there are **two different 16s being conflated**:
    1. **Loop length is not frame-quantised** — Bryan's own clean rows (88,200 / 22,050 / 4,410 samples, which are ≡ 8, 2, 10 mod 16) prove this.
    2. Where 16 *plausibly* still bites: the **relative frame phase** between the recorder's read-modify-write and the flex-track's read over the same buffer. There is a **15-sample band of head offsets** where every frame returns a **new/old sample mixture** — a discontinuity at **2,756 Hz** (the control-frame rate). A sub-sample-per-pass rounding error can walk the offset into that band over many passes.
    - A prediction tool, **`tools/recorder_framephase.py`**, was built to simulate this over Bryan's table: zero-error rows clean under either frame order; non-divisible rows seam every frame from pass 2 for ~16/ε passes then clean; there's a strict frame-order dependency. Three of Bryan's four clicking rows fit one order, and `286.2/2` fits the other — one fixed order predicts clean where Bryan's log shows clicks, flagged as **the row to repeat first**, plus `198/16` (rounded up, ε = −0.455).
    - Two cheap discriminators proposed: does clicking stop after ~16/ε passes; does a recorded-then-stopped buffer played back looped still click.
    - **Open question raised back to Bryan**: what trig type is actually firing per pass in his patch — REC, PLAY, both, or neither? "The mechanism differs for each."
  - **New emulation infrastructure reported (5 Sep)**: firmware now boots under **Unicorn (CFV4E core)**, mounts an **emulated CF card**, and loads a project through the firmware's **own storage stack**. LOAD PROJECT runs as **engine opcode 4** inside the real 46-opcode engine dispatcher, reads project/markers/arrangements/all 16 banks, and the resulting in-RAM part **matches `bank01.work` on disk**. Goal: arm a recorder locally from a loaded part and run the write path (`0x400068e4` under the per-frame dispatcher `0x4000d2a0`) with synthetic input, to settle the frame-order question by observation instead of guesswork. Reported as **~40 s per run, no flash needed.**
- **5 Sep, bamshanks, follow-up technical notes from the same emulator work**:
  - **[measured]** Unicorn's CFV4E core is **missing `bitrev`, `byterev`, `ff1`** (ColdFire ISA_C) and raises illegal-instruction on them. **437 sites** in the image use these, **219 of them `byterev`**, dense in the FAT filesystem code. `objdump` also can't decode them: `.short 0x02c0` = `byterev %d0`; `0x00c1`/`0x04c1` = `bitrev`/`ff1 %d1`. These were shimmed in the emulator.
    - **Cross-check flag**: CLAUDE.md documents several numbered "vendored-emulator defects" for the DSP56300/Unicorn stack (EMAC fractional-mode bug, MACSR S/U bit, AGU modulo-buffer bug — called "the eleventh," and the trampoline-retranslation bug). This ISA_C instruction gap (bitrev/byterev/ff1) reads like a **distinct, separately-discovered Unicorn/ColdFire defect** not obviously named in CLAUDE.md's list — worth checking whether it's already tracked under `tools/patches/` or needs its own entry.
  - **[measured]** The RTOS storage boundary is one hook: **PIO handlers only program the task-file registers**; the actual **data phase is the ATA ISR at `0x40015304`**; the queue primitive at **`0x4001568c`** blocks on **event wait `0x40000818`**. Intercepting that wait and performing the transfer there is sufficient to run the whole filesystem stack "cold" (headless).
  - **[measured]** Engine queue creator: **`0x40040b14`** (creates queues `0x460d17ce` / `...ee` / `...ae`, each a **1024-entry ring**). **RELOAD BANK is engine opcode 20**, whose argument is a **bitmask of banks, not an index**. **LOAD PROJECT is posted by `0x40023c7c(name)`**.
  - **[measured]** The set-name global at **`0x100f8480`** is an absolute path; firmware's default is **`/PRESETS`**; the **LOG file** written to the card root is described as "the best oracle for what a load did."

---

## 5. Sound-on-sound / clickless looping (Bryan T's ongoing project)

- **29 Aug, bryant12345**: has a spreadsheet with **~2,000 BPM/RLEN combinations** that work for clickless sound-on-sound looping on a stock Octatrack (`octatrack_clickless_loops.xlsx`).
- **6 Sep, bryant12345**: refined spreadsheet with a **calculator** for whether a given BPM/RLEN/clock-multiplier combination clicks (`octatrack_clickless_loops_2.xlsx`). Reference clicking case: **BPM=128, RLEN=4, clock mult=1**.
- **6 Sep, bryant12345** [firsthand-tested]: **AMP VOL at 0 is not true unity gain — it reads slightly greater than 0.** Workaround for infinite-feedback sound-on-sound loops (which otherwise blow up from the slight positive gain): reset the sample's AED-page gain from **+12 dB down to 0 dB**, then set **AMP VOL to 63** — this combination measured as true unity gain. "I think the mapping of the AMP VOL knob didn't quite line up at what they label 0. Very close, but not quite." Needed specifically because **infinite feedback amplifies any small positive-gain error until it blows up.**
- **6 Sep, bryant12345**: shared a PDF primer, `octatrack_sound_on_sound_primer.pdf`, describing the OT setup steps required before looping (references page-2 settings). A sample-based test approach requires the sample to be **longer than the loop** so audio crosses the loop boundary.
- The "16-sample confusion" investigation above (§4, 5 Sep) is the direct continuation/near-resolution of this thread; it is described as potentially "**Bryan's white whale**" (9 Sep, bamshanks), which was reportedly **cracked open by insight from maxolydian's slice-playhead work** on octamax (9 Sep) — not confirmed resolved in this file, but flagged as a breakthrough lead.
- **5 Sep, zackyoti_98392** asked bryant12345 to clarify the goal and reported never personally noticing clicks (using a Multiclock external clock) — bryant12345's answer: perpetual-recording sound-on-sound ("like a long delay line with infinite feedback") clicks at the loop point for most BPM/RLEN combos; he wants all combos to work by fixing loop-point behavior, motivated by manual guidance to always add FIN at loop start, which is fine for one-shots but bad for infinite-feedback looping.

---

## 6. MIDI CC exposure for recording-buffer parameters (INAB/INCD/SRC3)

- **31 Aug, bryant12345**: asked about feasibility of exposing new MIDI CC parameters, e.g. changing **INAB, INCD, SRC3** (recording-buffer input sources) via MIDI.
- **31 Aug, bamshanks** [technical answer, largely inferred/architectural reasoning rather than a fresh disassembly, though grounded in prior measured work]:
  - "Pretty feasible... same approach as our tempo-sync stuff (small caves patched into the ColdFire OS)."
  - Stock can't do it because **the CC handler only accepts CC 16–45**, mapped through a **five-page table (PLAYBACK/AMP/LFO/FX1/FX2)**.
  - The recorder setup page **is a normal descriptor in the same page table** — it's just not one the CC path can express.
  - **CCs 62–111 are unused**; channel→track routing "comes free."
  - Those recorder params feed the **ColdFire recording engine (DMA rings) directly**, so **none of the DSP-publish weirdness applies** (i.e., the "parameter slot can draw a knob and publish nothing" DSP/panel disconnect trap doesn't apply here, since this bypasses the DSP-side param path entirely).
  - **One open unknown**: the recorder page has its **own storage/writer** (the generic CC writer doesn't cover it) — needs one disassembly pass to locate it and confirm the engine **latches INAB/INCD/SRC3 at rec-trig time**. If so, the whole feature is "a tens-of-bytes cave off the CC handler."
- No follow-up in this file confirming whether that disassembly pass was done.

---

## 7. Pickup machine vs Flex-track recording buffer

- **3 Sep, bryant12345** asked: is the **Pickup machine** entirely ColdFire-side? Does the DSP ever feed a Pickup machine? (Motivated by understanding structural differences from recording buffers.)
- **3 Sep, bamshanks** [explicit guess]: "I would guess it's all coldfire and a recording buffer" — **not verified via disassembly in this thread.**
- **3 Sep, bryant12345** [firsthand-observed behavioral difference, not code-level]: recording buffer 1 on track 1 records **post-effects**, whereas the **Pickup machine records pre-effects**. Notes this makes Pickup machine pre-DSP if the ColdFire-only guess is right — described as "an interesting design decision."

---

## 8. CUE output level vs main output

- **4 Sep, bryant12345** [firsthand-observed, hardware]: **CUE output is very slightly quieter than MAIN out** (~0.1 dB). Filed an elektronauts thread about it: https://www.elektronauts.com/t/cue-slightly-attenuated/241715. **No code-level explanation was offered in this channel** — remains an open question. kjnilsson (as "kjnilsson") reported never having noticed it; zackyoti_98392-adjacent user "zackyoti_98392" (actually a separate poster, zackyoti_98392's neighbor "zackyoti_98392" — see raw log) said they'd also noticed it but assumed it was just them.

---

## 9. LFOs / LFO Designer

- **4 Sep, bryant12345**: open question — what's known about LFOs and the LFO Designer? Is it feasible to add LFOs, replace existing ones, or set useful default shapes for the 8 LFO Designer tracks?
- **4 Sep, bryant12345**: noted a specific implementation obstacle for setting defaults: **"the code is streamlined to set swaths of values at once,"** making per-shape LFO Designer defaults harder than expected. Suggested a project-manager tool (external, not firmware) might be the better fix for saving/reusing LFO shapes rather than a firmware change.
- **16 Sep, bamshanks** shared `octatrack-lfo-params-in-ram.md`, captioned **"According to Claude based on our findings"** — i.e., explicitly flagged by bamshanks himself as an LLM-derived synthesis rather than an independently verified disassembly result. **[inferred]** Topic: where LFO parameters live in RAM when a project is not yet saved (question originally asked by anglingar).

---

## 10. UI/panel rendering: greying out unused controls, linked knobs, "—-" indicators

- **7 Sep, buma2855**: explored building a custom "special functions" menu; double-clicking "function" opens the global menu and jumps directly to Octalab — a partial, imperfect shortcut. Asked whether any key combos are unused on stock firmware.
- **14 Sep, bryant12345 / kjnilsson**: raised wanting to **grey out (or hide) controls that do nothing in a given mode** — example given: the **Q knob does nothing in EQ's high/low-shelf modes**. kjnilsson noted his own arranger work caused **unexpected greying-out** behavior that he didn't understand yet.
- **16 Sep, bryant12345** shared `enable-nibbles.md`, described as correcting some things in the octabam repo; ingested by bamshanks ("Especially for my mod dpth/time in my new effects"). Findings from that doc, per bryant12345's own message:
  - **No evidence found for a true "grey out" capability** for unused knobs.
  - The alternative — making a knob **vanish entirely** — was tried but is not fully clean, e.g. blanking a knob (bamshanks) **"left the circles"** behind.
  - bryant12345 was independently experimenting with a page-2 switch that makes a page-1 knob vanish — "not the most intuitive."
- **16 Sep, kjnilsson** separately shared `PANEL_DRAW.md`, related to the same graying-out investigation.
- **16 Sep, bamshanks**: implemented and shared screenshots of **linked-knob indicators** (credited to Bryan T's findings) and an **"optional empty knob"** treatment using **"—-"** as a visual indicator for controls not used in the current mode, described as "not fully blank but better than nothing." Also mentions adding **1/4, 1/8-style rate indicators** at applicable knob positions.
- **14 Sep, kjnilsson**: shared `ARRANGER.md` (arranger investigation). Separately noted a **checkerboard graying pattern appearing on REM (remark) rows in the arranger**, believed by kjnilsson to be **"probably just an accident"** rather than an intentional UI feature — unconfirmed.

**Cross-check flag**: this whole UI thread (descriptor-driven knob rendering, formatter behavior, vanish-vs-grey, linked knobs) is squarely the same territory as CLAUDE.md's documented traps *"A DESCRIPTOR'S DISPLAY FORMATTER OVERRIDES ITS VALUE COUNT"* and *"A parameter slot can draw a knob and publish nothing"* (which point to `docs/firmware/PARAM_PAGES.md`). `enable-nibbles.md` and `PANEL_DRAW.md` (both from this thread) sound like they may already be the documents behind — or supplementary to — those trap writeups; worth checking whether they're already ingested into `docs/firmware/PARAM_PAGES.md` or a panel-drawing equivalent.

---

## 11. Label length limits (page-2 descriptor names)

- **12 Sep, bryant12345**: asked, for a MODE switch with three label states, how long labels can be — "5 character max? 4?" **No answer given in this channel.**

**Cross-check flag**: this is very likely the exact same field CLAUDE.md documents in *"A DESCRIPTOR NAME THAT EXACTLY FILLS ITS FIELD LEAVES NO NUL"* — `abbr` is a 5-byte field holding 4 characters + NUL, `fullname` is 13 bytes holding 12 + NUL, and an over-length name causes a line-F crash (`PC 0x48454C4C = "HELL"`) specifically when the parameter is LFO-modulated. Bryan's question predates that trap being written up (his question is 12 Sep; the trap's dated incident is 2 Sep 2026 per CLAUDE.md, so the bug was already known in-repo when he asked) — worth pointing him at that section if not already done, since he appears to be about to hit the same 5-byte-field trap with a 3-state MODE label.

---

## 12. Effect DSP-load management (dynamic vs worst-case)

- **13 Sep, bryant12345**: raised whether the DSP load could be **dynamically managed** (refuse to enable an effect on a Part if it would push the DSP over budget) instead of octabam's current approach of **statically calculating for the worst case** (e.g., assuming a user stacks 4 or 8 copies of an effect).
- **13 Sep, bamshanks**: explicitly declined to pursue this — "too hard basket," "feels like a rabbit hole that might lead to unwanted side effects," though acknowledged it "could be a great way to eek more out of it" if solved. Currently octabam "pressure test[s] using every combo" instead.
- **13 Sep, exit_planet_dust**: philosophical note — "Hard limiting is in the spirit of the gear - stability at all costs."
- **13 Sep, mishandchips** (Machinedrum context, adjacent project): separately investigating whether a DSP can **recover after an overload** on the MD, "in the same spirit as the two general fix" (a referenced prior MD fix, not detailed here) — could raise how far hard limits can be pushed if it works. Not Octatrack-specific but may be relevant if similar DSP overload-recovery logic is ever wanted for octabam.

---

## 13. USB audio / USB MIDI (plentynights + exit_planet_dust, 16 Sep) — substantial hardware thread

- **16 Sep, plentynights** [firsthand-tested, working build]: has had **USB audio working for about a month**, built by decompiling the 1.4C firmware in Ghidra.
  - Audio currently works only when the track is configured as **track 8 / master**; achieves **stereo CD-quality** output that way.
  - **Intermittent instability**: connection drops after roughly **10 seconds**.
  - **Full 8-track USB audio is blocked**: individual track data isn't accessible unless recording is armed on that track, and plentynights hadn't yet investigated the recorder side to work around this.
  - **USB-MIDI is built into the ColdFire hardware but not enabled in firmware**, for unknown reasons ("for some reason (??)").
  - Implementation is currently **UAC2 (High-Speed)**; a UAC1 attempt didn't work well on macOS specifically (macOS is picky about "frankenstein" UAC1 devices; plentynights called it unsupported on Mac in his testing).
  - Shared the **MCF54455 Reference Manual** PDF and a photo of the on-board **USB PHY IC**.
  - Debugging approach discussed with exit_planet_dust: use **Wireshark/USBPcap on Windows** (not macOS's Console/logger) to capture **URBs**, specifically looking for **unresponded GET_CUR/SET_CUR** requests, consistent with the hypothesis that the 10-second disconnect is an **OS driver health-check timeout**.
  - plentynights considers full 8-track streaming likely infeasible without significant community effort due to data volume, and is unsure whether the disconnect is Octatrack-side or Mac-driver-side.
  - Also mentioned working on **USB MIDI** in parallel and has most of the **bootloader mapped/commented in Ghidra**, proposed as a first target if the community wants a general system understanding (e.g., toward a C port) rather than isolated patches.
- **16 Sep, exit_planet_dust** [technical/architectural, largely inferred from datasheet comparison, not disassembly of the OT itself]:
  - Explained **why the Octatrack likely never got Overbridge, unlike the Digitakt/Digitone (DT1/DN1) family**: those units' ColdFire has a **64-channel eDMA controller** vs the **Octatrack's 16 channels**, and the Digi's USB controller can **pull directly from SDRAM without CPU involvement**. On the Octatrack, **everything touching SDRAM shares one bus**, so DMA-driven USB audio competes for the same bus as everything else.
  - Believes **stereo UAC audio out (and maybe in) plus class-compliant MIDI is feasible**; **8-track (or Overbridge-style) audio is likely too taxing** for the shared-bus architecture.
  - Debated **UAC1 vs UAC2**: plentynights already has UAC2 (High-Speed) working; exit_planet_dust thought UAC1 might be more realistic for the Octatrack's CPU headroom, though plentynights notes UAC1 at Full-Speed isn't standard/well-supported the way HS UAC2 is.
- **16 Sep, plentynights**: separately asked whether anyone had inspected the **companion MCU** (the button/UI controller chip, distinct from the main ColdFire) — buma2855 had not; plentynights planned to **dump its firmware and map the buttons**, not yet done as of this file.
- Model/tooling aside: plentynights mentioned using an LLM called "MiMo V2.5" for the Ghidra/RE work and a custom agent harness, and was considering DeepSeek 4.1 for future work.

---

## 14. Demo mode entry

- **17 Sep, sdkboi**: asked how to enter Octatrack "demo mode," referencing code that accesses embedded demo-mode graphics.
- **17 Sep, bryant12345** [uncertain/unverified]: "I think you press 'yes' while powering on the OT with no compact flash installed. Something like that." — **not independently confirmed in this thread.**

---

## 15. Crash causes / stability posture

- **10 Sep, yvez_me**: asked if there's a documented list of things known to crash the Octatrack.
- **10 Sep, bryant12345** [firsthand]: his own crash was caused by "not understanding how a memory address was referred to" — froze the unit, which then rebooted normally, allowing a firmware swap.
- **10 Sep, buma2855**: expects the usual C/C++ failure classes — invalid memory access, out-of-bounds indexes, buffer overflows, corrupted state, bad pointers — but notes that as of his writing, the project has been studied enough that crashes should be uncommon if new work is grounded in existing research. Notes the **bootloader supports SysEx transfer in recovery mode** as an emergency recovery path if a bad image is flashed.

*(This directly parallels the project's own `docs/remixer/FAILURE_MODES.md` register — worth checking whether these anecdotal community crash reports are already captured there.)*

---

## 16. Crossfader (XVOL / scene crossfade curve)

- **18 Sep, bryant12345**: asked whether anyone has explored the crossfader's curve behavior — is **XVOL** driven by a lookup table or computed math? **bamshanks: "not me."** **Left as an open, unanswered question** in this channel. (Note: the crossfader scene-interpolation routine `FUN_4003f1b4`, "muls.l interpolation for the Crossfader scenes," was already named in the 28 Aug frame-timing discussion — §2 above — as a possible starting point for this question, though the two threads were never explicitly connected in-channel.)

---

## 17. Repitch vs stock Rate control

- **18 Sep, zackyoti_98392**: asked how community "Repitch" (a project module) differs from the stock Rate control.
- **18 Sep, homeboiflex**: "Rate makes it go out of sync" (with the sequencer/tempo).
- **18 Sep, .reliktfarn** [clear technical explanation, matches project's own Repitch feature]: "Repitch controls the internal playback rate automatically to match the sample's BPM to the project's. Loops sound better that way because they won't get piped through a timestretch algorithm." I.e., Repitch avoids timestretch-induced quality loss on loops by changing playback rate instead, while keeping sync — unlike manual Rate changes, which desync the sample from the sequencer's tempo.
- Also **17 Sep, .reliktfarn**: submitted a PR for the repitch algorithm; bamshanks acknowledged and commented on it. (This matches the repo's own `modules/repitch/` work already tracked in git status — likely the same PR.)

---

## 18. Arpeggiator scale/key expansion

- **9 Sep, bryant12345**: asked if anyone has found the "KEY" internals for the arpeggiator, with intent to expand it.
- **9 Sep, maxolydian** [firsthand, already implemented]: "I just expanded the scales to all greek modes + blues and harmonic" — already done in maxolydian's own repo/mod (octamax), not detailed further here.

---

## 19. Cross-project notes: octamax / DDR tail overwrite and Unicorn bug

- **9 Sep, bamshanks** shared `octabam-notes-for-octamax.md` to maxolydian, containing observations from reviewing octamax's latest work:
  - **[inferred by bamshanks, from octabam's own prior findings]**: maxolydian's "DDR tail overwrite" bug **looks like it's hitting the same delay-ring buffers Bryan has mapped out**, combined with **the Unicorn emulator bug that has affected everyone in the project.**
  - **Cross-check flag**: "the Unicorn bug that has burned us all" is almost certainly the same defect(s) CLAUDE.md documents under the ColdFire/EMAC and AGU trap entries (fractional-mode EMAC halving, MACSR S/U bit misread, or the AGU modulo pre-decrement bug) — worth checking `octabam-notes-for-octamax.md` (if ingested) against those exact trap writeups for consistency, since this message treats it as one already-known, previously-costly bug being reapplied to a second project's symptom.
- **9 Sep, bamshanks**: separately notes maxolydian's **slice-playhead work** helped him solve something in his own emulator, and potentially "Bryan's white whale" (very likely a reference to the sound-on-sound loop-click problem in §5).

---

## 20. Other open/unresolved questions logged verbatim (no answer given in-channel)

- Where does the delay live? (28 Aug, bamshanks — rhetorical opener, effectively resolved over the following weeks by §4 above.)
- Is there a full map/list of all DSP tables in the Octatrack? (28 Aug, bryant12345 — partially addressed by the table-atlas work in §3, but no canonical list confirmed to exist.)
- Are there many open architecture/codebase questions left? (14 Sep, bryant12345 — posed as a general check-in; kjnilsson's reply about "midi machines" being a bad idea per Claude was the only response captured, itself an LLM opinion rather than a technical finding.)
- Any unused key-combo real estate on stock firmware for a custom menu shortcut? (7 Sep, buma2855 — not answered.)
- Is the Octatrack compatible/adaptable to a hypothetical "outbox 8" device? (16 Sep, .reliktfarn — not substantively answered.)

---

## Sessions/documents referenced but not inlined (attachments only, content not extractable from this transcript)

These `.md`/`.pdf`/`.xlsx` files were shared in-channel; their content is described above only insofar as participants summarized it in chat. If these files are recoverable (e.g., already ingested into the repo or in Discord CDN history), they likely contain more raw detail than captured here:

- `octatrack-delay-architecture.md` (bryant12345, 29 Aug)
- `timestretch.md` (ribon3000, 29 Aug)
- `TABLE_ATLAS.md` (bryant12345, 30 Aug, revised)
- `octatrack-recorder-architecture.md` (bryant12345, 1 Sep and revised 5 Sep — two distinct revisions)
- `note-for-bam-session5.md` / `RECORDER.md` (bryant12345, 5 Sep)
- `octatrack_clickless_loops.xlsx` / `octatrack_clickless_loops_2.xlsx` (bryant12345, 29 Aug / 6 Sep)
- `octatrack_sound_on_sound_primer.pdf` (bryant12345, 6 Sep)
- `octabam-notes-for-octamax.md` (bamshanks, 9 Sep)
- `ARRANGER.md` (bryant12345/kjnilsson, 14 Sep)
- `enable-nibbles.md` (bryant12345, 16 Sep)
- `octatrack-lfo-params-in-ram.md` (bamshanks, 16 Sep, explicitly Claude-derived)
- `PANEL_DRAW.md` (kjnilsson, 16 Sep)
- `MCF54455RM.pdf` (plentynights, 16 Sep — official Freescale/NXP ColdFire reference manual for the Octatrack's CPU)

Given PR #52's own text ("the full write-up with the disassembly is in the PR"), at least the recorder-architecture material has already been partly ingested into the repo (referenced there as `docs/EXTERNAL.md §6`, per the embed text) — consistent with CLAUDE.md's own note that `docs/history/EXTERNAL_INGEST` once existed before the 16 Sep history prune.
