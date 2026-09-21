# Findings: #dream-features (28 Aug – 18 Sep 2026)

Source: `Octahackers - OCTATRACK - dream-features [1542740806434164746].txt` (730 messages).
Nominally a wishlist channel, but it carries a real firmware-archaeology thread (the
sound-on-sound recorder click bug) plus a lot of load-bearing detail about what
bamshanks/Bryan T/others have actually built or tested. Feature requests are grouped
briefly at the end; technical content comes first.

Legend: **[measured]** = someone reports directly testing on hardware/emulator and
stating a result. **[inferred/opinion]** = reasoning, guess, or hedged claim, not
verified. **[wishlist]** = feature request only, no technical backing.

---

## 1. Recorder / sound-on-sound click bug — measured and fixed in-channel

This is the one thread in the channel that reads like a project devlog rather than a
wishlist, run between bamshanks and bryant12345 (Bryan T), 28 Aug – 8 Sep 2026.

- Bryan T's own writeups, shared 03.09.2026: `octatrack_sound_on_sound_primer.pdf` and
  `octatrack_clickless_loops.xlsx` (Google Drive links, verbatim):
  - PDF: https://drive.google.com/file/d/1vPD5GU_6IkaBdKB9aTK2y2HaYwBwvVDr/view?usp=drive_link
  - XLSX: https://docs.google.com/spreadsheets/d/1O0bGngFqRzBWiUyuq5MtmtfVWN0q_mLN/edit?usp=drive_link&ouid=109645928635107374488&rtpof=true&sd=true
  - A follow-up note file `note-for-bam-seam-flash.md` was also shared (07.09.2026, as a
    Discord attachment, not a repo link).

- **[measured, bamshanks, 07.09.2026]** Running the firmware under emulation: at the
  default 128 BPM / RLEN 4, the recorder arms and writes a buffer length of 20,672
  samples. Bryan's spreadsheet predicted 20,671.875, rounded up. Formula recovered:
  `steps × 44100 × 720 / tempo24`, computed once per frame, round-half-up. At 120 BPM
  the length comes out exact: 22,050 samples. bamshanks: "the workbook matches the
  machine."

- **[measured, bryant12345]** Confirms the 128/RLEN4 click is audible on real hardware,
  not just a spreadsheet artifact: "You absolutely will hear it." Also confirms it does
  **not** stop over time once present in the buffer, and reproduced it with REC+PLAY
  trigs on the same steps (tested steps 1, and separately 2/6/10/14) — clicking is
  identical either way, i.e. not a step-position artifact.

- **[measured, bamshanks, 07.09.2026, later message]** Root cause found, with a patch.
  Mechanism (as reported): the sequencer keeps exact fractional event times and fires
  each recorder trig at `⌊event⌋`. The recorder length is computed once per pass and
  never moves afterward. At 128/RLEN4 the period is 20,671.875 samples, so an
  eighth-of-a-sample residue accumulates; once every 8 passes two arm events land
  20,671 samples apart while the recording itself is 20,672 samples long — a
  one-sample overlap at the loop point, audible once every 2 bars. Cited as measured
  "over ten passes" in `docs/RTOS_FORK.md §10.16.5` (note: per this repo's own history,
  `docs/history/RTOS_FORK.md` was later removed on 16 Sep 2026 — the citation is still
  the documented provenance and recoverable via `git show` per CLAUDE.md's own
  instructions).
  - Two corrections bamshanks made to Bryan's spreadsheet model: (1) the residue does
    not walk in trig *positions* — it accumulates in the exact fractional event times,
    and `⌊·⌋` releases it as one whole sample every `1/ε` passes; (2) the length
    converter multiplies by a **truncated** reciprocal `⌊2³¹/tempo24⌋`, so an exact
    `x.5` quotient rounds **down**, not up — Bryan's 128 BPM / RLEN 16 row was
    82,688 in the sheet, but the firmware computes 82,687. (Cited to `§10.16.4`.)
  - **Flag: may relate to existing project trap docs.** This rounding/truncation
    behavior of the length converter, and the recorder-arm-timing mechanism, sound like
    they could already be captured (or should be cross-checked against) whatever this
    repo's current recorder/repitch/timestretch documentation says about tempo24
    arithmetic and frame-based event timing — worth a human diff against
    `docs/TIMESTRETCH_PIPELINE.md` and any RTOS_FORK-derived doc.
  - The fix shipped as `modules/recorder-seam/` — described as a **ColdFire cave at the
    length converter's tail, address `0x40006e0c`**. It re-derives the recorder length
    every frame from the sequencer's next step event using the frame builder's own
    arithmetic, and substitutes it only when the result is within one sample of the
    stock length (so it doesn't touch a deliberately different RLEN). Files named:
    `seam_cave.s` (source), `manifest.py` (pins the bytes), `README.md` (register map).
    Build via `remixes/seamtest.py` (bus + the cave): `REMIX=seamtest make bus`, or
    `REMIX=seamtest BUILD=<nn> make image` for a card image.
  - Commit referenced (verbatim): https://github.com/sambanks/octabam/commit/4405a122133262389cfcd4d8672312ddbeb35076
    — "RTOS 10.17: recorder-seam ColdFire cave — fixed-RLEN recordings sized from the
    sequencer's next event (seams 0 in route A, unflashed)" — i.e. **unflashed at time
    of posting**; only emulator-verified when announced. A `§10.17` citation exists for
    this that isn't mentioned in this repo's current CLAUDE.md history section (which
    only cites up to `§10.16.x`) — worth a human checking whether `§10.17` is preserved
    somewhere.

- **[measured, bamshanks, 08.09.2026]** Diagnostic protocol proposed to separate causes
  when Bryan reported clicks persisting with a *live input* (Moog into Input A) rather
  than a sample: (1) record one pass, delete the REC trig, keep PLAY trig every 4 steps
  — does it click? (2) delete the PLAY trig too, let the buffer free-loop with LOOP on —
  does it click? The idea: clean on one and clicking on the other isolates whether the
  cause is the recorded content itself, the retrig, or the loop point. (Outcome not
  resolved within this transcript — the "whale" callback ("the whale remains elusive")
  suggests the live-input case was a separate, still-open issue as of 8 Sep.)

- **[measured, bryant12345]** Pickup machines resample **before** effects — a firmware
  behavior he didn't remember correctly until testing it live: "I was just playing
  around with Pickup machines and it does seem that they resample before the effects. I
  didn't remember them working that way. Neat." (03.09.2026). By contrast, Flex-track
  self-recording (SRC = own track) captures **after** effects — this asymmetry is what
  drove the "can Flex record pre-FX like Pickup does" discussion.
  - **[inferred, bryant12345]**: "my mental model now has the Pickup machine entirely
    on the ColdFire side, then passing the loop to the DSP" — offered as a guess for
    why pre-FX Flex recording might not be straightforward; explicitly not verified.

- **[measured/practical, bryant12345]** A working Flex overdub recipe without any
  firmware change: Input A (e.g. guitar) → SRC3 = T1 → records onto Recording Buffer 1;
  Track 1 is a Flex track playing Recording Buffer 1. The buffer doesn't have to record
  continuously — it can be armed and overdubbed on demand; "the clickless stuff only
  really matters if you're leaving it recording perpetually."

- **[measured, bamshanks]** The freeze delay is described as "a buffer but it is
  triggered" and Bryan T states plainly: "The delay is a four-second buffer that's
  constantly recording" (when in freeze). Later in the multitrack-streaming discussion,
  Bryan T states the delay and recording buffers already have per-track SDRAM
  round-trip "plumbing" — **individual stereo tracks, not one 16-channel block** — which
  is offered as evidence that streaming all 8 tracks to CF is not starting from zero.

---

## 2. Multitrack streaming to CF / USB multitrack audio — active but unverified engineering

A long, speculative-but-technical thread (14 Sep 2026) between exit_planet_dust (a
self-described "electronics person, not a coder"), bryant12345, and yvez_me, about
streaming all 8 tracks to compact flash or over USB. Treat everything numeric here as
**[inferred/estimated, not measured on hardware]** — several numbers are explicitly
attributed to asking "gemini" for a plausibility estimate, not to any actual profiling.

- Proposed pipeline (exit_planet_dust's diagram, verbatim ASCII):
  ```
  [DSP Core (DSP56300)]
         │ (Taps 8 stereo tracks into 32-frame mini-chunks)
         ▼
  [Internal DSP SRAM] ──(2 KB burst every 0.725 ms)
         │
         ▼ (DSP Hardware DMA / Host Interface)
  [SDRAM 4 MB Ring Buffer] ──(Accumulates until 128 KB)
         │
         ▼ (stems_task)
  [CF Card] ──(Sequential ATA write burst: 20 ms lock / ~70 ms free window)
  ```
- **[estimated, not measured]** Naive approach (DSP writes straight to SDRAM, waits on
  main memory): ~152 DSP cycles cost, 1.35 MB RAM, ~100 ms latency, "about 5% DSP load."
- **[estimated, not measured]** Alternative (DSP drops frames into on-chip SRAM first,
  flushes every 32 frames, ~2 KB SRAM cost): reduces cost to ~16 DSP cycles.
- 8 stereo tracks at 24-bit/44.1 kHz = 2.11 MB/sec raw data rate (arithmetic, not an
  estimate — straightforward calculation).
- **[opinion/inferred, exit_planet_dust]** USB class-compliant / Overbridge-style audio
  is judged unlikely: "USB is managed by the CPU and it would require completely
  changing how the CPU manages USB." A non-class-compliant async alternative is floated
  instead: SDRAM ring buffer → CPU chunks blocks → sends over USB → a companion PC-side
  tool unpacks them. Not truly live, but usable for stem capture.
- **[in progress, self-reported, canardval_92147, 14.09.2026]**: has started work on
  "multitrack USB audio with 8 separated stereo tracks for the OT mk2" and says "it
  seems doable" — but this is a personal early-stage assessment, not a working
  prototype at time of posting, and long timeline expected ("a long work").
- **[in progress, self-reported, yvez_me]**: posted a PR to the octabam repo
  (09.09.2026, "Highly vibe-coded... lots and lots of grains of salt") proposing
  8-track recording to CF, and later (14.09.2026) a working branch:
  https://github.com/yvesrosius/octabam/tree/stem-rec-poc — described in-channel as
  recording 15 seconds of 16-bit audio from T1 directly to CF, first green run of
  `verify_stems.py`. Explicitly asked for review "before I flash."
- **[caution, bryant12345]**: has seen the OT display a `!` symbol under load using
  Static tracks and doesn't know exactly what it's complaining about — raised as a
  concern for whether sustained CF writes during playback would trip something similar.
  Also questions whether repeatedly writing buffered audio to CF on stop would stress
  the card.
- **[caveat, exit_planet_dust]**: OT doesn't use UDMA (not required, but a UDMA7 card
  would have "a significantly better controller" and fewer write-stall issues); no
  visibility into the spec of the OEM CF card; recommends testing write speed / clean
  format on real cards before trusting any of this.
- **Flag: may relate to existing project trap docs.** The description of the delay
  and recording buffers already round-tripping through SDRAM per-track lines up with
  this repo's own documented DRAM/ring-buffer layout (the alias-fold and ring-base
  traps already logged in CLAUDE.md). A human should check whether this externally
  proposed pipeline would collide with the delay ring's addresses documented there
  (e.g. `0x4F502C10`, the shared-window regions at `0x30000`/`0x34000`/`0x38000`).

---

## 3. In-progress community mods mentioned (status snapshots, not this project's work)

These are other people's independent firmware mods referenced in-channel — useful for
awareness of what else exists in the ecosystem, not verified by this project.

- **Direct pattern jump** — zackyoti_98392 (12.09.2026): "I built it. Can't flash for a
  couple days for testing, but it's emulator verified end-to-end." **[measured in
  emulator only, not yet hardware-verified at time of the message]**.
- **Sidechain compression** — zackyoti_98392 (17.09.2026): "Yes, I built sidechain.
  Working, but I'm still hunting a fix for a bug in my keytrack monitoring — the
  monitor audio passes through a multimode filter that is jacking up the sound when a
  trig fires on the target track. The main sidechaining function is solid, but I don't
  want to ship until the monitor is bug free." Also: "Not quite as easy as you might
  think, esp making it cross-core" — a firsthand note that cross-core coordination was
  the hard part, echoing this project's own documented cross-core race history.
- **MIDI CC-out FX / internal MIDI loopback substitute** — bukkakeborealis built and
  shared (as a `.bin` in a "demos" channel, not this repo) an FX that sends 5 MIDI CCs
  out, working with scenes/crossfader/step-locks. gotem4life (06.09.2026) is separately
  investigating true internal MIDI loopback (FX2-slot p-locking of roots/chords, or
  routing through an internal MIDI channel) — outcome unresolved in this file.
- **Repitch warp mode** — .reliktfarn (16.09.2026): "We finally need a repitch warp
  mode. Currently on it." (No further technical detail given here; matches this
  project's own known `repitch` module work per session memory — likely the same
  effort or a closely related one, worth a human cross-check.)
- **Unnamed third-party pickup-machine mod** (misterairplane, 11.09.2026): mentions
  receiving a tool from someone on Elektronauts that disables auto-BPM-set from pickup
  machines and adds long-press-copy-pattern-to-next-pattern; not shared in-channel
  because redistribution permission wasn't confirmed. bukkakeborealis confirms trying
  it too, and separately confirms (18.09.2026) that **Octakit already implements**
  instant pattern+kit cloning: "It works in octakit, clone pattern+kit to next one
  instantly."
- **New parameter page ("page 6")** — bukkakeborealis (17–18.09.2026): "Managed to
  create a new parameter page. Now the hard work is getting them locked etc." Access
  currently via the FUNC/arrow-up-down page combo; still needs a setup page; goal is
  assignable extra params (different targets/tracks) with per-track probability, plus a
  simple audio-track arp living on the new page. **Flag: may relate to existing project
  trap docs** — this repo has documented, in detail, the descriptor-clone /
  display-formatter trap (`verify_menu`, count-vs-formatter mismatches) and the
  fixed-size name-field overflow trap; any new page work by other community members hits
  exactly that surface and is worth cross-checking if this project ever imports it.
- **Custom oscillator machine replacing Static** — bukkakeborealis (03.09.2026):
  "testing an oscillator (replacing static machine for now) it enters the Amp page and
  can be shaped by envelopes... does react to chromatic mode," but has "trouble tuning
  it properly" (unresolved pitch drift as of the message). Also claims: "I've found out
  there are 3 more machine slots after pickup but couldn't select them yet" — an
  **[unverified/inferred]** claim about unused machine-table slots, floated as a future
  "Octamachine" concept. Not confirmed elsewhere in this file.
- **mrscruff2277's personal build** (30.08.2026) — self-reported as already
  implemented: double-tap scene buttons to mute/unmute one-handed; "active scenes
  persist through part switching" (ported from a firmware called Octamax); MIDI tracks
  send duplicate CCs when a trig is present; improved lofi distortion/saturation
  algorithm. An improved reverb for DJ wash/transition effects was in progress, not yet
  done.
- **LOFI2 module progress (Bryan T)** — 05.09.2026 milestone: first effect rendered,
  278 words; ring mod with low/high modes "more like the Moog 102"; frequency shifter
  with subtraction/addition modes and feedback; a stereo Bode frequency shifter planned
  but not yet implemented ("will be expensive since it will be stereo — the one from
  mutable was mono"). 12.09.2026 update: **[measured, tested on hardware]** "Made some
  good progress with LOFI2. Tested it on the Octatrack." Ring mod low/high modes and
  frequency shift up/down modes confirmed working; stereo phase control on the ring mod
  added but uncertain if it will be kept. **Flag: may relate to existing project trap
  docs** — this is very likely the same `LOFI2` module the project's own CLAUDE.md
  documents as having shipped with an absolute (not per-payload) stock-table address
  bug ("mistuned on tracks 1–4"), found 13 Sep 2026, i.e. shortly after these
  in-channel progress reports. Also the same contributor ("Bryan T") whose
  `modules/hello/` overflowed a 5-byte `abbr` field per the fixed-size name-field trap.
  Good candidate for cross-referencing dates/commits if anyone audits that history.
- **bamshanks' own effects architecture** — described in his own words (16.09.2026):
  "Character is pretty tested and ready. As is Spectrum (filters and stuff), I'm just
  working on my final one now which is a modulation station... I'm replacing the whole
  effects architecture for my stuff." Links given:
  https://github.com/sambanks/octabam/blob/main/modules/character/README.md and
  https://github.com/sambanks/octabam/tree/main/modules/warpfold (a Mutable
  Warps/Wavefolder port). Also references porting "something like braids to the
  ColdFire" as a longer-term idea ("that's down the list").

---

## 4. Menu / UI / descriptor architecture notes

- **[opinion, bukkakeborealis]** On why MIDI CC knobs can't easily show the raw CC
  number instead of a generic "CC1/CC2" label: "Because after machines/fx selection it
  gives static names in stock" — i.e. label text appears to come from a static
  per-machine/effect table, not a dynamically formatted value. Unverified mechanism,
  but consistent with this project's own documented descriptor/display-formatter
  coupling.
- **[fact, gurttractor, crossposted from Elektronauts, 05.09.2026]**: stock firmware
  already has a `MAP/TRACK` setting (in audio note-in settings) that lets each track
  respond differently to incoming MIDI notes — e.g. slices for one track, slots for
  another — but this per-track behavior was never extended to the trig-mode switch you
  operate manually on the device (you have to keep toggling FUNC+UP/DOWN globally when
  changing tracks). Presented as an existing, testable stock behavior.
- **[opinion/technical suggestion, mrscruff2277, 12.09.2026]** On implementing
  per-track "remembered trig mode": "I would assume that means finding 3 bits of unused
  storage per pattern and then adding a hook on pattern change to set the mode." A
  concrete guess at where such state would need to live (3 bits × 8 tracks, per
  pattern) — not verified, but a reasonable technical starting point if anyone builds
  this.
- **[fact via testing, bryant12345]** "XVOL already shows that different curves are
  possible" — offered as evidence that the crossfader/level mapping is not
  hard-wired to one linear curve, in response to a request for alternate crossfader
  curve types (DJ-mixer style). No further detail on how XVOL's curve is implemented.
- **[fact, tenacious_lemur_99636]** "The glass itself is red so no RGB possible I
  think" — explains why any "different LED color" UI proposal (e.g. inverted colors for
  a hypothetical page 5-8 indicator) is a non-starter on this hardware. Stated as fact,
  not deeply sourced, but plausible/consistent with known OT hardware.

---

## 5. Known stock-firmware bugs reported by the community

- **[reported as known, homeboiflex, 30.08.2026]**: BPM resets to the project BPM when
  changing banks, even when patterns have their own per-pattern BPM set. Called "a
  known bug."
- **[firsthand report, rolandjx3p, 06.09.2026]**: on a MIDI track, entering a note via
  an external keyboard (hold step + press key) registers correct velocity; if you then
  replace that note the same way, the new velocity is ignored and the old one is kept.
- **[firsthand report, befriendthedragon_93582, 06.09.2026]**: "dub aborted" errors
  occur with pickup machines; asks whether it's related to Master Tempo override or
  timestretch — not answered/confirmed in this file (bamshanks: "not me but I never use
  pick up machines to date").
- **[architecture fact, _bradf, 06.09.2026]**: the Octatrack has 256 patterns where
  every other Elektron device in the ecosystem (Digitakt, etc.) has 128 — so
  program-change-based multi-device pattern sync (e.g. OT + Digitakt) only works for
  the first half of the OT's patterns under the standard PC scheme. Proposed fix
  (wishlist): a toggle to select whether banks 1–8 or banks 9–16 respond to/send
  program change 0–127.
- **[community-sourced, links only, referenced by bryant12345]** Elektronauts threads
  with independently-measured compressor parameter tables (not this project's own
  measurement, cited as prior research bryant12345 used before digging into code):
  - Ratios: https://www.elektronauts.com/t/ot-compressor-meaning-behind-the-values/151923/35
    — RAT knob values for target ratios: 1:1→0, 1.2:1→21, 1.5:1→43, 1.8:1→57, 2:1→64,
    2.5:1→77, 3:1→86, 4:1→96, 5:1→105, 6:1→109, 8:1→115, 10:1→119, 12:1→122, 15:1→127.
  - Makeup gain: https://www.elektronauts.com/t/compressor-makeup-gain/254416
  - bryant12345's general observation on reverse-engineering effect parameters: "Takes
    some creativity to recover the values for the more complex effects... if only [it
    were] look up value in table, plug into equation."
- **[considered and rejected, bryant12345, 12.09.2026]**: an idea to add a
  higher-sample-rate-ratio pitch mode to lo-fi by dropping half the samples was
  self-reasoned through and abandoned: "it would basically take a given bit depth and
  throw out the top part of the range... which is exactly what a lower bit depth
  setting would do." Documented here as a dead end so it isn't re-investigated.

---

## 6. Hardware constraint claims (mostly hedged, not confirmed)

- **[hedged/inferred, bamshanks]** On Analog Rytm-style master distortion applied to
  individual OT outputs: "Sadly I believe that would be a hardware constraint... could
  be wrong but I would assume so."
- **[self-acknowledged speculation, sawtoothwave]** Reconfiguring the 1/4" I/O jacks as
  inputs or outputs per-project: "I'm sure this is completely impossible on a hardware
  level but hey, you asked."
- **[opinion, exit_planet_dust]** Overbridge/USB-class-compliant audio "probably not,
  because USB is managed by the CPU and it would require completely changing how the
  CPU manages USB." Separately, _anfim states flatly "Outbox depends on overbridge, OT
  doesn't have the hardware" — asserted, not sourced.
- **[architecture note, bamshanks, 28.08.2026]** On why a reverb/delay's menu can't
  easily live outside a host track: "I would love to put the menus for it somewhere
  else, rather than a track hosting it, but I don't think it's really possible... needs
  a host track." Also: the CUE bus "can't be bussed" internally the way the new
  send/return bus can — "you can't bus it though, so gotta think through the routing."
  Both are architecture observations from bamshanks' own build experience, stated with
  some hedging.
- **[design note, bamshanks]** The harness used for building effects is deliberately
  "locked to the same limitations as the hardware, so you can tell how much space you
  have as you are getting it in there" — i.e. space accounting in the dev harness
  mirrors real DSP/word budget constraints, not a separate emulated-only limit.

---

## 7. Feature wishlist themes (brief, grouped)

No technical backing beyond the request itself unless noted. Grouped for future module
planning reference.

- **Recording/looping**: auto-save Flex recordings to a free Flex/Static slot with
  auto-selection and no playback interruption; punch-in/out overdub instead of
  buffer-erase on Flex; "skip-back"/always-running buffer recording (SP-404 style);
  routing matrix to recording buffers independent of MAIN/CUE; conditional recording
  (trig-condition-gated); threshold-triggered recording; loop-start updatable mid-loop
  (for single-cycle waveform scanning); crossfade/clickless-loop tool in the audio
  editor.
- **Sequencer/patterns**: LST + direct-pattern-jump simultaneously (currently believed
  mutually exclusive on every Elektron box that has one or the other); live pattern
  fork/clone of the currently playing pattern without pre-selecting the destination;
  looping a portion of the sequencer; page-length-aware page jumps for step counts <16;
  Euclidean sequencing; >8 arrangements in the Arranger; global per-track trig
  probability p-lockable; per-track "remembered" trig mode; disable/long-press-guard
  the stop and clear-pattern combos; a real undo without a time limit.
- **MIDI**: scenes for MIDI tracks; internal MIDI loopback without external cabling;
  NRPN support; renaming CCs; naming CCs on the UI; DT-style true Note Off instead of
  velocity-0; overlapping/polyphonic long notes across steps; 6–8 note polyphony;
  step-locked Program Change; MIDI CC glide/slide between p-locks with selectable
  curve shapes; velocity → Amp Vol mapping; note-length mapping; per-page MIDI CC
  "auto channel" context control of the 6 encoders; humanized chord note timing.
  Two people (kjnilsson, bukkakeborealis) reported independently prototyping
  global/per-track PROB for the MIDI sequencer around 17.09.2026, comparing notes on
  method (MIDI-seq only got theirs "kinda working"; audio-seq attempt using XVOL as the
  parameter host "no luck").
- **Mixer/gain staging**: dB-scaled gain/level values instead of 0–127; sidechain
  compression; a true peak limiter; a compressor mode with 0 attack acting as a
  limiter; base/width filter for sample tracks; 2nd LFO (noted: "Elektron said they
  tried and failed" per _anfim — **unverified**, hearsay); envelope follower as a
  modulation source; gate FX (toggle mode on the compressor).
- **Effects**: better/interchangeable reverb and delay (large existing thread, being
  actively worked by bamshanks); wavefolder/waveshaper FX; gain cut/restore control
  paired with bit-reduction (Bryan T's LOFI2 direction); OTT-style multiband
  compressor; "RAS Bonkers"-style distortion+EQ+feedback effect; harmonic tremolo
  (kjnilsson, in progress); slew/smoothing control for LFO shapes (square, S&H).
  DC-offset removal from "stock offending effects" was raised independently by
  Bryan T (30.08.2026) as a clean, simple win — worth checking against this project's
  own already-documented DC-offset/persistent-slot findings.
- **Synthesis / machines**: porting Mutable Plaits/Braids-style synthesis to the
  ColdFire (bamshanks: "longer term... down the list"); dual-oscillator/wavetable
  machine idea inspired by the Microwave XT, with pre-filter ring mod and
  aliasing/quantization character; round-robin sample sequencing (Volca-style, cycles
  through up to N samples per trig); barebones polyphonic machine as a proof of
  concept; MIDI drum sequencer with per-note-per-channel visualization for one-MIDI-
  channel multi-voice targets (e.g. targeting a Pulsar-23).
- **I/O / routing**: per-input (A/B/C/D) DIR routing on the mixer page instead of
  paired AB/CD; CUE bus panning; scene-lockable "send volume to Cue" pre-stage;
  8-track individual outputs (wishlist, acknowledged hardware-heavy); a pre-send
  HPF/LPF ahead of the shared BusDelay/BusVerb aux bus (pinkpanther606, 18.09.2026, with
  a specific suggested frequency list: OFF/60/90/120/160/220 Hz).
- **UX/ergonomics**: double-tap-safe trig deletion (currently oversensitive on MKII per
  mentholatum1761, contrasted with the Digitakt "same buttons" not having the issue);
  congruent FUNC-snap-to-default behavior across all parameters; sample
  search/filtering by name; software-scalable (less sensitive) MKII encoders; naming
  tracks and patterns (not just projects); a visual "this pattern uses Fill
  conditions" indicator.
- **Vision-level / synthesis of the whole project** (antonio110582._72773,
  29.08.2026): combine Elektron Model-series-style 256 Kits (replacing Parts),
  OctaBAM's send/return bus with shared reverb/delay, and a chooser to swap in
  different insert-FX modules, while keeping the stock sequencer/scenes/project
  structure untouched. Framed explicitly as already close to being realized by this
  project's direction. Pure aspirational synthesis, not a technical claim, but useful
  as a signal of what community members already believe the roadmap is.

---

## Notes on sourcing quality

- The recorder-seam thread (§1) is the only place in this file with hard numbers,
  addresses, and a shipped commit — everything else technical is either a hedge, an
  estimate explicitly sourced to asking an LLM for a plausibility check, or a
  self-reported "I built X, works/emulator-only so far" claim from someone outside this
  project's own toolchain (their claims are not independently verified here).
- Several claims cite `docs/RTOS_FORK.md` section numbers (§10.16.4, §10.16.5, §10.17)
  from *inside* the Discord conversation, at a time before this repo's own
  `docs/history/` removal (16 Sep 2026). Per this project's CLAUDE.md, that citation
  chain is recoverable via `git log --all -- docs/history/RTOS_FORK.md` /
  `git show <sha>:docs/history/RTOS_FORK.md`, and `§10.17` in particular doesn't appear
  in the CLAUDE.md excerpt available at the time of this extraction — worth a follow-up
  check that it's actually preserved in history.
