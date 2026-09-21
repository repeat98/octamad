# Discord findings — Octahackers / OCTATRACK / octabam

Source: `Octahackers - OCTATRACK - octabam [1548130870752448562].txt`, 330 messages,
12–19 Sep 2026. Primary voices: **bamshanks** (repo author, "sambanks" upstream),
**bryant12345** ("Bryan T", named in this project's CLAUDE.md), **rbl0k_28323**,
**devilfish707**, **bukkakeborealis**, **em** (emuyia), **yvez_me**, **anglingar**,
**.reliktfarn**, **reubenfinger**.

Confidence markers used below: **[HW-measured]** = stated as tested on real
hardware; **[emu-only]** = tested only in the emulator/remixer; **[claim/theory]**
= asserted but not (yet) verified in-thread; **[disproven]** = raised then
contradicted later in the thread.

---

## The recorder "loop clicking" whale hunt

- 12 Sep, bamshanks believed he'd found the root cause(s) of Bryan T's
  long-standing recorder loop-click bug: "your loop clicking white whale might
  be three whales and I think I have got them this time," packaged as a
  `recfix` remix for Bryan to test. He linked
  `docs/firmware/RECORDER_CLICK.md` (upstream sambanks/octabam) as the writeup.
- After a long build/toolchain saga (below), Bryan tested on hardware
  **[HW-measured]** and reported mixed results (12 Sep, 13:36): the click
  **no longer gets recorded into the buffer**, but it **still clicks on
  playback**. Specifically: 128.0 BPM, RLEN 16, recording — click every other
  pass; with record/play trigs on steps 1/5/9/13, clicks on **seven of eight**
  repetitions.
- bamshanks: "interesting, it completely got rid of them on the testing
  material. wonder what I'm doing different" — i.e. his own test material did
  not reproduce the residual click, Bryan's did. Deferred returning to the
  hunt until after finishing an in-progress effects suite ("these effects are
  nearly done").
- Bryan attached a file `note-for-bam-recfix-click.md` (13 Sep, 14:08) with
  presumably further repro detail — content not visible in the export (Discord
  attachment link only), but the filename and timing suggest it documents the
  playback-click repro precisely (BPM/RLEN/trig pattern). **Worth pulling this
  attachment from Discord/CDN if still reachable — it looks like the most
  detailed repro note for the still-open bug.**
- **Status at end of thread: UNRESOLVED.** No later message in this export
  reports the playback click fixed. This directly extends (does not yet close)
  whatever `docs/firmware/RECORDER_CLICK.md` currently documents — cross-check
  that doc against "still clicks on playback, 7/8 repetitions" since the doc
  predates this exchange.

## Build / toolchain breakage chasing `make check REMIX=recfix` (12 Sep)

A long back-and-forth between bamshanks and Bryan T while Bryan tried to build
and test the `recfix` remix — useful as a record of transient build fragility,
not a DSP/firmware trap per se, but several items are concretely diagnostic:

- **verify_menu.py false failures on a no-FX2 remix**: Bryan's first clean-repo
  run reported 32 fails in `verify_menu.py`. `FX2_LIST` entries past index 2
  read garbage (`0x42565242` etc. — decodes as leftover ASCII "BVRB"/"Verb"/
  "Bus"), and the check compared against `0x400d6b00` while `build_bus.py`'s
  own log said it wrote the relocated chooser list to `0x400d7bbc`. Bryan's
  hypothesis (relayed via an LLM, explicitly flagged "That's from Claude, not
  from me"): `verify_menu` may not account for `recfix`'s shape (no
  FX2-visible modules). bamshanks acknowledged and dug in; resolution not
  spelled out verbatim but subsequent runs succeeded, implying this was fixed
  or was actually a stale/incomplete checkout (see below).
- **`make setup` silently stale**: Bryan ran `make setup` believing it
  succeeded, but was still running against an old setup script until he
  re-pulled — bamshanks noted "doesn't look like the git pull landed if you
  are still getting that." General lesson: a `make setup` that "looks OK" can
  still be running pre-pull logic; always confirm the new script's expected
  distinguishing output line before trusting a green run.
- **dsp56300 vendor library version mismatch — build error, not warning**:
  ```
  vendor/dsp56300/source/dsp_host/dsp_host.cpp:590:20: error:
        no member named 'setSharedWindow' in 'dsp56k::Memory'
  ```
  bamshanks: "looks like a version mismatch of DSP56300... let me push a fix
  to pin the version." Fix was to pin the vendored dsp56300 dependency's
  version (via `make setup`/submodule pin), requiring a `rm -rf
  vendor/dsp56300` + fresh `make setup`. **This is a concrete, dated (12 Sep
  2026) instance of the vendored-dsp56300-drift class of problem this project
  already tracks heavily (the assembler patch, the AGU bug, etc.) — the
  `setSharedWindow` API existing/not-existing across versions is itself a
  signal that the "shared window" mechanism (cross-core FX2 buffer sharing)
  is relatively recent/actively-changing vendor-side. Cross-check against
  `docs/remixer/PLACEMENT.md` / the shared-window docs for whether the pin
  version is recorded.**
- **elektron-firmware-tool also needed pinning**: a later step in the same
  session — `make image REMIX=recfix BUILD=84` failed making the `.bin`
  (`make_bin.py` couldn't find `out/elek_84.bin` because the `.syx`-only path
  had been taken due to a build tool mismatch). bamshanks: "elektron-firmware-
  tool needs pinned as well, sorry didn't expect it to take so many loops."
  Fix: `rm -rf vendor/elektron-firmware-tool && make setup` (should print "at
  065d18f (pinned)" and "local patch applied"). Bryan T's joking name for this
  whole saga: "whack-a-mole (whack-a-whale?)".
- **Successful end state, with a concrete hash to match**: bamshanks gave
  Bryan the byte-identity check for the resulting BUILD=84 image:
  ```
  make image REMIX=recfix BUILD=84
  shasum -a 256 out/OCTATRACK_OCTABAM84.bin
  ```
  should start `ecb574a9` — "byte-for-byte the image I tested on my unit."
  This is exactly the kind of "port is a proof" oracle-matching the project's
  CLAUDE.md emphasizes; worth noting BUILD=84/`ecb574a9` as a dated
  cross-check artifact if that image is still referenced anywhere.
- Bryan's full `make verify` transcript (12 Sep, 05:21) is a useful literal
  reference for what a **clean-but-incomplete** remix (`recfix`, "no
  FX2-visible modules") looks like when run through the full verify suite —
  lots of `[ -- ]`/`[SKIP]` lines for DRAM payload, MENU SHORTCUT, CF PROBE,
  bus screen table relocation, cc page-2 cave, "hides nothing" — all
  correctly inapplicable to a remix with no selects, followed by a **hard
  FAIL** because `out/mainos_bus.bin` had last been built for remix `bus`
  rather than `recfix` (verify checks whose-build-wrote-that-artifact, per
  the "shared scratch"/"who wrote out/ last" class of trap this project
  already documents for `verify_dram_boot`). **This is the same failure
  family as the "THE BOOT VERIFIER BOOTED THE WRONG IMAGE" trap already in
  CLAUDE.md — direct confirmation that `verify_menu.py` has (or had, as of
  12 Sep) the same "trust `out/` blindly" weakness that `verify_dram_boot`
  was fixed for. Worth checking whether `verify_menu.py` also rebuilds its
  own remix first, the way `verify_dram_boot` now does.**

## Cycle budget table (posted by Bryan T, 12 Sep 07:17, presumably from a build report)

```
                   cycles/sample
stock rows           NOT COUNTED   [FILTER, EQUALIZER, DJ EQ, PHASER, FLANGER, CHORUS, SPATIALIZER, COMB FILTER, COMPRESSOR, LO-FI, DELAY, PLATE REV, SPRING REV, DARK REV] -- stock code; FILTER measured 192
WORST ONE CORE                 0   (nothing of ours)
                                   4 FX2 slots, at most one server (the design rule)
budget/core                 4535   (200 MIPS / 44.1 kHz)
usable by us                3120   measured 23 Aug 2026; stock takes the other ~1415
headroom                    3120   against the worst core above
                                   the counter reads ~270 LOW on the reverb (CHIP.md s2); the wall is a CLIFF
```

- **[HW/measured, dated]** FILTER (stock) measured at 192 cycles/sample.
  `usable by us` = 3120 cycles, measured 23 Aug 2026 (stock consumes ~1415 of
  the 4535/core budget at 200 MIPS / 44.1 kHz).
- Explicit caveat embedded in the table itself: the cycle counter reads
  **~270 cycles LOW on the reverb** specifically, and "the wall is a CLIFF" —
  i.e. this is a known undercount, not a comfortable margin. This should be
  read as a live caveat on any reverb cycle number quoted elsewhere
  (`docs/firmware/CHIP.md` §2 is cited as the source — **cross-check that
  CHIP.md still carries this ~270-cycle-low caveat and that it's marked with
  the appropriate confidence level**, since CLAUDE.md's "how claims are
  written here" section explicitly calls for propagating retractions/caveats
  across documents).
- Design rule restated here: 4 FX2 slots per core, **at most one server**
  per core — consistent with the "insert vs. server" distinction already in
  CLAUDE.md.

## FX2 id exhaustion — devilfish707's ports (13 Sep)

- devilfish707 ported **RC Inflator**, **jc Tapehead**, and **jc Phoenix**
  (JSFX clones by "vladg" of TDR Molot fame, from
  `github.com/JClones/JSFXClones`) into octabam. **[HW-measured]**: "They
  work on hardware OT though" — described as still messy/proof-of-concept,
  and "Phoenix also eats a lot of words."
- **Concrete instance of the FX2/FX1-shared-id problem**: "I'm currently
  running into the id problem (no more free id's, dunno how to handle that)
  ... So i had to take spatializer's id for Phoenix but that messes up the
  controls." **This directly matches the documented project trap "AN FX2 ID
  IS ALSO AN FX1 ID... a module on a stock effect's id replaces that effect's
  code wherever it is selected, FX1 included" — this is a live, independent
  confirmation from a third-party contributor hitting exactly that
  constraint from the outside, dated 13 Sep 2026, worth citing as an example
  in that trap's writeup if not already.** No resolution/workaround is
  recorded in this thread beyond "messes up the controls" — appears unsolved
  for Phoenix as of this export.
- Effect descriptions, useful for context if these ever get PR'd: RC Inflator
  = "a 1:1 clone from elsewhere"; jc Tapehead = "like the old Massey plugin
  cloned"; jc Phoenix = "a guesstimate clone," ~4-5 tape modes × 3 brightness
  settings each, described by devilfish707 as "eats like all three reverbs"
  (word-budget-wise) but "might be optimisable." Inflator and Tapehead
  described as "quite cheap" (word-budget), "subtle," intended more for
  buses/masters than single-track inserts.
- Separately, devilfish707 ported **Airwindows ironoxide5** (tape emulation)
  and **[claim, self-reported, not explicitly hardware-confirmed in text but
  implied by "works over here in remix"]** optimized it from ~1200 words down
  to **877 words**. Praised for a "baxandall-like" Lo/Hi frequency control
  tied into the tape emulation's speed parameter; devilfish707 called it his
  new favorite channel effect for the OT. He also mentioned he'd already had
  to cut flutter and noise out of ironoxide5 to fit budget, and considered
  Airwindows ToTape "expensive" and hasn't ported it yet.
- rbl0k_28323 separately confirmed **PR #280** ("fix: keep Octakit FX2
  chooser validation in sync") landed and was merged by bamshanks 15 Sep,
  with bamshanks adding an FX1-side fix to the same branch before merging.
  Root cause per PR title: **Octakit's own hardcoded stock FX2 chooser table
  fell out of sync with OCTABAM's relocated live FX2 chooser table** when
  OCTAKIT is present as a module alongside octabam's own FX2 changes — a
  second, distinct manifestation of the "two lists must agree" class of bug
  (see next section for the crash version of this).

## Octakit + BusVerb/BusDelay interoperability crash (rbl0k, 14–15 Sep)

- 14 Sep 22:32: rbl0k reported specific commits under test — "Checkout
  b38dd21 with these choosings if selecting Send, Busverb oder Busdelay" using
  "the latest octakit with bugfix instead of your pin 92cf70b" (i.e. testing
  against octakit HEAD rather than octabam's pinned octakit commit).
- 15 Sep 01:00, rbl0k identified root cause and fix pending: **"If using
  Verb/Delay & octakit together they actually use two different lists for
  the same cursor index when switching to FX2 which causes the crash. Will
  push fix tomorrow after verifying."** **[claim/theory at time of posting,
  fix reportedly pushed the next day per the PR #280 discussion above — read
  these two messages together as the same underlying "two lists, one cursor
  index" defect, now understood as the FX2 chooser table desync described in
  PR #280.]** This is a second, independent line of evidence for the same
  "cloned/duplicated menu list must be kept in sync with the relocated live
  one" trap class already documented (compare to the existing "A
  DESCRIPTOR'S DISPLAY FORMATTER OVERRIDES ITS VALUE COUNT" trap — same
  family: two copies of menu-adjacent state, one goes stale).

## Combined "ok-ms" remix (octakit + midi-scenes) stability

- 14 Sep 16:02: bamshanks published first combined remix of **em's octakit**
  and **BUKKAKEBOREALIS's midi scenes**, `docs/remixes/ok-ms.md`.
- 18 Sep 18:10, devilfish707 **[HW-measured]**: "Bam i've been testing ok-ms
  and it's not very stable for me. Got a crash after creating a new project,
  sequencer hanged when rebooting. Tried to reload the project sequencer
  hanging again."
- bamshanks' response: has not tested octakit+midi-scenes together himself
  ("I've not actually tested them together as it isn't my goal, but I
  believe @BUKKAKEBOREALIS has been"); suggested testing each module in
  isolation to localize whether it's one module or a resource-contention
  issue from combining them.
- devilfish707 followed up suspecting a red herring: **[disproven-ish]**
  "Noticed some cfw behave buggy when USB is still plugged in, gotta rule
  that out" → after testing "without USB, seems stable for now" (18 Sep
  18:48) — implying the earlier crash/hang reports might have been partly a
  USB-connected artifact rather than a pure firmware bug, though this is not
  conclusively separated from the octakit/midi-scenes interaction itself.
  BUKKAKEBOREALIS separately confirmed testing "together. And with other
  remixes" and speculated that combining remixes might be why they
  "glitched," but had not yet isolated individually as of this export.
- Separately, bukkakeborealis reported (18 Sep) crackling from **Spectrum**
  at high resonance settings — noted below with the other crackle reports,
  since it may or may not be related to ok-ms specifically (message doesn't
  make clear whether ok-ms or the main effects rig was in use).
- Unrelated minor UI bug also under the ok-ms/midi-scenes umbrella:
  devilfish707 and bukkakeborealis discussed **MIDI CC fader values being
  "jumpy" compared to turning the physical knob directly** when using
  midi-scenes with certain synths (Multi/Poly reported as bad, Micromonsta2
  "seems smoother," Analog Rytm reportedly unhappy with MIDI CC in) —
  bukkakeborealis suggested this is synth-dependent behavior rather than a
  midi-scenes bug per se, and moved further discussion off this channel.

## BusVerb stability and the "wedge" (sequencer stall)

- 18 Sep 10:54, .reliktfarn: **[HW-measured, negative result]** "Anyone have
  a working new reverb implementation? My own ones still have lots of quirks,
  crossbleeding and bugs while having multiple instances running. Also the
  Busverb implementation instantly crashed the sequencer."
- bamshanks' response, 18 Sep 11:27–11:30: **[claim, contradicts the crash
  report somewhat]** "Busverb is stable for me now, but you gotta do it on a
  clean project and kinda set everything up right." Confirms this is a known
  and named issue: **"If you look in the known issues Claude calls the
  sequencer stall a wedge."** Also: "it doesn't play well with others, you
  gotta go all in coz it steals all the resources" — i.e. BusVerb is known to
  be resource-greedy and expects to own the whole bus/rig, not coexist
  casually with unrelated setups; several people have reportedly used it
  successfully "for quite a while" when set up correctly. **The "wedge" name
  for the sequencer-stall class of failure is worth cross-referencing against
  `docs/remixer/FAILURE_MODES.md`, which CLAUDE.md says is the register of
  hardware failure modes (symptom → cause → fix) — if "wedge" isn't already
  the canonical name there, this Discord message is the naming provenance.**

## Crackle bug hunt (18 Sep 2026) — UNRESOLVED at end of thread

Multiple independent crackle reports converged in one conversation on 18 Sep;
worth reading as one bug hunt even though several different effects/paths are
implicated:

- bukkakeborealis **[HW-measured]**: crackles from **Spectrum** with high
  resonance settings ("Sounds great though" otherwise). bamshanks: "Haha damn
  thought id exorcised the crackles" — implying this is a regression or a
  previously-believed-fixed issue resurfacing.
- .reliktfarn **[HW-measured]**: "Also getting crackles with my tape echo
  implementation still" (his own, separate tape-echo port, not necessarily
  the project's `tapeecho` module).
- bamshanks **[HW-measured, own rig]**: crackles "mostly when adjusting the
  time and feedback controls." Attached is an animated GIF from
  ambient.signals_76175 captioned "the crackles in question" (visual, likely
  a waveform/scope capture — not machine-readable from this export) and a
  WAV attachment from rbl0k (`Output_1-2.wav`) described as "Mainly digital
  noise, but you hear the crackles in it. play it VERY silent, plz!" — an
  audio artifact worth pulling if the CDN link is still live.
- **Key diagnostic fact, stated directly by bamshanks: "They don't happen on
  the emu."** i.e. the crackles are hardware-only and not reproducible in
  `dsp_host`/the emulator locally. This is exactly the class of problem
  CLAUDE.md's "A MEASUREMENT CAN BE STRUCTURALLY BLIND..." and "THE
  HARNESS'S MODEL OF THE DISPATCHER IS NOT THE DISPATCHER" traps warn about
  — **flag clearly: this is a live, currently-unresolved case of "hardware
  shows a defect the local harness cannot show," the exact failure mode this
  project has been burned by before (r7 dispatcher mismatch, XBUS
  synchronization). Worth escalating to the ColdFire port
  (`ot_emu`) per the existing playbook rather than continuing to reason about
  it from the emulator.**
- bamshanks' own working theory, explicitly hedged: "Param smoothing
  initially. But there are other ones that don't go away until you reload...
  which I thought/hoped I'd sorted. I think it's cycles but I'm not 100%."
  **[theory, unconfirmed]** — i.e. suspects a cycle-budget overrun (dropped
  frames / blown deadline) as at least one of possibly multiple distinct
  crackle causes, separate from param-smoothing discontinuities. No
  resolution recorded by end of export (19 Sep).
- MK1 vs MK2 hardware split: rbl0k reported crackles "on latest checkout on
  my MK1 too" and asked whether bamshanks tests on MK2 or MK1 (not answered
  directly in-thread). reubenfinger (MK2) could **not** replicate a
  "digital noise"/crackle using a tone through the filters at peak resonance,
  nor with an 808 kick sample (both tested on-device, not through inputs) —
  a **negative hardware result on MK2** for at least the resonance-crackle
  report, suggesting a possible MK1-specific angle or a narrower repro
  condition than "high resonance" alone. This is an open thread, not
  resolved — **worth cross-checking against MK1/MK2 hardware differences
  already known to the project (if any) and against FAILURE_MODES.md.**
- Scope note from bamshanks: all of this testing so far has been "full rig"
  testing (his whole personal effects chain at once), not per-module —
  "I feel like if you just sub part of it in it's probably gonna have issues
  ... As I've only done full rig testing." This means none of the crackle
  reports above have yet been isolated to a single module/effect by the
  author himself.

## Reverb development difficulty (bamshanks, 18 Sep)

- "Reverb was probably harder than all the other effects combined."
  "tuning up all those allpass filters and stuff was so time consuming and
  tricky."
- **Pre-delay abandoned for cycle-budget reasons**: "Lost a day trying to
  make pre delay work but not enough grunt" — i.e. pre-delay for the reverb
  was attempted and dropped because there wasn't enough DSP cycle budget
  (consistent with the reverb-specific cycle-budget cliff noted in the
  budget table above — worth reading these two facts together: the reverb is
  both measured ~270 cycles low by the counter AND already had a feature
  (pre-delay) cut for lack of headroom).
- Contrasts with most other effects in the rig: "Everything else I could say
  Claude make me a thing for the most part. But reverb I had to hand roll to
  the hardware" — i.e. reverb voicing/tuning was NOT done via LLM-assisted
  generation the way other effects apparently were; implies other stock-effect
  replacements in the "character station," filters, etc. were more amenable
  to automated/assisted authoring while the reverb's allpass network tuning
  was manual, hardware-in-the-loop work.

## Delay/reverb routing — hardwired, not independent (18 Sep)

- rbl0k_28323 relayed a claim (attributed to "GPt" — evidently an LLM,
  possibly ChatGPT) that a specific commit
  (`3f19cfd1069a3deb6770c1e49ec39a40aad0d0f9`) "is going back to having
  Delay/Reverb completely independent from each other," contradicting his
  own hardware-flashed build where delay was hardwired into reverb.
  **[claim relayed from an LLM, not verified against the actual commit]**
- bamshanks' direct reply, unambiguous: **"I'm doing them hard wired."**
  **[Author statement, effectively DISPROVES the LLM-relayed claim above.]**
  This is a clean example of exactly the caution this project's culture
  demands around LLM-generated claims about the codebase — the relayed
  "GPT claims..." message was wrong, or at least not what the author intends
  going forward, and should not be treated as documentation of current
  behavior. rbl0k separately mentioned struggling for days trying to patch
  "the old 2Bus for Delay/Reverb" from commit `9da61068` backward — i.e.
  attempting to un-hardwire delay/reverb routing on an older base — with no
  resolution recorded.

## Remixer/emulator audio-level bugs (bryant12345, 12–13 Sep)

- 6 dB rendered-file discrepancy: **[emu-only bug report]** Bryan reported
  that a WAV file rendered to disk (`out/_audition`, triggered by pressing
  "r" in the remixer's effect-audition interface) sounded 6 dB quieter than
  the source when "mix" was off, tested specifically with a sine sweep test
  file at 100/200/400/800 Hz through an effect he was developing. bamshanks
  acknowledged as a known category of issue: "there are volume mismatch
  things all over the place I'm working through... because they aren't
  voiced the same as the device... that's all very wip poc until I get v1
  across." Logged as a remixer "uplift note," not yet fixed as of this
  export. **Not a hardware/DSP-arithmetic bug — explicitly an
  emulator/tooling voicing mismatch, separate from the device's real
  output level.**
- Stale-render bug: **[emu-only, apparently transient]** Bryan separately
  reported (13 Sep 22:30) that the audition-rendered file in `out/_audition`
  was identical to the input file "regardless of settings" when testing
  whether the remixer could render audio through **stock** effects (he fed a
  sine sweep through the stock Equalizer and heard no change). devilfish707
  confirmed stock Equalizer worked fine for him in the remixer the same day,
  and diagnosed Bryan's issue as needing a rebuild: "Had to make remix again
  i think" — implying the audition path can silently render against a stale
  build if the remix wasn't rebuilt after a relevant change. No further
  disagreement recorded, so treat this specific case as resolved by
  rebuilding, though the underlying "audition can silently use a stale
  artifact" mechanism was not further investigated in-thread (compare to the
  documented `out/`-provenance traps already in CLAUDE.md — same family:
  trusting `out/` without checking who/what last wrote it).

## Architecture Q&A and community intel

- bamshanks' plain-language explanation of the DSP replacement mechanism
  (11 Sep, to a newcomer "anglingar"): "the firmware contains the coldfire
  code and the dsp code and at boot the coldfire loads the dsp code into
  each core and it runs from there. The DSP machine code can be
  disassembled. Each effect is an entry in a dispatch table indexed by the
  FX id, so we can read a stock effect's code, and we can replace an entry
  with our own code assembled for the DSP, then rebuild the image." Useful
  as a concise author-stated summary of the whole mechanism, consistent with
  CLAUDE.md.
- **Digitone 2 (DN2) apparently has no DSP56300 / no on-chip DSP code**,
  per anglingar (11 Sep, unconfirmed/secondhand: "Apparently no DSP code in
  the firmware I'll make sure but that is the first impression"). Separately,
  anglingar posted what reads as output from some analysis tool/LLM (12 Sep
  12:19) describing DN2 firmware section structure: "no section carries a
  DSP instruction stream: bootstrap, MAIN OS, updater — all ColdFire;
  section 8 — ARM Cortex-M, and new in 1.11, but the DN2 made sound in
  1.10E; blob — 32-bit word data. Stride-3 column entropy is 0.01, which
  rules out the DSP56300's 24-bit word outright, against 1.17 at stride 4.
  The low-entropy final byte is a little-endian float32 exponent." bamshanks'
  only reaction: "Strange." **This is about a different device (Digitone 2,
  not Octatrack) and is explicitly unconfirmed/"first impression" —
  tangential community intel, not a claim about octabam itself, but flagged
  here since it bears on whether the octabam DSP-replacement technique could
  ever generalize to DN2 (answer implied: no, if DN2 truly has no DSP56300
  instruction stream in firmware and instead an ARM Cortex-M core added in
  OS 1.11).**
- `.mdee` (11 Sep) mentioned having "a mostly done SLEIGH module for SHARC
  VISA on DT2" (Digitakt 2?) "but need to check" — no further detail given,
  unconfirmed/in-progress, not elaborated later in this export.
- Elektronauts thread on octabam was locked; bamshanks' read: "They can't
  really I don't think. They shut that down more because of people playing
  up I believe... some people have certainly had some attitudes" — social/
  community context, not technical, included for completeness since it may
  affect where future bug reports/contributions get routed.

## Architectural question left open (rbl0k, 12 Sep 17:17) — no answer recorded

> "T8 FX1 runs Character in BUS mode and brings the BusVerb return into T8's
> audio path. Could a custom chorus then run on T8 FX2, but use
> Character/T8 FX1's otherwise-unused 3072-word buffer for its delay memory?
> BusVerb already owns Core A's FX2 buffer pool. Would that be
> architecturally valid?"

No reply from bamshanks or anyone else is present in this export. This is a
concrete, specific proposal about reusing an FX1 instance's otherwise-idle
3072-word buffer as delay memory for an FX2 chorus on the same track/core,
predicated on BusVerb fully owning Core A's FX2 buffer pool (consistent with
the documented "payload A's half of the shared window is FULLY OWNED" trap).
**Flag for whoever picks this up: it's an unanswered design question that
directly engages the shared-window ownership rules already documented in
CLAUDE.md — worth deciding/answering explicitly rather than assuming, since
the existing docs say there is "no free ground" in payload A's half for
things like delay lines when BusVerb is present.**

## Character/channel-strip effect development

- bamshanks described building a "character" station/effect combining
  tape/tube/fuzz-style saturation, plus a "monster channel strip and master
  bus" built by "cherry picking all my favourite open source effects,"
  explicitly citing devilfish707's JSFXClones pointer as an input: "they have
  made my character station quite a bit nicer." He was also independently
  tuning "wave folders and distortions and comps."
- reubenfinger (18 Sep, hardware) praised Character on his own build: "first
  time really seeing/hearing properly what you've been producing Bam" and
  specifically called out "Bryan's sound on sound technique" being usable
  with Character — implies Bryan T contributed or documented a "sound on
  sound" usage technique for the Character effect (not detailed further in
  this export; may be documented elsewhere, e.g. a module README).
- bamshanks mentioned building "stations with modes, like the bus effects,
  to squeeze more functionality into the same space" and specifically
  "Just Voiced the modulation station" (12 Sep) — i.e. a multi-mode
  parameter-page technique is being extended beyond the bus effects
  (BusVerb/BusDelay) to standalone "stations" like Character/Modulation.

## Miscellaneous smaller items

- **Workbench "Type Error" on column switch** (rbl0k, 12 Sep, macOS 14.7.1,
  "latest build") — screenshot attached, not machine-readable here. rbl0k
  later posted a fix on a fork: `github.com/rbl0k/octabam` branch
  `octabam-local-fixes` (12 Sep 15:30). bamshanks' framing: "workbench has
  been a bit unloved since the turbo work on the emulator and the effects.
  Will get it all ship shape and get Octakit and Scenes and stuff rolled in
  soon" — i.e. Workbench is acknowledged as currently under-maintained
  relative to the DSP/emulator work.
- **"scene-kit" in Workbench** — rbl0k asked (13 Sep) whether scene-kit in
  workbench is "not anymore necessary"; no direct answer recorded in this
  export.
- **T1 recorder-arm feature (yvez_me, 14 Sep)**: a PR in progress adding a
  menu-armable 15-second, 16-bit recording of T1 to CF card. Not yet flashed
  to real hardware as of this message (yvez lacked a USB-to-MIDI-DIN cable
  to do a factory-restore-if-bricked flash). Planned staged rollout: (1) peer
  sanity check, (2) real hardware flash + verify 15s recording writes to CF
  correctly, then if that succeeds, (3) extend to "safe" 3600 seconds, (4)
  extend to T1–T8 simultaneous recording, (5) upgrade to 24-bit. bamshanks:
  "happy to roll it in but you will want to test it first please." No later
  update on hardware test results appears in this export.
- **Exception screen work by "em"** (emuyia) — bamshanks credited this (14
  Sep) with expediting troubleshooting generally; no further technical
  detail given here (likely a DSP/ColdFire fault screen shown on crash,
  useful context for anyone debugging the wedge/crash reports above).
- **Timestretch/repitch remix** — .reliktfarn announced (16 Sep) "Just
  finished the repitch warping feature/remix," generating excitement
  (_anfim confirmed community demand: "it's a different 'timestretch' mode
  that changes pitch when you change the bpm, like slowing down a vinyl
  record... present on the digitakt but not OT"). bamshanks: "Can't wait for
  that PR." .reliktfarn confirmed (17 Sep) intent to push that night. This
  is presumably the seed of what became the `repitch`/`REPITCH.md` work
  already tracked in this project's own memory (`project_repitch.md`,
  "image 81 works on MKII (16 Sep)") — **worth noting the Discord-side
  provenance/community-demand context (Digitakt parity request, "years of
  people asking") for that feature if it's ever written up further.**
- Windows build support: mayrakissa asked about building on Windows;
  bamshanks said yvez had gotten it working via WSL, but "I have no plans to
  make anything beyond how it works now" (i.e. no native Windows support
  planned, WSL is the community-found workaround).
