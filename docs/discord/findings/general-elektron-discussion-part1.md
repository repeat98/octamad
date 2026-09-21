# Octahackers #general-elektron-discussion — Part 1 (lines 1–4500, 28 Aug – 8 Sep 2026)

Scope note: this range is heavily "joined the server" noise, stickers, and social chat
(gear opinions, Melbourne meetups, Elektron-business-model debate, LLM-agent-safety
tangents). Only technically substantive items are extracted below.

## Chip identification / hardware family

- **bamshanks (28 Aug, ~09:00), firsthand/measured (posted a chip photo)**: identifies the
  Octatrack's DSP as **DSP56721** (image attachment, not machine-readable text but stated
  explicitly in chat). This is a different part than the Machinedrum's DSP.
- **robottosan_ (28 Aug), firsthand (from his own MD reverse-engineering work)**: Machinedrum
  hardware is **ColdFire 68k + two Motorola DSP56303s**. Says the firmware blobs are "packed
  with a variant of some well-known compression algo," which was the major hurdle to getting
  at the code, and speculates the Elektron Firmware Tool (mischa85's tool) can now handle that
  unpacking too (not confirmed firsthand here).
- bamshanks speculates the Octatrack and Machinedrum might share "the same dual Motorola on a
  chip" and that porting/sharing effects between them could be possible — **speculative**, not
  tested. Later (09.09 range) bamshanks notes a friend is "completely redoing the MD with 6x bus
  effects," and describes the MD architecture as differing from OT: "2x DSP instead of a dual
  core with shared mem," a different ColdFire-family variant, but "all similar family stuff" —
  speculative/inferred, not measured.
- **robottosan_ (05 Sep), firsthand claim**: Digitakt II / Digitone II are **still ColdFire +
  SHARC DSP based**, not ARM/Linux/Rust as some had assumed — claims this is verifiable "from
  teardown photos" and that the Elektron Firmware Tool can extract those images. Contrasts with
  **Tonverk**, which he describes as Elektron's "totally new Linux-based ARM SoC platform,"
  firmware delivered via SWUpdate and encrypted. Names the SoC as an NXP part:
  `MIMX8ML4DVNLZAB` (i.MX8M Plus, 4x Cortex-A53 + NPU) — this specific SoC identification is
  **speculative/inferred** ("I heard Tonverk was all Rust"; no direct teardown citation given
  in-channel).
- **robottosan_ (08 Sep)**: "Only Elektron device with protection measures is the Tonverk" —
  stated as fact, unclear how verified. Also claims EU law generally permits reverse engineering
  absent malicious intent, copyright infringement, or circumvention of protection measures
  (legal opinion, not a technical claim).
- videomusik (07 Sep, unclear how firsthand): "DTII is two Coldfire MCUs. The DNII I think has
  at least one FPGA" — the DNII/FPGA part is hedged ("I think"), treat as speculative.

## DSP payload space budgets (may relate to existing project trap docs — cross-check)

- **bryant12345 (28 Aug 16:24), self-flagged as uncertain**: "I think each payload of the DSP
  firmware has 8192 words max. The payload with the least available words is A. I think that has
  494 words free [at the time]. Effects seem to range from roughly 300 to 1000 words." He later
  explicitly retracts confidence: "I might be completely wrong on some of these numbers. I've
  verified a handful, but don't know that 8192 with certainty" (28 Aug 16:53).
- **bamshanks (28 Aug 16:54), firsthand/measured**: confirms the ~8192-word figure via a "burn
  test tool where I turn the knob until it starts squealing" — an empirical overrun probe,
  landing "around that number." Caveats: "they have lots of little bits and pieces all over the
  place so you can never be sure" — i.e. the true usable budget per payload is fuzzy even with
  this probe. **This directly overlaps the project's own per-core FX2 buffer / payload-size
  constraints (CLAUDE.md's payload asymmetry and cycle-budget warnings) — cross-check against
  current measured word budgets for payload A/B before relying on the 8192/494 numbers.**
- **bamshanks (01 Sep), technique**: describes a **dispatch-consolidation trick** for saving
  space: "if I take three effects I point all their pointers to the same effect" — i.e. multiple
  FX2 slot ids can share one code body by aliasing their dispatch-table pointers to the same
  implementation. This is the same mechanism the project's CLAUDE.md documents as "AN FX2 ID IS
  ALSO AN FX1 ID" / shared dispatch tables — **cross-check**: this consolidation approach is
  exactly the kind of aliasing that trap warns can silently take stock effects away from FX1 too
  if not tracked carefully.
- **bamshanks (03 Sep 12:55), firsthand**: freeing DSP space requires **contiguous** free
  regions, not just cumulative freed words: "if you want to free up blocks you have to free up
  contiguous free space… sacrificing just chorus and compressor wouldn't free up a single
  contiguous slot." Confirms stock FX ordering is effectively fixed unless you're willing to do
  more invasive rework ("yeah quite possibly… but isn't my personal focus").
- **rbl0k_28323 / GPT-assisted bug report (03 Sep 14:28–14:44), firsthand build failure**: PR #58
  workbench/"remixer" tooling bug — the Workbench planner reported a remix as "boots" with a
  dynamically-computed donor budget (~3619 words), but the saved remix's actual harvested donor
  region was still the fixed legacy reverb donor size (`stock.region_words(...) == 2724`,
  harvesting only PLATE REV/SPRING REV/DARK REV). `make bus` then correctly failed with
  `payload A: WARPFOLD overruns the region (2972 > 2724 words)`. Diagnosed as "Workbench
  placement/budget state can become stale or diverge from the saved chooser-derived harvest
  state." This is a specific, dated (b341b4d) reproducible build-tooling bug in early
  workbench/remixer code — **may be long since fixed in current octamad remixer, but the
  stale-donor-budget failure mode is worth checking against current `stock.region_words()`
  logic if similar symptoms reappear.**

## Build/tooling bugs found and fixed

- **rbl0k_28323 (01 Sep 23:00–23:05), via Claude analysis, fixed same day**: two bugs in
  `scripts/analyze.sh` (octabam repo), merged as PR #51:
  1. Missing `|| true` after
     `strings -n 6 "$f" | sort -u | head -40 | tee "$OUT/${base}.strings.txt" >/dev/null` — under
     `pipefail`, `head` closing the pipe early causes `sort` to receive SIGPIPE (exit 141),
     aborting the whole pipeline — **this masked bug 2**.
  2. The `elektron-firmware-tool` invocation in the script only *generates a report*; it does not
     perform the actual extraction to `out/raw/`. It needed a second call with `-d 3 -o out/raw`
     for `make recon` to actually deliver what its own comment promised.
  This is upstream octabam tooling, not necessarily current octamad state, but the pipefail/SIGPIPE
  masking pattern is a generally reusable diagnostic lesson.
- **devilfish707 (04 Sep)**: `make recon` fails on macOS because `mapfile` (a bash builtin) is not
  supported under Bash 3.2, which ships on macOS through at least macOS 15 — a portability gap for
  anyone running the toolchain on stock macOS bash rather than a Homebrew-updated one. No fix
  landed in this range; bamshanks acknowledged testing was done on "a pretty modern rig."
- Multiple users note Windows/WSL friction setting up the build (`make setup` requiring
  Homebrew, which doesn't exist on native Windows) — yvez_me and rbl0k_28323 both got the
  remix tooling working under WSL after "a few hiccups" (yvez_me attached a `WSL.md` writeup of
  steps/hurdles, not captured verbatim here).

## ColdFire-side machine/synth porting (bukkakeborealis)

- **bukkakeborealis (04–05 Sep), firsthand, via Cursor + Ghidra**: unlocked normally-inaccessible
  **machine slots 6/7/8** in the Octatrack's SRC/machine-select menu, and got a **pseudo "GND SIN"
  machine** (ported/adapted from Machinedrum code — "From MD" in response to bamshanks asking
  whether it came from MD or scratch) working as a single-oscillator synth with pitch adjustment,
  routed straight to the AMP page. Reports it "sounds super clean" in isolation but has trouble
  with **pitch assigned to chromatic mode** and with **hooking LFOs and scenes to it** — open
  issues, not resolved in this range.
- Speculates dual-oscillator machines with selectable shapes, and parameter locks for the SETUP
  page, would be desirable next steps for proper Machinedrum-style machines on the Octatrack —
  aspirational, not yet implemented.
- This effort is entirely **ColdFire-side** (bamshanks: "I assume that's all in the coldfire?" —
  bukkakeborealis confirms yes) and does not touch DSP.

## MIDI scenes implementation (bukkakeborealis)

- **Early prototype (28 Aug), firsthand**: "audio track FX sending midi CC internally (scenes) to
  control midi tracks parameters with crossfader" — described as "Fake midi scenes," achieved by
  routing an audio-track effect's CC output internally to drive MIDI track parameters via the
  crossfader.
- **Full implementation announced (05 Sep 23:03), firsthand, "pure madness"**: "Full midi scenes
  working. Every parameter of every page of midi tracks is lockable to the 16 scenes to A and B
  and morphs between them with Xfader. Same as audio per parts per bank. Reloadable.
  Copy/paste/clear. Everything." States some bugs remain, and plans to add MIDI filters for
  **CC48/CC55/CC56** in personal settings.
- **06 Sep 00:17, firsthand workaround**: "I usually disable the crossfader CC48 which causes a
  lot of trouble" — implies CC48 (crossfader) is a known troublemaker for external MIDI gear, and
  he uses a Midihub for filtering/testing. Notes he needs to "try without and see the real mess."
- **06 Sep 23:45, firsthand**: "Spent ages finding where to properly save the midi scenes into
  parts and persist reboot haha. Finally nailed it just now!" — confirms MIDI-scene state is
  stored inside **part data** (consistent with the project's own documented trap about part slot
  layouts and stored-data compatibility — **cross-check**: any future work reading/writing part
  data for MIDI scenes should be aware of the project's "a part saved under an older slot layout
  feeds the new layout its old bytes" trap class). No GitHub was public as of this range.
- No public repo yet as of 05–06 Sep; bukkakeborealis says he'll set one up "as soon as possible."

## Recording buffer / flex playback behavior (unresolved, firsthand-adjacent)

- **michaelknubben (04 Sep 21:56–23:00), firsthand but "from memory, it's been a while"**:
  describes overwriting a buffer that's being read concurrently by other tracks as *not*
  handled gracefully. Setup: multiple tracks playing back the same buffer; recording into that
  buffer while a track's playback head is reading ahead of (past) the record head. Claims the
  playback "just stops" — possibly upon encountering unwritten/NaN-like data — and recalls "maybe
  there was even an audible glitch." Explicitly uncertain about the precise mechanism ("I think
  there's quite a few situations where it just stops the voice's playback if it encounters
  something it can't handle, like presumably: a chunk being written as it tries to read?").
  **This is a candidate area of overlap with the project's own recorder/EMAC traps documented in
  CLAUDE.md (the recorder length converter and block-walk-stall symptoms tied to the ColdFire
  EMAC fractional-multiply bug) — cross-check whether this "buffer overwrite while reading"
  symptom is actually a manifestation of the same underlying EMAC sign bug, or a genuinely
  separate buffer-race issue.**
- **bryant12345 (04 Sep 16:34, 21:25, 05 Sep 01:47)**: names this general area ("fully understand
  the recording buffer and flex playback to remove clicks at the loop point for all BPM/RLEN
  combinations") as his "white whale" — a long-standing unsolved problem, worked on over that
  weekend, no conclusive resolution reported in this range.
- **rbl0k_28323 (03 Sep 21:36), firsthand hardware report, unresolved**: reports a delay/reverb
  cross-core send bug: layout was Send on T1, BongDelay on T4, ChonVerb on T5. Everything worked
  initially including the delay's send into the reverb; then, without changing parameters, after
  turning knobs C and F (tone & pitch) a few times, "no delay, no send to verb" while other
  parameters continued to show changes. bamshanks's response: "sounds like it could be the buffer
  not flushing or something," deferred pending "the current (massive) re-arch." **Flag as
  possibly related to the project's documented "persistent slot that init does not clear" /
  stale-state trap family, or to the auto-gain "registers but contributes nothing" trap
  (CLAUDE.md) — cross-check once the current codebase's tone/pitch knob handling for
  BongDelay/ChonVerb-equivalent modules is examined.**

## Feature designs discussed in-channel (not all implemented as of this range)

- **zackyoti_98392 (Kyoti firmware), firsthand build/emulation-tested, not yet hardware-tested at
  time of posting (03 Sep 21:53)**: new mute-mode system with 4 selectable options — (1) OT
  original cut, (2) OT original cut + FX tails, (3) OT original cut + FX tails in a trig-mute
  style, (4) DT trig-mute style (FX tails + sample follows its amp envelope after muting). Mutes
  triggered by soloing respect whichever mode is selected. Also in progress: **sidechain
  compression** (any track selectable as the key/trigger track, a bipolar filter applied before
  the key track's signal hits the target, and it works even when the key track itself is muted),
  a **Direct Jump** feature modeled on the Analog Rytm, and a QoL feature to delete fully-unlocked
  trigless locks from the grid after erase (to reduce visual clutter). Notes his sidechain
  implementation **cost him one stock effect slot (Spatializer)** to build. Also separately floats
  (08 Sep) putting **Direct Jump on Pattern+Yes** and surfacing **recording quantize** to the
  hardware panel instead of a menu — feature proposals, not confirmed built.
- **bamshanks, firsthand (in-progress)**: also building a **sidechain** implementation, but one
  that "gives up all stock effects" as part of a much larger DSP rearchitecture ("Things have
  gone… to the extreme"). Describes redesigning the whole effects section around rack-style
  multi-effect **"stations"** — filter station, mod station, character station — designed to
  "behave more like algos from eventide than single effects," explicitly to compensate for the
  Octatrack's limited internal routing. Confirms (03 Sep) he **replaced the delay's internal
  grain engine with a ported Mutable Instruments Clouds ("Nimbus") engine**, which he found
  sounds better than his own — consistent with the project's own Nimbus module lineage.
  ChonVerb and BongDelay are both confirmed **bus-only effects that occupy the entire FX2 space**
  (bamshanks, 02 Sep) — "big and take the whole of fx2 over" — and mixing bus + insert effects in
  the same slot picker in the (then-current) workbench UI was "impossible." He planned splitting
  Nimbus into a lighter insert version plus a separate bus version because "Nimbus is huge as
  well."

## Emulation/tooling architecture notes (bamshanks, firsthand, in-progress across this whole range)

- Harness architecture as described: "python wrapping c++ wrapping the emus," with MIDI used to
  drive the real/emulated device and a soundcard capturing audio feedback for iteration loops (28
  Aug). Confirmed later that the "ears" (audio comparison) are "as prone to hallucination as
  everything else" — i.e. bamshanks flags his own automated audio-similarity judging as
  unreliable, self-aware caveat.
- Doc: `docs/HARNESS.md` in `sambanks/octabam` was published 28 Aug explaining the harness.
- By 06–07 Sep: got a **ColdFire emulator working locally** and was "wiring in the DSP now" to
  build "a much more comprehensive local testing harness" to cut down on hardware round-trips.
  Separately mapped out "a lot of the cf stuff" (ColdFire) over the preceding weekend.
- 07 Sep: mentions working towards **an RTOS emulation** ("having an emulation of the rtos will
  quickly pay off"), and a side quest to **map out and emulate the CompactFlash card** so that
  work relying on part/project data on the CF card can be done off-device — "still a way to go."
- 05 Sep: "nearly got midi for effects page 2 stuff going in" — wiring MIDI control of FX page-2
  parameters into the harness, explicitly needed for automated "voicing rounds" (i.e. the harness
  can drive/test parameter changes and get the DSP ~70% voiced before human ear-tests) — this
  matches the project's own emphasis on the harness/`send_probe`/`dsp_host` architecture, though
  described at a much earlier/rougher stage than current octamad tooling.
- 05 Sep 00:05: bamshanks reports his "first exception / soft brick" during this dev period — no
  cause given, no further detail in this range.
- bukkakeborealis (30 Aug), firsthand: confirms flashing experimental firmware can brick the unit,
  but the OS-upgrade-at-boot menu (hold FUNC while powering on) reliably allows recovery via a
  sysex firmware flash over MIDI — "bricked it a few times already but always managed to access
  the [upgrade] menu." Reverting to stock 1.40C fully recovers the unit, but the **current project
  file can become corrupted** (he hit a "stuck sequencer" and had to create a new project) —
  firsthand, hardware-tested.

## Relevant repo/tool links mentioned

- `sambanks/octabam` — https://github.com/sambanks/octabam (main project repo referenced
  throughout)
- `docs/HARNESS.md` — https://github.com/sambanks/octabam/blob/main/docs/HARNESS.md
- PR fixing analyze.sh — https://github.com/sambanks/octabam/pull/51
- `bryantysinger/octa-bt-pt` (Bryan T's own repo) — patch tool for adjusting default parameter
  values on new-project creation: https://github.com/bryantysinger/octa-bt-pt/blob/main/patch_tool/
- `yatli/ghidra_dsp56k` — DSP56k disassembler module for Ghidra, used by robottosan_ for
  Machinedrum RE: https://github.com/yatli/ghidra_dsp56k
- `joelanders/gearmulator-md-mm` — alpha Machinedrum/Monomachine emulator (Gearmulator fork),
  VST3/standalone, requires user-supplied Elektron firmware/user data (not bundled):
  https://github.com/joelanders/gearmulator-md-mm/releases/tag/mdmm-v0.1.0-alpha.6
- octakit (em/emuyia's mod: 256 freely-assignable kits replacing per-bank parts) —
  https://www.junes.website/goodies/octakit — as of 07 Sep, confirmed by emuyia to actually offer
  **256 kits**, not 128 as some assumed.
- Original lineage note (zackyoti_98392, 07 Sep, firsthand-relayed): the mod tree traces back to
  **Maxolydian's Octamax**, built using **mischa85's Elektron Firmware Tool**; octabam and others
  forked from Octamax.

## Not substantive (skipped)

Large stretches of member joins, stickers/reactions, gear-preference debates (Rytm vs newer
Elektron boxes, Tonverk form factor complaints), off-topic AI-safety podcast discussion, and
general community-building chat (channel structure suggestions, tester roles, pizza-party jokes)
were skipped as instructed.
