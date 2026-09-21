# Discord findings — index

Eight channel exports from the "Octahackers" Discord server (28 Aug – 19 Sep
2026) were mined for anything implementation-relevant to this project. Each
channel has its own findings file (below); this index cross-checks the
standout items against the tree as it exists now and says which are already
settled and which are still live leads.

**Methodology note on confidence:** the per-channel files were written by
agents reading Discord chat in isolation — they flag anything that *might*
relate to a documented trap without confirming it. This index closes a
sample of those flags against the actual current docs/git history. Where a
flag is marked "confirmed" below, someone read both sides. Everything else
in the per-channel files is unverified against the current tree and should
be treated as a lead, not a fact.

## Who's who

| Discord handle | Identity / role |
|---|---|
| bamshanks | sambanks — author of upstream `octabam`, this project's fork source |
| bryant12345 | Bryan T — contributor named repeatedly in this project's own CLAUDE.md traps (LOFI2 payload bug, `modules/hello/` abbr overflow, recorder click math) |
| emuyia | author of Octakit (256 kits/project mod) |
| bukkakeborealis | author of the MIDI scenes mod |
| mischa85 | author of `elektron-firmware-tool` (.syx container inspector) |
| plentynights | independent RE contributor; likely source of the untracked `docs/TIMESTRETCH_PIPELINE.md` in this working tree |
| rbl0k_28323 | community tester, reports build breakage and cross-module bugs |
| devilfish707 | porting JSFX effects (RC Inflator, Tapehead, Phoenix) into FX2 slots |

## Already settled — confirmed against the current tree

These were flagged by the mining agents as "may relate to an existing trap."
Checked directly; all confirmed already resolved/documented, so no action
needed beyond awareness of the backstory:

- **Recorder loop-click "whale hunt"** (dream-features, octabam channels) —
  the Discord threads (28 Aug – 13 Sep) capture the *early* diagnosis
  (Bryan T's rounding-drift math, bamshanks's first ColdFire cave). The
  project's own history goes much further: `docs/firmware/RECORDER_CLICK.md`
  is a "facts-only," hardware-measured writeup (three caves, `recfix`
  remix, OCTABAM84 hardware-verified), with the full derivation in
  `docs/history/RTOS_FORK.md` §10.16–10.58. **The Discord "still clicks on
  playback, 7/8 repetitions" report and Bryan's undelivered
  `note-for-bam-recfix-click.md` match RECORDER_CLICK.md's own "Not proven"
  §4 item** — "a sporadic blip... at no repeating bar position... untested"
  — so that loose end is already named in the current doc, not lost.
- **dsp56300 unpinned-clone build breakage** (general-elektron-discussion
  part 2) — `scripts/setup.sh` already pins `dsp56300` to commit
  `c051afad31612c2d2c7a81a7ab23e1c5ac9e61af` and pins `mc68k`/
  `elektron-firmware-tool` too. Fixed since the Discord report.
- **Unicorn CFV4E missing `bitrev`/`byterev`/`ff1`** (open-technical-questions)
  — already found and emulated in this project's own port
  (`tools/emu/ot_emu/v4e.cpp`, `tools/emu/emu_bringup.py`), with a retraction
  of an earlier wrong note about which opcodes are absent. Not a gap.
- **Reverb cycle-pricer reads low** (octabam channel: "~270 cycles low...
  a cliff") — already measured and tabulated in `docs/firmware/CHIP.md`
  ("the R46 reverb's true cost... `cycle_count.py` prices it 1,384, so the
  pricer reads ~270 low on the reverb, ~264 high on the delay").
- **LOFI2 payload-A/payload-B stock-table address bug** (general-elektron
  part 3, dream-features) — the Discord account from bryant12345 (13 Sep) is
  almost certainly the firsthand source for the trap CLAUDE.md documents;
  it's already fully written up in `docs/firmware/EXTERNAL.md` §10.
- **`docs/TIMESTRETCH_PIPELINE.md` being an unverified LLM-derived writeup**
  (flagged from general-elektron part 3) — already self-retracted at the top
  of the file (dated 18 Sep 2026: every address is 0x400 low, superseded by
  `docs/firmware/REPITCH.md`). No action needed; it's honestly labeled.
- **"The wedge" failure name** (octabam channel) — already the exact section
  title in `docs/remixer/FAILURE_MODES.md`.

## Still open — worth a look

- **BusVerb-only-wedge, cause open** (octabam channel, `.reliktfarn`'s
  report) — `docs/remixer/FAILURE_MODES.md` ("The audio engine wedges with
  only BusVerb + the return 🔴 cause open") documents this exact failure on
  a *dedicated soak-test project* with cause still unknown. The Discord
  report adds a detail not in that doc: `.reliktfarn` says it wedges on
  their project but bamshanks confirms it's stable **only on a clean,
  fully-dedicated project** ("steals all the resources") — i.e. it may
  reproduce specifically under resource contention from other tracks/effects
  rather than being a pure BusVerb+return interaction. Worth feeding into
  the next soak-test round as a variable to isolate.
- **Crackle bug (Spectrum at high resonance, tape-echo on time/feedback
  changes), hardware-only, not reproducible on `dsp_host`** (octabam
  channel, 18 Sep) — `docs/remixer/FAILURE_MODES.md` gained 68 new lines in
  the currently uncommitted working tree (`git status` shows it modified),
  and `modules/tapeecho/` and `modules/vintageverb/` are both mid-edit right
  now, so this looks like exactly the bug already being worked on in this
  session's own pending changes — cross-check the MK1-reproduces/MK2-does-not
  split reported in Discord against whatever's landing in the working tree.
- **FX2 id exhaustion hit by a third-party porter** (octabam channel,
  devilfish707 porting RC Inflator / Tapehead / Phoenix, had to steal
  Spatializer's id) — not this project's own bug, but live evidence of how
  tight the FX2 id space is for anyone stacking modules; relevant context if
  a future remix wants to bundle more community effects.
- **Cross-core send dropout, BongDelay→ChonVerb** (general-elektron part 1,
  rbl0k_28323) — reported against someone's fork with renamed bus effects,
  unresolved in the thread. Possibly the same family as this project's own
  auto-gain-registration trap, but on different code — not confirmed.

## Repository follow-through (19 Sep 2026)

This review produced three deliberately small changes; none claims to fix a
hardware bug from chat testimony alone:

- `docs/remixer/FAILURE_MODES.md` now makes clean/dedicated versus
  resource-loaded projects an explicit BusVerb soak variable, and keeps the
  reported sequencer stall distinct from the measured transport-alive audio
  dropout.
- `modules/octakit/README.md` now records the unmeasured Kit/MIDI-SCENES write
  protocol and the reported REC SETUP stale-live-state failure as integration
  checks with a concrete regression matrix.
- `tools/emu/ot_emu/machine.h` no longer describes
  `bitrev`/`byterev`/`ff1` and fractional EMAC as current port gaps; `v4e.cpp`
  already implements them.

The remaining useful work needs evidence the export cannot supply: a long
hardware soak with both project shapes, isolated MKI/MKII crackle recipes, and
a watch of saved Kit bytes versus live recorder state during a Part change.

## Ecosystem awareness — third-party mods that may matter for compatibility

Independently developed mods that touch the same firmware surface as this
project's modules (relevant if a future remix wants to bundle or must avoid
colliding with one):

- **Octakit** (emuyia, github.com/emuyia/ems-octakit) — 256 kits/project,
  ColdFire-side only (sequencer/part/kit/pattern/scene), ~3.1MB of the Flex
  sample pool. bamshanks is already building a combined "OK-MS" remix
  (Octakit + midi-scenes) with a conflict-avoidance layer conceptually like
  this project's module-claim system. A real PR (#280) had to fix Octakit's
  FX2 chooser table falling out of sync with octabam's relocated one —
  concrete precedent for how two independently-developed mods collide.
- **MIDI scenes** (bukkakeborealis, github.com/bkkbrls-del/midisc) —
  scene-crossfadable MIDI CC/note locks, pure data-model/UI work, no DSP.
  Notably: the author accidentally shared a compiled modified firmware
  binary once, caught it, and switched to build-instructions + a
  browser patcher over the user's own dumped stock OS — a real-world
  precedent for exactly this project's "never an Elektron byte" rule.
- **DUALBUS** (mrscruff2277) — a new custom machine (replaces PICKUP) for
  A/B bus crossfading; code currently private. Would occupy a machine slot
  if ever integrated — check against slot/id-sharing rules first.
- **Reverb ecosystem**: multiple independent Clouds/Dattorro-style reverbs
  exist in the community — kjnilsson's "Cirrus" (measured to fit exactly in
  Plate's 594-word budget) and planned "Cirrusxl", bukkakeborealis's
  "CLAUDS", noeisgirl's "lex verb" (Dattorro, 354 hardware-flashed
  iterations) — distinct from, but conceptually parallel to, this project's
  own "Nimbus" grain-window reverb already documented in CLAUDE.md.
- **octa-bt-pt** (Bryan T, github.com/bryantysinger/octa-bt-pt) —
  parameter-default patch tool for OS 1.40C, same contributor as several
  entries in this project's own trap list.

## Reference tools worth knowing about

- **elektron-firmware-tool** (mischa85, github.com/mischa85/elektron-firmware-tool)
  — unofficial `.syx` container inspector covering ELE3/ELE2/ELEK/AD/Pre-ELE
  formats. Already a pinned build dependency in `scripts/setup.sh`.
- **Octamax** (maxolydian, github.com/mxldyn/octamax) — educational RE
  toolkit targeting the same OS 1.40C / ColdFire+DSP56xxx platform; has its
  own documented "DDR tail overwrite" bug noted in Discord as tying to this
  project's delay-ring/Unicorn bug family (unconfirmed link, worth a look if
  ever cross-referencing RE notes).
- **octalab-notes** (BuMa, github.com/nordseele/octalab-notes) — independent
  MKI-focused 1.40C reverse-engineering notes; useful as an MKI cross-check
  since this project's own measurements are mostly MKII.

## Independently corroborated numbers

Measurements from the community that line up with (and in some cases predate)
this project's own documented figures — useful as independent confirmation,
not new information:

- Octatrack DSP chip = **DSP56721** (bamshanks, photo evidence).
- DSP cycle budget ≈ **3120 cycles/core** (bamshanks, 17 Sep — matches this
  project's own `CHIP.md` figure).
- Control frame is **16 samples / 2756.25 Hz**, not 64 — a fully worked,
  address-cited resolution in open-technical-questions (`0x4000ad46`,
  `0x4000aef2`, `0x4000aad0`, plus function addresses), reconciling an older
  "64 samples" claim as a *different*, real recorder-length floor (4×16).
  Worth checking this matches whatever this project's own docs say about
  frame size, since it was derived independently.
- Per-effect code-size table (bryant12345, 11 Sep, measured): DARK REV 1067,
  SPRING REV 1063, FILTER 727, PLATE REV 594, LO-FI 537, DJ EQ 345,
  CHORUS 329, FLANGER 289, EQUALIZER 282, COMB 277, SPATIALIZER 261,
  PHASER 207, COMPRESSOR 180 words.

## Per-channel files

| File | Channel | Notes |
|---|---|---|
| [octabam.md](octabam.md) | #octabam | Densest file — direct dev discussion, two unresolved hardware bugs, build fragility, FX2 id exhaustion |
| [dream-features.md](dream-features.md) | #dream-features | Wishlist channel that turned out to contain the full recorder-click derivation |
| [open-technical-questions.md](open-technical-questions.md) | #open-technical-questions | Densest technical Q&A — control-frame timing, PR #52 delay/recorder math, dead NOISE effect |
| [midi-scenes.md](midi-scenes.md) | #midi-scenes | Third-party mod; licensing near-miss relevant to this project's distribution rule |
| [octakit.md](octakit.md) | #octakit | Third-party mod changelog; memory-cost data; compatibility fixes with octabam |
| [demos.md](demos.md) | #demos | Showcase channel; effect code-size table; reverb ecosystem survey |
| [the-mods.md](the-mods.md) | #the-mods | Curated reference catalog of tools/mods/creators |
| [general-elektron-discussion-part1.md](general-elektron-discussion-part1.md) | #general-elektron-discussion (lines 1–4500) | Chip IDs, payload budgets, FX2-aliasing trap corroborated |
| [general-elektron-discussion-part2.md](general-elektron-discussion-part2.md) | #general-elektron-discussion (lines 4300–8800) | Spare-RAM discovery/retraction, FAT/RAM card-size limits, toolchain provenance |
| [general-elektron-discussion-part3.md](general-elektron-discussion-part3.md) | #general-elektron-discussion (lines 8600–end) | LOFI2 bug firsthand source, USB-audio architecture, REC SETUP part-bleed bug |
