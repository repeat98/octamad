# The front-panel map

What `tools/panel/key_map.json` and `param_map.json` say, and how each entry
was measured (Tim Hastie, 11-25 Sep 2026: the stock image under route A,
then under the port; keys injected on the panel UART, the screen and LEDs
read back from the firmware's own panel stream through
`tools/panel/panel_link.PanelLink`). The investigation logs these tables
came from, and their replay scripts, are `git show f5148320:tools/panel/KEYMAP.md`;
the firmware facts they established are in `docs/firmware/PANEL.md` section 8.

A tap is `<row> <1<<bit>` then 60 ms, `<row> 0` then 100 ms (`Lab.tap`);
holds and chords keep per-row state exactly as `panel_server.key` does.
Boot ~15 s wall; the project load ~90 s.

## Three things that were not known before

- **SET DATE/TIME can be dismissed.** YES (0x26.1) stores the clock (writes
  the 7-byte record at `0x80000080`, shows `DATE/TIME STORED`, 91 LCD
  blocks); NO (0x26.2) straight on the dialog closes it without writing the
  record (90 blocks, `0x80000080` stays zero, E6 `dlg_no`,
  `E6_dlg_no.png`). Every run below works on the real main screen after one
  YES. `E1_yes.png`. (E3's `dlg_no`, 34 blocks, came after `dlg_yes` had
  closed the dialog and is the DISARM ALL popup of the next bullet.)
- **YES and NO are keys on the bare main screen: `ARM ALL` / `DISARM ALL`.**
  From a clean main screen (MIXER opened and closed, 112 blocks), YES alone
  draws the `ARM ALL` popup (28 blocks, `0x46c803d4` := ffff,
  `E5_yes_alone.png`) and NO alone draws `DISARM ALL` (35 blocks,
  `0x46c7fe22` := ffff, `E5_no_alone.png`); FUNC held changes nothing but
  the LEV box (`E5_func_yes.png`, `E5_func_no.png`, same block counts).
  The E1 run attributed these to FUNC+YES / FUNC+NO (E1 `func_yes` = the
  same 0x46c803d4 write, 25 blocks because it landed on a DISARM ALL
  popup; E1 `func_no` logged no change because the plain NO two steps
  earlier, `func_yes_no`, had already drawn DISARM ALL -- the first one in
  E1 is `func_mixer_no2`, the NO after the one that closed the menu).
  Under the emulator the popups do not time out (10 s idle,
  `E5_no_idle10000.png`); page keys redraw around them (`E5_yes_pg_amp.png`),
  a track key or a second NO leaves them (E5 `no_t2`, `no_no`: 0 blocks);
  only a full redraw clears them -- MIXER open+close, or any window opened
  and closed. So the NO that closes the last window is one NO too many, and
  every `*_no2: blk 34/35` step in E1 (6 of them) and E4's `main` baseline
  (`E4_main.png`, reached by YES then NO on the dialog) are that popup. It
  sits over the parameter boxes only; no key/LED/RAM measurement depends on
  it.
- **The panel's key rows are 0x20-0x26 only** (13 Sep 2026: plus row 0x27 =
  the encoders' PUSH switches, the last section of this file). Rows 0x27-0x2f were tapped
  on the dialog, the main screen and inside the PROJECT menu (E1 `sw_*`,
  E3 `menu_c27_*`, E4 `27_*`): no RAM, LED or menu-cursor change ever; the
  only effect of 0x27.x is a 2-4 block redraw of the tempo readout (and,
  once, a deferred redraw of the PROJECT menu). Not keys.

## Keys (row.bit -> id), with the measurement

Row 0x20/0x21/0x22 as given (trig 1-8, trig 9-16, T1-T8): re-measured --
T2..T8 taps move `0x80000000` / `0x100b14cc` to 1..7 and LED row 5/6
(`leds.out`, E1 `midi_t3`, E4 `*_T2`); trig taps on the MIXER toggle the
mute masks `0x8000000a` (audio) / `0x8000000e` (MIDI) one bit per key
(`leds.out`, E1 `mixer_trig1/9`).

| cell | id | evidence (log step -> PNG) |
|---|---|---|
| 0x23.0 | **tempo** | opens the `TEMPO 120.0` window; encoder 0x36 in it edits the BPM (`E1_tempo.png`, `E1_tempo_enc36+2.png`); FUNC+it = `TAP TEMPO` (`E1_func_tempo.png`) |
| 0x23.1 | **scene_a** | held: trig LEDs show the scene slots (row 0 bit 0 + row 2 bit 1 = scene A on 1, B on 9, the defaults); + trig 3 writes the Part's scene-A byte `0x40170f70` 0->2 and the next hold lights trig 3 (E1 `sceneA_*`); FUNC+it clears LED row 4 bit 0 and sets `0x80000006` (scene mute) |
| 0x23.2 | **scene_b** | same with the colours swapped; + trig 11 writes `0x40170f71` 8->10 (E1 `sceneB_*`); FUNC+it: row 4 bit 2, `0x80000007` |
| 0x23.3 | **scale** (inferred) | alone: nothing on the dialog, main screen, PROJECT menu, or while playing (E1/E2/E3/E4). FUNC+it opens `PATTERN SCALE 16/16 1x` with all trig LEDs lit (`E1_func_23_3.png`, `E2_func_x23_3.png`, `E4_23_3_func.png`). Named by that FUNC layer only |
| 0x23.4-7 | -- | nothing alone, with FUNC, held with T2, or under T2 (E4) |
| 0x24.0 | **down** | PROJECT menu: `MENU_SELROW` 0x400cbd98 0->1->2 (E3 `menu_d24_0*`); dialog: decrements the field under the cursor (day 12->11, month 09->08, `E3_dlg_c24_0*.png`); FUNC+it opens the TRIG MODE list and moves down it (`E3_tm_d24_0*.png`) |
| 0x24.1 | **right** | dialog cursor year->month->day (`E3_dlg_right*.png`); held on the main screen it blanks the BPM digits (tempo nudge, 6 blocks, E1 `main_24_1_*`) |
| 0x24.2-6 | **pg_playback, pg_amp, pg_lfo, pg_fx1, pg_fx2** | footer reads `PLAYBACK>STATIC`, `AMP`, `LFO`, `FX1>FILTER`, `FX2>DELAY` (`E1_pg_24_*.png`); page kind `0x460d1684` = 0, 2, 1, 3, 4; FUNC+0x24.2/3 open the PLAYBACK / AMP setup menus |
| 0x24.7 | **stop** | transport `0x800065b8` 1->0 while playing (E2 `stop`); FUNC+STOP does nothing visible on a fresh project (paste, nothing copied) |
| 0x25.0 | **play** | transport 0->1, LED row 11 01->08 (E2 `play_down`); again while playing: transport 2 (pause), row 11 09; FUNC+it = `CLEAR PATTERN` (`E1_func_play.png`) |
| 0x25.1 | **rec** | grid recording toggle: LED row 10 bit 4 on/off, the poked trigs (1, 5, 9, 13) appear on the trig LEDs, + trig 3 places one (E2 `rec*`); FUNC+it = `COPY PATTERN` (`E1_func_rec.png`) |
| 0x25.2 | **cue** | held: `0x460d168f` := 1 and a 2-block indicator; + T1 sets the cue mask `0x80000009` bit 0 and LED row 5 a9->a8 (E1 `cue_*`) |
| 0x25.3 | **recab** (inferred) | held, it swallows a T2 press (no track change, E4 `25_3_T2`); FUNC+it = `RECORDING 1 SETUP 1` (`E4_25_3_func.png`) |
| 0x25.4 | **reccd** (inferred) | same swallow (E4 `25_4_T2`); FUNC+it = `RECORDING 1 SETUP 2` (`E4_25_4_func.png`) |
| 0x25.5 | **func** | held: the LEV box reads MAIN (`E1_func_mixer_funcdown.png`); FUNC+MIXER = PROJECT menu (`E1_func_mixer.png`), FUNC+MIDI = PART chooser (`E1_func_midi.png`), FUNC+T1 = mute track 1 (`0x8000000a`), FUNC+BANK = `PATTERN A01 SETTINGS`, FUNC+PATTERN = arranger on (`0x80000010` := 1, LED row 8 bit 0, `E1_func_pattern.png`). FUNC+YES / FUNC+NO are NOT a layer: they draw the same `ARM ALL` / `DISARM ALL` popups YES / NO draw alone (E5 `func_yes` 28 blk, `func_no` 35 blk vs `yes_alone` 28, `no_alone` 35) |
| 0x25.6 | **pattern** | held: `SELECT PATTERN` window, current pattern on the trig LEDs; + trig 3: `0x80000004` and `0x800065be` 0->2 (E2 `pattern_*`) |
| 0x25.7 | **bank** | held: `SELECT BANK` window, 16 banks on the trig LEDs (a9 aa aa aa with OTLIVE) (E2 `bank_*`, `E2_bank_down.png`) |
| 0x26.0 | **mixer** | MIXER page, mute LEDs 55 55 ff ff, LED row 12 bit 6 (`E1_mixer.png`) |
| 0x26.1 | **yes** | dismisses SET DATE/TIME storing the clock (E1 `yes`, E5 `dlg_yes`: 7-byte record at `0x80000080`, 91 blk); bare main screen: `ARM ALL` popup (E5 `yes_alone`, `E5_yes_alone.png`); PROJECT menu: the first YES moves the focus descriptor `MENU_FOCUS` 0x400cbda8 from the root `0x400cbd8c` to `0x400cbcac` (into the PROJECT list, 0 blocks -- the menu does not redraw here), DOWN then YES activates SAVE: `SET / NO SET IS MOUNTED! PLEASE MOUNT ONE [OK]` over `CHOOSE A SET` (65 blk, `E5_menu_yes_yes.png`; the three NOs after it uncover `CHOOSE A SET`, the list with SAVE highlighted, the main screen: `E5_menu_no0..2.png`); TEMPO window: closes it, BPM kept (`E5_tempo_yes.png`, 60 blk); PATTERN SETTINGS checkbox rows: nothing (E5 `ps_yes`, `ps_yes2`) |
| 0x26.2 | **no** | closes windows/menus one level at a time (every `*_no` step: TEMPO, PROJECT menu and its alerts, PART chooser, PATTERN SETTINGS, PATTERN SCALE); on the BARE main screen it draws the `DISARM ALL` popup instead (35 blk, `0x46c7fe22` := ffff, `E5_no_alone.png`), which stays up until a full redraw (see above); a second NO on it: 0 blocks (E5 `no_no`) |
| 0x26.3 | **up** | PROJECT menu `MENU_SELROW` 2->1 (E3 `menu_u26_3`); dialog: increments the field (day 11->12, `E3_dlg_c26_3.png`); FUNC+it moves up the TRIG MODE list; held + track key opens the sample slot list `<< MACHINE:STATIC` (`E3_h26_3_t2.png`) |
| 0x26.4 | **left** | dialog: cursor day->month (then DOWN edits the month, `E3_dlg_c24_0b.png`); held on the main screen blanks the BPM digits like RIGHT (E1 `main_26_4_*`) |
| 0x26.5 | **midi** | MIDI mode `0x80000015` 0/1, LED row 8 04->cc (`E1_midi.png`); in MIDI mode the page LEDs use their second bit (AMP: row 8 f0) |
| 0x26.6-7 | -- | nothing in any combination (E1, E3, E4) |

## Encoders (row -> knob)

Reports are `<row> <signed delta>`; `+2` was sent, then `-2`.

| row | id | main screen, PLAYBACK page (empty card, static machine) | MIXER |
|---|---|---|---|
| 0x30 | a | slot 0 PTCH (`0x40170f8a`) | MAIN (`0x80000035`) |
| 0x31 | b | slot 1 STRT (`0x40170f8b`) | DIR AB (`0x80000031`) |
| 0x32 | c | slot 2 LEN (`0x40170f8c`) | GAIN AB (`0x8000002f`) |
| 0x33 | d | slot 3 RATE (`0x40170f8d`) | CUE (`0x80000036`) |
| 0x34 | e | slot 4 RTRG (`0x40170f8e`) | DIR CD (`0x80000030`) |
| 0x35 | f | slot 5 RTIM (`0x40170f8f`) | GAIN CD (`0x8000002e`) |
| 0x36 | level | track level `0x80000c50 + 2*track` 108->110 (LEV box) | MIX (`0x80000032`) |

E1 `enc_main_*` / `enc_mixer_*`, `E1_enc_mixer_3?+2.png` (the box that
changed). Top row of the MIXER left to right = A B C, bottom row = D E F.

## LEDs (bitmap row.bit; brightness id = row*8+bit)

`row.bit` is the LED bitmap row of the panel stream -- the 2-byte
`0x20+row <mask>` messages (`0xa0+(row-16)` from row 16), what
`panel_link.PanelLink.led_rows` holds and `led_bits()` flattens to
`row*8+bit`. It is NOT the `bits` string of `panel_server`'s `/leds`:
`_parse_leds` fills that from `0x10 <off> <8 bytes>` frames, which are LCD
page-0 blocks (docs/firmware/PANEL.md section 9), so `panel.html`'s `ledOn([byte, bit])`
follows the bottom band of the screen, not an LED. Measured on an own
server (port 8577, `srv_check.log`): at boot `bits[5]` bit 0 (led_t1) = 0
and `bits[8]` bit 2 (led_pg_playback) = 0 while the LED rows say 5=a9 and
8=04 (both lit); after REC through `/key?row=0x25&bit=1` `bits[10]` bit 4
(led_rec) = 0 while bytes 4-63 of `bits` all changed with the redraw; only
`ids["0x48"]` moved, 6 -> 15 -> 6. Until `/leds` carries `link.led_rows`
(17 bytes, row 0 first) and `ledOn` indexes that, the map's LEDs do not
light on the page. Not a keymap file, so not changed here.

Boot state (after `43` and the 88 brightness inits): rows 4=05 5=a9 6=aa
7=ff 8=04 9=01 11=01 16=0f, all else 0; brightness 15 for ids 0-0x37,
0x40-0x47, 0x49-0x5b; 6 for 0x48; 0 for 0x38-0x3f and 0x5c+.

| LED | row.bit | evidence |
|---|---|---|
| trig n | (n-1)//4 . 2*((n-1)%4) | MIXER: mute of trig 1/2/3/4 clears row 0 bit 0/2/4/6, trig 5 row 1 bit 0, trig 9 row 2 bits 0-1 (`leds.out`, E1 `mixer_trig*`); grid rec shows trigs 1/5/9/13 as rows 0-3 = 01 (E2 `rec`); the odd bit is the second colour (MIDI trigs ff in the MIXER, non-current banks aa) |
| track n | 5+(n-1)//4 . 2*((n-1)%4) | selecting T2 turns row 5 a9->a6 (track 1 bit0->bit1, track 2 bit3->bit2); T5..T8 move row 6 the same way (`leds.out`); the selected track holds the even bit, the others the odd bit; CUE+T1 a9->a8, FUNC+T1 (mute) a9->ab |
| play | 11.3 | row 11 01->08 on PLAY, 09 when paused, back to 01 200 ms after STOP (E2) |
| stop | 11.0 | the complement above; lit at boot |
| rec | 10.4 | row 10 00<->10 with the REC key, brightness id 0x48 6<->15 alongside (E2 `rec`, `rec_off`) |
| scene A / B | 4.0 / 4.2 | lit at boot; FUNC+SCENE A clears 4.0, FUNC+SCENE B clears 4.2 (E1 `func_scene*_funcup`) |
| tempo (inferred) | 4.6 | row 4 05->45 50 ms after the first PLAY and never off again, no blink on the wire (E2 `playing+50ms`); the only unexplained bit near the scene LEDs |
| pages | 8.2 PLAYBACK, 8.4 AMP, 10.6 LFO, 10.0 FX1, 10.2 FX2 | E1 `pg_24_*` (row 8 04->10->00, row 10 40->01->04); in MIDI mode bit+1 too (cc, f0) |
| midi | 8.6 | row 8 04->cc with the MIDI key (bits 6-7 = the two colours) |
| mixer | 12.6 | row 12 00->40 while the MIXER is open |
| arranger | 8.0 | row 8 04->05 after FUNC+PATTERN, back with the second |
| PROJECT / PART menu | 15.0 / 15.2 | with brightness ids 0x78 / 0x7a := 15 while open |

Not found: a FUNC LED (holding FUNC changes no row), the card LED (a
`request_card_mount` run, E3 `mount+*`, sends no LED traffic -- the CF LED
is presumably wired to the card slot), whatever rows 7 (ff at brightness
0) and 16 (0f) are, and why brightness id 0x48 (row 9 bit 0, lit dim at
boot) follows the REC key; row 9 bit 1 lights in CHROMATIC trig mode.

## Open ends

- 0x23.3 = SCALE and 0x25.3/0x25.4 = REC AB / REC CD rest on their FUNC
  layers (PATTERN SCALE window; RECORDING 1 SETUP 1 / 2) and on the two REC
  cells swallowing a track press (the `[TRACK]+[REC]` sampling chord); the
  emulator has no audio path, so a manual sampling never shows. A third
  recorder key (SRC3) was not found in rows 0x23-0x26.
- 0x23.3 swallowed a T2 press once (E3 `h23_3_t2`, straight after the slot
  list had been closed) and not in E4; treat that one as state left over.
- The PROJECT menu does not redraw on cursor moves or on the YES that
  enters a sub-list under the emulator (RAM moves, 0 LCD blocks); the
  dialog, the main screen and the alerts it opens do. A tap on row 0x27
  made it redraw once (`E3_menu_c27_0.png`, cursor on SYSTEM).
- REC AB/REC CD held + a trig, or FUNC + trig 1, light that trig's LED and
  nothing else visible (E1 `func_trig1`, E3 `h26_4_trig5`).
- The `ARM ALL` / `DISARM ALL` popups (YES / NO on the bare main screen)
  never clear on their own here; whether that is the emulator (a timer the
  UI task never sees) or the firmware was not checked. A panel user who
  taps NO one time too many keeps `DISARM ALL` on screen until the next
  full redraw (MIXER twice).
- `/leds` does not carry the LED rows the map indexes (see the LEDs
  section): the page's LEDs stay wrong until panel_server/panel.html are
  changed.
- The PROJECT-menu LED (row 15 bit 0) clears one LED refresh late: still
  set after the third NO closed the menu, cleared at the next MIXER open
  (E5 `menu_no2`, `menu_mixer_open`; E3 `menu_no2` the same).

## LED colours

The trig LEDs (rows 0-3) and the track LEDs (rows 5-6) are bi-colour, two
bitmap bits each: the map's bit is RED, the next bit up is GREEN, both lit is
YELLOW. The level nibble of the lit bit's id (`row*8 + bit`) is the
brightness: 15 full, 5 half. Measured against manual 11.5 / 12.4:

| state | bits | level |
|---|---|---|
| sample trig (`[TRIG]` in GRID RECORDING) | red | 15 |
| trigless lock (`[FUNC]+[TRIG]`) | green | 5 (half-bright) |
| trigless trig (`[TRIG]+[NO]` on a sample trig) | green | 15 |
| one-shot trig (`[FUNC]+[TRIG]` on a sample trig) | red+green = yellow | 15 |
| active track | red | 15 |
| other tracks | green | 15 |
| muted active track (`[FUNC]+[TRACK]`) | red+green = yellow | 15 |
| muted unselected track | off | – |

The page (`applyLeds`) renders the pair and the brightness; the other LEDs
stay single-bit with their fixed colour.

## The crossfader, the page encoders, the scene chords

Measured under the port on the OTLIVE fixture (the BLANK fixture for the init values).

### The crossfader is `0x40 <adc>` on the panel UART

The RX parser `0x4009228c` classes a report by its first byte's high nibble:
`0x2r` keys, `0x3r` encoders, **`0x40` the fader** (one payload byte, the pot's
ADC value 0..255, row nibble must be 0), `0x7r` a nine-byte report
(docs/firmware/PANEL.md section 9 has the decode). The byte goes through a calibration record at
`0x1ffffe` (magic `0x1234`; absent under emulation, so `pos = byte >> 1`) into
sys message kind 4 (`0x40092fac` -> `0x40092f2c` -> `0x40061e0a`), which
stores `0x460d16c8` (127 = scene A, 0 = scene B: the weight table
`0x80003c60` reads `0x8000_0000` at 127), needs AUDIO CC OUT = INT or INT+EXT
(`0x8000004a` bit 0; the fixture has `MIDI_AUDIO_TRK_CC_OUT=3`), echoes CC 48
= 127 - pos when EXT, and redraws the fader icon (LCD x 104-108, y 59-61).

| sent | `0x460d16c8` | LCD blocks |
|---|---|---|
| `0x40 255` / `254` | 127 | 2 / 1 (the icon; the first also the page) |
| `0x40 128` / `127` | 64 / 63 | 1 |
| `0x40 64` / `192` | 32 / 96 | 1 |
| `0x40 0` / `1` | 0 | 1 |
| rows `0x27`-`0x2f`, `0x37`-`0x3f`, `0x41`, `0x42`, `0x4f` with `0x40` | unchanged | 0 (`0x27`/`0x37`: the tempo readout, 2) |

The server's `/xfader?pos=` (0 = A/left .. 127 = B/right, = CC 48) sends
`0x40 (2*(127-pos)+1)`; the page's fader drags, wheels and arrows through it.
Direction confirmed with sound: AMP VOL locks in scene A make the mix 4.4 dB
quieter at `pos=0` than at `pos=127` (below).

### What the page encoders edit (param_map.json)

From the knob handler `0x40055008` and measured with `knob +1 / +5 / -6` per
slot on T5 (FLEX) and T1 (STATIC), `writes` naming the store `0x40055170`
(and the SRAM mirror at `0x40055172`), the LCD box redrawn each time:

| page (first press, kind `0x460d1684`) | slot s of track t = `base` + ... (`base` = `[0x46c82456]` + `[0x100b14cf]`*6322) | T1 / T5 measured |
|---|---|---|
| PLAYBACK (0) | `0x8edaa + t*30 + machine*6 + s` (machine byte `base+0x8eda2+t`: 0 STATIC 1 FLEX 2 THRU 3 NEIGHBOR 4 PICKUP) | `0x40170f8a..8f` / `0x40171008..0d` (+6 = FLEX) |
| LFO (1) | `0x8ee9a + t*24 + 0 + s` | `0x4017107a..7f` / `0x401710da..df` |
| AMP (2) | `0x8ee9a + t*24 + 6 + s` | `0x40171080..85` / `0x401710e0..e5` |
| FX1 (3) | `0x8ee9a + t*24 + 12 + s` | `0x40171086..8b` / `0x401710e6..eb` (FILTER) |
| FX2 (4) | `0x8ee9a + t*24 + 18 + s` | `0x4017108c..91` / `0x401710ec..f1` (DELAY) |
| LEVEL (row 0x36, any page) | `0x80000c50 + 2t` (pc `0x4004ec5a`), Part copy `base + 0x8ed92 + 2t` (`0x4004ec00`) | 108 -> 109 -> 114 -> 108 |

One detent = one unit, clamped to the descriptor's `[min, min+count-1]`
(RATE / HOLD / REL / WDTH / VOL at 127 stay on +1); PTCH (min 4, count 121)
wrote 64 on +1 -- its hook accumulates fractions, so the reset re-reads and
sends again. The descriptor per page is FUN_40031da4's: PLAYBACK from the
machine (`[0x400d5f38 + 4*machine]`), LFO `0x400d37f6`, AMP `0x400d3988`,
FX1/FX2 from the effect id (`base+0x8ed80+t` / `+0x8ed88+t` into
`0x400d5f58` / `0x400d5fdc`); with E = descriptor - 0x38: name `E+0x4e+6s`,
init `E+0x96+s`, min `E+0xa2+4s`, count `E+0xd2+4s`, live = bit 0 of nibble
s of the long at `descriptor+0x18e` (AMP `0x11811111`: F = XVOL is 8, and
knob F on the AMP page writes nothing, measured). **Init values** = the
BLANK fixture's bytes on all eight tracks = the descriptor defaults: PB 64 0
0 127 0 79, LFO 32 32 32 0 0 0, AMP 0 127 127 64 64, FX1 0 127 0 64 0 64,
FX2 47 0 127 0 127 0, LEVEL 108. `/knob/reset` measured on 8593: AMP VOL 84
-> 64 (`sent [-20]`), PTCH 70 -> 64 (`[-6, -1]`), STRT 33 -> 0, LEVEL 93 ->
108; refused: AMP SETUP (`a SETUP page is open`), MIXER, MIDI mode, AMP F.

### The scene chords, end to end

`lab_scenes.py` on the own server (Shift-latched chords are two `/key`
edges, the same as the page sends):

- `[SCENE A]` (0x23.1) held + `[TRIG 2]` (0x20.1): the Part's slot-A byte
  `base+0x8ed90` 0 -> 1; `[SCENE B]` (0x23.2) + `[TRIG 3]`: `base+0x8ed91`
  -> 2. LED rows while SCENE A is held: `01 00 02` = trig 1 red (this slot's
  scene), trig 9 green (the other slot's), the manual's colours.
- Lock: SCENE A held, AMP page, knob D (VOL) -64 on T1..T4: the Part VOL
  bytes do not move (84/64/64/64), the scene block `blob + pattern*0x18b2 +
  scene*0x100 + 0x8f3e2 + t*0x20` gets byte 15 (= AMP*6 + VOL) = 20/0/0/0
  (`0x401716d1/f1/711/731`, `0xff` = unlocked), the VOL box is drawn
  inverted with the locked value while the key is held (`S_lock_held.txt`).
- Morph: with the cores, PLAY 3 s / STOP at three fader positions: A
  (`pos=0`) -7.7 dBFS RMS, mid (64) -5.5, B (127) -3.3 (takes 3/4/5 of
  that server; peak 32768 in all three -- the fixture clips). The parameter
  boxes keep the Part values; the fader icon moves; the DSP-bound copy is
  what changes (`docs/firmware/MIDI.md` appendix C). Nothing in the panel needed fixing for
  the flow: the scene keys latch, the chords land, the fader was the
  missing piece.

## The encoder push: key-matrix row 0x27, bit = the encoder

Measured under the port on the OTLIVE fixture.

- **The parser has no push class.** `0x4009228c` (docs/firmware/PANEL.md section 9) accepts
  exactly four first bytes: `0x2r` keys (1 payload byte), `0x3r` encoders
  (1), `0x40` the fader (1), `0x7r` (9); anything else leaves it in its
  header state (`0x40092350`). An encoder report's byte is ADDED to the
  pending delta (`0x4009250c`) or posted as the delta (`0x4009254a`), so
  no value of it can mean "push". The key descriptor table at
  `[0x46c901dc]` (`0x4610048c` here) starts `ff 80` -- modifier row 0xff,
  so the ISR's shifted layer (+770) is never used -- then holds one
  12-byte entry per row 0x20-0x27 x bit 0-7, EVERY one live: `01 <code>
  01 00 460d17ae 00000000` = type 1, key code = row*8+bit (0x00-0x3f),
  down 1 / up 0, the UI queue. Rows 0x28+ index the all-zero shifted
  layer and are dropped. So the only key codes without a panel key are
  row 0x27's `0x38`-`0x3f` -- which is why a tap there always redrew the
  tempo readout (the 11 Sep note above): the UI does handle them.
- **Measured.** GRID RECORDING (REC), TRIG 1 held (the fixture's step 1
  has a sample trig on T5, mask `.. 01 01`), encoder A +5: the PTCH box
  inverts (dark pixels 2634 -> 2842) and ONE byte of the 36,568-byte
  pattern record changes, `0x400e46a1` = the track record (`blob +
  pattern*0x8ed8 + track*0x91a`, T5 = `0x400e4648`) + 0x59: `0xff` (no
  lock) -> `0x45` (69 = 64+5, the locked value). Still holding TRIG 1,
  `27 01` then `27 00` (60 ms apart): the byte is `0xff` again, the box
  is drawn normal (2634), nothing else in the record moved, and after the
  release the trig is still there (mask unchanged, LED red). Knob B +5 ->
  `+0x5a` = `0x05`; `0x27.0` does NOT clear it, `0x27.1` does. Knob F +5
  -> `+0x5e` = `0x54` (RTIM 79+5); `0x27.4` leaves it, `0x27.5` clears
  it. The lock bytes: `track record + 0x59 + slot` for the PLAYBACK page
  (A..F = +0x59..+0x5e), `0xff` = unlocked.
- **It is a toggle.** A push with NO lock on that parameter sets one at
  the current value: `0x27.0` on an unlocked PTCH -> `0x40` (64) and the
  box inverts; the next push -> `0xff`. (`0x27.4` in the F run put an E
  lock `0x00` = RTRG 0 on the step the same way; pushed again, gone.)
  The unit's [TRIG] + knob press does this too; the page's gesture
  inherits it.
- **LEVEL is bit 6**, measured through a scene lock (TRIG + LEVEL turn
  changed no pattern byte here): SCENE A held, LEVEL -5 -> the LEV box
  inverts (dark 2632 -> 2804); `0x27.6` with SCENE A still held -> normal
  again (2632): manual 10.3.1, "pressing the LEVEL knob while holding the
  SCENE key removes the lock". C and D (bits 2, 3) follow from the order
  A B . . E F; bit 7 is spare.
- **The lock LED.** With the lock on and the trig released, `/leds/stream`
  (`flash_stream.log`) shows row 0 go `0x01` -> `0x03` for ~24 ms every
  ~490 ms: the red trig LED gets a green blink (yellow for a frame) twice
  a second -- manual 12.5's "flash rapidly" as the emulated firmware
  emits it (a `/leds` snapshot reads `0x01` 23 times in 24). Without the
  lock there is no row-0 traffic; while the trig key is held the blink
  does not run.

`key_map.json` carries it as `knob_push` (a = [0x27, 0] .. f = [0x27, 5],
level = [0x27, 6]). The server's `/knob/press?row=0x30..0x36` sends the
down / up pair through the same per-row state as `/key`, so a trig held by
`/key` or by the page's Shift-latched chord stays held around it; the page
sends it for a double-click on an encoder while a TRIG key is held (alone,
a double-click is still `/knob/reset`).

## MKII keys (`ot_emu --mkii`)

Measured under the port booted as an MKII (`docs/firmware/PANEL.md` section 4c)
on bamsep26 + OCTABAM89_setgate; the same cells tapped under MKI reach
the dispatcher `0x40031904` and draw nothing (the MKI key table has no
record for them).

| cell | code | id | evidence |
|---|---|---|---|
| 0x23.4 | 0x1c | **proj** | PROJECT menu (PROJECT / SYSTEM / CONTROL / MIDI) |
| 0x23.5 | 0x1d | **part** | part chooser ONE / TWO / THREE / FOUR |
| 0x23.6 | 0x1e | **aed** | audio editor `STATIC 001` TRIM SLICE EDIT ATTR FILE |
| 0x23.7 | 0x1f | **arr** | arranger menu `ARR 1:` |
| 0x26.6 | 0x36 | **rec3** (inferred) | MKII key table record beside REC AB / REC CD with their sub-map; nothing drawn on a STATIC track |
| 0x23.3 | 0x1b | **page** = scale | same handler in both tables; FUNC + it draws `SCALE, TRACK 3` under `--mkii` |

0x24.7 = STOP re-measured under `--mkii` (LED row 11 back to `0x01`);
0x25.2 does not stop the transport.

