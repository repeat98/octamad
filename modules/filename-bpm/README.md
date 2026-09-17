# FORCE FILENAME BPM

A PERSONALIZE checkbox. With it on, the number in a sample's filename **is**
the sample's tempo. Off — the power-on state — the unit is stock.

## What stock actually does

The manual's "if the file name contains the BPM value it will be used to
determine whether the calculated tempo should be halved or doubled" is
precise, and narrower than it reads. Measured 17 Sep 2026 from 1.40C
(`out/raw/section_3_MAIN_OS.bin`, `objdump -m m68k:cfv4e`):

`0x40020ad8(sampleCount, name)`

1. Guesses a **power-of-two** beat count from the length:
   `beats = 2^(floor(log2 count) - 14)`, pinned at 2 below 32,768 samples
   (`ff1.l` on the count, `d3 = 50 << (msb - 15)`, in units of beats×25).
2. Tries **three** candidates in order — `beats/2`, `beats`, `beats*2`.
3. For each, tempo is `2,540,160 * (beats*25) / count` in BPM×24
   (`0x40020a94`), divided by 24 and **truncated**, `sprintf("%d")`, then
   `strstr(basename, that string)` — strstr is `0x40014158`, basename is
   `strrchr(path, '/')` at `0x400204a8`.
4. First hit wins. No hit keeps the middle candidate.

Three consequences, all falsifiable on a unit:

- The middle estimate always lands in **(80.75, 161.5] BPM**; the three
  candidates together span 40.4–323. The manual's "85–170" is not what the
  code computes.
- A loop that is not a power-of-two number of beats long (3, 6, 12 beats)
  can **never** match its own filename, because no candidate can equal its
  tempo.
- Samples of **50,000 samples or fewer** (~1.13 s at 44.1 kHz) never
  consult the name at all: `cmpi.l #50000` at `0x4009922a` sends them to a
  hardcoded 120 BPM (`0xb40` = 2880 = 120×24).

And the value does not only come from there. The project file's `[SAMPLE]`
block stores `BPMx100` / `BPMx24` per slot, so a slot that has been saved
once is **restored**, not re-estimated (`0x40086b24`, `0x40086b62`).

## What this module does

Parses the basename itself and writes the tempo through the firmware's own
explicit-tempo setter `0x40099090(settings, bpm*24, len)` — the routine
behind CAL BPM FROM SELECTION — so `+0x118` (the reciprocal, from the stock
bank at `0x400abf38`), `+0x11c`, `+0x120` and `+0x128` are all written by
stock code.

The parse rule: every maximal run of digits in the basename is a candidate,
optionally followed by `.` or `,` and **one** more digit. The **last**
candidate whose integer part is 30–300 wins — the same bound the tempo field
itself clamps to, so a sample rate, a year or a track number is ignored by
the field's own limits. Nothing found leaves stock alone.

| the name | the tempo |
|---|---|
| `amen_170.wav` | 170 |
| `loop_126.5.wav` | 126.5 (BPM×24 = 3036) |
| `loop_01_128.wav` | 128 (the last in-range number) |
| `2024_session_140.wav` | 140 (2024 is out of range) |
| `sr44100_hit.wav` | stock (44100 is out of range) |
| `/AUDIO/170bpm/loop_90.wav` | 90 (the basename, not the path) |
| `kick.wav` | stock |

Three hook sites, because a tempo reaches a slot from three directions:

| site | what it is |
|---|---|
| `0x400992ea` | the per-slot attribute init `0x40099148`, after the trim words the setter reads are stored and after both stock arms have written their tempo |
| `0x40086b24` | the project's `[SAMPLE] BPMx100` restore |
| `0x40086b62` | the same block's `BPMx24` restore |

## The PERSONALIZE row

Three parallel 16-entry arrays — labels `0x400b2a34`, getters `0x400b2a74`,
setters `0x400b2ac0` — contiguous and immediately followed by unrelated
data, so they are relocated with `TableGrow` and their five references
repointed (`0x40068efe`, `0x40068f0a`, `0x40069022`, `0x4006903e`,
`0x40069056`). The item count at `0x40068fb2` goes from `moveq #15` to
`#16`.

**Only fifteen stock entries are copied.** The count is `15` or `16`
depending on `0x46c8d18c`, a word a GPIO probe sets at boot
(`0x4001f8ce`) — so index 15 is the entry stock hides on the variant that
reads zero, and that entry is LED BRIGHTNESS. Appending would have hidden
OUR row there instead. Our row takes index 15 and LED BRIGHTNESS is
re-appended at 16 through two `jmp` forwarders to its stock getter
(`0x40068c80`) and setter (`0x4006907c`), which is right on both variants.
🟡 "the word is the hardware variant, and the hidden item is LED
BRIGHTNESS" is inferred from the GPIO probe and the list order; falsifier:
open PERSONALIZE on an MKI and count the rows.

The menu mechanism is the retired `patch_menu` module's, which ran on
hardware (`git show 40a1f19:tools/patch_menu.s`).

## Measured

`python3 tools/verify/verify_fnbpm.py` (in `make check`) runs both hooks
under the ColdFire port against a fabricated settings record and reads the
tempo field back: 12 names, the checkbox off, the derived fields, and both
displaced instructions. It caught a real defect on its first run — the
stored tempo had been stashed in `%d1`, which the parser uses as scratch,
so a name with no number came back as its last character minus 48.

## Open

- **Not on hardware.** No flash yet.
- **The toggle does not survive a power cycle.** It is a bare RAM word
  (`0x800000d4`, zero stock references), like the `patch_menu` precedent's
  two. Persisting it means a new project-settings key and a hook in the
  writer as well as the parser.
- The load hook is measured with a fabricated record, not with a real
  sample coming off a card; `0x40099148`'s seven call sites are not all
  walked.
- A sample whose tempo the user sets by hand in AED (CAL BPM, or the
  ORIGINAL TEMPO knob) keeps that tempo **for the session** — the module
  does not fight an explicit edit — but the filename wins again the next
  time the slot is loaded or the project is reopened. That is the intended
  reading of "strictly"; say so if it should be stricter still.
- `.ot` companion files are not hooked. They are a separate binary path
  from the project's `[SAMPLE]` block and were not located here.
