# <Module name>

One paragraph: what it is. (`modules/character/README.md` is this template
filled in.)

## Status

Measured vs inferred, with what would falsify each claim.

## Parameters

| slot | name | what it does |
|---|---|---|
| 0 | P0 | |

## Open

What is unresolved.

## Gates

How a reader reproduces the measurements, in order. `tools/verify/verify_character.py`
is the pattern: predict the arithmetic exactly, drive both signs, refuse to
run if the id it resolves is the fallback rather than the effect.
