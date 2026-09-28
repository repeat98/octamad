# Remixes

A remix is a named selection of modules; `make image REMIX=<name>` builds it into a card-flashable image from your own OS 1.40C. [BUILDING.md](BUILDING.md) is the step-by-step guide. Each remix is a directory, `remixes/<name>/`: `remix.py` is the selection and `README.md` says what is in it and where it has run. `remixes/test/<name>/` holds the remixes that carry one module for that module's gates. This index is rendered from the selections (`make docs`). BUILDING.md §8 says how to write one.

## The rig

| remix | contains | proof |
|---|---|---|
| [`bottleservice`](../../remixes/bottleservice/README.md) | The rig + USB MIDI + USB AUDIO MASTER (T8 over USB) + Octakit. | on hardware: Sam's MKII, image 88, 27 Sep 2026 |
| [`rig-kits`](../../remixes/rig-kits/README.md) | The rig + Octakit. | `make check` |
| [`rig-mods`](../../remixes/rig-mods/README.md) | The rig + MIDI SCENES + Octakit, bridged. | `make check` |
| [`rig-scenes`](../../remixes/rig-scenes/README.md) | The rig + MIDI SCENES. | `make check` |
| [`usb`](../../remixes/usb/README.md) | The rig + USB MIDI (class-compliant, mirrors DIN). | `make check` |
| [`usb-audio`](../../remixes/usb-audio/README.md) | usb + USB AUDIO: the tracks, MAIN and CUE over USB (UAC2, 20 channels). | on hardware: Sam's MKII, image 64, 25 Sep 2026 |

## Effects

| remix | contains | proof |
|---|---|---|
| [`bus`](../../remixes/bus/README.md) | The plain two-server image: BusVerb + BusDelay + send bus + tempo sync. | on hardware: under earlier names |

## Firmware mods on the stock effects

| remix | contains | proof |
|---|---|---|
| [`kits`](../../remixes/kits/README.md) | All the firmware mods of the Octakit family, no effects: 256 Kits, the LO-FI AMF fix, CC to page 2. | port-gated |
| [`mods`](../../remixes/mods/README.md) | MIDI SCENES + Octakit + the LO-FI AMF fix + CC to page 2, bridged, on the stock effects. | port-gated |
| [`octatrick`](../../remixes/octatrick/README.md) | SYNTH MACHINE + SCALE QUANTIZER + DIRECT JUMP on the stock effects. | `make check` |
| [`octatrick-usb`](../../remixes/octatrick-usb/README.md) | SYNTH MACHINE + SCALE QUANTIZER + DIRECT JUMP + USB MIDI + USB AUDIO on the stock effects. | on hardware: Tim's MKI, 26 Sep 2026 (OCTATRICK9), USB audio on all 20 channels |
| [`ok-ms`](../../remixes/ok-ms/README.md) | Octakit + MIDI SCENES on the stock effects: the two mods alone. | on hardware: midisc's author's unit, 14 Sep 2026 (OKMS2) |
| [`recfix`](../../remixes/recfix/README.md) | The recorder loop click: the four ColdFire fixes beside the stock FX2 chooser, no DSP code of our own. | on hardware: with the bus, 12 Sep 2026 (OCTABAM83); RECORDER HOLD and RLEN PLEN port-gated |
| [`scenes`](../../remixes/scenes/README.md) | All the firmware mods of the MIDI SCENES family, no effects: scenes over MIDI, the LO-FI AMF fix, CC to page 2. | port-gated |
| [`usb-full`](../../remixes/usb-full/README.md) | stock + USB MIDI + USB AUDIO FULL (16 ch: the tracks). | port-gated |
| [`usb-lean`](../../remixes/usb-lean/README.md) | stock + USB MIDI + USB AUDIO (20 ch: tracks, MAIN, CUE). | port-gated |
| [`usb-master`](../../remixes/usb-master/README.md) | stock + USB MIDI + USB AUDIO MASTER (2 ch: track 8). | port-gated |

## Reference

| remix | contains | proof |
|---|---|---|
| [`machinedrum`](../../remixes/machinedrum/README.md) | Machinedrum machine on T1-T4, hidden DSP dispatch, stock inserts on the unaffected tracks. | ? |
| [`restock`](../../remixes/restock/README.md) | every stock FX2 effect, all fourteen: put my unit back. | `make check` |

## Probes

| remix | contains | proof |
|---|---|---|
| [`cfmeter`](../../remixes/cfmeter/README.md) | octatrick-usb + CF METER on T8's FX2: ColdFire idle time and frame-interrupt duration, over USB. | port-gated: the readout chain under the port |
| [`cfmeter-port`](../../remixes/cfmeter-port/README.md) | cfmeter without the idle loop: the port gate for the readout chain and the interrupt timing. | port-gated: the readout chain under the port |

## Test remixes

One module each, for that module's gates: `make check REMIX=<name>`.

| remix | contains | proof |
|---|---|---|
| [`euclid`](../../remixes/test/euclid/README.md) | Euclid rhythmic modulation: 12 dB LP/BP/HP or AMP, both FX slots. | local render: the module's render gates |
| [`lofi-amf-fix`](../../remixes/test/lofi-amf-fix/README.md) | Reference minimal build: the LO-FI AMF mpysu->mpyuu fix, alone. | `make check` |
| [`midi-scenes`](../../remixes/test/midi-scenes/README.md) | Reference minimal build: the MIDI SCENES ColdFire patch, alone. | `make check`: on hardware inside `ok-ms` |
| [`miniverb`](../../remixes/test/miniverb/README.md) | Minimal allocator-owned FDN reverb. | local render: `make verify-miniverb` |
| [`octakit`](../../remixes/test/octakit/README.md) | Em's Octakit alone -- must reproduce her own build byte for byte. | `make check`: on hardware inside `ok-ms` |
| [`repitch`](../../remixes/test/repitch/README.md) | stock effects with variable-speed REPITCH in the TSTR selector. | on hardware: repeat98's MKII, 16 Sep 2026 (OCTABAM81) |
| [`tapeecho`](../../remixes/test/tapeecho/README.md) | Tape Echo replacing Spring Reverb, alone. | on hardware: the author's unit (OCTACLID4): six instances; a seventh freezes it, open |

Never share a built image: it contains Elektron's OS.
