# RECORDER HOLD

Three ColdFire code caves, no DSP code: a recorder-buffer FLEX voice that
reads one sample past its recording repeats the last sample instead of
playing a zero.

In sound-on-sound (a REC3 trig with SRC3 = the track, on the same step as
the PLAY trig) the recorder arms 64 samples after the play trig binds, so
the voice plays the previous pass. Its window is the current arm spacing and
its content is the previous one. At a tempo whose bar is not a whole number
of samples the spacings alternate (82,687 / 82,688 at 128 BPM), and on each
pass where the window is one sample longer the voice fetches index END
(`+0x64`). No block is mapped there, so the fetch returns the pool base
`0x40a955e0`, one zero sample plays, and SRC3 records it back into the loop.

Each cave sits after one fetch of the forward copy paths and runs the shared
fixup in `fix.inc`: a fetch of exactly END that came back unmapped becomes a
fetch of END − 1 with a count of one.

| cave | hook | stock bytes |
|---|---|---|
| `hold_copy.s` | `0x400086c2` | `move.l d0,d3 / addq.l #8,sp / tst.l d1` |
| `hold_xfade_a.s` | `0x4000853e` | `movea.l d0,a3 / move.l d1,d4 / move.l (76,a2),-(sp)` |
| `hold_xfade_b.s` | `0x4000854e` | `move.l d0,d7 / lea (16,sp),sp / tst.l d4` |

Conditions: the fetch returned the arena base with a positive count, `+0x15`
is negative (a recorder buffer) and the fetched index equals `+0x64`.
Anything further past END is stock.

The arena base is `0x40a955e0` on stock. A remix with a DRAM runtime (USB
AUDIO, any `dram=True` unit) moves it by the platform's 1,707 pages to
`0x41495de0`, and the fetch then returns the moved base. The manifest
declares the caves' three base literals each (`pool_base_literals`); the
build checks the count and rewrites them with the firmware's own base sites
(build report: `arena: hold cave ...: 3 arena-base literal(s) -> ...`).
Before that (PR #444 alone), in such a remix the caves compared against the
stock base and never fired: 0 substitutions and 31 zero samples at RLEN 4
in the port. Found by Bryan T on his USB recording remix, 26 Sep 2026.

## Measured in the port (26 Sep 2026)

`recfix` image, fixtures built from the RECTRIG backup: T1 FLEX on R1, REC1 +
REC3 (SRC3 = T1) + PLAY on the same steps, a 997 Hz tone into A/B. The
residual of a two-tap sinusoid predictor at each wrap, relative to the local
amplitude:

| fixture | without | with |
|---|---|---|
| 128 BPM, RLEN 16, trig on step 1 — the one-sample-long wrap | 195 % | 7 % |
| 128 BPM, RLEN 4, trigs 1/5/9/13 — pass 8, then its repeats | 187 %, 47 %, 12 %, 3 % | 9 %, 2 % |
| 128 BPM, RLEN 4 — pass 16 | 62 %, 15 %, 4 % | 13 %, 3 % |

The caves substitute on those wraps only: 2 of 4 wraps at RLEN 16, 3 of 19 at
RLEN 4 (there the crossfade copy reads both positions, so each wrap is two
substitutions). What remains, 7–13 %,
is the one-sample change in loop delay that any whole-sample loop of a
fractional period has: the one-sample-short passes measure the same, with or
without the cave.

Unchanged, all eight tracks' voice audio bit-identical: the self-loop
(REC1 only) at 128 BPM RLEN 4 and 16 against `recfix`, and sound-on-sound at
120 BPM RLEN 4 and 16 against stock.

Not measured: hardware; reverse playback (the fixup acts on forward fetches only);
16-bit recorder formats (the fixture records 24-bit).

Assemble from the repo root (for the `.include`):
`m68k-elf-as -mcpu=5475 -o x.o modules/recorder-hold/hold_copy.s`; the build
re-assembles and compares against the pinned bytes.
