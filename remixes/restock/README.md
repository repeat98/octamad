# `restock` — Restock

The fourteen stock FX2 effects: an octabam-built image that behaves like stock. For undoing a remix without reflashing the stock OS.

## What is in it

- the 14 stock FX2 effects, listed so the chooser is stock's.

## Status

Builds; the chooser matches stock's. Not flashed.

## Build

```bash
make image REMIX=restock BUILD=1     # -> out/OCTATRACK_OCTABAM1.bin
```

[BUILDING.md](../../docs/remixes/BUILDING.md) is the walk-through from a fresh machine to a flashed unit. `make check REMIX=restock` runs every gate first.
