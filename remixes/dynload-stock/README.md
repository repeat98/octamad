# `dynload-stock` — the stock effects, each DSP effect loaded on demand

The tester image for DSP dynamic loading: the fourteen stock effects on both menus, exactly as
stock offers them, with no stock DSP effect built into the image. `DSP DYNLOAD STOCK` uploads each
effect into its arena when a selection, a Part or a project needs it. Nothing else is in it: it
should play and switch as stock does, and it frees the program space other remixes take from a
stock effect.

## Status

Port qualification in progress (30 Sep 2026): `verify_stock_relocation`, `verify_stock_load`
and `verify_stock_switch` (FX and Part switches while playing, against pristine 1.40C). Not on
hardware.
