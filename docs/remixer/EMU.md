# The Unicorn ColdFire emulator

The firmware's own screens, drawn by its own code, without a flash. Two
routes on Unicorn's CFV4E core:

- **Tier-0** (`tools/emu/emu_bringup.py`): boots a MAIN OS image to the
  RTOS multitasking handoff (`trap #0`, ~7,000,000 instructions, ~4 s),
  then calls draw code directly against the warm machine. What the
  remixer's UNIT pane and the label/formatter gates use.
- **Route A** (`tools/emu/emu_rtos.py`): crosses the handoff and runs the
  firmware's own scheduler (the trap dispatched by hand, every `rte`
  popped by hand, PIT0 as a timer counted in samples, the interrupt
  controllers modelled), loads a project from an emulated card, runs the
  sequencer. ~120× real time, no audio; the oracle the C++ port
  is measured against.

The bring-up records (`EMU_BRINGUP.md`, `RTOS_FORK.md`, `COLDFIRE_PORT.md`)
are in git history (`git show 3ceba41:docs/history/<name>`).

## Setup

```sh
make emu-setup                       # uv sync --extra emu -> .venv with unicorn + textual
make emu-unicorn                     # route A: the EMAC-fixed Unicorn
.venv/bin/python3 tools/emu/emu_bringup.py [image]
make emu-rtos PROJECT=<project dir>
.venv/bin/python3 tools/emu/emu_rtos.py --project <dir> --set OCTABAM --name RIG --load-project --ms 6000
.venv/bin/python3 tools/emu/emu_rtos.py --project out/_testproj --set OCTABAM --name RIG \
  --sequencer --internal-clock --poke-trig 2 --frames 400 --ms 20000 [--via-key]
.venv/bin/python3 tools/emu/emu_rtos.py --selftest
```

`unicorn` must be given `UC_CPU_M68K_CFV4E`: the default plain-68k core
does not decode `mvz`/`mvs`/EMAC. The `.venv` must be the host's native
architecture (an x86_64 build under Rosetta crashed on its first
`emu_start`).

**Route A needs the EMAC-fixed Unicorn.** Stock Unicorn 2.1.4 computes the
ColdFire's fractional-mode `macl`/`macw` as an unsigned product `>> 32`
where the MCF5445x does a signed product `>> 31`, and reads the MAC/MSAC
bit from the wrong word so `msac` adds. `scripts/build_unicorn.sh` applies
`tools/patches/unicorn_emac_fractional.patch` and builds the m68k-only
library into `.venv/lib/unicorn-emac/`; `emu_bringup` points the Python
bindings at it through `LIBUNICORN_PATH`. `emu_bringup.emac_selftest()`
pins the semantics (`0xc00 × 0x200000` = 3, `−0xc00` = −3, `msacl` = −3);
`emu_rtos.py` refuses a stock EMAC unless `--stock-emac`. The
EMAC-with-load shim keeps one trampoline slot per distinct instruction
(a rewritten trampoline is not retranslated).

## What the boot needs

Reset state: `SR = 0x2700` before `A7 = 0x48000000` (SR first, or the
supervisor/user stack banks swap). Peripheral MMIO is modelled by callback;
default read = all-ones satisfies every wait-until-set poll. One value is
load-bearing: the firmware reads `0xfc0c4000`, takes the top byte as the
PLL multiplier, and halts at `0x4000fa8c` unless `(reg>>24) × 12 MHz`
equals 264 MHz, so the harness returns `0x16000000`. Async completion
flags are auto-poked after the write that starts each operation.

| region | what it is | notes |
|---|---|---|
| `0xfc0c4000` | clock/PLL config | load-bearing (above) |
| `0xfc0a4066/69` | serial/UART-ish | writes `0x43`, `0x33` |
| `0xfc064000..01c` | a serial/timer module | status polled at `+4` |
| `0xfc048018..05b` | another module | writes `0x1b`, `0x06` |
| `0xfc088000/02` | serial shift-out (shift-done in bit 2) | write datum, poll bit 2, 8× |

## Drawing the firmware's screens (Tier-0)

The capture primitive is `FUN_40012bd8`, the draw-string call every
renderer funnels through (189 call sites): `FUN_40012bd8(font, canvas, x,
y, count, char *str)`, cdecl, `sp@(12)=x sp@(16)=y sp@(24)=str`. The detour
recipe: boot to the handoff; install the string-capture hook and a
map-on-fault hook (a cold detour can leave one stale pointer; a zero page
under it makes `strlen` read `""`); `ctl_flush_tb()` (the draw functions
were JIT-cached during the boot splash without the hooks); call the window
open (`FUN_40064c18`); set `[0x400cbf40]=1` and `[0x400cbd9c]=6` (the
visible-row clamp; the row loop bound is `min(clamp, count)`); poke
`[0x400cbd98]` = cursor row; call the draw (`FUN_40064d7c`). The line
pitch is 7 px, larger y = higher row. The selection highlight is an XOR
rect (`FUN_40012254`), not captured.

`render_menu(r, cursor)` returns the MAIN MENU as `(x, y, string)` tuples;
`render_fx2(r, track, effect_id)` / `render_fx1(...)` render the real FX
parameter pages with the effect assigned (the chooser column plus the
twelve knob rows, both pages). `tools/build/stock_labels.py` and
`tools/verify/verify_labels.py` / `verify_modenames.py` call display
formatters through the same machine. Item-level descent inside the menu
(a submenu item, a param page reached by key) needs the real key handler
`FUN_40064e64`, whose keycodes are position-dependent; repointing the
display at a submenu descriptor directly lands the labels at a bogus x.

## The screen itself (the port, 17 Sep 2026)

`ot_emu --lcd FILE` writes the firmware's own 1-bpp plane (`0x46c7e0ea`,
1,024 bytes) to FILE whenever it has changed, at most once per 2M ColdFire
instructions, and once more at exit (tmp + rename, never a torn frame).
`tools/emu/lcd_view.py FILE` shows it in a Tk window and follows the file;
`--term` draws it in the terminal with half blocks; `--png out.png` takes
one frame. The plane is 64 columns × 128 rows, 8 bytes per row, MSB left,
and screen pixel (x, y) is column 63−y of row x — stored a quarter turn
round; the PLAYBACK page reads upright under that layout and no other
(`docs/firmware/PANEL.md` §1). A 400-frame sequencer run on the rig
project flushed 12 frames: the panel redraws seldom, and the port drives
no keys, so what you see is the page the load leaves and whatever the
transport changes on it (BPM, the play icon, the pattern indicator).

## The card (route A)

`tools/emu/emu_card.py`: a pure-Python FAT16 image builder (a SET folder
holding a PROJECT folder → an MBR + FAT16 image the firmware's mount code
accepts; VFAT long names), an ATA task-file model at the FlexBus window
`0x90000000` (IDENTIFY advertises PIO only, so the driver never programs
the on-chip DMA channel), and one wait hook past the RTOS: the PIO
handlers only program the registers, and the data phase is the ATA
interrupt handler, so `attach()` hooks the queue primitive `0x40000818`
and performs the transfer the handler would when a command is in flight.
The set name needs a leading `/`; a WRITE's count byte is the remaining
count.

## Limits

No audio, no display pixels (strings only), no key matrix; route A models
no DSP. The C++ port (`make emu-cf`, `tools/emu/ot_emu`) runs both DSP
cores and the host port and is what `make check`'s boot verifier uses.

## Speed (the port, measured 17 Sep 2026, M-series Mac, native arm64)

Stock 1.40C, the rig project, `--sequencer --internal-clock --dsp`:

| phase | emulated | wall | ratio |
|---|---|---|---|
| boot to the handoff | 205 ms, 10.2 M instructions | 3.5 s | 17× |
| load (`--load-ms 20000`, DSPs stepping through the idle skips) | 20 s | ~35 s | 1.7× |
| play (400 → 1200 frames) | 290 ms of audio | ~2.9 s | **~10×** |

The play phase runs 23,946 ColdFire instructions per 16-sample frame =
1,497 per sample = 66 M/s for real time; the hottest loop is the stock
delay's EMAC mix (`0x40003734`, EXTERNAL.md), real work, not a poll. The
DSPs execute ~415 instructions per sample on core 0 after the idle skip
(3.82 G counted, 3.44 G skipped over 917,730 samples).

Where the wall time goes in the play phase (`sample`, top of stack, after
the two changes below): Musashi itself 29%, the DSP interpreter and its
per-instruction bookkeeping (`DspPair::stepCore`) 32%, the per-instruction
harness — interrupt delivery, timers, the opcode pre-read, `pc()` — 40%.

Two changes with outputs bit-identical (audio, block dump, plane, report):
the interrupt controllers' 22 `std::function` lines became one wires mask
per controller (`Intc::setWires`; the lines were ~35% of the run), and
`Machine::find` indexes regions by the top address byte instead of
scanning (a last-hit cache was tried first and lost on the play phase,
whose accesses alternate between code, data and the fast RAM). Together
53.0 → 38.9 s on the load + 400 frames run, 55.8 → 41.2 s at 1200 frames
(three runs each; single runs scatter by up to 10 s on a shared machine,
so the play-phase ratio above is ±20%). `cmake` from Intel Homebrew
configured the port x86_64 under Rosetta; `make emu-cf` and
`scripts/setup.sh` now pass the host architecture.

What real time (~10× on play) would take, in order, none of it started:

1. a coarse-grained run mode — interrupt delivery, timers and gates every
   N instructions, the DSPs in JIT blocks with a larger quantum, no PC
   ring. Not bit-identical to the exact mode (interrupt latency jitter up
   to N), so a flag, with the exact mode staying the instrument;
2. the EMAC/V4e path inline in Musashi rather than through the
   illegal-instruction callback (`v4e.cpp`): 9.5% of boot instructions,
   and the delay's mix loop is 12 EMAC of 21;
3. Musashi's memory path: every access is a virtual call through the
   peripheral check and region list; a flat fast path for the two SDRAM
   regions;
4. live input: a pipe or socket into the UART queues in place of
   `--midi FILE`; keys need the panel link's byte protocol
   (`0x400109bc`, `PANEL.md` §1), unread.

`--profile` now prints the hottest PCs over the frames alone as well as
over the boot, and the report carries the ColdFire instruction count over
the frames.

## The C++ port on a project

```sh
.venv/bin/python3 tools/emu/ot_emu/stage_card.py PROJECT_DIR OCTABAM RIG --out out/card.img \
    [--audio "SRC.wav:RIG/name.wav" --audio "SRC.ot:RIG/name.ot"]   # a sample the part plays
out/emu/ot_emu --image out/mainos_bus.bin --card out/card.img --set OCTABAM --project RIG \
    --sequencer --internal-clock --frames 600 --load-ms 20000 --dsp --main-level 64 \
    [--poke-trig 2] [--audio-in tone.wav] [--block-dump F] [--audio-out PREFIX]
```

- The project's `[STATES] BANK=` is the bank that plays; `--bank N` selects
  live and the transport start re-applies the saved bank's part over the
  live lane (half of the live id array was the other bank's after three
  frames, 15 Sep 2026). Write the fixture into the saved bank.
- Samples: `stage_card.py` skips `.wav`/`.ot`; `--audio` stages one at its
  card path. FLEX and STATIC (measured 15 Sep 2026: TSMODE 0 fits the file
  at unity, −69 dB) both play. `--main-level` is required for any voice.
- Cost: the 20 s load ≈ 40 s wall; ≈ 15 frames/s with both cores live.
- A panel action: `--poke-early ADDR=BYTE` (before the call; `0x80000000`
  is the current track), `--call ADDR,arg,...` (a firmware routine as
  main, after the load) and `--call-at N` (the same call N frames after
  the transport start, so the part re-apply does not erase an edit).
  `--poke` writes after the load, before the frames.
- MIDI IN: `--midi FILE`, one event per line, `<frames after the
  transport start> <hex bytes>` or `pre <hex bytes>` (before the transport
  start, the transport stopped). Bytes go onto UART0 (`0xfc060000`, INTC0
  source 26) and the firmware's own RX ISR, framer and MIDI thread take
  them: CC 40 = 100 on T2's channel moved T2's SEND halfword (with the
  page-1 slew, ~30 frames), CC 68 landed in the FX1 page-2 lane through
  the CC PAGE 2 cave, `pre C0 10` switched to bank B while stopped. A
  program change while playing waits for the pattern's end (thousands of
  frames).
- `--dsp-dirty [SEED]` fills both cores' X/Y and the shared window with a
  xorshift stream before the boot, as hardware's unzeroed RAM (dsp_host
  `-dirty` covers Y only). OCTABAM88 bank B on the rig image, clean vs
  dirty at 1800 frames: the aux return on T8 −31.4 vs −30.1 dBFS.
- Watches: `--watch-mem ADDR,LEN[;ADDR,LEN...]` (every write, with the
  PC), `--watch-read`, `--watch-pc`, `--dsp-watch core:X|Y|P:addr`,
  `--dsp-pcwatch core:pc`, `--dsp-peek core:X|Y|P:addr,len` (upper-case
  space letter), `--mem-dump addr,len=file`.
- The record a track's DSP instances read is `0x80000110 + 64·t` (32
  halfwords, `docs/firmware/MIDI.md`); the page-2 lane `0x80000810 + 72·t`.
- `--card-out FILE` writes the card as the firmware left it;
  `emu_card.extract_image(bytes[, out_dir])` reads any FAT16 card image
  back ({path: bytes}, long names). The firmware writes `LOG 000000.txt`
  in the card root during a load: one `ERROR` line per sample it could
  not open (`Couldn't load STATIC[n] with 'x.wav' ('FILE NOT FOUND')`)
  and `Couldn't read bank file '/SET/PROJ/bank01.work' ('PARSE ERROR')`
  for a PART record whose index byte is wrong (measured 15 Sep 2026) —
  the unit's PARSE ERROR, readable without a card. A load under the rig
  image or the `bus` image rewrote no project file (257 WRITE commands =
  the LOG and the FAT).

`tools/verify/verify_set.py REMIX --project DIR [--bank N]` (in `make
verify` when `OT_PROJECT` is set or `~/.octabam_project` names a project) does all of this for one part of a real
project and asserts: the load completed; the live FX1/FX2 id arrays equal
the part's; every track's record halfwords 18-26 equal its page-2 lane;
every track with record audio has a chain output; the main out is not
silent; CC 40 over MIDI IN moved T2's SEND and (CC PAGE 2) CC 68 reached
T1's FX1 page 2; on a one-aux remix RET at 127 over CC 38 brings T2's
send back on T8's chain output through the delay and the reverb (−45
dBFS at frame 900; the two engines warm up 256 blocks each, in series);
the load rewrote no project file; the firmware's LOG carries no error
beyond the unstaged samples. The tested bank is staged as bank A too and
`MASTER_TRACK=0` (the emulated load ends on bank A, and the transport
start's refresher re-applies the saved bank's ids for T1-T3, T7 and T8
only, by `--bank` or by a program change alike; with the master on
nothing reaches TX0 under the port). ~80 s. On the image before PR #271
it fails T1 and T5 (the tempo cave); on it, 18 checks pass (OCTABAM88
bank B, 15 Sep 2026).
