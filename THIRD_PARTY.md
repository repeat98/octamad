# Third-party sources

What this repository carries from elsewhere, under which licence, and where.
`LICENSE` covers this repository's own code and documentation (MIT). Nothing
below is an Elektron byte: the firmware is the user's own copy, read at build
time (`.incbin`, `make os`).

## Transcribed into DSP modules

| source | licence | copyright | used in |
|---|---|---|---|
| jpcima `rc-effect-playground` — Hera `HeraChorus.dsp`, `bbd_line.h` (Juno-60 chorus) | ISC | Jean Pierre Cimalando | `modules/modulation` JUNO |
| pendragon-andyh Juno-60 chorus measurements | data | Andy Harman | `modules/modulation` JUNO (rates, delay ranges) |
| Roland SDD-320 Dimension D service notes + published measurements | laws only | — | `modules/modulation` DIM (the mix amounts were voiced here, not taken from the notes) |
| J. Dattorro, *Effect Design Part 2*, JAES 45(10), 1997 | paper (laws) | AES | `modules/modulation` FLNG (Table 6) |
| Mutable Instruments Rings `string.h` / `string.cc` | MIT | Emilie Gillet | `modules/modulation` COMB |
| ChowDSP ChowPhaser (Schulte Compact Phasing A model) | BSD-3-Clause | Jatin Chowdhury | `modules/modulation` PHSR |
| Airwindows Pockey | MIT | Chris Johnson | `modules/character` TXTR, 13 to 22 Sep 2026 (removed; `git show OCTABAM43:modules/character/pockey_ref.py`) |
| JClones TapeHead, DaTube, OInflator, AC1 (JSFX) | MIT | JClones | `modules/character` SAT (TAPE / TUBE / INFL), COMP / GLUE |
| audiojs/filter `moogLadder`, `oberheim` (Zavalishin's zero-delay forms) | MIT | audiojs contributors | `modules/spectrum` LADR, LP / BP |
| markandrus/octemu `custom/coldfire/usb-midi.s`, `custom/usb-midi.py` (descriptors) | MIT | markandrus | `modules/usb-midi` (his text; one ISA-B substitution, README) |
| markandrus/octemu `custom/coldfire/usb-audio.s`, `custom/usb-audio.py` (descriptors) | MIT | markandrus | `modules/usb-audio-extended` (his shims, producer, packet builder and servo; the loader replaces his card payload machinery); `modules/usb-audio-full` and `modules/usb-audio-master` assemble the same source with fewer channels |
| markandrus/octemu `src/board/ot-board.c` USB packet bench (line protocol) | MIT | markandrus | `tools/emu/ot_emu/usb.h` speaks the same protocol so his `tests/usb-host.py` drives the port; the model is written here |
| Airwindows Capacitor2 | MIT | Chris Johnson | `modules/spectrum` ISO (`capacitor2_ref.py`) |

Retired transcriptions (in history only): jpcima `string-machine` (BSL-1.0,
the Solina ensemble, removed 16 Sep 2026).

`docs/effects/PORTS.md` is the survey behind the modulation and station
ports, with the sources that were read for laws only (GPL code was never
transcribed).

## Firmware modifications built from their authors' repositories (git submodules)

| module | upstream | licence |
|---|---|---|
| `modules/midi-scenes` (MIDI SCENES) | https://github.com/bkkbrls-del/midisc | MIT (the repository's LICENSE file, added by its author 9 Sep 2026, carries octabam's copyright line verbatim) |
| `modules/octakit` (Octakit) | https://github.com/emuyia/ems-octakit | MIT, Copyright (c) 2026 June Kiff |
| `tools/remix/loader.S` (the DRAM loader) | derived from Octakit's `runtime/loader.S` | MIT, Copyright (c) 2026 June Kiff |

`modules/kits-reload`, `modules/scenes-kits`, `modules/cc-map`,
`modules/tempo-sync`, `modules/mode-defaults`, `modules/flex-seekbind*`,
`modules/recorder-spacing` and `modules/lofi-amf-fix` are written here
(sambanks; the LO-FI fix from Bryan T's finding) and carry `LICENSE`.

## Emulator and panel from a fork of this repository

| source | licence | copyright | used in |
|---|---|---|---|
| Tim Hastie, [timhastie/octa-panel](https://github.com/timhastie/octa-panel) at `be68244` (a fork of octabam, 10-25 Sep 2026) | MIT (the fork's `LICENSE` is octabam's, copyright line unchanged) | Tim Hastie (his changes) | `tools/panel/` (the virtual front panel, the macOS app, the key/LED map and its evidence); `tools/emu/ot_emu` (`--interactive`, pacing, the DSPI RTC, DMA timers DTIM0-3, event-horizon bursts, the page-table memory path, lazy DSP batching, `--dsp-rt`, bounded records, card write-back, memory-to-memory eDMA copies, per-track taps; `oracle/`, `pgo.sh`); the `--dsp-rt` hunks of `tools/patches/dsp56300.patch`; `docs/firmware/COLDFIRE_PORT.md` (his milestones O14i-O24) |
| Mark Roberts, [markandrus/octemu](https://github.com/markandrus/octemu) `assets/panel/gen_svg.py` | MIT (Copyright (c) 2026 Mark Roberts) | Mark Roberts | `tools/panel/skin/gen_svg.py`: the MKII front panel drawn as SVG (geometry measured from photographs of a unit, keys, knobs, fader, LEDs, the lighting classes); octabam added the `dark` palette and an output directory |

## Analysis tooling

Portions of the firmware analysis tooling originate from
https://github.com/mxldyn/octamax, Copyright (c) 2025-2026 Maxolydian, MIT
(`LICENSE`).

`tools/ghidra/processors/DSP56300/` (the DSP56300 processor module) and
`tools/ghidra/patches/coldfire-emac.patch` (ColdFire ISA_C/EMAC in Ghidra's
68000 module) were written for this repository by Robert Gay and are offered
to Ghidra upstream as `roblg/ghidra` #3 and #2. They carry Ghidra's
licence, Apache-2.0, in each file's header so they can go upstream as they
are; the patch is a diff against Ghidra 12.1.4's
`Ghidra/Processors/68000` (Apache-2.0, National Security Agency).
`make ghidra-install` adds both to a copy of your own Ghidra release; no
Ghidra file is committed.

## Fetched by `make setup`, never committed (`vendor/`, gitignored)

| what | licence | note |
|---|---|---|
| dsp56300 (DSP56300 emulator; `dsp_asm` / `dsp_host` are additions written here, under `tools/harness/dsp_host/`) | GPL-3.0 | patches in `tools/patches/`; built binaries are never distributed |
| joelanders/mc68k-md-mm (Musashi-derived ColdFire core) | GPL-3.0 | pinned commit in `scripts/setup.sh` |
| mischa85/elektron-firmware-tool | MIT, Copyright (c) 2026 Marcel Bierling | `tools/patches/elektron-firmware-tool.patch` |
| Unicorn (via `.venv`, `make emu-setup`) | GPL-2.0 | `tools/patches/unicorn_emac_fractional.patch` |
