# Changelog

One entry per image that reached a unit, newest first; `Unreleased` is what
main carries beyond the last flashed image. The version the panel shows is
`BUILD` (`make image BUILD=N`); a git tag `OCTABAM<N>` marks the commit each
flashed image was built from.

## Unreleased (main after image 43; image 52 built)

- Nothing else is selectable on FX2 (image 52, 22 Sep 2026): BusVerb and
  BusDelay are hidden from the chooser (one row, SEND) and keep their
  twelve names on the host page (`named`). RIG HOSTS, a new ColdFire
  module: one detour in the part-defaults initialiser (0x40005688, the
  fourteen bytes that load a track's FX2 default from the stock DELAY
  descriptor's id) writes the id by track instead -- BusDelay on T1,
  BusVerb on T5, the stock DELAY on T8 the master (its beat repeat; Sam,
  22 Sep 2026), SEND elsewhere -- so a project made on the unit hosts
  the bus with no stamp (measured under the port: the ids of a project
  the firmware created read 6 9 9 9 7 9 9 8). `ot_project.py host
  <project>` does the same for an older project. `verify_hidden`'s other
  slot moved from 0x6400 (an FX1 slot since image 48) to 0x6500.

- The bus engines are locked to their host slots (`Remix.locked`, image
  51, 22 Sep 2026): BusDelay runs on T1 and BusVerb on T5, and either is
  an exact dry pass on any other track (the HOSTGUARD body hidden engines
  already took, at proc entry, `r7 == 0x6200`). The stock DELAY row is out
  of the FX2 chooser: every other FX2 is a SEND. `stamp-defaults` warns
  about an engine off its slot. Sam, 22 Sep 2026: a known working
  combination over a free one.
- Character: TXTR (Airwindows Pockey) removed after a high-pitched squeal
  on the unit when it was touched on the master, unreproduced on the
  harness at any value, with garbage RAM or on the GLUE position; WDTH
  takes its page-1 slot 2, page 2 is SAT alone. 304 words per payload
  freed; `pockey_ref.py` and the two codec tables gone.
- Images 44–50: 44 and 45 wedged, 46 washed, 47 and 50 were probes (47:
  the core-1 tracker one ahead on every block; 50: the dispatcher's call
  pattern matches stock's code on a fresh project, no marker). On a fresh
  project on 50 every tested configuration was clean; the THRU-host wash
  of images 40–49 reproduced only in OCTABAM91 and was not bisected
  further.

- The bus no longer needs the cores to agree on the flip's phase (image
  49, 22 Sep 2026): eight accumulator buffers (`Y:0x901..0x980`) and eight
  chain buffers (`Y:0x9d8..0xa57`), a server reads three back, the
  housekeeper clears two on, and a core-1 client counts its own blocks
  from a seed read at init, checked against the rotation once a block
  with a tolerance of one either way (`XBUS.md` "The accumulators",
  "Housekeeping and the rotation"). The per-core tracker, its position-0
  advance and the `T == R + 1` rule are gone. Bus latency 48 samples (32
  before); `verify-bus` reference re-saved for it; the two-core gate
  identical to the one-core control under every skew. BusVerb's SEND
  field moved `0x941` → `0x981`.
- SEND returns at proc entry on an FX1 slot (r7 0x6100/0x6400/0x6700/
  0x6a00, measured under the port; image 48): id 0 is SEND and FX1 NONE is
  id 0, so the client had been running on every FX1 slot with no effect —
  sending from an unseen page byte (audio in the bus with every SEND at 0,
  image 46) and, on core 1, comparing the tracker before position 0's
  advance, which left the core one step ahead whenever core 0's flip
  landed before the 0x6100 call (`XBUS.md` "An FX1 slot is not a client";
  `FAILURE_MODES.md`, the THRU-host wash). 21 words per payload.
- The tracker's self-check of images 44–46 (stamps, hold flag) removed
  (image 48).

Images 44–47 reached the unit and none is a release: 44 and 45 wedged on
the first play (a one-word displaced Y store the chip had never run, then
the self-check's unmasked read of an unseeded slot into a wild Y
address; `CLAUDE.md` for both traps); 46 played with static and the wash
on a T2 THRU host and bled into the bus with every SEND at 0; 47 (branch
`probe47`, a marker tone on a wiped stamp) sounded on every block of plain
play, the measurement behind image 48.

## Image 43 — 21 Sep 2026 (`OCTABAM43`, bamsep26 at b3f6471)

On the unit: the sample-host wash gone (T3 STATIC, a trig every step,
eight loops and a reload clean; the FX2 change on T1 clean). Still
washing: a THRU host past position 0 with a trig on every step
(`FAILURE_MODES.md`, open; not a rig configuration). Not yet heard: the
TIME ramp, the once-per-block glides, the names and `---` per mode,
Character's TONE on page 1, Modulation's five modes.

- The bus participants take a split block's frame offset from `r0` (0 on
  a first call, 2 x split on the a=1 call, as the dispatcher passes it)
  instead of a flag and a split the first call stashed in `$65/$66` for
  the second. Image 42 washed again after a reload and a loop, so PR
  #347's init-store bisect was one lucky run per image; the stash not
  surviving between the two calls on the unit is the reading that fits
  every fact (`FAILURE_MODES.md`). SEND, BusDelay, BusVerb alike; the
  `$65/$66` slots are free. Bit-identical in every gate (dsp_host passes
  the same `r0`); image 43 is the test.

## Image 42 — 21 Sep 2026 (`OCTABAM42`, bamsep26 at d3fceaf)

On the unit: the delay on a trig host clean (T2 THRU and T3 STATIC with a
trig on every step, two loops, OCTABAM91), the fixture that washed on
39, 40 and 41 (all three flashed 21 Sep 2026 without a section here; the
bisect is the first bullet). Not yet heard on the unit: everything else
below (the TIME ramp within the block, the once-per-block glides, the
names and `---` per mode, Character's TONE on page 1, Modulation's five
modes). The image's delay is d3fceaf's; the docs of that commit landed
after the build. Before play: `stamp-defaults <project> bamsep26 --all
--keep-mode` (done on the card for OCTABAM89 and OCTABAM91).

- BusDelay: nothing at `r7+$84` or above. On the unit (21 Sep 2026, images
  40 and 39 alike) the delay on T3 with a sample playing on every step
  printed a white-noise wash from the second pass of the pattern on -- T3's
  LEVEL kills it, FDBK does not touch it, WET scales it, STOP does not end
  it, PLAY does. The delay kept its WET glide state and four per-call words
  at `r7+$84..$88`, the range DSP.md has recorded since 10 Aug 2026 as not
  persisting across calls on hardware; every previous image had the delay
  on T1, a THRU, which plays no voice. The five words moved to raw `$0c $20
  $2a $6d $83` (`r7_latch_slot` 0x86 -> 0x20); bit-identical to image 40's
  engine (`verify_delay`, 28 cases, the reference's latch read at the
  manifest's slot: the manifest is shared, so a reference reading the old
  slot renders garbage and fails, which is what every latch move looked
  like until the marker-fill probe showed the engine writing exactly the
  slots it should). `tools/harness/slot_census.py` is that probe: fill the
  instance block, render, read back which words were written; it found
  GRAIN's pitch words at `$3e/$3f` (spelled `-$b`/`-$a`) under a first
  relocation that a displacement scan had called free. The port cannot see
  the mode (`FAILURE_MODES.md`). Cause inferred from the symptom and the
  record; image 41 is the test.

- BusDelay: the glides run once per block. A trig splits a block into two
  dispatcher calls (a=0 before the trig, a=1 after), and the TIME glide, its
  ramp base and the FDBK/TONE/PING/WET glides ran on both: the ramp
  restarted from last block's state at the trig, a jump of a quarter or
  three-quarters of the glide step (up to ~30 samples on a big TIME move)
  -- a click at every trig while the knob moved, which `dsp_host` cannot
  show (it never splits) and the port does. Gated on the frame offset
  (first call only); the a=1 call keeps the ramp's running value and its
  increment. With it: the 4-sample snap becomes a minimum step of 1/16
  sample per block toward the target, never past it (the last 4 samples
  take 23 ms at a slope of 1/256 instead of one block at 1/4), and the
  glide state is guarded against boot garbage (negative, or past the line:
  start at the target; only an exact 0 was). Bit-identical at rest
  (`verify_delay` against image 39's source, every case); `glide_census`
  0 / 73 / 896 as before; +33 words. Under the port, T1's chain output
  with the sequencer's trigs (`verify_set --midi-file`, spikes per 1,000
  samples > 0.02 FS, `port_click_census.py`): CLEAN
  (`tools/harness/midi/delay_time_clean.midi`, TIME 20 -> 90 -> 20) 22.8 /
  24.3 per window over each glide, max 145 / 164, on image 39's code ->
  1.1 / 3.0, max 7 / 13, the windows at the moves themselves 98 / 127 ->
  0 / 6; REVERSE (Sam's recipe) TIME windows 7.2 / 5.1 (max 51 / 31) ->
  4.1 / 3.0 (max 12 / 10), level with REVERSE's own splice floor. Found
  by the 21 Sep static audit; the census takes its marks from a recipe.

- BusDelay: the four init stores of PR #344 (zeroing the TONE/FDBK/PING/WET
  glide states) are gone: they were the white-noise wash on a host past
  dispatch position 0 with trigs on it, bisected on the unit (38 clean,
  39/40/41 wash, 42 = 41 minus the stores clean; `FAILURE_MODES.md`).
  Mechanism open. The rest of #344 (the audit, the `$85` port measurement,
  the doc corrections) stands.

- Names per mode (Sam, 20 Sep 2026: "size is confusing"): BusDelay's SIZE
  draws GLEN in GRAIN and SLEN in REVERSE; Spectrum's FREQ draws VOWL in
  VOWL (it morphs A E I O U); Modulation's TONE draws BRIT in COMB (the
  string's brightness). Character's TONE is back on page 1 in the return's
  slot 4 and WDTH moves up to page-2 slot 7 (page 1 DRV FOLD TXTR COMP
  TONE MIX, page 2 SAT WDTH); no other effect has an empty page-1 slot.
  Stamp before play: Character slot 4 (TONE 64 over the old RET byte) and
  slot 7 (WDTH 64); CC 38 is TONE, CC 69 WDTH.

- Every knob a mode never reads is named `---` in that mode (Sam, 20 Sep
  2026: "all per-mode knobs ... blank with --- titles, like the others,
  across all effects"), from each engine's reads: BusDelay CLEAN adds SIZE
  and PTCH, REVERSE adds PTCH and PING (the mode pins PING to 0);
  Modulation COMB names RATE, DPTH and WDTH (it has no LFO), PHSR names
  TONE (no line filter). Spectrum (every mode takes the modulated cutoff,
  RES and WDTH), BusVerb and Character have no inert knob. The MODE cave
  renames them, as SCAT/DENS since image 29; `verify_modenames` now checks
  a non-MODE select renames nothing (its own slot's name is the mode's).

- BusDelay: the TIME glide ramps within the block. Sam, 20 Sep 2026 (image
  38): "time and feedback causes crackles on delay ... reverting their
  settings doesn't fix" -- the glide's state moved once per block (up to
  ~17 samples a step) and the loop's tap, REVERSE's heads and GRAIN's read
  base all jumped by the step at every block edge: a click per block for as
  long as the step exceeded a sample (~1 s per big move, in both
  directions, so a revert was another second of it; the exponential tail
  takes ~3 s to settle, which is why it seemed to stay). Measured under
  `dsp_host` (`tools/harness/glide_census.py`: 5,228 / 2,676 / 4,483
  second-difference spikes per mode, 0 / 73 / 896 with the ramp) and under
  the port with the recipe over MIDI (`tools/harness/port_click_census.py`,
  `tools/harness/midi/delay_knob_moves.midi`: 24 -> 6 spikes per 1,000
  samples during the glide in REVERSE, 0 at rest). The loop's Q8 TIME now
  walks from last block's state to this one's a sixteenth of the step per
  sample; REVERSE's lag floor and GRAIN's read base are re-derived per
  sample from it. Bit-identical at rest (`verify_delay`, every case); +28
  words. FDBK and PTCH moves measured clean before and after; the FDBK
  "crackle" was the TIME glide's tail. `dsp_host -sched b:i:s=v` (a knob
  move mid-render) and `-dumpcore`; `verify_set --midi-file` (a CC script
  through the panel's real path).

## Image 38 — 20 Sep 2026 (`OCTABAM38`, bamsep26 at 60f41b0)

On the unit: the reverb on T5 clean (Sam: "verb sounds clean on t5 now")
-- the "less rich / bit-crushed" return of image 35 did not follow the wet
onto the host. Images 33, 34 and 35 were flashed on 20 Sep 2026 without a
section here (the glides; the wow; the RET label); 30-32, 36 and 37 were
built and not flashed. The bullets below are everything since image 29.
Before play: `stamp-defaults <project> bamsep26 --all --keep-mode` (done on
the card for OCTABAM89 and OCTABAM91).

- The bus returns on its hosts (Sam, 20 Sep 2026: the T8 return "has
  proven to be too difficult"; option (b), the chain kept). Each engine
  prints its wet under its host's own dry: T1-4's BusDelay the repeats,
  T5-8's BusVerb the tail (of the sends and the repeats); no return
  anywhere else. Gone: Character's RET (page-1 slot 4 is `---`, a stored
  byte there is never read), `ret_fmt.s`, the position pin's return half
  (GLUE by position stays), the hosts-quiet stamps (`Y:0x9d8/0x9d9`), the
  engines' published stage outputs (`Y:0x9da..0xad9`), the return-station
  liveness stamps (`Y:0x9c4/0x9c5`). The hosts send (a host adds its wet
  in place after its own send tap); the SEND stays refused on T8 (Sam:
  "we still dont want send on t8" -- with MASTER TRACK on its input is the
  mix, the hosts' wet included). Words: Character 1,138 / 1,195 -> 975 / 975,
  BusVerb 1,963 -> 1,914, BusDelay 1,385 -> 1,326; payload A FREE 706 ->
  918, B 1,240 -> 1,519; static cycles reverb 1,159 -> 1,135, delay 1,129
  -> 1,109, Character 639 -> 623. `verify_onebus` rewritten for the host
  prints (T8 still refused; a stored RET byte inert); `verify_set` checks each
  host's chain output and refuses an engine on the wrong core;
  `ot_project.py stamp-defaults` and `ot_spec.py report` warn per part
  about BusVerb on T1-4 / BusDelay on T5-8 (it runs as SEND there). Stamp
  before play (slot 4 127 -> 0). Placement: Modulation moves down on both
  payloads (A 0x17d4, B 0x133b), the shape of OCTABAM5's silence on the
  station banks (`FAILURE_MODES.md`, cause open); if the station banks go
  silent, pad Character back to its previous placement first.

- BusDelay: the tape wow is back and the freeze is gone (Sam, 20 Sep 2026:
  "wow back freeze gone"). WOW on page-2 slot 11 (the freeze's), one depth
  knob, 0 .. ±254 samples, wow 0.8 Hz + flutter 7.3 Hz at an eighth, fixed
  rate, on the loop tap in every mode through the glide's between-samples
  read; WOW 0 is bit-identical to the glide alone (`verify_delay`, every
  case, against image 33's source). The freeze hold, its crossfade, the
  `DFRZ`/`DFRZAT` build hooks and the refhash cases go; CC 67 is WOW. Delay
  1,362 -> 1,385 words. Stamp before play: slot 11 stored 0/1 reads as WOW
  0/1.
- BusDelay (image 33 defect): the glide's fraction slot was raw `$41`,
  inside GRAIN's line-L record (grain 0's window), so in GRAIN the loop tap
  read a window value as its fraction. Found by `verify_delay` when the
  fraction moved: image 33's source differed from itself-with-the-slot-moved
  only in the GRAIN 23 ms +12 case. The lag and fraction are per-sample
  slots `$2b/$2c` now.
- Character RET defaults to 127 and draws as `---` with no value on
  tracks 1-7 (Sam, 20 Sep 2026): a formatter cave
  (`modules/character/ret_fmt.s`) reads the current-track byte and writes
  the descriptor's name field (`RET` on T8, `---` elsewhere, Sam's ask after 35) before
  printing; the build exports every clone's address (`CLONE_<KEY>`) for a
  cave that writes its own descriptor. The DSP already clears the level off
  the master. `verify_labels` reads name and value back from the emulated
  firmware per track; the drawn page is not yet looked at under the port.
- Knob glides against the crackle on knob turns (Sam, 20 Sep 2026: TIME and
  FDBK on the delay brought it back on a clean project): BusDelay reads its
  tap between samples at the glide's fraction and glides FDBK/TONE/PING/WET
  per block; BusVerb glides SIZE (1/64 per block) and TONE/DIFF/SHMR/WET, and
  its init zeroes those slots. Image 33: the crackles gone (Sam, 20 Sep 2026).
- BusDelay: the TIME glide snaps onto its target once within one step. In
  image 33 a TIME increase stopped up to 4 samples short (the /1024 step
  rounds to zero), leaving the tap between samples at rest: a two-sample
  average on every pass round the loop, up to -10 dB at Nyquist per pass.
  Measured: state 600/256 samples below the target stayed there for 2,940
  blocks; with the snap both directions land exactly.
- BusVerb: +6 dB on the wet (WET 127 = ×2); BIG with eight senders at SEND 100
  peaks −8.9 dBFS on the wet alone.
- Modulation: MIX bottom right (page-1 slot 5), LOFI on slot 4 — the wet/dry
  knob sits bottom right on every effect (image 30, on the card).
- MODE top left (page-2 slot 6) on every effect, Character's SAT included;
  page 2 fills from the top left with no gaps: BusVerb `MODE TONE DIFF GATE`,
  Spectrum `MODE`, Character `SAT TONE WDTH`, Modulation `MODE TONE WDTH`.
  `stamp-defaults --all --keep-mode` before play.

## Image 29 — 16 Sep 2026 (`OCTABAM29`, bamsep26 at ed27afe)

On the unit: the link brackets draw, SHFT draws its words on page 1, the
`---` names draw. Before play: `stamp-defaults <project> bamsep26 --all
--keep-mode`.

- The knob pass (Sam, 16 Sep 2026): BusVerb p1 `SEND TIME⌐SIZE SHMR⌐SHFT WET`,
  p2 `MODE TONE DIFF — GATE —`; Character p1 `DRV FOLD TXTR COMP RET MIX`,
  p2 `TONE SAT — — WDTH —`; Modulation p1 `RATE⌐DPTH DLY FDBK MIX LOFI`,
  p2 `— MODE TONE WDTH — —`; links on BusDelay TIME⌐FDBK, SCAT⌐DENS,
  SIZE⌐PTCH and Spectrum FREQ⌐RES, LDP⌐LSP; BusDelay's SCAT/DENS read `---`
  outside GRAIN. `⌐` = the panel's link element (`Param(link=True)`, bit 1 of
  the enable nibble); first use by a module, and the first stepped select on a
  page 1 (SHFT). Renders bit-identical by knob name across the layouts.
  `stamp-defaults --all --keep-mode` before play.
- Modulation: ENS (the Solina) removed; MODE = JUNO DIM FLNG COMB PHSR; FLNG's
  view RATE 8; per-mode output trims (DIM −8, FLNG −7, PHSR −2, COMB −12 dB);
  a LOFI knob on page-2 slot 8 (the delay line clocked coarse and quantised).
  Stored MODE bytes 3..5 read one mode lower: `stamp-defaults` before play.
- BusDelay: the tape wow knobs removed (slots 7/8 are GRAIN's SCAT/DENS).
- BusVerb: MOD / RATE knobs removed, tank modulation pinned; SHMR on page-1
  slot 2 (`stamp-slot <project> busverb 2 0` before play).
- `make check`: the ColdFire-port gates no longer masked as SKIP; the module
  gates (character, spectrum, modulation, nimbus, hello) run; the set gates
  read `~/.octabam_project`; `make image` requires `BUILD=N`.

## Image 28 — 15 Sep 2026 (`OCTABAM28`, bamsep26 at 7b5da98)

- BusDelay: two 32K lines, TIME to 741 ms (1/4 and 1/2T at 121 BPM); a
  stored TIME byte means twice the time.
- Spectrum: TAME removed.
- MODE set over CC 62/68 re-defaults the mode's knobs, as the panel does.

## Images 25–27 — 15 Sep 2026

- 25: the bus engines are add-only pedals with WET knobs; SEND on every
  track; host print only while no return.
- 26: MODE DEFAULTS — a MODE turned on the panel re-defaults its knobs.
- 27: only the MODE select names itself (SIZE / FRZE / SHFT keep their names).

## Image 24 — 15 Sep 2026

- The tempo cave no longer clobbers an FX1 station's page 2 on a bus host
  (note-only cave; the DSP reads tempo from stock).

Earlier images (the 13 Sep 96–100 series, flash 7 = `OCTABAM21`, and before)
are in `docs/remixer/FAILURE_MODES.md`, the module READMEs and the git log
(`git show 3ceba41:docs/history/VOICING.md` for the ear rounds up to 16 Sep 2026).
