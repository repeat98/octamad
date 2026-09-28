# `machinedrum` — a Machinedrum on T1–T4

A Machinedrum engine on core 1: one MD per Part, on T1, T2, T3 or T4
(FLEX plus an MD signature, chosen in SRC SETUP). A 16-part kit and an
embedded 16-lane sequencer on the parent track's grid; kits and patterns
persist with the project (`machinedrum.work`). T5–T8 keep the stock
inserts and DELAY; T1–T4's stock FX pass audio through, since payload B's
effect code holds the MD.

## What is in it

- **MACHINEDRUM** (repeat98) — the MD engines (TRX, EFM, P-I, GND), the
  kit and sequencer on the ColdFire side, the SRC SETUP pages (SYN 1–8,
  VOL, PAN, ENG), persistence in SRAM and on the card.
- The stock inserts FILTER, EQUALIZER, DJ EQ, PHASER, FLANGER, CHORUS,
  SPATIALIZER, COMB FILTER, COMPRESSOR, LO-FI and DELAY.

## Status

Every MD gate passes under the ColdFire port and octemu plays it. Not
flashed; the work packets are in
[MACHINEDRUM_WORKPACKETS.md](../../docs/proposals/MACHINEDRUM_WORKPACKETS.md).

## Build

```bash
make image REMIX=machinedrum BUILD=1 VERSION=MDRUM01
MDBURN=1 make image REMIX=machinedrum BUILD=1 VERSION=MDRUM01B   # BURN knob: core 1's spare cycles
```

The MD gates need `MD_EMU=<port>` and `OT_PROJECT=<project>`:
`make verify-md verify-md-transport verify-md-seq verify-md-kit`, and
`tools/verify/verify_md_ui.py`, `verify_md_c3.py`, `verify_md_persist.py`.
