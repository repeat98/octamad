# `bamsep26-burn` — the rig with all three meters

[`bamsep26`](bamsep26.md) unchanged, plus a **CF BURN** FX2 row. Built with
`make burn`, one image measures spare time on all three processors while
the stress project plays (`tools/harness/STRESS_PROJECT.md`):

| processor | knob | step |
|---|---|---|
| ColdFire | CF BURN's BURN / FINE, on T8's FX2 in place of its SEND | 640 / 10 instructions per frame |
| DSP core 1 (payload B, T1–T4) | SEND page-2 BURN on T2 | 24 cycles per sample |
| DSP core 0 (payload A, T5–T8) | SEND page-2 BURN on T6 | 24 cycles per sample |

The image differs from `bamsep26` in three ways:

- the SendBurn splice;
- one chooser row;
- the CF BURN hook, which costs 75 instructions per frame with its knobs
  at zero.

T8 gives its SEND to CF BURN, so the bus has one fewer client in these
measurements.

The procedure is in [modules/cfburn/README.md](../../modules/cfburn/README.md).

## Status

- **Under the port:** builds, and CF BURN is inert and exact
  (`verify_cfburn`).
- **On hardware:** not flashed.

## Build

```bash
make burn-image REMIX=bamsep26-burn BUILD=N
```
