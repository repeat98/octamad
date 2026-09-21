# Octakit — Discord findings

Source: `docs/discord/Octahackers - OCTATRACK - octakit [1544137111605612684].txt` (90 messages,
01–17 Sep 2026, #octakit channel). Author of the mod is **emuyia**. Frequent commenters:
**bamshanks** (octabam maintainer), **bukkakeborealis**, **_bradf**, **homeboiflex**, **w_winter**,
**machinista__21901**, **reubenfinger**, **noeisgirl**.

- Patcher: https://www.junes.website/goodies/octakit
- Repo: https://github.com/emuyia/ems-octakit
- Bug tracker: https://github.com/emuyia/ems-octakit/issues/new?template=bug_report.md
- GitHub description (verbatim, from an embed): "Custom firmware mod for the Elektron Octatrack.
  Replaces 4 Parts per Bank with 256 Kits per Project."
- Source code was made public 05.09.2026 (emuyia posted a link to the source alongside that day's
  build).

## What Octakit does (mechanism)

- Replaces the 4-Parts-per-Bank model with **256 Kits per Project**. A single Kit is stated to be
  functionally equal to a Part: "A single Kit is equal to a Part, with all that a Part contained"
  (emuyia, 06.09.2026). This includes **each Kit having its own full set of 16 Scenes** — Scenes
  are per-Kit, not shared across a "grouping" of kits (confirmed explicitly, not the parts-share-16-
  scenes model people expected).
- Old-project migration: Bank A's parts become Kits 1–4, Bank B → 5–8, Bank C → 9–12, and so on
  (i.e., 4 kits allocated per legacy bank, in bank order). Each Pattern is then auto-assigned the
  Kit slot that its old Part was migrated into (emuyia, 01.09.2026).
- Active kit state is distinct from a *saved* kit slot. Clearing a kit slot only clears the saved
  data — the currently-playing (active) kit keeps playing until explicitly changed. This was
  initially "by design" per emuyia, but loading an *empty* kit slot not clearing the active kit
  state was identified as a genuine bug (see changelog `ot-26914-152100-dev`).
- Kit naming: 7 characters max, no dedicated "rename" command — you rename a kit by re-saving it
  under a new name. 7 chars was chosen so the name plus a 3-digit kit number fits the main screen
  (e.g. `001 ABCDEFG`); emuyia said 8+ characters "didn't look right" (emuyia, 17.09.2026).
- New workflow shortcuts added over the course of the thread:
  - `FUNC+PART+YES` — quick kit save (skips the name-input dialog).
  - `FUNC+PASTE+PART` (when pasting a pattern) — pastes kit state into the next available kit slot
    and loads it.
  - `UNDO KIT` option added to the `LOAD KIT` menu (mirrors MnM/MD behavior).
  - `PTN+FUNC+RIGHT` (added `ot-26913-223407-dev`) — a 4-step combo: (1) save current kit, (2) copy
    kit to next available slot, (3) copy pattern to next adjacent slot with the new kit, (4)
    load/queue that pattern. Described by bamshanks as "unreal."
  - `PTN+FUNC+TRIG` + copy/paste/clear/undo — manage *inactive* patterns without loading them,
    including across banks (hold `BANK`, tap `TRIG` to pick the bank, then with `BANK` still held,
    `FUNC+TRIG` + copy/paste/clear/undo operates on patterns in that bank).

## Version / changelog history (verbatim build tags)

- **`ot-26901-014903-dev`** (01.09.2026):
  - fix crash when copy/pasting or clearing Scenes
  - fix crash when previewing a sample
  - add quick kit save (`FUNC+PART+YES`)
  - add paste-pattern extension that also pastes kit state to next slot and loads it
    (`FUNC+PASTE+PART`)
  - add `UNDO KIT` option to `LOAD KIT` menu
  - fix patterns still being assigned kits after they are cleared
  - fix empty patterns being assigned kits after old-project migration

- **`ot-26905-141307-dev`** (05.09.2026):
  - fix last step of pattern not sounding during pattern transition
  - fix crash while changing track scale ("maybe?" — emuyia could not reliably reproduce the
    original scale-change crash, so this fix is **unconfirmed by the reporter** at time of posting)
  - source code published same day

- **`ot-26912-163229-dev`** (12.09.2026), diff:
  https://github.com/emuyia/ems-octakit/compare/ec70ddad6957af375d8cab02d76a2bc46aba748a...8ded51760dde63de67c2f59e759bea0b323a7998
  - fix crash switching between chained Patterns with different Kits while editing FX1
  - fix crash from pressing `STOP` during rapid Pattern/Kit changes
  - "possible indirect fixes to other crashes" (speculative, not individually confirmed)
  - fix MKI `FUNC+REC` then `BANK` shortcut opening Pattern Settings instead of Recording Edit when
    `FUNC` remained held
  - fix `LOAD KIT` not assigning the selected Kit to the current Pattern
  - **added build, model, D0 register, SP and more specific fault addresses to exception/crash
    screens** — explicitly to make crash reports easier to diagnose remotely (relevant if octabam
    ever wants richer crash telemetry from user reports)
  - added MIT license

- **`ot-26913-223407-dev`** (14.09.2026), diff:
  https://github.com/emuyia/ems-octakit/compare/8ded51760dde63de67c2f59e759bea0b323a7998...fc904c853f9d2307f4ffdc663d24c6b627da3d3c
  - fix another crash switching between chained Patterns with different Kits
  - add `PTN+FUNC+RIGHT` combo (see above)
  - add `PTN+FUNC+TRIG` inactive-pattern management (see above)

- **`ot-26914-011006-dev`** (14.09.2026), diff:
  https://github.com/emuyia/ems-octakit/compare/fc904c853f9d2307f4ffdc663d24c6b627da3d3c...92cf70b3a51c99aebd9bb65f12919bbcb6ea2ce3
  - fix `PTN+FUNC+RIGHT` sometimes assigning the *source* pattern the new kit instead of keeping
    its original kit assignment

- **`ot-26914-152100-dev`** (14.09.2026), diff:
  https://github.com/emuyia/ems-octakit/compare/92cf70b3a51c99aebd9bb65f12919bbcb6ea2ce3...7ba0ad68127bbf3b3609dbb70174112cb4bc65ed
  - fix loading an empty kit slot not clearing active kit state

## Bugs and crashes reported (firsthand hardware testing)

- **bukkakeborealis, 01.09.2026 (firsthand, tested on hardware)**: pasting pattern+kit together
  "works really well," but found: (a) step 16 on a default 16-step pattern doesn't sound when
  switching pattern, and (b) it "bricks" (crashes) when changing track scale. Both targeted in the
  `ot-26905-141307-dev` build (the scale-crash fix was unconfirmed-reproducible by emuyia). Also
  requested pasting pattern+kit to the next slot **without stopping the sequencer**, stating "this
  is doable I tested it" — a firsthand claim about feasibility, not yet implemented.

- **_bradf, 08.09.2026 (firsthand)**: triggered an exception by changing kits within the same
  pattern too fast. Specifically reproduced by **re-selecting the kit that is already playing**
  (Kit 4 was active, selecting Kit 4 again) — causes brief per-track silence until the next active
  trig, and can escalate to a crash. Attached a crash screenshot (`IMG_1481.jpg`). In a follow-up
  the same day, also hit: a crash just from changing patterns that use different kits, and a crash
  when using "change sets" from the project menu. Notes this was on "mega long stem slices," 128-bar
  patterns — flagged by the reporter as possibly relevant context (large pattern lengths).

- **w_winter, 10.09.2026 (speculative, not tested)**: a hunch that a variant of Octakit capped at
  128–160 kits (instead of 256) would free up ColdFire-side headroom for DTII-inspired plock/
  sequencer features. No implementation or measurement backs this — pure speculation about a
  hypothetical fork.

- **bukkakeborealis, 14.09.2026 (firsthand)**: reported "kit clear is not instant" — clearing a kit
  slot doesn't stop the currently playing kit; it keeps going until changed. This is exactly the
  active-vs-saved-kit-state bug that emuyia then acknowledged and fixed same day (see
  `ot-26914-152100-dev`).

- **bukkakeborealis, 15.09.2026 (firsthand, but caveated)**: testing bamshanks's combined
  "OK-MS" remix (Octakit + a "midi scenes" mod), reported (a) a small delay on the first note after
  a pattern change, and (b) an audio tick at project load plus a quick LED blink on the "A rec
  setup" LED. Explicitly caveats this may have been because the test project was originally saved
  under an older/WIP firmware, not a reproducible bug in the current combo.

- **bukkakeborealis, 17.09.2026 (firsthand follow-up)**: after switching to always reloading
  projects fresh (or starting new projects), saw **no further issues** — suggesting the 15.09
  symptoms were likely stale project state rather than a code defect.

- **reubenfinger, 06.09.2026 (firsthand)**: successfully flashed Octakit via SysEx and successfully
  reverted back to stock firmware on an Octatrack MK2, confirming reversibility in practice.

## Memory layout / RAM

- 256 kits are stored by **repurposing ~3.1 MB (uncompressed) of RAM taken from the Flex sample
  pool** (emuyia confirms the figure "yeah it's 3.1 MB" on 10.09.2026, responding to
  machinista__21901's question; bamshanks had estimated "about 3MB" just before).
- Halving to 128 kits would only recover **~0.77 MB (~25% of the 3.1 MB)** — most of the 3.1 MB is
  fixed overhead (code and other buffers), not a purely linear per-kit-slot cost (emuyia,
  10.09.2026).
- Quoted impact figure (homeboiflex, 13.09.2026, quoting a source not otherwise linked in this
  channel): "Octakit currently shaves off 18.4s (16-bit) / 12.3s (24-bit) from the flex pool
  (3.6%)" — i.e., reduced Flex recording time.
- emuyia (13.09.2026) says he's investigating "alternate ways of recovering the RAM" that avoid
  removing features, and has "some leads."
- bamshanks (13.09.2026) notes the DSP side is not an option for reclaiming this space ("Can't go
  on DSP where the effects live") — RAM recovery leads are apparently ColdFire/filesystem-side, not
  DSP-side. He also remarks that "messing around with the fat fs is deep voodoo," in the context of
  RAM recovery — this reads as a caution about one class of approach (touching the FAT filesystem),
  not a confirmed statement of what emuyia's leads actually are.

## Project file format

- Legacy project migration mapping is explicit: Bank A → Kits 1–4, Bank B → Kits 5–8, Bank C →
  Kits 9–12, etc. (4 kits per legacy bank, in order).
- Two migration-related bugs were fixed in the first tracked build (`ot-26901-014903-dev`): empty
  patterns being wrongly assigned kits after migration, and patterns retaining a kit assignment
  after being cleared. Both are pattern↔kit bookkeeping issues tied to the new project data model.
- Kits fully subsume what a Part held, including a full independent set of 16 Scenes per kit (not
  shared).

## Compatibility with other mods — flagged for cross-check

**May relate to module compatibility — cross-check.** bamshanks is building a combined remix
called **"OK-MS"** (Octakit + a separate "midi scenes" mod) and describes needing to do manual
conflict resolution between the two:

- bamshanks, 14.09.2026: "just working on conflicting part reloads between octakit and midi
  scenes, so it's timely [re: emuyia's latest fix]. Think we are nearly there" — this names an
  explicit, concrete conflict ("conflicting part reloads") between Octakit and the midi-scenes mod
  at the ColdFire/part-kit-reload level.
- bamshanks, 15.09.2026, describing how the OK-MS remix is built: "I just do a thin wrap on the
  build which moves some bits round so you don't conflict with each other" — implies both mods
  claim overlapping resources (addresses/hooks) that must be manually relocated, conceptually
  parallel to octabam's module-conflict refusal (same FX2 id / hook site / cave / etc.), but this
  is a ColdFire mod pairing, not a DSP one, and no specific addresses or symbols are named in this
  channel.
- bamshanks states fixes for the observed OK-MS combo bugs (delay after pattern change, audio tick
  at load) will "quite likely be upstream" in emuyia's own Octakit code rather than being remix-
  specific, and that he personally won't invest much in bug-fixing the combined remix ("not a combo
  I'll be using").

No FX2 ids, DSP hook/detour sites, cave addresses, or DSP dispatch details are mentioned anywhere in
this channel. Octakit, as discussed here, is scoped entirely to ColdFire-side sequencer/part/kit/
pattern/scene logic (menus, project data model, pattern-kit assignment) — it does not appear (from
this channel) to touch the DSP payloads that octabam's server/insert module traps concern. The only
concrete "conflict" surfaced is the Octakit ↔ midi-scenes part-reload conflict noted above, which is
worth checking against octabam's module system if either mod (or the "OK-MS" remix logic) is ever
folded in or referenced.

## Hardware flashing / reversibility

- Procedure (emuyia, 06.09.2026): hold `FUNC` while powering on, select option 3 (test mode), then
  send the firmware `.syx` file over MIDI.
- bamshanks, 06.09.2026: "All of these firmware are reversible even if they crash. As long as you
  have a way of sending it midi." (general claim about this class of mod, not Octakit-specific.)
- reubenfinger, 06.09.2026 (firsthand): confirms uploading the Octakit sysex and successfully
  booting back to stock on an Octatrack MK2.

## Notable non-technical context

- emuyia signaled reduced availability for Octakit work through October (flagged 05.09 and again
  15.09.2026), inviting community PRs in the meantime; bamshanks noted he'd likely be similarly
  less available soon after.
- bamshanks, 06.09.2026, on the value proposition: "yeah this is going to buy me probably 8 more
  songs per project" (subjective/anecdotal, not a measurement).
