# MIDI Scenes — Discord channel findings

Source: `Octahackers - OCTATRACK - midi-scenes [1545532434660196464].txt` (327 messages, 4–19 Sep 2026).
Author of the mod: **bukkakeborealis** ("bkkbrls-del" on GitHub), working from Octatrack **1.40C**.
Primary tester/reviewer from this project's side: **bamshanks** (sambanks/octabam). Also present:
bryant12345 (Bryan T), emuyia (em, Octakit author), devilfish707, pituzinho9269, mayrakissa, and others.

## What the mod does

- Adds MIDI parameter-locking to scenes (A/B crossfader), mirroring how audio-track parameters already
  lock to scenes and morph via the crossfader. "Every parameters of every pages of midi tracks are
  lockable to the 16 scenes to A and B and morph between them with Xfader. Same as audio per parts per
  bank." — bukkakeborealis, 05 Sep, firsthand (author's own build/test).
- Reloadable, copy/paste/clear scene data for MIDI tracks, matching stock scene UX. (bukkakeborealis,
  05 Sep, firsthand.)
- Note/arp values locked to scenes update **only on trigs**, not continuously like CC crossfades — stated
  explicitly by the author as an architectural property, not a bug: "notes locked to scenes update only
  on trigs. XF on a CC should not lag much though" (bukkakeborealis, 11 Sep).
- Octatrack Pitch Bend (PB) and Aftertouch (AT) can also be locked to scenes and are sent correctly
  (bukkakeborealis, 12 Sep, firsthand claim, no independent confirmation seen in this channel).
- Explicitly NOT included (as of this channel's timeframe): sequencing audio tracks from MIDI tracks
  without a physical MIDI cable (DIN-out looped to DIN-in). Author says this "could be added" via MIDI
  note setup selection beyond channels 1–16 (T1–T8 audio-track targeting), referencing an idea from an
  earlier personal project called "MSCN" (a MIDI effect) that did something like this in reverse
  (bukkakeborealis, 12 Sep). Speculative/roadmap, not implemented.
- Roadmap items mentioned but not delivered in-channel: muting MIDI tracks/notes per scene (velocity=0
  idea raised by community, "could find a way internally" per author, 06 Sep — unresolved); a
  "CONTROL ALL" custom machine concept (parameters of other tracks controllable from one track) and
  synthesis-based custom machines — these are described as *separate, future* projects, not part of
  midi-scenes itself (bukkakeborealis, 05 Sep).
- Author considered adding "midi slides" (a quick combo to set trig slides without the extra menu dive)
  but this stayed at brainstorm stage with community pushback on UX feasibility (13–14 Sep, bryant12345,
  tenacious_lemur_99636, re5etuk); not implemented for midi-scenes.

## Storage / firmware implementation details

- "Midi scenes were not built in stock firmware so had to create their data storage, include that in
  bank/parts for saving and recall and implement XF over trig locks while retaining lfo." — bukkakeborealis,
  09 Sep, firsthand description of the implementation approach. No specific addresses given in this
  channel.
- "for storage had to find room for it where there was some" (09 Sep) — implies scavenging unused
  space in the existing bank/part data structures for the new MIDI-scene-lock data, consistent with this
  project's own documented trap about persistent slots and part/bank layout changes (see
  CLAUDE.md's "A PART SAVED UNDER AN OLDER SLOT LAYOUT..." trap) — **may relate to existing project trap
  docs**, flagged for human cross-check since no exact slot/offset is named here.
- No FX2 ids, hook sites, detour addresses, DSP registers, or ColdFire symbols are named anywhere in this
  channel — this is entirely a UI/data-model level MIDI-page feature, not DSP or bus work.

## Cross-project technical exchange (bamshanks <-> bukkakeborealis / emuyia)

- 10 Sep, bamshanks: "I've been doing a little work on a remix with midi-scenes and octakit and need a
  couple mods, but also think my new emulator might have found a decent bug. It finds heaps of stuff the
  old harness doesn't." Two attachment files were shared but their content is not present in the export
  (Discord attachments, not inline text):
  - `octabam-notes-for-bkkbrls-del.md` (10 Sep, and a follow-up "one more little fix please" on 11 Sep,
    same filename)
  - `octabam-notes-for-em.md` (10 Sep, questions for emuyia)
  bamshanks notes "They compile fine together just some minor crossover that needs resolved" and "Take
  them with grains of salt etc" (10 Sep) — i.e., the notes are inferred/preliminary, not fully verified.
  These `.md` files are not retrievable from this text export; if their content matters, they would need
  to be sourced from Discord directly (attachment URLs are given in the raw export around lines
  613/626/1050 of the source file) or from bamshanks/sambanks directly.
- 10 Sep, emuyia responding to bamshanks' questions about Octakit's memory footprint (context: making
  midi-scenes + Octakit coexist in one remix):
  - "octakit only needs that `0x47fc7410..0x47fd910f` memory area on boot. after that its code lives in
    the reserved flex pool space, so the temporary copy is no longer needed"
  - "kits retain the part layout / offsets"
  - "saved kit data is available via `__gk_canonical_payloads`. the saved kit and active working kit are
    separate though, so changes need to go through octakit's editing functions so they're included when
    you save the kit. the sequence is `gk_workspace_prepare`, `gk_physical_acquire`,
    `gk_descriptor_store_byte` for each changed byte, `gk_workspace_mark_dirty_pending`,
    `gk_workspace_commit_update` and `gk_descriptor_release`"
  This is a **firsthand, specific technical claim from Octakit's author** about Octakit internals (memory
  range, function names/call sequence) — high-value, likely load-bearing for anyone composing Octakit with
  another ColdFire mod. Not midi-scenes-specific but directly relevant to this project's module-composition
  work.
- 12 Sep, bamshanks: "Popped a PR in to enable your repo as an upstream source" — i.e., bukkakeborealis's
  `midisc` repo was integrated as an upstream source in (presumably) the octabam/octamad remixer tooling.

## Bugs found and fixed (chronological, all firsthand author reports unless noted)

- **06 Sep** — "scenes not surviving the boot inside the parts" (i.e., MIDI scene lock data didn't
  persist correctly through a reboot/part reload). Author: "It'll take longer than I thought."
- **06 Sep** — Lag/performance degradation "with many tracks locked" when combining trig locks + scene
  locks together (the "full path"). Author distinguished two architectures:
  - Option A: scene locks and trig locks run in parallel (near-zero latency, but "doesn't behave entirely
    like audio scenes" — locking a note to scene B while A has a trig-locked note acts like transpose
    rather than a proper mix/crossfade of the two notes).
  - Option B ("full path"): true trig-lock/scene-lock interaction like stock audio scenes, but originally
    "very quickly (5-6 locks on scene) slows down and even crash" (07 Sep). Author: "I know what Elektron
    meant now" (implying this is why Elektron never shipped MIDI scenes — a real performance/complexity
    constraint, not just neglect).
  - By 07–08 Sep the author reports getting the "full path" working with "little latency" / "no lag issue
    at all" after further optimization — firsthand, but caveated ("will need some more testing").
- **09–11 Sep** — Multiple project/part persistence bugs during the initial GitHub releases:
  - "sticky locks on parts after part paste" (10 Sep).
  - Bug where reloading a project saved with a previous midi-scenes build could "brick" — mitigated by
    telling users to use a new project or one not saved under the older version (11 Sep, version
    1.40MIDISC5 release notes: "parts/projects-save/reload fixed", "CC leak fixed").
  - "known bug if you save project on any other bank than bank1. Reloading project will hang." (12 Sep) —
    fixed same day/next day per "the proper project save/reload from all banks (not just bank1) is fixed"
    (12 Sep, later message).
  - "currently fixing values jumps on trigs" (12 Sep) → "removed the values jumps on XF moves over Trigs"
    (12 Sep, later same day).
- **12–13 Sep** — CC crossfade "steppy"/quantized sound reported by devilfish707 when the CC-target synth
  is sequenced (notes) from the *same* MIDI track as the CC lock; smooth when a separate MIDI track (no
  trigs) carries the CC. Author confirms: "I made a change yesterday to the mix behaviour. That might be
  it" and later "I noticed the stepping issue. I think I know why it is doing that." This reads as a
  real, reproduced, firsthand-diagnosed bug tied to how CC values are mixed/interpolated when a track's
  note trigs interact with its own CC scene locks — root cause not fully stated in-channel.
- **12–13 Sep** — Machine-selection UI bug: on tracks other than FLEX/STATIC, moving right on the pad to
  select a machine doesn't move/animate the selection (only YES works) — pituzinho9269 (12 Sep) and again
  independently (17 Sep). Author's guess: "I might have done something when selecting new machines and
  the menu for CC filters and didn't revert" (12 Sep) — **unresolved as of 19 Sep** (see below); this
  looks like an unintended side effect of the (later-removed) CC-filter menu work.
- **13 Sep** — Known bugs called out explicitly before fix: "part reload" and "part change waits for
  pattern length"; fixed same day in release "1.40MIDISCN8": "fixed the part reload", "fixed part change
  latency", plus "CC filters in midi control menu (they don't persist on reboot or project save yet)".
- **14 Sep** — Author removed the CC-filtering feature entirely ("it was giving me trouble") after
  struggling to debug it, deciding to "settle on the last version" (no CC filters) rather than keep
  fighting it. Per 17 Sep message the shipped build is "1.40MIDISC8.1... without CC filters" (a naming
  correction — the GitHub `1.40MIDISC8` build was reported as still having CC filtering enabled,
  contradicting the "removed" statement; the author clarifies 8.1 is the no-filter build).
- **18–19 Sep (last messages in export, still open as of 19 Sep 2026)** — Two more serious, apparently
  unresolved bugs reported firsthand by pituzinho9269 on 1.40MIDISC8.1:
  1. **Audio machine/track-selection instability**: on tracks 5–8, a newly created STATIC pattern
     produces no sound; switching to FLEX produces sound but reverts to STATIC as soon as the
     machine-select menu is exited; pressing YES on a machine selection "reverts to static" the first
     time and "sticks" only on a second attempt, or reliably if you change track before leaving the menu.
     Author reproduced testing FLEX/STATIC on tracks 5–7 but "does not happen" for him initially (19 Sep);
     later reproduced the "reverts to static on NO" behavior himself and pushed a fix ("updated GitHub and
     the patcher with a know [sic] good version today", 19 Sep). Also reported: "false triggers that
     dont make sound when changing from midi to audio", and a **crash that lost all MIDI pattern info
     when going back and forth between MIDI and audio track views** (channel assignments recovered after
     reboot) — 17 Sep, pituzinho9269, not yet confirmed reproduced by the author in this export.
  2. **Crash/EXCEPTION on FUNC + Record menu 2**, reproducible "from any page" — pituzinho9269, 19 Sep.
     Author confirmed: "so I bricks with func+rec2. I'll have a look at that." — acknowledged but no fix
     landed within this export's timeframe.
  - Standard troubleshooting advice reiterated by the author and community throughout: always reload
    the project after flashing new firmware, and don't trust behavior from a project last saved under a
    different/older experimental build (e.g., zackyoti_98392, 19 Sep: "Ensure you reload your project
    before testing... I've noticed that can clear up a lot of stuff that looks like bugs at first"; author
    repeats this pattern multiple times, e.g. 09–13 Sep bank/part bugs traced to stale saved projects).

## Known/accepted limitations (not bugs, stated by author)

- Notes/arp values locked to scenes only update on trigs (not continuously) — inherent to how trig-based
  sequencing works, not planned to change.
- Performance ceiling exists when mixing many trig locks with many scene locks simultaneously — author
  chose the "full path" architecture after iterating, but flagged from the start that "there will be
  limitations" (06 Sep) and "I know what Elektron meant now" (07 Sep, i.e., speculating this constraint is
  *why* Elektron never shipped official MIDI scenes).
- CC48 (crossfader), CC55 (scene A), CC56 (scene B) are sent as real MIDI CC messages out of MIDI tracks
  and can flood/confuse connected synths (repeatedly reported: bamshanks says the raw crossfader traffic
  "nukes my prophet" and he has to filter it heavily on a Midihub, 10 Sep). An in-firmware CC filter for
  48/55/56 was attempted (added ~13 Sep, "CC filters in midi control menu") then **removed 14 Sep** due to
  bugs, and remains unresolved/off as of the last messages (17–19 Sep). Workaround: external MIDI
  filtering hardware (Midihub) or per-synth CC-ignore config.
- No 14-bit MIDI message locking mentioned beyond PB/AT (channel pressure not addressed either way in
  this channel; a user asked, author answered only re: PB/AT).
- Direct audio-track sequencing from MIDI tracks without a physical MIDI loopback cable is not supported
  (see above); MIDI-note targeting of audio tracks/slices via an arpeggiator is described as a *future*
  idea from the author's separate "MSCN" project, not delivered here.

## Licensing / distribution note (directly relevant to this project's "never an Elektron byte" rule)

- **05 Sep 2026, bukkakeborealis**: "I realised I shared a modified firmware which is copyrighted. I'll
  prepare a link with different the features I am working on that can be rebuilt with your own OS." This
  is an explicit, firsthand acknowledgment that an earlier share (presumably a pre-built, distributable
  firmware binary/image containing Elektron's copyrighted OS) was improper, followed by a stated
  correction: distribute a way to **rebuild** the mod from the user's own stock OS instead of distributing
  the modified binary directly. Reaction from another member was two 🚔 (police-car) emoji, i.e. calling
  out the copyright concern.
- This correction was carried through for the rest of the project's life in this channel:
  - The GitHub repo description itself states the policy: "Octatrack 1.40C MIDI scene locks (1.40MIDISC)
    — rebuild from your own stock OS" — https://github.com/bkkbrls-del/midisc (linked 09 Sep 2026).
  - A browser-based build tool was published so users patch their own dumped stock 1.40C rather than
    receive a prebuilt image: https://bkkbrls-del.github.io/midisc-patcher/ ("MIDISC patcher — Browser
    patcher: build 1.40MIDISC for Elektron Octatrack from your own stock OS 1.40C.", linked 10 Sep 2026).
  - The author repeatedly reminds users the process starts from "your own stock 1.40C from Elektron" (19
    Sep exchange with pituzinho9269: "Should I create the OS from a stock 1.40C from elektron?" / "On the
    patcher yes").
  - This is exactly the pattern this project's own CLAUDE.md mandates ("Never an Elektron byte in the
    repo... `.incbin` from the user's stock image at build time is the pattern") — **directly confirms**
    the community consensus/legal necessity behind that rule; not a "may relate," this is the same
    concern playing out in public with a real correction after an initial mistake.

## Firsthand hardware-testing claims vs. speculation/rumor

Firsthand (person reports testing on their own hardware):
- bukkakeborealis: continuous self-testing throughout, on Ableton control? no — real external synths:
  0-Coast, DFAM (via MFB/mafd MIDI-to-CV), Analog Rytm-adjacent workflows, and general OT hardware;
  numerous demo videos referenced (attachment links only, e.g. `IMG_0942.mov`, `IMG_0972.mov`,
  `IMG_0973.mov`, `IMG_0974.mov`, `IMG_0979.mov` — not retrievable as text, note their existence only).
- devilfish707: flashed to a second OT, tested with a Korg mono/poly and a "multi/Poly" synth; reported
  the CC-stepping bug and the CC48-crosstalk workaround discussion firsthand (10, 12, 18 Sep).
- drrumble: "I tried it last night, it work seamlessly" (10 Sep) — firsthand but low detail.
- bryant12345: "Tried it out with my moog. Controlled three parameters with totally predictable behavior."
  (12 Sep) — firsthand, positive, low detail.
- mayrakissa: tested OT1 MIDI out -> Analog Rytm MK1 MIDI in, reported lag; explicitly caveated as "very
  old version" and possibly resolved in newer builds already (11 Sep) — firsthand but self-flagged as
  possibly stale/non-representative.
- pituzinho9269: most detailed bug-hunting firsthand testimony in the channel (12–19 Sep): machine
  selection bug, FUNC+REC2 crash, track 5-8 STATIC/FLEX audio bug, lost MIDI pattern data after a crash.
  All stated as directly observed on their own unit.

Speculation / secondhand / unverified:
- _anfim, 11 Sep: "I think the lag might be on the AR side, it's known to freak out when you hit it with
  too many ccs" — explicitly framed as a guess ("I think"), not a tested claim, offered to explain
  mayrakissa's reported lag.
- devilfish707, 12 Sep: "when assigning filter cutoff... moving the scene crossfader is quite steppy
  sounding while wiggling the cc knob is completely smooth. Is this unavoidable behaviour?" — a firsthand
  *observation* but with an open causal question; the author's causal explanation ("mix behaviour" change)
  is itself tentative ("That might be it").
- zackyoti_98392, 06 Sep: asked (didn't claim) whether internal parameter scene locks and MIDI scene locks
  share a bus that could compound congestion — an open technical question, never answered definitively in
  this channel.
- kjnilsson, 09 Sep: asked whether parts needed to be extended for the new storage — question, not
  answered directly in the visible thread.

## Version/release timeline (as stated in-channel)

- 09 Sep: GitHub repo created — https://github.com/bkkbrls-del/midisc
- 10 Sep: patcher published — https://bkkbrls-del.github.io/midisc-patcher/ (initial build described as
  "yesterday's tested version")
- 11 Sep: **1.40MIDISC5** — save/reload fix, CC leak fix, no CC filter yet. Warning issued: projects saved
  under the prior (buggy) build could brick on reload; use a new project.
  - Caution: users saving under "MIDISC5"/"MIDISN5" and reloading under later builds also hit issues
    (13 Sep, devilfish707) — consistent with the project's own documented trap about stored data
    surviving a slot/layout change (**may relate to existing project trap docs** — flagged for cross-
    check, not a confirmed match).
- 13 Sep: **1.40MIDISCN8** — fixed part reload, fixed part-change latency, added CC 48/55/56 filters in
  MIDI control menu (not yet persisted across reboot/project save).
- 14 Sep: CC filtering removed again due to bugs; author settles on the last (no-filter) build.
- 17 Sep: clarified as **1.40MIDISC8.1** (no CC filters) vs. an earlier "1.40MIDISC8" that a user observed
  on GitHub still appearing to have filtering — naming/versioning was a bit muddled in the channel itself.
- 19 Sep (last entries in export): a "known good version" re-pushed to GitHub/patcher after the author
  suspected some in-progress (AI-assisted, "Cursor") edits had been inadvertently included; confirmed still
  labeled 8.1. A machine-selection fix reported working after this re-push.

## Tooling note

- The author mentions using AI coding assistance directly: "I used Cursor to provide the GitHub so I hope
  it checks out" (09 Sep, re: initial repo/README quality) and later suspects unintended changes were
  "pushed by cursor at some point" requiring a revert to a known-good version (19 Sep). devilfish707 also
  mentions using Claude to help resolve build errors (10 Sep) and get "inflator" working (11 Sep, unclear
  what "inflator" refers to — possibly an unrelated personal project, not explained further in-channel).
