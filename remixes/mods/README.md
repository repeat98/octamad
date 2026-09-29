# `mods` — every ColdFire mod that fits in one image

The firmware modifications that change what the unit does without touching
the effects: the stock FX1/FX2 choosers stay as shipped, so every existing
project plays as it did. Not in it: SCENES P2 (the ledger refuses it beside
KITS RELOAD and MIDI SCENES) and Tim Hastie's three (DIRECT JUMP hooks
`0x400a06d6`, a site Octakit's recipe writes; SCALE QUANTIZER's 2,916-byte
ROM unit beside REPITCH's leaves CC MAP's 724-byte cave no run in the free
ROM; both measured 28 Sep 2026). Those three are
[`octatrick`](../octatrick/README.md).

## What is in it

Each module's own page has the technical detail and the measurements.

| area | module | what you get |
|---|---|---|
| Kits | [OCTAKIT](../../modules/octakit/README.md) (Em, [ems-octakit](https://github.com/emuyia/ems-octakit)) | 256 named Kits per project in place of 64 bank-tied Parts; any Kit on any pattern. Her README is the manual. |
| Scenes | [MIDI SCENES](../../modules/midi-scenes/README.md) (bkkbrls-del, [midisc](https://github.com/bkkbrls-del/midisc)) | scene locks driven over MIDI: hold, morph, save, reload, clear, copy, paste |
| | [KITS RELOAD](../../modules/kits-reload/README.md) | the bridge that lets MIDI SCENES' Part Reload run beside Octakit's kit reload |
| MIDI | [CC MAP](../../modules/cc-map/README.md) | CC 62–67 reach the FX2 effect's page-2 knobs, CC 68–73 the FX1 effect's (stock reaches page 1 only) |
| | [SCENES KITS](../../modules/scenes-kits/README.md) | the bridge that lets CC MAP and Octakit share the CC dispatch |
| Recorder | [RECORDER SPACING](../../modules/recorder-spacing/README.md), [RECORDER HOLD](../../modules/recorder-hold/README.md), [FLEX SEEK BIND](../../modules/flex-seekbind/README.md), [FLEX SEEK BIND CTR](../../modules/flex-seekbind-ctr/README.md) | the recorder loop click fixed: a fixed-RLEN take is exactly as long as the gap to the next arm, and a re-trig on the buffer seeks the voice instead of restarting it |
| | [RLEN PLEN](../../modules/rlen-plen/README.md) | RLEN value PLEN: one loop of the track's pattern, so TRIG ONE + QREC PLEN records the next pass and stops |
| Machines | [REPITCH](../../modules/repitch/README.md) (repeat98) | TSTR REPITCH: a track follows the project tempo by playback speed, like a turntable |
| Fixes | [LOFI AMF FIX](../../modules/lofi-amf-fix/README.md) (Bryan T) | stock LO-FI's AMF knob no longer jumps the pitch backwards |
| USB | [USB MIDI](../../modules/usb-midi/README.md), [USB AUDIO OUT TRACKS MAIN CUE](../../modules/usb-audio-out-tracks-main-cue/README.md) (markandrus, [octemu](https://github.com/markandrus/octemu)) | a class-compliant MIDI port mirroring the DIN ports, and a 20-channel 24-bit audio input on the computer: the tracks, MAIN and CUE |

The fourteen stock FX2 effects are listed, so the chooser is stock's.

## Where it has run

- **Under the ColdFire port:** boots; every `apply_part` in a project load
  runs the chained dispatch; `make check REMIX=mods` green (REPITCH's
  playback checks skip while the port's output carries no audio).
- **On hardware, in subsets:** Octakit + MIDI SCENES + KITS RELOAD as
  `ok-ms` (midisc's author's unit, 14 Sep 2026); the recorder fixes as
  OCTABAM83/84 (Sam's MKII, 12 Sep 2026; RECORDER HOLD and RLEN PLEN
  port-gated only); REPITCH as OCTABAM81 (repeat98's MKII, 16 Sep 2026);
  USB AUDIO as image 64 (Sam's MKII, 25 Sep 2026).
- **Not flashed as a whole.** Not measured: MIDI CCs through the chained
  dispatch on hardware; midisc's Part save/reload menu hooks against
  Octakit's LOAD/SAVE KIT menus.

## How to flash

```bash
make image REMIX=mods BUILD=1     # -> out/OCTATRACK_OCTABAM1.bin
```

[BUILDING.md](../../docs/remixes/BUILDING.md) is the walk-through from a
fresh machine to a flashed unit; `make check REMIX=mods` runs every gate
first. **Octakit migrates Parts into Kits on project load:** back up the
card first; going back to stock can lose Kit data.
