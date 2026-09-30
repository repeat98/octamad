# Remixes

A remix is a named selection of modules; `make image REMIX=<name>` builds it into a card-flashable image from your own OS 1.40C. [BUILDING.md](BUILDING.md) is the step-by-step guide. Each remix is a directory, `remixes/<name>/`: `remix.py` is the selection and `README.md` says what is in it and where it has run. `remixes/test/<name>/` holds the remixes that carry one module for that module's gates. This index is rendered from the selections (`make docs`). BUILDING.md §8 says how to write one.

## The rig

| remix | contains | proof |
|---|---|---|
| [`bottleservice`](../../remixes/bottleservice/README.md) | The rig + USB MIDI + USB AUDIO OUT MASTER (T8 to the computer) + USB AUDIO IN CD (the computer onto inputs C/D) + Octakit. | on hardware: Sam's MKII, image 88, 27 Sep 2026 |

## Firmware mods on the stock effects

| remix | contains | proof |
|---|---|---|
| [`analog-bassdrum`](../../remixes/analog-bassdrum/README.md) | Analog BD source machine, switchable 808/909, stock AMP and FX. | port-gated: source/UI under the port; earlier ANALOGBD1 auditioned on MK1, current revision unflashed |
| [`analog-bd-dynload`](../../remixes/analog-bd-dynload/README.md) | Analog BD on all eight tracks and all 14 stock effects, each DSP effect loaded on demand. | port-gated: port qualification in progress; not yet on hardware |
| [`dynload-stock`](../../remixes/dynload-stock/README.md) | The stock effects, each DSP effect loaded on demand: stock behaviour, stock program space freed. | port-gated: port qualification in progress; not yet on hardware |
| [`mods`](../../remixes/mods/README.md) | Every ColdFire mod in one image on the stock effects: MIDI SCENES, Octakit, the recorder fixes, REPITCH, USB MIDI + AUDIO (octatrick's three cannot join it). | port-gated |
| [`octatrick`](../../remixes/octatrick/README.md) | SYNTH MACHINE + SCALE QUANTIZER + DIRECT JUMP on the stock effects. | `make check` |
| [`octatrick-usb`](../../remixes/octatrick-usb/README.md) | SYNTH MACHINE + SCALE QUANTIZER + DIRECT JUMP + USB MIDI + USB AUDIO on the stock effects. | on hardware: Tim's MKI, 26 Sep 2026 (OCTATRICK9), USB audio on all 20 channels |
| [`ok-ms`](../../remixes/ok-ms/README.md) | Octakit + MIDI SCENES on the stock effects: the two mods alone. | on hardware: midisc's author's unit, 14 Sep 2026 (OKMS2) |

## Reference

| remix | contains | proof |
|---|---|---|
| [`restock`](../../remixes/restock/README.md) | every stock FX2 effect, all fourteen: put my unit back. | `make check` |

## Test remixes

One module each, for that module's gates: `make check REMIX=<name>`.

| remix | contains | proof |
|---|---|---|
| [`bus`](../../remixes/test/bus/README.md) | The plain two-server image: BusVerb + BusDelay + send bus + tempo sync. | on hardware: under earlier names |
| [`cfmeter`](../../remixes/test/cfmeter/README.md) | octatrick-usb + CF METER on T8's FX2: ColdFire idle time and frame-interrupt duration, over USB. | port-gated: the readout chain under the port |
| [`cfmeter-port`](../../remixes/test/cfmeter-port/README.md) | cfmeter without the idle loop: the port gate for the readout chain and the interrupt timing. | port-gated: the readout chain under the port |
| [`dsp-dynload`](../../remixes/test/dsp-dynload/README.md) | Experimental real residency and dispatch qualification. | port-gated: Emulator-gated; a first hardware test image keeps the static originals. |
| [`dsp-dynload-transport`](../../remixes/test/dsp-dynload-transport/README.md) | Two-core dynamic-loader transport qualification. | port-gated: Both-core DMA, bounded P staging and UI message; not for flashing. |
| [`euclid`](../../remixes/test/euclid/README.md) | Euclid rhythmic modulation: 12 dB LP/BP/HP or AMP, both FX slots. | local render: the module's render gates |
| [`lofi-amf-fix`](../../remixes/test/lofi-amf-fix/README.md) | Reference minimal build: the LO-FI AMF mpysu->mpyuu fix, alone. | `make check` |
| [`midi-scenes`](../../remixes/test/midi-scenes/README.md) | Reference minimal build: the MIDI SCENES ColdFire patch, alone. | `make check`: on hardware inside `ok-ms` |
| [`miniverb`](../../remixes/test/miniverb/README.md) | Minimal allocator-owned FDN reverb. | local render: `make verify-miniverb` |
| [`octakit`](../../remixes/test/octakit/README.md) | Em's Octakit alone -- must reproduce her own build byte for byte. | `make check`: on hardware inside `ok-ms` |
| [`pmap-probe`](../../remixes/test/pmap-probe/README.md) | Hardware probe for the DSP's 16K program map (MAIN L core 0, R core 1: 882 Hz pass, 110 Hz fail). | `make check`: builds; under the port it passes by construction; the unit is the measurement |
| [`repitch`](../../remixes/test/repitch/README.md) | stock effects with variable-speed REPITCH in the TSTR selector. | on hardware: repeat98's MKII, 16 Sep 2026 (OCTABAM81) |
| [`tapeecho`](../../remixes/test/tapeecho/README.md) | Tape Echo replacing Spring Reverb, alone. | on hardware: the author's unit (OCTACLID4): six instances; a seventh freezes it, open |
| [`usb`](../../remixes/test/usb/README.md) | The rig + USB MIDI (class-compliant, mirrors DIN). | `make check` |
| [`usb-audio`](../../remixes/test/usb-audio/README.md) | usb + USB AUDIO: the tracks, MAIN and CUE over USB (UAC2, 20 channels). | on hardware: Sam's MKII, image 64, 25 Sep 2026 |
| [`usb-io-main-ab`](../../remixes/test/usb-io-main-ab/README.md) | stock - SPATIALIZER + USB MIDI + USB AUDIO OUT MAIN + USB CROSSBAR + USB AUDIO IN AB. | port-gated: `make check` (verify_usb, verify_usb_in) under the port, 28 Sep 2026; not on hardware in this form |
| [`usb-io-main-abcd`](../../remixes/test/usb-io-main-abcd/README.md) | stock - SPATIALIZER + USB MIDI + USB AUDIO OUT MAIN + USB CROSSBAR + USB AUDIO IN ABCD. | port-gated: `make check` (verify_usb, verify_usb_in) under the port, 28 Sep 2026; not on hardware in this form |
| [`usb-io-main-cd`](../../remixes/test/usb-io-main-cd/README.md) | stock - SPATIALIZER + USB MIDI + USB AUDIO OUT MAIN + USB CROSSBAR + USB AUDIO IN CD. | port-gated: `make check` (verify_usb, verify_usb_in) under the port, 28 Sep 2026; not on hardware in this form |
| [`usb-io-main-cue-ab`](../../remixes/test/usb-io-main-cue-ab/README.md) | stock - SPATIALIZER + USB MIDI + USB AUDIO OUT MAIN CUE + USB CROSSBAR + USB AUDIO IN AB. | port-gated: `make check` (verify_usb, verify_usb_in) under the port, 28 Sep 2026; not on hardware in this form |
| [`usb-io-main-cue-abcd`](../../remixes/test/usb-io-main-cue-abcd/README.md) | stock - SPATIALIZER + USB MIDI + USB AUDIO OUT MAIN CUE + USB CROSSBAR + USB AUDIO IN ABCD. | port-gated: `make check` (verify_usb, verify_usb_in) under the port, 28 Sep 2026; not on hardware in this form |
| [`usb-io-main-cue-cd`](../../remixes/test/usb-io-main-cue-cd/README.md) | stock - SPATIALIZER + USB MIDI + USB AUDIO OUT MAIN CUE + USB CROSSBAR + USB AUDIO IN CD. | port-gated: `make check` (verify_usb, verify_usb_in) under the port, 28 Sep 2026; not on hardware in this form |
| [`usb-io-tracks-ab`](../../remixes/test/usb-io-tracks-ab/README.md) | stock - SPATIALIZER + USB MIDI + USB AUDIO OUT TRACKS + USB CROSSBAR + USB AUDIO IN AB. | port-gated: `make check` (verify_usb, verify_usb_in) under the port, 28 Sep 2026; not on hardware in this form |
| [`usb-io-tracks-abcd`](../../remixes/test/usb-io-tracks-abcd/README.md) | stock - SPATIALIZER + USB MIDI + USB AUDIO OUT TRACKS + USB CROSSBAR + USB AUDIO IN ABCD. | port-gated: `make check` (verify_usb, verify_usb_in) under the port, 28 Sep 2026; not on hardware in this form |
| [`usb-io-tracks-cd`](../../remixes/test/usb-io-tracks-cd/README.md) | stock - SPATIALIZER + USB MIDI + USB AUDIO OUT TRACKS + USB CROSSBAR + USB AUDIO IN CD. | port-gated: `make check` (verify_usb, verify_usb_in) under the port, 28 Sep 2026; not on hardware in this form |
| [`usb-io-tracks-main-cue-ab`](../../remixes/test/usb-io-tracks-main-cue-ab/README.md) | stock - SPATIALIZER + USB MIDI + USB AUDIO OUT TRACKS MAIN CUE + USB CROSSBAR + USB AUDIO IN AB. | port-gated: `make check` (verify_usb, verify_usb_in) under the port, 28 Sep 2026; not on hardware in this form |
| [`usb-io-tracks-main-cue-abcd`](../../remixes/test/usb-io-tracks-main-cue-abcd/README.md) | stock - SPATIALIZER + USB MIDI + USB AUDIO OUT TRACKS MAIN CUE + USB CROSSBAR + USB AUDIO IN ABCD. | port-gated: `make check` (verify_usb, verify_usb_in) under the port, 28 Sep 2026; not on hardware in this form |
| [`usb-io-tracks-main-cue-cd`](../../remixes/test/usb-io-tracks-main-cue-cd/README.md) | stock - SPATIALIZER + USB MIDI + USB AUDIO OUT TRACKS MAIN CUE + USB CROSSBAR + USB AUDIO IN CD. | port-gated: `make check` (verify_usb, verify_usb_in) under the port, 28 Sep 2026; not on hardware in this form |
| [`usb-out-main`](../../remixes/test/usb-out-main/README.md) | stock + USB MIDI + USB AUDIO OUT MAIN (2 ch: MAIN L/R). | port-gated: `verify_usb` under the port, 28 Sep 2026 |
| [`usb-out-main-cue`](../../remixes/test/usb-out-main-cue/README.md) | stock + USB MIDI + USB AUDIO OUT MAIN CUE (4 ch: MAIN + CUE). | port-gated |
| [`usb-out-master`](../../remixes/test/usb-out-master/README.md) | stock + USB MIDI + USB AUDIO OUT MASTER (2 ch: track 8). | port-gated |
| [`usb-out-tracks`](../../remixes/test/usb-out-tracks/README.md) | stock + USB MIDI + USB AUDIO OUT TRACKS (16 ch: the tracks). | port-gated |
| [`usb-out-tracks-main-cue`](../../remixes/test/usb-out-tracks-main-cue/README.md) | stock + USB MIDI + USB AUDIO (20 ch: tracks, MAIN, CUE). | port-gated |

Never share a built image: it contains Elektron's OS.
