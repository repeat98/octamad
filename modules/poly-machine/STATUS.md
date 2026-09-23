# Poly Machine implementation status

Updated: 2026-09-22 (image 93, packaged as `POLY93`. Image 92 / `POLY92`
had two bugs found by hand in the emulator -- a chord pressed all at once
played one note, and FUNC+RIGHT past octave 3 hung the UI -- fixed in 93;
do not flash 92)

This file is the engineering handoff for the `poly-machine` remix.

## Where it stands

`out/OCTATRACK_POLY93.bin` (card) and `out/OCTATRACK_OS1.40C_POLY93.syx`
(MIDI) are built from this tree; the packed `mainos_bus.bin` was compared byte
for byte with the image every result below was measured on (0 bytes differ).
`make check REMIX=poly-machine` passes (357 PASS, no FAIL). Not yet flashed.

Measured under octemu (with the uncached-alias fix below), walking a fresh
card on which T2 starts as STATIC:

| step | result |
|---|---|
| SRC SETUP: cursor to POLY, YES | Part machine byte 0 -> 5 |
| RIGHT | slot list opens (`<<FLEX`, recorder buffers, slots) |
| RIGHT, pick `TONE220.WAV`, YES | loads into T2's FLEX slot 2; slot row reads `2 TONE220` |
| NO, NO | main page `SRC>POLY`, track box `POLY`; Part byte still 5 |
| FUNC+DOWN, DOWN, release | trig mode 1 (CHROMATIC), keyboard shown |
| hold TRIG1, +TRIG5, +TRIG8 | 1, 2, 3 active voices; spectrum 110 / 110+139 / 110+139+165 Hz, each within 1 dB |
| release TRIG5, TRIG1, TRIG8 | exactly that key's voice stops each time; silence at the end |
| FUNC+RIGHT x2 | TRIG1 = 110, 220, 440 Hz; the walk wraps 2 -> 0 |
| T1 (POLY from boot): TRIG1+5+8 pressed at once | three voices, 110/139/165 Hz; all off after release |
| back to TRACKS, grid trig step 1, PLAY | sequencer trig sounds at 220 Hz (no leftover octave shift); retriggers stack into extensions |
| FLEX control, same walk | stock: TRIG1 = 110 Hz (POLY's mapping matches), one voice, sequencer fine |

Resampler quality: off-band energy (all energy outside +-4 Hz of each tone
and 6 harmonics) about -60 dB with 2-3 voices, against -61 dB for the stock
voice alone; <= -67 dB above 2 kHz, so no chunk-seam hash.

CPU (ColdFire port, `benchmark_polyphony.py`, 32 voices at one pitch):
65,808 instructions / frame, 1.55x stock mono (was 59,768 / 1.40x before the
resampler). Wide chords cost more; not measured.

## Fixed in images 92-93 (each found and verified under octemu, 22 Sep 2026)

1. **RIGHT on the POLY row did nothing.** SRC SETUP is its own copy of the
   chooser (state `0x460d5c28` list / `0x460d5c30` cursor / `0x460d1a48`
   pane); its RIGHT handler is `0x4003d1c0` and it opens a slot list only for
   cursor 0/1. The existing `poly_sample_ui_*` hooks patch the OTHER copy
   (`0x40077a9c..`, state `0x460e73xx`), which SRC SETUP never runs. Nine
   six-byte cursor reads now see FLEX for POLY (`poly_src_cursor_*`); the
   two commit sites (`0x4005a616`, `0x4005a850`) keep writing raw 5. Writing
   FLEX into the cursor instead (the old hooks' approach) would have turned
   the track FLEX on the first sample assignment.
2. **Default TSTR AUTO made POLY mono.** The render hook falls back to one
   voice when lane byte 28 (TSTR) is non-zero. `poly_config_tstr`
   (`0x4000c140`) forces the live TSTR to OFF for POLY after the config walk
   copies the six SRC SETUP bytes to `0x80000830 + 72*track`.
3. **Every held voice played the newest pitch.** The renderer does not
   resample: it fetches raw source frames (count derived from the primary's
   increment by the caller at `0x40004108..`) and the DSP resamples the track
   once. Swapping `STATES+36` during an extension render (the old
   `.select_increment`) changed nothing the renderer reads. `.render_ext` now
   fetches each extension's own frame count and linearly resamples it to the
   primary's source rate (Q16 ratio, 1-2 carried frames, phase in [0,1)).
   The increment each extension keeps is `STATES+36` read at the
   initializer. MEASURED order within a frame (breakpoints, image 93):
   consumer (chord dequeue) -> initializer -> increment recompute -> render,
   so it still holds the OLD note's increment there. RETRACTED: image 92
   claimed the initializer already saw the new note's increment (inferred
   from the all-one-pitch symptom, whose real cause was the shared DSP
   resampler) and took the increment from the last render instead; with keys
   pressed together the next note triggers before the previous one is
   rendered, the saved increment was 0, and that voice played DC forever.
4. **The octave shift never reached the DSP** (same dead path).
   `poly_increment_shift` (`0x40004100`) applies it where the builder
   recomputes the increment, capped below 4.0 (63 frames per chunk).
5. **A chromatic note left the track deaf to the sequencer for good.** The
   press's command (0x1d, bit 8 clear) sets the track's bit in the frame
   consumer's live-played mask `0x46c7e9f8`; stock clears it with bit 6 on
   the release. The POLY release now posts bit 6 once the track's last key is
   up. The primary also stops through stock's `0x40006820` now, not a bare
   `clr.b` (that left `STATES+4` and the generation counter behind; it was
   not the deafness cause -- measured -- but it was wrong).
6. **Stale key/shift on non-chromatic triggers.** A press's key and shift are
   consumed by the trigger it causes (0xff = no key); note tables start at
   0xff so key 0 no longer matches empty slots.
7. **A chord pressed all at once played one note, and left a voice stuck**
   (image 92, found by hand). Presses in one control scan go through the
   chord queue, and the queue's re-arm runs between the consumer taking a
   command and that command's trigger, so it overwrote the key/octave
   side-channel of the note about to start. Now two-stage: presses and
   re-arms write `poly_armed_*`, the consumer promotes them to
   `poly_pending_*` when it takes the track's command, the trigger consumes
   those. Measured: three keys at once on T1 -> 110/139/165 Hz within 1 dB,
   keys filed 0/4/7, every voice off after release.
8. **FUNC+RIGHT past octave 3 hung the UI** (image 92, found by hand). The
   stock chromatic LED routine (`0x4004d47e`) writes two 8-entry stack
   arrays at `2*octave` and `2*octave+1`; octave 4 smashes its stack. POLY's
   walk was 0..10; it is 0..2 now (the pitch cap makes higher octaves
   repeat anyway). Measured: 0->1->2->0..., UI alive through a track switch.

## Open

- Hardware: nothing above has run on a unit. CPU headroom with wide chords
  on eight tracks is the first thing to watch (see README).
- The track-side glyph for a POLY track reads `M` (F for FLEX, S for STATIC):
  an out-of-range letter lookup, cosmetic, not located.
- The second chooser copy (`0x40077a9c..`, hooks `poly_sample_ui_*`) is
  reached from some entry path other than SRC SETUP; that path was not
  identified or exercised this session.
- MIDI chromatic play is stock (one voice).
- More than four presses in one control scan: queued presses released before
  they play are not matched.
- An extension keeps the pitch it was stolen with (no PTCH/LFO follow).

## ☠ Instrument notes (octemu), all measured

- **octemu mapped the uncached SDRAM alias as separate memory** (fixed,
  uncommitted, in the octemu tree: `src/board/ot-board.c` 128 MiB + alias at
  `0x48000000`). Without it every DRAM runtime detour jumps into zeros; the
  build 83->87 bisect and "these hooks stall track switching" were artefacts
  of that and are retracted.
- **QEMU does not step over a Z0 breakpoint on continue**: a naive logger
  re-hits the same address. Remove, `s`, re-insert.
- **`0x400041c4` (render) and `0x4000b7bc` (chord dequeue) are not reached
  with no voice playing**: a breakpoint there that never fires on an idle
  unit is not evidence of anything. The earlier "RIGHT handler breakpoints
  never fire" was true but pointed at the wrong handler copy.
- **Scripted "simultaneous" presses are not simultaneous**: consecutive
  `press` steps land in different control scans, so they never exercised
  the chord queue that a real keyboard hits. Two POLY bugs hid behind this.
- **octemu with `--gdb` does not run freely until a debugger attaches**;
  attach early and continue. `--unthrottled` did not shorten walks here.
- **Script step arguments are capped at 96 characters** (`src/script.c`
  `Step.arg`): long screenshot paths are silently dropped.
- **Gestures**: chromatic mode = FUNC+DOWN (popup) then DOWN; octave =
  FUNC+LEFT/RIGHT; SRC SETUP knobs need several detents per step
  (`"times":8`); SRC SETUP reopens in the pane it was left in.
- **Another session's build can replace `out/mainos_bus.bin` mid-test**
  (happened 20:33): copy the image aside before emulating it.

## Useful commands

From `/Users/jannikassfalg/coding/octamad`:

```sh
make check REMIX=poly-machine
make image REMIX=poly-machine BUILD=93 VERSION=POLY93
python3 tools/harness/benchmark_polyphony.py --project <dir> --image <bin> \
  --work out/polyphony-benchmark-<n>
```

From `/Users/jannikassfalg/coding/octemu` (a card with samples in the set's
AUDIO pool: `scripts/card.py copy <card> <wav> "/Set 260922/AUDIO/<NAME>.WAV"`
on a copy of `out/fx/card.img`):

```sh
./octemu --headless --cf-card <card> --nvram <nvram> --os <image.bin> \
  --script <walk.jsonl> --timeout 400 --gdb <port> --recording <x.wav>
```
