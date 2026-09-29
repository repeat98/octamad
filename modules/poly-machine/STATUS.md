# Poly Machine implementation status

Updated: 2026-09-25 (image 95, packaged as `POLY95`: an AMP envelope per
voice, a constant DSP rate on POLY tracks, POLY's own octave -2..+2. Images
93-94 are superseded; 92 must not be flashed)

This file is the engineering handoff for the `poly-machine` remix.

## Where it stands

`out/OCTATRACK_POLY95.bin` (card) and `out/OCTATRACK_OS1.40C_POLY95.syx`
(MIDI) are built from this tree, and `out/POLY95_OCTEMU/play.sh` boots the
same image in octemu on a card whose T1 is POLY with a tone loaded.
`make check REMIX=poly-machine` passes (@CHECK@). Not yet flashed.

## Image 95 (25 Sep 2026), measured under octemu

The user played POLY94 in the octemu window: the key boxes worked, but
"a lot of envelope artifacts, and the release of the amp doesn't get
respected -- we need an amp per voice, not fx per voice; extend the octave
range".

**Stock's AMP envelope, measured** (FLEX, TONE220 on T1, one chromatic key,
knobs turned with the encoders; poking the Part or the live lane does NOT
reach the DSP record -- the first sweep did that and changed nothing):

- It runs on the DSP, once per track, after the voices are summed. The
  ColdFire sends ATK/HOLD/REL/VOL/BAL/XVOL as record halfwords 0-5 and
  events in the command word `+0x3c` (`0x40004bd4`): trigger `0x80` (+ a
  sub-block offset in the low nibble), gate `0x40` (the DSP holds while it
  is set every frame), release `0x20`. HOLD is timed on the ColdFire: a
  timer from the trigger, `+ tempo24*16` per frame with SYNC on (2880*16
  off), against `0x400a9690[HOLD]` (HOLD 16 = 1.125 steps = 141 ms at 120
  BPM); 127 = INF. AMP page 2: mode ANLG/RTRG/R+T/TTRG (`+0x2a`), SYNC
  (`+0x2b`), attack curve LIN/LOG.
- Attack: linear, 0 -> full in 3.39 ms * 2^(ATK/8.39) (ATK 35: 61 ms, 51:
  ~240 ms, 67: ~0.9 s, 83: ~3.3 s, 99: ~12 s). Fit to 6 points; RTRG (the
  default) restarts from zero on every trigger.
- Release: exponential, time constant 0.337 ms * 2^(REL/8.64) (REL 48: 15
  ms, 64: 60 ms, 80: ~200 ms, 96: ~750 ms); 127 = INF (the level stays).
- HOLD also ends a HELD key: HOLD 16 and 32 released at ~145 and ~285 ms
  with the key still down. Release starts at the hold's end or key-up,
  whichever comes first.

**The artifacts, measured** with a click detector (the largest |second
difference| of the output within 150 ms of an event; a smooth tone gives
2-8). Walk: ATK 0, REL 64, hold C, add E, add G, release E, release C+G.

| event | POLY94 | 95b (DSP at unity) | 95c (+ no DSP retrigger) | POLY95 (+ ramped limiter) |
|---|---|---|---|---|
| E added to a held C | 1034 | 1783 | 4 | 3 |
| G added | 646 | 1878 | 263 | 5 |
| E released | 190 | 139 | 55 | 7 |
| C and G released | 518 | 3 | 3 | 3 |

1. **Releases** clicked because a released voice was cut (clr.b / stock
   stop). Each voice now has its own envelope (`.env_track`, `.env_voice`,
   the stock laws above as 128-entry tables); a released key's voices enter
   their release and `.env_reap` stops them at -78 dB.
2. **A new key made every sounding voice step.** The DSP resampled the whole
   track by the newest note's increment, and its trigger restarted the
   track's DSP processing under the voices still sounding. POLY now keeps
   the DSP at unity (`poly_increment_shift` stores the note's increment per
   voice and gives STATES+36 2^26), resamples every voice on the ColdFire
   (`.render_voice`; a voice that moves slots takes its phase and carried
   frames along), and while any voice sounds `poly_amp_hook` drops the
   trigger, its offset and the release from the command word and holds the
   gate; the record's ATK/HOLD/mode go to 0/INF/ANLG. MEASURED: with the
   trigger still passed (95b) the steps were larger; with it dropped (95c)
   they went. Whether unity alone was needed is not separated.
3. **Level jumps**: the sum was divided by 2 or 4 by voice count. Every
   voice now plays at unity and a limiter turns the sum down only where it
   would clip, its gain ramped across each chunk (a per-chunk step clicked:
   the 263 and 55 of 95c).

MEASURED also: E fades by its REL after its key-up (-23 dB at 200 ms, REL
64) while C and G hold; the envelope states at every step (gdb) match;
POLY octave -2 plays TRIG1 at 28.3 Hz (27.5 expected; 1.7 Hz FFT bins).

**Octaves**: POLY keeps its own octave (`poly_octave`, -2..+2, 0 = stock's
octave 0) instead of walking stock's 0x460d16fc (a stock track left at
octave 2 by images <= 94 played only TRIG1: stock rejects keys above 24).
The keyboard prints it signed (`0x400449b8`), the page lamps show it
(`0x4004d442`: stock indexes two 8-entry stack arrays by 2*octave, which
is why octave 4 hung image 92), and each trig remembers the key it pressed
so its release matches after an octave change. With the DSP at unity a
voice's own fetch sets the ceiling: 16 frames at 5.75 fit poly_fetch, about
+30 semitones (was +24).

**CPU** (ColdFire port, `benchmark_polyphony.py`: 8 tracks x 4 looping
voices, sequencer trigs on steps 1-4, all at the sample's own pitch):

| build | instructions / 16-sample frame | vs stock mono (42,539) | frames on time |
|---|---:|---:|---:|
| POLY93 | 65,808 | 1.55x | 736 of 1,399 |
| 95d, every voice through the resampler | 76,056 | 1.79x | -- |
| POLY95 (fast paths) | 65,228 | 1.53x | 684 of 1,399 |

"Frames on time" is the port's count of ColdFire frames delivered exactly
16 DSP samples apart (stock mono: 1,354 of 1,399, spread 14-17; POLY 15-23).
95d's load made the port's sequencer late enough that the fourth trig missed
the 1,400-frame window (the benchmark's allocator check failed: 16 of 24
extensions); POLY95's fast paths -- a voice at exactly the DSP's rate is
fetched straight into place, a voice held at unity is added without a
multiply, one voice alone at unity is copied -- bring the untransposed case
back to POLY93's cost. The 95d figure is the measured cost when every voice
is transposed (every voice resampled). A PTCH override of the fixture meant
to measure that on POLY95 did not take (counts identical); not re-run.
These are port instruction counts, not hardware cycles.

## Image 94 (25 Sep 2026), measured under octemu

The user played POLY93 by hand in octemu and reported no polyphony and no
multiple key marks. Two separate causes:

1. **The play card booted T1 as FLEX** (Part machine byte 1, screen
   `SRC>FLEX`), and POLY engages only once SRC SETUP commits POLY. Replayed
   with human timing (TRIG1, +30 ms TRIG5, +40 ms TRIG8) on that card: FLEX
   gave one voice; after SRC SETUP -> POLY -> TONE220 the same chord gave
   three voices, 110 / 138.6 / 164.8 Hz within 1 dB. Not a code defect; the
   new package boots on POLY.
2. **POLY drew no key box at all** (a code defect, fixed). The keyboard draw
   `0x40044920` boxes one held key per track from `0x460d171d[t]`, which
   POLY's key handler never set. `poly_kbd_fill` / `poly_kbd_next` point the
   draw loop at a list of eight entries per track: stock's byte for other
   machines, every held key for POLY.

| step (T1 POLY, TONE220, T2 selected for MIDI) | result |
|---|---|
| TRIG1 / +TRIG5 / +TRIG8 held | 1 / 2 / 3 boxes, on C, E, G |
| release TRIG5 | boxes on C and G; 138.6 Hz at -97 dB, 110 and 164.8 Hz held |
| release all | no box; silence (-6 dB RMS, int16) |
| MIDI ch 1: 72, 76, 79 in ONE packet | 3 voices owned by 72/76/79, 110 / 138.6 / 164.8 Hz within 1 dB |
| MIDI note-off 76 | its voice stops (-97 dB); gate bit stays set |
| MIDI note-off 72, 79 | all voices off, held set empty, gate bit clear, silence |
| MIDI legato 72 -> 76, then off 72 | 76 alone (72 at -95 dB) |
| MIDI note-on 76 velocity 0 | released like a note-off; a ~0.2 s tail at -32 dB, then silence |

Also in 94:

- **MIDI chromatic notes** (`0x4000e746` note-on, `0x4000dfd4` note-off)
  press and release POLY keys through the same path as the panel: owner
  `0x80 + note`, queued behind a busy mailbox, each note-off stops the voices
  its note owns; the gate bit clears and stock's release posts only when the
  track holds no key.
- **Races closed**: presses and releases run with interrupts masked (stock's
  idiom at `0x40006844`), and the armed key is written BEFORE the trigger
  command. Image 93 wrote the command first, so a frame landing between the
  two writes took a command whose owner was not written yet (inferred from
  the code; a window of a few instructions, never observed).
- **A queued or armed press released before it played** is dropped or
  withdrawn (stock's note-off overwrites the command the same way), instead
  of playing later with no key to stop it.
- **Stock parity on the panel**: AUDIO NOTE OUT sends each key's note on/off
  (`0x4003f3a8`, key + 72); a press with `0x8000004c` bit 0 clear (INT off)
  triggers nothing; stock's release-held routine (`0x40043728`, track and
  mode changes) releases every panel key held on a POLY track
  (`poly_release_held`). The last two are read from the code, not exercised.
- `tools/hw/ot_spec.py` names machine 5 POLY.

## Image 93 (22 Sep 2026), measured under octemu

With the uncached-alias fix below, walking a fresh card on which T2 starts
as STATIC:

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
- The per-voice AMP models ATK/HOLD/REL/SYNC only: the AMP mode
  (ANLG/RTRG/R+T/TTRG) and the LOG attack curve are not modelled (every voice
  starts at zero, linear). The laws are fits to octemu measurements of the
  DSP's envelope, not read from the DSP code; tempo scaling of ATK/REL with
  SYNC on was not tested (measured at 120 BPM).
- While a POLY track sounds, a new note does not retrigger the DSP's track
  processing, so an FX envelope (FILTER ENV) restarts only on a note from
  silence.
- Every voice, the newest too, is resampled by linear interpolation on the
  ColdFire; aliasing at large upward transpositions was not measured.
- The limiter engages only when the voices' sum would clip; its pumping on
  loud chords was not listened to.
- Live recording of panel chromatic keys on a POLY track: POLY's handler
  returns before stock's recorder calls (`0x40042d1c`, read from the code).
- The track-side glyph for a POLY track reads `M` (F for FLEX, S for STATIC):
  an out-of-range letter lookup, cosmetic, not located.
- The second chooser copy (`0x40077a9c..`, hooks `poly_sample_ui_*`) is
  reached from some entry path other than SRC SETUP; that path was not
  identified or exercised.
- More than four presses in one control scan: the fifth and later are
  dropped (queue of three behind the mailbox).
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
- **The keyboard draw runs on redraw events, not continuously**: a read
  watch on `0x460d171d` armed 300 ms after a press saw no read in 3 s. A
  quiet watch there says nothing about the draw.
- **Headless octemu cannot `panelshot`** (it needs the window's skin); use
  `screenshot` (the 128x64 display).
- **MIDI into octemu**: `--midi` creates the CoreMIDI port `Octatrack
  Emulator In`; a small CoreMIDI sender that waits on `[mark]` lines in the
  log drove the 25 Sep tests (not in the tree; 60 lines of C).
- **Another session's build can replace `out/mainos_bus.bin` mid-test**
  (happened 20:33): copy the image aside before emulating it.

## Useful commands

From `/Users/jannikassfalg/coding/octamad`:

```sh
make check REMIX=poly-machine
make image REMIX=poly-machine BUILD=94 VERSION=POLY94
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
