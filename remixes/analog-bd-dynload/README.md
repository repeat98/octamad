# analog-bd-dynload

Analog BD on all eight tracks, with all 14 stock effects kept on both menus.
No stock DSP effect is built in: the DSP dynamic loader (`DSP DYNLOAD STOCK`)
loads each one into its arena when a Part or a selection needs it.

**Not a flash candidate yet.** Port-only, work in progress (30 Sep 2026).

## Layout (per core, payload A shown; B is 0x240 lower)

| P range | words | what |
|---|---|---|
| 0x7d1..0x96f | 414 | shared stock routines the effects call (FILTER's library, two reverb helpers) |
| 0x96f..0x1a8f | 4,384 | the loader's table: 64 saved entries + a 4,320-word arena |
| 0x1a8f..0x1bd0 | 321 | the loader's receiver |
| 0x1bdb.. | 996 | Analog BD (reserve 1,028) |

## Measured

- `verify_stock_relocation`: all 13 stock DSP effects run sample-identically
  to stock from the lowest, a middle and the highest arena address on both
  cores, with the effect block filled with `illegal` under the shared copies
  (702 renders).
- The image builds; `scripts/refhash.sh check` is bit-identical on all 24
  cases, and the `analog-bassdrum` image and report are unchanged.
- It boots under the port: both receivers answer with their table size, no
  transport errors.

## Open, before any image

- Stock's boot and project load publish FILTER (the default FX1) on every
  track through unguarded paths, before anything is loaded; during a project
  load the pattern-request guard refuses and shows `DSP LOAD FAILED` twice.
- An effect published around the guards gets the dry stub's init; its real
  init must run once its code is bound (the dispatcher calls init only when
  a slot's id changes).
