# `lofi-amf-fix` — The LO-FI AMF fix alone

Two DSP words. No cave, no menu row.

## What is in it

- **LOFI AMF FIX** (Bryan T, [octa-bt-pt](https://github.com/bryantysinger/octa-bt-pt)) — stock LO-FI's AMF knob jumps the pitch backwards at some settings because its coefficient multiply is `mpysu` (signed × unsigned) where both operands are magnitudes; two DSP words become `mpyuu`.

## Status

Both words disassembled against stock (`mpysu x0,y0,a` → `mpyuu x0,y0,a` at P:0x01bef / P:0x019af). Upstream's 128×128 sweep (zero monotonicity violations) is his claim, not re-measured here. Not flashed.

## Build

```bash
make image REMIX=lofi-amf-fix BUILD=1     # -> out/OCTATRACK_OCTABAM1.bin
```

[BUILDING.md](../../../docs/remixes/BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `make check REMIX=lofi-amf-fix` runs every gate first.
