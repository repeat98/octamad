# Gloam Verb

A new reverb algorithm replacing stock DARK REV (FX2 id 0x16). A small
four-line Hadamard-mixed FDN: no LFO, no interpolation, no input diffuser,
no shimmer -- closer in spirit to Airwindows' VerbTiny (small, cheap,
Hadamard-butterflied, a downsampled/non-modulated tank) than to this repo's
own BusVerb (eight modulated lines, input diffuser, shimmer). It is not a
port of VerbTiny or of anything else: Airwindows' processing is
double-precision float C++ with `pow`/`frexp`/dither, none of which exists
on this fixed-point chip, so the arithmetic idioms (the one-pole damp, the
Hadamard butterfly, the A2-clean dance after every `and`) are this repo's
own, proven ones (BusVerb's, Nimbus's), applied to a smaller topology.

Status: unflashed, gated locally only (no hardware pass).

## What it is

- Four fixed-tap 4096-word lines (taps 1327/1979/2663/3541 samples, picked
  with no simple common ratio so the un-modulated tank does not ring on one
  pitch), one shared write pointer (all four lines are the same size).
- Per line, per sample: read the old tap, one-pole damp it (DAMP), scale by
  DECAY, feed all four through a 4x4 Hadamard butterfly (two sum/difference
  stages, normalised by one right shift so the matrix itself adds no gain),
  inject the pre-delayed mono input with alternating sign, write back.
- Two of the four post-Hadamard rows (two orthogonal rows of the same
  transform) feed WET L/R directly -- decorrelated for free, no separate
  wet-sum stage.
- A 2048-word pre-delay line ahead of the tank (PRE, 0..~46 ms).
- WIDTH blends wet L/R toward their mono sum; MIX crossfades dry/wet
  (`docs/firmware/PARAM_PAGES.md`-shape: page 1 DECAY/DAMP/PRE/MIX, page 2
  slot 6 WIDTH).
- Buffer: Y:0x4000..0x87FF (18,432 of the 32,768-word per-core FX2-instance
  region) -- the same ground BusVerb's tank and Nimbus's line use, so only
  one of the three may be selected per core.
- Every buffer address is a full literal plus a masked (manually `and`ed)
  offset -- Nimbus's idiom, not BusVerb's hardware-AGU-modulo tank, chosen
  specifically to avoid the alignment precondition hardware modulo depends
  on. No `do` loop over the four lines: each is unrolled straight-line code
  (Nimbus's idiom again), so no Tcc pair or address-register modulo state
  is shared across code that could grow between two uses of it.

## Measured

- **Build**: `make check REMIX=gloamverb` -- assembles clean on both
  payloads, 348 words each (stock DARK REV is 1,067). `verify_dirtystate`
  (8 renders from a garbage-filled instance block, defaults and every knob
  nudged): tail and transient peak both -138.5 dBFS -- silent, so init
  zeroes everything the sample loop reads. `verify_initregs`: r1 preserved.
  `verify_replaces`: DARK REV correctly aliased to GLOAMVERB's dispatch
  when this module is selected, and correctly left as real stock DARK REV
  in every remix that omits it.
- **THD** (`send_probe.py`, 438.74 Hz bin-centred sine, --direct): -143 dB
  -- the tank has no saturating nonlinearity in this signal path, so this
  number says "linear system", not "sounds good".
- **Static cycle cost** (`cycle_count.py`, a floor -- word-span of the
  sample loop, no contention modelled): **265 cycles/sample**. Four
  instances on one core (the worst case a chooser allows): 1,060 of the
  3,120-cycle usable budget (`docs/firmware/CHIP.md`) -- comfortable
  headroom even at 4x.
- **Dynamic instruction cost** (`dsp_host`'s per-block meter via
  `send_probe.py -v`, 12,060 blocks of 16 frames, steady state, compared
  against GENUINE stock DARK REV -- see the methodology note below):
  **Gloam Verb ~236.9 instructions/sample; stock DARK REV ~197.2
  instructions/sample.** Gloam costs about 20% MORE dynamic instructions
  per sample than stock, despite being about a third the code size (348 vs
  1,067 words) -- the four lines are fully unrolled with no shared
  sub-expression reuse across them, where stock's larger word count
  apparently buys cheaper steady-state per-sample work (a `do` loop or
  narrower per-line arithmetic this module does not have visibility into,
  since stock's source is not in this repo). Reported as measured, not
  inferred to be better or worse -- smaller code and cheaper-per-sample are
  different claims and this module is only the first one.
- **Audio**: click (single-sample impulse), loop (drum groove) and pad
  (sustained chord) renders of both, at roughly matched settings
  (DECAY=100 MIX=90 here; TIME=100 MIX=90 on stock), via
  `tools/remix/audition.py`. Not committed (never an Elektron byte, and
  these are synthesised test signals besides, so the rule does not even
  apply -- they are just build output, `out/_audition/` and
  `out/test_audio/` are gitignored); reproduce with:

  ```
  python3 scripts/make_test_audio.py
  python3 tools/remix/audition.py gloamverb out/test_audio/loop.wav DECAY=100 MIX=90
  python3 tools/remix/audition.py dark out/test_audio/loop.wav TIME=100 MIX=90
  ```

## A methodology trap found while measuring this (added to the general
## catalogue below is the specific instance; the rule itself belongs in
## CLAUDE.md-style project memory, not repeated per-module)

**Once a module declares `MenuEntry(replaces="DARK REV")`, auditioning
GENUINE stock DARK REV locally through `send_probe.py --direct` (not
`tools/remix/audition.py`, which handles this) gets its knobs decoded
through the REPLACEMENT's slot layout, not stock's own** -- this module's
DECAY/DAMP/PRE/MIX/WIDTH landing in stock's own BAL/HP/LP/MIX/MIXF/MONO/
PRE/SHVF/SHVG/TIME fields is not a mapping that means anything, and one
first render of it (click.wav, module present, `--pick V` against a
`restock` dump) came back as a dead-flat -16.7 dBFS forever -- not decaying,
not silent, a sustained non-decaying artifact from garbage in TIME or
similar. Confirmed by temporarily hiding this module (`modules/_gloamverb/`,
the registry's own "directories starting with `_` are skipped" convention)
and re-rendering: stock DARK REV at its OWN defaults is close to silent
after a click (a conservative low-MIX default, matching stock FLANGER's
MIX=0 dry-pass convention elsewhere in this repo's own gates), and with
TIME/MIX pushed up by name it renders a plausible, slowly decaying tail.
The DYNAMIC INSTRUCTION COUNT (`-v`'s core meter) was NOT affected by this
-- 197.2/sample either way, module present or hidden -- because it is
data-independent code, not data. The AUDIO was completely unusable while
contaminated. Same family as CLAUDE.md's "a dump can resolve a perfectly
plausible dispatch entry for an effect it does not contain": a clean-looking
render is not evidence the thing being rendered is what you asked for.
`tools/remix/audition.py` is unaffected (it resolves the module by name
through the registry directly, not by re-deriving stock's knob layout from
whichever module currently owns the id) and is the tool to use for a stock
effect's own behaviour once a replacement exists in the tree.

## Inferred, not measured

- The tap constants (1327/1979/2663/3541) were chosen for "no simple common
  ratio", not derived from any target modal density; nobody has listened
  for metallic ringing on a sustained tone systematically (the pad render
  is a start, not that measurement).
- No hardware pass: cycles/instructions are the emulator's; the project's
  own experience (`CHIP.md`) is that a stock effect's TRUE cost needs the
  hardware burn-sweep (`make burn`), which this module has not had run
  against it, on either side of the comparison.
- WIDTH's mono-fold behaviour and the pre-delay's audible effect have not
  been checked by ear against a reference, only that they assemble, pass
  `verify_dirtystate`, and the THD gate stays clean with them nudged.

## Open

- No hardware flash; no `make burn` cycle-sweep comparison (the only way to
  price stock DARK REV's TRUE cost, per `docs/firmware/CHIP.md` s2).
- Not added to any shipping remix (`bamsep26`, `mods`, etc.) -- lives in its
  own `remixes/gloamverb.py` for isolated local testing only.
- No listening pass for the un-modulated tank's ringing on a sustained tone
  beyond the one pad render.
