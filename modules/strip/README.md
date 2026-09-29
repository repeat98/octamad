# MASTER STRIP

Two insert slots on the summed MAIN, run inline after payload A's mixdown: the master strip
of `docs/proposals/MIXER.md` (step 2, §11 and §12). Which effect each slot runs and its
knobs come from a model on the ColdFire, `strip_model`, which the MIXER page will edit and
a Part will store; until then it starts at OXIDE on slot 1 at its 0 dB points (IN 48,
OUT 80) and slot 2 empty. The main out, the recorder and USB audio (stock's pack) and the
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

Why split: the first version ran all 16 samples at P:0x2d5, and under the port the phones'
first sample of every frame went out two frames stale, because the pass held stock's cue
mix back past the DMA (MIXER.md §11).

## `strip_model`

Two slots of 16 bytes: the FX id at +0 (0 = none), three spare bytes, then the twelve knob
values, page 1 at +4..+9 and page 2 at +10..+15. The MIXER page (next) writes it; each
value must already be inside its parameter's count (the DSP only masks to 0..127, and a
select read past its count is the trap in `AGENTS.md`).

## Not yet

- No page edits the model yet, and no Part stores it: it holds its boot value until the
  MIXER page (stage B, the layout Jannik locked on 29 Sep 2026) and Part storage land.
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
