# Changelog

One entry per image that reached a unit, newest first; `Unreleased` is what
main carries beyond the last flashed image. The version the panel shows is
`BUILD` (`make image BUILD=N`); a git tag `OCTABAM<N>` marks the commit each
flashed image was built from.

## Unreleased (main after image 38)

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
