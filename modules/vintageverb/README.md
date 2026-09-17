# Vintage Verb

A Dattorro plate reverberator, running at half the audio rate, replacing
stock DARK REV (FX2 id 0x16).

Status: unflashed, gated locally only (no hardware pass). v3, 17 Sep 2026.

## v3: half rate buys the room AND the cycles

v2 was structurally right but cost 1.62x stock's instruction count, and its
room was small: 16,384 words at 44.1 kHz is a 0.30 s figure-8 where
Dattorro's own tuning is 0.717 s. Both are the same problem, and running the
tank at **22.05 kHz** fixes both at once -- the tank executes every other
sample, and the same memory holds twice the time (0.607 s figure-8, 85% of
Dattorro's). 22 kHz is also what the machines this is named after ran at
(Lexicon 224: 31.25 kHz, AMS RMX16: 32 kHz), so an 11 kHz reverb bandwidth
is period-correct rather than a compromise.

The input is decimated by a two-sample average whose null sits exactly on
the new Nyquist, so it *is* the anti-alias filter; the output is linearly
interpolated back up (the last two tank outputs are kept, a tank sample
emits the older and an off sample their mean, so every sample carries the
same two-sample latency and there is no zero-order-hold step). Measured: no
image spikes -- the tail rolls off smoothly, -20.7 dB at 8-10 kHz to
-28.6 dB at 16-20 kHz relative to its 0.5-2 kHz level.

| | words | instr/sample | vs stock | figure-8 loop |
|---|---|---|---|---|
| v1 Freeverb | 729 | 493.6 | 2.50x | n/a |
| v2 Dattorro, full rate | 466 | 319.9 | 1.62x | 0.30 s |
| **v3 Dattorro, half rate** | **497** | **200.6** | **1.02x** | **0.607 s** |
| stock DARK REV | 1,067 | 197.2 | 1.00x | -- |

RT60 across the DECAY knob: 30 -> 1.29 s, 60 -> 1.74 s, 90 -> 2.50 s,
110 -> 3.33 s, 127 -> 4.67 s. Click IR at DAMP 85: DC -0.000001, bands
7% / 26% / 50% / 11% / 6% (below 200 Hz / 0.2-1k / 1-4k / 4-8k / above 8k),
centroid 2759 Hz, no clipping at any tested setting.

`cycle_count.py` prices this at 374 cycles, which is a CEILING, not the
cost: the half-rate gate is a forward conditional skip and the tool charges
the tank path on every sample (the module declares
`; CYCLES_FORWARD_BRANCHES`, and the tool permits only *conditional*
forward skips -- an unconditional `bra` is refused, which is why the off
path falls through rather than branching around the tank).

## ⚠️ A measurement error that invalidated a day of analysis

Every render this module was judged by before 17 Sep 2026 was analysed by a
script that read the harness's **24-bit** output WAVs as **16-bit**
(`wave.getsampwidth()` is 3; the reader assumed 2). Misparsed bytes still
produce an RMS envelope that loosely tracks the real one, which is why the
numbers looked plausible and nobody caught it: the decay curves, the
"both effects plateau at high decay" finding, the peak/clipping figures and
every spectral claim from that analysis are **retracted**. The listening
tests were of course unaffected, which is why the ear caught what the
instrument did not. The analyser now dispatches on `getsampwidth()` and is
the only thing the numbers below come from. Same family as CLAUDE.md's
"a measurement can be structurally blind to the thing you are using it to
rule out" -- here the instrument was blind to *everything*, confidently.

## Why v1 was replaced rather than tuned

v1 was a Freeverb (parallel damped comb filters into series allpasses).
Re-measured correctly, its click IR said:

| | v1 Freeverb | stock DARK REV |
|---|---|---|
| RT60 at DECAY 100 | **0.75 s** | ~4 s |
| loudest tail component | **0 Hz** | 108 Hz |
| tail below 200 Hz / above 8 kHz | 14% / 27% | 3% / 18% |
| tail centroid | 5490 Hz | 4688 Hz |

Four combs of ~1,200 samples at g = 0.78 *is* a 0.8 s decay -- the short
tail was structural, not a knob. A comb filter has DC gain 1/(1-g) and
nothing blocked DC, so the tank filled with rumble until 0 Hz was the
loudest thing in it. Four combs is a sparse, ringy mode set (peaks at
102/199/802 Hz). And WARP's modulation stepped the read pointer by a whole
sample every 512 samples -- an ~86 Hz click train laid over the tail. Boomy,
fizzy, hollow and short, all at once, and none of it reachable by tuning.

## What v2 is

Dattorro's plate reverberator (JAES 1997, *Effect Design Part 1*) -- the
structure most lush digital reverbs descend from. Input diffusion into a
figure-8 tank of nested allpasses, which builds echo density
**exponentially** rather than linearly, so it is smooth where a comb bank is
ringy. It is also **cheaper** here than the comb bank was, for two reasons
that are both structural:

- allpasses are unity-gain, so there is no headroom scaling to get wrong and
  no DC accumulation to block (one input DC blocker is enough);
- **one shared circular buffer**: Y:0x4000..0x7FFF, 16,384 words, `m5 =
  $3FFF`, `r5 = base + head`. Every line writes at `(head - W)` and reads at
  `(head - W - D)`, so its data occupies the fixed relative window
  `[W, W+D]` and **the AGU's modulo does every wrap for free**. v1 spent
  seven instructions per line on a compare+`tge` wrap and another four on
  per-line pointer bookkeeping; v2 spends none. (0x4000 is 16,384-aligned,
  which is what the modulo mode requires.)

Signal path: mono/4 -> PRE -> DC block -> input LP -> 3 series allpass
diffusers (142/107/379) -> figure-8 tank (per branch: modulated allpass ->
delay -> damping LP -> ×DECAY -> allpass -> delay, each branch fed by the
other's output ×DECAY) -> 4-tap output, L and R built from different points
in the tank -> WIDTH -> MIX. The allpasses use the one-coefficient form
(`v = x - g·v[n-N]`, `y = v[n-N] + g·v`) built from two `mac`s, which is 6
cycles cheaper each than the two-multiply form and mathematically identical.

## Measured (all from the corrected analyser)

- **Cost**, benchmarked against genuine stock DARK REV the same way
  (`dsp_host` per-block instruction meter via `send_probe -v --direct`,
  12,060 blocks; the module is temporarily renamed `_vv_hidden` for the
  stock reading -- see the methodology note below):

  | | words | static cycles/sample | dynamic instr/sample | vs stock |
  |---|---|---|---|---|
  | v1 Freeverb | 729 | 646 | 493.6 | 2.50× |
  | **v2 Dattorro** | **466** | **369** | **319.9** | **1.62×** |
  | stock DARK REV | 1,067 | *(uncounted)* | 197.2 | 1.00× |

  Four instances on one core cost 1,476 of the 3,120-cycle usable budget.

- **Decay is now spread across the whole DECAY knob** instead of crammed
  into its top 15 values (measured by fitting the -5..-35 dB slope of the
  click IR): DECAY 40 → 0.93 s, 80 → 1.53 s, 100 → ~2.4 s, 110 → 2.85 s,
  127 → 5.35 s.

- **The tail is clean**: DC is −0.000003 (v1: 0 Hz was the loudest
  component). Click IR spectrum at DAMP 85: 5% below 200 Hz, 22% 0.2–1k,
  54% 1–4k, 16% 4–8k, 3% above 8k, centroid 2509 Hz -- a full-range tail,
  where v1's was scooped. No clipping at any tested setting.

- **The modulation no longer adds grit.** WARP=0 leaves 5.6% of the late
  tail above 10 kHz; WARP=127 leaves **2.2%** -- i.e. modulating *reduces*
  HF (it smears the modes) instead of adding a click train, because the
  read is now linearly interpolated between two taps.

- `make check REMIX=vintageverb`: 154 `[PASS]`, no failures other than 6
  pre-existing unrelated remixes that cannot build Octakit's ColdFire
  runtime on this machine's toolchain (reproduces with this module absent).
  `verify_dirtystate` silent from a garbage instance block;
  `verify_initregs` r1 preserved; `verify_replaces` both directions.

## Methodology note, still true

Once a module declares `MenuEntry(replaces="DARK REV")`, auditioning genuine
stock DARK REV through `send_probe.py --direct` decodes its knobs through
*this* module's slot layout. Use `tools/remix/audition.py` (resolves by name
through the registry), and for a clean stock baseline rename the module
directory to start with `_` and rebuild the scratch dump. The dynamic
instruction count is unaffected either way (data-independent code): stock
measures 197.2 with this module present and hidden alike.

## Inferred, not measured

- The tank delays are Dattorro's, scaled ~0.62 to fit 16,384 words; the
  output tap positions are scaled likewise. Neither was tuned by ear.
- The input LP (0.70), the allpass gains and the ~1.3 Hz LFO rate are
  Dattorro's values or plausible defaults, not A/B'd here.
- No hardware pass: cycles are the emulator's. A stock effect's true cost
  needs the hardware burn sweep (`CHIP.md` §2), not run for either side.

## Open

- Still 1.62× stock DARK REV. Available cuts, in the order I would take
  them: the constant table (put the ~33 `n5`/gain immediates in Y and walk
  them with r6, −33 cycles, no sound cost, but needs warm-up init); the
  third input diffuser (−15); two of the four output taps (−12); making the
  second tank allpass unmodulated (−14). Together ≈ −74 cycles → ~1.3×
  stock, at some cost in smoothness for the last three.
- No hardware flash; not in any shipping remix (own `remixes/vintageverb.py`).
- WARP has no rate knob; the allpass gains are not knob-controlled
  (the reference's DENSITY/DIFFUSION).
