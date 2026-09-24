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

**The port's EMAC gate holds both ACCext layouts (23 Sep 2026).** The
frame ISR saves the interrupted context's accumulator extension registers
in integer mode (`clrl %d0; movel %d0,%macsr; movel %accext01,%d4; movel
%accext23,%d5` at `0x4000ac96`) and restores them the same way at
`0x4000d968`, every frame. `v4e.cpp`'s write knew only the fractional
layout (eight extension + eight low bits per accumulator; the integer
layout is sixteen extension bits), so every restore put the saved word's
low byte into ACCn[7:0]: 0x12345678 came back 0x123456ab, the extensions
0xfe008900 for 0xfedc89ab. Found by Jannik Aßfalg (an A/B/A of a ColdFire
patch whose integer-mode MAC loop the ISR interrupted mid-accumulation;
a stock A/A repeats exactly because the corruption is deterministic),
reproduced here to the byte by the eight new assertions in
`test_emac.cpp`, fixed to QEMU's `set_mac_exti`. `verify_set` on
OCTABAM89 (900 frames, `bus`): block dump bit-identical before and after,
18/18 — that fixture never has a live extension at an interrupt, so the
fix is landed on the gate, not on a symptom.

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

## Driving it: the panel from a FIFO (18 Sep 2026)

`ot_emu --live FIFO` reads panel events while the RTOS runs and feeds
them to the firmware over the panel link (UART1) in the controller's own
framing (`docs/firmware/PANEL.md` §4b), and MIDI over UART0:

```
mkfifo out/panel.fifo
./out/emu/ot_emu --image out/raw/section_3_MAIN_OS.bin --card out/card.img --set OCTABAM --project RIG \
    --load-ms 20000 --dsp --lcd out/lcd.bin --live out/panel.fifo
.venv/bin/python3 tools/emu/lcd_view.py out/lcd.bin --panel out/panel.fifo     # other terminal
```

Lines: `key <code> down|up`, `enc <n> <delta>`, `pot <0..255>`,
`midi <hex>...`, `quit`. Without `--sequencer` the transport is yours
(PLAY is `0x28`); with it the frames target still ends the run. The
viewer's `--panel` draws keys (press/release, so FUNC + key holds), the
seven encoders (buttons or the mouse wheel over the label) and the MAIN
pot under the screen, with keyboard shortcuts (arrows, Return, Escape,
space = PLAY, `1..8 q..i` = trigs, F1..F5 = pages). The FIFO is polled
every 256 instructions and at most every 10 ms of wall time; the plane
file is flushed from the same poll 30 ms after a redraw. Measured: a
page key changes the screen in under a second of wall time at idle.

`--fast N` evaluates timers, interrupt delivery and the stop condition
every N instructions instead of every one. Measured on the 1200-frame
rig run: 42.3 s exact, 36.5 s at N = 8 (block dump identical, the audio
file's length differs by the run's end point), 35.4 s at N = 32 (block
dump differs). It is not the exact mode and is off by default; the
gates never use it.

## USB: the device controller and a scripted host (the port, 25 Sep 2026)

`--usb-host SOCKET` gives the port the MCF5445x's USB OTG module as the
firmware drives it (`tools/emu/ot_emu/usb.h`): the Chipidea device
controller's registers at `0xfc0b0000`, the session and interrupt
semantics its driver depends on, and the transfers themselves -- a host on
a unix socket walks the firmware's queue heads and transfer descriptors in
guest memory, moves the bytes, retires the descriptors and raises the
completion interrupt (INTC1 source 47, the firmware installs it at level 4).
Without the option the window stays the all-ones stub every earlier gate
was measured against, and the firmware never brings the controller up.

What the firmware does with it, read from the 1.40C image: the boot selects
a ULPI transceiver (an external high-speed PHY); the bring-up at
`0x4001d630` writes USBMODE 0x0e (device, big-endian), the endpoint list
at `0x4ec94800` and USBINTR 0x57 as soon as OTGSC reports a session; the
ISR at `0x4001e594` answers GET_DESCRIPTOR from the tables at `0x400e2000`
(Elektron 1935:0002, one MSC/SCSI/BOT interface on EP1) and runs the SCSI
worker over EP1, answering "no medium" until USB DISK MODE unmounts the
card. Nothing in the image runs the controller as a host, and the separate
host-only module at `0xfc0b4000` is never touched.

```sh
out/emu/ot_emu --image out/mainos_bus.bin --usb-host /tmp/ot-usb.sock &
tools/harness/usb_host.py /tmp/ot-usb.sock msc        # reset, enumerate, INQUIRY, TEST UNIT READY
tools/harness/usb_host.py /tmp/ot-usb.sock midi-send 903c64
tools/harness/usb_host.py /tmp/ot-usb.sock audio 3 2.0 capture.pcm 4
```

The socket protocol is octemu's (`setup`/`in`/`out`/`reset`/`speed`;
markandrus, MIT), so its `tests/usb-host.py` drives this port unchanged.
After every other phase the port HOLDS the machine for the bench until the
client has connected and hung up (`--usb-hold-ms`, a wall-clock cap: an
idle machine skips through emulated seconds in milliseconds). A `reset`
is deferred until the firmware has attached, so a script that connects
before the bring-up waits instead of failing. `--usb-notify FILE` logs the
attach/detach edges of USB DISK MODE (the firmware's own flag at
`0x460e76a0`); `--usb-fs` reports full speed in PORTSC1. The exit summary
prints the registers and the transfer counts; a primed queue head whose
token was never cleared is named on stderr (the defect that crashed a unit
twice under octemu's USB-audio payload).

Measured 25 Sep 2026: the stock stack in `bamsep26` enumerates at high
speed and answers INQUIRY `Elektron Octatrack DPS-1 0002` with a good CSW
(`make verify` runs this as `verify_usb`, 3 s). octemu's USB-MIDI image
built from the same stock bytes enumerates with three interfaces, and two
channel messages sent to EP2 OUT reach the firmware's own MIDI receive
FIFO (six writes to `0x46100b80` from `midi_rx_enqueue`). The peripheral
gate (`ot_periph_test`) pins the register rules, the SETUP byte order, a
bulk chain (INQUIRY data + CSW), one-descriptor-per-poll on an
isochronous endpoint, OUT, stall and reset on a fake memory.

What it cannot see: timing. The port serialises the host's polls, the
frame interrupt and the eDMA, so the USB-audio producer's race against the
read-back bank swap -- octemu's open hypothesis for its mid-stream clicks
-- cannot show here. And octemu's card-loaded payload does not install
under the port: its trampoline hooks `fs_card_detect_poll` (`0x4003f174`),
the firmware routine the card-detect GPIO poll reaches, and the port mounts
the card by posting the mount message directly, so that routine never runs
(0 hits on a PC watch across a 800-frame run). The modules `usbmidi` and
`usbaudio` carry the same code on octabam's loader instead, and
`verify_usb` streams from them: the bench polls an isochronous endpoint
once per 500 us of DEVICE time (`isoPoll`), which is what a real host's
bInterval-3 schedule does; a script draining as fast as the socket allows
starved the ring and pulled the rate servo down to 21/22 frames.

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

Route A's RAM map folds the OS image's uncached alias at `0x48000000` into
the same 32 MB as `0x40000000` (25 Sep 2026; the port's `machine.h` folds
it too). octabam's loader depacks the DRAM runtime through that alias and
the code then runs from the cached address, so with two separate mappings
every DRAM remix faulted in the boot (`UC_ERR_WRITE_UNMAPPED` at loader pc
`0x4010fe92`, a1 `0x48a97000`) and `verify_hidden` drew nothing for their
host pages. The `0x46000000` region's alias at `0x4e000000` is still
separate here (grown on demand by `_prime_menu`'s hook); the port folds
both.

## Speed (the port, measured 17 Sep 2026, M-series Mac, native arm64)

Stock 1.40C, the rig project, `--sequencer --internal-clock --dsp`:

| phase | emulated | wall | ratio |
|---|---|---|---|
| boot to the handoff | 205 ms, 10.2 M instructions | 3.5 s | 17× |
| load (`--load-ms 20000`, DSPs stepping through the idle skips) | 20 s | ~35 s | 1.7× |
| play (400 → 1200 frames) | 290 ms of audio | ~2.9 s | **~10×** |

The play phase runs 23,946 ColdFire instructions per 16-sample frame =
1,497 per sample = 66 M/s for real time; the hottest loop is the stock
delay's EMAC mix (`0x40003734`, `COLDFIRE_DELAY.md`), real work, not a poll. The
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

Direct timing of the play phase (the `cpu` report line, 18 Sep 2026):
**14.0× off real time exact, 12.4× at `--fast 8`**; 4.7 M ColdFire
instructions per wall second all-in. By 1 KB of code (`--profile`, the
frames alone): 28.5% the stock delay's EMAC mix (`0x40003400..`), 22.5%
the frame builder (`0x4000cc00..`), 7% the frame dispatcher, ~4% the
host-port transfer state machine — real work, nothing to idle-skip.
Unicorn's TCG (route A's core, QEMU's m68k JIT) on a store loop from this
image with no hooks and no instruction count: 52 M instr/s. Real time
needs 66 M/s on the ColdFire plus the DSP side.

Jannik Aßfalg's exclusive profile (23 Sep 2026, 🟡 his port build with a
`--work-profile` PC counter that is not in this tree; a fixture of eight
FLEX tracks looping a 440 Hz sample at 120 BPM, trigs on steps 1–4, DELAY
on T1–T7 and PLATE on T8, 5,600 frames after a 20 s load; instructions,
not cycles):

| ColdFire scope | instructions / frame | share |
|---|---:|---:|
| frame ISR `0x4000aad0..0x4000d9b0` | 10,720 | 26.2% |
| eight-track delay `0x400031a0..0x4000385a` | 7,665 | 18.7% |
| sample analysis `0x40098388..0x400985ac` | 5,643 | 13.8% |
| voice renderer `0x40007960..0x40008f82` | 5,605 | 13.7% |
| correlation search | 2,196 | 5.4% |
| total | 40,903 | |

Ranges are half-open and exclusive of callees; the four boundaries
re-checked here by objdump ✅ (the ISR ends in `rte` at `0x4000d9ae`, the
delay and the renderer in `rts` at `0x40003858` / `0x40008f80`, the
analysis routine is a `lea -36(%sp)` frame ending in `rts` at
`0x400985aa`). What "sample analysis" and the "correlation search" do is
his reading, unverified here; the routine's MAC recurrence at
`0x40098494..0x400984be` is five `macl`/`msacl` with parallel loads in a
`bgt` loop, and no `jsr`/`lea` in the image names `0x40098388` (a table
or relative call). His opt-in module `stock-analysis-fast` (−251
instructions/frame, 0.6%, audio identical over 5,600 frames on his
emulator) was not sent; his hardware acceptance is pending, and his
report's own limits hold: p95/p99 unchanged, so no worst-case headroom
claim.

**Retracted 22 Sep 2026**: "it has no MAC-with-parallel-load form" was
wrong. Unicorn 2.1.4's `DISAS_INSN(mac)` (vendored QEMU 5.0.1) has the
form and decodes it with three defects, found by reading markandrus/octemu's
independent fix against QEMU 11.1 and confirming the identical lines are
present, verbatim, in Unicorn's own source: Rx read from the opcode word
instead of the extension word; a phantom dual-accumulate flag read out of
Ry's own register field, which `disas_undef`s on `cfv4e` (no
`M68K_FEATURE_CF_EMAC_B`) — this, not an absent form, is why route A shims
every site (`emu_bringup._emac_load_shim`, `native_macload_sites`) instead
of running them natively; and the MASK register resets to zero instead of
CFPRM's all-ones, folding every load address to 0. Fixed in
`tools/patches/unicorn_emac_fractional.patch` (three files: `translate.c`,
and `unicorn.c` — NOT `cpu.c`'s `m68k_cpu_reset`, which this patch also
carries for documentation but which Unicorn's own `uc.c` never calls;
`unicorn.c`'s `reg_reset` is the reset Unicorn actually runs). Verified by
`emu_bringup.emac_selftest`'s new cases (fails on stock, passes fixed) and
by a route-A boot to the RTOS handoff completing clean with the shim
disabled (`OCTA_MACLOAD_NATIVE=1`, `emu_rtos.py`) — but that run never
executes any of the 435 hooked sites (0 shim calls either way without a
project on the card), so this is NOT yet evidence the shim can be retired
on real firmware traffic; `OT_PROJECT=<dir>` would be. The shim stays the
default until that run exists.

**Parked 18 Sep 2026** (someone else is working on a core). The options,
cheapest first: (1) hot-loop HLE — the two loops above are 51% of the
play-phase instructions and `v4e.cpp` has the EMAC semantics; days, ~2×
on the ColdFire side, verifiable bit-identical with the block dump;
(2) Unicorn/TCG as the fast core with the RTOS glue rewritten on its
hooks and QEMU's translate.c taught the load form; ~3× on the ColdFire
side; (3) a custom ARM64 JIT (asmjit is vendored) with the DSP JIT and a
thread per core — the only route to real time, weeks.

What real time would take, in order, none of it started:

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
  `--dsp-pcwatch core:pc` (the last 24 arrivals with a, b, x, y, r0, r4, r6, n4, sp, r2, m2, r1, n1, r7, m7, m0 and, since 21 Sep 2026, n7 -- the frame count of a call), `--dsp-peek core:X|Y|P:addr,len` (upper-case
  space letter), `--mem-dump addr,len=file`.
- `--dsp-sample core:pc:FILE[:max]=SPACE:[rN+]addr,len[;...]` (24 Sep
  2026) writes one line per arrival at a DSP PC: the executed count,
  r0–r7, then each span's words. A span's base is absolute, or relative
  to r0–r7 as they are at the arrival (`X:r2+1e,1` is the track state's
  trig word at core 1's `P:0x198`). It is the per-frame view the
  24-arrival pcwatch cannot give. The Machinedrum's trig bit and its
  bit-exact check were measured with it.
- The stall check (a loop within 64 bytes of PC for 4 × 500K
  instructions) counts sequential RAM byte reads as progress, not only
  writes (24 Sep 2026). A hash or compare walking memory is progress, and
  a poll re-reads one address. The loader's hash over the Machinedrum's
  300 KB core-1 upload reads 2.7 M instructions without writing, and was
  reported as `unrecognised spin` before.
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
every track with record audio has a chain output; the main out's TX0
counts are printed (informational: on OCTABAM89_setgate only T8's chain
output ever reached TX0 under the port, measured 20 Sep 2026 with and
without the return; which tracks reach TX0 under the port is open); CC 40
over MIDI IN moved T2's SEND and (CC PAGE 2) CC 68 reached
T1's FX1 page 2; on a bus remix each engine's host carries T2's send on
its chain output (the wet prints on the host since 20 Sep 2026; the
engines warm up 256 blocks each) and an engine on the wrong core is
refused;
the load rewrote no project file; the firmware's LOG carries no error
beyond the unstaged samples. The tested bank is staged as bank A too and
`MASTER_TRACK=0` (the emulated load ends on bank A, and the transport
start's refresher re-applies the saved bank's ids for T1-T3, T7 and T8
only, by `--bank` or by a program change alike; with the master on
nothing reaches TX0 under the port). ~80 s. On the image before PR #271
it fails T1 and T5 (the tempo cave); on it, 18 checks pass (OCTABAM88
bank B, 15 Sep 2026).
