# RIG HOSTS

A ColdFire patch: a new part is born hosted. The part-defaults
initialiser (`0x40005638`, the routine that gives a new part FX1 = FILTER
and FX2 = DELAY on every track) is detoured three times: the FX2 default
load jumps to `righosts.s`, which writes FX1 = NONE and the FX2 id by
track (BusDelay on T1, BusVerb on T5, the stock DELAY, Echo Freeze, for
its beat repeat, on T8 the master, SEND on every other track); and each
track's FX2 page-1 and page-2 defaults come from that track's own
descriptor through the id table instead of the stock DELAY's. The ids
come from the manifests at build time.

With the engines hidden from the FX2 chooser and locked to their host
slot, this is what makes a project made on the unit host the bus without
a chooser row or a stamp. An older project keeps its stored ids: host it
with `python3 tools/hw/ot_project.py host <project>`.

## Measured

- Under the port (22 Sep 2026): loading a project name the card does not
  carry makes the firmware create one, and its live FX2 ids read
  6 9 9 9 7 9 9 8, FX1 0 x8; T1's page bytes are BusDelay's defaults,
  T5's BusVerb's, T8's the stock delay's.
- On the unit: image 52 (22 Sep 2026) ran the FX2 hosting with FX1 left
  at stock's FILTER default, which on that image was Spectrum's id with
  FILTER's page bytes ("muted and quiet and modulated" until re-selected);
  image 53 added the FX1 = NONE and page-defaults detours, measured under
  the port. Image 88 carried the current module, not exercised there.

## Open

- A project born on the unit under the current module.
