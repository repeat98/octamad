# `tapeecho` — TAPE ECHO alone

Jannik Aßfalg's (repeat98) tape echo, in SPRING REV's slot.

## What is in it

- **TAPE ECHO** — a mono single-head tape echo with stereo dry output, running on the ColdFire in the stock delay's four-second per-track ring; the DSP side is a passthrough and allocates no buffer. Knobs TIME FDBK WOW AGE SYNC MIX. `modules/tapeecho/README.md`; the delay routine it sits in is `docs/firmware/COLDFIRE_DELAY.md`.

## Status

On the author's unit (OCTACLID4): six instances run; a seventh freezes the unit, open. `make verify` runs its CPU gate (`tools/verify/verify_tapeecho_cpu.py`); emulator instruction counts are not hardware cycles.

## Build

```bash
make image REMIX=tapeecho BUILD=1   # -> out/OCTATRACK_OCTABAM1.bin
```

[BUILDING.md](../../../docs/remixes/BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `make check REMIX=tapeecho` runs every gate first.
