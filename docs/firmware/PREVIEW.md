# Sample previews

How OS 1.40C plays a sample preview ([FUNC] + [YES] to the main outputs,
[CUE] + [YES] to the cue outputs, from the Flex/Static slot lists, the file
browser and the audio editor), and what `modules/previewvol/` changes. Read
from `out/raw/section_3_MAIN_OS.bin` (SHA256 `164f3122…`, base
`0x40000400`) and run under the ColdFire port, 16 Sep 2026. Markers as in
`CHIP.md`: ✅ measured, 🟡 inferred.

## What the user sees

A preview plays through the **active track**: its FX (unless PERSONALIZE →
PREVIEW WITHOUT FX), its levels. Stock also forces most of the track's
playback: the SRC page neutral and the AMP envelope. It does **not** force
AMP VOL, so a track turned down on the AMP page previews quietly or not at
all. With PREVIEW VOL, previews play at the AMP descriptor's default VOL
(64, shown as 0) on every track.

## The ground

**Starters.** Two routines start a preview on track `t` (✅ port):

| routine | machine it previews as | args | callers |
|---|---|---|---|
| `0x400940ac` | STATIC (sets the track's machine byte to 0) | track, slot, start, loop, no-FX | the main-task message 49 (`0x40062412`) |
| `0x40096c54` | FLEX (machine byte 1) | track, slot (0..135), start, loop | `0x4006dd0c`, `0x400738de`, `0x40076852`, `0x400793e8` (the audio editor among them) |

Their stops are `0x40093e9c(track)` (🟡 entry read, not called) and
`0x40096ab0(track)` (✅ called). Both stops
end in `0x40001f18(bank, part, track)`, which rebuilds the track's live
values from the part (✅ port: AMP VOL comes back).

**The pending record** `0x46c7dfda + 32·t` (✅ port): per-track bytes in the
order SRC 0..5, LFO 6..11, AMP 12..17, FX1 18..23, FX2 24..29; `0xff` means
no change. A per-frame routine (🟡 the `0x4000e702` region) copies the other bytes
into the live values at `0x80000810 + 72·t` (same order; page 2 at
`0x80000830 + 72·t`, `PARAM_PAGES.md` §5b) and resets them to `0xff`. Both
starters queue:

| bytes | stock value | what |
|---|---|---|
| +0..+5 | 64, start, 0, 127, 0, 127 | PTCH, STRT, LEN, RATE, RTRG, RTIM |
| +9..+11 | 0 (no-FX only) | LFO depths |
| +12, +13, +14 | 0, 127, 32 | ATK, HOLD, REL |
| **+15** | **not written** | **AMP VOL** |
| +16, +17 | 64, 127 | BAL, XVOL |

and clear the lock/modulation longs `0x80000c34 + 32·t` for those groups
(🟡 read, not run). Page 2 is forced too (`0x80000830 + 72·t`: LOOP from the
loop argument, SLIC, LEN 0, RATE 0, TSTR 0, TSNS 64).

**Cue routing.** The starters do not know main from cue. [TRIG] + [CUE]'s
handler (`0x40043e00`, ✅ read) sets the track's cue bit (16 + t) and mute
bit (8 + t) in `0x80000008` while held and restores both on release; the
mixer record builder (`0x40004db8`) then gives the track a main gain of 0
and its cue level (`0x80000c62 + 4·t`) as cue gain. 🟡 The slot-list
[CUE] + [YES] uses the same bits (its handler is not located). Either way
AMP VOL is applied in the voice, before the routing.

`0x80000008`: bits 0..7 solo, 8..15 mute, 16..23 cue (`TRACK_CUE_MASK` is
byte `0x80000009`). `0x80000036` is the MIXER CUE level, `0x800000b0` the
PREVIEW WITHOUT FX setting.

**Measured under the port** (a generated 440 Hz loop on slot 1, T1, no
trig, the starter called at frame 300):

| image | T1 AMP VOL 0 | 64 | 127 |
|---|---|---|---|
| stock / Octapitch 1.0, FLEX | silent | RMS 517,600 | 2,038,187 (+11.9 dB) |
| stock / Octapitch 1.0, STATIC | silent | 510,725 | 2,011,117 |
| PREVIEW VOL, FLEX | 515,375 | 515,375 | 515,375 |
| PREVIEW VOL, STATIC | 513,054 | 513,054 | 513,054 |

(The two runs' windows differ slightly: 517,600 and 515,375 are the same
level measured over different spans.)

## The patch (`modules/previewvol/`)

| site | what |
|---|---|
| `0x40094296` `vol_static` | STATIC starter: the displaced REL write, then `move.b #64,15(a0)` |
| `0x40096eb2` `vol_flex` | FLEX starter: the same |

The preview's AMP VOL is then queued like the other AMP bytes and undone by
the same stop. FUNC+YES and CUE+YES both change (the user's choice); the
track's MAIN and CUE levels, its FX and the MIXER volumes still apply.

## Tests

`python3 tools/verify/verify_previewvol.py [REMIX]` (in `make verify`):
the two hooks, and with `OT_PROJECT` the port cases (FLEX and STATIC at VOL
0/64/127, a FLEX stop restoring VOL 0, and the stock OS as the control).
The port's `--call` takes several `;`-separated calls with one
`--call-at` frame each, which is how the stop is driven.

What none of this sees: the panel (the port has no keys; the starters are
called directly) and hardware timing.
