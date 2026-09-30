# `<name>` — <KEY>

One line: what the module does.

One paragraph: what you get on the unit, in plain words. For a port, the
author and a link to the upstream repository.

## Knobs

| page | slot | name | range | what it does |
|---|---|---|---|---|
| 1 | 0 | P0 | 0–127 | |

Omit this section for a module without knobs.

## Measured

✅ facts, each with how and when it was measured (the gate, the harness,
the port), and what would falsify it. 🟡 for inferred.

## On the unit

Hardware results: image, unit, date. "Not flashed" is a valid entry.

## Open

Things to find out.

## Gates

The `tools/verify/verify_*.py` gates and `make` targets that cover the
module (the manifest's `Gate(...)` entries). `tools/verify/verify_character.py`
is the pattern: predict the arithmetic exactly, drive both signs, refuse to
run if the id it resolves is the fallback rather than the effect.

Module-specific sections (design, memory, collisions, updating) follow as
further `##` sections after Gates.
