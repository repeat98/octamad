# SPECTRUM

A filter pedal on its own id 0x0a (stock FILTER's 0x04 until 30 Sep 2026; FILTER is back). FX1 only: an FX2 instance runs as
a dry pass (`Claims(fx1_only=True)`, `verify_spectrum.py`); the FX2 chooser
hides the row.

| page 1 | FREQ ⌐RES · ENV · LDP ⌐LSP · WDTH |
|---|---|
| page 2 | MODE (LADR SEM ISO VOWL) ⌐SHPE · — · — · — · — |

- **LADR** — the linear zero-delay Moog transistor ladder (audiojs/filter
  moogLadder, MIT), 24 dB/oct; RES 127 is the edge of self-oscillation,
  bounded there. The passband sits at 1/(1 + k) (k up to 3.9 at RES 127:
  −13.8 dB), so since 23 Sep 2026 the output carries a RES makeup
  M = min(1 + k/2, 2.3), one per-block word and one multiply per channel
  (Sam: "the vol drop desperately needs it"). Loop RMS against dry at RES
  64 / 127: FREQ 127 −9.4 / −13.5 → −3.5 / −6.3 dB, FREQ 64 −9.1 / −8.6 →
  −3.1 / −1.4. The clamp keeps `verify_spectrum`'s 0.3 FS noise at RES 127
  off the rails (1 + 0.75k railed 4.6 %, 1 + k/2 0.4 %). VOWL's RES 127
  loss (7.5 to 9 dB on the loop, the bands narrowing) is left: a 0.1 FS
  tone at the formant already peaks at −4.7 dBFS through its ×8 makeup,
  and ×12 put it on the rails.
- **SEM** — a driven Oberheim SEM zero-delay SVF (Zavalishin's
  trapezoidal form, audiojs/filter oberheim, MIT); the cutoff ramps per
  sample, 1/128 of the way to the block's cutoff per sample. SHPE (page 2,
  slot 7; `---` in every other mode) sweeps LP → BP → HP: 0 lowpass, 64
  bandpass, 127 highpass, an equal-power crossfade between neighbours on
  the SVF's taps (27 Sep 2026; BP was its own MODE and SHPE's middle was a
  notch from 23 Sep). With d = (k − 64)/64 below 64 and (k − 64)/63 above,
  kHP = max(0, s(d)), kLP = max(0, −s(d)), kBP = s(1 − |d|), where
  s(x) = x(A − Bx²) is a quarter sine (`fs_qs`: within 0.006 of
  sin(πx/2), s(x)² + s(1 − x)² within 0.05 dB of 1, s(1) = 1.00001 so a
  store limits it onto 1). Each weight is exactly 1 at its own stop and 0
  at the others. The panel prints SHPE as LP / BP / HP at 0 / 64 / 127 and
  the number elsewhere (`shpe_fmt.s`, below).
  - Why equal power: at the cutoff the three taps are equal in size and
    LP/BP, BP/HP are in quadrature, so an equal-power fade holds a tone at
    fc level across the sweep; a linear one dips 3 dB at SHPE 32 and 96
    (float model of the same SVF). Away from fc the level follows the
    passband that is fading in, as it does between any two filter types.
  - Loop RMS, dBFS (`dsp_host`, FX1 slot, FREQ 64 = fc 949 Hz; the loop
    stem is `scripts/make_test_audio.py loop` at 0.5, 3 s):

    | signal | RES | SHPE 0 | 32 | 64 | 96 | 127 |
    |---|---|---|---|---|---|---|
    | loop stem | 0 | −20.1 | −23.1 | −35.2 | −30.5 | −28.4 |
    | loop stem | 64 | −20.0 | −22.8 | −33.1 | −29.6 | −27.7 |
    | tone 949 Hz (fc) | 0 | −16.9 | −17.0 | −16.9 | −17.0 | −16.9 |
    | tone 949 Hz (fc) | 64 | −4.8 | −4.9 | −4.8 | −4.9 | −4.8 |
    | tone 300 Hz | 0 | −16.6 | −19.2 | −26.6 | −29.3 | −36.6 |
    | tone 3 kHz | 0 | −36.8 | −29.4 | −26.7 | −19.1 | −16.6 |

    The loop's −35 dB at 64 is the bandpass on a low-heavy loop: BP was
    that level as its own MODE (SHPE 64 is bit-identical to it).
  - Saved parts: MODE's values moved (BP 2 → SEM 1, ISO 3 → 2, VOWL
    4 → 3); SHPE keeps its stored value, so a part that was on BP comes
    back as SEM at whatever SHPE it held. Once per project, before play:
    `python3 tools/hw/ot_project.py remap-slot <project> SPECTRUM MODE 2:1,3:2,4:3`.
- **Ramps** (26 Sep 2026): every coefficient a knob moves (the SVF's c4 d
  kLP kHP, LADR's k/4 d/2 M/4, VOWL's b0 m1 a2 per formant and vg, ISO's
  gn lpBase trim) is a run value the loop steps once per sample, 1/128 of
  the way to the block's target (`fs_rset`, `fs_r3`); a step that rounds to
  0 lands it on the target, and the first block of a mode starts it there.
  VOWL's morph fraction is 21 bits (5 until then). `make verify-knobs`
  measures every knob moved mid-render; a knob at rest renders as before,
  except the cutoff under ENV or the LFO, which now follows them through
  the 1/128 ramp.
- **ISO** — an isolator (Airwindows Capacitor2; `capacitor2_ref.py` is the
  float reference). In ISO FREQ is LOW and RES is COLR, the dielectric colour.
- **VOWL** — a three-formant bank (constant-peak-gain resonators) morphed
  across A E I O U by FREQ; RES (SHRP) narrows the bands. Formants are
  Peterson & Barney (1952) male means; bandwidths 90 / 110 / 170 Hz.

FREQ is exponential, 60 Hz → 15 kHz, an equal step per detent (a 33-word
P table interpolated per block). ENV (a block-peak follower, instant attack,
LSP = release) and LDP (an LFO, LSP = speed ~0.08–9 Hz) both move the
cutoff. WDTH is mid/side width on the output. TAME (the filters' state
saturation, 14 Sep 2026) is gone since 15 Sep 2026 -- Sam: "tame should be
gone"; the removal is bit-identical to TAME 0 and frees the two `div`-fed
per-block words and six 28-word calls per channel pair.

Defaults are a bit-exact passthrough (FREQ 127, RES 0, ENV 64, LDP 0, WDTH
64, MODE 0): the engine detects that block and copies nothing, because every
part that chose FILTER runs this on FX1. A part's stored bytes are stock FILTER's until
`ot_project.py stamp-defaults` writes ours.

Every mpy is `mpy x0,y1` or `fs_qs`'s `mpy y0,x0`, the audited-signed
forms, but the VOWL decode's `mpy x1,y1,b` (R' > 0;
`build_bus.MPYSU_AUDITED`); every clip is the store limiter.

## SHPE's display

`shpe_fmt.s`, a ColdFire formatter cave (89 B) registered as page-2 slot
7's formatter (`fmt(buf, value)` → sprintf): "LP" at 0, "BP" at 64, "HP" at
127, `%d` elsewhere; the stored and delivered value stays 0..127. In LADR,
ISO and VOWL, whose MODE rename names the slot `---`, it prints the number:
it reads slot 7's name from the clone (`CLONE_SPECTRUM` + 0x40, a build
export), so its bytes depend on the clone's address and the source is the
only truth (a build without the m68k toolchain refuses). It is pinned at
`0x400c45b0`, the 338 B zero run (`docs/remixer/PLACEMENT.md`): the clone
window had 18 B left and the overflow run none, and floating it there
pushed MODULATION's 454 B label formatter out of both (the build refused).
midisc's own build used that run on hardware; in the remixer its
`enc_unlock` is DRAM.

## Measured

- `tools/verify/verify_spectrum.py`: defaults bit-exact on a full-scale
  ramp; LP slope; SHPE 64 (BP) and 127 (HP) at DC → 0; a tone at fc level
  within 0.5 dB across SHPE 0..127; SHPE 32 passes DC at 0.704 (≈ cos π/4),
  96 blocks it; VOWL A vs I distinct; every knob at both extremes renders;
  an FX2 instance is a bit-exact dry pass.
- The BP fold (27 Sep 2026), against main's build over 15 settings
  (FREQ 64 RES 90 WDTH 100, each with and without ENV/LDP): LADR, ISO, VOWL,
  SEM at SHPE 0 and 127, defaults, zeros and max are bit-identical, and
  SEM at SHPE 64 is bit-identical to main's BP MODE. The SVF loop's two
  channel copies became one body (`do #2`), which paid for the crossfade's
  words: Spectrum 1,338 → 1,337 words (main after #476); the SVF loop
  127 → 139 words/sample in the pricer (ISO's 262 still prices the station).
- `verify_labels` calls SHPE's formatter after the MODE formatter in each
  mode: SEM prints 0:LP 32:32 64:BP 96:96 127:HP; LADR, ISO, VOWL print
  the numbers.
- `tools/verify/verify_spectrum_ident.py ref/check` (13 settings: every
  MODE with and without ENV/LDP, defaults, zeros, max) and `make verify-ident
  MOD=spectrum` (every MODE at two knob sets, zeros, max): the bit-identity
  gates for a rewrite.
- `verify_dirtystate` (in `make verify`): init zeroes every persistent slot
  the loop reads. Before it did, filter B's frozen HP poles held a stale
  value and put up to a full-scale DC on a station's output, which surfaced
  on hardware as the master compressor collapsing the right channel.
- Cost (pricer words/sample per mode, SVF / VOWL / LADR / ISO): 126 / 216
  / 238 / 292 on 23 Sep 2026 after SHPE and the makeup → 107 / 170 / 198 /
  250 after the loop pass the same day (one `do n7` per MODE, dispatched
  per block; only the selected mode's stream is built; the input peak,
  LADR's Grun and CAP's rotation count in address registers for the loop;
  CAP's amounts ring set up per block and written in read order, its
  four per-block constants in a second ring; the parallel moves stock runs
  in the same shape: `mpy/mac … x:(rN)+,x0`, `x:(rN),x0`, `add … a,x0`,
  `a,y0`, `x0,b`, `x1,b`, `asl a a,x1`, `asl b y0,a`; `max a,b` for the
  peak). Displaced moves (`x:(r7+$nn)`, 3.98 cycles on the chip against 2.00
  for a pointer or register move, probe 57, `docs/firmware/CHIP.md` §2) per
  sample: 49 / 78 / 39 / 88 before the 22 Sep pointer rewrite, 9 / 7 / 10 /
  17 after it, 4 / 0 / 0 / 1 now (SVF's cutoff ramp and its two reads; ISO's
  WDTH). LADR's G' clamp at $7f0000 went: G = g/(1+g) is 0.645 at the
  table's top (0x748894) and the ramp stops at G. Both identity gates
  bit-identical across the pass; hardware cycles unmeasured (a station's
  timer window is pre-empted by whole frames, CHIP.md §2). Program words:
  payload A FREE 848 → 621 (four loops carry their own width block).
- `verify_menu`, `verify_replaces`, `verify_labels` pass on the rig.

On Sam's unit since flash 4; the LADR voicing (PR #254) since image 21.

## Open

- VOWL went silent once on the unit with RES up
  (`docs/remixer/FAILURE_MODES.md`, seen once, not reproduced).
- The remaining displaced moves are the SVF's cutoff ramp (g2run += dg,
  read twice per sample) and ISO's WDTH read; the other modes step g2run
  per block by n7·dg (`fs_gramp`), the same end value.
