# Discord #demos — extracted technical findings

Source: `Octahackers - OCTATRACK - demos [1542722403220721786].txt` (28 Aug – 19 Sep 2026, 229 messages).

This channel is mostly showcase posts (videos, audio clips, screenshots) with community
reaction. Below is everything with technical substance. Claims are marked **measured**
(author or a third party ran it on real hardware/emulator and reports the outcome),
**firsthand-reported** (author describes their own implementation/experience but no
independent verification is in this channel), or **opinion/inferred** (guess, wish-list,
or subjective take).

---

## Octakit (emuyia) — 256 kits per project

- **emuyia**, 28 Aug: Octakit replaces the stock "4 parts per bank" model with "256 Kits
  per Project." Announcement page: https://www.junes.website/goodies/octakit — GitHub
  repo promised "soon."
- GitHub landed 29 Aug: https://github.com/emuyia/ems-octakit and issue template
  https://github.com/emuyia/ems-octakit/issues/new?template=bug_report.md
- **bukkakeborealis**, 28 Aug, **measured** (tested it directly): "It's awesome to have
  unlimited parts. I noticed changing patterns don't always recall properly the right
  kit" — a recall bug when switching patterns. Also reported **a crash after a while**
  (screenshot attached, no repro details given in text).
- Clarified behavior (**measured**, bukkakeborealis + kjnilsson, 29 Aug): kits can still
  be shared across patterns just like stock parts can; "Kits are 256 parts" — i.e. Octakit
  is functionally "more parts, potentially one per pattern," not a fundamentally different
  data model.
- Feature discussion (opinion/wishlist, not implemented): bukkakeborealis wants
  per-pattern kit auto-assignment/auto-save so copy-pasting a pattern also carries its
  kit; emuyia floated a "quick save" and a "special pattern paste" that special-cases
  kit-slot allocation (place kit data in the next free kit slot on paste). Nothing here
  is confirmed built as of this channel's end.
- homeboiflex requested one-click "copy part → paste to new part → select it" and the
  pattern-level equivalent — feature request, unimplemented.
- Side reference (emuyia, 30 Aug): says they already have "copy/paste/clear/undo other
  patterns without loading them" working for an **upcoming mnm (Monomachine) firmware
  beta**, invoked via `BANK+FUNC+TRIG+copy/paste/clear` on mnm, and thinks the same
  would be welcome on OT. This is Monomachine-specific, not Octatrack, but notes a
  cross-pollination of UI ideas between the two platforms.

## bamshanks's own tooling (voicing/remixer)

- 31 Aug, **firsthand**: "Added a lil renderer for the effects so you can mess around
  with your effects and have claude read the log. Should make voicing a bit quicker and
  easier" (video attached). Also did "ui work on the remixer, not complete but mostly
  working and useful" (screenshot attached). No further detail on what the renderer
  outputs beyond "log" that an LLM reads.
- bryant12345 asked (31 Aug) whether saveable effect presets are planned; bamshanks
  called it "interesting" — no commitment, unresolved.

## DUALBUS — custom submix machine (mrscruff2277)

Two posts (08 Sep and 16 Sep), the second a full Claude-written spec. **Firsthand,
author-reported**; not yet public/shared as code (author says private, "I'll DM you"
to one interested party as of 16 Sep; no GitHub link posted in this channel).

- Replaces the **PICKUP machine slot** (08 Sep: "It currently replaces pickup but I'll
  look into if it's possible to add it as an additional machine instead").
- Purpose: DJ-style crossfade transitioning between two configurable groups ("buses")
  of tracks, so the hardware crossfader can be freed for effects only instead of double
  duty as a DJ mixer.
- Mechanism (from the 16 Sep spec): setting a track's machine to DUALBUS turns that
  track from a sound source into a bus — it sums audio from other tracks you assign to
  it (page 2 gives two columns, A and B, each picking from tracks 1–8). The bus track
  keeps its own level/mute/cue/FX1/FX2/scene assignments, so one reverb/compressor can
  process a whole group.
- Four per-track states: off, crossfaded-on-A, crossfaded-on-B, or "always present"
  (added post-crossfade/EQ at full level, unaffected by the A/B knobs).
- Controls: LVL knob crossfades A/B (full-left = A only, centre = both at full,
  full-right = B only); **BASS kill** = a second-order ~200 Hz high-pass that swaps
  between A/B (one way kills B's bass, other way kills A's, centre kills both) — author
  says this was "matched by measurement" to an **Allen & Heath Xone:96**; **LO MID** =
  a −27 dB bell at ~360 Hz, also matched to the Xone:96, centred = pass-through; **SWAP**
  instantly exchanges A/B assignment for the knobs, implemented as a smooth sweep (not a
  hard switch) to avoid clicks.
- Send behavior: how much a source track sends to the bus follows that track's own
  level fader; muting a source track removes it from the main mix but it **still feeds
  the bus** — lets you route a track "into the group only."
- Claims all knob ramps (level, bass, low-mid) are click-free, including on
  FUNC+encoder jumps.
- Usage examples given by author: T7 as DUALBUS with T8 as a "neighbour" track for a
  4-FX-slot master (08 Sep); later config (16 Sep) uses T6 as DUALBUS with T7/T8 as thru
  tracks for a 6-master-FX-slot setup; another config: tracks 1&3 → bus A, 2&4 → bus B,
  track 5 always-present.
- **May relate to existing project trap docs**: this is a new custom machine type
  occupying an existing machine's slot (PICKUP), and octamad's CLAUDE.md documents
  several traps about ids/slots being shared or reused incorrectly (the FX2/FX1 shared
  dispatch-table trap, descriptor-formatter inheritance trap). Worth a human cross-check
  if DUALBUS or a similar machine-replacement idea is ever ported into octamad, since
  the machine-table equivalent of those traps isn't documented yet in this project.

## LOFI2 demos (bryant12345)

- 14 Sep, **firsthand**, two SoundCloud clips: ring modulator (low/high modes,
  demonstrating stereo behavior) on a static loop
  (https://on.soundcloud.com/RNKiFlABp2BuyjLBMs), and a frequency modulator demo with a
  synth played into it inside a sound-on-sound feedback path
  (https://on.soundcloud.com/ipiRkMjmj61jOeNlWQ).
- **Flag for cross-check**: octamad's CLAUDE.md already documents a LOFI2 stock-table
  addressing bug ("AN ABSOLUTE STOCK-TABLE ADDRESS IS RIGHT IN PAYLOAD A AND 13 WORDS
  OFF IN B" — Bryan T's LOFI2 shipped mistuned on tracks 1–4 for about a week, found
  13 Sep 2026). These demo clips are dated 14 Sep, i.e. the day after that fix's
  reported discovery date — worth checking whether the demo audio predates or postdates
  the stock-table fix, since if it's the buggy build the ring/freq-mod behavior described
  may only be correct on tracks 5–8.

## Reverb work across the community

- **bryant12345**, 11 Sep, posted a **measured** stock effect code-size table (in
  words), presumably from disassembly/build output:
  ```
  DARK REV     1,067      CHORUS       329
  SPRING REV   1,063      FLANGER      289
  FILTER         727      EQUALIZER    282
  PLATE REV      594      COMB         277
  LO-FI          537      SPATIALIZER  261
  DJ EQ          345      PHASER       207
                           COMPRESSOR  180
  ```
  Useful reference data for anyone budgeting FX2 code space (octamad's own build already
  tracks per-effect word budgets; this table is an independent, non-project data point
  for the same stock effects and could be cross-checked against any budget numbers in
  `docs/firmware/CHIP.md` or similar).
- **noeisgirl**, 09 Sep, **firsthand, hardware-tested** (see full mod list below): built
  a "lex verb" replacing spring reverb, based on **Dattorro's reverb algorithm** ("a
  famous algorithm used by old lexicon reverbs... had to optimize the fuck out of it...
  not quite the same algo but sounds close enough").
- **bamshanks**, same thread, **firsthand**: confirms their own reverb (the project's
  BusVerb/vintageverb lineage, not explicitly named here) is *also* Dattorro-based, but
  says "mine certainly isn't" a straight insert swap and "it's at least 4x too big" to
  fit the spring reverb slot — i.e. bamshanks's own Dattorro implementation is
  significantly larger than noeisgirl's and needed a bigger bus/bank rather than an
  in-place SPRING REV replacement. Also: "I couldn't get it not metallic without a heap
  of allpasses and long tanks" and "tuning it was a bitch" — firsthand tuning
  difficulty notes, useful if revisiting vintageverb/gloamverb tuning.
- Separately, **bamshanks**, 11 Sep, **firsthand**: "Yeah I did pre delay for my verb
  and abandoned it because it was so expensive" — a pre-delay feature was tried and
  dropped on cost grounds for the project's own reverb. Relevant if pre-delay is
  reconsidered for vintageverb/gloamverb-style modules.
- **bryant12345**/**kjnilsson**, 11 Sep, **question/inferred, not resolved**: curiosity
  about how the *stock* Dark Reverb's pre-delay is implemented and whether it has its
  own buffer — no answer given in-channel.
- Stock delay mechanism discussion (11 Sep, **opinion/inferred**, not a measured claim):
  mayrakissa called the stock delay "black magic"; bryant12345 corrected "not black
  magic... just RAM"; bamshanks: "it's a flex track, more or less." No further detail —
  treat as informal community folklore about how the stock delay is built, not a
  verified mechanism.
- Three separate community members independently building **Mutable Instruments
  Clouds-inspired** granular/reverb effects — worth distinguishing since they are
  different code, not the same module:
  - **kjnilsson**'s "**Cirrus**" — a Clouds-style reverb ("clouds but cleaner"), demoed
    11 Sep with an mp3 (arp-modes-cirrus-colour-test.mp3) combining MIDI arp
    accumulators/walk modes with a mu-law encode/decode effect feeding Cirrus.
    **Measured** claim: "one nice thing about the cirrus reverb is that I managed to
    get it to fit exactly into the plate reverb slot" (i.e. same code-size budget as
    stock PLATE REV, 594 words per the table above). Plans a "**cirrusxl**" variant with
    more parameters and 12-bit emulation, which "would fit into spring or dark [reverb
    slot] only" — i.e. estimated larger than plate's budget, needs Spring's (1,063
    words) or Dark's (1,067 words) footprint.
  - **bukkakeborealis**'s "**CLAUDS**" — also Clouds-inspired, demoed 18 Sep
    (video attached). bamshanks noted his own project's grain effect is called
    "**Nimbus**" — this directly matches the "Nimbus" module already documented in
    octamad's own CLAUDE.md trap notes (the `mpy phase,2^(23-k)` grain-window bug), so
    Nimbus = bamshanks's own in-project module, confirmed here as a separate thing from
    CLAUDS/Cirrus.
- General reverb/effect-replacement sentiment (11 Sep, **opinion**, several
  participants): broad agreement that stock SPRING REV is weak/rarely used
  ("fine... never use it" — bryant12345; "not fine" — mayrakissa; "a bit safe" —
  kjnilsson) and that PLATE REV's built-in gate makes it more valued despite being the
  smallest reverb (594 words) — several people would sacrifice Spring's larger budget
  (1,063 words) for a better effect (comb filter upgrade, a Clouds-style granular verb,
  a combined reverb/delay). All opinion — no implementation confirmed from this
  thread beyond Cirrus/CLAUDS/lex-verb already covered above.
- **bryant12345**, 11 Sep, mentions having previously "mapped out compensations" for
  auto-compensating pitch when filtering the comb filter's low-pass, published on
  Elektronauts (no link given) — a possibly-useful external reference for comb-filter
  work, but not retrievable from this channel alone.
- **kjnilsson**, 11 Sep, **opinion/design note**: if implementing a granular effect,
  would build it as a **machine** running off a flex/record buffer rather than as an
  **effect** constrained to an insert's input buffer, because "don't think it would be
  able to support many grains" as an effect; "crippled/uninspired granular is worse
  than no granular." Relevant design consideration for anyone porting a granular effect
  into octamad's insert/server model.

## MIDI scenes mod (bukkakeborealis) — real-world usage report

- **ambient.signals_76175**, 09 Sep, **measured** (their own testing, MK1 hardware):
  "midi scenes works very well. Tests done on mk1." Says they've been stress-testing for
  the author and a GitHub release is expected "in a few days."
- Usage detail given (**firsthand**, describing their own patch): sending 4 channels of
  sequencing to a Digitone Keys, 9 CCs per channel, crossfade-driven, "no latency";
  plus another 4 channels for additional CC control (also 9 CC each) — "9cc x 8
  channels = 72 ccs being modulated via xfade." No mod-web/MW or breath-control channels
  used yet, which the poster notes would allow even more control.

## ARP accumulator mode (kjnilsson)

- 09 Sep, **firsthand/measured** (demoed via video, unnamed attachment): new arp mode
  "**ACCU**" (note accumulator) — "bypasses the arp and only accumulates each time a
  note is triggered (strictly speaking each time the pattern plays)." Also confirmed
  working with chords. Possible rename under discussion: "**CYCL**." Author notes: "it
  took quite a lot of claude time to get there" despite the mode being conceptually
  simple.
- This is distinct from the noeisgirl "octave up on AED" and other arp-adjacent work —
  no indication these are the same mod.

## noeisgirl's mod pack — ChatGPT-assisted, hardware-tested via 354 flashed builds

Posted 09 Sep with a compressed demo video. Author explicitly frames this as an
amateur/non-developer effort using a ChatGPT Plus trial, with **each of 354 iterative
.bin builds flashed and tested on real hardware** (their own description of process:
"i just asked for a flashable .bin file each time and tested it on the hardware every
time. if it crashed or appeared broken... i just reported the error code or the parts i
didn't like, and told it to fix it"). So each listed item below is **hardware-tested by
the author**, though not independently verified by anyone else in this channel, and no
code/`.md` writeup was ever confirmed shared (author's trial was expiring same day;
unclear if a findings doc was produced). No GitHub link was posted for this work.

1. **TRX B2** (a Machinedrum bass-drum machine/model) "successfully ported" to
   Octatrack.
2. **EFM-SD** ported, "but with bugs that need fixing" — author says it currently works
   better as a synth voice than as a snare drum.
3. "**Vintage distortion**" — a new FX1 effect that **replaces the LOFI effect**.
4. "**Lex verb**" — replaces SPRING REV with "infinite sustain on full decay setting";
   Dattorro-based (see Reverb section above); kjnilsson said from the demo audio it
   "sounded quite good" (secondhand impression from audio only, not independently
   built/tested).
5. Octave-up option added to **AED** (machine).
6. Not shown in the demo: a "fully controllable varispeed looper" on the **Pickup
   machine** — record at any rate, then change playback rate and record on top of that,
   plus reverse.
7. Not shown: long-press **FUNC+REC** duplicates the current pattern to the next
   available pattern slot, intended as a live "snapshot" shortcut while
   performing/editing on the fly.

Author states all of this runs **compatible alongside emuyia's Octakit** concurrently
(a compatibility claim, hardware-tested per their own account, but no detail on how
extensively). `_anfim` asked about the actual dev process ("run a desktop/cli agent and
give it access to ghidra?") — this question was never answered in-channel, so the exact
tooling behind this work (whether Ghidra was used at all) is unconfirmed.

## Rytm (Analog Rytm) work — tangential, not Octatrack, but same community

- **mrscruff2277**, 18 Sep, **firsthand, in-progress**: started modding the Rytm. First
  mod adds accents to the Euclidean sequencer (logic control gets 4 new options
  targeting accents rather than trigs). Considering velocity randomization, noting it's
  "impossible with the LFO" on stock firmware.
- Same author, **in-progress, unresolved**: characterizing the Rytm's compressor via an
  ext-in loopback with Claude driving test signals over CC, to build a behavioral model
  — no results reported yet.
- **anglingar**, **opinion/inferred**: believes Rytm MKII/DN2-era LFOs are "out of the
  DSP" making a second LFO "easy," but is unsure of the Analog Rytm (AR/AR MKII)
  architecture. **bamshanks**, guessing: "still be coldfire I'd imagine" for the AR —
  explicitly a guess, not measured.
- Feature wishlist (antonio110582, opinion): wants a Digitakt-style equal-slice sample
  mode (16/32/64 slices) or ideally transient-detection-based auto-slicing, to pack many
  one-shots into a single Rytm sample slot. `_anfim` notes stock Rytm can already do
  sample chains up to 120 slices via "STA" set to coarse, but antonio110582 points out
  stock chaining requires equal-length samples per slot, wasting memory if one sample is
  longer — an existing stock-firmware limitation, not a bug in any mod.

## Other notes

- **bryant12345**, 09 Sep, stated goal (not yet built): wants "clickless" sound-on-sound
  looping at any BPM/RLEN combination, which "isn't possible with the stock firmware" —
  demo clip is just documenting the target behavior on stock gear, not a mod:
  https://on.soundcloud.com/sYopCOeOiSxmT6bDu7
- **bamshanks**, 09 Sep, **firsthand**: "So after I guess about a week I can finally
  reproduce this on my emulator... not fix it but reproduce" — refers to whatever bug
  bryant12345's clickless-looping post surfaced, but the specific bug isn't named in
  this channel; likely tracked elsewhere (worth checking other channels/commit history
  around 9 Sep 2026 for what "this" refers to).
- **mrscruff2277**, 18 Sep, opinion: "It should be trivial for Claude to rebuild any
  mods on top of new firmware revisions" — an untested claim about mod portability
  across firmware versions.
</content>
</invoke>
