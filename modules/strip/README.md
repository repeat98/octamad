# MASTER STRIP

Two insert slots on the summed MAIN, run inline after payload A's mixdown: the master strip
of `docs/proposals/MIXER.md` (step 2, §11 to §13). Which effect each slot runs and its
knobs come from a model on the ColdFire, `strip_model`, which the MASTER page of the MIXER
window edits and each Part stores (below); a Part nobody has written gives OXIDE on slot 1
at its 0 dB points (IN 48, OUT 80) and slot 2 empty. The main out, the recorder and USB audio (stock's pack) and the
phones' MAIN share all hear the slots; the metronome click, which stock adds to MAIN after
the pack, is added after them and is not processed.

## How it runs

- **At boot** (a `jsr` over P:0x40, the first instruction after the upload) it zeroes the
  strip's block, starts slot 1 at OXIDE (its init, on slot 1's instance block) with IN 48 /
  OUT 80, then replays the displaced instruction. The unit's RAM is not zeroed, so nothing
  here trusts what X held before.
- **Head, every frame** (a `jsr` over P:0x2d5, MIXER SEAM's site): gathers MAIN's 16 dry
  pairs, runs slot 1 then slot 2 on sample 0 only and puts it back in the TX ring. Stock's
  tail (the pack, the click, the gain ramp, the cue mix into the phones) then writes
  sample 0 about as early as stock does: the output DMA reads it about half a sample after
  the mixdown.
- **Tail, every frame** (a `jsr` over P:0x35d, after the cue mix): samples 1..15 in order,
  both slots on each. The click is the ring's MAIN minus the dry sample; MAIN becomes the
  slots' output plus the click; the phones are recomputed with the cue mix's own gains;
  then stock's pack routine runs again on the processed samples, so the recorder and USB
  audio get them.
- **The record, every frame.** `strip_xport.s` takes the host-transfer chain's state 3
  entry (`0x400ab626`): before stock's core 0 block it packs `strip_model` into 32
  halfwords (a magic, per slot the FX id and its twelve knob values, a checksum) and sends
  them to core 0 as one more 64-byte burst. The block lands in the bank the DSP works in
  the next frame, and the tail's last step takes it: only when the magic and the checksum
  hold (the bank holds garbage until the first burst), every value masked to 0..127, the
  page-1 knobs to the slot's record as `v << 16` and page 2 packed two a word, as the stock
  dispatcher hands a track's knobs over. A slot whose id changed gets the new effect's init
  and proc; an id that is 0 or not on the strip's list leaves it dry. The list is OXIDE
  (`0x1f`). A knob reaches the samples of the frame after the record lands.
- The slots reach their effects through the stock dispatch tables by FX id, as a track slot
  does, with the track slot's contract (r0 the pair, n0 = 1, r6 the record, r7 the
  instance block, n7 = 1). The strip needs OXIDE in the remix (`requires`); OXIDE also
  stays in the FX chooser.
- Every register the bodies write that stock might read afterwards is saved and put back.
- Its state and records are at X:0x7c00..0x7cff, the slots' instance blocks at 0x7d00 and
  0x7e00 (`boot.asm` has the map); the record lands at X:0x3c80 or 0x5c80. None of them is
  written by anything else under the port on the user's project.

## The MIXER pages

`strip_ui.s` pages the MIXER window, in the layout Jannik locked on 29 Sep 2026:

- **LEFT / RIGHT** walk the strips: MIXER (the stock page, with a ▶ in its title band)
  and MASTER (◀). **UP / DOWN** walk MASTER's slots, INS 1 and INS 2. While the MIXER
  is open the arrow keys are the pages', so LEFT / RIGHT no longer nudge the tempo there.
- **MASTER** keeps the window's frame and the MUTE band (the trigs mute, FUNC works) and
  redraws the boxes above the band as two: MAIN as a number over a speaker, and the slot,
  its name down the side and its effect's six page-1 knobs as numbers, named and printed
  by the effect's own descriptor.
- **A–F** turn those knobs in `strip_model`, with a stock MIXER knob's step, held inside
  each parameter's range; **LEVEL** turns MAIN (the stock handler of A on the MIXER page).
  An empty slot, or a knob the effect does not draw, is an empty cell and turns nothing.
  The edit reaches core 0 in the next frame's record.
- **YES** on MASTER opens the slot's SETUP, "INS 1 SETUP" or "INS 2 SETUP", drawn as
  stock's EFFECT 2 SETUP: the strip's list on the left (NONE and the effects core 0 runs
  on the strip, OXIDE for now), the slot's effect inverted and a cursor that **UP / DOWN**
  move and **YES** takes; on the right the effect's page-2 knobs, which **A–F** turn,
  lifting to show their value as stock's do. YES on an effect puts it on the slot with its
  descriptor's defaults. **NO** closes the SETUP onto the MASTER page. It opens one window
  level above the MIXER, which stays open under it (MIXER.md §14).
- Three detours in the stock window: the opener's layer push (ours goes on top), the
  close's layer pop (ours come off first, the SETUP's with them) and the draw's entry
  (the stock draw, then the page, then the SETUP when it is open), so every stock redraw
  (a knob, a mute, FUNC, the knobs' lift) redraws the page too. The window reopens on
  MIXER.

Why split: the first version ran all 16 samples at P:0x2d5, and under the port the phones'
first sample of every frame went out two frames stale, because the pass held stock's cue
mix back past the DMA (MIXER.md §11).

## The Part keeps it

Each Part window carries the two slots, 32 bytes at bank + `0x904e2`: the audio LFO
designer's shapes **T7 and T8**. A slot is stored as `strip_model` holds it but for its
spare bytes: a tag (`0x53`), the checksum byte (the sixteen sum to 0 mod 256) and a version
(`1`). The Part is the truth, `strip_model` its cache: once a frame `strip_sync` reads the
window of the part the panel edits, and a window that differs from the one adopted and has
held for two frames becomes the model (both slots valid; otherwise the boot default). So a
part change, a bank change, a Part Reload and a project load follow with no hook of their
own. Each of the page's three edits calls `strip_store`: the window, the part's SRAM twin
and the marks stock's editors set (the Part's asterisk, the edited words). Costs, from
the image and the project (MIXER.md §15): no byte of a Part is spare, so a project that
chooses DSGN T7 or T8 on an LFO plays the strip's bytes as its steps, and drawing a shape
there resets the strip to the boot default; midi-scenes uses the same bytes and the ledger
refuses the pair by name (`Claims.part_window`); scenes-p2's pool is beside them, not on
them. Not the panel's Part Save or Reload (the port writes no card): a poke of the window
stands in.

## `strip_model`

Two slots of 16 bytes: the FX id at +0 (0 = none), three spare bytes, then the twelve knob
values, page 1 at +4..+9 and page 2 at +10..+15. The MASTER page writes page 1, the
SETUP the id and page 2 (and page 1's defaults with a new id); each value must already be
inside its parameter's count (the DSP only masks to 0..127, and a select read past its
count is the trap in `AGENTS.md`), which both clamps hold.

## The AUX passes

Stage 1 of the returns (`docs/proposals/MIXER.md` section 18): the tail sums the ten
sources the mixdown read (T1..T8, IN AB, IN CD) into two stereo blocks, AUX A at
X:0x7ca0 and AUX B at X:0x7cc0, at twenty sends (`aux_model`, 0..127, in the record's
spare halfwords). At rest every send is 0. Nothing reads the blocks yet. `verify_aux`
holds the arithmetic at 0 LSB on the input pairs and the rest of the image unchanged;
a track's term is read, not run (no track reaches the mixdown under the port).

## Not yet

- A Part nobody has written gives OXIDE on slot 1 (the test remix's boot state); a shipping
  remix wants an empty strip there (`BOOT_MODEL`, and `boot.asm`'s record). The MAIN level
  on the page is stock's and is not stored. Part storage is not measured on a unit, and a
  part that is not stock's four (an Octakit kit window) keeps the model to itself.
- Only OXIDE is on the list. An insert joins it once it is shown to run correctly one frame
  per call with no dispatcher state: Character, for one, glides its knobs per call and reads
  X:0x213 at init.
- `make cycles` does not price site bodies. Under the port (instructions, not cycles, per
  16-sample frame): head 120 with both slots empty to 602 with OXIDE on both; tail 1,108 to
  7,690, the record's apply included. OXIDE costs 158 a frame in a track slot.
- Where MAIN plus the click clips, the tail's click (a difference of clipped values) is not
  stock's.
- Nothing is measured on a unit, including the DMA margin.

## Proof

`tools/verify/verify_strip.py`, under the ColdFire port against the same image with all
three sites' stock words put back, on four fixtures:

- **tones** (the input tones on MAIN) and **dirty** (the same with both cores' X and Y
  filled with garbage before the boot): core 0's TX0 MAIN pair equals
  `modules/oxide/design.py`'s `fixed()` of the reference's MAIN, sample for sample; the
  record flows every frame and changes nothing.
- **click** (the tones plus the metronome on MAIN): MAIN is `fixed()` of the pack's MAIN
  plus the click.
- **record**: `strip_model` is edited mid-run as the page will edit it (slot 1's IN to 96,
  slot 1 to none, slot 1 back to OXIDE, OXIDE on slot 2 too). Every frame of the pack's
  MAIN is the model of its phase or the next, 0 LSB, and every phase is reached in order:
  the knob change carries OXIDE's state, none leaves the frame dry, a new id starts from
  zero, slot 2 runs on slot 1's output, and each switch lands on a frame boundary, three
  frames after the poke. MAIN out is that pack's MAIN.

In all four the phones differ only by MAIN's change at the cue mix's gain, first sample of
each frame included; the recorder/USB pack's CUE half is identical; every other TX0 word
and host-port block is identical. Statically: the boot's start and `strip_model`'s agree,
and the chain's state 3 entry is `strip_xport`. The fixtures' MAIN carries the input
tones: under the port no track reaches the mixdown yet (`docs/remixer/EMU.md`).

`tools/verify/verify_mixerpages.py`, under the port on the same card against the image
with the three detours' stock bytes put back: the MIXER page is the stock page but for its
▶ (and again after RIGHT, LEFT and after a close and reopen, pixel for pixel); MASTER's
MUTE band is stock's and its boxes draw as locked, with OXIDE's IN and OUT and four empty
cells; INS 2 shows six empty cells; a trig mutes and leaves the page; A, B and LEVEL move
IN, OUT and MAIN by exactly what A and LEVEL move MAIN and MIX by on the stock page, and
the edit reaches core 0's record; MIXER, NO and FUNC + UP close the window and leave no
layer behind. The SETUP: its list is NONE and tail.asm's ids, the slot's effect inverted;
with slot 1 poked to DELAY its knob grid equals stock's EFFECT 2 SETUP's pixel for pixel
after the same turns (minimum, small steps, maximum, and a knob still lifted with its
value); YES puts NONE or OXIDE on a slot, with the defaults, and core 0 runs it (or runs
the slot dry) from the record; NO returns to the MASTER page, and every way out of the
SETUP leaves no layer behind. It cannot see the unit's LCD, the MKII keymap, a real
encoder's acceleration or a list longer than the window.

`tools/verify/verify_stripstore.py`, under the port on the same card, one load and a panel
script a case (`poke` lines change the window while the unit runs): a project nobody has
written gives the boot default and writes nothing; A +10 on IN, and NONE onto INS 1, leave
the window in the model's stored form with both slots valid, the SRAM twin the same bytes
and the edited words set, part 1 untouched; a valid record poked into the window becomes
the model (the window is not written back, no mark); a stale checksum and a designer's
shape give the default; a record then zeros give the record then the default; the panel's
part 1 shows and edits part 1's window and sets its dirty bit; part 4 keeps the model to
itself and leaves the ISR's look free; with the DSP a record poked into the window reaches
core 0 as slot 1's record. It cannot see the panel's Part Save or Reload, the bank file, an
Octakit kit window or the strip's bytes under a real designer shape.
