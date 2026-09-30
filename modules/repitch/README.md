# `repitch` — REPITCH

A fifth timestretch value, REPITCH: the track follows the project tempo by
playback speed, like a turntable.

`speed = project BPM / sample BPM`, without grains (Ableton's Re-Pitch). A
120 BPM loop at 120 BPM plays untouched; at 90 BPM it plays at 0.75, a
fourth lower and 4/3 as long; the change follows the tempo live. Pitch and
length move together; nothing is time-stretched. Released to the user as
**Octapitch v1.0** (`Octapitch_v1.0.bin` / `.syx`, version string
`OCTAPITCH`): the same MAIN OS as image 81, only the container's version
field differs. The firmware facts it stands on are
[`docs/firmware/REPITCH.md`](../../docs/firmware/REPITCH.md). Markers as in
`CHIP.md`: ✅ measured, 🟡 inferred.

## Knobs

REPITCH adds a value to two existing selects; it has no knobs of its own.

| page | slot | name | range | what it does |
|---|---|---|---|---|
| SRC SETUP (STATIC, FLEX) | 10 | TSTR | OFF AUTO NORM BEAT **RPCH** | RPCH (raw 4) puts the track on REPITCH |
| audio editor, ATTR | row 2 | TIMESTRETCH | OFF NORMAL BEAT **REPITCH** | the sample's own attribute; applies when SETUP TSTR is `AUTO`, as stock's NORMAL/BEAT do |

| raw | SETUP (STATIC/FLEX) | ATTR TIMESTRETCH | stock |
|---:|---|---|---|
| 0 | OFF | OFF | yes |
| 1 | AUTO | -- | yes |
| 2 | NORM | NORMAL | yes |
| 3 | BEAT | BEAT | yes |
| 4 | RPCH | REPITCH | new |

- **To the renderer it is OFF.** The voice renderer resolves REPITCH to 0
  and plays dry, forwards and in reverse; only the increment (and so both
  the pitch and the rate the sample is consumed at) carries the tempo.
- **PTCH is off.** The PTCH word is not applied (LFO and note transposition
  included) and the PTCH knob on the SRC page draws empty. RATE still
  applies (tape stops keep working).
- **Limits.** The speed is clamped to 2x, stock's own ceiling (PTCH +60).
  A sample without a tempo in the firmware's range (30..300 BPM, BPMx24
  720..7200) plays as stock. PICKUP is not offered REPITCH: its descriptor is
  untouched (a pickup buffer has no attributed tempo of its own, and stock
  forces pickups onto the grain path).
- **Storage.** Existing values keep their raw numbers, so saved projects
  load unchanged. Both the part (SETUP) and project.work (`TSMODE=4`) store
  4 verbatim (✅ the project parser at `0x40086c5a` does not clamp). A stock
  OS loading such a project sees an unknown value (🟡 SETUP: a blank value
  and granular playback; ATTR: `ERROR`).

## Measured

Playback under the port (`verify_repitch.py --project`, a generated 440 Hz
loop attributed 120 BPM, a live change to 90 BPM at frame 2000; ✅ 16 Sep
2026): the pitch from zero crossings, the SPEED from every write to T1's
sample position (voice `+68`), in frames per output sample.

| case | pitch Hz | speed | resolved | image 80 |
|---|---|---|---|---|
| stock-off (FLEX, OFF) | 440.05 -> 440.00 | +1.0007 -> +1.0004 | 0 | same |
| stretch (FLEX, NORM: the control) | 440.03 -> 440.01 | +1.0007 -> +0.7503 | 2 | same |
| repitch (FLEX, RPCH) | 440.01 -> 331.16 | +1.0007 -> +0.7503 | 0 | speed -> +1.0004, resolved 4 |
| auto (FLEX, AUTO + sample REPITCH) | 440.01 -> 331.27 | +1.0007 -> +0.7503 | 0 | speed -> +1.0004 |
| ptch (FLEX, RPCH, PTCH +24) | 440.03 -> 330.04 | +1.0007 -> +0.7503 | 0 | speed -> +1.0004 |
| static (STATIC, RPCH) | 440.01 -> 330.09 | +1.0007 -> +0.7503 | 0 | speed -> +1.0004 |
| reverse (FLEX, RPCH, RATE full reverse) | 440.04 -> 330.12 | -1.0007 -> -0.7503 | 0 | speed -> -1.0004 |

The stretch control is what makes the speed column mean something: a real
timestretch keeps the pitch and slows the position, REPITCH moves both, and
image 80 moved the pitch alone. The pitch readings sit up to 1.3 Hz off 330
where the port's block-boundary steps land on a zero crossing (a ramp loop
shows those steps at unity speed on OFF too); the speed does not see them.

- The resolution runs from `0x40007d96` to `0x40007dc0` on both images for
  TSTR 0..5, STATIC, FLEX and PICKUP and three previous values: the patched
  image with REPITCH equals stock given OFF, register for register
  (`ot_repitch_stock_test`).
- The increment check runs the builder from `0x4000406a` to `0x40004108` on
  both images for 9,000 combinations (two tracks, FLEX and PICKUP, TSTR
  0..4, TSMODE 0/2/4, sample tempos in and out of range, project tempos
  30..300 BPM, three PTCH and two RATE values): 8,520 are bit-identical to
  stock and 480 equal stock's neutral-PTCH increment x project / sample,
  clamped.
- PLAYBACK SETUP draws `OFF AUTO NORM BEAT RPCH` on the five-position icons
  for STATIC and FLEX; the PLAYBACK page drops exactly the PTCH dial for
  SETUP REPITCH and for AUTO with a REPITCH sample, and keeps it otherwise;
  the audio editor's ATTR page (`0x4006e450`) prints TIMESTRETCH 0/2/3/4/5
  as `OFF NORMAL BEAT REPITCH ERROR` (`verify_repitch_ui.py`).

What none of this sees: the LCD's pixels (the page tests capture text and
bitmap calls) and hardware timing.

## On the unit

- ✅ Image OCTABAM81 (16 Sep 2026, Sam's MKII), the third implementation:
  pitch and length follow the tempo, no stretch.
- Image 80 (the second) drew the panel right but pitched the sample while
  keeping its tempo, and sounded time-stretched: the voice renderer still
  moved the sample at the old speed (`docs/contributing/FAILURE_MODES.md`).
  The first showed a blank TSTR value.
- MKI: the same image, not yet run there. The MKI and MKII run one OS: the
  1.40C download we build from is the shared file (zip SHA256 `370c55a3…`,
  `FLASHING.md`), and its MAIN OS (SHA256 `164f3122…`) is the one octalab
  reads and runs on an MKI through this remixer's loader
  (`vendor/refs/octalab-notes`). What differs between the models is the
  panel: two keymap tables (`0x400bfbf6`, `0x400c01f4`) and which keys
  exist. REPITCH binds no key; its controls are the SRC SETUP page and the
  audio editor's ATTR page, reached the same way on both. 🟡 So nothing in
  it is model-specific; falsified by any difference on an MKI.

## Open

- Slices and the recorder buffers are not measured.

## Gates

- `python3 tools/verify/verify_repitch.py [REMIX]` (the manifest's gate,
  run by `make check` for a remix carrying REPITCH): the hook contracts,
  the page drawings, and with `OT_PROJECT` the playback cases.
- `out/emu/ot_repitch_stock_test [--patched IMAGE]`
  (`tools/harness/repitch_probe.cpp`, also under CTest): the stock facts
  in `docs/firmware/REPITCH.md` (the nine renderer readers among them), and
  on the built image every hook through the firmware's own code.
- `.venv/bin/python3 tools/verify/verify_repitch_ui.py`: the page drawings.
- `python3 tools/verify/verify_repitch_reference.py`: the offline
  variable-speed reference (not firmware).

## The patch

| site | what |
|---|---|
| `0x4000406a` `rate_gate` | resolves REPITCH for the track the builder is on (SETUP 4, or AUTO and TSMODE 4, not a PICKUP, with a tempo in range) and parks the sample's BPMx24 in d3 (free from the builder's entry to `0x40004176`) |
| `0x4000409e` `pitch_gate` | the PTCH word is replaced by neutral `0x4000` when d3 is set |
| `0x40004100` `rate_hook` | the finished increment x project / sample, exact (quotient and remainder), clamped to `0x08000000` |
| `0x40007d96` `tstr_resolve` | the renderer resolves REPITCH to 0: every renderer site takes OFF's path, forwards and backwards (stock's next line still makes a PICKUP's 0 a 2) |
| `0x4006e71c`, `0x4006ee56`, `0x4006ef7c` | ATTR TIMESTRETCH: `REPITCH`, BEAT -> REPITCH, REPITCH -> BEAT |
| STATIC/FLEX slot 10 | count 4 -> 5, formatter `tstr_fmt` (`RPCH`), widget -> `0x40046ab4` |
| STATIC/FLEX slot 0 | widget -> `ptch_widget`: the knob with value -1 on a REPITCH track (UI track `0x80000000`) |

## Retracted

- "STATIC/FLEX grow to five values, PICKUP from three to four" (first
  implementation): PICKUP is no longer touched.
- "The patched test executes all five formatter values": true, and it could
  not see the blank value, which is the widget's (`FAILURE_MODES.md`).
- "Full Flex playback at three tempos" validated the tempo each run loaded
  with, not a change while playing, and not the SETUP editor; both are
  covered now.
- "FLEX and STATIC on REPITCH measure 440 Hz before and 330 Hz after" (image
  80) as evidence that REPITCH played: the pitch was right and the sample
  position still advanced at 1.0, which the unit played as a timestretch.
  "After the change the tone shows the port's block-boundary glitches and
  level dips; a stock run pitched down by PTCH shows the same": the dips
  after the change were REPITCH skipping a quarter of every chunk. The
  port's own block-boundary steps are real (a ramp loop shows them at unity
  speed on OFF), which is what made the attribution look safe.
- "`0x40007ede` and `0x40008210` select the dry or grain path": they are two
  of nine sites that read the resolved TSTR.
