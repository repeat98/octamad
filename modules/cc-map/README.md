# CC MAP

Maps MIDI CC numbers that stock ignores onto parameters stock CC cannot
reach. Each **block** is a range of CC numbers written to one page's slots.
Stock incoming CC reaches page 1 only (CC 16–45): the handler admits
`cc−16 < 30` and derives `slot = flat % 6` (`docs/firmware/MIDI.md` §2).

| block | target |
|---|---|
| CC 62–67 | FX2 page 2, slots 6–11 |
| CC 68–73 | FX1 page 2, slots 6–11 |

`Kind.CF_PATCH`: one cave (`cc_map.s`, linked where the ColdFire free region
places it) and one poke. Named CC PAGE 2 (`modules/ccpage2`) until
25 Sep 2026. Flash notes and commits before that date use the old name.

## Hook

The MIDI dispatch table's CC entry `0x400d64a0` (`0x400d6474[0xB]`) is
repointed from the stock handler `0x4000e79c` to the cave. A CC outside
every block tail-calls `CC_NEXT` with the message pointer intact. The build
defines `CC_NEXT`: the stock handler, or Octakit's handler when the
SCENES KITS bridge is in the image (`modules/scenes-kits`). With the bridge,
the order is this cave's blocks, then Octakit's handler, then stock's.

## What a CC in a block does

The cave rebuilds the channel→track map (`0x40001854`, as stock does on
every CC), returns if AUDIO CC IN (`0x80000049`) is zero, and writes to
every audio track whose trig channel matches the message's channel. The
part is byte `0x80000003`, the one the page-2 editors use.

Each block makes the stores of that page's firmware editor. DB is the long at
`0x46c82456`. Store addresses are `+ part*6322 + track*30 + slot2`, and lane
addresses are `0x80000810 + track*72 + lane + slot2`.

| block | editor | written when | clamp | Part | shadow | lane |
|---|---|---|---|---|---|---|
| 62–67 | FX2 page 2, `0x4003aab2` | the Part's FX2 id is BusDelay (6) or BusVerb (7); other ids skip the track | count tables in the cave (`VCOUNT`/`DCOUNT`) | DB `+0x8f084` | `0x100a51d2` | `+0x38` |
| 68–73 | FX1 page 2, `0x4003abe4` | the Part's FX1 id is not 0 (NONE) | the FX1 descriptor's min/count (`0x400d5f58[id]`, `+0x6a`/`+0x9a`) | DB `+0x8f07e` | `0x100a51cc` | `+0x32` |

Both blocks then set the editor's four dirty flags: `DB+0x95048 |= 1<<part`,
`0x100b145e |= 1<<part`, `DB+0x9b332 = 1`, `0x100f8598 = 1`. The cave leaves
out the editors' redraw marker and refresher call. Without the dirty flags
the Part store is inert. The page-2 path posts nothing to the DSP. The
per-frame copier `0x4000cae8` ships the live lane every frame.

Selects are clamped to their count. A stored value past a select's count
is used as an index and stalls the sequencer (AGENTS.md, "A part saved
under an older slot layout").

After each write the cave calls `CC_MODEDEF2` (FX2) or `CC_MODEDEF1` (FX1)
with a2 = slot2, d2 = the clamped value, d4 = track, d5 = part. When MODE
DEFAULTS is in the image these resolve to its entries, so a MODE sent over
CC re-defaults the knobs around it. Otherwise they resolve to a stock `rts`
(`0x40027e1a`).

## Adding a block

1. Take CC numbers from the free list below.
2. Trace the target page's editor: its Part, shadow and lane stores, its
   clamp, and its dirty flags. `docs/firmware/MIDI.md` §6 has the table for
   the three page-2 editors traced so far (PLAYBACK `0x4003a474`, FX2, FX1).
3. Widen the range test at `CAVE` (today `cc−62 ≤ 11`) and add a write path
   for the block.
4. Regenerate the oracle (`manifest.CODE`), and extend
   `tools/verify/verify_ccmap.py` to prove the new stores on all eight
   tracks against the editor.

## CC numbers

Stock audio-track CC map (handler `0x4000e79c`, `docs/firmware/MIDI.md`
§1): 7, 8, 16–61 and 112–127 are used. 0–6, 9–15 and 62–111 fall through
to the handler's `rts`.

| range | count | holder |
|---|---|---|
| 62–73 | 12 | this module |
| 74–111 | 38 | free |
| 0–6, 9–15 | 14 | free |

Octakit's handler reads 7, 46, 47 and 55–58, all stock numbers.

Controllers send some numbers in these ranges without being asked, for
their standard MIDI meanings:

- 64–67 (sustain, portamento, sostenuto, soft pedal) are in the FX2 block.
  A sustain pedal on a track's channel writes FX2 page-2 slot 8 on a bus
  host.
- 96–101 are data increment/decrement and NRPN/RPN select.
- 0 is bank select, 1 mod wheel, 6 data entry, 10 pan, 11 expression.

## Oracle

`manifest.CODE` is the hand-assembled form of the cave. `legacy_bytes`
patches in the count-table addresses. It is the `CavePatch.reference` that
the linked source is compared against, wherever the source is linked. The
comparison is skipped when `CC_NEXT` is bridged to Octakit or `CC_MODEDEF*`
resolve to MODE DEFAULTS, since those change the bytes.

`VERB_COUNTS` / `DLY_COUNTS` in the manifest and `VCOUNT` / `DCOUNT` in the
cave must match the busverb and busdelay page-2 counts.

## Measured

- `tools/verify/verify_ccmap.py` (in `make check`): for each track 0–7
  on its own channel, CC 62 lands count-clamped at the traced Part, live
  and shadow bytes; an over-count value clamps; CC 40 reaches the next
  handler and writes no page-2 byte. This runs single-core under Unicorn, so
  it proves the write and the decision.
- Under the ColdFire port (`verify_set`, `OT_PROJECT=<dir> make check`):
  CC 68 over UART0 reaches the FX1 page-2 lane and the DSP record
  (15 Sep 2026).
- MODE DEFAULTS over CC, under the port: CC 62 = 1 on T1's channel lands
  GRAIN's view in the lane; a CC 63 in the same frame then sets SCTR.

## On the unit

- Image 96: CC 63 on channel 5 moved SHMR on the panel and raised the
  reverb tail's 2–8 kHz bands 5–8 dB. Images before 96 wrote the PLAYBACK
  page-2 byte (`docs/remixer/FAILURE_MODES.md`).
- Image 97: the station voicing sweep set FX1 MODE over CC 69 (`docs/remixer/FAILURE_MODES.md`).

## Open

- FX2 page 2 of any FX2 effect other than BusDelay/BusVerb: the cave skips
  those tracks.
- MIDI CC through the SCENES KITS chain on hardware (the port has no MIDI
  input on that path).
- Whether an FX1 page-2 edit reaches the DSP on a THRU track
  (`docs/remixer/FAILURE_MODES.md`).
