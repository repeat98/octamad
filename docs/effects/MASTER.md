# The master (14 Sep 2026; the return left it 20 Sep 2026)

What track 8 does, in what order, with which knobs. The bus and where its
wet comes out:
`docs/effects/XBUS.md`; the chain line by line:
`modules/character/character.asm`; the listening log:
`docs/history/VOICING.md` (git history, `git show 3ceba41:docs/history/VOICING.md`). ✅ measured on the unit, 🟡 measured under the
port or the harness only, ❓ inferred.

## The shape

```
T1..T7  ──(AMP VOL, BAL)──▶ FX1 station ──▶ FX2 = SEND, one SEND knob ──(LEVEL)──┐
                                                                                 │  the mix
T1 FX2 = DELAY SERVER: T1 prints dry + repeats ─ chain ─▶ T5 FX2 = REVERB SERVER: T5 prints dry + tail
                                                                                 │
T8 (MASTER TRACK on)  ◀──────────────────────────────────────────────────────────┘
   FX1 = CHARACTER:  FOLD ▶ TXTR ▶ SAT ▶ TONE ▶ COMP (GLUE by position) ▶ WDTH ▶ MIX
   FX2 = nothing (the SEND is refused on T8: its input is the mix)
```

- **T8 is the master.** With MASTER TRACK on, T8's effect chain sees the
  sum of the other tracks' outputs after their LEVEL (✅ O9d/O14 under the
  port: T8's chain input equals T1 + T2 summed; AMP VOL and BAL are pre-FX
  on each track, LEVEL is post-FX at the mix).
- **One aux send per track**, the SEND knob at slot 0 of every track's FX2
  (the ordinary tracks run SEND there; T1's FX2 is the delay engine and
  T5's the reverb engine, and both still have their SEND knob). The delay's
  output feeds the reverb (✅ flash 7).
- **Each engine's wet comes out on its host** (20 Sep 2026): T1 prints its
  dry + the repeats × WET, T5 its dry + the tail × WET, each under that
  track's LEVEL, mute and scenes, and the master hears both as ordinary
  tracks. A host adds the wet in place after its own send tap, so a host
  never sends its own wet; T8's send stays refused (its input is the mix,
  the hosts' wet included). From 7 to 20 Sep 2026 the wet returned instead
  through Character's RET on T8, in front of the chain, with the hosts
  stamped quiet and the send refused on T8 (✅ flash 7); on image 35 that
  return was degraded on the unit and clean under the port
  (`FAILURE_MODES.md`), and it went.
- **The stations on T1–T7** (Character on T1, Spectrum on 2/3/4/6/7,
  Modulation on 5) are ordinary inserts; Spectrum is the filter pedal since
  14 Sep 2026 (SEM LP/BP/HP, Capacitor2, formants, the Moog ladder; ENV and
  LFO onto the cutoff; width); their defaults are a bit-exact
  passthrough under the harness (🟡 — on the unit they appear to run LIVE
  at the stamp, ❓ the page-2 publish; harmless for the sound since 14 Sep,
  see below).

## The stamp (`ot_project.RIG`, `ot_ladder` bank G)

| track | FX1 | FX2 |
|---|---|---|
| 1 | CHARACTER, defaults | DELAY SERVER, SEND 30 |
| 2, 3, 4, 6, 7 | SPECTRUM, defaults | SEND, SEND 40 / 30 / 40 / 50 / 40 |
| 5 | MODULATION, defaults | REVERB SERVER, SEND 40 |
| 8 | CHARACTER, COMP 40 (GLUE by position) | — (the send is refused on T8) |

Stamp every project for the current remix before play
(`tools/hw/ot_project.py stamp-defaults`); a part saved under an older slot
layout feeds the new layout its old bytes.

## Character on the master, knob by knob

Page 1: DRV, FOLD, TXTR, COMP, TONE, MIX. Page 2: SAT, WDTH, —, —, —, —
(16 Sep 2026: MIX bottom right, SAT top left; page-1 slot 4 was RET from
13 to 20 Sep 2026 and is TONE again).
The chain runs in the fixed order drawn above, distortion before dynamics.
Every stage holds its level as its knob rises (the tape lifts about +2 dB
by 127, by ear).

- **DRV / SAT** — DRV 0 is bit-exact, no saturation stage at all. SAT picks
  TAPE (JClones TapeHead), TUBE (DaTube) or INFL (OInflator). ✅ TAPE's
  drive law voiced live: unity plus a gentle lift ("drv sounds great").
- **FOLD** — WarpFold's wavefolder, 1× to 48× into the fold at a held level.
- **TXTR** — Airwindows Pockey, the 12-bit sampler texture: 0 off, up moves
  its bit-depth and rate sliders together, 12-bit µ-law and a 27 kHz hold
  at the bottom of the travel, 2 bits and 3.5 kHz at the top. 🟡 proven
  against the transcription, unheard.
- **TONE** — a tilt after the saturator in every mode, drawn −64..+63: 0
  flat and bit-exact, + bright, − dark: +3.5 dB above / −6 dB below the
  1.2 kHz pivot at 127, the mirror at 0 (the tilt's own law).
- **COMP** — JClones AC1's console channel law: `Lv = K × level`; `gr =
  (Lv²/2 − 1)² + a·Lv` clamped at 1 — a dip around Lv = 1 whose depth is
  `a = 0.75 − 0.675·COMP/128`; makeup `1 / (1 − 0.3375·COMP/128)`. GLUE
  (0.5 / 500 ms, K = 3) on the master BY POSITION, COMP (0.5 / 63 ms,
  K = 4; the release coefficient is 3024/2^23, written as 50 ms until 21
  Sep 2026) on every other track; no knob for it. MIX 127 is 127/128. COMP 0 skips the stage
  bit-exactly. The stamp is 40. ✅ On the unit (image 8): COMP 40 / 80 /
  127 keep both channels within 0.6 dB of each other.
- **WDTH** — mid/side, drawn −64..+63: 0 untouched, −64 mono, +63 double
  the sides.
- **MIX** — out = x + MIX·(w − x); 127 in the stamp.

## Dirty state (13–14 Sep 2026)

"The master compressor collapses the RIGHT channel above COMP 40" was
Spectrum's filter B: its two HP poles were not cleared at init and stayed
frozen at the passthrough stamp, so `hp2 = yB − h2` subtracted a stale value
from every sample, up to a full-scale DC on that track's output; the
master's makeup clipped DC + audio to a constant on one channel. An
AC-coupled capture cannot see DC. ✅ Localised on the unit by track LEVEL
(post-FX mute cleared it, pre-FX mute did not), reproduced under `dsp_host`
with the block pre-filled with garbage, fixed by zeroing every persistent
slot at init in Spectrum, Modulation and Character (PR #246), confirmed on
image 8. `tools/verify/verify_dirtystate.py` (in `make verify`) renders
every module of the remix from a garbage-filled instance block on silence,
at its defaults and with every knob nudged, and refuses any output. The
unit's RAM is never zeroed; the port and the harness always are.

## Open, as of 14 Sep 2026

- 🔴 A diagnostic image whose Character was 189 words shorter silenced every
  bank with stations on the unit while the port played them; padding the
  module back to the known placement plays. Placement, cause not bisected
  (`FAILURE_MODES.md`, "A diagnostic image silenced every bank").
- ❓ The stations run live at the passthrough stamp on the unit (the port
  bypasses them). Costs cycles, not sound; the pricer already charges the
  live price.
- 🟡 The audio engine wedged once with only BusVerb + the T8 return (one
  freeze in ~15 minutes on 13 Sep); cause open, the return gone since 20
  Sep 2026 (`FAILURE_MODES.md`).
