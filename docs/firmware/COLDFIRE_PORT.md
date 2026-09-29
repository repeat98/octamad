# The ColdFire port for the virtual front panel: milestones O14i-O24

Tim Hastie's records from his fork
[timhastie/octa-panel](https://github.com/timhastie/octa-panel) at
`be68244` (11-22 Sep 2026, branch `panel-ui`), carried over with the code
they describe (`tools/emu/ot_emu`, `tools/panel`) on 25 Sep 2026. The text
is his, unedited; the paths in it are this tree's. Comments in the port
that cite "COLDFIRE_PORT.md O15c" and the like point here.
`CONTEXT.md`, which the text cites, is his fork's session notes and
stays there.

Milestones O1-O14 (the port's own, 7-12 Sep 2026) are in
`git show 3ceba41:docs/history/COLDFIRE_PORT.md`. His O14i-O14k are not
our O14 (the gain chain): the letters are his.

What changed on the way in, and what did not come over, is in the PR that
ported it and in `tools/panel/README.md` "In octabam".

Confidence markers as in `CHIP.md`: ✅ measured, 🟡 inferred, ❌ retracted.

## Milestone O14i — `--interactive`: the port as the panel's emulator, with a real-time clock (11 Sep 2026, branch `panel-ui`)

The virtual front panel (`tools/panel`) drives route A one key at a time:
push `<row> <mask>` into UART A's receive queue, run 50 ms, decode what the
firmware sent the panel. `--interactive` gives the port the same surface
over a pipe, so the panel (or any script) can drive it instead of the
Python emulator without a change of contract. The boot, the mount and the
load are the batch code paths, unchanged, flag for flag; the loop starts
where the batch reports would have, and `quit` returns before them.

### The protocol (`main.cpp`, `serveInteractive`)

```
out/emu/ot_emu --interactive --image ... [--card IMG --mount --set S --project P] [--dsp] [--frame] [...]
```

boots exactly as today, prints one line `ready sample=<double> frames=<u64>`
to stdout, then reads one command per line from stdin and answers one line
per command, flushed. Integer arguments are decimal or `0x..` -- a leading
zero is NOT octal (`key 0x26 08` is mask 8; the first cut parsed with
`strtoull` base 0, so it answered `err usage` and `010` meant 8 -- fixed 11
Sep 2026, later the same day); `run`'s ms is any non-negative decimal
(`50`, `50.0`, `1e+03` as the panel's `:g` prints it); hex payloads
lowercase, no spaces.

| command | reply | does |
|---|---|---|
| `run <ms>` | `ok sample= frames= stop=<time\|gate\|fault\|illegal>` | `Rtos::run(ms, untilGate=false)`, idle skip included |
| `key <row> <mask>` | `ok` | `Uart::rxPush(row); rxPush(mask)` into UART A; the receive interrupt follows `Uart::irq()` |
| `knob <row> <delta>` | `ok` | row, then `delta & 0xff` (signed detent delta) |
| `tx` | `tx <hex>` | UART A's transmit bytes since the previous `tx` (the first answers everything since boot: the panel's whole screen is in it) |
| `peek <addr> <len>` | `peek <hex>` | `len` 1..4096; `Machine::mapped` first -- an unmapped address answers `err` instead of growing a zero page |
| `poke <addr> <hex>` | `ok` | same mapping rule |
| `frame on\|off` | `ok` | `Rtos::setFrame`; with `--dsp` the DSP-driven edge stays as configured (`frame on` is what arms it) |
| `status` | `status sample= ms= frames= frame= idle= wall=` | `wall` = seconds of wall clock spent INSIDE `run` since ready |
| `quit` | `ok` | exit 0 |

Anything else answers `err <message>` and the loop keeps serving -- an
empty line, an unknown word, the wrong number of arguments (`tx`, `status`
and `quit` take none: `tx extra` / `status now` / `quit please` answer
`err usage: ...` instead of ignoring the word, as the first cut did), a
number out of range or with a stray character; EOF on stdin exits 0.
Measured 11 Sep 2026: 33 malformed lines all answer `err`, `key 0x26 08` /
`0x26 010` / `38 0X1A` / `knob 0x30 -3` land `26 08` / `26 0a` / `26 1a` /
`30 fd` in UART A (read back through a peek of its data register), and
the queue is empty after the rejected ones. `run` is the only command that costs
emulated time. A `peek`/`poke` of a peripheral register is a real bus
access (a peek of UART A's data register consumes a received byte).

### ✅ The RTC on the DSPI (`periph.h`, `Dspi`)

Found 10 Sep 2026 under route A (`panel_server.install_rtc`), ported here:
on DSPI chip-select 2 the far end is a DS1390-style SPI real-time clock.
PUSHR is CONT (bit 31) | PCS (bits 21-16) | data (bits 15-0); the firmware
reads one register per transaction, `<reg> 00` with CONT held between the
two frames: 0x01 sec, 0x02 min, 0x03 hour, 0x04 weekday (1 = Monday), 0x05
date, 0x06 month, 0x07 year, all BCD, plus 0x00 hundredths and 0x0e status,
and one write `9e 07` at boot. Transactions are delimited by CONT, not by
counting frames (a boot-time one is three frames). Every other chip select
keeps the loopback (reply 0); on chip-select 2 the reply is the clock's
time, and a written register is remembered and answered back from then on
(the dialog's own SET sticks; that register no longer advances).

**`--rtc host|off|<epoch>`, and OFF is the batch default** (11 Sep 2026,
later the same day, after the verifier's diff). The first cut answered the
host clock unconditionally, in the batch too, and that broke the repo's
own oracle rule: the standard card-loaded batch (`--card otlive.img
--mount --set OTLIVE --project PROJECT --ms 1000 --serial-out --golden`)
had byte-identical stdout but its `serial_a` differed from the pre-RTC
binary at byte 5141 of 7325 (158 bytes: the dialog's date), two runs of
the same binary seconds apart differed from each other (44 bytes from
5211: the seconds), `oracle.py` on the two goldens exited 1 with `DIFFERS
serial_a`, and route A's stock `emu_rtos.Dspi` still answers 0 (only
`panel_server.install_rtc` has the model) -- so a route-A-vs-port oracle
on any loaded project reported a false fatal serial divergence. Now
`Dspi::RtcClock` is `Off` unless `--interactive` (then `Host`), and
`--rtc` picks explicitly (`main.cpp`, wired through `Dspi::setRtcClock`
before `Rtos::install`):

| `--rtc` | chip-select 2 | the dialog, OTLIVE loaded (looked at) | YES stores at `0x80000080` |
|---|---|---|---|
| `off` (the batch default) | the loopback: reply 0, nothing remembered -- the pre-RTC `Dspi::write`, byte for byte | `SUN 2000-00-00 00:00:00` | `07d0 00 00 00 00 00` |
| `host` (the `--interactive` default) | DS1390 registers from the host's local time | `FRIDAY 2026-09-11 20:58:15` (`otlive_boot.png`) | `07ea 09 0b 14 3a 0f` |
| `<epoch>` (seconds since 1970) | the same registers from that instant, decoded as UTC and frozen -- the same dialog on every machine, every run | `--rtc 1000000000`: `SUNDAY 2001-09-09 01:46:40` | `07d1 09 09 01 2e 28` |

A non-default mode prints one `rtc        :` line in the boot log; the
default batch prints nothing. Measured after the fix, the same batch
invocation, the fixed binary run twice: `serial_a` is byte-identical to
the pre-RTC binary's and run to run (`cmp` silent, 7325 bytes), stdout
identical (output paths aside), `oracle.py` base-vs-fixed and
run-vs-run both `8 compared field(s) agree`, exit 0; 19.9 s wall.

Under `--interactive` (`out/_agents/port/smoke.py --card
out/_agents/port/otlive.img`, `otlive_boot.png`): the SET DATE/TIME
dialog the boot opens reads **FRIDAY / 2026-09-11 / 20:58:15**, the host
clock at the time, over `LAST SET: 0000-00-00 00:00:00`; before this (and
in the batch, still) it reads 2000-00-00. YES writes the 7-byte clock
record at RAM `0x80000080` as **u16 year, u8 month, day, hour, minute,
second, binary** -- `07ea 09 0b 14 3a 0f`, the boot-time read, 17 s behind
the host by the time YES lands -- and draws DATE/TIME STORED
(`otlive_main.png`). `ctest` still passes 7/7: the rtos test's 4831-byte
serial prefix ends before the dialog's date is drawn (and the tests run
the batch default, the loopback).

### ✅ Speed, OTLIVE loaded, frame on (`out/_agents/port/measure.py`, 11 Sep 2026)

The M1 that runs the port; boot + load 19.2-19.3 s wall to `ready`
(277,821 samples = 6.3 s emulated). Tracks activated by poking pattern +84
+ 2330·t := 1 (pattern base = PART_PTR `[0x46c82456]` + CUR_PATTERN
`[0x80000004]` × 0x8ed8, here 0x400e21e0 + 0), CLOCK RECEIVE bit clear
(it already was), PLAY as the matrix key `0x25 0x01` / `0x25 0x00`.

| edge | idle, emulated ms per wall s | playing, emulated ms per wall s | emulated ms per 16th | wall s per 16th | sequencer |
|---|---|---|---|---|---|
| `--frame` (16-sample timer, `frame on` after the load) | 357 (5000 ms in 13.99 s; 13,782 frames = 2756/emulated s) | 356 (6008 ms in 16.88 s; 16,559 frames) | **125.2** (48 steps) | **0.352** | ✅ runs: the tick byte `0x800065b6` changed in 60/60 100-ms slices, the step byte 0..15 wraps every 2 s |
| `--dsp` (the cores' bank word is the edge; `frame on` arms it) | 134 (5000 ms in 37.36 s; 13,781 frames) | 132 (6007 ms in 45.43 s; 16,557 frames) | **125.2** (48 steps) | **0.946** | ✅ runs, identically: tick byte changed in 60/60 slices, same step trace; boot + load 30.3 s wall (the cores run through the boot) |
| `--dsp --frame-timer` (the cores run, the 16-sample timer is the edge) | 133 (5000 ms in 37.50 s; 13,782 frames) | 134 (6008 ms in 44.68 s; 16,559 frames) | **125.2** (48 steps) | **0.931** | ✅ runs: tick byte changed in 60/60 slices, same step trace; the timer's frame count (13,782, as `--frame`) at the cores' cost (boot + load 30.6 s); `out/_agents/port/dsptimer_measure.txt` |

Nominal at 120 BPM is 20.8 ms per tick and 125 ms per 16th, so under the
timer edge the port's sequencer runs at the firmware's own rate in emulated
time -- every one of the 2756 frame interrupts per emulated second is
delivered (the CPU is 3990 instructions per sample and the frame handler
fits). Route A at the same point delivers ~414 of them (`KEYMAP.md` "PLAY
through `/key`": ~840 emulated ms per step, ~15 wall s per step at 54-59
emulated ms per wall second); the port is **43x faster per wall second of
play and 6.7x closer to real time** on top of that. Idle with the frame
clock on costs the same as playing -- the frame handler is the load, not
the sequencer -- and `status idle=` shows the idle skip still runs between
frames (37,383 skips over the 5 s).

### What it does not do

- Nothing paces the receive bytes: a `key` lands both bytes at once, and
  the firmware's own double-tap and long-press timers see whatever spacing
  the client's `run`s give them (a tap is row+mask, ~60 ms, row+0, ~100 ms
  -- `smoke.py`'s `tap`).
- `run` blocks the pipe for its whole length; there is no interrupt, and a
  `fault`/`illegal` stop is permanent.
- Only UART A is exposed; the LED bitmap and levels, the LCD, are the
  client's to decode (`tools/panel/panel_link.py`).
- The sequencer-to-UI "trigs fired" message and the trig-row running light
  are the same open item as under route A (`KEYMAP.md`); the LCD position
  bar under the BPM redraws (8639 panel bytes over 6 s of play) but the trig
  LEDs do not chase.
- A written RTC register freezes; nothing advances it or rolls it over,
  and a pinned `--rtc <epoch>` is a constant: its seconds do not advance
  with emulated time (reproducibility over realism, by design).
- The batch does not read the RTC at all unless told to (`--rtc host`):
  a `--golden`/`--serial-out` capture past the dialog draw (~400 ms) is
  only reproducible because of that.

**Reproduce:** `.venv/bin/python3 out/_agents/port/smoke.py --card
out/_agents/port/otlive.img` (boot, ready, the protocol's error and
argument-parsing checks, YES, MIXER, tx -> PanelLink -> PNG, PLAY, 3 s, tx,
status, quit; ~28 s wall, exit 0; `--rtc off` / `--rtc 1000000000` pass
the mode through and the clock-record check follows it) and `measure.py
--tag frame` / `--tag dsp --dsp` / `--tag dsptimer --dsp --frame-timer`.
The card image is `stage_card.py` over `out/_projects/otlive/OTLIVE/PROJECT`
with its AUDIO pool (`--audio` per WAV, options before the positionals).

## Milestone O14j — the DMA timers, and the trig-row running light ✅ (12 Sep 2026)

The sequencer's running light never showed under any emulator. Two causes,
neither in the DSP path (identical LED timelines with `--frame` and `--dsp`):

- **Pattern byte +84 + 2330·t is PLAYS FREE, not "active".** `FW_TRANSPORT(0)`
  (the PLAY key, `0x4009bc76`) sets a track up only while that byte is ZERO;
  `FW_START_TRACK` (`0x4009b630`) is the trig-key start of a track whose byte
  is SET. The panel used to set the byte on all eight tracks before PLAY
  ("activate"), which is exactly what silenced the sequencer; the fixture
  project plays as saved with the bytes left clear. The "trigs fired" note is
  SYS command 22 (handler `0x400622da` = table[21] of the 78-entry sys
  dispatcher at `0x40061cfa`), built by the frame builder at
  `0x4000c832/0x4000c858`, drawn by `0x40043fdc` as timed `set_led` flashes;
  the running light follows the UI's CURRENT track (`0x100b14cc`).
- **The LED countdowns need the MCF5445x DMA timers.** `set_led(id, n)`
  (`0x40013784`) is a countdown of n ticks decremented by `0x4001387c` in the
  task pending on `0x46c7e0e2`, whose only signaller is the DMA-timer-1
  interrupt (vector `0x61`, DTRR 68750 / DTMR 0x1d = 8.333 ms at the 132 MHz
  bus; every second tick also posts 0x01 to the UI queue and 0x05 to sys). The
  port had no `0xfc07xxxx` model: flashes never cleared, LEDs 9-16 stayed lit.
  `DmaTimer` (periph.h/.cpp: four channels at `0xfc070000 + 0x4000·n`, INTC0
  sources 32-35, DTMR/DTXMR/DTER/DTRR/DTCR/DTCN, restart and free-run; gated in
  `test_periph.cpp`) fixes it. Cost: the firmware's own boot mount now runs
  (boot + fixture load 37.5 s wall, was 21 s; `--boot-logo` restores the
  faithful logo wait, `Rtos::Quirks::skipBootLogo` is the default) and play is
  ~11% slower from the 60 Hz UI/sys ticks. Batch stamps move ~140 samples
  earlier than pre-timer logs. DTIM0 counts the (unmodelled) DTIN0 pin.

Measured after: the lit trig pair equals the STEP byte `0x800065b5` in 84/84
25 ms slices at 125.1-125.2 ms per step (120 BPM); the eight fired-track
flashes at PLAY clear 83 ms later; STOP leaves the LED table all zero.

## Milestone O14k — the DSP main output over the `--interactive` pipe ✅ (12 Sep 2026, branch `panel-ui`)

The 12 Sep audio spike (`out/_agents/audio/`) proved the batch renders the
sequenced sample sample-exact with `--dsp`: `run3_core0.wav` slots 2/3 =
`third-0.wav` x 0.70 at `--main-level 64`. None of it reached the pipe, for
two reasons in `main.cpp`: `--audio-out` is written only after the batch
reports (`writeWav24`, one-shot, needs the total), and `--interactive`
returns into `serveInteractive` before them; and `--main-level` was posted
only inside `if(sequencer)`, so under `--interactive` the gain table
`0x80003c60` stayed zero and every voice rendered silent (O9b's trap).

### What changed (`main.cpp`, `dsp.h/.cpp`; the batch untouched)

- **`--main-level` defaults to 64 under `--interactive`** and is posted
  after the load, before `ready` (the same `Rtos::setMainLevelLive`, the
  same `main level :` boot-log line, up to 200 ms emulated); `--main-level
  off` (or a number, `0` included) overrides. The batch default stays -1
  (never posted): the reference command's `run3_core0.wav` and its log are
  byte-identical before and after (`cmp` silent; `out/_agents/port-audio/
  base_run3_core0.wav` from the pre-change binary vs `new_run3_core0.wav`,
  69 s wall each), and ctest passes 7/7.
- **A second, bounded capture on the same ESAI TX sink** (`dsp.cpp`, the
  de-rotated ring words of O9c; `DspPair::setAudioStream`): core 0 only,
  16-bit (the 24-bit word >> 8, `writeWav24`'s top two bytes), in a ring of
  `g_streamCapFrames` = 60 s x 44100 frames (10.6 MB for a pair, 42.3 MB
  for all eight), allocated at `audio start`, freed at `audio stop`. Full
  = the OLDEST frame is overwritten and counted. The batch's
  `setAudioCapture` vector is untouched beside it.

### The commands (`serveInteractive`; `err audio needs --dsp` without the cores)

| command | reply | does |
|---|---|---|
| `audio start [main\|cue\|all]` | `ok` | starts empty (restarts if on). `main` (default) = ring words 2/3 as L,R; `cue` = words 4/5 (the second pair, 3.1 dB lower); `all` = the eight words per frame (0/1/6/7 are zero on the fixture) |
| `audio read [<maxframes>]` | `audio <frames> <hex>` | everything pending (at most `<maxframes>`, 1..cap), little-endian signed 16-bit interleaved PCM, 2 (or 8) words per frame, lowercase hex; those frames are released. Never blocks: it answers what is there (`audio 0 ` when nothing is) |
| `audio status` | `audio status on=0\|1 mode=off\|main\|cue\|all captured=<frames since start> pending=<unread> rate=44100 dropped=<overwritten> cap=2646000` | |
| `audio stop` | `ok` | also when off |

Bad input answers `err` and the loop keeps serving (`audio` alone, `audio
start bogus`, `audio start main extra`, `audio read 0`, `audio read`
before a start). A 25 ms `run` is ~1100 frames = 4.4 KB = 8.8 KB of hex on
one line; a 100 ms one 4410 frames = 35 KB of hex.

### Measured (`out/_agents/port-audio/smoke_audio.py`)

`.venv/bin/python3 out/_agents/port-audio/smoke_audio.py` boots
`--interactive --dsp` on the spike's card (`otlive2.img`, OTLIVE/PROJECT),
checks the gain table at `ready`, the error answers, then YES, `frame on`,
the batch's trig (track 1 step 5 poked into the PART_PTR blob as
`--poke-trig 5` does), `audio start main`, PLAY as the matrix key `0x25
0x01`/`0x25 0x00` (the pattern's +84 bytes left clear, O14j), and `run 100`
+ `audio read` for 4 s emulated (one read split with `audio read 500`).
It writes `pipe_main.wav` (16-bit stereo) and `pipe_metrics.txt`, and
asserts: frames per emulated second = 44100 within 0.5 %, `captured = read
+ pending`, nothing dropped, no read over 1 s wall, the capture not silent,
`third-0.wav` L fits at the onset with a residual under -20 dB, and the
capture equals the batch's `run3_core0.wav` slot 2 after onset alignment
(residual under -20 dB). `--cap-test` instead runs 61 s emulated with no
read and asserts `pending = cap`, `captured = cap + dropped`, RSS growth
under 40 MB, and that exactly `cap` frames read back afterwards.

Measured 12 Sep 2026 (the M5 Mac of O14j; `pipe_run.txt`, `pipe_metrics.txt`,
`cap_run.txt`, `cap_cap_metrics.txt` beside the script):

| measurement | value |
|---|---|
| boot + fixture load to `ready`, `--dsp` | 58.6 s wall (`ready sample=277688`; the batch's same boot is O14j's 37.5 s plus the cores) |
| gain table `0x80003c60` at ready | `0xbf7fc081` (the boot log's `main level : sys command 4 posted with 64 -> gain table[0] = 0xbf7fc081`) |
| frames captured, 4.064 s emulated of PLAY | 179,213 over 40 reads = **44,099.9 per emulated second** (status `captured=179213 pending=0 dropped=0`) |
| wall, playing and reading every 100 ms | 37.4 s / 36.7 s (two runs) for 4.064 s = **9.0-9.2 wall s per emulated s** (109-111 emulated ms per wall s; O14i's `--dsp` play figure was 132, before O14j's timers) |
| longest `audio read` | 0.2 ms wall (4410 frames, 35 KB of hex); the `audio read 500` split answers exactly 500 |
| first sound | frame 81 = 1.8 ms after the PLAY key (the fixture pattern has a saved trig on step 1: PART_PTR blob bytes 6/7 = `01 01`) |
| `third-0.wav` L in `pipe_main.wav` | gain-only fit over the whole sample: frame 80 x 0.7134, residual -18.5 dB -- and the batch's own `run3_core0.wav` slot 2 fits the same, x 0.7140, -18.4 dB: the DSP voice FADES IN over ~256 samples (residual rms 1666 in the first 1024 samples, 40-160 after). From sample 256 on: **x 0.7032, -33.0 dB** (pipe) vs x 0.7032, -33.2 dB (batch) -- the spike's "x 0.70" |
| pipe vs the batch reference | the pipe's 9551 samples inside `run3_core0.wav` slot 2 at frame 282745: x 1.0005, **-30.1 dB**, 481 samples bit-identical; the residual is the attack (rms 446 in the first 1024, 1-42 in the rest against a signal of 2000-7600) -- the same voice, started by the PLAY key instead of `startTransportLive` |
| 61 s emulated with no read (`--cap-test`, `frame` off) | 26 s wall; `captured=2690147 pending=2646000 dropped=44147` = cap + dropped; RSS 1010 -> 1012 MB; the 2,646,000 frames read back afterwards in 500,000-frame reads; `audio stop` frees the ring |

The first run's fit was asserted on the whole sample and failed at -18.5 dB
on BOTH the pipe and the batch; the attack is the DSP's, not the pipe's,
and the script fits from sample 256 (`ATTACK`) and finds the batch lag by
search (its first non-zero sample is one frame before the pipe's). The
second run, with those fits, passes every check (`PASS`, exit 0, 98 s wall).

### What it does not do

- Core 1 is not captured (it puts out no ESAI frames on the fixture).
- 16-bit only over the pipe; the batch's `--audio-out` keeps the 24-bit
  words, and the two capture paths are independent (`--audio-out` under
  `--interactive` still writes nothing, as before).
- Nothing paces playback to wall time: at 9 wall s per emulated s the
  client that wants sound in real time buffers (60 s of ring) and plays
  what it has.
- `out/_agents/port/smoke.py` without a card fails 7 checks on this binary
  AND on the pre-change one (the O14j boot change: `ready` at sample 9083,
  the dialog not yet drawn); the only difference here is `ready` 139
  samples later (the main-level post).

Note (verifier, 12 Sep 2026): the `--main-level` default under `--interactive`
also moves the firmware's own main-level tick on the status bar (bottom right,
cols 104-108 of rows 59-61: col 108 = off/0, 107 = 32, 106 = 64, 105 = 100,
104 = 127) and adds one panel message; `--main-level off` reproduces the
pre-change screens byte for byte. RSS grows in bursts while the sequencer
plays regardless of the audio ring (pre-existing; ~+34 MB per 2 s slice
observed) -- a long playing session has not been measured.

## Milestone O15a — event-horizon bursts: the run loop 4.2x faster, bit for bit ✅ (12 Sep 2026, branch `panel-ui`)

The first step of the speed plan (`out/_agents/speed-plan/PLAN.md`, the
architect's plan from the read-only investigation of the same day). Before
it the port played at **215-220 emulated ms per wall s** without `--dsp` and
**97** with (`out/_agents/speed/bench.py`: boot on `otlive.img`, PLAY with
`frame on`, 16 x `run 250`); real time is 1000. Nothing the firmware does
may change: the gate is `out/_agents/speed-oracle/oracle.sh` (28 checks
against the frozen pre-speed binary `out/emu/ot_emu.ref-1e76ac5`: boot
logs, serial bytes, goldens, the O14k render WAV, the `--interactive` UART
stream, peeks and run stamps, the `--dsp` pipe PCM, ctest).

### What changed (`rtos.cpp/.h`, `periph.h`, `machine.cpp/.h`; no CLI change)

The old loop called `tickTimers()` and `deliver()` after EVERY instruction:
two PIT advances, four DTIM advances, the frame edge, the eDMA's due list,
the ATA latency, then the two INTCs' `top()` -- 26 `std::function` line
probes -- to re-offer or withdraw an interrupt. Both are pure functions of
the models' state and the sample clock, so between two instructions that
change neither they are no-ops. Every way that state CAN change is now
either flagged or timed, and `Rtos::runInternal` runs **bursts**:

- `nextEvent()` = the earliest of: every armed PIT expiry (PIE or not --
  PCSR reads back PIF), every armed DTIM reference match (`DmaTimer::
  nextMatch`, new: ORRI or not -- DTER.REF reads back), `m_nextFrame` while
  `m_frame || m_frameFromDsp` (otherwise `tickTimers()` never touches it and
  the eDMA boundary it publishes is a constant), `m_ataIrqDue`, and
  `Edma::nextDue` (new) -- the earliest booked completion, gated ones
  included: a due-but-gated entry answers a sample already past, which
  forces exact stepping until it clears, because the gate is the DSP's ring
  and is re-asked after every instruction.
- A burst is up to N = min(4096, floor((nextEvent - m_sample) * ips) - 2,
  the run's end) instructions doing only stepOnce's own per-instruction work
  (the PC ring when armed, the create record at `g_create`, the dispatch
  record after the scheduler's `rte`, the first-handoff record, `m_sample +=
  1/ips` -- the same add in the same order, so every stamp is bit-identical
  -- and `Machine::stepFast()`); `tickTimers()` + `deliver()` once at its
  end. The exact tail then steps instruction by instruction across the
  event, so every timer fires on the same instruction as before.
- A burst ends early on: any peripheral access (`Machine::peripheralRead/
  Write` set `m_periphTouched` -- the models, the boot's override table, the
  card window, the co-processor), an interrupt acknowledgement (the ack
  hook sets `m_wake`: the core consumed the injected vector and `deliver()`
  must re-offer or withdraw), the DSP's host-word hook (`m_wake`: a frame
  edge the horizon cannot see), the PC landing on main's spin after at
  least one instruction (the idle skip gets its look, as the old loop
  checked before every instruction), and `runInternal` entry (`m_wake =
  true`: keys pushed, memory poked, the frame switched between runs are
  delivered after the run's first instruction, as before). An early end is
  always exact -- it calls the pair where the old loop called it too.
- **The list of everything that can change deliverable state** (beside
  `Intc::addLine` in the constructor, as the plan asked; also the comment on
  `Rtos::nextEvent`): a peripheral WRITE (INTC masks/forces/ICRs, PIT and
  DTIM control and acks, eDMA kicks/CINT/CDNE, UART masks, the card's
  command and data registers, the DSPI, the host port) -> touched; a
  peripheral READ with a side effect (UART +0x0c pops the receive queue
  and its line, the card's STATUS clears INTRQ and a DATA read re-arms it,
  DSPI POPR, the host port) -> touched; the CPU acknowledging a vector ->
  wake; the DSP's bank word -> wake; the outside world between runs -> wake
  at entry; TIME (the six sources above) -> the horizon. The DSP cores'
  state reaches the ColdFire only through the host port (a read), the
  eDMA gate (a due entry) and the host-word hook; their per-instruction
  tick is unchanged inside a burst, so the O12 interleave does not move.
- **The mandatory fix the architect found in the prototype**: `Edma::
  setBoundary(m_nextFrame)` and `setNow(m_sample)` are refreshed before
  EVERY eDMA register access in BOTH `Rtos::peripheralRead` and
  `peripheralWrite`. The prototype did it on reads only; a CSR.START kick
  is a WRITE and `Edma::start` books its bus-paced completion from
  `m_now`, so with `m_now` stale by up to a burst the DSP took its block
  early and the `--dsp` pipe PCM drifted by +-1 LSB in 280 samples
  (`interdsp.pcm` FAILED, 27/28). The refreshed value is the exact path's:
  `tickTimers()` set it from `m_sample` after the previous instruction, and
  `m_sample` has not moved since (the increment follows the instruction).
- `Machine::stepFast()`: `step()` minus three costs -- the PC through
  `m68k_get_reg` (now `pcFast()`: a pointer to the CPU state's `pc` field,
  taken once at construction; measured at ~12 % of the burst loop's samples
  when it was an out-of-line call into an out-of-line `getCpuState()` three
  times per instruction), the opcode through the region walk (the SDRAM
  region's bytes are read directly while the PC is inside it; `read16`
  otherwise, so the alias window, a grown page and a PC in a peripheral
  behave as before), and `Mc68k::exec()`'s legacy GPT/SIM/QSM pass
  (`execInstruction()` runs the core alone). ⚠️ That last one is exact
  only because the legacy models are unreachable on this machine: they are
  addressed through `Mc68k::read*/write*`, which `Machine` overrides
  wholesale and never forwards to, so TMSK1 stays 0, PITR is never written
  and there is no SCI/QSPI traffic -- none of them can ever inject an
  interrupt (documented in `machine.h`; `OT_STEPFAST=0` is the bisect knob
  and the architect's bisect of the prototype cleared it). The instruction
  count, PC watch, profile, A-line pre-decode into the V4e layer and the
  co-processor's one tick per instruction are kept exactly.
- **Kept exact per instruction**: `run(_ms, untilGate=true)` (the batch's
  M6a gate), `runUntil` (the render's frame predicate, `runToPc`),
  `callAsMain`, `runToMainSpin`, `loadProjectLive`'s mount wait -- plan
  step 6 extends them. The bursts apply to `run(_ms, false)`: every
  `--interactive` `run`, and the load's own 6 s run.
- **Knobs and stats, stderr only, opt-in** (the batch stdout is diffed byte
  for byte): `OT_BURST=<quantum>` (default 4096; `0` = the pre-O15a loop),
  `OT_STEPFAST=0` (`Machine::step` inside bursts), `OT_BURST_STATS=1`
  (one `burst stats:` line on stderr when the `Rtos` is destroyed:
  bursts, instructions inside them, exact instructions, how bursts ended
  -- periph / wake / horizon / spin -- idle skips, the instruction count,
  the knobs). `Rtos::burstStats()` exposes the same counters. No command,
  reply or log line changed.

### Measured (12 Sep 2026, the M5 Mac of O14j, macOS 26.5; logs under `out/_agents/impl-1-bursts/`)

Reference = `out/emu/ot_emu.ref-1e76ac5`, candidate = this tree, both run
in the same session with no other emulator running (an unrelated 25-day-old
Python process at 100 % of one core was present throughout, as it was for
the baselines). `bench.py` unless said otherwise.

| measurement | reference | candidate | ratio |
|---|---|---|---|
| play, no `--dsp` (emulated ms per wall s) | 217, 220, 215 | **904, 913** (920 with `bench_cmp.py`, no `sample` profiler) | **4.2x** |
| play, `--dsp` | 97 | **132** (138 with `bench_cmp.py`) | **1.36-1.42x** |
| boot + fixture load to `ready`, no `--dsp` | 39.2-39.3 s | **10.3-10.5 s** | 3.8x |
| boot + fixture load to `ready`, `--dsp` | 58.2 s | **28.8-29.0 s** | 2.0x |
| oracle `card` batch (`--ms 1000`, under the parallel battery) | 49.6 s | 12.0 s | 4.1x |
| oracle `render` (O14k reference, 3000 frames `--dsp`) | 91.1 s | 41.7 s | 2.2x |
| oracle `inter` boot / 4490 ms of `run` | 45.4 s / 21.1 s | 11.9 s / 4.6 s | 3.8x / 4.6x |
| oracle `interdsp` boot / `run` | 68.4 s / 52.6 s | 30.8 s / 31.4 s | 2.2x / 1.7x |

The first pass (before `pcFast` was inlined) measured 709-766 no-dsp and
130-134 `--dsp`, ready at 12.2-12.7 s; the second pass is what ships. The
`--dsp` figure is the plan's ceiling for this step: the cores are ~50 % of
the wall and their interleave cannot change (O12).

**The gate: 28 PASS, 0 FAIL, twice** (`out/_agents/speed-oracle/reports/
20260912-070039-impl1-bursts.txt` for pass 1, `20260912-071233-impl1-bursts-b.txt`
for pass 2): boot logs identical, `serial_a` 5731 / 9257 bytes identical,
goldens 12,757 / 26,367 bytes identical, `run3_core0.wav` 7,936,292 bytes
identical, the UART A stream 18,297 / 18,309 bytes identical step by step,
109 peeks identical, 47 run stamps with max |dsample| = 0 and |dframes| =
0, **`interdsp.pcm` 497,788 bytes identical**, ctest 7/7 with the tests
built in the candidate tree (`out/_agents/impl-1-bursts/build`, `rtos`
run from the repo root). `bench_cmp.py`'s fingerprint (every reply, the
whole UART stream hashed, the peeks, a MIXER key pushed in the middle of
play for the rxPush-then-wake path) is IDENTICAL to the pre-speed control's
(`out/_agents/speed-cpu/fp_control_rtc.fp.json`, `fp_dsp_control_rtc.fp.json`),
with and without `--dsp`.

**What the bursts do** (`OT_BURST_STATS=1`, the whole `bench_cmp.py`
session, boot + 4 s of play): without `--dsp`, 14,258,883 bursts covered
1,084,851,615 of 1,146,675,308 instructions (94.6 %; the rest is the boot
before the handoff and the load's borrowed calls), 11,500 went through the
exact tails; bursts ended on a peripheral access 13,810,549 times (96.9 %),
a wake 167,644, the horizon 227,059, main's spin 53,631; 53,665 idle
skips. **The mean burst is 76 instructions**: the firmware polls its
peripherals constantly (UART status, INTC IPR, DTIM3's timestamp, the host
port), and every such read ends a burst. With `--dsp`: 14,171,369 bursts,
1,051,929,979 instructions, and 32,933,949 exact instructions (2.9 %) --
the gated eDMA completions holding the exact path while the DSP drains.
The counts are identical between the two passes (the loop restructure
changed no decision).

### What it does not do

- A side-effect-free peripheral read (a status poll, an IPR read, a DTCN
  timestamp) still ends the burst; letting those through needs a
  per-register classification and is not in the plan.
- The gated, predicate and borrowed-call runs are still exact per
  instruction (plan step 6); memory access still walks the region list
  (step 3); no LTO/PGO (steps 2, 4).
- Nothing paces playback to wall time (plan step 7); at 0.9x real time the
  panel's idle pump and `run`s simply finish sooner.
- Route A is not the oracle here; the 28 checks are port-vs-port against
  the frozen binary, as the speed-oracle README says.

## Milestone O15b — link-time optimisation: +11 % on top of the bursts, bit for bit ✅ (12 Sep 2026, branch `panel-ui`)

Step 2 of the speed plan; `tools/emu/ot_emu/CMakeLists.txt` only, no
source change. The run loop crosses a library boundary on every
instruction (`m68kops.c` -> `m68k_read_memory_*` -> `Machine::read*`,
Musashi's `execute_one` -> `Machine::stepFast`), and a per-translation-unit
build cannot inline across it. The speed-mem investigation measured full
`-flto` at 1.17x on the pre-burst code; this lands it in the build.

**What changed.** `option(OT_LTO ON)` + `OT_LTO_MODE full|thin` (cache
string), set BEFORE the `add_subdirectory` calls so the vendored targets
inherit it: `include(CheckIPOSupported)` / `check_ipo_supported(LANGUAGES C
CXX)` guards it (a toolchain without LTO builds as before and says so at
configure), then `CMAKE_INTERPROCEDURAL_OPTIMIZATION_RELEASE` (and
`_RELWITHDEBINFO`) `ON`. CMake's AppleClang default for IPO is
`-flto=thin` (`Modules/Compiler/Clang.cmake`); in `full` mode
`CMAKE_C/CXX_COMPILE_OPTIONS_IPO` are overridden to `-flto` so the whole
program is one module at link time, as the investigation measured. Verified
on the verbose build (`out/_agents/impl-2-lto/build.build.log`): `-flto` on
109 of 167 compile lines -- all of `68kEmu` (`m68kops.c`, `m68kcpu.c`,
`mc68k.cpp`, ...), `dsp56kEmu`, `dsp56kBase`, `ot_machine`, `ot_emu` and
the test programs -- and on every link line (`-O3 -DNDEBUG -flto -arch
arm64 ... -o ot_emu`). The 58 without it are `asmjit` (its own
`cmake_minimum_required(VERSION 3.5)` leaves policy CMP0069 OLD in that
subtree, so the property is ignored there; asmjit is the JIT's assembler and
is not on the interpreter's path). `OT_LTO=OFF` reproduces the pre-change
build exactly (no `-flto` anywhere, `ot_emu` 2,789,704 bytes as before) --
the bisect knob. Default `cmake --fresh -B out/emu -S tools/emu/ot_emu &&
cmake --build out/emu -j8` now builds with full LTO; nothing else changed:
no CLI, command, reply or log line.

**Measured** (12 Sep 2026, the same M5 Mac, macOS 26.5, AppleClang 21.0.0,
CMake 4.4.3; `bench.py`, all four binaries in one session, one after the
other, no other emulator running; logs `out/_agents/impl-2-lto/impl2_*.log`,
`bench_series.txt`). Reference = `out/emu/ot_emu.ref-1e76ac5`; Step 1 =
this tree at commit `cada0f2`, rebuilt as `build-pre` with `-DOT_LTO=OFF`;
LTO = `build` (full); thin = `build-thin` (`-DOT_LTO_MODE=thin`).

| measurement | reference | Step 1 (no LTO) | **full LTO** | thin LTO |
|---|---|---|---|---|
| play, no `--dsp` (emulated ms per wall s) | 217 | 879, 874 | **977, 977** | 978, 976 |
| play, `--dsp` | 96 | 132, 135 | **147, 147** | 144 |
| boot + fixture load to `ready`, no `--dsp` | 39.5 s | 10.4-10.7 s | **9.8-10.1 s** | 9.6-9.7 s |
| boot + fixture load to `ready`, `--dsp` | 60.9 s | 28.6-29.0 s | **26.7-27.4 s** | 26.9 s |
| `ot_emu` size (bytes) | 2,788,712 | 2,789,704 | **2,273,512** (-18.5 %) | 2,384,360 |
| link step of `ot_emu` alone (re-link, warm) | -- | 0.35-0.56 s | **5.4-5.7 s** | 1.8-2.1 s |
| full `--fresh` configure + build, `-j8` | -- | 15.3-16.7 s | **19.3 s** | 16.7 s |

Ratios: full LTO over Step 1 **1.115x** without `--dsp` (977 / 876.5) and
**1.10x** with (147 / 133.5) -- the plan asked for >= 1.08x on the burst
binary and estimated >= 1.1x; over the reference in the same session
**4.5x** (977 / 217) and **1.53x** (147 / 96). Thin LTO ties without the
cores (976-978) and is 2 % slower with them (144 vs 147) for a 3x faster
link; full stays the default, as the plan says. The `--dsp` gain is
smaller, as O15a's was: the cores are ~50 % of the wall (speed-dsp's
profile) and their interleave cannot change, so only the ColdFire half
speeds up. `lib68kEmu.a` grows 1,097,752 -> 1,500,856 bytes (bitcode, not
machine code, until the final link).

**The gate: 28 PASS, 0 FAIL** (`out/_agents/speed-oracle/reports/
20260912-075538-impl2-lto.txt`, copy in `out/_agents/impl-2-lto/oracle1-
report.txt`; 57 s wall): boot logs identical, `serial_a` 5731 / 9257 bytes
identical, goldens 12,757 / 26,367 bytes identical, `run3_core0.wav`
7,936,292 bytes identical, the UART A stream 18,297 / 18,309 bytes
identical step by step, 109 peeks identical, 47 run stamps with max
|dsample| = 0 and |dframes| = 0, `interdsp.pcm` 497,788 bytes identical,
ctest 7 / 7 in the LTO tree (also 7 / 7 in `build-pre` and `build-thin`).
Under the parallel battery the candidate's jobs took: `card` 10.6 s (Step 1:
12.0 s), `render` 37.7 s (41.7), `inter` boot 10.9 s + 4.2 s of `run` (11.9
+ 4.6), `interdsp` 28.0 s + 28.2 s (30.8 + 31.4). Floating-point results
did not move: the DSP pipe PCM and the render WAV are the sensitive
outputs, and both are byte-identical (`-flto` adds no fast-math or
reassociation flag; the compile lines are otherwise unchanged).

**What it does not do.** No PGO yet (step 4 of the plan adds
`OT_PGO_PROFILE=<path>` in this file); no page-table memory path (step 3);
asmjit is not LTO'd (not needed -- the JIT is not used). Every build now
pays 5-6 s at the link for `ot_emu` and again for each test program (four
in this tree, three in `vendor/mc68k`); a tree that iterates on one source
file re-links everything through LTO -- configure with `-DOT_LTO=OFF` for
that. Debug builds (`-DCMAKE_BUILD_TYPE=Debug`) are untouched. Route A and
the panel server are not affected (the server builds `out/emu` with the
default configure, so it gets the LTO binary).

**Verified** (`out/_agents/impl-2-lto-verify0/`, the same Mac, later the
same morning): a fresh default configure + build reproduces the builder's
`ot_emu` byte for byte (sha256 `b25c12b6…`, 2,273,512 bytes; LLVM bitcode
in every `68kEmu`, `dsp56kEmu`, `dsp56kBase`, `ot_machine` and `ot_emu`
object, Mach-O only in asmjit); a build from a source copy with the
`option(OT_LTO ...)` line commented out reproduces the Step 1 binary byte
for byte (2,789,704 bytes, no `-flto`); a Debug configure carries `-flto`
in nothing but CMake's own IPO probe. Oracle rerun with `--fresh` (both
sides re-executed): **28 PASS, 0 FAIL**, 111 s. Bench, serial, in one
session: no `--dsp` reference 218, no LTO 942 / 911, **LTO 1027 / 1010**
(1.10x, 4.7x the reference; ready 10.3-10.4 s -> 9.4 s); `--dsp` reference
99, no LTO 135 / 136, **LTO 147 / 148** (1.09x, 1.49x; ready 28.3-28.7 s ->
26.4-26.5 s). ctest 7 / 7 in both trees; the vendored `dsp56kTestRunner`
(EXCLUDE_FROM_ALL) also links under LTO.

## Milestone O15c — the page-table memory fast path: +28 % on top of bursts + LTO, bit for bit ✅ (12 Sep 2026, branch `panel-ui`)

Step 3 of the speed plan; `machine.h` / `machine.cpp` only, no CLI change.
Every memory access the core makes -- the opcode fetch, the immediates,
every operand read and write -- went through `Machine::read*`/`write*`,
and each of those walked the region list: `isPeripheral` over three
windows, the `alias()` fold, then `find` over up to twelve `Region::
contains` checks (the boot map's six plus the six `Rtos::install` and
`mapCardMemory` add). The speed-mem investigation clocked that at 2.6 ns
per opcode fetch and 15-31 ns per data access on the pre-burst binary and
found the memory callbacks at 28 % of the burst loop's samples; its
prototype (`out/_agents/speed-mem/patch_fast.py`) measured 1.11x on the
pre-burst code with the oracle at 28 PASS. This lands it.

### What changed (`machine.h/.cpp`)

- **`m_pages`**: one host pointer per 4 KB page of the 4 GB address
  space (1 << 20 entries, 8 MB), rebuilt by the constructor after the
  boot map is laid out and by every `mapRegion`. The inline `read8/16/32`,
  `readImm16` and `write8/16/32` in the header index it with `addr >> 12`
  and, when the entry is non-null, read or write the bytes in place
  (`memcpy` + `bswap`, big-endian as the region bytes are). `stepFast`'s
  O15a special case -- the SDRAM region's bytes read directly while the
  PC was inside it -- is gone: the inline `read16` IS that direct read,
  now for every page in the table.
- **The rule for an entry, `find`'s page by page** (`rebuildPageTable`):
  the FIRST region in list order that touches a page claims it, and the
  page gets an entry only if that region covers all of it -- so no
  non-straddling access inside the page could resolve to any other
  region. A region that covers a page only partly claims it with NO
  entry, and a later region cannot take it: `find` would have answered
  the earlier one for the bytes both hold. (On this machine's map no two
  regions overlap, so the rule reduces to "one region covers the page";
  it is written the conservative way so a future `mapRegion` cannot make
  the table disagree with `find`.)
- **Never in the table**: a peripheral window (`isPeripheral` is checked
  per page; `assert`ed, and the guard leaves the entry null in a Release
  build regardless), a page this machine grew on its own (every access
  to one goes through `noteUnmapped`, whose count is in the boot log and
  in `test_rtos` -- so a grown page must keep taking the slow body), and
  anything unmapped.
- **The alias window** 0x48000000-0x4fffffff: the first pass skips the
  two regions mapped inside it (the boot's 1 MB at 0x48000000 and the
  card's 127 MB at 0x48100000 -- unreachable since 9 Sep 2026, because
  `alias()` folds every access out of the window before `find` runs), the
  second pass copies each alias page's entry from the page 0x08000000
  below. A write through 0x4fxxxxxx lands in the 0x47xxxxxx bytes as
  before; the O6 ring-clear and loader findings hold.
- **Everything else takes the ORIGINAL body, renamed `*Slow`**: a null
  entry (peripheral, grown, unmapped), an access that straddles a page
  (`(a & 0xfff) > 0xffe` for 16-bit, `> 0xffc` for 32-bit -- `find`
  answers those with the region-end and auto-map rules, so they are left
  to it), and every write while a write watch is armed (`addWriteWatch`
  sets `m_writeSlow`; watches are never removed). The Slow bodies are the
  pre-O15c code line for line: `isPeripheral` -> `peripheralRead/Write`
  (with `m_periphTouched`, the logs, the trace, the host-port log), the
  fold, `find`, `noteUnmapped`, the auto-map with its limit and
  `badWrite`. The only edit inside them is that `++m_writes` (the boot's
  stall detector's store counter) moved into the inline wrappers, their
  sole callers, so it counts every write as before.
- `readImm16` is the inline `read16` (it was an out-of-line call to it).
  `fastPages()` reports the table's population; nothing prints it.

### Checked beyond the gate (`out/_agents/impl-3-memory/pagecheck.cpp`)

A standalone program against the built `libot_machine.a`: the boot map,
then `Rtos::install`'s two spans, then `mapCardMemory`'s four, checking
the table's population against the map by hand (36,896 pages after the
boot map = 20,512 region pages + 16,384 alias copies; 37,393 after
install; **70,401** with the card: 37,633 + 32,768 -- the whole
0x40000000-0x47ffffff span is then covered, so every alias page has an
entry), then 2,000,000 random accesses over every region and through the
alias, one in seven placed to straddle a page: `read8/16/32` equal to
`read8/16/32Slow` at every one, writes through the inline path read back
through the Slow body and vice versa, the PLL override whole through
`read32` and `read16`, an unmapped address counted on every access and
grown once (and not entering the table), a write watch hit through the
inline wrappers including via the alias. **0 mismatches.**

### Measured (12 Sep 2026, the same M5 Mac, macOS 26.5, AppleClang 21.0.0; logs under `out/_agents/impl-3-memory/`)

`bench.py`, all three binaries in one session, interleaved, one after the
other, no other emulator running (`bench_series.sh` -> `bench_series.txt`,
`impl3_*.log`). Reference = `out/emu/ot_emu.ref-1e76ac5`; Step 2 = this
tree at commit `3055b36` (bursts + LTO), built here as `build-pre` before
the patch landed; Step 3 = `build`. The `ready sample=277688.167` stamp is
identical in all ten runs.

| measurement | reference | Step 2 (bursts + LTO) | **Step 3 (+ page table)** |
|---|---|---|---|
| play, no `--dsp` (emulated ms per wall s) | 221 | 1026, 984 | **1292, 1287** |
| play, `--dsp` | 99 | 144, 148 | **150, 149** |
| boot + fixture load to `ready`, no `--dsp` | 39.0 s | 9.8-9.9 s | **7.4 s** |
| boot + fixture load to `ready`, `--dsp` | 57.5 s | 26.5-27.7 s | **25.1-25.7 s** |
| `ot_emu` size (bytes) | 2,788,712 | 2,273,512 | 2,522,328 |

Ratios: Step 3 over Step 2 **1.28x** without `--dsp` (1289.5 / 1005) --
the plan asked for >= 1.12x and estimated 1.15-1.25x on the burst binary
-- and **1.02x** with (149.5 / 146); over the reference **5.8x** (1289.5 /
221) and **1.51x** (149.5 / 99). Playback without the cores is now
**1.29x real time** (a 16th at 120 BPM in 0.097 s wall). The `--dsp` gain
is exactly the ColdFire's share: at Step 2 an emulated second with the
cores costs 6.85 wall s, of which the ColdFire side is ~1.0 s (the no-dsp
figure) and the two DSP interpreters the rest; cutting the ColdFire side
by 1.28x predicts 151 emulated ms per wall s, measured 149.5. The cores'
interleave cannot change (O12), so the `--dsp` figure stays bounded by
them, as O15a and O15b said. Ready is 1.33x faster (the boot and the
6 s load are the same instructions, now with the cheaper fetch).

**The gate: 28 PASS, 0 FAIL** (`out/_agents/speed-oracle/reports/
20260912-082136-impl3-memory.txt`, copy in `out/_agents/impl-3-memory/
oracle1-report.txt`; 55 s wall): boot logs identical, `serial_a` 5731 /
9257 bytes identical, goldens 12,757 / 26,367 bytes identical,
`run3_core0.wav` 7,936,292 bytes identical, the UART A stream 18,297 /
18,309 bytes identical step by step, 109 peeks identical, 47 run stamps
with max |dsample| = 0 and |dframes| = 0, `interdsp.pcm` 497,788 bytes
identical, ctest 7 / 7 in the candidate tree (also 7 / 7 standalone,
`ctest.txt`). Under the parallel battery the candidate's jobs took:
`card` 8.9 s (Step 2: 10.6 s; reference 46.1 s), `render` 36.9 s (37.7),
`inter` boot 8.6 s + 3.2 s of `run` (10.9 + 4.2), `interdsp` 26.5 s +
27.7 s (28.0 + 28.2). The build carries only the vendored `-Wswitch`
warnings; nothing from `machine.*`.

Verified independently (`out/_agents/impl-3-memory-verify0/`): a fresh
build of this tree (byte-identical binary, sha `e298c877…`) and of commit
`3055b36` in the same session, `bench.py` interleaved with nothing else
running: no `--dsp` reference 223, Step 2 1008 / 1004, **Step 3 1375 /
1312** (1.34x); `--dsp` 99, 147 / 149, **151 / 151** (1.02x); ready
7.2-7.4 s vs 9.6-10.0 s, the stamp identical in all ten runs. Oracle
`--fresh` (both sides rerun) 28 PASS / 0 FAIL (`reports/20260912-084127-
impl3-verify0.txt`); ctest 7 / 7; an adversarial program over the table
(`adv.cpp`, 175 checks: every peripheral page null and every access to the
three windows reaching `peripheralRead/Write`, the overrides, both alias
ends, region-end and in-region straddles proven slow by swapping the page
entry for a scratch buffer, grown pages counted per access and entering the
table only through `mapRegion`, a later region overlapping an earlier one
losing the shared pages, write watches through the wrappers and the alias)
0 failures; the `watchmem` / `writes` / `watch` / `hits` / `poke` replies
of a YES-PLAY-STOP script byte-identical to the reference's (312 lines).

### What it does not do

- A grown (auto-mapped) page is still a slow access, by design: its
  per-access count is a finding, not overhead. With a card attached the
  golden path makes 4 such accesses at three boot-time addresses (O7:
  `0x04020000`, `0x100a0000`, `0xffff0000`), so nothing on the oracle's
  path is left slow except the peripherals and those four.
- A peripheral access is exactly as expensive as before, and still ends
  the burst (O15a).
- No PGO (step 4), no `m68k_execute(N)` hook (step 5); the gated and
  predicate runs are still exact per instruction (step 6).
- The table is rebuilt whole on every `mapRegion` (8 MB written, seven
  times per boot: the constructor and the six `mapRegion`s); it costs
  nothing measurable and keeps the rule in one place.

## Milestone O15d — profile-guided optimisation, opt-in: +28 % on top of bursts + LTO + page table, bit for bit ✅ (12 Sep 2026, branch `panel-ui`)

Step 4 of the speed plan; `tools/emu/ot_emu/CMakeLists.txt` and a new
`tools/emu/ot_emu/pgo.sh`, no source change, no CLI change. The compiler
already inlines across the whole program (O15b) and the memory path is a
table lookup (O15c); what it still guesses at is which branches are hot --
which of Musashi's 1,968 opcode handlers the firmware actually runs, which
of `DspPair::stepCore`'s paths the cores take, where `Rtos::runInternal`'s
burst loop leaves. A profile answers that. The speed-mem investigation
measured +12 % over LTO on the pre-burst code (1.31x vs 1.17x) and 1.33x
with `--dsp` on its own fast+LTO prototype; this lands the build option and
the ritual that makes the profile.

### What changed (`CMakeLists.txt`, `pgo.sh`)

Two cache knobs, both OFF by default, set BEFORE the `add_subdirectory`
calls so the vendored cores inherit them (directory-scoped
`add_compile_options` / `add_link_options`; nothing here names a vendored
target):

- `-DOT_PGO_GENERATE=ON`: `-fprofile-instr-generate` on every compile and
  link line (verified on the verbose build: 167 of 167 compile lines, the
  `ot_emu` link line). The binary writes an LLVM `.profraw` to
  `$LLVM_PROFILE_FILE` when `main` returns -- `quit`, EOF on stdin, the end
  of a batch run (`main.cpp` returns, it never `_exit`s).
- `-DOT_PGO_PROFILE=<.profdata>`: `-fprofile-instr-use=<path>` on every
  compile and link line (167 / 167 and the links), FATAL_ERROR if the file
  does not exist, exclusive with GENERATE. Clang's per-file noise is
  silenced -- `-Wno-profile-instr-unprofiled` (a file the training never
  ran: 40 lines, all asmjit, the DSP JIT `jit*.cpp`, the vendored unit
  tests, `test_emac` / `test_dsp`) and `-Wno-backend-plugin` (the
  per-function "hash mismatch" of a stale profile) -- while
  `-Wprofile-instr-out-of-date` stays visible: one line per file whose
  functions no longer match the profile, i.e. "regenerate". With a FRESH
  profile 22 such lines remain and are expected: the 19 `jit*.cpp` files
  (header-defined functions the JIT shares by name with the interpreter and
  compiles differently; the JIT is never run) and the test programs whose
  `main` collides with `ot_emu`'s. `-DOT_PGO_WARNINGS=ON` shows all three
  (the acceptance check of the plan: NO `profile-instr-unprofiled` on
  `machine` / `rtos` / `periph` / `v4e` / `dsp` / `card` / `main` /
  `m68kops` / `m68kcpu` / `mc68k` -- verified on a `-j1 --verbose` build,
  `out/_agents/impl-4-pgo/build-warn.build.log`).
- `-fprofile-instr-use` changes code placement only -- inlining decisions,
  block layout, branch weights, register allocation hints; it adds no
  fast-math, no reassociation, no flag the DSP's floating point could see.
  The oracle is run on the result all the same (below).

`tools/emu/ot_emu/pgo.sh` is the whole ritual in one command (`bash
tools/emu/ot_emu/pgo.sh`, 2 min 19 s wall on this Mac): (1) the
instrumented build into `out/emu-pgo-gen` (23 s); (2) two training runs on
that binary with `LLVM_PROFILE_FILE=out/emu-pgo/raw/<tag>-%p.profraw` --
the `bench.py` sequence (boot on `out/_agents/port/otlive.img` with the
OTLIVE project, `frame on`, PLAY, 16 x `run 250`, `quit`), once without
the cores (ready 12.9 s + 4.7 s of play, instrumented) and once with
`--dsp` plus `audio start main` / `audio read` after every run so the pipe
path is in the profile too (38.6 s + 37.7 s); (3) `llvm-profdata merge`
(found via `xcrun -f llvm-profdata`, overridable with `LLVM_PROFDATA=`)
into `out/emu-pgo/ot_emu.profdata` -- 2 x 944,272 B raw, 1,443,552 B
merged, 9,819 functions, 26,091 blocks, 3.28 x 10^11 counts; (4) the
optimised build into `out/emu` with `-DOT_PGO_PROFILE=` (18 s), which is
the operator's binary: the panel server picks it up unchanged. Options:
`--dest` / `--gen` / `--prof` / `--card` / `--image`, `--no-dsp` (skip the
long training run), `--skip-train` (rebuild with the profile on disk),
`--clean-gen` (the instrumented tree is kept by default so a different
training sequence needs no rebuild), `-j N`. It refuses to finish with an
instrumented binary in `--dest` (`otool -l` for `__llvm_prf_*`) or one of
the wrong architecture, and it refuses to finish with an object in
`--dest` older than the profile (the re-run finding below).

**The profile is build-host specific and goes stale.** It belongs to this
compiler (AppleClang 21.0.0), these flags and the source bytes it was
collected on; clang matches it function by function by name and CFG hash.
After ANY change under `tools/emu/ot_emu` or `vendor/{mc68k,dsp56300}`
run `pgo.sh` again (re-running it into a tree that already holds a PGO
build is the normal case and is safe -- since fix1 below; the first
version of the script failed exactly there) -- a function whose hash
moved simply gets no weights, so a stale profile loses speed and nothing
else. That claim was measured,
not assumed: `out/_agents/impl-4-pgo/build-stale` is this tree built with
the speed-mem investigation's profile from the PRE-BURST source (its
`src-fast` copy of `1e76ac5` + the page-table patch, collected on a
different binary hours earlier: `speed-mem/pgo/fastlto-both.profdata`).
Clang reported 25 out-of-date files (the 22 above plus `machine.cpp`,
4 of 82 functions mismatched, `rtos.cpp`, 1 of 128, and `main.cpp`, 1 of
132 -- the page table, the burst loop and the interactive loop are what
changed since; `periph`, `v4e`, `dsp`, `card` still match); the binary is
2,333,704 bytes; **oracle 28
PASS, 0 FAIL** (`reports/20260912-090429-impl4-stale.txt`, ctest 7 / 7);
bench 1500 / 161 -- still +17 % / +7 % over LTO because Musashi's handlers
and the DSP interpreter did not change, 9 % / 6 % short of the fresh
profile. Nothing is committed: the profile lives under `out/` with the
binaries, and a default configure (no option) reproduces the O15c binary
byte for byte (sha `e298c877…`, 2,522,328 bytes, `build-lto`).

### Measured (12 Sep 2026, the same M5 Mac, macOS 26.5, AppleClang 21.0.0; logs under `out/_agents/impl-4-pgo/`)

`bench.py`, all binaries in one session, interleaved, one after the other,
nothing else running (`bench_series.sh` -> `bench_series.txt`,
`impl4_*.log`). Reference = `out/emu/ot_emu.ref-1e76ac5`; LTO = the
default configure of this tree (= O15c, `build-lto`); **PGO** =
`out/emu/ot_emu` as the first `pgo.sh` left it (sha `2d75bde6…`,
2,351,544 bytes, -6.8 % vs LTO; the binary in `out/emu` now is the one
fix1's re-run left, sha `1634501f…`, same size, same speed -- its own
series is below). The `ready sample=277688.167` stamp is identical in all
fourteen runs.

| measurement | reference | LTO (O15c) | **PGO + LTO** | stale profile |
|---|---|---|---|---|
| play, no `--dsp` (emulated ms per wall s) | 220 | 1336, 1239 | **1665, 1619** | 1500 |
| play, `--dsp` | 100 | 151, 151 | **171, 171** | 161 |
| boot + fixture load to `ready`, no `--dsp` | 39.0 s | 7.9, 7.4 s | **6.6, 6.8 s** | 6.9 s |
| boot + fixture load to `ready`, `--dsp` | 57.8 s | 24.9, 25.0 s | **18.4, 18.5 s** | 19.7 s |
| `ot_emu` size (bytes) | 2,788,712 | 2,522,328 | **2,351,544** | 2,333,704 |

Ratios: PGO over LTO **1.28x** without `--dsp` (1642 / 1287.5; the plan
asked for >= 1.10x and a landing >= 1000) and **1.13x** with (171 / 151);
over the reference **7.5x** (1642 / 220) and **1.71x** (171 / 100).
Playback without the cores is **1.64x real time** (a 16th at 120 BPM in
0.075-0.077 s wall; O15c: 0.097 s); with the cores 0.17x, exactly the
plan's "~0.17-0.20x" landing for the exact single-thread design (O12: the
cores' interleave cannot change, and their interpreters are what the
profile speeds up here -- the ColdFire half is now < 0.7 s of the 5.85 wall
s an emulated second costs with `--dsp`). Ready with `--dsp` is 1.35x
faster (25.0 -> 18.45 s: the DSP boot and the sample load are core-bound),
without 1.14x. The instrumented binary itself (5,926,040 bytes) runs at
848 / 106 -- 0.66x / 0.70x of LTO -- which is why it lives in
`out/emu-pgo-gen` and never in `out/emu`.

Profile-to-profile variance: a second, independent training run (below,
the Rosetta accident) produced a profile of 9,840 functions and a
different binary (2,360,440 bytes, sha `724c5763…`) that benches 1652 /
176 -- the same speed within noise. The same profile always gives the
same bytes: three trees (`-j1` verbose, `-j8`, `OT_PGO_WARNINGS` on and
off) were byte-identical, and a fresh configure from the final profile
(`build-pgo3`) reproduces `out/emu/ot_emu` byte for byte.

**The gate: 28 PASS, 0 FAIL** on the PGO binary (`out/_agents/speed-
oracle/reports/20260912-091014-impl4-pgo-arm64.txt`, copy in
`out/_agents/impl-4-pgo/oracle_pgo_arm64.txt`; 49 s wall): boot logs
identical, `serial_a` 5731 / 9257 bytes identical, goldens 12,757 /
26,367 bytes identical, `run3_core0.wav` 7,936,292 bytes identical, the
UART A stream 18,297 / 18,309 bytes identical step by step, 109 peeks
identical, 47 run stamps with max |dsample| = 0 and |dframes| = 0,
`interdsp.pcm` 497,788 bytes identical, ctest 7 / 7 in `out/emu`. Under
the battery (with a build running alongside) the candidate's jobs took:
`card` 8.25 s (O15c: 8.87 s; reference 44.2 s), `render` 31.7 s (36.9),
`inter` boot 8.2 s + 3.0 s of `run` (8.6 + 3.2), `interdsp` 23.6 s +
24.5 s (26.5 + 27.7). The plain binary: 28 PASS (`…-090416-impl4-plain.
txt`; its bytes are O15c's verified binary, so the oracle served the
candidate side from its cache and re-ran ctest, 7 / 7 in `build-lto`).
The stale-profile binary: 28 PASS, as above.

**The Rosetta accident, kept as a finding.** The first run of `pgo.sh`
was started as `bash tools/emu/ot_emu/pgo.sh` from a shell whose PATH has
the Intel Homebrew's `/usr/local/bin` ahead of `/bin`: that `bash` is an
x86_64 binary, runs under Rosetta, and every child (cmake, clang) inherits
the translation, so clang targeted x86_64 by default and the whole ritual
-- instrumented build, training, optimised build -- produced an **x86_64
`ot_emu`** (`-arch x86_64` in `flags.make`, 2,426,472 bytes). It passed the
oracle, 28 / 28 (`…-090149-impl4-pgo.txt`: the render WAV and the pipe PCM
byte-identical across two instruction sets -- the port's arithmetic does
not depend on the host ISA), but it is not the operator's binary. `pgo.sh`
now re-executes itself under `arch -arm64 /bin/bash` when
`sysctl.proc_translated` says it is translated, and checks `lipo -archs`
of both builds against `uname -m`. The re-run through the same
`bash pgo.sh` invocation is the binary measured above. (CONTEXT.md's
"keep /opt/homebrew first in PATH" is this in another form.)

### Re-running `pgo.sh` failed: the tree kept the old profile's objects (fix1, 12 Sep 2026)

The verifier ran `bash tools/emu/ot_emu/pgo.sh` twice from a clean
state. The first run built `out/emu/ot_emu` (2 min 17 s); the second
(same command, nothing changed) died at 1 min 51 s in step 4's link, for
`ot_emu` and every test binary: `ld: LTO codegen error: linking module
flags 'ProfileSummary': IDs have conflicting values ... from
out/emu/mc68k/lib68kEmu.a[2](gpt.cpp.o), and ... from ld-temp.o` -- and
left `out/emu` WITHOUT `ot_emu`, the operator's binary destroyed by the
script meant to make it (`out/_agents/impl-4-pgo-verify0/pgo_run2.log`).

The cause is in the build system, not in clang: `cmake --fresh` clears
the top-level `CMakeCache.txt` and `CMakeFiles/`, nothing else. The
vendored subtrees' objects (`out/emu/mc68k`, `out/emu/dsp56300`: 156 of
the 171 `.o` files) had been compiled against the first profile, and
make saw no reason to recompile them: their sources had not changed and
their `flags.make` was byte-identical -- the same
`-fprofile-instr-use=<same path>`, whatever the bytes at that path. Only
`ot_machine` and `main.cpp` (whose `CMakeFiles/` `--fresh` had removed)
were recompiled against the second profile, and two profiles cannot be
LTO-linked into one module: every object carries its profile's summary as
a module flag and the linker refuses to merge two different ones. Any
second run into a tree holding a PGO build hit this -- i.e. the documented
rule "run `pgo.sh` after every source change" described the failing path.

The fix (`CMakeLists.txt`, the `OT_PGO_PROFILE` branch) makes the tree
follow the profile's BYTES rather than its path:

- `file(SHA256 …)` of the profile goes into every compile line as
  `-DOT_PGO_PROFILE_SHA256=<hex>` (`add_compile_definitions` before the
  `add_subdirectory` calls, so the cores get it too). Nothing reads the
  macro; its only job is to change every `flags.make` when the profile
  changes, which recompiles every object -- the same mechanism that makes
  a `-D` change rebuild a tree. `pgo.sh` still does not `rm -rf out/emu`
  (the frozen reference lives there) and still uses `--fresh` for the
  cache; the recompile is now the CMakeLists' guarantee, not the script's.
- `CMAKE_CONFIGURE_DEPENDS` on the profile file: a plain `cmake --build`
  after the profile changed re-runs the configure step by itself, so the
  hash is recomputed without anyone remembering to reconfigure.
- `pgo.sh` step 4 checks its own work afterwards: `find "$DEST" -name
  '*.o' ! -newer "$PROFDATA"` must be empty (it was 156 in the failing
  run), else exit 1 with the count.

Measured (logs `out/_agents/impl-4-pgo-fix1/pgo_run{1,2,3}.log`,
`ritual.log`, `checks.log`), started from the state the verifier left --
`out/emu` holding a PGO build from ANOTHER profile, compiled by the
pre-fix CMakeLists, the failing precondition:

- run 1: exit 0, 2 min 9 s (instrumented build 12 s, objects reused;
  training 97 s; optimised build 20 s, 167 compile lines) -> `out/emu/ot_emu` sha
  `dbe419dd…`, 171 of 171 objects newer than the profile;
- run 2 (same command, nothing changed -- the verifier's failing case):
  exit 0, 2 min 7 s, 167 compile lines in step 4 = every object
  recompiled, link fine -> sha `1634501f…`, 2,351,544 bytes, 171 / 171;
- run 3, `--skip-train` (same profile): exit 0, 8 s, only the 11
  top-level objects recompiled (`--fresh` clears their `CMakeFiles/`; the
  cores' 156 are kept), the binary byte-identical to run 2's -- the same profile still gives the
  same bytes in the same tree, and (`build-pgo2`) in a fresh tree;
- the `CMAKE_CONFIGURE_DEPENDS` path (`build-swap`): configure + build
  with run 1's profile (-> `dbe419dd…`, the run 1 bytes), overwrite the
  profile FILE with run 2's bytes, plain `cmake --build` with no
  reconfigure: cmake re-ran itself once, recompiled 167 files, linked ->
  `1634501f…`, the run 2 bytes. The old CMakeLists would have linked
  nothing here;
- the define does not reach the bytes: the stale-profile build
  (`build-stale`, speed-mem's pre-burst profile) is byte-identical to the
  one measured above (sha `5672b791…`, 25 out-of-date warnings), and the
  default configure (`build-plain`, no `-fprofile` anywhere) is still
  O15c's `e298c877…`.

**The gate on the binary left in `out/emu` (run 2's): 28 PASS, 0 FAIL**
(`reports/20260912-095805-fix1-outemu.txt`, 45 s, `--build-dir out/emu`,
ctest 7 / 7); the plain and stale binaries 28 PASS each (their bytes were
already verified, so the oracle served them from its cache and re-ran
ctest: `…-095851-fix1-plain.txt`, `…-095902-fix1-stale.txt`). `bench.py`
on it, same session, interleaved, nothing else running (`checks.log`):

| measurement | reference | LTO (`build-plain`) | **PGO, `out/emu` (fix1)** |
|---|---|---|---|
| play, no `--dsp` (emulated ms per wall s) | 222 | 1320, 1371 | **1652, 1655** |
| play, `--dsp` | 100 | 150, 151 | **168, 172** |
| boot + fixture load to `ready`, no `--dsp` | 38.5 s | 8.0, 7.2 s | **6.6, 6.6 s** |
| boot + fixture load to `ready`, `--dsp` | 56.8 s | 25.0, 24.9 s | **19.2, 18.5 s** |

PGO over LTO 1.23x without `--dsp` (1653.5 / 1345.5), 1.13x with (170 /
150.5); over the reference 7.4x and 1.70x; 1.65x real time without the
cores (a 16th at 120 BPM in 0.076 s wall), 0.17x with. `ready
sample=277688.167` in all nine runs. The instrumented binary trained at
843-844 / 105-106, as before.

Verified independently (verify1, `out/_agents/impl-4-pgo-verify1/`): from
a clean state (no instrumented tree, no profile, `out/emu` cleaned of its
build products) `bash pgo.sh` exit 0 in 138 s -> sha `75df7057…`; the same
command again exit 0 in 127 s, 167 compile lines in step 4 -> sha
`ccff1e46…` (2,351,544 bytes, arm64, no `__llvm_prf`, 171 / 171 objects
newer than the profile); `--skip-train` 8 s, byte-identical to that. A
touched source rebuilds one object and the same bytes; the profile file
swapped for run 1's under a plain `cmake --build` reconfigures once,
recompiles 167 and gives run 1's bytes back, and restoring it gives run
2's. Oracle 28 PASS / 0 FAIL on both profiles' binaries (`…-101606-
verify1-outemu.txt`, `…-101852-verify1-run1.txt`, ctest 7 / 7 in
`out/emu`), on the default build (`e298c877…`, no `-fprofile` in any
`flags.make`) and on the stale-profile build (`5672b791…`). `bench.py`,
one session, interleaved, nothing else running: reference 221 / 98, LTO
1263, 1242 / 149, 151, PGO 1615, 1632 / 176, 175 -- PGO over LTO 1.30x /
1.17x, over the reference 7.3x / 1.79x; ready 38.9 / 7.9, 7.7 / 7.1, 6.8 s
without the cores, 57.1 / 25.7, 24.6 / 17.8, 18.4 s with.

### What it does not do

- Nothing changes without the option: a default configure is O15c's LTO
  build, byte for byte. Neither the panel server's auto-build (`cmake
  --fresh -B out/emu …` when the binary is missing) nor anyone's script
  gets PGO unless `pgo.sh` is run; that is deliberate -- the profile is a
  local, perishable artefact, and a build must never fail for want of it.
- The training is `bench.py`'s sequence on the OTLIVE fixture: playback
  with and without the cores, the boot and the fixture load. Knobs, SETUP
  pages, the file browser, sample loading and `--audio-in` are not in the
  profile; their code runs with static heuristics, as before, not slower.
- The DSP JIT and asmjit are compiled with the profile flag but have no
  data (never run); the vendored unit tests likewise.
- The profile is not committed and not portable: a different compiler
  version refuses or ignores it, a different source changes the hashes
  (measured above: it costs speed, never bytes). `pgo.sh` after every
  source change is the rule; the `-Wprofile-instr-out-of-date` lines in a
  build are the reminder. Re-running it into `out/emu` recompiles the
  whole tree (19 s), never less: the profile's hash is on every compile
  line, and there is no partial rebuild against a new profile.
- `cmake --fresh` is not a clean: it clears the cache, not the objects.
  Nothing in the ritual deletes `out/emu` (the reference binary lives
  beside the build); the recompile against a new profile rests on the
  hash define, and step 4's object-age check is the tripwire if that
  ever stops being enough.
- The remaining `--dsp` distance to real time (0.17x) is the two
  interpreters' own work under the exact interleave; the plan's step 5
  (`m68k_execute(N)` with an instruction hook) is in reserve for the
  ColdFire side, and nothing exact reaches the cores' ceiling (plan:
  <= 0.4-0.55x).

## Milestone O15e — bursts under the gate, the borrowed calls and the waits: `ready` 7.4 → 5.5 s, `test_rtos` 3.7x, bit for bit ✅ (12 Sep 2026, branch `panel-ui`)

Step 5 of this run of the speed plan (the architect's step 6); `rtos.cpp`,
`rtos.h`, `main.cpp`; no CLI change, no vendored change. O15a left five
loops stepping exactly, one `stepOnce()` -- `tickTimers()` + `deliver()`
-- per instruction: `run(_ms, true)` (the M6a gate: the batch's and
`test_rtos`'s first second), `runUntil` (the render's frame predicates,
`runToPc`), `runToMainSpin`, `callAsMain` (the borrowed slot: LOAD PROJECT's
post, SET MAIN LEVEL, the transport start) and the memory waits inside
`loadProjectLive` (card ready), `selectBankLive` (the bank byte) and
`setMainLevelLive` (the gain table). Measured on the Step 4 state before
this change (`OT_BURST_STATS=1`, `out/_agents/impl-5-bootbursts/`): the
OTLIVE boot to `ready` executes 787,138,663 instructions, of which
725,319,505 were in bursts and 10,170,953 in the boot before the handoff;
the other **51.6 M** (6.6 %) went through the exact loops -- 35.8 M in the
gated run to 205.96 ms and ~16 M in the load's borrowed calls and waits --
at roughly a quarter of the burst rate, so they cost about a quarter of
the wall. `test_rtos` was the extreme: its negative-control machine runs
the full 1000 ms with the transmit interrupt storming (186 M instructions,
bursts of ~10 between acknowledgements) and every one of its 232 M
instructions was exact.

### What changed (`rtos.cpp/.h`, `main.cpp`)

- **One loop.** `runInternal` is now `Rtos::runLoop(const RunSpec&)`, and
  every way the machine is run is a `RunSpec`: a sample budget (`ms`,
  `hasEnd`), an instruction budget (`budget`, `callAsMain`'s `n <
  _budget`), the gate (`untilGate`), a PC to stop BEFORE (`pc`, `pcArmed`),
  a caller's condition (`stop`) with whether it changes only on an event
  (`stopOnEvent`), the idle skip (`idleSkip`), the install check
  (`needInstall`, the public `run`/`runUntil` only, as before) and the two
  `m_why` strings each old loop set (`whyGate`, `whyTime`; null = leave
  it). The loop's top asks, in the old order, time/budget, the gate (only
  when `m_gateDirty`), the PC, the condition, then the idle skip; the
  stepping is O15a's burst body, the exact entry step and the exact tail
  across the horizon, unchanged. So what O15a proved for the plain run --
  the same `m_sample += 1/ips` in the same order, the pair called only
  where the old loop called it -- holds for all of them.
- **The gate ends a burst** (`endGate`): a create (`recordCreate` at
  `g_create`) and a dispatch (the record after the scheduler's `rte`) are
  the only writers of `m_gateDirty`, both are already detected per
  instruction inside the burst, and the burst now breaks on the flag after
  that instruction -- the pair, then the loop's top asks `gate()` exactly
  where the old loop asked it (once per create/dispatch: 61 evaluations in
  the boot, as before). `Stop::Gate` lands on the same instruction and the
  same sample: `gate_ms` 205.965 in the stock golden, 6296.63 in the card
  golden, `test_rtos`'s "205.964903 ms".
- **A PC condition is compared inside the burst** (`endPc`): `runToPc`,
  `runToMainSpin` and `callAsMain`'s return (the return address IS main's
  park) stop before the instruction at the address, where the old loops
  asked their predicate -- after the previous instruction's pair, which
  runs at the break. `callAsMain` counts instructions as its old `n` did
  (a burst is cut to the remaining budget; the budget is checked before
  the PC, so a call that returns on its last permitted instruction is
  still "did not return", as before).
- **A memory condition gets a write watch that wakes** (`wakeOnWrite`):
  `loadProjectLive`'s card-ready word, `selectBankLive`'s bank byte and
  `setMainLevelLive`'s gain-table longword are watched (once each, at
  first use; `Machine` watches are never removed) with a callback that
  sets `m_wake`, so the store that satisfies the condition ends its
  burst on that instruction and the condition is asked there. `runUntil`
  gained `Changes` -- `Anything` (the default: asked before every
  instruction, no bursts, the pre-O15e loop) or `OnEvent` (the condition
  can change only on a burst-ending instruction: an acknowledged vector,
  a peripheral access, a watched write) -- and the caller is answerable
  for the classification; `main.cpp`'s two frame-count predicates
  (`--pre-roll`, `--frames`) pass `OnEvent` because `m_frameCount` moves
  only in the ack hook, which wakes. A condition on unwatched memory
  stays `Anything`.
- **No idle skip where there was none.** The borrowed calls and the
  waits stepped through main's park (`bras .`) between the ATA
  interrupts; a skip would land the clock ON the expiry where stepping
  lands it a fraction of a sample past, and every later stamp would
  move. `idleSkip` is off for them, and without it the burst does not
  break at the park either (it would be a burst of one instruction): the
  spin runs to the horizon in bursts of 4096, the exact tail takes the
  timer on the same instruction.
- The per-instruction cost added to the burst body is three predictable
  compares (the PC target -- an odd sentinel when none is armed --, the
  gate flag under the gated run, the spin under the idle skip), hoisted
  as constants; the loop's top reads the PC through `pcFast()`. `OT_BURST=0`
  is still the exact loop for all of them (the card batch under it: golden
  byte-identical, 31.9 s). `OT_BURST_STATS=1` prints two more counters,
  `endGate` and `endPc`; `BurstStats` gained the same two fields.

### Measured (12 Sep 2026, the same M5 Mac, macOS 26.5, AppleClang 21.0.0; logs under `out/_agents/impl-5-bootbursts/`)

Same session, interleaved, nothing else running (`pgrep -x ot_emu` = 0
before each series). **LTO pair**: `build-base` = the Step 4 state at HEAD,
default configure (= O15c's binary, sha `e298c877…`) vs `build-cand` = this
tree, default configure. **PGO pair**: `out/emu/ot_emu` as O15d's `pgo.sh`
left it (sha `1634501f…`) vs `emu-pgo/ot_emu` = this tree through
`pgo.sh --dest/--gen/--prof` into the log dir (`pgo_run.log`). `bench.py`
unless said otherwise; `ready.py` = boot to `ready` with `--rtc
1000000000` and the burst stats.

| measurement | Step 4, LTO | **this step, LTO** | ratio | Step 4, PGO | **this step, PGO** | ratio |
|---|---|---|---|---|---|---|
| boot + fixture load to `ready`, no `--dsp` | 7.5, 7.3, 7.28 s | **5.5, 5.4, 5.62 s** | **1.34x** | 6.6, 6.6 s | **5.7, 5.3 s** | 1.20x |
| … `--dsp` | 25.4, 25.09 s | **23.4, 23.38 s** | 1.08x | 18.8 s | **17.4 s** | 1.08x |
| play, no `--dsp` (emulated ms per wall s) | 1341, 1387 | 1402, 1460 | 1.05x | 1714, 1720 | 1679, 1671 | 0.98x |
| play, `--dsp` | 153 | 151 | 0.99x | 174 | 175 | 1.01x |
| `card` batch (`--mount … --ms 1000 --golden`, standalone) | 7.36 s | **5.48 s** | **1.34x** | 6.57 s | **5.42 s** | 1.21x |
| `stock` batch (`--ms 1000 --golden`) | 1.62 s | **0.82 s** | **2.0x** | | | |
| `--sequencer --golden --bank 1 --frames 400` (no `--dsp`) | 7.85 s | **5.66 s** | 1.39x | | | |
| `test_rtos` (two boots, the gate, the negative control's full second) | 8.62 s | **2.32 s** | **3.7x** | 7.70 s | **2.78 s** | 2.8x |

The play rate is the untouched path (`run(_ms, false)`): 1.05x and 0.98x
are the LTO series' noise and the profile-to-profile variance O15d
measured (1652 vs 1665 on two profiles). The gains are where the exact
loops were: `ready` from 7.36 s (mean) to 5.51 s, `test_rtos` 3.7x, the
stock batch 2.0x. The `card` batch's 1.34x is what its instruction
accounting allows -- 52 M of its 787 M instructions were exact at Step 4
and the rest already burst -- so the plan's "3-4x" for it (estimated
before Steps 2-4 shrank everything else) was never on the table; 3.7x
on `test_rtos`, the plan's other case, is. Acceptance: `ready` <= 9 s
(5.5 s), `gate_ms` unchanged (205.964903 in `test_rtos`, 205.965 /
6296.63 in the goldens), oracle 28 PASS, ctest 7/7.

**What the bursts do now** (`OT_BURST_STATS=1`): the OTLIVE boot to
`ready`, 787,138,663 instructions as before (the same instructions --
the count is unchanged in every run below): 776,958,966 in 11,618,842
bursts (98.7 %; Step 4: 725.3 M in 11.42 M), 8,744 exact (Step 4:
6,965), the rest the boot before the handoff; bursts ended on a
peripheral access 11,330,746 times, a wake 65,421, the horizon 180,587,
main's spin 42,021, **the gate 61, a PC 6** (5 in the card batch: the
load's borrowed calls and PC waits; the sixth is SET MAIN LEVEL's, which
`--interactive` posts by default -- a PC wait that finds the PC already
there at its top, or on its exact entry step, is not a burst end and is
not counted). `test_rtos`: the first
machine 43,931 bursts / 35,830,945 instructions / 121 exact, 61 gate
ends; the negative control 17,595,901 bursts / 175,958,997 instructions,
17,595,900 of them ended by a wake -- the transmit interrupt it was
built to leave storming, ten instructions apart, and still 3.7x faster
than a pair per instruction.

**The gate: 28 PASS, 0 FAIL, twice** -- the LTO candidate
(`out/_agents/speed-oracle/reports/20260912-104149-impl5-bootbursts.txt`,
copy `oracle1.txt`, 53 s wall) and the PGO candidate
(`…-105258-impl5-bootbursts-pgo.txt`, `oracle_pgo.txt`, 43 s): boot logs
identical, `serial_a` 5731 / 9257 bytes identical, goldens 12,757 /
26,367 bytes identical, `run3_core0.wav` 7,936,292 bytes identical, the
UART A stream 18,297 / 18,309 bytes identical step by step, 109 peeks
identical, 47 run stamps with max |dsample| = 0 and |dframes| = 0,
`interdsp.pcm` 497,788 bytes identical, ctest 7 / 7 in `build-cand` /
`emu-pgo`. Under the battery the LTO candidate's jobs took: `stock`
0.60 s (reference 2.37), `card` 6.34 s (44.19), `render` 31.6 s (75.3),
`inter` boot 6.35 s + 3.0 s of `run` (44.1 + 19.8), `interdsp` 24.7 s +
27.6 s (66.0 + 42.4); the PGO candidate: `card` 6.41, `render` 25.0,
`inter` 6.36 + 2.68, `interdsp` 18.6 + 23.8. Beyond the gate, standalone
against the Step 4 binary: the `stock`, `card` and `--sequencer --bank 1
--frames 400 --main-level 64` goldens and batch logs byte-identical
(`selectBankLive` exercised: saved bank 0, played bank 1), and the card
batch under `OT_BURST=0` byte-identical to both.

### What it does not do

- A `runUntil` condition on memory nobody watches, or any condition a
  caller does not classify, runs the exact loop as before (`Changes::
  Anything` is the default); the three watched words are the only memory
  conditions in the tree. Watches cost: every write takes `Machine`'s
  slow body once one is armed (O15c), and the card-ready watch arms it
  at the mount rather than at the PART_PTR watch a few hundred ms later
  -- the same state every card session was already in for the whole of
  its play.
- The `--dsp` `ready` gains 8 %: the DSP boot and the sample load are
  the cores' work, ticked per instruction inside a burst as outside it.
- The stock path's remaining cost is not the loop: 17.5 M of its 46 M
  instructions write into the 0x42000000 span the stock run never maps
  (auto-mapped, the slow body); a mapped span there is `machine.*`'s
  business, not this step's.
- Nothing paces anything (plan step 7); the plan's step 5 (`m68k_execute
  (N)` with an instruction hook) stays in reserve.

## Milestone O15f — real-time pacing: the child tracks its wall clock, 1.00x whenever the core keeps up, opt-in, bit for bit ✅ (12 Sep 2026, branch `panel-ui`)

Step 6 of this run of the speed plan (the architect's step 7); `main.cpp`
(`serveInteractive` only), `tools/panel/panel_server.py`,
`tools/panel/panel.html`, `tools/panel/README.md`; no change to the run
loop, the batch, the vendored cores or any existing command. O15a–e made
the ColdFire side faster than the unit (1.4x real time playing without
the DSP cores on the M5) but nothing held it *at* the unit's rate: the
panel server pumped `run 25` and slept 30 ms, which macOS stretched to
33.9, so idle the firmware's clocks ran at 0.69x without the cores and,
with them, at 1.02x in bursts of 0.85–2.0x (the 10 ms `run 25` skipped
the sleep on 58 % of pumps); playing, at whatever the core did. The
double-tap chord (a track key twice opens its sample slot list; the
firmware measures the gap in ITS time, window between 191 and 242
emulated ms) only landed from the page because the server slowed its
pump for 0.5 s after a track key (`SLOW_PUMP_MS`), compressing 0.45 s of
wall into 191 emulated ms. The pacing investigation
(`out/_agents/speed-pacing/`, `REPORTS.md` "pacing") measured all of that
and prototyped both a server-side and a child-side pacer; this milestone
lands the child-side one the plan prefers, with the commands interleaved.

### What changed (`main.cpp`: three commands and one argument, all opt-in)

- **`pace on [rate]` / `pace off`.** While `pace` is on and no command
  line is pending on stdin, `serveInteractive` free-runs: it takes an
  anchor (wall time, emulated ms) at `pace on` and before every step
  compares the lead = emulated − (anchor + wall elapsed × rate). A slice
  (10 ms) or more ahead, it sleeps the excess, capped at one slice,
  **inside `poll()` on stdin** so a command wakes it at once (the first
  cut of the prototype used `sleep_for` and every command waited up to a
  slice: 13.7 ms median key round trip against 0.09). Otherwise it runs
  `_rtos.run(10, false)` — the ordinary run loop, idle skip and bursts
  included, so idle a slice is a handful of idle skips and playing it
  costs what the core costs; a core faster than real time builds a lead
  and sleeps it off, a slower one never leads and runs flat out. More
  than 250 ms behind (a slower core, a long command) it re-anchors and
  counts it, so the lag never turns into a catch-up burst later. A
  pending line is served between slices, one reply per command, exactly
  as unpaced; a `run` from the client advances on top of the pacer (the
  pacer then waits for the wall clock). A slice that stops on
  fault/illegal ends the free run; `pacestatus stop=` says so and the
  next `run` answers as it always did. `pace on` re-anchors; `rate` is
  emulated seconds per wall second (0.5 = half speed; 1.0 default).
- **A 1 ms grace after every reply.** A client sends its commands in
  rounds (the panel's `tx`, `audio read`, `pacestatus`, ~100 µs apart),
  and a slice begun in that gap made every command of the round wait for
  a slice — four slices, 231 ms, per page click while playing with the
  cores. After a reply the loop polls stdin for 1 ms before the next
  slice, so a round goes through in one; at 1.0x the millisecond comes
  out of the sleep, flat out it is under 1 % (a round per 200 ms).
- **`pacestatus`** → `on= rate= ratio= lag= slices= reanchors= slept=
  busy= stop= ms=`: `ratio` is emulated ms per wall s over the last
  closed window of at least a second (commands served inside it included)
  / 1000 — the honest "x real time"; `lag` how far emulated time is
  behind its wall target now (0 when ahead); `slept` wall seconds inside
  `poll()`, `busy` inside slices (also added to `status wall=`); `stop`
  the last slice's Stop word; `ms` the emulated clock. Pending stdin is
  detected through iostream's buffer, stdio's (`stdin->_r`: `cin` is
  synced with stdio, whose FILE may hold a line `poll()` cannot see) and
  `poll()`.
- **`run <ms> wall <seconds>`.** The plain run, also ended when the wall
  budget is spent: `Rtos::runUntil` with `Changes::OnEvent`, whose
  condition is asked at every burst end and exact step, and the
  condition reads the clock once per 4096 instructions
  (`Machine::instructions()`; bursts average ~70 instructions, so a
  `steady_clock` read per call would have cost ~5 %). Where the run ends
  moves no firmware event (timers, frames and the panel UART advance by
  sample count); `stop=wall` when the budget ended it, else the usual
  word. `run <ms>` alone is the untouched path (`_rtos.run(ms, false)`),
  and every old input — `run`, `run 10 20` — gets the old reply
  byte-for-byte; only a `run <ms> wall ...` attempt (a four-word line
  whose third word is `wall`) has the new usage text -- `run 10 x 1` is an
  old input and keeps `err usage: run <ms>`.

### What changed (`panel_server.py`, `panel.html`)

- **`Panel._loop_paced`** replaces the pump for the port backend: after
  the boot the loop sends `pace on 1` and from then on only serves
  actions (a blocking `actions.get(timeout=0.02)`, so a click is served
  the moment it arrives) and, every 20 ms when none is queued, `tx`, the
  audio drain, `pacestatus` (which sets `rt.sample`, `ran_ms`, the
  meters) and the render. A fresh child (respawn, card re-insert, sound
  switch) is armed again when the loop sees a new `rt`; a child without
  `pace` (an older `--port-bin`) makes `pace on` answer `err` and the
  loop falls back to the old pump, with the reason in `backend_note`.
  Route A keeps the pump loop, unchanged. `SLOW_PUMP_MS`/`slow_until`
  are ignored under the pacer (the route A pump still uses them).
- **An ordinary key edge does no `run` of its own** under the paced
  child (`_key_act(run_ms=None)`): the pacer's next slice delivers it
  within 10 ms of emulated time anyway, and the old 50 ms run cost the
  click 50 emulated ms at the core's rate (40 ms of wall playing without
  the cores, ~330 with them). PLAY down and STOP down keep their 50 ms so
  the frame-mode switch and the take open/close still sit around a
  processed key; `tap()` (hold/gap inside one action) and `transport()`
  (down + up as one action) pass their runs explicitly, as before.
- **`run_ms`** (the page's RUN 1s/5s, `/run`) passes the remaining wall
  budget to each slice as `run <ms> wall <s>`, so a slice, not just the
  loop, is bounded in wall time; `stop=wall` ends it like the budget did.
- **`/status`** gains `rt` (x real time by the wall clock: emulated ms
  per wall s over the last second of `pacestatus` readings / 1000 — the
  `RtMeter`; null under route A and before the pacer is up) and `pace`
  (the last `pacestatus`, as numbers). `speed` is kept with its old
  meaning — emulated ms per wall second *inside* the emulation, fed from
  the child's `busy` deltas — and still reads high idle (thousands: idle
  slices are instant); scripts that want the honest figure read `rt`.
  The sound note no longer claims "~9x slower".
- **The page** shows `rt` as a tiny badge beside the phase (`1.00x`,
  green at ≥ 0.97, yellow below, hidden while it is unknown), from the
  same 350 ms status poll.

### Measured (12 Sep 2026, the same M5 Mac, macOS 26.5, AppleClang 21.0.0; logs under `out/_agents/impl-6-pacing/`)

Nothing else running (`pgrep -x ot_emu` empty before each series), every
run started at nice 0 (see the QoS paragraph: a zsh `&` job is not). The
candidate is `build/ot_emu` (sha `261ffec46498…`), this tree at the
default configure; the reference `out/emu/ot_emu.ref-1e76ac5`.

**The child alone** (`pace_child.py`: the OTLIVE card, `--rtc 1000000000`,
YES on the dialog, then `pace on`; `pacestatus` once a wall second):

| | no `--dsp` | `--dsp` |
|---|---|---|
| boot + load to `ready` | 5.8 s | 24.1 s |
| idle, 20 s: emulated ms per wall s | **1000.5** (per second 990–1012; `ratio` 0.988–1.012) | **1000.2** (992–1007; 0.991–1.009) |
| … slices / re-anchors / slept / busy | 1613 / 0 / 19.18 s / 0.89 s | 1617 / 0 / 13.74 s / 6.41 s |
| … child CPU | 3.8 % | 29.7 % |
| `key` down + `key` up round trip, idle | 0.24 ms median, 4.99 max | 2.64 ms, 8.31 max |
| the same with a `run 50` after each, idle | 7.08 ms | 33.4 ms |
| playing (frame on, PLAY), 20 s | **999.6** (994–1004; `ratio` 0.999–1.002, `lag` 0) | **151.0** flat out (137–164; 0.137–0.164; `lag` 57–284 ms, 70 re-anchors) |
| … child CPU | 69.1 % | 100 % |
| key round trip, playing | 2.3 ms median, 13.6 max | 103.1 ms, 146.5 max (before the grace poll) |
| `run 250` vs `run 250 wall 100` (never hit), 8 pairs interleaved, playing | 177.0 vs 171.9 ms (−2.9 %: noise) | 1651.8 vs 1647.6 ms (−0.3 %) |
| `run 250 wall 0.05` / `wall 0.02`, playing | 50.1 ms wall, 75.6 emulated ms, `stop=wall` / 20.1 ms, 30.9 | 50.6 ms, 8.44 / 20.4 ms, 3.34 |

Idle, the pacer holds the unit's clock to ±1 % second by second with and
without the cores (the acceptance: 1.00 ± 0.01) at 4 % of a core without
them; playing without the cores it holds 1.00x too, because the O15a–e
core is 1.4x real time and the pacer sleeps the difference (busy 16.7 of
20 s); with the cores it is flat out at the core's own rate (bench.py on
the same binary: 150–152) and says so. The wall predicate costs nothing
measurable and a budget that is hit ends the run within 0.1–0.6 ms of it.
The error paths answer `err usage` for `pace`, `pace maybe`, `pace on 0`,
`pace on 1 2`, `pacestatus x`, `run 10 wall`, `run 10 wall -1`, `run 10
wall x`; `run 10 x 1` gets the old `err usage: run <ms>` (the new text is keyed
on the third word being `wall`, not on the word count; the verifier's
`child_cmds.py` diff of every old input -- `run`, `run 10 20`, `run 10 x 1`,
`run abc`, `run -1`, `status`, `tx`, `frame`, `key`, `quit x` -- against the
reference is empty apart from the bare word `pace`, a new command;
`out/_agents/impl-6-pacing-fix1/cmds_{cand,ref}.log`).

**The panel server end to end** (`srv_measure.py`: `panel_server.py
--port 8590/8591 --port-bin build/ot_emu`, the OTLIVE project, then
`/status` once a wall second, 30 `/key` edges (MIXER), PLAY, STOP,
`/run?ms=1000`, and the double tap by wall time; `srv_nodsp3` /
`srv_dsp2`, the final code):

| | `--sound off` | `--sound on` (`--dsp`) |
|---|---|---|
| boot to `phase ready` | 6.1 s | 24.2 s |
| idle, 20 s: `ran_ms` per wall s | **1000.3** (964–1017); `/status rt` 0.991–1.008, median 0.999 | **1000.2** (978–1029); `rt` 0.992–1.008, median 1.000 |
| … CPU child / server | 3.8 % / 0.5 % | 29.5 % / 0.4 % |
| `/key` round trip, idle | **1.7 ms** median, p90 1.9, max 1.9 | **1.0 ms**, p90 3.5, max 3.8 |
| playing, 30 s | **1000.2** (981–1019); `rt` 0.997–1.004, median 1.000; lag 0 | **149.5** (130–161); `rt` 0.133–0.161, median 0.148; lag ≤ 319 ms, 98 re-anchors |
| … CPU child | 74.4 % | 97.8 % |
| `/key` round trip, playing | **2.0 ms** median, p90 8.3, max 11.2 | **35.7 ms** median, p90 44.1, max 79.4 |
| `/run?ms=1000`, idle | 1004 ms in 0.02 s | 1004 ms in 0.28 s |
| two page clicks on T1, 0.15 s of wall apart (2 trials) | OPEN, 150 / 150 emulated ms press to press | OPEN, 150 / 150 |
| … 0.30 s apart | miss, 300 / 311 | miss, 290 / 300 |
| the take from PLAY to STOP | — | take-003.wav, 6.3 s, `dropped` 0 |

Against the pump it replaces (the pacing report's measurements on the
same fixture: idle 686 emulated ms per wall s without the cores, 1025 in
bursts of 0.85–2.0x with them; `/key` 29.7 ms idle, 327 ms playing;
double taps landing only through `SLOW_PUMP`): idle is now 1.000x either
way, a click waits ~1–2 ms idle and about the slice in progress playing
(2 ms at 1.0x, 36 ms with the cores at 0.15x, where a slice is ~65 ms of
wall), and the double-tap window is the unit's own — 0.15 s of wall
lands, 0.30 s does not, cores or no cores. Two intermediate runs are in
the log dir for the record: `srv_nodsp` (the key's 50 ms run still in
place: `/key` 40.2 ms median playing, 4.2 idle) and `srv_dsp` (before
the grace poll: 230.7 ms median playing — four slices — with the same
rates and the same double-tap result); `srv_nodsp2`/`srv_dsp` also ran
at nice 5 by accident (a zsh `&` chain) with rates indistinguishable
from the nice 0 runs.

**Ratio to the reference, same session** (`bench.py`, the fixed `run
250` protocol, pacing never on): no `--dsp` **1414 vs 221** emulated ms
per wall s (6.4x; `ready` 5.4 vs 38.8 s), `--dsp` **150 vs 100** (1.5x;
`ready` 23.5 vs 57.4 s) — the O15a–e rates; this step adds nothing to the
fixed-run path and takes nothing from it (1423, 1341, 1414 across the
session's three no-`--dsp` runs of the candidate).

**The QoS question** (the speed-mem report's "backgrounded runs of a
byte-identical binary differed by 1.5x"). Explained and measured: a job
started with `&` in zsh runs at nice 5 (`BG_NICE`, on by default), which
on an idle machine costs nothing (1357 vs 1341/1423 without the cores,
151 vs 151/152 with) and under contention gives way — the 1.5x was
another emulator on the machine. The class that does matter is the
darwin background policy (`taskpolicy -b`: efficiency cores, throttled
I/O — what a background-QoS or napped app and its children get):
**385** emulated ms per wall s without the cores (boot 21.4 s) and **43**
with them (boot 90.9 s), 3.7x / 3.5x slower. A process may leave that
class itself — `setpriority(PRIO_DARWIN_PROCESS, 0, PRIO_DARWIN_NORMAL)`
in the child before `exec` (`bench.py` variant `OT_DARWIN_NORMAL=1` under
`taskpolicy -b`): **1469**, boot 5.5 s — so `PortProc` now spawns the
child with exactly that `preexec_fn` (a no-op when nothing is inherited;
niceness cannot be lowered without privilege, so `/status` reports it as
`nice` and the server prints a warning at start when it is > 0). The
app-bundle half (`open -a` on a re-identified copy of `Virtual
Panel.app`, bundle id `io.octabam.virtual-panel.qos-test`, port from
`VIRTUAL_PANEL_PORT`, `projectDir` in its own defaults) could not be
measured: the copy blocked in `Log.open` → `open()` on
`out/panel_app.log` (`app_stuck.sample.txt`) — macOS's consent prompt for
`~/Downloads`, which the new identifier triggers and only the user can
answer; the launched app itself ran at nice 0, priority 46. The
terminal-launched control on the same code path (`qos_terminal`, the
pre-O15f binary through the fallback pump): 179.5 emulated ms per wall s
playing with the cores.

**The gate: 28 PASS, 0 FAIL** (`out/_agents/speed-oracle/reports/
20260912-120131-impl6-pacing.txt`, copy `oracle1.txt`, 52 s wall): boot
logs identical, `serial_a` 5731 / 9257 bytes identical, goldens 12,757 /
26,367 bytes identical, `run3_core0.wav` 7,936,292 bytes identical, the
UART A stream 18,297 / 18,309 bytes identical step by step, 109 peeks
identical, 47 run stamps with max |dsample| = 0 and |dframes| = 0,
`interdsp.pcm` 497,788 bytes identical, ctest 7 / 7 in `build`. Under
the battery the candidate's jobs took `stock` 0.55 s (reference 2.33),
`card` 6.07 s (44.08), `render` 31.6 s (74.2), `inter` boot 6.12 s +
2.96 s of `run` (43.6 + 19.3), `interdsp` 23.5 s + 27.5 s (63.2 + 41.6)
-- the O15e figures: the oracle never says `pace on` or `wall`, and the
paths it drives did not change.

**Verified (12 Sep 2026, the verifier's own build of the same tree, sha
`089bd73fb869…`, byte-identical to the fixed binary; logs under
`out/_agents/impl-6-pacing-verify1/`).** Oracle `--fresh`, both sides
rerun: 28 PASS / 0 FAIL, 106 s wall; ctest 7 / 7. The old inputs answer
byte-for-byte as the reference (`child_cmds.py`: only the bare word
`pace`, a new command, differs). Same-session `bench.py`: **1473 vs 224**
without the cores (6.6x; `ready` 5.4 vs 38.9 s), **155 vs 101** with
(1.5x; 22.6 vs 56.9 s). The server end to end (`srv_verify.py`, ports
8590/8591, the OTLIVE fixture, nice 0): idle 60 s **1000.2** emulated ms
per wall s both with and without the cores (per second 979–1029 /
976–1029; `/status rt` 0.990–1.014 / 0.991–1.009, median 0.999 / 1.000;
0 re-anchors), child CPU 4.7 % / 30.5 %; playing 30 s **1000.2** without
the cores (`rt` 0.996–1.003, lag 0) and **150.7** with them (`rt`
0.136–0.164, median 0.150, 89 re-anchors, lag ≤ 279 ms), i.e. what
`bench.py` measured on the same binary; `/key` round trip 1.66 / 0.98 ms
idle, 1.72 / 24.2 ms playing; double taps 0.15 s of wall apart OPEN (150,
163 / 150, 150 emulated ms press to press), 0.30 s miss (300, 300 / 315,
300), twice each, `/tap n=2` opens; the take from PLAY to STOP recorded
(take-005.wav, 8.74 s, `dropped` 0), `/audio/pcm` streamed +7553 frames
per wall s while playing with the cores. **The LEDs in wall time**
(`led_chase.py`: `/leds` polled ~250 times a second for 20 s of play,
sound off): the running light enters trig row 1 (trigs 5–8) once per
16-step sweep every **2000.2 ms** (10 crossings, stdev 15.7, min 1971.6,
max 2021.3) = **125.01 ms per 16th** at the fixture's 120 BPM, and the id
`0x48` LED blinks every **250.0 ms** (79 intervals, stdev 13.2) — the
unit's tempo, on the wall clock; with the cores the same blink comes
every 1646 ms (18 intervals) = 0.152x, as `rt` says. QoS reproduced:
`taskpolicy -b` 381 emulated ms per wall s (boot 21.3 s) vs 1520 with
the child's `setpriority` (boot 5.4 s); the server itself started under
`taskpolicy -b` booted in 6.0 s and paced at 1.000x (its `preexec_fn`
takes the child out of the class; the server process stays in it, so
its own polling is slower — 11 `/leds` a second against ~250). `nice 5`
on the idle machine: 1475.

### What it does not do

- It does not make the cores faster: with `--dsp` the pacer is a
  reporter (0.15x, re-anchoring every ~0.3 s of wall) until the DSP work
  in the plan lands; the "honest playback note" in the README stands.
- Idle with `--dsp` costs ~30 % of a core: the cores render silence
  through every idle slice (the DSP idle fast-forward the pacing report
  hands to the core team, proposal E, is not done).
- Nothing in the batch, the fixed `run`, the run loop or the vendored
  cores changed: the oracle's 28 checks drive fixed runs and are
  byte-identical; the pacer is off unless a client says `pace on`.
- The app-bundle half of the QoS question could not be measured (see
  Measured): a re-identified copy of the bundle hits a TCC consent
  prompt for `~/Downloads` that only the user can answer.
- A `run <ms> wall <s>` that ends on the budget is still one `run`: the
  frames it advanced are what it advanced, and a script that relies on
  `run` advancing exactly `<ms>` must not pass `wall`.
- The `hits` record line is formatted into a 160-byte buffer and can be
  cut short when every register is 8 hex digits (up to 215 bytes); a
  pre-existing limit, left as it is because changing it would change an
  existing command's output. (Fixed in O15g, below: the record has its
  own buffer; the reply's grammar did not change.)

## Milestone O16a — the oracle in the repo, a second frozen reference, and the Phase B audio contract ✅ (12 Sep 2026, branch `panel-ui`)

Phase B (the DSP pair: lazy batching / a thread per core, E2/E3 in
`out/_agents/speed-plan/REPORTS.md`) cannot be held to bit-identical audio:
O12 measured that ANY change of the core interleave (quanta 1 / 64 / 2,000 /
50,000) moves a few samples of a reverb return by one LSB at the host-frame
edge (frame 641 on that fixture), while the hardware runs the two cores
truly in parallel — a different interleave is not less faithful. What must
not move is the firmware's observable behaviour: screens, LEDs, sequencer
timing, the goldens' dispatch order. This step makes that contract a tool.

### What changed (`tools/emu/ot_emu/oracle/`, new; nothing in the emulator)

- `out/_agents/speed-oracle/` (Phase A's gate, O15a–O15f) is now
  `tools/emu/ot_emu/oracle/` — `oracle.sh`, `drive.py`, `tmo.py`,
  `cmp_text.py`, `cmp_stamps.py`, the README — as a maintained tool. Every
  input is a flag or an environment variable with the Phase A path as its
  default: `--ref`/`OT_ORACLE_REF` (`out/emu/ot_emu.ref-73c2815`; a first
  positional still overrides), `--image`, `--card` (card/inter/interdsp),
  `--card2` (render), `--set`/`--project` (`OTLIVE`/`PROJECT`), `--out`
  (cache + reports, `out/_oracle/`), `OT_ORACLE_PY`. No firmware byte and no
  fixture is in git: the image and the two card images stay under `out/`.
  `drive.py` takes `--image/--card/--set/--project` and finds the repo root
  from its new depth; `tmo.py`, `cmp_text.py`, `cmp_stamps.py` are unchanged.
- The cache is keyed on the binary's sha256 AND on the job's inputs
  (`inputs.txt`: path, size, mtime of the image and card, set, project; the
  interactive jobs also the driver's sha) — a changed fixture reruns.
- **`cmp_audio.py`** replaces `cmp` for the two audio captures.
  `cmp_audio.py A B [--fmt s16|wav24|auto] [--tol L] [--frac P] [--len-tol N]`
  reports on one line: frames per side, max |diff|, the differing count and
  percent, the first differing frame (channel, both values), the onset frame
  (first frame with any non-zero sample) per side, a trailing length
  difference, and a SHIFT HINT when B equals A displaced by ±1..3 frames; then
  PASS/FAIL. PASS needs the WAV header identical, |frames_A − frames_B| ≤
  len-tol, max |diff| ≤ tol, differing ≤ P % of the compared samples, and the
  onset frame identical (alignment is never tolerated). Byte-identical files
  short-circuit without decoding. Pure Python (the venv has no numpy):
  2,645,416 24-bit samples decode and compare in 0.4 s.
- `oracle.sh` gains `--audio-tol <lsb16>` (interdsp.pcm), `--wav-tol <lsb24>`
  (render.wav), `--audio-frac <percent>`; `--frame-tol N` now also bounds the
  audio captures' LENGTH (a frame edge on a run boundary). All default 0 =
  the strict Phase A gate. Everything else — logs, serial, goldens,
  `oracle.py`, UART stream, per-step sizes, peeks, replies, `ready` — stays
  byte-strict whatever the flags.
- `phase_b.sh CAND [--build-dir DIR]` runs the candidate against BOTH
  references with the Phase B tolerances (`--audio-tol 2 --wav-tol 8
  --audio-frac 0.5 --frame-tol 1`); the second pass only compares (the
  candidate's runs are cached).
- **The second frozen reference:** `out/emu/ot_emu.ref-73c2815` =
  `out/emu/ot_emu` at HEAD `73c2815` (Phase A's PGO binary, sha256
  `3c7d2111891c…`, the binary the last Phase A report gated 28/28), copied
  with `cp -p` and made read-only. Untracked, like `ref-1e76ac5`; keep both.

### The Phase B contract (decided for the DSP work; B0 and B1 held at 0)

Everything the oracle checks stays byte-identical — boot logs, serial,
goldens (dispatch order and stamps), the UART A stream (LCD/LEDs), peeks,
`run` stamps — EXCEPT the two audio artefacts, which may differ from the
reference within: `interdsp.pcm` (16-bit) max |diff| ≤ 2 LSB and ≤ 0.5 % of
samples differing; `run3_core0.wav` (24-bit words) max |diff| ≤ 8 and
≤ 0.5 % differing; the audio must stay sample-ALIGNED (the onset frame
identical); the frame counts in `run` replies and the captures' length may
differ by at most 1 (`--frame-tol 1`), only where a frame edge lands on a
run boundary. A step whose diff exceeds that FAILS. Phase B steps are gated
against BOTH references: strict against `ref-73c2815` on the non-audio
checks (and, since the two references are byte-identical on every check,
equally against `ref-1e76ac5`); the audio tolerance against either.

### Measured (12 Sep 2026, the same M5 Mac, macOS 26.5; reports under `out/_oracle/reports/`, logs under `out/_agents/speed-b0/`)

| run | result | wall | report |
|---|---|---|---|
| `ref-73c2815` vs itself (determinism; ctest on a fresh plain-LTO HEAD tree, `out/_agents/speed-b0/build`) | **28 PASS, 0 FAIL** | 47 s | `20260912-130930-b0-refref-73c2815` |
| `ref-1e76ac5` vs `ref-73c2815`, strict | **28 PASS, 0 FAIL** | 106 s (the 73c2815 side cached; the pre-speed side: card 42 s, render 73 s, interdsp boot 63 s + 43 s of `run`) | `20260912-131027-b0-1e76ac5-vs-73c2815` |
| negative control: `ref-73c2815` wrapped with `--rtc 1000000001`, WITH the Phase B tolerances on | **14 PASS, 13 FAIL** (27 checks, no ctest) | 44 s | `20260912-131239-b0-negctrl` |
| `phase_b.sh` on the plain-LTO HEAD build (sha `089bd73fb869`) | **28 PASS vs `ref-1e76ac5`, 28 PASS vs `ref-73c2815`** | 54 s + 4 s | `20260912-131324-…`, `20260912-131418-b0-phaseb-headlto` |

The negative control fails where Phase A's did — the `rtc` boot-log line,
the goldens at char 4870 (dispatch stamps moved 0.08 samples; `card.oracle_py`
one disagreement), `card.serial_a` at byte 5147, the UART stream at byte
5234 (the dialog's seconds digit), the clock record `..2e28` → `..2e29` —
and the two audio captures stay identical (the RTC does not reach the DSP):
the tolerance flags loosen nothing outside the audio. Per job on the Phase A
binary under the full parallel load: stock 1.0 s, card 6.6 s, render 27 s,
inter boot 6.6 s + 2.9 s of `run` (4,490 emulated ms), interdsp boot 20.5 s
+ 25 s of `run`, ctest 5.8 s.

`cmp_audio.py` checked on the real captures (the Phase A `interdsp.pcm`,
124,447 frames, onset frame 98; `run3_core0.wav`, 330,677 frames x 8 slots,
onset frame 282,744): identical → PASS in 0.02 / 0.04 s; 300 PCM samples
moved by ±1..2 → `max 2, 0.1125 %`, FAIL strict, PASS at `--tol 2 --frac
0.5`; the same moved by +3 → FAIL `max 3 > 2`; the PCM shifted by one frame
→ FAIL `onset moved: frame 98 vs 99` (+ `SHIFT HINT: B == A shifted −1
frame(s)`); one frame shorter → FAIL at `--len-tol 0`, PASS at `--len-tol 1`
with 0 samples differing; 500 WAV words moved by ±3..8 → `max 8, 0.0189 %`.
The shift hint is only emitted when the unshifted window is itself out of
tolerance (a first version fired on every shift inside digital silence).

### What it does not do

- The emulator is untouched: no source under `tools/emu/ot_emu/*.cpp/.h`
  changed, no CLI flag or output moved; the HEAD tree built for the ctest
  half is byte-identical to both references on all 28 checks.
- `out/_agents/speed-oracle/` is left in place (its reports and cached runs
  are Phase A's record; CONTEXT.md's "THE GATE" line still names it — the
  maintained copy is `tools/emu/ot_emu/oracle/`, and CONTEXT.md should be
  pointed at it with the next CONTEXT edit).
- The audio tolerance bounds |diff| and the differing fraction; it does not
  judge audibility or structure. A Phase B step that uses it must say where
  the diff sits (`cmp_audio.py`'s first differing frame) and why (O12).
- Nothing in the battery exercises `pace on`, threads, or shutdown timing;
  the Phase B steps that add threads must prove those separately (a
  `-fsanitize=thread` Debug build through `drive.py`, a measured quit/EOF/
  SIGTERM).

## Milestone O15g — the `hits` record, uncut: its own buffer ✅ (12 Sep 2026, branch `panel-ui`)

`main.cpp` (`serveInteractive`, the `hits` command only); no other reply,
no run-loop, batch or vendored change. O15f's last "does not do" item,
closed. Every `serveInteractive` reply was formatted through one shared
`char buf[160]`, and the `hits` record is the one reply that can exceed
it: 23 fields, ` %llx` for the instruction count (up to 16 hex digits)
and `:%x` for the 22 registers (up to 8 each), 1 + 16 + 22 × 9 = **215**
bytes when every value is wide. `snprintf` truncates silently, so the
client got a 158-character record with the trailing registers missing,
the last one shortened (a wrong value, not a missing one) or, when the
cut fell just after a `:`, an empty last field -- which the
`int(x, 16)` parse every instrument script does
(`out/_agents/seqled/probe.py`, `ledtimer.py`, `verifier/gate.py`)
raises on. The frame handler `0x4000ab1a` reaches it routinely: with
`a1`, `sp` and the five stack words all 8 digits, the record is over
160 before `d2..d7` start.

### What changed (`main.cpp`)

- **The record has its own `char rec[256]`** in the `hits` handler; the
  format string and the 23 arguments are as they were. The shared
  `buf[160]` still serves every other reply (`ready`, `status`, `ok`,
  `pacestatus`, `audio status`, the `err unmapped` lines and the
  six-field `writes` record), so no other command's output can change.
- **The protocol is unchanged**: `hits n=<count> <rec> ...` on one line,
  `<rec>` =
  `<instr>:<pc>:<d0>:<d1>:<a0>:<a1>:<sp>:<stack0..4>:<d2..d7>:<a2..a6>`,
  hex without `0x`. What changed is that a record is now always the 23
  fields the comment above the command promises. The parsers in
  `tools/panel` (none read `hits`; `KEYMAP.md` documents the format) and
  `out/_agents` (`seqled/probe.py`, `seqled/ledtimer.py`,
  `seqled/seqcheck.py`, `verifier/gate.py`, `verifier/seqcheck.py`,
  `samples/scan.py`, `impl-1-bursts-verify0/adv.py`,
  `impl-3-memory-verify0/instr_cmp.py`) all split the reply on spaces
  and each record on `:`; a longer record is what they were written for.

### Measured (12 Sep 2026, the same M5 Mac, macOS 26.5; logs under `out/_agents/fix-hits-buf/`)

`hits_len.py` boots the OTLIVE fixture (`--card out/_agents/port/otlive.img
--mount --set OTLIVE --project PROJECT --internal-clock --rtc 1000000000`),
watches `0x400622da,0x4009bc76,0x4000ab1a`, taps YES / MIXER / NO / PLAY,
runs 600 ms and reads `hits` once -- on this tree's build (`build/ot_emu`,
`cmake --fresh -B out/_agents/fix-hits-buf/build -S tools/emu/ot_emu`,
Release + LTO as the default configure) and, run only, on the pre-fix
`out/emu/ot_emu`:

| | `out/emu/ot_emu` (before) | `build/ot_emu` (after) |
|---|---|---|
| records | 3982 | 3982 |
| longest record (chars) | 158 | 181 |
| records cut at 158 | 36 | 0 |
| records with fewer than 23 fields | 34 (15 × 20, 11 × 21, 8 × 22) | 0 |
| records the scripts' `int(x, 16)` parse rejects | 8 | 0 |

(`hits_len_ref.txt`, `hits_len_fix.txt`; the record dumps beside them.)
The two sets are the same hits in the same order: record by record,
3946 are byte-identical and the other 36 -- every one a 158-character
before-record -- are proper prefixes of their after-record, which runs
159 to 181 characters (`prefix_check.txt`). The first cut one is the
frame handler with `a6 = 1`: before, `...:ffffff00:` (an empty 23rd
field); after, `...:ffffff00:1`.
The earlier instrument logs show the same defect in the wild:
`out/_agents/impl-3-memory-verify0/instr_ref.txt` has 85 of its 6363
`hits` records with fewer than 23 fields, and its candidate log the same
85 -- both binaries of that comparison were cut identically, which is why
the O15c gate could not see it. `ctest` in `build/`: 7/7 (`ctest.txt`).

### What it does not do

- It does not touch `out/emu/ot_emu` or `out/emu/ot_emu.ref-1e76ac5`:
  the build is under `out/_agents/fix-hits-buf/build/`; the operator's
  binary is rebuilt as before
  (`cmake -B out/emu -S tools/emu/ot_emu && cmake --build out/emu -j8`).
- A `hits` reply is still one line of unbounded length (the log is capped
  at 2M records, each now up to 215 bytes); a client needs a line reader,
  as every script above has.
- The other replies keep the shared 160-byte `buf`; none was measured
  against it here. The change is the `hits` record only.

## Milestone O16b — the DSP step, exact: the pair's per-instruction wrapper trimmed without moving a single interpreted instruction ✅ (12 Sep 2026, branch `panel-ui`)

Phase B's step B1 (proposal E1 of `out/_agents/speed-plan/REPORTS.md`,
prototyped as `out/_agents/speed-dsp/build1`): the part of the pair's cost
that is NOT the interpreter's work, taken out where it can be taken out
without changing the order or count of interpreted instructions, the ESAI
clock, a host-port event or a hook. Held to the STRICT gate (0 tolerance,
both references) because it changes no schedule. `dsp.cpp`, `dsp.h` only.

### What the wrapper cost, measured before the change

With `tickInstructions(1)` per ColdFire instruction, `m_due` grows by 1.043
per call and `runDue`'s quantum (64) is never reached in the RTOS phase:
each tick was one `runDue` and ~6 `stepCore` calls of which 2 executed an
instruction and 4 returned `false` on their first test (core at the due
count) -- and every one of those calls paid the prologue of a function that
also held a 256-byte trace line, a 24-hit PC-watch record, the TIMER0
capture and the fault message. On the O14k render command cut to 300 frames
(6.45 emulated s from the boot: `OT_DSP_STATS=1`, `stat-build.err`):
799.4 M `runDue` calls made 1,231.4 M passes and 859.0 M interpreter steps
(435.1 M core 0, 423.8 M core 1) -- i.e. the shipped code made 3.32 G
`stepCore` calls for 0.86 G instructions (one returning `false` per core
per pass, 2,462.8 M, plus one per instruction). **831.8 M of the 859.0 M steps
(96.8 %) are idle steps**: a poll executed after an `idleStep` whose room
was 1 or 2 instructions (core 0 95.3 %, core 1 98.4 %). Under the exact
schedule that is the shape of the work: the fast-forward advances by the
room the due count gives it, and that room is what the ColdFire's tick is.

### What changed (`dsp.cpp`, `dsp.h`)

- **`runDue` skips a core that is already at the due count** on a compare
  (`!c.faulted && executed >= due`): `stepCore` would have returned `false`
  at once with no side effect. A FAULTED core keeps its call, because that
  call has one (`executed := limit`; O8's fault path); a core still in the
  bootstrap ROM is skipped only when at the due count, where its
  `max(executed, limit)` is a no-op. Same passes, same order (core 0 to its
  quantum, core 1 to its, again until a pass runs nothing).
- **The per-instruction body is `stepBody`** (stepCore minus its three
  runnable checks), and `runDue` loops on it with the limit test inline:
  `while(executed < lim) stepBody()`. The calls that only returned `false`
  are gone; the count of bodies executed is the count of instructions
  interpreted before (the `interp` counters, below, match the O9b
  `executed` arithmetic call for call). `stepCore` itself is unchanged for
  `runCoreUntil` (the read-back pull) and now delegates to `stepBody`.
- **The cold parts are out of the body** as `noinline` helpers, in the same
  places in the same order: `faultPc` (the message, `executed := limit`),
  `timerCapture` (the TIMER0 first-enable record: the batch report prints
  it, so the `readTCSR(0) & 1` test -- an inline load -- stays on every
  instruction; only the capture moved), `instrumentBefore` (the stopwatch,
  then the PC watch) and `traceLine`, the last two behind ONE flag
  `m_instrumented` = trace armed or PC watch armed or stopwatch on core
  0/1, refreshed by the setters. The PC ring stays on every instruction
  (the fault report's "last PCs", the write watch's `last[4]` and the
  timer capture read it).
- **`doLoopEnd` is called only with SR_LF set** (`regs().sr & 0x8000`):
  its own first test is `sr_test_noCache(SR_LF)` and it returns `false`
  without touching a register otherwise, so the gate is exact.
- **Counters** (`DspPair::Stats`: `runDue` calls, passes, `stepCore`
  wrapper calls, interpreter steps and idle steps per core; one add each,
  always on) and an opt-in dump on stderr at exit: `OT_DSP_STATS=1`. No
  new command, nothing on stdout, nothing without the variable.
- NOT changed: the double `m_due` arithmetic (the prototype's integer
  version moved the idle horizon: `idle=` 63749 → 63755), `room`
  (`limit - executed`, the same limit), the idle-window detection, the
  bank-word hook, `tickInstructions`/`tickSamples`, `runCoreUntil`, every
  hook and every report line.

### Measured (12 Sep 2026, the same M5 Mac, macOS 26.5, with another agent's Python at ~99 % of a core throughout; logs under `out/_agents/speed-b1/`)

**The strict gate (0 tolerance, `tools/emu/ot_emu/oracle/oracle.sh`, no
tolerance flag, `--build-dir` for the ctest half; reports under
`out/_oracle/reports/`):**

| check | result | report |
|---|---|---|
| B1 (`build/ot_emu`, plain LTO, sha `372b19b0a8b8`) vs `ref-1e76ac5`, strict | **28 PASS, 0 FAIL** (ctest 7/7), 50 s | `20260912-133355-b1-vs-1e76ac5` |
| the same vs `ref-73c2815`, strict | **28 PASS, 0 FAIL**, 3 s (the candidate's runs cached) | `20260912-133445-b1-vs-73c2815` |
| `idle=` in the four `status` replies (stripped by the oracle; the prototype's integer due arithmetic had moved it) | 42022 / 42023 / 54842 / 66357 on both sides (`out/_oracle/runs/{3c7d2111891c,372b19b0a8b8}/{inter,interdsp}/wall.txt`) | – |
| the render command cut to 300 frames, HEAD build vs B1 (`stat-*.log`, `stat-*_core0.wav`) | WAV byte-identical (284,261 frames), log identical bar the output path | – |
| B1 vs itself (the oracle's determinism rerun into `runs/<sha>-b/`) | **27 PASS, 0 FAIL**, 44 s (no `--build-dir`: no ctest row); `20260912-134318-b1-determinism` | – |
| B1's PGO build (`build-pgo`, `pgo.sh --dest/--gen/--prof` under `speed-b1/`) vs `ref-73c2815`, strict, no ctest | **27 PASS, 0 FAIL**, 41 s; `20260912-135047-b1-pgo-vs-73c2815` | – |


**Speed (`out/_agents/speed/bench.py`: boot on the OTLIVE card, PLAY,
4 emulated s in 16 x `run 250`; emulated ms per wall s, wall of the 16 runs
in brackets; HEAD and B1 alternated round by round so both saw the same
load; HEAD = `git archive HEAD tools/emu/ot_emu` built in `build-head/` with
the default configure = Release + LTO, B1 = `build/` the same way):**

| round | HEAD `--dsp` | B1 `--dsp` | HEAD no `--dsp` | B1 no `--dsp` |
|---|---|---|---|---|
| r1 | 151 (26.53 s) | **170** (23.55 s) | 1432 | 1362 |
| r2 | 153 (26.08 s) | **170** (23.58 s) | 1451 | 1483 |
| r3 | 152 (26.30 s) | **168** (23.77 s) | 1388 | 1380 |
| mean | 152.0 | **169.3 (+11.4 %)**; wall 26.30 → 23.63 s (−10.2 %) | 1424 | 1408 (noise: the pair is not constructed without `--dsp`) |
| boot to `ready`, `--dsp` | 23.5 / 22.7 / 22.9 s | **19.2 / 19.3 / 19.2 s (−16 %)** | – | – |
| PGO, alternated: `ref-73c2815` (= HEAD's `pgo.sh` binary) vs B1 through `pgo.sh --dest/--gen/--prof` under `speed-b1/` (its own training runs) | `ref-73c2815` 173 (23.17 s) / 172 (23.20 s) / 174 (22.98 s) / 174 (22.92 s), mean 173.2 | B1 `build-pgo` **178** (22.49 s) / **179** (22.30 s), mean **178.5 (+3.0 %)**; wall 23.07 → 22.39 s | – | – |

The 300-frame render above, run while the oracle's eight jobs loaded the
machine: 26.83 → 22.23 s of wall (−17 %; the boot and the idle-heavy
pre-roll are where the wrapper was the largest share).


**Where the time went (bench.py's 10 s `sample` mid-play, round 2,
`b1_build-head_dsp_r2.sample.txt` / `b1_build_dsp_r2.sample.txt`,
`out/_agents/speed-dsp/agg.py`; self time as a share of the same 10 wall
seconds, which on B1 cover 11 % more emulated time):** HEAD `stepCore`
35.9 % + `runDue` 1.2 % = **37.1 %**; B1 `stepBody` 23.7 % + `runDue` 7.8 %
= **31.5 %** — the wrapper's self samples fell 2,881 → 2,441 (−15 %) while
the interpreter's own rose as a share (`op_Parallel` 3.9 → 4.5 %,
`alu_multiply` 3.6 → 3.7 %, `op_Mac_S1S2` 1.3 → 1.9 %), which is the work
that was waiting behind it. Inclusive, `runDue` is 67.7 % on both. What is
left in `stepBody`'s self time is the interpreter's dispatch inlined into
it (`m_interruptFunc`, `fetchPC`, the `execOp` member call), the idle path
(`idleStep`, 96.8 % of the steps) and the four compares per tick — all per
instruction whatever wraps them.


### What it does not do

- The `--dsp-trace` line keeps its 256-byte buffer (`traceLine`; clang
  warns the format can reach 311): the truncation is O9b's and the trace
  output must not change here.
- It does not touch the interleave, so it does not touch the ceiling: the
  pair still executes every idle poll the exact schedule gives it, 831.8 M
  idle steps for 27 M of real work on the render fixture. That is E2/E3's
  ground (the lazy batch / the thread), under the Phase B audio tolerance.
- The gain is what the wrapper had to give under exactness, not the
  investigation's 10-15 % estimate: **+11.4 % on the plain-LTO build,
  +3.0 % on the PGO build** (the operator's binary, `out/emu/ot_emu` via
  `pgo.sh`), because PGO had already inlined `stepCore` into `runDue` and
  made the returning-false calls cheap; the architect's +2.6 % on the
  prototype was that figure. The interpreter's own dispatch
  (`m_interruptFunc`, `fetchPC`, `execOp`) and the ESAI clock are per
  instruction whatever wraps them.
- `OT_DSP_STATS` prints at destruction: a run that ends through
  `std::exit` or a signal prints nothing. Batch and `--interactive quit`
  both destroy the pair.
- No thread, no new flag, no CLI change: batch mode and every script that
  drives `ot_emu` see the same bytes (the 28 checks, twice).

## Milestone O16c — lazy batching of the DSP pair: the ticks booked and replayed in chunks, the frame edge guarded, bit for bit ✅ (12 Sep 2026, branch `panel-ui`)

Phase B's step B2 (proposal E2 of `out/_agents/speed-plan/REPORTS.md`,
prototyped as `out/_agents/speed-dsp/build1`'s `--dsp-lazy`). The pair no
longer runs after every ColdFire instruction: a tick only BOOKS the due
count, and the backlog runs in one chunk at the points where the ColdFire
can observe or affect the cores. Held to the STRICT gate in the end (0
tolerance, both references, 28/28), not the Phase B audio tolerance it was
allowed: the two designs that moved the schedule failed the gate by far
more than an LSB, and the one that ships is the exact schedule replayed.
`dsp.cpp`, `dsp.h`, `rtos.cpp`, `rtos.h`, `machine.h`, `main.cpp`. Default
on in every mode; `--dsp-lazy 0` restores the per-tick path.

### What changed

- **`Coprocessor::sync()`** (`machine.h`, default no-op): "bring the
  co-processor up to everything booked so far". `Rtos::runLoop` calls it
  before `tickTimers()`/`deliver()` at every burst end and `stepOnce` after
  every exact instruction -- the point where the pair's state becomes
  observable (the frame latch, the eDMA gate) and where the old loop had
  already run it (inside each instruction's tick). `OT_DSP_SYNC=0` drops
  those two calls (a measurement knob: what the per-burst sync costs).
- **`DspPair::setLazy(N)`** (`--dsp-lazy N`, default
  `g_lazyDefault` = 4160 = one sample; 0 = exact): `tickInstructions`
  adds `ratio` to `m_due` as before and counts the tick; the backlog runs
  through **`runChunk`** when it reaches N inside a burst, at `sync()`, at
  every host-port touch point (`read`/`write` of the window, the eDMA's
  `pushHalfwords`/`pullHalfwords`/`hostRingEmpty` gate, `runCoreUntil`,
  `blockNote`, `peekWord`), before the idle skip's `tickSamples` (which
  then steps one sample at a time as before), and inside every probe
  (`peekP/X/Y`, `pc`, `executed`, `idleSkipped`, `report`; const, so they
  cast -- what they observe is the pair NOW). The boot (before the Rtos)
  is exact: its report is in every boot log.
- **`runChunk` REPLAYS the tick sequence**: the same `+= m_ratio`
  additions from the same value (every limit the same double), and for
  each, core 0 to it then core 1 to it -- `runDue`'s one pass per tick
  (its 64-quantum never bites on a tick, O16b). So the cross-core
  interleave, every idle step's room and every peripheral event fall on
  the same DSP instruction as under the per-tick schedule; the chunk saves
  the per-tick call and its pass bookkeeping, nothing else. `tickSamples`
  (the ColdFire idle skip, whole samples, 64-quanta) and the exact
  `--dsp-lazy 0` path still go through `runDue`.
- **THE EDGE GUARD** (`predictEdge`): the one event the DSP raises on its
  own that the ColdFire must see at the instruction is the bank word
  (P:0x73, the frame edge). It is predictable: the dispatcher writes it
  when DMA2's source pointer equals 0x8070 or 0x80f0 (a one-slot equality
  window, O8), DSR2 advances one word per ESAI slot exec (`writeSlotToFrame`
  triggers the DMA before the frame callback), and the slot cadence is
  `esaiCyclesPerSlot` = 520 instructions on the DSP's own counter. The
  frame sink records (counter, DSR2) at each callback -- a slot exec -- and
  from that grid point the boundary slot is `togo` slots on; from three
  slots before it until one slot after (or until the write fires) every
  tick is exact (`m_due >= m_edgeGuard` in `tickInstructions`), lazily
  elsewhere; a prediction that finds no new callback retries one ESAI frame
  (8 slots) later. `stepBody`'s bank-write path reports an edge that fires
  outside a window as `edges-late`. Edges inside idle skips are the skip's
  own (whole samples, as before) and counted apart.
- **Counters** on the O16b `OT_DSP_STATS=1` line: `hostR/hostW`,
  `syncs`, `chunks` with the mean and max backlog, `edges` with their
  lateness, `edges-late`, `edges-in-idle-skips`, `guardticks`,
  `predictions`. `OT_DSP_EDGELOG=1`: one stderr line per bank write seen
  from a chunk (the guard's evidence, `out/_agents/speed-b2/edgelog*.txt`).
  No command, reply or stdout line changed.

### The two designs that failed the gate, measured (`out/_agents/speed-b2/`)

1. **The chunk through `runDue` (64-instruction quanta), no guard** -- the
   E2 prototype's shape. Bench **244 / 246 / 244** ms per wall s (+46 %),
   `ready` 7.6 s. Gate: `interdsp.stamps` max |dsample| 16.63 (a run end
   moved a frame period), the PCM 16 frames short and **max |diff| 4301,
   16.6 % of samples differing** (`20260912-142635-b2-lazy`). Not a shift
   (the best frame shift is 0 in every window) and not an LSB drift: at
   frame 49703 the candidate reads 6806, 12851, 22777 where the reference
   has 6689, 11889, 20756 -- a gain ramp one frame ahead, converging to
   1-LSB tails. The frame interrupt was delivered up to a chunk late
   (mean 1141 DSP instructions for the 6 % of edges that fall in bursts,
   max 4158), the block reached the DSP that much later, and where that
   crossed a bank boundary the port's known 15/17-frame jitter moved: a
   parameter block met its audio a frame off.
2. **The same chunk with the guard.** `edges-late` 152 of 413 on the first
   build (the retry after a window waited 128 slots = the boundaries' own
   period, so every retry landed past the next boundary; `edgelog.txt`),
   0 of 412 once the retry was one ESAI frame -- and the gate still failed:
   UART 18309 vs 18301 bytes (a block crossed the PLAY step), stamps
   max |dsample| 46.82, PCM 42 % differing (`20260912-144242-b2-guard2-
   interdsp`); the batch WAV byte-identical but its log's ack tail with
   vector 0x48 (the eDMA completion) acknowledged at other PCs. The
   cross-core interleave: inside a 64-quantum chunk core 0's mailbox
   waits on core 1 end up to a quantum early or late, and with them the
   bank write and the host ring's drain -- by up to 61 ColdFire
   instructions, enough to move both interrupts.

Replaying the tick sequence (above) removed every difference:
`20260912-144621-b2-replay-interdsp` 8/8 with the PCM byte-identical.

### Measured (12 Sep 2026, the same M5 Mac, macOS 26.5; nothing else running; logs under `out/_agents/speed-b2/`)

**The gate** (`tools/emu/ot_emu/oracle/`, final binary sha `0605bde48918`,
`--build-dir` for ctest):

| run | result | report |
|---|---|---|
| `phase_b.sh` vs `ref-1e76ac5` (Phase B tolerances) | **28 PASS, 0 FAIL**, 36 s | `20260912-145609-b2-final` |
| `phase_b.sh` vs `ref-73c2815` | **28 PASS, 0 FAIL**, 3 s (cached) | `20260912-145646-b2-final` |
| strict, no tolerance flag, vs `ref-73c2815` | **28 PASS, 0 FAIL** | `20260912-145702-b2-final-strict` |
| B2 vs itself (determinism) | **27 PASS, 0 FAIL**, 36 s | `20260912-145706-b2-determinism` |

Every check byte-identical, the audio included: `interdsp.pcm` 124,447
frames identical (max |diff| 0, 0 % differing, onset frame 98),
`run3_core0.wav` 330,677 frames identical (onset 282,744), the UART stream
18,309 bytes, 47 run stamps with |dsample| = 0, the boot logs and the batch
log with the pair's own report (executed, idle-skipped, bank latency)
identical -- which is why the default is on in the batch too.
`edges-late` **0** of 741 chunk edges over the bench session (+10,727 in
idle skips), 0 of 413 in the edge log.

**Speed** (`out/_agents/speed/bench.py --dsp`, HEAD = `git archive HEAD`
built in `build-head/`, both plain LTO, alternated round by round;
emulated ms per wall s, the 16 runs' wall in brackets):

| round | HEAD (B1) | B2 | `ready` HEAD / B2 |
|---|---|---|---|
| r1 | 169 (23.69 s) | **203** (19.72 s) | 18.5 / 14.9 s |
| r2 | 166 (24.05 s) | **204** (19.60 s) | 19.6 / 14.5 s |
| r3 | 168 (23.87 s) | **203** (19.70 s) | 18.8 / 14.4 s |
| mean | 167.7 | **203.3 (+21 %)**; wall 23.87 → 19.67 s (−18 %) | 19.0 → **14.6 s (−23 %)** |
| `--dsp-lazy 64` / `1024` | – | 199 / 202 | – |
| `OT_DSP_SYNC=0` | – | 206 (the per-burst sync is free: the host port syncs it first) | – |
| `--dsp-lazy 0` (the per-tick path) | – | 166 = HEAD | 20.1 s |
| no `--dsp` | 1434 | 1418 (noise; the pair is not constructed) | 5.4 / 5.4 s |

**Where the ceiling is** (`stats.py`, the play phase = boot→PLAY + 4 s):
the pair's work is identical to HEAD's -- core 0 763.2 M due, 26.0 M
idle-skipped, **733.2 M interpreted** (HEAD 733.6 M), core 1 324.3 M
interpreted with 61.3 M idle steps (HEAD 324.3 M / 61.3 M) -- and what the
chunk removed is the per-tick wrapper: `runDue` calls 356.3 M → 0.10 M,
passes 709.5 M → 6.2 M, 38.1 M chunks of 9.4 ticks on average (the
firmware makes 8.2 M host-port accesses per emulated second while playing:
8.83 M reads, 25.3 M writes over the phase, most of them the eDMA's
halfwords), 2.3 M guard ticks (0.65 %). Per emulated second the pair now
costs ~4.2 wall s of the 4.9 (the ColdFire ~0.7): ~1 G interpreted DSP
instructions per 4.16 s at ~4 ns each is the vendored interpreter's own
throughput, E4's ground and outside this plan. Profile (`sample`, 10 s
mid-play, `agg.py`): `stepBody` self 25.0 %, `runChunk` 3.8 % (was
`runDue` 7.7 %), `op_Parallel` 5.2 %, the pair 69 % inclusive.

**The panel end to end** (`panel_e2e.py`, `panel_server.py --port 8584
--sound on` on the OTLIVE fixture, this binary): `ready` after 14.7 s;
idle 999.7 emulated ms per wall s, `/status rt` median 1.000 (0.993-1.007),
child 31 % of a core; PLAY: the trig rows chase (31 LED-state changes in
12 s), **playing 206 emulated ms per wall s, `rt` median 0.203**
(0.190-0.226; O15f/B1 measured ~0.15-0.17), child 97 %; `/audio/pcm` of
the last second 44,100 frames, 88,200 non-zero samples; STOP closed
`take-003.wav`, 406,020 frames = 9.2 s, 1,624,124 bytes; `rt` 0.993 back
at idle, no fault, no restart.

**Shutdown** (`shutdown.py`, `--interactive --dsp` with `audio start
main`): `quit` 22 ms, EOF 22 ms, SIGTERM 22 ms, SIGTERM with `run 2000` in
flight 23 ms. No thread was added (the chunk runs on the caller's thread),
so there is nothing for `-fsanitize=thread` to find; the determinism run
above is the deterministic-handshake proof.

### What it does not do

- It does not batch across the host port: a chunk ends at every host-port
  access and burst end, and while playing the firmware touches the port
  34.1 M times in 356 M instructions (the eDMA's halfwords included), so
  the mean chunk is 9.4 ticks and N (64..4160) barely matters.
  The gain is the wrapper, not the interpreter; the interpreter is ~85 % of
  the `--dsp` wall.
- The schedule-moving designs are not shipped, not even opt-in: they
  failed the Phase B contract by orders of magnitude (16-42 % of samples,
  thousands of LSB), because the port's frame/bank phase is one slot from
  a boundary and any lateness of the frame interrupt or any cross-core
  skew moves it. The contract's LSB expectation (O12) was about the
  interleave inside a chunk with the ColdFire's view held; that view is
  what has to stay exact.
- The edge guard is payload A's: it knows the ring (X:0x8000-0x80ff), the
  two boundaries and P:0x73. A payload that moves them gets no window and
  the edge lands a chunk late (`edges-late` says so); `--dsp-lazy 0` is
  the fallback.
- `OT_DSP_STATS` prints at destruction, as in O16b; `OT_DSP_EDGELOG` is a
  diagnostic and prints nothing without the variable.

## Milestone O17 — `--dsp-rt`: the DSP cores as JIT workers on the lockstep schedule ✅ built, ⚠️ not real time (12–13 Sep 2026, branch `panel-ui`)

The spike (`out/_agents/jit-spike/SPIKE.md`) proved the vendored JIT
(dsp56300 at `3c01813f`, HAVE_ARM64) executes both of this firmware's DSP
programs once five defects are patched, and that free-running cores are a
dead end (the frame protocol reads the bank id with no ready check and
halts on thread-level jitter). This milestone builds the design it
recommended instead: **the ColdFire stays the master of emulated time and
O16c's booking is kept exactly, but the backlog is executed by two worker
threads under the JIT** — one per core, each run to the booked count and
never past it — so the ColdFire's bursts and the cores' chunks overlap in
wall time and the ordering the firmware depends on is lockstep's by
construction. `--dsp-rt` is opt-in, `--interactive` only; every other mode
is untouched (the strict oracle: 28/28 byte-identical, ctest 7/7). The
panel spawns it with `--sound on` and falls back to `--dsp` when it cannot
start. **Real time was the target and is not reached: the unit plays at
0.62–0.65x (3.2x the lockstep 0.2x), for reasons measured below.**
`dsp.cpp`, `dsp.h`, `machine.h`, `rtos.cpp/.h`, `main.cpp`,
`tools/patches/dsp56300.patch` (vendor/dsp56300 in place),
`tools/panel/panel_server.py`, `tools/panel/README.md`.

### What changed — the design as built (`dsp.cpp`, "THE REAL-TIME MODE")

- **Workers on the lockstep schedule.** `DspPair(ratio, ips, rt=true)`
  starts two pthreads (16 MB stacks — the JIT compiles on the core's
  thread; `ThreadPriority::High` = QoS user-initiated; the ColdFire's
  thread joins that band under `--dsp-rt`). Each waits for its boot ROM
  to jump (`sendWord` says so and records the core's **offset**: lockstep's
  `executed := limit` while held, so `executed = counter + offset` from
  then on), then loops: read the posted due count (one shared cache
  line, `m_rtDue`/`m_rtGen`; the worker subtracts its offset and adds the
  lead), run `execJit()` — the peripheral service, then one block and its
  linked children — while its counter is below the target, publish the
  counter every 256 instructions and exactly when it stops (`reached`,
  its own line), spin 200 µs on an empty target, then park on a condition
  variable (the poster stores the count, bumps the generation and looks
  at `parked`, both seq_cst, so a post is never lost).
- **The touch points post; observing ones wait for nothing new.** Every
  O16c touch point (sync at burst ends and exact steps, host-port
  read/write, `pushHalfwords`/`pullHalfwords`/`hostRingEmpty`,
  `tickSamples`, the probes) goes through `rtCatchUp`: a post when the
  count moved by a quantum (writes 32, reads 32), and a wait only when a
  core LAGS the count by more than `OT_RT_LAG` (4160 = one sample; read at
  the burst ends every 512 counts). A core behind the count only makes the
  host look faster to it — a word lands earlier in DSP time, a command is
  taken earlier — which the protocol lives with; a core AHEAD is what
  broke the spike, and the target forbids it. Tick booking is unchanged
  (`m_due`, the boot's per-instruction ratio and the RTOS's per-sample
  clock); the boot posts every 512 ticks (it has no sync).
- **A bounded lead.** `OT_RT_LEAD` (default 8320 = 2 samples): the workers
  may run that far ahead of the count. Traced through the frame protocol
  the DSP's own timeline is unchanged by it — it sees the host's actions
  L later in its time, the ColdFire sees the bank-word edge L earlier —
  and the double-buffered blocks land well inside the frame; **4 samples
  measured healthy, 8 stalls the protocol** (`edgesinpull` 13 at 16, core
  0 parked at P:0x97 with its bank word untaken: the next bank word lands
  while the ColdFire is still inside the previous frame's bus-paced
  read-back pull), which is the firmware's timing assumption the spike
  named.
- **The bank-word edge.** Every peripheral write made by JIT code carries
  the PC of the instruction (the vendored `Jitmem::storePcCurrentOp`), so
  the HDI08 transmit callback on core 0's thread identifies P:0x73 →
  HOTX and raises an atomic count (`m_edgePending`, raised inside
  read-back pulls too, as `stepBody` has it); `Rtos::runLoop` asks
  `Coprocessor::edgePending()` every 64 instructions of a burst and ends
  it, and `sync()` applies the existing host-word hook on the ColdFire's
  thread (`rtApplyEdges`, with the lateness recorded: the count minus the
  edge's executed count). O16c's edge guard is not the default: as a
  per-tick rendezvous (`OT_RT_GUARD=1`, 29.9 M guard ticks in 4 s) it
  costs nothing measurable and changes nothing measurable — 583 vs 581
  emulated ms per wall s, mean lateness 85 vs 116 DSP instructions —
  because the lead already keeps the workers ahead of the count.
- **The two cores' interleave.** Each worker holds itself within
  `OT_RT_SKEW` (512) instructions of the other (`rtSkewWait`: the mailbox
  handshake at P:0x74/0xa3 and 0x57/0x8d would otherwise spend a core's
  budget spinning on the other), except when the other is idle for the
  current post (at its target, stopped at a skip's edge, its pull's word
  there) — ❌ without that exception core 1 waited the full 200 ms
  timeout 728 times in one `run 250`. A read-back pull runs its core past
  the count until HOTX holds the word (`RtCore::pred`), and the other core
  follows it to the same point, as `runCoreUntil` steps the other core.
- **The idle skip** (`rtTickSamples`): the whole skip is posted with the
  workers armed to stop at the first bank-word edge inside it
  (`m_skipArmed`/`m_skipEdge`); the ColdFire's clock lands on the sample
  boundary after the edge (lockstep's per-sample grain, `skipedges`), the
  targets come down to it, and the edge is delivered there.
- **Host commands** go through the library's cross-thread door
  (`injectExternalInterrupt`) and a per-core `kick` the worker turns into
  the core's interrupt queue before its next block — ❌ a zero peripheral
  delay stored from the ColdFire's thread was overwritten by the core's
  own service and the command waited for the next ESAI slot, up to 520
  instructions: 29 M extra exact ColdFire steps behind the eDMA's drain
  gate in 2 s. ICR host flags via `setPendingHostFlags01`; HCP is not
  raised in HSR (the core's register); an INIT with TREQ (never written by
  the firmware) does not clear the receive ring from this thread
  (`treqdropped`).
- **The shared window** is one memory through the MMU: after the two
  `Memory` objects exist, one 256 KB shm object is mapped `MAP_FIXED` over
  words 0x30000–0x3ffff of all six views (2 cores × P/X/Y), verified
  word for word at setup; the mode is refused when `Memory` is not
  MMU-backed. `setSharedWindow`'s redirect and cross-core opcode-cache
  hook and the write hook are not installed (the JIT reads and writes
  through host pointers; the hook would touch the other core's JIT from
  the wrong thread).
- **The audio pipe**: the ESAI sink on core 0's thread pushes de-rotated
  frames into the ring under `m_streamMx`; `setAudioStream`,
  `takeAudioStream` and `streamStatus` lock it. No pacer thread: wall
  pacing is `pace on` as before.
- **The gate in bursts.** Behind the eDMA's drain gate the exact loop
  steps one instruction at a time (~100 ns each, bit-exact completion
  timing for the lockstep modes: 18 M steps in 4 s); the rt mode steps the
  gate in bursts of 32 (`rtos.cpp`, the completion lands at most 32
  instructions late).
- **The eDMA mover's block notes** (`Rtos::installHostPortMover`) read
  DMA0's pointer and the landed words through `peekWord` at every
  completion; they are the block log's and the block dump's, and are now
  made only when one of those is on (the note string was built and
  dropped otherwise) -- under `--dsp-rt` those are the core's thread's
  registers and memory, and every one of the thread sanitizer's reports
  was that read against the DMA's write (below). Byte-neutral: the log's
  content when on is what it was.
- **The poll fast-forward, JIT edition.** A block re-entered eight times
  in a row with no DO loop open, nothing pending and no pull running is a
  poll (P:0x57, 0x8d, 0x97, 0xa3: one instruction on itself), and payload
  A's three-block DSR2 poll re-entered at its head P:0x4b is the one
  multi-block loop allowed (its iteration count in b1 — the DSP's own idle
  meter, written to X:$3f80/$3f81 after the bank word — is kept faithful,
  seven instructions per skipped iteration); the worker then advances to
  its next peripheral event through `DSP::idleStep` and executes the poll
  once. Measured: it matters at idle (the cores cost ~0.2 of a core each
  at 1.00x idle, `xmips` 0.4) and hardly while playing — on this fixture
  core 0 executes 180–190 M of its 183.5 M instructions per emulated
  second, i.e. the DSP is loaded ~95 % and there is nothing to skip.
- **Faults never block the ColdFire**: a PC outside P memory stops the
  core (`faulted`, the last 64 block-entry PCs in the report); a core that
  does not reach the count within 2 s of a ColdFire wait is faulted by the
  waiter; a read-back word not there within 100 ms is `not in time`.
  `~DspPair` sets stop, wakes and joins the workers before anything they
  touch is destroyed; `quit`/EOF go through the existing path.
- **Commands and knobs**: `rtstatus` (`--dsp-rt` only; MIPS per core and
  executed MIPS, busy fraction, worker CPU seconds, core 0's ESAI frames,
  the count and each core's lag, posts/wakes/parks, waits, edges raised /
  applied / inside pulls with their lateness, skip edges, skew waits,
  fast-forwarded instructions, pulls and their time, read-back words not
  in time, dropped host words, faults, the knobs, the first read-back
  words not in time with both workers' state), `cfstatus` (any mode: the
  ColdFire's instruction count and clock — the rate meter that settled the
  bottleneck below), and `OT_RT_LAG / LEAD / SKEW / POSTQ / READQ /
  READWAIT / CHECKQ / TICKPOST / SPIN_US / FF / GUARD / DOITER /
  WORKER_QOS / TRACE` (diagnostics; the defaults are the mode) plus
  `OT_SELFPROF=<hz>` (an in-process sampler of the main thread, because
  the macOS `sample` tool, `lldb -p` and TSan's symbolizer all hang on
  this process — its MMU-backed DSP memory maps three 64 MB views per
  core). The interpreter's per-instruction instruments (`--dsp-trace`,
  `--dsp-pcwatch`, `--dsp-stopwatch`, `--dsp-watch`, `--dsp-map`,
  `--dsp-writes`, `--dsp-no-idle`) do not observe the JIT workers (a note
  in the boot log says so).
- **The panel** (`tools/panel/panel_server.py`, `tools/panel/README.md`
  "Hearing the unit"): `--sound on` spawns the child with `--dsp-rt`; an
  rt child that reports `dsp-rt : cannot start` or exits before `ready`
  is respawned once with the lockstep `--dsp`, `backend_note` says why and
  `sound_note` says what to expect (~0.65x rt, ~0.2x lockstep); `/status`
  adds `sound_rt`; `GET /rtstatus` relays the child's `rtstatus` (`ok`
  false with the reason when the child has none). The owner's
  `out/emu/ot_emu` predates `--dsp-rt`, so until `pgo.sh` rebuilds it the
  panel takes the fallback (measured below).

### Every vendor fix (`tools/patches/dsp56300.patch`, 864 lines, 20 files; proven with `git apply --check` on a scratch worktree of `3c01813f`, the applied diff byte-identical to the patch)

The spike's five, each found by an instrument (SPIKE.md): (1) the JIT
function tables pre-sized to all of P at setup (`notifyProgramMemWrite
(sizeP-1)`: they grow only with the P addresses the same core writes, and
core 1's entry P:0x38000 is written by core 0 through the window — a null
call on the core 1 thread); (2) `setDmaTriggerOnArm` (`dma.cpp`
`checkTrigger`: a channel armed with its request already holding fires
once for a non-host-stepped core too — DMA2 armed with TDE set never
started); (3) `JitConfig::dynamicFastInterrupts = true` (payload A's
dispatcher lives inside the vector area P:0x40–0xaf, reached by a plain
`jmp`; the JIT compiled it as two-word fast-interrupt blocks returning to
the interrupted PC); (4) `pushPCSR` pushes the next PC in Dynamic mode
unless the processing mode is FastInterrupt (`jitops_helper.cpp`, a csel;
`jsr` from such a block pushed the interrupted PC and re-entered forever);
(5) the peripheral-write PC (`jitblock.h/.cpp` `m_pcCurrentOp`,
`jitmem.h/.cpp` `storePcCurrentOp` in both `writePeriph` emitters,
`callDSPMemWritePeriph` invalidates it after; `dsp.h`
`get/setPcCurrentInstruction`). Plus `setPeripheralsUnderMaskedInterrupt`
(O8's defect 3 as a flag for a non-host-stepped core), the HDI08 transmit
FIFO (`setTransmitFifoDepth`, 1024 here) with the receive-side burst
drain, and three of this milestone's own: (6) **the FIFO transmit
request is level-sensitive** (`hdi08.cpp`: with a FIFO, room is a standing
request and the DMA fills it as a burst in one service — ❌ the spike's
edge-triggered shape delivered one word per service whenever the host
drained the FIFO between two services, and every core-1 read-back pull ran
its core 5000–8300 instructions past the count; then every eDMA push
found both cores ahead and its drain gate stepped 1100+ instructions
instead of lockstep's 494); (7) the DRS bound check (`dma.cpp`: the
request source is a 5-bit field indexing a 21-entry array; the spike
crashed in `setDCR` on a garbage DCR); (8) `setDelayCycles(0)` stores a
zero target instead of reading the DSP's instruction counter (it is
called from the host's thread by `writeRX`/`readTX`/`clearRX`); and a
diagnostic getter (`getExecPeripheralsFunc`). The spike's
diagnostics-only hunks (`peripherals.cpp` DSR2/peripheral-write logs,
`jitblockchain.cpp` compile timer) are not carried.

### Measured (12–13 Sep 2026, the M5 Max, macOS 26; logs under `out/_agents/jit-build/`; a stuck spike process, `build-tsan/ot_emu --dsp-rt` pid 51757 at 98 % of a core, ran throughout — not this session's to kill)

**The gate.** `oracle.sh out/emu/ot_emu.ref-73c2815 <cand> --build-dir`,
strict, no tolerance: **28 PASS, 0 FAIL** (ctest 7/7) on the LTO-off build
(`20260912-230157-jit-build-early`) and on the LTO build
(`20260912-235112-jit-build-lto`, then `20260913-000250-jit-build-lto-final`,
`-final2` and `20260913-001015-jit-build-lto-final3` on the final source,
sha `b98fd9b51b9e`). Batch, `--interactive --dsp` and no-DSP are
byte-identical.

**Speed** (`bench.py <tag> --dsp --dsp-rt`, the extra arguments forward as
they are; 4 emulated s of PLAY in 16 × `run 250`, emulated ms per wall s):

| build | `--dsp --dsp-rt` | `--dsp` (lockstep) | no `--dsp` | `ready` rt / lockstep |
|---|---|---|---|---|
| LTO (`build-lto`) | **664** (6.03 s) | 197 (20.33 s) | 1326 (3.02 s) | 7.9 s / 15.4 s |
| LTO off (`build`) | 578–602 | 180–186 | 1072 | 9.9 s / 16.7 s |

Paced (`pace on 1`, the panel's shape): **rt median 0.647 (0.594–0.684)**
over 3 minutes of PLAY (port 8582, below), 0.999 (0.989–1.010) idle. The
target — ≥ 1000 flat out, 1.00 ± 0.02 paced — is not met.

**Where the wall goes** (LTO off, 4 s of PLAY = 6.9 s wall, `rtstatus`
and `cfstatus`): the ColdFire executes the same 85.0 M instructions per
emulated second in all three modes (`cfstatus`: no-DSP 340215712 in 4000
ms, lockstep 340211222, rt 342733498), so its own emulation is the no-DSP
3.7 s (LTO: ~2.8 s) plus ~1.1 s of posts (5.6 M, ~200 ns each: two
seq_cst atomics on a line both workers spin on); the waits are the idle
skips (1.3–1.6 s: the cores' work the ColdFire cannot overlap) and the
read-back pulls (0.7 s = 14 µs each: the command's handoff, the handler,
the 256-word FIFO burst at ~30 ns a word on the DSP side and the 256 pops
on the ColdFire's); explicit lag waits 0.01 s. Core 0 is busy 0.37 of the
wall at ~300 MIPS (115 executed MIPS: 190 M executed instructions per
emulated second, the DSP is loaded), core 1 0.35. Per frame (0.363 ms
real) that is ~0.34 ms of ColdFire (0.25 with LTO) plus ~0.24 ms of core
0, serialized except within the lead — which the protocol caps at ~4
samples (above) — so the practical ceiling of this design on this build
is ~0.65x, ~0.8x with LTO+PGO, and real time would need either the
cores a frame ahead of the ColdFire's clock (the protocol forbids it) or
a ColdFire that runs its 85 M instructions in well under 0.6 s.

**The rendezvous (the design's go/no-go).** A post is one store and one
generation bump (~200 ns with the workers spinning on the line, 1.4 M per
emulated second while playing); a wait that has to run a lagging core
the last sample costs 30–60 µs and happens 20–350 times in 4 s; the
per-tick guard costs and gains nothing measurable (above); the first
read-back word of a pull is there 14 µs after the kick on average.
Wakes: 100–300 per 4 s with the 200 µs spin (with no spin, 4.5 M wakes
and 213 emulated ms per wall s: every pull waited for a parked worker).

**The panel** (`panel_e2e_rt.py`, `panel_server.py --port 8582 --sound
on` on the OTLIVE fixture, the LTO binary as `--port-bin`): `ready` after
7.6 s, `sound_rt` true; **idle** 999.7 emulated ms per wall s, `/status rt`
median 0.999 (0.989–1.010), child 67 % of a core (`ps -M`: ColdFire 17 %,
the two workers 24 % each spinning idle); **PLAY 181 s**: 117110 emulated
ms in 181.18 s wall = 646 per wall s (per-second 577–692), `/status rt`
n=180 median 0.647 (0.594–0.684), child 283 % (93 / 95 / 95 %); frames
kept coming for the whole run (`audio` captured 6,615,700 frames, no
halt); `rtstatus` after PLAY: edges 347,574 applied 347,574,
**edges-in-pull 0, faults 00, dropped 0, pullshort 0**, waits 266, edge
lateness mean 160 DSP instructions (max 5180), skew timeouts 0; the take
`out/_panel_takes_8582/take-001.wav` 5,564,210 frames = 126.2 s, 22.3 MB,
decodes. LED chase by wall clock (LED-state changes on `/leds`, two per
16th): 122 ms mean in the first 12 s of PLAY (~1x: the first bar, before
the load builds) and 122 ms mean / 123 ms median again after 60 s of
steady PLAY on a second run (port 8583, rt 0.619) — at 0.62x a 16th takes
~200 ms of wall; the running light's cadence does not follow it, which is
a question for the panel's LED decoding, not this milestone.
**Fallback** (`panel_fallback_8584.py`: `panel_server.py --port 8584
--sound on` with `--port-bin out/emu/ot_emu.ref-73c2815`, a binary without
`--dsp-rt`): the rt child prints its usage and exits rc 2 on the unknown
flag before `ready`, the server respawns it with the lockstep `--dsp`,
`ready` after 18.8 s, `/status` `sound` true, `sound_rt` false,
`backend_note` "the --dsp-rt child did not boot (exited (rc 2) before
ready; last: usage: ...); respawned with the lockstep --dsp",
`sound_note` says the lockstep child plays at ~0.2x, `/rtstatus`
`{ok: false, result: "PortError: unknown command rtstatus"}`, `rt` 1.00
idle; SIGTERM on the server leaves no child. Until `out/emu/ot_emu` is
rebuilt from this tree (`pgo.sh`) that is what the owner's panel does.

**A/B** (`out/_agents/jit-build/ab/`: `lockstep-ref-73c2815.wav` = the
spike's `run-ref-4s` capture on the frozen reference, `rt-lto.wav` = the
same `rtdrive.py` script on this binary with `--dsp-rt`, 199,358 vs
199,373 frames, `cmpwav2.py` and `perwindow.py`): onset frame **78 vs 82
(4 samples)**; RMS **−5.13 vs −4.39 dBFS (0.74 dB)**, both peak at
32767 (the fixture clips); per 0.25 s window the best lag is −4 samples
in 13 of 17 windows with signal and +60 / −36 in the others (the
15/17-frame jitter O16c documented, a loop restart moved a frame), the
gain fit 0.55–0.98, the residual median −5.4 dB (−15.7 dB in the last
second, −10 dB in the first): the same loops at the same level and time,
not the same samples — the functional contract, not the Phase B bytes.
Both WAVs are in the log dir for listening.

**Shutdown** (`shutdown_rt.py`, during a paced PLAY with `audio start`):
`quit` 47 ms, EOF 37 ms, SIGTERM 18 ms; no process left.

**Thread sanitizer.** A Debug build with `-fsanitize=thread -O1 -DNDEBUG`
(`build-tsan`; NDEBUG because the vendored `Jitmem::writeDspMemory`
asserts on a static out-of-range address that the MMU scratch area
absorbs in Release): the JIT-emitted code is not instrumentable, only the
C++ handshakes are. With TSan's own symbolizer on, the child hung in it
after `ready` (the same macOS symbolication that hangs `sample` and
`lldb -p` on this process); with `symbolize=0` (`tsan-run/`, addresses
symbolized offline with `atos -l 0x100000000`) it booted to `ready` in
322 s and played, and every report -- 10 in the first 2.5 s of PLAY --
was one pattern: the eDMA mover's `peekWord` reads (DMA0's DDR through
`Peripherals56362::read`, the landed words through `Memory::get`) on the
ColdFire's thread against core 0's DMA writes (`DmaChannel::execTransfer`
from `HDI08::exec` in the worker's peripheral service) -- 13 reports by
the time that run was stopped, 7 at `Memory::get` and 6 at
`Peripherals56362::read`, no other pattern. Fixed as above; the rerun on
the fixed binary (`tsan-run2/`, same launch) booted to `ready` in 343 s
and played the whole 20 s of PLAY (1344 s wall, 930,822 frames captured,
the take decodes, rc 0) with **no report**: no `tsan.log.*` written and
no ThreadSanitizer line on the child's stderr.

### What it does not do

- **Real time.** 0.62–0.65x paced, 664 emulated ms per wall s flat out
  with LTO. The lockstep-schedule premise — the cores never past the
  ColdFire's count, at most a few samples ahead — serializes the cores'
  frame work with the ColdFire's own emulation; the counters above say
  which part is which. A larger lead breaks the frame protocol (8
  samples measured), so the next lever is the ColdFire itself (its 85 M
  instructions per emulated second at ~90–120 M per wall second) or a
  read-back path that does not cost 14 µs a block.
- The audio is functional, not byte-identical: the O16a Phase B contract
  cannot be met by any threaded design (O16c), and `phase_b.sh` is not
  run on `--dsp-rt` captures.
- `--dsp-rt` is `--interactive` only (the batch keeps the interpreter);
  cue and core 1 are still not captured; the DSP-side instruments do not
  see the workers.
- The workers spin 200 µs before parking: ~0.2 of a core each at 1.00x
  idle.
- `rtstatus` reads its counters without a rendezvous (racy by design,
  diagnostic); the report at exit and the probes rendezvous first.
- The macOS `sample`, `lldb -p` and TSan's symbolizer hang on this
  process (the MMU-backed DSP memory's six 64 MB views); `OT_SELFPROF` is
  what profiles it.

## Milestone O17b — the fenced deep lead: `--dsp-rt` plays faster than real time ✅ (13 Sep 2026, branch `panel-ui`)

O17 left the unit at 0.62–0.65x with sound, and named the cost: the cores
could run at most ~2 samples ahead of the ColdFire's clock (8 stalled the
frame protocol), so the ColdFire waited for them through every idle skip
(1.3–1.6 s per 4 s of play) and every read-back pull (0.7 s), and its own
emulation (~0.7 s per emulated second) barely overlapped the cores' frame
work. This milestone lets the workers run **a whole frame ahead** (16
samples = 66,560 DSP instructions, `OT_RT_LEAD=frame`, the numeric knob
kept) and puts **one fence** at the only timing-assumptive point of the
protocol instead of a fixed lead. With it, plus the host port's rings and
DMA made cheap, the same binary plays the OTLIVE fixture at **1015–1058
emulated ms per wall s flat out with LTO** (`bench.py --dsp --dsp-rt`,
four runs; O17: 664), and the panel's paced child holds `rt` 0.999 over a
10 s PLAY and a median 0.981 over a 3-minute one with the test harness
polling it. The strict oracle is 28/28 byte-identical on every old mode
(the lockstep modes got faster too), the C++ handshakes are TSan-clean
after one fix, shutdown is 22 ms. What is not met, both by a little: the
A/B against the lockstep take is 1.34 dB quieter in RMS (the contract
said 1 dB; O17's own take was 0.74 dB), and the paced 3-minute `rt` is
0.98, not 1.00 ± 0.02 — for reasons measured below. `dsp.cpp`, `dsp.h`, `machine.h`, `rtos.cpp/.h`,
`main.cpp`, `tools/patches/dsp56300.patch` (vendor/dsp56300 in place:
`hdi08.h/.cpp`, `dma.h/.cpp`, `dsp.h`, `jit.h`), `tools/panel/README.md`.

### The protocol, measured (`OT_FENCE_TRACE=1`, lockstep `--dsp`, the OTLIVE fixture playing)

Every host-port transaction, every INTC0 mask change of the frame source
and every INTC0 acknowledgement on stderr with its sample. One frame,
identical in all 110 traced:

| Δ samples from the bank word | who | what |
|---|---|---|
| 0.000 | core 0 | `P:0x73` writes the bank id into HOTX (the edge) |
| 0.004 | ColdFire | ack vector 0x41; the handler **masks INTC0 source 1** (`pc 4000aae0`) |
| 0.004 / 0.015 | ColdFire | `0x8c` (frame) and `0x89` (read-back, 512 words) to core 0 |
| 0.70 | ColdFire | pulls 256 + 128 + 128 words from core 0 (eDMA ch 1 → 6 → 7), ack 0x4f |
| 0.71 | ColdFire | `0x89` to core 1, pulls 256 words (ch 1), ack 0x49 |
| 0.72 … 1.30 | ColdFire | `0x88` + push 672 (core 0), 672 (core 1), 64 (core 0), 128 (core 1), 128 (core 0) halfwords; ch 0 completes and acks after each |
| 1.30 … 3.2 | ColdFire | eDMA channels 2–5 kicked and completed 30 times (the EMAC mixer's own moves) |
| 3.24 | ColdFire | `0x88` + push 512 halfwords (core 0, the forwarded read-backs), ack 0x48 |
| 3.37 | ColdFire | **unmasks source 1** (`pc 40004bc8`) — the exchange is over |
| 16.00 | core 0 | the next bank word |

So the ColdFire's whole exchange is **3.4 samples** of its clock, ISR-driven
(the eDMA completion chain), and the firmware's own end-of-frame mark is
the unmask of the source it masked at entry. That unmask is what the
fence opens on. The dispatcher's other side, read off the payloads: at
each ring boundary core 0 selects a bank (`P:0x54`/`0x64`) and **patches
the host handlers' masks** (`move x0,p:>$58c` / `p:>$59b` at `P:0x75`/
`0x77`, `x0 = $3fff` or `$5fff`), so a host word `0x6080` lands in the
bank the DSP is NOT processing — the frame it processes reads the bank the
previous exchange filled, and every command taken after the patch lands in
the other bank. Core 1 does the same from the mailbox word (`P:0x59`,
`p:>$371`/`p:>$380`). So "finished handling frame N" has to cover the
whole exchange, not only the pulls: a command taken after the patch would
be masked into the wrong bank.

### The design, as built (`dsp.cpp`, THE FENCE AND THE SERVICE; `Rtos::peripheralWrite`)

- **The fence.** `Rtos::peripheralWrite` watches INTC0 source 1's mask
  across every INTC0 write and tells the co-processor `frameHandling()`
  (masked: the handler entered) and `frameHandled()` (unmasked: the
  exchange is over; `Coprocessor`, `machine.h`). Core 0's bank-word write
  (`P:0x73`) **closes** the fence (the HDI08 write callback, as O17
  identifies the edge); `frameHandled()` opens it. A worker whose next
  block starts at `P:0x73` while the fence is closed stops there: its
  clock is frozen (its ESAI does not tick), it publishes its position, and
  the lag bound, the skew bound and the idle skip count it as idle — it
  cannot come until the ColdFire opens it, and the ColdFire must go on to
  do so. `P:0x73` is declared a **volatile P address** in core 0's JIT
  (`Jit::addVolatileP`, vendored): a volatile address is never linked as
  a child block and every block generated later stops before it, so the
  worker regains control exactly there (the `bra int_000073` at `P:0x63`
  used to jump straight into it).
- **The fence applies only while the ColdFire takes frames** — the frame
  clock on (`Coprocessor::setFrameClock`, from `Rtos::setFrame`) or an
  exchange in flight (`frameHandling` without its `frameHandled`; STOP
  lands inside an exchange one time in five). ❌ Measured before this
  rule: the firmware's `ICR = 0x81` (INIT, an interface reset) drains the
  port during the boot, core 0 looped through frames nobody took, froze at
  its second bank word for the whole load, and spent the first seconds of
  PLAY 1.1 G instructions behind the ColdFire's clock with the sequencer
  running 4.7x too fast (`exec0 52 M` against `due 1169 M` at `ready`).
- **The service.** A held or idle worker still serves the host. A host
  command (`kick`), pushed words (`svc`, new) or a pull (`pred`) makes it
  run its pending interrupts through their handlers to their `rti`
  (`DSP::execInterrupts` per vector, then `exec()` until the PC is back
  and the mode is not `LongInterrupt`, then `execDefaultPreventInterrupt`)
  and its peripheral service (the vendored `execPeripherals`: the host
  DMA's drain and FIFO fill, the ESAI and the timers as of the counter),
  with the main line held where it is (`rtService`). The chip's DMA and
  interrupts run beside the core; nothing a handler does depends on the
  main line. A worker in the skew wait (spinning for the other core)
  yields to the same three requests and serves them with one block. The
  bank take (`rxTake` outside a pull) sends a `svc` too: HTDE, the bit
  `P:0x97` polls, is set by the core's own service.
- **Gated edge delivery.** An edge is no longer applied when raised. The
  worker puts its executed count (the DSP's own clock, in due units) on a
  16-deep SPSC ring; `Coprocessor::edgePending()` — asked every 64
  instructions of a burst — is true only when the ColdFire's clock has
  reached the oldest edge, and `rtApplyEdges` applies exactly those. The
  idle skip (`rtTickSamples`) is bounded by a produced edge: at or behind
  it the edge is delivered first (no skip), ahead of it the skip ends on
  the sample boundary after it; with no edge yet the whole skip is posted
  with the workers armed to stop at the first bank word inside it, as O17
  had it. So the frame interrupt arrives at the sample the DSP's clock
  says — lockstep's timing — however far ahead the DSP produced it
  (`edgelate mean 25.7, max 67` DSP instructions in bursts: the burst's
  grain; `skipedgelate mean 2127`: the sample grain). ❌ Without the gate a
  frame-deep lead delivers frame N+1 as soon as the handler finishes frame
  N: the sequencer would run at the exchange's rate (3.4 samples a frame),
  not the DSP's.
- **The poll lead** (`OT_RT_POLLLEAD`, 2 samples). The lead is for
  executed work; the poll fast-forward (an idle step is ~40 ns for 520
  instructions, i.e. the DSP's clock races at ~13 G instructions per wall
  second inside a poll) is bounded differently. The one poll whose end is
  the ColdFire's act — the HTDE wait after the bank word, `P:0x97`, the
  take — never carries core 0's clock more than the poll lead past the
  ColdFire's clock, and at that bound the core waits idle for the ColdFire
  to move. ❌ Measured with the frame lead on it (three stalls in ~200 s
  of play, `stall_hunt.py`): in the microseconds the ColdFire took to get
  to the take, core 0 burned a whole frame of its own clock at `P:0x97`,
  missed its next ring boundary (the DSR2 equality window is one word),
  took a 32-sample frame, DMA2 ran dry (`dsr2=008070 dco2=0000ff`, the
  dispatcher's poll never saw the boundary again) and the frame protocol
  stopped for good. The DSP's own waits — the ring boundary at `P:0x4b`,
  the mailbox at `P:0xa3` / `0x57` / `0x8d` — keep the work lead (the
  skew bound already ties the mailbox waits to the other core). `P:0x4b`
  is a volatile address too: the fast-forward must fire at the poll's
  head, before the `movep DSR2` read, and the JIT linked the loop's `bra`
  into it — O17 had executed that poll, ~30k instructions a frame.
- **The host port's rings and DMA** (vendored, `tools/patches/dsp56300.patch`,
  22 files, 56 hunks, `git apply --check` on a scratch worktree of
  `3c01813f` clean and the applied diff byte-identical to the patch):
  - `HDI08`'s two rings are the lock-free `RingBuffer<TWord, 8192, false>`:
    both are single-producer / single-consumer and no caller pushes into
    a full ring or pops an empty one unasked, so the locking ring's
    semaphore pair (two contended atomic read-modify-writes per word, on
    both threads) was pure cost — the frame's 2,944 words paid ~70 ns a
    word each side. The lockstep modes use the same rings and got faster
    (below); their bytes did not move (the oracle).
  - **Burst transfers on the host port** (`DmaChannel::burstFromHost` /
    `burstToHost`, driven from `HDI08::exec` when a FIFO is configured):
    a request-triggered single-counter channel reading HORX or writing
    HOTX moves up to the FIFO's depth of words in one call with the
    per-word peripheral dispatch, callbacks and delay resets taken out
    (`popRXFast` / `pushTXFast`); the block-end bookkeeping is
    `execTransfer`'s. The per-word path is kept for any other shape.
  - The host side pushes a block's words into the ring in one call (the
    lane model resolved once: every halfword lands on TXM:TXL and sends)
    and pops a pull's words in one call (`readTXBulk`: one delay reset for
    the batch instead of one per word on a line the core's thread reads at
    every block). `OT_RT_BULK=0` is the per-word path.
- **Posts** every sample (`OT_RT_POSTQ`/`READQ` 4160, were 32): with a
  frame of lead the workers do not need the count more often, and O17's
  1.4 M posts per emulated second (~200 ns each on a line both workers
  spin on) become 28 k.
- **The DO-loop time slice** (`OT_RT_DOITER` 64, was 0): a DO loop yields
  its block every 64 iterations so a stopped-core service or a periph
  service is never further away than a few microseconds; measured 1033
  against 993–1016 unbounded, interleaved.
- **Workers spin while the host is active** (a command, push or pull
  within 2 ms) instead of parking after 200 µs: a parked core's wake cost
  core 1's read-back pull tens of microseconds once a frame.
- **Diagnostics.** `rtstatus` grew: the fence's state (`fence= inexch=
  frameon= edgesq= c0fenced=`), `fenceopens`/`fencewaits`, the services
  (`svc0/1`, `svcint0/1`), the ColdFire's waits by cause in wall seconds
  (`cfwait skip= lag= pull= pullword= kick= push= post= fenceopen=`), each
  worker's wall time split (`busy= idle= fence=`), core 0's HSR/HCR/HPCR,
  peripheral target, TCR, DCR2/DSR2/DCO2 and counter (as the worker last
  published them, with the MIPS and at every idle transition — never a
  look at the worker's data from the ColdFire's thread), the knobs, and
  the last 200 protocol events (`proto:` —
  commands, pushes, pulls, eDMA kicks and completions, the frame and eDMA
  acks, edges with their lateness, handled/masked, the frame clock; a
  1024-deep ring always on in the rt mode). `cfstatus` adds `pc=`.
  `edmastatus` (new) prints the eDMA's booked completions, IRQ lines,
  gated-wait count and INTC0's mask on the frame source. Env knobs:
  `OT_FENCE_TRACE=1` (the per-frame trace above, any mode),
  `OT_RT_WAITLOG=1` (every ColdFire wait over 5 ms and every skew timeout
  with both cores' state), `OT_RT_POLLHIST=1` (where the fast-forward
  fired, per core, at exit), `OT_RT_FENCE=0`, `OT_RT_DSR2FF=0`.

### Measured (13 Sep 2026, the M5, macOS 26.5; LTO builds unless said; logs under `out/_agents/rt-fence-build/`)

**The O17 baseline with the new instrumentation** (this binary with O17's
knobs: lead 2 samples, no fence, posts every 32, per-word host paths,
`P:0x4b` executed, DO loops unbounded — `fin-o17knobs-4s`), 4 s of PLAY in
16 × `run 250`, the deltas over the play: **771 emulated ms per wall s**;
the ColdFire's waits **1.71 s of the 5.19 s wall**: idle-skip catch-up
1.133 s (22,926 skips), pulls 0.214 s (49,812; 0.004 s of it waiting for a
word), pushes 0.271 s, posts 0.079 s (1.44 M), kicks 0.014 s, lag 0.001 s;
core 0 busy 2.78 s, core 1 2.07 s. (The frozen O17 binary itself: 664;
its pulls 1.370 s per 49,828 = 27.5 µs each, its posts 5.65 M.)

**The steps**, `--dsp-rt` flat out, each on the LTO-off build unless said
(`rtdrive.py`, 4 s of PLAY):

| step | emulated ms per wall s | what moved |
|---|---|---|
| O17 knobs, LTO off | 597 | — |
| the fence + the frame lead (and the frame-clock gating) | 663 | skip waits 1.24 → 0.25 s; pushes 1.60 s (!) |
| + lock-free rings | 832 | pushes 1.60 → 0.30 s, pulls 0.56 → 0.44 s, core 0 busy 3.44 → 2.80 s |
| + burst DMA | 929 | pulls 0.44 → 0.08 s, waiting for a word 0.110 → 0.006 s |
| the same, LTO | 976 → **1086 / 1109** | (`bench.py`) |
| + the poll lead on every poll (the stall fix, first cut) | 970–995 | the DSR2 poll idled at the bound |
| + the poll lead on the host wait only, `P:0x4b` fast-forwarded | 889–990 | core 1 sat in the skew wait through the pulls |
| + the skew wait yields to the host, DO loops sliced | **1018–1044** (hunts), **1042 / 1058** (`bench.py`) | — |

**Final, flat out** (`bench.py`, four runs on the last two builds of the
tree — the second differs only in `rtstatus`'s published fields and the
`edmastatus` reply): **1058, 1042, 1030 and 1015 emulated ms per wall s**
(0.118–0.123 s wall per 16th at 120 BPM); the lockstep `--dsp` 208 (O17:
197), no `--dsp` 1357. Boot to `ready`: **6.8–7.1 s** with
`--dsp-rt` (14.8 s lockstep, 5.8 s without the cores). Eight-second PLAY
cycles with STOP/PLAY in between (`stall_hunt.py`, 3 × 8 cycles): 981–1044
per cycle.

**The wait breakdown after** (`fin-rt-4s`, the deltas over 4 s of PLAY,
3.82 s wall = 1048): the ColdFire's waits **0.263 s**: pulls 0.089 s
(49,836; 0.006 s waiting for a word, 12,260 waits), pushes 0.152 s
(74,754), kicks 0.014 s (112,131), posts 0.007 s (111,615), idle-skip
catch-up **0.000 s** (1 skip waited), lag 0.001 s. The other 3.55 s is the
ColdFire's own emulation of 388.8 M instructions (110 M per wall s). Core 0
busy 1.26 s, fenced 0.77 s (12,451 of 12,459 frames reached the fence
before the exchange ended), idle 2.46 s; core 1 busy 1.31 s. Per frame:
0.285 ms of ColdFire emulation + 0.021 ms of waits = 0.306 ms against the
0.363 ms the unit has. **The pull wait before/after**: 27.5 µs per pull on
the O17 binary → 1.8 µs (0.12 µs of it waiting for the DSP).

**The fence is what keeps the protocol in order.** The same binary with
`OT_RT_FENCE=0` and the frame lead: 1059 ms per wall s, and **454 bank
words inside read-back pulls in 4 s** (`edgesinpull`; 0 with the fence).

**The stall that the poll lead removed** (three captures, `hunt-2/4/13`):
the bank words 32 samples apart, the exchange with two ~30-sample gaps at
pushes (drain gates held), the next edge 48 samples late, then core 0 at
`P:0x4b` or `P:0x97` for good — DMA2 finished, the ESAI dead. **The stall
that the yielding skew wait removed** (`hunt-bg-3`, the 1024-event ring):
core 0 spinning in `rtSkewWait` for core 1 did not drain the 64-word push,
its gated completion came 8.4 samples late (after the EMAC phase that
normally follows it within 0.04 samples), and the handler's ISR chain
never issued the last push: `outstanding=0`, source 1 still masked, the
ColdFire idle at main's spin (one capture in 8 hunts, 336 s of PLAY, with
the poll lead alone). After both fixes: **0 stalls in 3 hunts of 8 cycles
(192 s of PLAY with STOP/PLAY cycles)**, the 3-minute panel PLAY below,
its three 10-second probes, and the 20 s under TSan.

**The gate: 28 PASS, 0 FAIL, twice** (`tools/emu/ot_emu/oracle/oracle.sh
out/emu/ot_emu.ref-73c2815 <cand> --build-dir <lto>`, strict, no
tolerance; reports `out/_oracle/reports/20260913-030632-rt-fence-final.txt`
and `…-033122-rt-fence-final2.txt` for the final source (sha
`32b162a40ade…`), 37–38 s wall, ctest 7/7): boot logs, serial, goldens, `run3_core0.wav`, the
UART stream, peeks, run stamps and `interdsp.pcm` byte-identical. The
lockstep jobs got faster from the rings alone: `interdsp` boot 23.8 →
15.8 s and its 4.49 s of `run` 28.2 → 20.7 s, `render` 30.8 → 21.3 s.
⚠️ The x86 Homebrew `bash` (`/usr/local/bin/bash`, under Rosetta) ran the
script for 13 minutes without printing a line; `/bin/bash` ran it in 37 s
— the O15d Rosetta accident in another costume.

**A/B against the lockstep take** (`rtdrive.py` with and without `--rt` on
this binary, `abcorr.py`; `fin-ab-lockstep`, `fin-ab-rt`): 199,358 frames
both; onset 82 vs 80 (**−2 samples**); the music itself sits 126 samples
later in the rt take (the best lag); RMS over the overlap **−4.39 vs
−5.73 dBFS (1.34 dB)**, both peaking at full scale; envelope correlation
0.939 over the whole overlap in 50 ms windows, 0.31 in 10 ms windows over
the first 2 s. Where the level goes: the lockstep take has 20 % of its
samples at full scale in every 0.5 s window (the fixture clips, the
sample at level 64), the rt take 3–17 % — the same loops with lower peaks,
not gaps: no 10 ms window with signal is under half the lockstep level, and
0.45 % of the 16-sample frames are under 0.35x (O17's own take: 0.54 %,
−5.12 dBFS, a 0.74 dB difference). 🟡 Not located: the DSP's output
limiter runs on its own history and the cores' interleave differs, and the
A/B cannot tell that from a frame of the mix landing a frame off. It is a
miss on the contract's 1 dB; the audio is the same music at the same
time.

**Thread sanitizer** (`-fsanitize=thread -O1 -DNDEBUG`, Debug, LTO off;
`TSAN_OPTIONS=symbolize=0 log_path=…`, addresses symbolized with `atos -l
0x100000000`; `tsan_drive.py`: boot, `frame on`, `audio start`, PLAY, 80 ×
`run 250` with `audio read` and three `rtstatus`, STOP, `quit`): the first
run (`tsan-run/`) booted to `ready` in 257 s, played its 20 s (55,295 edges,
none inside a pull) and reported **two races, both in the new `rtstatus`
peeks** — the ColdFire's thread reading DSR2 through
`Peripherals56362::read` against `DmaChannel::dualModeIncrement` on core
0's thread, and reading the instruction counter against `DSP::idleStep` —
then aborted at exit as macOS TSan does with reports pending (rc −6).
Fixed: the worker publishes those registers with its MIPS
(`RtCore::hsr/hpcr/tgt/tcr/dcr2/dsr2/dco2/ctr`) and `rtstatus` reads the
atomics. The second run on the fixed binary (`tsan-run2/`): `ready` in
258 s, 20 s of PLAY in 740 s of wall (55,292 edges, `edgesinpull` 0,
`faulted` 00, `dropped` 0, 884,732 audio frames captured), `quit`, **rc 0,
no `tsan.log` written and no ThreadSanitizer line on stderr**.

**Shutdown** (`shutdown_verify.py`, during a paced PLAY with audio on):
`quit` 22 ms, EOF 22 ms, SIGTERM 23 ms; no process left with the card in
its arguments.

**The panel, paced, 3 minutes** (`panel_verify.py 8582`, `panel_server.py
--port 8582 --sound on`, this binary as `--port-bin`, the OTLIVE fixture;
`panel-rt-8582.log`): `ready` after 7.1 s with `sound_rt` true; idle
`/status rt` median 1.000 (0.996–1.008); **PLAY 180 s**: 178,860 emulated
ms in 181.36 s wall = **986 per wall s** (per-second 913–1104, median
984), `/status rt` n=180 **median 0.981 (0.905–1.080)** — under the
target's 1.00 ± 0.02, with the test's own load on the same machine
(`/leds` polled 29,638 times, the headphones-monitor mirror fetching
`/audio/pcm`, a status poll per second; the server's own pump on top);
the pacer re-anchored 10 times and ended with `lag` 0. The same child
over a 10 s PLAY after the MIXER / double-tap / encoder items: **1000
emulated ms per wall s, `rt` median 0.999 (0.995–1.003)**. Audio: end
613,750 → 8,501,474 frames = **44,100 per emulated second** (target
44,100), captured 8,501,474, **dropped 0**; the take
`out/_panel_takes_8582/take-002.wav`, 7,896,152 frames = 179.05 s,
decodes. `rtstatus` after the PLAY: edges 418,514 applied 418,514,
**edgesinpull 0, faulted 00, dropped 0, pullshort 0**, `waitto` 0.
**The LED chase in wall time** (`/leds` at ~165 polls a second, every
LED-state change stamped; `panel-rt-8582.leds.tsv`): 1,633 changes in
181 s, the trig-row running light's 16-step sweep recurring every
**1,941 / 1,944 / 2,027 ms (medians of the three sweep patterns, 69–75
sweeps each, 1,852–2,125 ms)** = 121–127 ms of wall per 16th against the
fixture's 125 ms (120 BPM; the sequencer's own step period in emulated
time is unchanged at 125.1 ms). MIXER opens and closes the mixer page,
the T1 double tap opens the slot list, the LEVEL encoder redraws, the
card re-insert reboots to `ready` in 7.6 s with `--dsp-rt` and
`sound_rt` true.

### What it does not do

- **The A/B's level.** 1.34 dB quieter than the lockstep take in RMS on
  the clipping fixture (the contract asked for 1 dB; O17's take was 0.74
  dB). Same onset (−2 samples), same loops at the same time, no gaps; the
  DSP's output limiter and the cores' interleave are the suspects, not
  located. A non-clipping fixture would separate "quieter" from "less
  clipped".
- **Paced under the panel with a test harness polling it**, `rt` sits at
  0.98 (median over 3 minutes), not 1.00 ± 0.02; the same child without
  the harness holds 0.999. Flat out the margin over real time is 4–6 %
  with LTO (a PGO build, `pgo.sh`, was not measured here), so any other
  load on the machine shows up in `rt`.
- **The stall proofs are statistical**: 0 in 576 s of hunting plus the
  3-minute panel PLAY after the two fixes, against three and one
  captures before them. The captures are in `hunt-2/4/13` and
  `hunt-bg-3`; `stall_hunt.py` (8-second PLAY/STOP cycles, stopping at
  the first frozen frame count with `rtstatus`, `cfstatus` and
  `edmastatus`) is the instrument to run again.
- The fence, the poll lead and the volatile blocks know payload A
  (`P:0x73`, `P:0x97`, `P:0x4b`); a payload that moves them gets O17's
  behaviour (the lead then only as safe as the fixed lead was).
- `rtstatus`'s counters are the workers' published atomics, read without a
  rendezvous: a consistent-enough snapshot for a diagnostic, not a
  rendezvous (as O17's were).
- The idle-skip catch-up, the lag bound and the fence cost the ColdFire
  nothing measurable while playing; what remains is its own emulation
  (0.285 ms of the 0.306 ms a frame takes). The next lever is the
  ColdFire (PGO: O15d measured +13–17 % on the `--dsp` rate), not the
  cores.
- The batch keeps the lockstep interpreter; `--dsp-rt` is `--interactive`
  only, cue and core 1 are not captured, the DSP-side instruments do not
  observe the workers — all as O17.

## Milestone O17c — `--dsp-rt` renders the lockstep bytes: the DSP's clock at every wait, the exact boot, the ISR's drain times ✅ (13 Sep 2026, branch `panel-ui`)

O17b left the real-time mode "the same music, not the same samples": on
the clean fixture (`out/_agents/audio/otlive2.img`, the O14k reference
project, T1 playing `third-0.wav` at 0.7032) the driver
`out/_agents/jit-spike/rtdrive.py` + `out/_agents/audioq/fit.py` fit the
lockstep `--dsp` capture to the sample at **gain 0.7032, residual −33.0 dB**
and the `--dsp-rt` capture at **gain 0.577, −10.7 dB** (a second run −11.8;
`OT_RT_LEAD=2` −7.4, `OT_RT_POLLLEAD=0` −15.1, `OT_RT_DSR2FF=0` −20.5,
`OT_RT_BULK=0` −8.1, `OT_RT_DOITER=0` −9.5; every run different) — the
owner hears crackling on clean kicks and dropouts. This milestone finds
six mechanisms with instruments, fixes them in `tools/emu/ot_emu` alone
(the vendored patch is untouched), and ends with the rt capture
**bit-identical to the lockstep capture: 0 mismatches of 199,358 samples,
L and R, in three consecutive runs (−33.0 dB, gain 0.7032 each)**. Logs,
captures and the scripts under `out/_agents/audiofix/`.

### The instruments (all kept; the scripts under `out/_agents/audiofix/`)

- **The per-block diff** (`perframe.py`, `hits.py`, `slips.py`, `corr.py`):
  the rt capture aligned to the lockstep capture, the error per 16-sample
  block in dB, the wrong samples by position, the stale test (a wrong
  sample equal to the lockstep sample 32 earlier = the ring word from the
  previous revolution), a per-block shift search. It said: one stale
  sample at the block's first position in a third of the blocks, whole
  stale blocks now and then, and long stretches in each hit's tail where
  every sample is wrong by −10 dB with a per-block gain 0.5–1.0.
- **The frame trace** (`OT_DSP_FRAMETRACE=1`, any mode; `ftr.py`): one
  stderr line at core 0's marker PCs — the bank word `P:0x73`, the take seen
  `P:0x99`, core 1's reply `P:0xa5`, the output stage `P:0x1cb`/`0x205`
  (made volatile P addresses under the trace), the return to the DSR2 poll
  `P:0x4b` — and core 1's `0x57/0x59/0x8d/0x8f`, with the DSP's own clock,
  the ColdFire's due count and DSR2. Lockstep: the take at +0.79 samples
  after the bank word (the lazy chunk's grain), the output stage at +1.26,
  DSR2 = 0x79 there — **the ring write has ~0.5 samples of slack before
  DMA2 enters the half it writes**. rt: the take at +0.37 median, p99 1.8,
  max 3.0; the output stage past +2.0 in 255 of 11,400 frames.
- **The exchange timeline** (`OT_FENCE_TRACE=1`; `exch.py`, `pushlat.py`):
  per frame, the ColdFire's ack, commands, pulls, pushes and acks in its
  own clock. Lockstep: the whole exchange 3.36 samples, every push's
  completion a constant of its shape (`pushlat.py` over 12,360 frames:
  core 0's 336-word push 0.340, core 1's 0.165, the 256-word forward 0.126,
  the 64-word ones 0.032, the 32-word one 0.017; ≤ 10 distinct values each,
  within 0.005). rt: 2.85 samples, every push done 0.015 after its kick,
  with a wall-dependent tail up to 2 samples.
- **The block dump under rt** (`--block-dump`, `blockdiff*.py`): every
  host-port block of every frame against the lockstep dump. It separated
  "the DSP was given different data" from "the DSP computed differently",
  and found the ColdFire's own blocks differing (below). The dump had
  stalled the rt protocol (the mover's `peekWord`/`blockNote` peeks into
  the core's registers from the ColdFire's thread); they are skipped under
  `--dsp-rt` now, the dump's words are the ColdFire's own RAM.
- **The ESAI-vs-ring check** (`rtstatus esaimism=`): in the sink, the eight
  words the ESAI put out against the ring words the −9 rule says DMA2 took
  them from. 0 mismatches until a stall — the DMA2/ESAI/sink path is
  faithful; what differed was the ring's content.
- **Determinism**: two rt runs were not bit-identical to each other (66k
  mismatches), so a JIT arithmetic divergence (the spike's CCR U bit) was
  ruled out; every mechanism below is timing.

### What was wrong, in the order found (`dsp.cpp` THE WAITS / THE RENDEZVOUS AT THE TAKE / THE COMMAND RENDEZVOUS / THE EXACT BOOT / THE GATE WAITS FOR THE DRAIN; `rtos.cpp` THE DRAIN TIMES; `periph.h` `setHostDrainTime`)

1. **The DSP's clock at the take.** Under lockstep core 0 leaves its HTDE
   wait (`P:0x97`) at the ColdFire's clock of the take. Under rt the poll
   lead (2 samples) let the worker's clock run to E+2 while the ColdFire
   caught up its 13-sample lead, so the take was seen at E+0…2.2 of the
   DSP's own clock, and the ring write that follows (`P:0x25b`, r1 = the
   other half) landed after DMA2 had entered that half: the block's first
   ring words came out stale (the previous revolution's samples: the
   crackle), whole blocks when the wait was longer (the dropouts). Fix:
   `OT_RT_POLLLEAD` defaults to 0 (the wait's fast-forward never passes the
   ColdFire's clock); the bank take and the end of a read-back pull post
   the exact count (`m_hostEventAt`); at the wait's exit (`P:0x97 → 0x99`,
   a volatile address) the worker idle-steps its clock up to that count
   through its peripheral events.
2. **The read-back refill race.** After the take the ColdFire's `0x89`
   refills HOTX with the read-back within 45 of its instructions (~0.5 µs
   of wall); the worker's service and poll take microseconds, so HTDE was
   clear again before the poll ran and core 0 stayed at `P:0x97` through
   the whole pull (0.7 samples: `waitcu0` ≈ one per frame of ~1,500
   instructions) — on the chip and under lockstep it leaves at the take.
   Fix: THE RENDEZVOUS AT THE TAKE — `rxTake` holds (its clock frozen,
   ~1 µs, `take=` in `rtstatus`) until the worker has left the wait
   (`m_takeSeen`).
3. **The mailbox waits.** Core 0's wait for core 1 to take its word
   (`P:0xa3`) and core 1's for core 0's two words (`P:0x57`, `0x8d`) were
   fast-forwarded to the work lead; with the other core idle at its own
   bound the wait left 3–24 samples late (the frame's work, ring write and
   all: a whole stale block, a skipped frame, DMA2 dry — the O17b stall,
   reproduced once in 4 s). Fix: a mailbox wait's fast-forward is bounded
   by the other core's published clock plus the skew, the mailbox hooks
   record the sending/taking core's clock (`Mailbox::sentAt/takenAt`) and
   the wait's exit catches up to it; a wait whose condition already holds
   runs its poll instead of idling (❌ the first cut deadlocked both cores
   idle at each other's bound with the word already there: a 2 s wait
   timeout and a faulted core).
4. **The boot's phase.** The DSP's due count is booked per ColdFire
   instruction from the first one, the RTOS's sample clock starts at the
   handoff, so the DSP's frame clock sits `boot instructions / 3990`
   samples ahead of the RTOS clock — 2877.39 under lockstep, **3213–3329
   per rt run**, because the loader's 53,627 host-port polls (TXDE/RXDF for
   every uploaded word) spun a wall-dependent number of times. The
   sequencer's bookkeeping against the frame grid moved with it: the
   fixture's second voice (core 1's track, a 64-sample position that walks
   16 a frame) started 7–8 samples off the reference, and the two voices
   comb-filtered to −10 dB from ~30 ms into each hit. Fix: THE EXACT BOOT
   (`OT_RT_BOOTEXACT=1`, default) — until the frame clock is on the
   workers run with no lead and every host-port read is a rendezvous at
   the exact count (`bootreads=53627`, the offset **2877.418, identical
   run to run**; boot to `ready` 8.0–8.9 s LTO-off, was 7).
5. **The ISR's drain times.** The frame handler's pushes are kicked
   through SSRT (unpaced) and complete at the drain gate: the lockstep
   interpreter's DMA0 drains a word per service, a constant per block
   shape (above); the JIT worker drains a block in one service, so the
   completion came 0.015 samples after the kick — the ISR chain 0.5
   samples shorter, and its length following the wall (350–430 of 74,000
   completions per run later than that, up to a sample; every divergence
   from the reference began at one, `blockdiff*.py`: the first differing
   block was the ColdFire's own record for core 1, rendered inside that
   chain, its 8-sample position bucket flipped). Fix: THE DRAIN TIMES —
   under rt `Edma::start` books an SSRT-kicked host-port burst at the kick
   plus the lockstep drain time of its shape (`installHostPortMover`: the
   six measured shapes, two instructions a word for any other,
   `OT_RT_DRAINPACE=0` to switch off); THE GATE WAITS FOR THE DRAIN —
   `hostRingEmpty` holds (clock frozen, `gatedrain=` in `rtstatus`, ~400
   holds of ~10 µs per 4 s) instead of letting the ColdFire step past the
   booked time; and the rt gate-stepping rule (32 instructions) applies only
   to a completion already past due, so a booked one lands on its
   instruction. Measured after: 0.340 / 0.166 / 0.126 / 0.032 / 0.032 /
   0.017 with max = median.
6. **The command poll.** The handler polls CVR's HC until the DSP takes
   the command — at its next instruction under lockstep, at its next block
   (wall) under rt, a wall-dependent number of iterations. Fix: THE COMMAND
   RENDEZVOUS — a CVR read with a command pending holds until the worker
   has taken it (`hcwait=` in `rtstatus`, ~0.3 µs each).

### Measured (13 Sep 2026, the M5, macOS 26.5; `out/_agents/audiofix/`)

| build / run | gain | residual (fit.py) | vs the lockstep capture |
|---|---|---|---|
| lockstep `--dsp` (`ls1`, `ls2`) | 0.7032 | −33.0 dB | — (byte-identical to the O14k reference and to each other) |
| `--dsp-rt` HEAD (`rt2`…`rt7`) | 0.54–0.65 | −7.2 … −14.0 dB | 17–64 % of the samples wrong |
| + the take's clock (fix1) | 0.59 / 0.70 | −11.5 / −32.8 dB | one run stalled at 3.3 s |
| + the mailbox waits, the take rendezvous (fix3) | 0.42–0.60 | −5.2 … −13.3 dB | the DSP's timeline lockstep's; the ColdFire's blocks differ from frame 3 |
| + the exact boot (fix4) | 0.54–0.70 | −10.1 … −32.8 dB | one run in three right; the rest a coin flip per trig |
| + the drain times, the command rendezvous (fix6) | 0.60–0.70 | −11.7 / −20.6 / −32.7 dB | the held gates at the divergences |
| + the gate waits for the drain (fix7, three consecutive runs) | **0.7032** | **−33.0 / −33.0 / −33.0 dB** | **0 mismatches of 199,358 samples, L and R** |

Flat out (`bench.py --dsp --dsp-rt`, the LTO build): **1042 and 1020 emulated ms per wall s** (two runs, 4 s of PLAY in 16 × `run 250`; O17b measured 1015–1058 on its LTO build).
The same on the LTO binary with no instrument on (`final-lto-1..3`): **−33.0 dB,
gain 0.7032, three of three; inside the 4 s of PLAY 0 mismatching frames
against the lockstep capture in all three** (`rtdrive.py` itself timed the
play at 1164–1218 emulated ms per wall s); after the driver's STOP, two of
the three differ from lockstep in 1,447 frames (4.06–4.24 s, max |diff|
1292, the two identical to each other) — a binary post-STOP outcome, not
measured further. Boot to `ready`: 6.8–7.4 s LTO, 8.0–8.9 s LTO off (was
7 / 7.9). Three PLAY/STOP cycles of 6 s (`stall_hunt.py`, `hunt-lto/`):
1016–1027 per cycle, no stall. The strict oracle on the old modes: **28 PASS, 0 FAIL** (ctest 7/7, 37 s; `out/_oracle/reports/20260913-071250.txt`). The vendored tree and
`tools/patches/dsp56300.patch` are unchanged (`git -C vendor/dsp56300
diff` equals the patch byte for byte).

### What it does not do

- The drain-time table knows payload A's six block shapes (and the
  interpreter's base rate for any other); a payload with other shapes gets
  the two-instructions-a-word rate — deterministic, not lockstep's.
- The sink's de-rotation (`rot = (DSR2 − 9) & 7`) still takes ring words
  0..rot−1 of a de-rotated frame from the next ring sample; with the exact
  boot the rt phase is lockstep's (rot ≤ 2, main L/R inside one sample)
  and the captures agree, but a boot with rot ≥ 3 would put main R one
  sample behind L in the capture (seen on the random-phase runs before
  the exact boot: R = lockstep's R delayed by one sample, L exact). The
  batch capture has the same rule and the oracle pins its bytes, so it is
  left as it is.
- The waits are bounded (2 ms) for a dead core and counted (`take=`,
  `hcwait=`, `gatedrain=`, `waitto`); the diagnostics (`OT_DSP_FRAMETRACE`,
  `esaimism=`, `waitcu0/1=`) stay in.

## Milestone O18 — the panel child's memory: the peripheral-write record ended at the seed, the dispatch record bounded ✅ (13 Sep 2026, branch `panel-ui`)

The port's process grew while the sequencer played and never gave the
memory back: **11-13 MB per emulated second of PLAY**, in bursts, with the
DSP cores off as well as under `--dsp-rt` (CONTEXT.md's "+34 MB per 2 s
slice"; the O15a verifier's +48 MB for 6 s, +175 MB for 13 s). The panel
runs one child for hours, so an hour of play was 40 GB of address space.
The growth was measured, not guessed: `MallocStackLogging=1` on a 20 s
play and `malloc_history -allBySize` while the child was still playing,
then a memory instrument inside the emulator (`OT_MEMSTAT=1`, below) for
the rates of every record; the driver and every log are under
`out/_agents/memfix/` (`memdrive.py`: boot on `otlive.img`, `frame on`,
PLAY, `run 250` + `tx` per slice the way the server pumps, `ps -o rss`
every few seconds, `vmmap`/`malloc_history` before STOP).

### What grew, measured

| record | rate during play | before | after |
|---|---|---|---|
| `Machine::m_periphWrites` — one 12-byte record per peripheral write the models take (the boot's seed for `Rtos::install`) | 0.4-0.8 M writes per emulated s (the vector's 2^24-entry block was live 20.5 s into play: 201,342,976 bytes, plus its 206 MB predecessor freed but still resident — the doubling that made the growth bursty); **the whole leak in both modes** | unbounded, never read after the seed | ended at the seed: `Machine::endPeripheralWriteLog()` after `Rtos::install` has replayed it (and captured `m_seeded`); the vector is freed |
| `Rtos::m_dispatches` — one 24-byte record per scheduler `rte` | ~720 per emulated s (24,643 after the load, 164,531 at 200 s of play: 17 KB/s, 62 MB/h) | unbounded | `Rtos::DispatchLog`: the true count, the first 65,536 whole, a ring of the last 4,096, the TCB set for `ran()` (1.7 MB at most) |
| `AtaCard::m_log` — one entry per ATA command | 10,339 after the load, +12 over 200 s of play (the fixture's flex slots live in RAM) | unbounded | capped at 262,144 entries, the rest counted (`logDropped()`) |
| `Rtos::m_acks` | at its existing 100,000 cap 19 s into play (3.2 MB) | capped (O7) | unchanged |
| the panel UART's `tx` (`Uart::m_tx`) | 187 B/s during play (45,707 bytes at 200 s; 0.7 MB/h) | unbounded | unchanged — `main.cpp`'s `tx` cursor indexes it absolutely and the batch's `serial_a` golden is the whole stream (see below) |
| everything else (`m_periphLog` 4,096, `m_periphTrace` / `m_hostPortLog` / `m_memWrites` / the DSP's `m_log`, `m_trace`, maps, watch hits — all opt-in and capped; the audio ring 60 s fixed; the eDMA due list; `m_created` 10) | flat | bounded or opt-in | unchanged |

The `--dsp-rt` mode adds nothing of its own: the JIT's block chains were
21 MB in four allocations at 20 s and did not grow; the HDI08 rings held
one word; the ESAI capture is off outside the render.

### What changed (`machine.h/.cpp`, `rtos.h/.cpp`, `card.h/.cpp`, `dsp.h/.cpp`; no CLI change, `main.cpp` untouched)

- `Machine::peripheralWrite` records into `m_periphWrites` only while
  `m_periphWriteLogOn`; `Rtos::install` calls `endPeripheralWriteLog()`
  right after `m_seeded = peripheralWrites().size()` — the record's one
  reader is the seed replay above that line (`grep` finds no other), so
  every printed count is taken before it is dropped.
- `Rtos::DispatchLog` replaces `std::vector<Dispatch>`: `size()` is the
  true count (the batch's "N dispatches", the load's delta), `operator[]`
  answers the first 65,536 and the last 4,096 (`writeGoldenJson` reads the
  first 200, the batch's "dispatch tail" the last 14; a batch run never
  passes 65,536 — boot 51, load ~24,400, a 3,000-frame render ~10,000
  more), `ran()` is kept incrementally. An index that fell out answers a
  zero record; no reader asks for one. `kept()` says how many are held.
- `AtaCard::note()` keeps the first `g_logCap` = 262,144 entries and
  counts the rest (`logDropped()`); `stampLastCommand` stamps only an
  unstamped last entry, so a dropped command never re-stamps a kept one.
- **The instrument**: `OT_MEMSTAT=1` prints one `memstat <ms>: ...` line on
  stderr at the end of every `Rtos::run()` and at destruction with the
  size of every record above — `Rtos::memStat()`, `Machine::memStat()`,
  `Coprocessor::memStat()` (a default, `DspPair` overrides it with its log,
  trace, maps, stream, watch hits, capture and HDI08 rings). stderr only,
  opt-in: stdout is diffed byte for byte by the oracles.

### Measured (13 Sep 2026, the M5, macOS 26.5; Release, `-DOT_LTO=OFF`, `out/_agents/memfix/build` = before, `build-fix` = after; logs under `out/_agents/memfix/`)

300 emulated seconds of PLAY on the OTLIVE fixture, `run 250` + `tx` per
slice, RSS at PLAY and at its end (the peak is the last play sample; the
drop at STOP in the "before" rows is the compressor, not a release):

| mode | before: PLAY → 300 s | after: PLAY → 300 s | speed (emulated ms per wall s) |
|---|---|---|---|
| no `--dsp` | 422 → **3,856 MB** (+3,434 MB, 11.4 MB per emulated s; 2,323 MB after STOP) | 418.4 → **418.7 MB** (+0.3 MB; 362.7 after STOP) | 1,009 before, 1,008 after |
| `--dsp-rt` | 1,056 → **4,890 MB** (+3,834 MB, 12.8 MB per emulated s; 2,589 after STOP) | 1,052.0 → **1,052.8 MB** (+0.8 MB, 0.6 of it in the first slice; flat after STOP) | 839 before, 792 after (the after run shared the machine with the oracle's ten jobs for its first minute — not a speed measurement) |

The remaining growth is the UART stream (187 B/s), the dispatch ring's
one-off 1.7 MB and the acks' 3.2 MB cap — a 5-minute play adds under 1 MB,
an hour under 4 MB. `malloc_history` before the fix (20 s of play,
`base-mh-nodsp/malloc_history.txt`): the one live block from
`Machine::peripheralWrite` at 201,342,976 bytes, then only construction
(the card region 133 MB + 67 MB, the image 67 MB, the SDRAM 33 MB × 2,
the acks 3,162,112, the dispatches 1,064,960); the same picture under
`--dsp-rt` with the DSP's memory and audio buffers on top
(`base-mh-rt/malloc_history.txt`).

**The gate: 28 PASS, 0 FAIL** (`out/_oracle/reports/20260913-080435-memfix2.txt`
against `out/emu/ot_emu.ref-73c2815`: boot logs, `serial_a` 5,731 / 9,257
bytes, goldens 12,757 / 26,367 bytes, `run3_core0.wav` identical, the
`--interactive` UART 18,297 / 18,309 bytes step by step, 109 peeks, 47 run
stamps at |dsample| = 0, `interdsp.pcm` 497,788 bytes identical, ctest
7/7; the first pass, `20260913-080310-memfix.txt`, was 27/1 only because
the candidate tree had not built the test executables yet). **The rt
audio is unchanged**: `rtdrive.py --rt --seconds 4` on `otlive2.img` →
`fit.py`: onset 82, lag 81, gain 0.7032, **residual −33.0 dB**
(`out/_agents/memfix/fit-rt/`).

### What it does not do

- The panel UART's transmit record still keeps every byte the firmware
  ever sent (187 B/s during play; 0.7 MB an hour). Trimming it needs
  `main.cpp`'s `tx` cursor to become an offset into a ring (three lines
  there, plus a `txBase()` on the `Uart`); the batch's `--serial-out` and
  the goldens want the whole stream, so the trim would be the interactive
  loop's alone. Left for the `main.cpp` owner.
- The acks stop at 100,000 as before (O7); the "ack tail" of an
  interactive session's end report is the tail of the first 100,000, as
  it was.
- Past 65,536 dispatches or 262,144 ATA commands the interactive
  session's end report still prints the true dispatch count, but its ATA
  command count and per-type histogram are the kept entries' (the batch
  runs never get there; nothing compares an interactive end report).
- The `--dsp` lockstep mode shares every record here; it was checked for
  60 s of play (0.1x real time), not five minutes.

## Milestone O19 — the card persists: `--card-rw` write-back, `card flush` / `card status` on the pipe; the panel boots a card file as it is ✅ (13 Sep 2026, branch `panel-ui`)

The owner's words: *"if I save the project, but then quit the program, not
only are all the samples I added to the flash gone, but my project is not
saved, and I cannot continue my previous work."* Two causes, both in the
code: `panel_server.py` rebuilt `out/_panel_card_<port>.img` from the
fixture at every start (and wiped the per-port sample pool), and the port's
`AtaCard` held the whole image in `m_img` — WRITE SECTORS landed in that
vector and were never written back to the file, so the firmware's own SAVE
PROJECT (which does write: 22,752 sectors on the OTLIVE fixture) went to
RAM. The design that fixes both is the hardware's: **the CF card is a real,
persistent file.**

### What changed in the port (`card.h`, `card.cpp`, `main.cpp`)

- `AtaCard::setWriteBack(path)` opens the image file `O_RDWR` and keeps the
  descriptor; `commitSector` — after the copy into `m_img`, as before —
  `pwrite()`s the same 512 bytes at the same offset, synchronously, before
  the WRITE completes (`writtenThrough()` counts the sectors, `writeErrors()`
  the short writes, never retried). Nothing is buffered on this side: after
  a commit the bytes are the kernel's, so a `kill -9` of the child loses
  nothing that was written. `flush()` is an `fsync`; the destructor fsyncs
  and closes. Reads are from memory as they always were (the file is never
  re-read); the class is copy-deleted.
- `--card-rw` (needs `--card`, else `card rw : --card-rw needs --card`,
  exit 2): after the card is attached, `setWriteBack(cardImage)` and one
  boot-log line `card rw    : write-back on -- WRITE SECTORS go through to
  <file> (O19)`. Without the flag the class and every line of output are
  the O18 ones — the gate below.
- Two interactive commands (`serveInteractive` now takes the card):
  `card status` → `card ok rw=0|1 path=<file> written=<sectors the firmware
  wrote> through=<sectors in the file> errors=<n>`; `card flush` → `card ok
  rw=0|1 through=<n> errors=<n>` (fsync; `card fsync-failed ...` if it
  fails); `err no card` without a card, `err usage: card status | card
  flush` otherwise. `quit` flushes before its `ok`. EOF and a fault leave
  the file as it is (already written through); SIGTERM/SIGKILL the same.

### What changed in the panel (`panel_server.py`, `panel.html`, the app)

- `--card <file.img>`: the image is booted **as it is** (no rebuild, no pool
  wipe), the child spawned with `--card-rw` when the binary knows the flag
  (`/status card_rw`; an older binary boots it read-only and says so in
  `backend_note`). A missing file is created once from `--project` + its
  sibling AUDIO + `--audio` — `build_card` as before — and a sidecar
  `<file.img>.json` keeps the set/project names, the removals marked for
  the next re-insert, the pool path; later starts read it (the firmware
  does not reload its last project by itself in emulation: a bare boot of
  the saved card, no `--mount`, leaves `0x100f8480`/`0x100f8378` zero with
  the card ready, `out/_agents/persist/bare-boot` run). The names the
  firmware holds are read at every flush and the sidecar follows a
  PROJECT > CHANGE on the unit. Without `--card` the per-port path is
  byte-for-byte what it was.
- `card flush` after every action batch and every 3 s idle (`_card_flush`);
  `_stop_child` = `card flush`, `quit`, kill — used by every reboot path
  (respawn, re-insert, sound switch) so a stopped child never leaves the
  file behind its memory. A SIGTERM handler in `main()` ends
  `serve_forever` through the `finally` (flush, quit, sidecar) — Python's
  default action killed the interpreter outright before, the app's README
  said so.
- The pool is `<file.img>.pool/`, never wiped. **RE-INSERT** on a
  persistent card (`_commit_persistent`): flush + stop the child, `hdiutil
  attach -imagekey diskimage-class=CRawDiskImage -nobrowse` (mounts the
  builder's image as FDisk + DOS_FAT_16 at `/Volumes/<label>`;
  `-mountpoint` answers "no mountable file systems" for it), copy the pool
  into `<SET>/AUDIO` (VFAT long names by macOS), delete the marked files,
  `card_clean` (`.fseventsd`, `.Spotlight-V100`, `.Trashes`, `._*`,
  `.DS_Store`, `.metadata_never_index` — the volume is asked not to index or
  log first), `hdiutil detach`, re-list, boot. Never a mount while the
  child runs.
- `Fat16Image`: a read-only walk of the image (MBR partition, BPB, the FAT,
  8.3 + LFN entries, cluster chains) — `/samples` lists `<SET>/AUDIO` from
  the file directly (`on_card: true`, the format from each file's first
  16 KB through `sample_header`, which takes bytes now), `/card` the sets
  and projects on it, and the sidecar-less card is booted into the first
  set/project found.
- `/card/eject` (flush, stop, mount browsable, `open` in Finder unless
  `?open=0`; every action answers `ok: false` "the card is ejected", the
  loop idles, nothing respawns) and `/card/insert` (clean, detach — `-force`
  on a second try — re-list, boot); `/status` gains `card`, `card_mode`,
  `card_rw`, `card_ejected`, `card_mount`, `project`. A server started on
  a card the previous one left mounted detaches it first
  (`card_mounted_at` from `hdiutil info -plist`).
- `panel.html`: the ejected state only — the slot shows the card out, the
  drawer says where the volume is and has INSERT CARD.
- The app: File > New Card from Project… (`out/cards/<Set>-<Project>.img`,
  remembered in `cardPath`, Open Existing / Replace when it exists), Open
  Card…, Show Card in Finder, Eject Card / Insert Card (one item, the
  title from `/status`), Open Project (scratch card)… keeps the old
  behaviour and forgets the card; `VIRTUAL_PANEL_CARD=<img>` (one launch),
  `VIRTUAL_PANEL_PORT_BIN=<bin>` (`--port-bin`). Quit → SIGTERM → the
  server's handler.

### Measured (13 Sep 2026, the M5, macOS 26.5; `out/_agents/persist/`: `verify.py`, `verify.log`, `verify.json`, `shots-verify/`, `oracle.out`, `fit-rt.out`)

One run of `verify.py` on port 8597 (its own `cards/VERIFY.img`, the
patched LTO build `build/ot_emu`, `--dsp-rt` on):

| step | measured |
|---|---|
| A new card from the OTLIVE fixture | ready in **7.1 s**; `/status` `card_mode persistent, card_rw true, project OTLIVE/PROJECT`; the child's argv carries `--card-rw`; 37 files listed from the image's AUDIO, none pending; sidecar `{set, project, image_bytes 67108864}` |
| B REC, TRIG 3 | REC LED on; the trig-3 LED (row 0 bit 4) 0 → 1, row 0 = `0x11` (bit 0 the fixture's trig 1) |
| C FUNC+MIXER, RIGHT, DOWN, YES, YES | the PROJECT menu popup 5/0/0xf6/0x40 (KEYMAP.md's), the `SAVE PROJECT ... CONTINUE?` box (shots C1–C4); `card flush` `through=0` → **`through=20030 errors=0`** (10.3 MB) 3.3 s after the second YES (a first burst at once, the bank files ~2 s later; the by-hand run wrote 22,752 — the save's size depends on what changed), the image's md5 changed |
| D SIGTERM | the server exits rc 0 in **78 ms**, no child left on the card, md5 unchanged |
| E `--card` alone | ready in 7 s, `project` from the sidecar; the trig-3 LED off until REC, **on in GRID RECORDING** — the trig is on the card |
| F a generated WAV | `/samples/add` → pending; `/samples/commit` → re-insert + boot **9.1 s**; listed `on_card: true`, pending `[]`, the pool empty, 38 files in the image's AUDIO; the firmware's file browser (T1 ×2, RIGHT, UP to the top of the list — `verify_browser.py`, shots J2/J3) lists it first: `AAA persist 440.wav 0.08`, footer `44.1k 16b 2Ch`, then the WAV copied in through the eject below |
| G SIGTERM + restart | still listed on the card (38) |
| H eject / insert | ejected in 0.5 s, mounted at `/Volumes/OCTABAM`, root = `[OTLIVE]`, `/key` → `ok: false` "the card is ejected", 0 children; a second WAV copied into `OTLIVE/AUDIO` by hand; `/card/insert` → booted in **8.1 s**, mount point gone, both files `on_card`, 39 in AUDIO, the image's root still `[OTLIVE]` (no `.fseventsd`/`.Spotlight-V100`/`.Trashes`) |
| the app (port 8598, `VIRTUAL_PANEL_CARD`, `VIRTUAL_PANEL_PORT_BIN`) | spawned `--port-bin ... --card ...`, `card item: Eject Card, enabled` at ready (+8 s); `/card/eject` → `Insert Card, enabled`, `EJECTED at /Volumes/OCTABAM`; `/card/insert` → back; SIGTERM → the app gone in 0.13 s, `server pid ... stopped (status 0)`, no child, nothing mounted; `build.sh` 0 warnings, `codesign -vv` valid |

**The gate: 28 PASS, 0 FAIL** on the patched build against
`out/emu/ot_emu.ref-73c2815` (`out/_oracle/reports/20260913-083439-persist.txt`:
boot logs, serial, goldens, the `--interactive` UART step by step, 109
peeks, 47 run stamps at |dsample| = 0, `interdsp.pcm` identical, ctest 7/7),
and **the rt audio fit −33.0 dB** (`rtdrive.py --rt --seconds 4` on
`otlive2.img` → `fit.py`: onset 82, lag 81, gain 0.7032).

### What it does not do

- Route A has no write-back (`--card` needs the port backend; the server
  exits saying so instead of falling back).
- `out/emu/ot_emu` is rebuilt by the orchestrator: until then the app's
  default spawn boots a persistent card **read-only** (`/status card_rw`
  false, the reason in `backend_note`); `VIRTUAL_PANEL_PORT_BIN` points a
  launch at `out/_agents/persist/build/ot_emu`.
- The "last set / last project" record the unit keeps is not on the card in
  emulation; the sidecar stands in for it. A card copied without its
  `.json` boots into the first set/project found on it.
- An eject leaves the volume mounted if the server dies; the next start
  detaches it (`card_mounted_at`). Finder's `._*` and `.DS_Store` are removed
  at insert; files a user leaves open in Finder make the detach fall back to
  `-force`.
- The write-through is per sector (~22,750 `pwrite`s for a project save,
  inside the emulation's own `run`); it was not measured against the pacer
  beyond "the count stood still 3.3 s after YES". A `pwrite` that fails is
  counted (`errors=`), not retried.

## Milestone O20 — the effects that use delay memory: an effects rig in both DSP modes, the Echo Freeze Delay's eDMA copies, and what the chorus/comb/delay still lack 🟡 (13 Sep 2026, branch `panel-ui`)

The owner's report: "the reverbs and the delay, and the chorus, and I'm
sure others like comb filter, don't sound good at all; the chorus sounds
like a very small glitchy loop of the audio repeating" — heard through the
panel with sound on (`--dsp-rt`), where plain sample playback is proven
bit-identical to the lockstep interpreter (O17c, `fit.py` −33.0 dB). This
milestone builds a rig that puts each effect on the playing track through
the firmware's own UI, saves the card, and renders the same card under both
DSP modes; measures every effect against the clean render of the same
emulator; and separates the two hypotheses with instruments. **Findings:
the DELAY is silent in BOTH modes (H1: two ColdFire-side causes, one fixed
here, one located); the CHORUS and COMB add nothing to the dry in BOTH modes
(H1: the module runs, writes its delay lines with audio, and multiplies its
input by a per-instance word the emulated DSP drives to zero — located to
the word, not fixed); the DARK REVERB works (a real, decaying wet in both
modes); and `--dsp-rt` is no longer bit-identical to lockstep once an
effect or the delay is on (H2: whole 16-sample blocks re-rendered
differently about once a second, run to run — small, documented, not
fixed).** Nothing in the rt scheduler was changed. Everything under
`out/_agents/fx/` (scripts, cards, takes, renders, logs, `analyze_*.txt`).

### The rig (`out/_agents/fx/rig.py`, `rig2.py`, `panctl.py`, `render.py`, `analyze.py`, `wet.py`, `anatomy.py`)

- **Setup through the panel**, on an own server (`--port 8593`, own
  binary `--port-bin out/_agents/fx/build/ot_emu`, LTO off), a fresh
  `--card out/_agents/fx/cards/<name>.img` made from the clean tree2 project
  (`out/_agents/audio/tree2/OTLIVE/PROJECT`, `third-0.wav` on the current
  track). The playing track is **T5** (the UI's current track at boot,
  `0x100b14cc` = 4, a FLEX machine); T1 is a STATIC machine. **The EFFECT
  SETUP chooser opens with FUNC + [EFFECT 1/2]** (`/key` row 0x25 bit 5 held
  around row 0x24 bit 5/6; the popup slot `0x460d175c` reads `0x46c7d34c`);
  a second bare press of the page key did NOT open it through `/key` on the
  paced child (the first rig run assigned nothing and YES on the main
  screen opened ARM ALL — `chorus/01..17_*.png`). The list is NONE, FILTER,
  EQ, DJ EQ, PHASER, FLANGER, CHORUS, SPATIALIZER, COMB, COMPRESSOR, LOFI
  (+ DELAY, PLATE, SPRING, DARK on FX2), the current effect highlighted, so
  CHORUS = 5 × DOWN from FILTER, COMB = 2 more, DARK = 3 × DOWN from DELAY;
  YES assigns (the right pane shows the effect's SETUP boxes) and leaves the
  window open; NO closes it; the page key once shows page 1 with the new
  names. Page-1 knobs A–F are the six slots (`/knob?row=0x30..0x35`,
  deltas applied exactly); the value is read back from the Part
  (`0x400e21e0 + 0x8ee9a + 4·24 + 12/18`, ids at `+0x8ed80/+0x8ed88 + 4`),
  which is how every state below was confirmed. PLAY 6 s (the pacer held
  `rt` 0.93 on this LTO-off build for every effect, reverb included), STOP,
  the take, then SAVE PROJECT (FUNC+MIXER, RIGHT, DOWN, YES, YES; 22,752 →
  47,355 sectors flushed) and a copy of the card per effect.
- **The cards** (`out/_agents/fx/cards/`): `clean` (untouched);
  `chorus` (FX1 0x12: DEL 64 DEP 94 SPD 13 FB 0 WID 127 MIX 40); `chorusmax`
  (DEL 127 DEP 127 SPD 13 FB 64 WID 127 MIX 64); `comb` (FX1 0x13: PTCH 26
  TUNE 64 LP 127 FB 127 MIX 90); `delay` (FX1 NONE; FX2 0x08 DELAY: TIME 47
  FB 70 VOL 127 BASE 0 WDTH 127 SEND 100 — at 120 BPM TIME 47 = 47/256 of a
  whole note = 367 ms = 16,193 samples); `dark` (FX2 0x16: TIME 84 SHVG 0
  SHVF 127 HP 0 LP 127 MIX 100, the delay's SEND back to 0).
- **The renders**: `render.py --card X --out D [--rt] --seconds 6` boots
  `ot_emu --interactive --mount --set OTLIVE --project PROJECT --dsp[-rt]`
  on the saved card (rtdrive.py's shape), PLAYs 6 s in `run 250` slices and
  writes `main.wav` (core 0 main L/R, 16-bit). The panel's own take is
  bit-identical to `render.py --rt` on the same card before STOP (chorus:
  0 mismatches of 261,132 frames), so the take is the rt render.
- **The measures**: `analyze.py` (onset, RMS, autocorrelation lags,
  spectrum, 100 ms envelope, lockstep-vs-rt alignment: max |diff|,
  mismatching samples, correlation, per-second dB); `wet.py` (the WET =
  effect render − clean render of the SAME emulator and mode, onset-aligned:
  its level, envelope, autocorrelation, cross-correlation with the dry over
  0–1000 ms, spectrum); `anatomy.py` (the wrong samples of rt against
  lockstep by position mod 16, magnitude, the stale tests, run lengths).
  A dry-fit against `third-0.wav` cannot separate a chorus from the dry on
  this tonal sample (a 6,075 Hz tone; a copy delayed by a few ms is
  absorbed into the fit gain) — the wet against the clean render is the
  measure that works.

### Measured (13 Sep 2026, the M5, macOS 26.5; `out/_agents/fx/rig2/analyze_*.txt`, `wet_ls.txt`, `anatomy_ls_vs_rt.txt`)

| card | wet vs dry (lockstep) | what the wet is | lockstep vs rt | rt vs rt (2 runs) |
|---|---|---|---|---|
| clean | — | — | **bit-identical** (0 of 287,500) | bit-identical (O17c) |
| chorus (MIX 40) | | | first hit identical, then −42 dB (0.37 % of samples, max 927) | |
| chorusmax | **−61.5 dBFS** vs dry −23.6 (−38 dB: nothing) | the same residual as the no-FX1 delay card | −36 dB, 3.6 % of samples, max 9,225; 11 whole 16-sample blocks | 103 wrong samples: 7 whole blocks (2.03, 3.14, 3.19, 3.21, 4.09 s) |
| comb | **−60.6 dBFS** (nothing; a feedback comb whose line reads zeros outputs exactly the dry) | as above | −37 dB, 3.6 %, max 5,901 | |
| delay (FX1 NONE) | **−63.2 dBFS**: no energy between the hits (−83…−240 dBFS with SEND 100 / FB 70): **no repeats** | the second voice / LSB noise | −34 dB but only 0.03 %: **6 whole blocks** (1.06, 2.17, 3.18, 4.06, 4.16, 5.17 s), not stale copies, a different mix of the block | the same 6 blocks in one run, none in the other |
| dark | **−24.1 dBFS**: a tail −47 → −56 dBFS over 0.75 s after each hit, decaying | a reverb | −28 dB, 84 % of samples (a modulated reverb's history: the O12 class) | |

The panel takes measure the same (`analyze_takes.txt`): the delay take
has silence between hits, the dark take a tail, the chorus/comb takes the
dry-fit residual of the clean fixture (−18.5 dB, the DSP's fade-in).

### H1 for the delay, cause 1 ✅ fixed: memory-to-memory eDMA channels moved no data (`rtos.cpp` `Rtos::copyMemToMem`, `installHostPortMover`; `rtos.h`; `main.cpp`)

The Echo Freeze Delay is not on the DSP (EXTERNAL.md §1): the ColdFire's
frame routine at `0x400031a0` points the eDMA at per-track rings in SDRAM
at `0x4f502c10` (8 × 1,411,328 bytes, cleared at boot). Read off the image
(`out/_agents/fx/delay_routine.lst`, the TCD init at `0x40002fd4`):
channels 2/3 fetch this frame's and last frame's delay positions from the
ring (SADDR = the 16-byte-aligned read position, DADDR = the block minus
the misalignment: `0x80003ad8` / block+160−8, ATTR `0x0402` = 16-byte
source bursts and 32-bit destination, SOFF 16, DOFF 4, NBYTES 144, CITER
1, no modulo; CSR `0x321` = START + link to ch 3), the routine busy-waits
ch 3's DONE at `0x400035a8`; channels 4/5 write the mixed block
(`*(0x800000e8)` = `0x80003ae0`) into the ring at the write position (ATTR
`0x0404`, NBYTES 128; a mirror at ring + 1,411,200 when the write lands at
the base; CSR `0x521`), waited at `0x40003780`. Route A's model moves no
data on any channel and the port's mover (O8) only ever carried the
host-port blocks (`installHostPortMover` returns for a DADDR outside
`0x20000000-0x20000fff`) — so the taps were never fetched and the ring
never written: the delay mixed zeros, in both modes.

The fix: at the kick, a channel with neither end in the host-port window
is copied per its TCD (`copyMemToMem`: NBYTES per minor loop as SSIZE
reads at SOFF and DSIZE writes at DOFF, SMOD/DMOD honoured, CITER minor
loops; the TCD's words left as the firmware wrote them — it reprograms the
addresses every frame and never reads them back). Counted:
`memToMemBlocks/Bytes`, reported only under `--block-log` or
`OT_M2M_REPORT=1` (the strict oracle compares the batch log line for line).
Measured: **12,800 blocks / 1,740,800 bytes per 400 frames** (32 per
frame: the routine runs for all eight tracks), the reference render
byte-identical (below), the clean card's lockstep render bit-identical to
the unfixed binary's, the rt fit gate unchanged.

### H1 for the delay, cause 2 🟡 located, not fixed: the mix loop's gains for T5 are zero

With the copies in, the delay is still silent: T5's ring is zero across
the whole span of a hit (`fix/delay/peek3.out`: seven 64-byte peeks from
ring + 0x94000 to + 0xac000, all zero), while T5's delay state record
(`0x8000609c`: read `0x4fb0ba88`, write offset `0xc6f80`) says the
geometry is right — **read = write − 16,545 frames = 375 ms** for TIME 47
(the 367 ms expected plus a frame or two). The pipe's `watchmem` on the
block the ring is written from (`0x80003ae0`, `watchblk.py`, 700 ms of
play): the eDMA fetch lands there (my copies: 277 non-zero bytes of
320,256), and the mix loop's two output stores (`movel %d1,%a0@+` at
`0x4000376c` / `0x40003772` = dry×SEND + taps×FB per sample) wrote
**15,440 zeros and nothing else**. Those gains come from the per-track
coefficient records at `0x80006180` (68 bytes a track, `moveml
%a4@(20),%d1-%d2/%a1-%a4`, ramped per sample): T1–T3's records carry
gain words (`0x00800000`, `0x007fffff`, `0x08ff00ff`), **T5's
(`0x80006290`) holds `8, 0x10, 0x10, 0x10, 0x800049d8, 0x80000690, 0,
0xc, 0…` and T6–T8's are all zero** (`fix/delay/peek4.out`). So the
firmware's parameter path that fills the delay's coefficient record for
T5 (SEND 100 / FB 70 / VOL 127 in the Part, confirmed) never ran under
the emulator, or the record walker reads a different table for tracks
5–8 — the next step is to read `0x400031e4–0x400033c0` (the walker,
`0x80005f8c`/`0x5f98`/`0x5fa0`/`0x5fa2` + 68·t) and `0x40003284` (the
routine's own staged-time write, EXTERNAL.md) with a `watchmem` on
`0x80006290`, and to check whether the record's writer is on a UI/menu
task path (the O12 "slew/scene stage" family) that a saved-and-reloaded
project should have run at the load. Not the eDMA, not the ring, not the
DSP.

### H1 for the chorus and the comb 🟡 located to the word, not fixed

The chorus (payload A, init `P:0xeb7`, process `P:0xed7`) is dispatched
every frame for T5 (`--dsp-pcwatch 0:ed7`: r7 = `0x6100` = position 0's
FX1 block, x0 = 0x12, r6 cycling the three parameter copies 0x263/0x2e3/
0x363, r0 = `x:$20e` = 0 = the 16-sample stereo block at X:0x0000), its
parameter block is right (`X:0x263..`: 7f 7f 0d 40 7f 40 = DEL DEP SPD FB
WID MIX), its instance base is `Y:0x1000` (`X:0x611{3,4}` = 0x1000 /
0x1600), and it **writes its two 1,532-word delay lines with the block's
audio** (`--dsp-writes`: non-zero writes in Y:0x1000–0x15ff and
0x1600–0x1bff at the hits' duty cycle; the line-write loop `P:0xfe4–0xfed`
forms `Y:base+idx` with the AGU's "N a multiple of 2^k is linear" rule,
which interpreter and JIT both apply). What it does not do is hear its
input: at `P:0xf43–0xf4b` the block is scaled by `y0 = x:(r7+$1d)` into
the wet scratch (`Y:0xc0`/`0x110`), and **`x:0x611d` is 0** — the scratch
gets zeros (`--dsp-watch 0:Y:c5`: pc 0xf49 ← 000000 every frame), the tap
sums are 0/−1 LSB (pc 0xfa1), and the shared mixer `func_7b0` mixes a zero
wet at MIX. The word is one of the module's own per-tap state words
(`x:(r7+$1a)..` — the loops at `P:0xf24` (stride 4) and `P:0xf62` (stride
3) smooth them toward payload tables at `X:0x8d79..0x8d8c` and
`X:0x6c00/0x6d00`, all present and non-zero in the emulated memory): at
frame 60 it reads `0x039b9a` and is growing, its siblings `0x6121/0x6125`
are `0x493782/0x771123` at frame 400, and by frame 400 it is back to 0
(`rig2/chorusmax/batch_state.log`, `batch_tbl.log`). The interpreter and
the JIT agree to −36 dB on this card, so it is a DSP-model defect common to
both (candidates, all in this module's path and none used by Sam's
modules that `dsp_host` renders bit-exactly: the nested `do` loops over
`(r3)+n3` with two strides, `tge`/`ifmi`/`ifgt` conditional transfers,
`lsr #$10,a` on the accumulator, `mpyi`/`macri`, `l:(r4)+` long moves,
`bset #$14,sr` scaling in `func_773`), not a memory-size or window defect
(the pair allocates 2 M words per space; the FX1 slot is internal Y). The
COMB (`P:0x1eca/0x1edc`) shows the identical wet (−60.6 dBFS) and was not
traced separately. Falsifier for the next session: a `--dsp-watch
0:X:611d` (the last 16 writers with PC and value) over the first 100
frames, then the writing instruction's semantics against the DSP56300FM.

### H2: `--dsp-rt` diverges from lockstep once the frame carries an effect (not fixed)

The clean card stays bit-identical (0 of 287,500 samples, ls vs rt, fixed
and unfixed binaries), but with an effect or the delay's SEND on, rt runs
differ from lockstep and from each other by **whole 16-sample blocks
re-rendered with a different mix** (`anatomy_ls_vs_rt.txt`: the delay
card 6 blocks in 6.5 s, all runs of exactly 16, not stale copies
(`cand==ref[i±16/32]` 0), |diff| up to 9,194; the chorus card 7–11 such
blocks plus the wet's own LSB drift; a second rt run of the delay card
had none of the six and the chorus card a different seven). That is the
O17c fix-5 class — the ColdFire's own record for a voice rendered inside
the frame ISR with a flipped 8-sample position bucket — reappearing when
the ISR chain is longer (the delay's EMAC work, the effect's heavier DSP
frame). `OT_FENCE_TRACE` / `OT_DSP_FRAMETRACE` and `blockdiff*.py` are the
instruments; not pursued here because it is −30 dB and inaudible next to
the H1 findings, and the fix belongs with the drain-time table (`rtos.cpp`
THE DRAIN TIMES).

### The gates

- Strict oracle, the fixed binary against `out/emu/ot_emu.ref-73c2815`
  (`out/_agents/fx/build-fix`, LTO off): **28 PASS, 0 FAIL**
  (`out/_oracle/reports/20260913-111137-o20-m2m-2.txt`). The first run
  failed only `render.log` on the new report line (`20260913-110823-o20-m2m`);
  the reference `render.wav` (8 ch, 330,677 frames) and `interdsp.pcm` are
  byte-identical with the copies on — the reference fixture's rings hold
  silence, so moving them changes nothing it renders.
- `fit.py` on the clean fixture in rt (`rtdrive.py --rt --extra "--card
  out/_agents/audio/otlive2.img"`, the fixed binary): **gain 0.7032,
  −33.0 dB** (`out/_agents/fx/fit-rt2/`); the tree2 clean card −33.0 dB in
  both modes.
- ctest 7/7 (inside the oracle).

### What it does not do

- The delay still has no repeats (cause 2 above); the chorus and comb
  still add nothing (their word); the dark reverb was not compared to a
  hardware reference (none exists here). Plate and spring were not run.
- The reverb on a shared-window FX2 slot (T7/T8, `Y:0x30000/0x34000`) was
  not exercised: the fixture has no audio on those tracks.
- The panel's monitor was not the cause on this machine (`rt` 0.93 with
  every effect, no starvation-specific symptom), but the owner's PGO
  binary and machine were not measured under the reverb.
- The rig's one-shot chooser navigation assumes the current effect
  (FILTER / DELAY on a fresh part); `rig2.py` tracks it across steps.

## Milestone O21 — the Echo Freeze Delay repeats: the eDMA copy read the TCD's ATTR/SOFF words swapped; the chorus and comb were never on a track that sounds; the JIT renders the DSP effects differently 🟡 (13 Sep 2026, branch `panel-ui`)

O20 left two "open causes": (A) the delay's coefficient record for T5
"holds no gain words", and (B) the chorus scales its input by a word the
DSP "drives to zero". Both were measurement errors, and under them sat one
real ColdFire-side defect (fixed here), one real EMAC corner (fixed, one
shift), and one real DSP-side divergence that is the owner's symptom and
is NOT fixed (the JIT). Everything under `out/_agents/fx2/` (scripts,
cards, renders, `O21_measurements.txt`, `wet_final.txt`,
`ls_vs_rt_final.txt`, the watch logs under `delay/` and `chorus/`).

### ❌ What O20 measured, retracted

- **"T5's coefficient record `0x80006180 + 4·68` holds `8, 0x10, …`"**:
  `0x80006180` is the frame routine's POINTER CELL — set to `0x80005f60`
  at `0x400033be` and advanced 68 bytes per track at `0x400036fe` — so the
  records are at `0x80005f60 + 68·t`, and O20 read past the eighth one.
  T5's (`0x80006070`), peeked on the delay card during play: `7e020000
  7e020000 b972a200 4e200000` = dry level `(0x7f00)²·2`, VOL `(0x7f00)²·2`,
  FB `sats(−66053·0x4600)`, SEND `(0x6400)²·2` — exactly the CFPRM's
  fractional squares and the saturating subtract (`macw %d7l,%d7l,%acc0`
  under MACSR `0xa0`, `mulsl`/`subl`/`satsl`; `out/_agents/fx2/watchrec-delay-1.out`,
  `hitsmix-delay-hit.out`). The writer was right all along; the four
  instruction variants it uses are now cases in `test_emac.cpp` (41 checks).
- **"T5 plays third-0.wav"**: the tree2 fixture's tracks are T1–T4 STATIC on
  sample slots 1–4 and T5–T8 FLEX on flex slots 1–4 (`first, second, third,
  fourth-0.wav`; third = fourth = fifth by md5), every track trigging at
  steps 1 and 9. In emulation **the slot-1/2 tracks (T1, T2, T5, T6) never
  sound**: DSP core 0 position 0 — the position whose FX record `X:0x25d`
  carries the rig's effect ids for T5 — receives nothing from the voice
  stage `P:0x41a` in any frame of a hit (`dsp watch 0:X:0` / `dsp pcwatch
  0:f49`: x0 = 0 through 1.00–1.08 s), while positions 2/3 (T7/T8, and
  T3/T4 on core 1) carry third/fourth-0.wav; the clean fit against
  third-0.wav alone is −33 dB, so first-0.wav is not in the main out. So
  every O20 effect card put its effect on a silent track, and the "silent
  wet" of the chorus/comb and the "no repeats" of the delay followed. The
  cause of that silence is not determined (a fixture/part state, or an
  emulation defect of the slot-1/2 path): 🟡 the falsifier is first-0.wav
  on T7's slot.
- **The O20 "comb" card is a chorus card**: its Part bytes hold T5 FX1 =
  `0x12` with the chorusmax page (the rig's second DOWN did not take).
- **The chorus word `X:0x611d`** is tap 0's gain (`r7+0x1a+3`), smoothed at
  `P:0xf24–0xf30` toward `X:(0x8d80+a)` = `0x400000` (a = 2, 1/√4) with
  y1 = `0x20c5`/2²³ = 0.001 per frame: `0x00d3b4` at 30 frames, `0x150545`
  at 400 (= 0.5·(1−e^−0.4)), `0x3ffc19` at 6000 — the DSP56300 semantics
  exactly; never 0 (`out/_agents/fx2/chorus/watch_611d_f*.log`).
- **The DSP has no DELAY module**: id 8's init entry `X:0x215+8` = `P:0x7c8`
  (`rts`), its process entry `X:0x235+8` = `P:0x7c9` (a copy in place). The
  delay is the ColdFire's alone: its dry is the per-position read-back
  (DSP DMA1 from `X:0x2600/0x4600 + 64·position`, 64 words = 16 stereo
  samples as hi/lo halves, → `0x80003190 + 0x400·ping + 128·slot`; core 1 =
  slots 0–3, core 0 = slots 4–7), its result returns as the forward
  (`0x6400` → `X:0x2400/0x4400`), one frame later.

### The rig, corrected (`out/_agents/fx2/`)

Cards are built directly from the project — no panel session: a copy of
`out/_agents/audio/tree2`, `tools/hw/ot_project.py set_fx(pdir, slot,
track, id, page, page2)` on **T7** (a track that sounds) with the O20
settings read back from the O20 cards' Part bytes, `emu_card.build_image`
→ `cards/{clean7,chorus7,comb7,delay7,dark7}.img` (comb7 = `0x13` with page
`26 64 127 127 0 90`, the PTCH TUNE LP FB — MIX order of DSP.md). Renders
with O20's `render.py`, wet with `wet.py` (a numpy venv at
`out/_agents/fx2/venv`). New instruments: **`dsp watch | dsp pcwatch | dsp
peek <core> <X|Y|P> <0xaddr> <len>`** on the pipe (`main.cpp`; the batch's
`--dsp-watch/--dsp-pcwatch` records and a DSP memory peek, readable in the
interactive run — the batch's `--sequencer` start leaves the playing
tracks silent on these cards, so the traces could only be taken here;
lockstep only), `dspq.py` (PLAY, run, issue pipe commands at chosen
times), `hitsmix.py` (the delay mix loop's registers per slot, 0x40003738 /
0x4000375e / 0x4000376c), `watchrec.py`. ⚠️ A `watchmem` on SDRAM must be
given as `0x8xxxxxxx`: the watch compares the cached alias, and a range
given as `0x4fxxxxxx` reports 0 writes while the ring fills (measured).

### Cause A ✅ fixed: `copyMemToMem` read the TCD's ATTR at +6 and SOFF at +4 (`rtos.cpp`; the eDMA log's labels in `main.cpp`; the comment in `periph.h`)

On the MCF5445x the 32-bit word at TCD+4 is `ATTR` (high half) and `SOFF`
(low half): TCDn_ATTR 0x04, TCDn_SOFF 0x06 (RM ch. 18), and the firmware's
values say so — the delay routine writes `0x0402`/`0x0404` there (SSIZE 4 =
16-byte bursts; DSIZE 2 = 32-bit or 4 = 16 bytes) and `0x0010` at +6 (the
16-byte stride). O20's copy had them swapped: SSIZE = DSIZE = 1 byte, DMOD
= 2 (a 4-byte destination modulo), and a source stride of 1026/1028. So
the 144-byte tap fetch folded 144 single bytes, from every 1026th address,
into the staging block's first longword (`watchmem 0x800039a0`: 1872
one-byte writes per 8 ms, all 0, pc `0x4000337c`), and the 128-byte ring
write folded into four bytes at the write pointer — the ring stayed zero
(`peek` of T7's ring `0x4fd16210 + 0x2000…0x5c000` at 1.07 s: all 0) while
the mix loop's ring-input stores were non-zero (inside the hit: T7 1650 of
1761 stores, gains `a2 4e200000 a3 b972a200 a4 7e020000`). Nothing else
reads those two words (the host-port mover uses NBYTES/CITER/SADDR/DADDR),
which is how the swap hid.

**Measured after the fix, delay7 (TIME 47 FB 70 VOL 127 SEND 100 on T7),
lockstep:** wet −38.6 dBFS with the echo at **lag 16,529 samples = 374.8 ms**
(wet×dry cross-correlation r = 0.297) and the second repeat at 33,058 (r =
0.164); the wet envelope −32…−39 dB at 350–600 ms and −38…−44 at 700–950
ms. Before: −44.5 dBFS, top lag 16 (the one-frame ColdFire latency), no
energy between the hits. 16,529 is the firmware's own staged time
(state record +0x38 = `0x81221 >> 5`); O20's 16,193 was 47/256 of a whole
note at 120 BPM, not the firmware's formula (`0x40003284–0x400032ea`,
unverified against hardware).

### Cause A′ ✅ fixed: fractional −1.0 × −1.0 (`v4e.cpp`)

The new gate caught it: the fractional product was formed as `(product <<
1) >> 24` in an int64, and the one product that reaches 2⁶² (0x80000000
squared, or the 0x8000 halves) overflowed into −2³⁹, where the 48-bit EMAC
holds +1.0 as +2³⁹ in its extension bits (CFPRM, fractional mode: only the
read-out saturates — `0x7fffffff` with OMC set, wrapped `0x80000000` with
OMC clear). Now `product >> 23`, one shift; no other input changes; both
read-outs are gate cases.

### Measured (13 Sep 2026, the M5, macOS 26.5; the LTO binary `out/_agents/fx2/build-lto/ot_emu`; `wet_final.txt`, `ls_vs_rt_final.txt`)

| card (effect on T7) | lockstep wet | what the wet is | rt wet | lockstep vs rt |
|---|---|---|---|---|
| clean7 | — | — | — | **bit-identical** |
| chorus7 (DEL 127 DEP 127 SPD 13 FB 64 WID 127 MIX 64) | **−43.6 dBFS** | a detuned copy (wet peak 6063 Hz vs the dry's 6075), no short-loop autocorrelation (top lag r = 0.18) | −49.0 | 27 % of samples, −21 dB; **the rt wet is not detuned** (6075 Hz) |
| comb7 (PTCH 26 TUNE 64 LP 127 FB 127 MIX 90) | **−28.3 dBFS** | a comb ringing at 337 samples = 130.9 Hz (C3 = PTCH 26), decaying over 1 s | −36.4 | 99 %, −5 dB; **the rt comb does not ring** (autocorrelation peaks at 24–39 samples, r = 0.5: the owner's "very small glitchy loop") |
| delay7 | **−38.6 dBFS** | the echo at 16,529 samples and its repeat | −38.6 | **bit-identical** |
| dark7 (TIME 84 … MIX 100) | −24.1 dBFS | a reverb, tail −35 → −44 dB over 1 s | −24.1 | 98 %, −9 dB (the tail is there, the samples differ) |

So **(B) as O20 stated it does not exist in lockstep**: the chorus and the
comb work once they are on a track that sounds. What does exist is a
**JIT-vs-interpreter semantic difference inside the DSP-side effect
modules** — `--dsp-rt` is the panel's mode, the owner listens to it — from
the first sample of a hit, not a scheduling class (the clean card and the
ColdFire-side delay are bit-identical between the modes; O20's H2 "whole
16-sample blocks" were this on the silent-T5 cards). Not fixed here.

### The gates

- Strict oracle, `out/_agents/fx2/build-lto/ot_emu` vs `out/emu/ot_emu.ref-73c2815`:
  **28 PASS, 0 FAIL** (`out/_oracle/reports/20260913-122719-o21-delay-fix.txt`);
  the reference `render.wav` / `interdsp.pcm` byte-identical — the
  reference fixture's rings hold silence (SEND 0 everywhere), and no other
  memory-to-memory channel changes bytes the oracle reads.
- ctest **7/7**, the EMAC gate **41 checks** (the delay-coefficient square
  law in three accumulators including an address-register operand, the
  mix loop's fractional `macl` with an `(An)` load, the `mulsl/subl/satsl`
  chain with and without overflow, and the −1×−1 read-outs).
- `fit.py` on the clean fixture in rt (`rtdrive.py --rt --extra "--card
  out/_agents/audio/otlive2.img"`): **gain 0.7032, −33.0 dB** (`out/_agents/fx2/fit-rt/fit.txt`).

### What it does not do

- **The JIT's effect rendering** (chorus not detuned, comb not ringing,
  reverb samples different under `--dsp-rt`) is diagnosed to the class,
  not to the instruction. The exact next step: a differential run of the
  comb module (`P:0x1eca` init, `P:0x1edc` process, and `func_773`'s
  `bset #$14,sr` … `bclr #$14,sr` window) — the same DSP state under the
  vendored interpreter and under the JIT (`out/_agents/jit-spike/jittest/`),
  the first register or memory write that differs names the instruction;
  the candidates are the ones O20 listed (`do` over `(r3)+n3`, `tge`/`ifmi`/
  `ifgt`, `lsr #$10,a`, `mpyi`/`macri`, `l:(r4)+`, the SR bit-20 window,
  `asr #$a,b,b`), and the fix belongs in `vendor/dsp56300` +
  `tools/patches/dsp56300.patch`.
- Why the slot-1/2 tracks are silent in emulation (T1, T2, T5, T6 with
  first/second-0.wav) is not determined.
- The delay's time formula (16,529 samples for TIME 47 at 120 BPM) is the
  firmware's; no hardware reference exists here to check it against.
- Plate and spring were not run; the O20 cards (effects on T5) were not
  re-rendered — they measure a silent track.

## Milestone O22 — the JIT renders the DSP effects: differential execution names two vendored-JIT defects (MPYI's immediate multiplied unsigned; a bit instruction on an M register left its modulo words stale), fixed in the patch ✅ (13 Sep 2026, branch `panel-ui`)

O21 ended with the owner's symptom diagnosed to a class: under `--dsp-rt`
(the panel's mode) the comb did not ring and the chorus was not detuned
while the lockstep interpreter rendered both, so one or more DSP56300
instructions were executed differently by the vendored JIT than by the
interpreter. This milestone finds them by DIFFERENTIAL EXECUTION — the same
DSP state under both engines, compared after every block, then after
every instruction — fixes the two in `vendor/dsp56300`
(`tools/patches/dsp56300.patch` regenerated), and re-measures the rig.
Everything under `out/_agents/fx3/` (`O22_measurements.txt` is the
index; `harness/` the harness, `snap-*.txt` the snapshots, `diff-*.txt`
the runs, `final*/` the renders, `ls_vs_rt_o22.txt`, `wet_*_o22.txt`).

### The harness (`out/_agents/fx3/harness/difftest.cpp`, on `dsp56k::DSP`)

One lockstep run per card (`out/_agents/fx2/dspq.py` with
`--dsp-pcwatch 0:<process entry>`, at ~1.05 s of PLAY): `dsp pcwatch` gives
the module's entry registers (24 hits — the dispatcher `P:0x4b4–0x50d`
calls each FX process entry TWICE per frame, `r0 = 0 / n7 = x:$20c = 4`
then `r0 = x:$20e = 8 / n7 = x:$20d = 12`, r7 the instance block, r6 the
parameter copy), `dsp peek` the memory (X:0–0xbfff, Y:0–0x7fff, P:0–0x6fff;
the reverb's lines at Y:0x30000–0x3ffff). Two `dsp56k::DSP` instances load
the same memory and entry registers (sr 0, M linear, `jsr` from a return
PC). The JIT instance runs with the rt mode's `JitConfig` exactly
(dynamicPeripheralAddressing, dynamicFastInterrupts, optimizer off,
maxDoIterations 64, linked blocks, the function table sized to all of P)
one `dsp.exec()` — one block, or the linked run of blocks — at a time; the
interpreter instance (host-stepped, `execInterpreter` + `doLoopEnd`) is
stepped to the same instruction count — its OWN step count: the library's
counter charges a host-stepped `do` twice, which made the first runs drift
by one per loop — and every register (a, b, x, y, r/n/m, sr, omr, pc, la,
lc, sp, sc) and the loaded X/Y ranges are compared. The CCR is compared
from `getSR()` and reported as a note only (both engines keep it lazily; a
CCR that matters shows up as data). `--maxinstr 1 --nolink` makes every
instruction its own block, which names the instruction. The module is run
for several frames (the same block each time) so a feedback structure
exercises its loop. `harness/mwtest.cpp` is the micro-test rig (a chosen
instruction sequence under both engines, as the spike's `jittest.cpp`).

### Defect 1 ✅ fixed: MPYI / MPYRI / MACI multiplied by the immediate as an unsigned word (`jitops_alu.cpp`)

The first data difference in the comb (`P:0x1edc`), one-instruction
blocks, block 31: **`P:0x1f01 mpyi #>$9bc5d1,x0,b`** (`0141c8 9bc5d1`):
interpreter `b = 0x000a88fb5c8102`, JIT `b = 0xffefa05d5c8102` — the low
24 bits agree, the difference is exactly `2·x0·2²⁴`: the JIT multiplied by
`+0x9bc5d1` (+0.609) where the immediate is the signed fraction `−0x643a2f`
(−0.391). In the chorus (`P:0xed7`) the same, block 38: **`P:0xeed mpyi
#>$f44800,x0,a`**, interpreter `a = 0xfff4507000f000`, JIT
`0x00f3981e00f000`. The DSP56300 Family Manual (MPYI, "Signed Multiply
With Immediate Operand": `#xxxxxx` is 24-bit immediate long data, a
two's-complement fraction like every ALU operand) sides with the
interpreter, whose `alu_mpy` sign-extends both operands. In the JIT's
`alu_mpy` the ARM64 path did `smull(r64 s1, r32 s1, r32 s2)` with `s2` an
`Immediate24` DspValue materialised from the raw opcode word (positive as a
32-bit value), and the x86-64 path `imm24() * 2` the same. The fix
sign-extends the immediate on both hosts (`signextend<int32_t, 24>`; the
power-of-two shift path only for a positive immediate; the unsigned-`s2`
callers untouched). The comb's coefficient chain `mpyi / max a,b / cmp /
tge` then clamped `b` to its floor 0x1800 — the ring's feedback gone, the
owner's "very small glitchy loop". The payloads carry eight negative
immediates (`mpyi #>$e00000,x1,a` ×6, `#>$f84c00`, `#>$f44800`,
`#>$d00000`, `#>$9bc5d1`, `#>$fcf669`, `maci #>$c04000`, `#>$9c0000`).

### Defect 2 ✅ fixed: a bit instruction on an M register left the JIT's modulo words stale (`jitdspregs.cpp`)

With defect 1 fixed the comb and the chorus were identical over three
frames, but the dark reverb (`P:0x171b`) still differed: block 89,
**`P:0x177c move (r4)-n4`** with `r4 = 0x0302e0, n4 = 0x10, m4 = 0x801f` —
set at `P:0x1776–0x1777` by `move m1,m4 / bset #$f,m4` — interpreter
`r4 = 0x0302f0`, JIT `0x0302c0`. `M = 0x801f` is the multiple wrap-around
modulo (`M = 0x8000 + 2^k − 1`, k = 5; DSP56300FM 4.3.3): the low k bits of
Rn are updated modulo 2^k and the upper bits kept, (0 − 0x10) mod 32 = 0x10
→ 0x0302f0, the interpreter's. The micro-test isolated it: every `bset` /
`bclr` on an M register left the JIT's mask/modulo words wrong (mask 0x20,
modulo garbage) while `move #>$801f,m4` and `move x0,m4` were right —
`bitmod_D` modifies the pooled M register in place and writes it back
through `decode_dddddd_write` → `setM` with THE DESTINATION AS ITS OWN
SOURCE, and `setM`'s "the source is an M register: copy its precomputed
mod/mask" shortcut copied the destination's own registers, acquired
write-only just above and never loaded. The fix skips the shortcut when the
source M register is the destination (the dynamic classification of the
value follows). The reverb's pointer walked one word too far back every
frame.

Both fixes carry unit tests in the vendor's `unittests.cpp` (mpyi/maci with
negative immediates against exact products; the reverb's bset/bclr-on-M
idiom: mask, modulo and the pointer), run by `dsp56kTestRunner` under the
JIT and the interpreter — all pass. The patch: 24 files, every one of the
627 old change lines kept, `git apply --check` on a scratch worktree of
`3c01813f` OK and the patched tree `diff -r` identical to
`vendor/dsp56300/source`. The interpreter path is untouched.

### Measured (13 Sep 2026, the M5; `out/_agents/fx3/build/ot_emu`, LTO, built from the working tree; both modes rendered with it, `--seconds 6.5`; `ls_vs_rt_o22.txt`, `wet_rt_o22.txt`)

| card (effect on T7) | lockstep vs rt | rt wet | lockstep wet |
|---|---|---|---|
| clean7 | **bit-identical** (0 of 309,564) | — | — |
| chorus7 | **bit-identical** (0 of 309,559) | −43.4 dBFS, wet peak **6063 Hz** vs the dry's 6075 (detuned) | −43.4, 6063 Hz |
| comb7 | **bit-identical** (0 of 309,559; a second rt run: one 16-sample run at 5.06 s, −60 dB) | −28.1 dBFS **ringing at 337 samples** (r = 0.954), −23 → −42 dB over 1 s | −28.1, 337, same envelope |
| dark7 | 77–78 % of samples at **−46 dB** (max 1185); was 98 % at −9 dB | −24.0 dBFS, tail −35 → −44 dB | −24.0/−23.9 |

The dark reverb's residue is not the JIT's semantics: two rt runs differ
from EACH OTHER (85 %, −45 dB, first difference at 0.151 s vs 0.239 s) as
much as from lockstep, the harness shows the module identical over three
frames at both granularities, and a semantics difference is deterministic
— it is O20's H2 class (whole 16-sample blocks, run-to-run, the ColdFire's
drain timing) fed into a long-memory effect, 37 dB down from where defect
2 had it (the comb's one block in one of three runs is the same class).
⚠️ O21's renders are not a baseline for this binary (O21's lockstep
clean7 vs this lockstep clean7: 6 % of samples, a different binary/session);
both modes must come from the same binary, which is what the table does.

### The gates

- Strict oracle vs `out/emu/ot_emu.ref-73c2815`: **28 PASS, 0 FAIL**
  (`out/_oracle/reports/20260913-131419-o22-jit-fixes.txt`; the batch modes
  use the interpreter, so byte-identical); ctest **7/7**; the vendor's
  assembler/JIT/interpreter/optimizer test suites pass with the new cases.
- `fit.py` on the clean fixture in rt (`rtdrive.py --rt`, otlive2.img):
  **gain 0.7032, −33.0 dB** (`fit-rt2.out`).
- Bench flat out `--dsp --dsp-rt`, machine idle: this LTO-only build
  **995 / 984 emulated ms per wall s**; O21's LTO binary without the fixes,
  same session, 913–941 — the fixes cost nothing; the PGO flavour built the same way under `out/_agents/fx3/build-pgo` (`pgo.sh --dest/--gen/--prof`, `out/emu` untouched): **1139 / 1146 emulated ms per wall s** (O17b: 1208 on the owner's PGO binary), boot to ready 6.9 s.

### What it does not do

- **MACRI is executed as two no-ops by BOTH engines**: `macri
  #>$9566,x0,a` (`0141c3 009566`, `P:0x779` in `func_773`, reached from the
  CHORUS `P:0xee6`, PHASER `P:0xcdd`, FLANGER `P:0xdb3`) is
  `errNotImplemented` in the interpreter (`op_Macri_xxxx`; the assert
  compiles out in Release) and in the JIT (`*** JIT errNotImplemented:
  opcode=$0141C3`, then the extension word `0x009566` decoded as a second
  unimplemented op). Identical in both, so not a ls-vs-rt divergence and
  not touched here; the manual's MACRI (`D + S × #xxxxxx`, rounded → D)
  would change the lockstep output of those three modules. The earlier
  patch implemented MPYRI the same way; MACRI is its accumulate-and-round
  sibling.
- The H2 scheduling residue on the reverb (and, one block in three runs,
  the comb) remains with the drain-time table (`rtos.cpp`), as O20 left it.
- Plate and spring were not run; core 1's audio and the cue out are not
  captured.

## Milestone O23 — per-track outputs: the eight stems tapped from the DSP's mixdown, over the pipe and onto the output device ✅ (13 Sep 2026, branch `panel-ui`)

The owner's ask: the hardware has only MAIN and CUE, but inside the DSP
each track's audio exists as a block of samples after its effects and
before it is summed into the buses — find those blocks, tap them every
frame, and send them to the output device as extra channels. **Emulator
side only: the firmware and the DSP programs are untouched** (what he
flashes is what he tested). Everything under `out/_agents/mout/`
(`map.py`, `analyze.py`, `server_verify.py`, `bench_audio.py`, the
streams, the logs, `oracle.out`, `gates.out`).

### The buffer map, from the disassembly (`out/dsp/payload_A.asm`) and confirmed by instruments

**The stems exist as data, per track, not accumulated in place.** Payload
A's frame on core 0 (the dispatcher P:0x40-0x25f, the mixdown P:0x238-
0x2d4 across the small modules P:0x260-0x2bf, the rest of P:0x2bf):

| step | P | what |
|---|---|---|
| the bank take | 0x4b-0x71 | waits `DSR2 == 0x8070` → bank A (`r0 = 0x8080`, `r2 = 0x4400`, `r4 = 0x4800`, `r5 = 0x4600`, `r6 = 0x4000`, `r7 = 0x4080`) or `0x80f0` → bank B (`r0 = 0x8000`, `r2 = 0x2400`, …); saved to `X:$203` (r0, the ring half), `X:$204` (r2), `X:$205` (r4), `X:$206` (r5), `X:$207` (r6), `X:$209` (r7). The DMA-in mask at P:0x75/0x77 (`x0 = 0x3fff` for bank A, `0x5fff` for B, patched into P:0x58c/0x59b) makes the host's `0x6400` land in the OTHER bank's `0x2400`/`0x4400`: the forward the ColdFire sends during frame N is consumed at frame N+1 — the "one frame later" of O21 |
| the host exchange | 0x73-0xe6 | the bank word, the HTDE wait, core 1's mailbox, the input ring copy |
| **the hi/lo join** | 0xe8-0xed (`func_56a`, n0 = 0x100) | the forwarded 512 host words at `X:$204` (8 tracks × 16 samples × L/R × hi,lo — the ColdFire's delay pass on the two cores' read-backs: core 1's positions 0-3 = T1-T4 in slots 0-3, core 0's = T5-T8 in slots 4-7, O21) become **256 24-bit words in place**: `extractu` the low byte from the lo word, `mac #$80` the hi word up 8 bits — so after it **track k's block is `X:$204 + 32k`, sample j's L at `+2j`, R at `+2j+1`, 24-bit signed** |
| the level path | 0xf5-0x10a, 0x10b-0x165 | per slot three 16-bit host words from `X:$205` (r4's block) → `X:0..0x1d` (×256), squared into `Y:0..0x13` (the CFPRM square law), scaled by the tables at `X:0x6c00` and the two master squares |
| the gain ramp | 0x203-0x237 | per slot (8 tracks + 2 inputs) a two-segment ramp over the 16 samples from the state at `X:0x3dd + 5k` into **`Y:0x40 + 20j + k` (the cue-bus gain of track k at sample j) and `Y:0x4a + 20j + k` (its MAIN gain)**, one mono gain a track (pan is upstream, in the block itself) |
| **the mixdown** | 0x238-0x2d4 | `m0 = 0xff` (a 256-word modulo buffer at `X:$204`), per sample: `mpy/mac y0,x0` over the eight slots (`x:(r0)+n0` with `n0 = 0x1f` steps 32 words a slot, L then R under the same `y0`) plus the two input pairs (`x:(r2)+`), `asl #2`, `move a/b,x:(r1)+` → ring words 0/1 (the cue bus, gains `Y:0x40..`) then the same over `Y:0x4a..` → **ring words 2/3 = MAIN L/R**, `(r1)+n1` to the next sample's 8-word group. The plain path (P:0x259) and the MASTER TRACK path (P:0x292, bit 10 of `x:(r6+$7e)`: slots 0-6 summed into `X:0x4278..` for track 8 to process, main = slot 7 alone) both end at **P:0x2d5** |
| after it | 0x2d5-0x2eb | `func_55a` × 4: the main pair and the input pairs packed hi/lo into `X:0x4700..` (the recorder's sources, the 128-word ch 6 read-back) |
| the cue mix | 0x30a-0x359 | ring words 4/5 = `Y:0x40+2j` × words 0/1 + `Y:0x41+2j` × words 2/3 — **it overwrites `Y:0x40-0x5f` at P:0x32d**, i.e. sample 0's and part of sample 1's gains, which is why the tap must read them before it |
| then | 0x36a-0x39f, 0x3a1… | the staging copy, the dispatch context, and the voices / effects of the NEXT frame's read-back |

Confirmed on the tree2 clean card (`out/_agents/fx2/cards/clean7.img`,
T3/T4/T7/T8 sounding, `map.py --peeks --frametrace`, lockstep):

- `dsp peek 0 X 0x4400 256` / `0x2400 256` while bank A is current
  (`X:$203 = 0x8080`, `X:$204 = 0x4400`): the 0x4400 block is the joined
  form — 32-word windows rms **25 / 25 / 604,919 / 604,919 / 25 / 25 /
  604,919 / 604,919** for slots 0-7 (24-bit units; T3/T4/T7/T8 carry
  third/fourth-0.wav, T1/T2/T5/T6 ~0) — while 0x2400 holds the NEXT
  frame's forward still in hi/lo form (every window ~2.3-2.6 × 10⁵: the
  stale TXH byte above the 16 payload bits, O8); a peek with bank B
  current shows the mirror (`0x2400` joined: 143 / 143 / 176,787 / …).
  So a per-track block is complete from the join at P:0xed until the
  next DMA-in into the same bank, one frame later.
- `Y:0x4a + 20j + k` at j = 2, 8, 15: **0x16c800 = 0.178 on every slot**
  (level 64: × 0.178 × 4 = 0.712, the 0.7032 fit gain of O14k); at j = 0
  the words are the cue mix's (0x0e5f6b, 0x7f6a9a, …) — the clobber,
  measured.
- `--dsp-pcwatch 0:2d5`: one arrival per frame, **66,546 / 66,574 DSP
  instructions apart** (the frame period), taps = frames in `audio status`.
- `OT_DSP_FRAMETRACE=1`: at P:0x205 (the ramp, ~1,000 instructions before
  the tap) **DSR2 = 0x807d / 0x807a for bank A and 0x80fd / 0x80fa for B**
  (1,748 / 522 / 1,690 / 509 of 4,469 frames) — the mixdown lands about
  half a sample before DMA2 enters the half it wrote; the return to the
  poll (P:0x4b) is at 0x80af / 0x802f, ~6 samples in — the frame's voice
  and effect work runs AFTER the mixdown, for the next frame.

### The tap (`dsp.h` / `dsp.cpp`, THE STEM TAP; nothing outside the sink/tap)

- `StreamMode::Tracks` (`audio start tracks`): **24 words a frame = the
  eight de-rotated ring words of `all` (0/1 cue bus, 2/3 main L/R, 4/5 cue
  L/R, 6/7 unused) followed by T1 L, T1 R, T2 L, … T8 L, T8 R**, 16-bit
  (the 24-bit words >> 8), LE, in the same 60 s ring (127 MB at 24
  words). `audio status` gains ` taps=<n>` in this mode only; every older
  mode's bytes and lines are unchanged.
- `DspPair::stemTap(Core&)` runs on core 0 with the PC at **P:0x2d5** —
  in lockstep a compare in `stepBody` beside the bank-word one, gated by
  an atomic flag set by `audio start tracks`; under `--dsp-rt` P:0x2d5 is
  one more volatile P address (`rtSetup`), so the block after the mixdown
  is always entered from `rtWorker`, where the tap fires once per arrival
  (keyed on the instruction counter), on core 0's own thread — every
  write it reads (the DMA-in, the join, the ramp) is that thread's, so
  there is no race and no lock. It reads `X:$203` (the half: 0x8080 →
  ring words 0x80-0xff, 0x8000 → 0x00-0x7f), `X:$204` (the block), and
  forms each track's own term of the mixdown: `((x × g) << 1) << 2`, the
  24-bit word of the accumulator with the move's limiter, >> 8 — into
  `m_stems[half][16][16]`; a boot-time arrival with other values in
  `X:$203/$204` stages nothing.
- The ESAI sink names, per delivered frame, the ring group of its main
  pair by the −9 rule per slot (`(DSR2 − 9 + ((2 − rot) & 7)) & 0xff) >> 3`,
  a rotated frame's pair placed by ITS ring words), and `streamPush`
  appends the 16 staged words of `m_stems[group >> 4][group & 15]` after
  the eight ESAI words. The half's staging is written ~half a sample
  before DMA2 enters it and next overwritten a frame later, after the
  half has played out — the sink never reads a half being staged.
- Cost: 256 multiplies and 640 word reads per frame at the tap, a 32-byte
  copy per sample at the sink. Measured below: nothing.

### The server, the app, the docs

- `panel_server.py`: with a device on the child's capture is `audio start
  tracks` (`OUTPUT_CAPTURE`; `_capture_start` falls back to `all`, then
  `main`, on a child that lacks the mode, and `output.note` says so); the
  drain de-interleaves main L/R (words 2/3 of 24) for the ring, the takes
  and `/audio/pcm` exactly as before; `AudioOutput` opens up to **24
  channels** and lays the pairs out in `OUTPUT_ORDER[24] = (1, 2, 4..11,
  0, 3)`: **main L/R → 1-2, cue L/R → 3-4, tracks 1-8 → 5-20, ESAI words
  0/1 → 21-22, 6/7 → 23-24**, as many as the device has (BlackHole 2ch:
  main; 8 ch: main, cue, T1-T2; BlackHole 16ch: main, cue, T1-T6; 64ch:
  all 24); `/audio/status` `capture` (`tracks`), `words` (24) and
  `output.map` / `output.layout` report it. Checked for every width
  (2/8/24 words × 2/8/16/24/64-channel devices) against the expected
  word placement, without PortAudio.
- `VirtualPanel.swift`: the map line and the per-device tooltips
  (`mapFor(channels:)`); `bash tools/panel/app/build.sh`: 0 warnings.
- `tools/panel/README.md` "Recording into a DAW" and the `/audio/status`
  row, `tools/panel/app/README.md`.

### Measured (13 Sep 2026, the M5, macOS 26.5, other agents' builds and runs on the machine throughout — load average ~4; the LTO binary `out/_agents/mout/build/ot_emu`, built from the working tree with the JIT agent's vendor change in progress)

`map.py`: the clean7 card, PLAY, 3 s, `audio start tracks`, FUNC + T7
at 1.6 s; `analyze.py` on the 24-word stream (`ls-tracks/`, `rt-tracks/`,
`ls-all/`; the same on both modes):

| measurement | lockstep `--dsp` | `--dsp-rt` |
|---|---|---|
| frames captured / taps | 150,159 / 8,943 (= the frames the ColdFire counted) | 150,158 / 8,949 |
| RMS dBFS, whole stream: main L/R | −23.9 / −24.0 | the same |
| T3, T4, T8 L/R | **−35.1 / −35.2** each | the same |
| T7 L/R (muted from 1.6 s) | **−38.1 / −38.2** | the same |
| T1, T2, T5, T6 L/R | −53.1 (below) | the same |
| Σ of the eight stems vs main L/R | **−51.8 dB** over every sample but four (rms 7.6 against 2,944), every difference in **−7..0 LSB** — each stem's word truncated where the mixdown truncates the sum once; the four samples: one per hit onset, where **the main pair's limiter** holds 32767 and the stems sum to 38,560 (the limiter is the mixdown's, after the sum) | the same figures |
| 1 s before → 1 s after the mute (from +100 ms) | T7 **−35.8 → −999 (exactly zero; last non-zero word 42 ms after the FUNC press = 2 ms after the T7 press)**; T3/T4/T8 −35.8 → −35.8, T1/T2/T5/T6 −53.8 → −53.8, main −23.5 → −25.9 (a quarter of the four gone) | the same |
| the first eight words vs `audio start all` on the same sequence | **byte-identical**, 150,159 frames (lockstep) | — |
| rt vs lockstep, onset-aligned, the 70,000 frames before the mute | main L/R and all sixteen stems **bit-identical**; the cue pair differs (19,111 of 70,000 samples, max 24,597) — pre-existing: the cue mix's table path under the JIT (the O21 class), captured by `all` before this milestone and never compared between the modes | |
| speed while playing and reading every 40 ms | 177 emulated ms per wall s (`--dsp-pcwatch` on: the instrumented step) | 1,100 |

The −53 dBFS of T1/T2/T5/T6 (the silent slot-1/2 tracks, O21) is
entirely a ~96-sample transient at each hit onset that **all eight
forwarded slots carry identically** (frames 82-178: the same words on T1
and T3 until they diverge at frame 145; T1 is ±2 LSB elsewhere, max 14):
the main pair's onset burst that clips at 32767 on this fixture and on
the reference `interdsp` capture (samples 132-153 there) is that burst
× 8 — a pre-existing feature of the emulated forward at a trig (the
ColdFire's delay pass or the read-back at the retrigger; not determined,
not this milestone's), visible per track now.

The gates, all on the same binary:

| gate | result |
|---|---|
| strict oracle vs `out/emu/ot_emu.ref-73c2815` (`--build-dir out/_agents/mout/build`) | **28 PASS, 0 FAIL**, 38 s (`out/_oracle/reports/20260913-130357-o23-stems.txt`; the interactive `audio.pcm` and `audio status` byte-identical) |
| `rtdrive.py --rt` on the clean fixture (`out/_agents/audio/otlive2.img`), `fit.py` | **onset 82, gain 0.7032, residual −33.0 dB** |
| `bench.py o23-stems --dsp --dsp-rt` (flat out, no capture) | 987 emulated ms per wall s (`per 16th 0.127 s`) under the machine's load; the A/B below |
| the tap's cost, `bench_audio.py` (the bench with a capture on and never read), rt: none / `all` / `tracks` | 970 / 981 / 968 emulated ms per wall s — within the run-to-run band, `tracks` taps 11,469 in the 4 s |
| the same, lockstep `--dsp`: none / `tracks` | 208 / 207 |
| ctest | 7/7 (inside the oracle) |
| the app | built, 0 warnings |

An A/B of the flat-out bench under the same load, alternating O21's LTO
binary (`out/_agents/fx2/build-lto/ot_emu`, no tap) with this one, no
capture and with `tracks` on (`ab_and_server.out`; the load average rose
from 3.7 to 6.7 during it — other agents' builds):

| run | O21 LTO, no capture | this binary, no capture | this binary, `audio start tracks` |
|---|---|---|---|
| #1 | 1,016 | 998 | 796 (the load spike) |
| #2 | 954 | 979 | 1,011 |

The band is the machine's, not the tap's: the same binary reads 968-1,011
with the stems on and 970-998 without, the O21 binary 954-1,016 — the
1,208 of O17b is the PGO binary on an idle machine, the 1,015-1,042 of
the O17b/O21 LTO builds their idle-machine figures.

**The server** (`server_verify.py`: port 8596, `--port-bin` this binary,
the tree2 fixture, `--sound on`, BlackHole 2ch, PLAY 60 s; run 1 with
the load at ~6.7, `server-run1/`):

| measurement | run 1 |
|---|---|
| ready | 7.6 s, the `--dsp-rt` child |
| `/audio/status` before / 1.5 s after `device=BlackHole 2ch` | `capture main, words 2` / **`capture tracks, words 24`**, `output.layout ["main L/R"]`, `map ["main L/R -> 1-2"]` (a 2-channel device) |
| PLAY 60 s, polled every 5 s | `/status rt` 0.99-1.025; **underruns 1 (inside the first 5 s, at the transport start), then 0 for 55 s; dropped 0, trimmed 0, pa_underflows 0** (run 3 below: 0 / 0 / 0 over the whole 60 s); buffered 68-83 ms; the drain's worst pump **3.0 ms** with 24-word reads (a 20 ms pump's reply is 85 KB of hex); `pushed` 2,722,821 / `played` 2,719,143 at +60 s |
| `/audio/pcm?from&max=44100` mid-play | 200, 44,100 frames, 176,400 bytes = the main pair, 4 bytes a frame (the headphones monitor's feed, unchanged) |
| the take | 60.258 s; `fit.py`: **onset 81, gain 0.7032, residual −33.0 dB** (the clean fit of O17c: the main pair the takes see is byte for byte what it was) |
| `device=off` | the capture back to `main`, 2 words, within 1.5 s |

A second run (port 8597, `server-run2/`) coincided with another agent's
`ot_emu` at a full core beside the panel's child: `/status rt` fell to
0.898, and the device stream showed what the pacer's shortfall always
shows (README, "Drift") — 18 underruns, 3,660 frames dropped, the take
58.7 s at +60 s — with the drain's worst pump still 3.2 ms, the take
still −33.0 dB, the capture `tracks` / 24 words throughout: the child's
pace, not the stems' cost (the tap's A/B above; the 24-word drain is 3 ms
a pump). A third run (port 8598, `server-run3/`, no other
emulator on the machine, load average ~4.5 from builds): **60 s with
underruns 0, dropped 0, trimmed 0, pa_underflows 0**, `/status rt`
0.989-1.016, buffered 57-118 ms, the drain's worst pump 37.8 ms once
(no consequence at 100 ms of prime), the take 60.208 s at −33.0 dB, the
capture `tracks` / 24 words throughout — the figure for a machine that
has a core for the child.

### What it does not do

- The stems are the MAIN terms: a track routed to CUE only (its `Y:0x40 +
  20j + k` gain) is not in its stem, and the two input pairs, the click
  and the mixdown's limiter are in no stem. Under the MASTER TRACK
  setting (P:0x292) tracks 1-7 feed track 8 instead of the main pair:
  their stems are then what the master receives (each with its own
  gain), track 8's is the main — not verified on a fixture (the OTLIVE
  projects have no master track).
- 16-bit over the pipe, as every capture; the DSP's words are 24-bit.
- A device with more than 24 channels gets 24; the layout is fixed
  (main, cue, tracks, the spare ESAI pairs), not chosen per device.
- The cue pair under `--dsp-rt` differs from lockstep (above): the JIT's
  rendering of the cue mix's table path, the O21 class, seen because the
  `tracks` stream was compared word for word between the modes; not
  this milestone's, not fixed.
- The onset burst on all eight forwarded slots (the fixture's clipped hit
  onset, now visible per track) is not explained here.
- Not tried: a many-channel device (this Mac has BlackHole 2ch; the
  layout beyond channel 2 is exercised by the width check, not by a
  device), the panel page's monitor with stems (it keeps the main pair
  by design), the batch `--audio-out` (the stems are the pipe's only).

## Milestone O24 — the "voice-start burst" is the card's own trim data: the fixture trims slots 1/2 to 64 frames, the firmware plays the 64-frame stub it is asked for, and the silent sample renders silence in both modes ✅ diagnosed, ❌ not an emulator defect (22 Sep 2026, branch `panel-ui`)

The brief: with a silent `SYNTH.wav` in a FLEX slot, the stock image "produces
a ~30 ms burst up to full scale at every voice start, passing the track's
mute" (modules/synth README, phase 2), the same thing as O23's "~96-sample
onset transient carried identically by all eight forwarded slots"; a silent
sample cannot burst on hardware, so find the emulation defect on the
voice-start path (four hypotheses on the DSP / host-port side). **None of
the four survives the first instrument.** Everything under
`out/_agents/burst/` (`drive.py`, `probe.py`, `blocks.py`, `stems.py`,
`repair_card.py`, the runs `ls1`/`ls2`/`ls3`/`rt1`/`p1..p6`/`w1`/`w2`, the
gates' outputs). The emulator is untouched.

### What the block dump says, before any DSP hypothesis (`--block-dump`, lockstep `--dsp`, the synth rig's card `out/_agents/synth/cards/synth8q.img`, stock image)

`audio start tracks` at the first trig (capture sample 81):

| stem | first non-zero | what |
|---|---|---|
| T8 (the SYNTH track, the silent file) | **never** — 0 non-zero words over the whole 1.6 s stream, lockstep and `--dsp-rt` alike | the silent sample plays digital silence from its first sample |
| T1, T2, T5, T6 | 81 | one identical 64-sample waveform (`25 −78 −229 −147 239 509 …`, ~7 kHz, growing to 4,820), then the FX1 filter's ring-down |
| T3, T4, T7 | 44,180 (the second trig) | the same 64-sample waveform |

The burst is **not on the trigged track**, and it enters **before the DSP
sees anything**: the 672-word push of frame 2 (the ColdFire's four 336-byte
track records per core, `0x80001c90 + ping·0xa80 + 336·track`) already
carries it — record T1/T2/T5/T6: header `(0, 0, 1.0, 0)` then
`(0x1010, phase, 1.0, tag)` + 16 pairs `10350000 104a0000 08ec0000 …` =
4149, 4170, 2284 … in 16-bit units, for frames 2–5 (64 samples), then the
same header with zero pairs from frame 6 on. The read-backs (frame 4:
positions 0/1 of BOTH cores, peak 1921) and the 512-word forward (slots
0/1/4/5) follow one and two frames later with exactly that content, so H1
(a stale ring half), H2 (a push off-by-one), H3 (uninitialised DSP memory)
and H4 (a declick coefficient) are all refuted at once: the DSP renders
what it is fed. The second trig's records carry the same longs again
(`158b0000 158c0000 …`, `fa650000 fa570000 …`, `bdd80000 bdcd0000 …`),
re-aligned to that trig's sub-frame position 4 — a fixed 64-sample block,
not the previous note.

### Where the 64 samples come from (PC watches on the ColdFire's renderer)

- The words are written by the format-3 (16-bit stereo) copy loop at
  `0x40008768..6e` (`movew (a0)+,(a3)+; clrw (a3)+` ×2), whose source `a0 =
  d3` and count `d2` come from a fetch through the voice struct's function
  pointer at `0x400086b6..c2` (`fetch(voice, position) → d0 = data pointer,
  d1 = frames available`; 0 → the silence path `0x40008722`).
- `watch 0x400086c0,0x400086c2` at the trig: T1/T2 (STATIC, `0x400932e8`)
  fetch `0x46aaa980`/`0x46aad980` (the STATIC head cache, `0x46aaa980 +
  0x3000·slot`) and T5/T6/T8 (FLEX, `0x40095bdc`) fetch `0x40ab1de0`/
  `0x40ab4de0`/`0x40accde0` (the FLEX arena at `0x40a955e0`, 6144-byte
  chunks via the tables at `0x80006914/18`), **every one with count 64 at
  position 0, then 48, 32, 16** — a 64-frame window — and T8 (LOOP on)
  starts over at 0 after it. A peek of those buffers: T1's and T5's hold
  `4149 4170 2284 2261 −3450 −3423 …` = **the first frames of
  `first-0.wav`**; T8's holds zeros (the silent file).
- The voice struct `0x800049d8 + 0xa8·track`, region at +40: `start 0, end
  0x40` on every one of these tracks (T8 included). Written at the voice
  start by `0x4000f790/f794` from `0x4000f6e2..f78a`: the region is the
  slot's **trim entry in its settings record** (`a4 + 300 + 20·(slice+1)`:
  start, end), and **a trim shorter than 64 frames is padded to 64**
  (`0x4000f758..f76c`). Poking the track's LEN to 127 changes nothing
  (`p5`) — the 64 is not the PLAYBACK page.
- The settings records (`0x100b14f0 + 0x448·slot` FLEX, `0x100d5b30 + …`
  STATIC) after the load: **slot 1 `first-0.wav` trim `0..0x40`, slot 2
  `second-0.wav` `0..0x40`, slot 5 `SYNTH.wav` `0..0x40`; slot 3
  `third-0.wav` `0..0x254f` = its 9,551 frames** (`p6`). The slot STATE
  records (`0x46c922c4 + 44·slot`) hold the right lengths for all of them
  (0xa77, 0xa77, 0x254f, 0x254f, 0x2b110) — the length is known; the trim
  is what the voice plays.
- `--watch-mem` on the trim end from the boot (`w1` slot 5, `w2` slot 3):
  written by the project load's **markers parser** at `0x40086396` (0 for
  SYNTH, 0x254f for third-0), then by the sanitiser at `0x400994b4`: `end
  = min(length, max(trim_end, start + 64))` (`0x40099448..94b8`) — 0 → 64.
  The parser (`0x40086xxx`) reads `PROJECT/markers.work` field by field
  through the card: a 22-byte `FORM … DPS1SAMP` header, 264 records of 784
  bytes (FLEX slots 1..136 — 129..136 the recorder buffers — then STATIC
  1..128: trim start, trim end, loop point, 64 slices × 3, a count), and a
  trailing u16 = the byte sum of the sub-header and every record
  (`0x460fab5c`; −54 on a mismatch). The layout is in
  `tools/hw/ot_project.py` (`MARKERS_*`).

### ✅ The finding: it is the card

`markers.work` of the OTLIVE fixture (`out/_projects/otlive/OTLIVE/PROJECT`,
and every card built from it: `out/_agents/port/otlive.img`,
`out/_agents/audio/otlive2.img`, the synth rig's `synth8q.img`) says, in
both halves: **slots 1 and 2 trim `0..64`, slots 3 and 4 `0..9551`**; the
synth rig's slot 5 has an all-zero record (its `mktree.py` wrote the
`[SAMPLE]` entry and no markers record). The firmware — the same code on
the unit — plays `[trim start, trim end]`, pads anything under 64 frames
to 64, and so plays a 64-frame stub of the file at every trig of T1/T2/T5/
T6 (slots 1/2). T3/T4/T7 of the synth rig were "moved to empty slots"
(static/flex slot 100, no `[SAMPLE]`, a zero record): they play a 64-frame
stub of arena page 0 = `first-0.wav`'s head at their step-9 trigs. And
**every WAV of the fixture starts with the same 2,048 frames**
(`first-0`, `second-0`, `third-0`, `fourth-0`, `extra-N`: one generator,
different lengths), which is the whole of O23's "identical transient on all
eight forwarded slots": eight tracks starting the same waveform, four of
them cut at their 64-frame trim (`ls3`, the clean fixture: T1/T2/T5/T6 ==
T3 for the first 64 samples, 63/64, then 0/136 — T3/T4/T7/T8 go on).

The "burst passes the mute" of the synth README: the mute was T8's and the
burst was T1/T2/T5/T6's. "At 12 ms the T8 record already holds the cave's
sine": T8 was right all along.

### ✅ Proven by repair, with the emulator unchanged (`repair_card.py`, `ls2`)

A copy of `synth8q.img` with the markers' slots 1/2 set to `0..2679` (the
files' frame counts) and slot 5 to `0..176400`, both copies (`markers.work`
+ `markers.strd`), both halves, checksum recomputed (`0x02d4 → 0x055e`;
the firmware accepted it):

| | card as built (trim 64) | trims repaired |
|---|---|---|
| T1/T2/T5/T6, first note | 64 frames, then the filter's ring-down to sample 6,362 | **2,629 frames of the 2,679-frame file, last non-zero at 81 + 2,676**, the first 64 samples byte-identical to the "burst" (63/64: it was the sample's own onset) |
| the T1 record, frames 6–9 | zero pairs | file data (max 16,648 / 12,289 / 23,713 / 29,601) |
| T8 (the silent file) | 0 non-zero words | 0 non-zero words |
| main out | the 64-frame stubs × 4 tracks, clipped | the four tracks' full notes |

`tools/hw/ot_project.py trim` (below) on a copy of the tree writes
`markers.work` **byte-identical** to that image patch (`tree_trim`).

### The fix, and where it is not

- **`tools/hw/ot_project.py`: `trims PROJECT_DIR` and `trim PROJECT_DIR
  SLOT full|END [START] [--flex|--static]`** — the markers layout, checksum
  and both copies (`.work` + `.strd`, as `_bank_write` treats banks). A
  tool that assigns a slot (`track-slot`, the synth rig's `mktree.py`) must
  write the record the unit's own browser load writes (`0x40095dd4`: end =
  the file's length, read from the code, 🟡 not driven through the
  browser): `trim PROJ 5 full`. Without it the slot plays 64-frame stubs.
- **Nothing in `tools/emu/ot_emu` or the vendored DSP** — the strict oracle
  on this tree's binary is 28/28 because nothing changed; "a real fix will
  change the reference render's onsets" was the premise, and the premise is
  wrong: the reference render's onsets ARE the fixture's trims.
- **The fixtures are the orchestrator's decision, not this milestone's.**
  Repairing OTLIVE's slots 1/2 (`trim PROJECT 1 full; trim PROJECT 2 full`
  on `out/_projects/otlive/OTLIVE/PROJECT`, then rebuilding
  `out/_agents/port/otlive.img` / `out/_agents/audio/otlive2.img`) makes
  T1/T2/T5/T6 play the whole of `first-0`/`second-0` at GAIN 75/72 — which
  changes every audio check of the oracle and, on the CLEAN fixture, the
  −33.0 dB fit itself: that fit is against `third-0.wav` alone and is clean
  precisely because the slot-1/2 tracks are 64-frame stubs. The synth rig's
  card wants `trim PROJ 5 full` (T8 then loops its 4 s of silence instead of
  64 frames of it — inaudible either way — and T1/T2/T5/T6 keep the
  fixture's stubs unless repaired too).

### The gates (this tree's `out/_agents/burst/build/ot_emu`, LTO, built from HEAD; the owner's app child `out/emu/ot_emu --dsp-rt` at 235 % of a core throughout, load average 4.8)

| gate | result |
|---|---|
| strict oracle vs `out/emu/ot_emu.ref-73c2815` | **28 PASS, 0 FAIL** (`out/_oracle/reports/20260922-133630.txt`) |
| ctest | 7/7 |
| `rtdrive.py --rt` on the clean fixture `otlive2.img` + `fit.py` (`rtfit2`; the script's default card is `otlive.img`, on which the fit reads −0.2 dB — the slot-1/2 loops at GAIN 75/72 are in the mix) | **onset 82, gain 0.7032, residual −33.0 dB** |
| the silent card under `--dsp-rt` vs lockstep (`rt1` vs `ls1`) | main and every stem **bit-identical over 44,000 frames**; T8 0 non-zero words in both; 1,111 emulated ms per wall s while capturing 24 words a frame |
| `bench.py --dsp --dsp-rt`, flat out, two runs | 974 and 945 emulated ms per wall s — under the owner's live child (2.35 cores) and the load above; O23's band for this binary class under load was 954–1,016, an earlier agent's idle-ish run 1,046 (`out/_agents/speed/verify_fix.log`). Not a code change: the binary is HEAD's |

### What it does not do

- Not driven through the unit's browser: that a browser load writes the
  full-length trim is read from `0x40095d90..5dd8` (`end = min(len,
  max(start + 64, a4))` with the slot state's length written from the same
  `a4`), not measured on a panel session. The synth README's panel load of
  `SYNTH.wav` was on a card whose slot-5 record the tool had already zeroed.
- Whether a real unit plays a 64-frame stub for a trim of 64 or 0 is the
  firmware's own arithmetic (`0x40099484`, `0x4000f758`: compares and adds,
  no EMAC), executed here instruction for instruction; 🟡 no unit to hand.
- The main pair's R lags L by one sample in the `main` capture on this card
  (R[i] == L[i−1] over the burst, `stock_silent`) while the stems' L and R
  agree — the ESAI sink's pair placement or the firmware's; noticed, not
  this milestone's.
- The fixture's own quirks stay as they are: OTLIVE's slots 1/2 at trim 64,
  the synth rig's T3/T4/T7 on empty slot 100 playing arena page 0.
