# RIG HOSTS

A ColdFire patch: a new part is born hosted. The part-defaults
initialiser (`0x40005638`, the routine that gives a new part FX1 = FILTER
and FX2 = DELAY on every track) has its FX2 default load replaced by a jump
to `righosts.s`, which writes the id by track: BusDelay on T1, BusVerb on
T5, the stock DELAY (Echo Freeze, for its beat repeat) on T8 the master,
SEND on every other track. The ids come from the manifests at build
time.

With the engines hidden from the FX2 chooser and locked to their host
slot, this is what makes a project made on the unit host the bus without
a chooser row or a stamp. An older project keeps its stored ids: host it
with `python3 tools/hw/ot_project.py host <project>`.

## Measured

- Under the port (22 Sep 2026): loading a project name the card does not
  carry makes the firmware create one, and its live FX2 ids read
  6 9 9 9 7 9 9 8.

## Open

- Not yet run on the unit.
- FX1 stays stock's FILTER default (Spectrum's id, a bit-exact passthrough
  at its defaults).
