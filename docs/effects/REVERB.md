# BusVerb

An eight-line FDN reverb, the reverb server of the bus (`XBUS.md`), hosted
on T5's FX2 in the rig. Source `modules/busverb/reverb_server.asm`, manifest
`modules/busverb/manifest.py` (the MODE rows), built by
`tools/build/build_bus.py`. The development record (the four-line engine,
the 32K re-layout, the crackle, the voicing rounds) is
`REVERB.md` and `VOICING.md` under `docs/history/` in git history
(`git show 3ceba41:docs/history/<name>`). ✅ measured on the
unit, 🟡 harness only.

## Signal path

```
chain in ─► 4 series allpasses ─► ┌─ FDN tank ───────────────┐ ─► shimmer ─► gate ─► width ─► WET
 (aux Σ, or the delay's    (input diffusion,     │ 8 × 4096-word lines       │
  output while it is live)  taps 641..1949)      │ interpolated LFO per line │
                                                 │ 8×8 FWHT (24 butterflies) │
                                                 │ HI damping + LO cut       │
                                                 │ in-loop allpass, lines 0-1│
                                                 └───────────────────────────┘
```

- Input diffusers: four series allpasses, taps 641/1051/1511/1949 (2048-word
  buffers; all modes share them since Round 13). Coefficient = DIFF + the
  mode's offset (`$3f`).
- Tank: eight 4096-word lines (spacing `0x1000`, modulo `0xfff`), an 8×8
  Walsh-Hadamard feedback matrix, decay constants scaled 2/√8. Every read
  is interpolated and LFO-modulated, each line on its own prime-relative
  rate; the input is attenuated 12 dB before the tank (headroom inside the
  loop; the output sum no longer divides, so the level is unchanged).
- In the loop: a one-pole low-pass (HI) and high-pass (LO) per line, one
  shared coefficient per pass; in-loop allpasses on lines 0 and 1, 512
  words, taps 298/446, LFO-modulated at a fixed non-zero depth.
- Out: L/R tap sums before the FWHT, sign patterns `+−+−+−+−` and
  `++−−++−−`; shimmer (a pitch shifter in a 2048-word line; `NOSHIM=1`
  excises it); GATE; mid/side width (pinned wide); the stage crossfade.
- The 4096-word pre-delay buffer is mapped and never read (PRE retired).

## Parameters

| page | slot | label | reads | function |
|---|---|---|---|---|
| 1 | 0 | SEND | `r6+$0` | this host's own dry into the aux bus (3-bit headroom, counted through `Y:0x941`); default 0 |
| 1 | 1 | TIME | `r6+$1` | feedback 0.875..0.999 via the mode's `k_mode` |
| 1 | 2 | SIZE ⌐ | `r6+$2` | scales all eight taps within the mode; floor `f = 0.4` (~1,810 samples, 24 Hz mode spacing); glided 1/64 per block since 20 Sep 2026 (state `y:$09f3`, zeroed at init, clamped to f's range); drawn linked to TIME |
| 1 | 3 | SHMR | `r6+$3` | shimmer amount, 0 off (bit-identical to no shimmer) |
| 1 | 4 | SHFT ⌐ | `r6+$4` | shimmer interval, 4 steps: +12 / +19 / +7 / −12; drawn linked to SHMR; the first stepped select on a page 1 (✅ image 29: draws its words) |
| 1 | 5 | WET | `r6+$5` | `out = in + 2 × wet × WET`, `in` the chain input at unity; 0 passes the chain input alone; the ×2 is 16 Sep 2026's makeup ("reverb is still too quiet"): BIG's wet alone with eight senders at SEND 100 peaks −8.9 dBFS, no clipping |
| 2 | 6 | MODE | `$c` bits 16–23 | 0 ROOM, 1 PLATE, 2 BIG; slot 6 since 4 Sep 2026 (an even slot is one the panel's page-2 editor writes) |
| 2 | 7 | TONE | `$c` bits 8–15 | LO + HI on one knob: 0..64 = LP 0..127 with HP off, 64..127 = HP 0..126 with LP open; 64 = flat |
| 2 | 8 | DIFF | `$d` bits 16–23 | allpass coefficient ~0.38–0.80 |
| 2 | 9 | GATE | `$d` bits 8–15 | gated reverb: 0 off; hold ~46–780 ms before the wet shuts; envelope keyed on the tank input (`$1b`), fast attack, ~20 ms eased release, per-sample multiply on the wet |
| 2 | 10, 11 | — | | (the tank modulation is pinned at MOD 30 / RATE 1× inside the engine since 15 Sep 2026; page 2 fills from the top left) |

The layout is the 16 Sep 2026 knob pass (before it: SEND TIME SHMR SIZE TONE
WET / MODE — DIFF SHFT GATE —). The renders at any knob value by name are
bit-identical across the two layouts.

The page-2 field map is `docs/firmware/PARAM_PAGES.md` §6. Stock DARK reads
its pre-delay from `$c`; BusVerb's `$c` knob field is MODE.

## MODE

Seventeen (r7 slot, value) pairs per mode, copied into the r7 block after
warm-up (`manifest.py` `_MODE_ROWS`; taps as fractions of the 4096-word
line):

| lever | r7 | ROOM | PLATE | BIG |
|---|---|---|---|---|
| `k_mode` (TIME law) | `$1e` | 0.5 | 0.4 | 0.25 |
| wet gain/2 | `$20` | 0.988 | 0.988 | 0.703 (−3 dB) |
| lines 0–3 taps | `$74..$77` | 3958/3386/2894/2474 | 3528/3283/3056/2845 | 4050/3403/2860/2403 |
| tap scale | `$6f` | 0.60 | 0.5625 | 1.0 |
| diffusion offset | `$3f` | 0.125 | 0.125 | 0.094 |
| damping scale | `$72` | 0.953 | 0.78 | 0.90 |
| mod depth scale | `$73` | 1.0 | 1.0 | 0.60 |
| wet high-cut | `$7a` | 0.523 | 0.68 | 0.60 (~6.4 kHz) |
| lines 4–7 tap scale (interleave) | `$6c` | 0.71875 | 0.765625 | 0.789 |
| diffuser taps | `$7e..$81` | 641/1051/1511/1949 | same | same |
| LFO rate scale | `$2f` | 1.0 | 1.0 | 1.0 |

The mean tap is 3178 in every mode (tap scale and spread independent). A
HALL mode was cut as indistinguishable from BIG in blind A/B. On the
four-mode engine of the time RT60 measured 2.7 / 4.7 / 7.7 / 10.0 s ✅.

## Memory

Buffer base `Y:0x4000` (the bank's whole FX2 allocation), every other
buffer in this core's half of the shared window (`build_bus.py` rewrites
the base literal per payload); 65,536 words per server:

| location | size | what |
|---|---|---|
| `base+0x0000..0x7fff` | 8 × 4096 | tank lines, taps to ~3914 (89 ms) at SIZE max |
| `shared+0x0800..` | 2048 | shimmer line |
| `shared+0x1000..0x1fff` | 4096 | former pre-delay, never read |
| `shared+0x2000..0x3fff` | 4 × 2048 | input allpasses |
| `shared+0x4000` / `0x4200` | 2 × 512 | in-loop allpasses |
| `shared+0x4500..` | 13 words/line | tank state tables A (tap loop) and B (write-back), 104 of 256 |

r7 block: `$00..$83` in use, `$84+` hangs the DSP; `$82` warm-up counter
(`$2c0000 | blocks`, capped 0x100), `$83` write phase; the asm header is the
slot map. The warm-up zeroes the allocation 128 words a block over 256
blocks and outputs dry until warm. One BusVerb per bank (role lock); a
second instance returns as a passthrough. Every address register is
committed in the sample loop; the rolled tank loops walk the Y state table.

## Engine rules

- Interpolation fraction: integer part via `asl #n`, fraction masked with
  `2^(24−n)−1` and shifted by `n−1`, never `n` (a shift by `n` reads
  negative past `0x800000` and the read jumps backwards once per LFO step:
  a fast flutter).
- Offset/fraction pairing: each line's fraction comes from the same LFO as
  its integer offset. Two lines with swapped fractions put a 1-sample
  sawtooth at ~76 Hz on the tail (−29.6 dB): the crackle. The carried
  interpolation partner (−64 dB) and the block-stepped LFO (−62.5 dB, 64
  cycles/sample) were not it.
- The in-loop allpasses' `d0` carry is seeded per block like the tank's
  (28 instructions per block).
- Modulation never reaches zero; rate, not depth, is what reads as
  seasick (pitch shift ∝ d(delay)/dt), and the pinned ~0.4 Hz base was the
  binding cause of the metallic end-ring: base ×8 to ~2.2 Hz with depth
  scales trimmed (Round 13; ROOM's crest 65 → 49).
- An in-loop allpass above ~15% of its line's length disperses (a spring)
  rather than diffuses; the 2048-word versions were cut for this.
- Pack the buffers: taps spanning 2.1:1 in equal power-of-two buffers left
  ~40% of the delay memory unread; ~1.6:1 recovered it.
- Input diffusion smooths the attack, in-loop diffusion thins the modes;
  they are not interchangeable.
- Averaging more tank lines into each output concentrates energy (the
  lines share a matrix); disjoint 2-line pairs per channel.
- Spectral flatness rewards broadband noise (it ranked the flutter builds
  highest); early crest factor is the companion metric; when it and the
  ear disagree, the ear is the measurement. Clipped-sample counts predict
  audibility badly (26,741 clipped on bass inaudible; 6 on the synth
  audible: loop compression, not the output rail).
- Modal prominence (8–11 dB over the local envelope) is monotonic in total
  delay; total delay read at SIZE max is the lever and it is spent.
- Change one thing per flash.

## Cloned descriptor rules

Four per-parameter arrays, `P`-relative (`docs/firmware/PARAM_PAGES.md`
§2, §7): `P+0x9a` count (drawn on a fixed 0–127 scale: count 16 = ⅛ of the
travel), `P+0x0ca` formatter A, `P+0x0fa` widget B, `P+0x12a` (zero for a
stepped control; 20 of 20 stock stepped params). A clone inherits all four
from its donor. Stepped pairs: CHORUS.TAPS (count 5) `0x4003c718` /
`0x40047254` (MODE uses this); SPATIALIZER.PHSE (4) `0x4003bbc0` /
`0x400467a4`; FILTER.Q (4) `0x4003bc60` / `0x40046c28` (draws
`none|HP|LP|BOTH`: the words come from the renderer, not the descriptor).
Every enabled slot needs an explicit in-range default (`verify_menu`).

## Render and verify

```sh
python3 tools/harness/render_reverb.py loop.wav                      # wet+dry
python3 tools/harness/render_reverb.py loop.wav -p TIME=100 -p SIZE=127 -p WET=80
python3 tools/harness/render_reverb.py loop.wav --sweep SIZE=0,64,127 --wet
python3 tools/harness/render_reverb.py loop.wav --build              # rebuild first
```

Knobs are named: `-params` indices 0–5 are page 1, 6/8/10 the knob fields of
`$c/$d/$e`, 7/9/11 their companions. `--wet -p WET=0` renders digital
silence (the alignment self-check). The tank is time-varying: render
material, not an impulse convolution. `send_probe --rmode` drives MODE
through the parameter word; `render_reverb --mode` forces the decoded value
and cannot see the field map. What needs hardware: the cycle budget under
load, everything ColdFire-side, a mid-run parameter change. `make
verify-bus` and `make check` are the gates (`docs/remixer/HARNESS.md`).

## Open

- The tank modulation depth's range (flattening after ~64 measured; the
  top half may do nothing) — the knob went 15 Sep 2026 and the depth is
  pinned at 30, so this is only reachable by changing the engine.
- An emulator-only divergence between one and two instances under a
  nonzero split.
- The R44 SIZE-turn kill, unreproduced (`docs/history/VOICING.md`).
