# `lofi-amf-fix` — LOFI AMF FIX

Fixes stock LO-FI's AMF knob jumping the pitch backwards at some settings:
one DSP multiply, in both payloads. Ported from [bryantysinger/octa-bt-pt](https://github.com/bryantysinger/octa-bt-pt).
`Kind.CF_PATCH`: two DSP-word pokes, no cave, no menu, no FX2 id.

Stock LO-FI's AMF coefficient computation runs `mpysu x0,y0,a` (signed ×
unsigned) at DSP `P:0x01bef` (payload A) / `P:0x019af` (payload B) on two
operands that are both magnitudes; the correct op is `mpyuu`. His report:
"LO-FI's AMF knob currently jumps the pitch backward at certain values".

The rest of octa-bt-pt generates per-user parameter defaults (any knob of the
14 stock effects, the FX1/FX2 default effect) and is not ported: there is no
canonical value to port. Two fixed-but-opinionated pieces are also left out:
a FLEX/STATIC `TSTR: AUTO → OFF` default, and "FX1/FX2 default = NONE".

## Measured

Both words disassembled with `vendor/dsp56300/.../dsp56kDisassemble` against
the stock image:

```
001bef: mpysu   x0,y0,a   ; 01278d   (stock, both payloads)
001bef: mpyuu   x0,y0,a   ; 0127cd   (the fix)
```

Both addresses resolved with `tools/build/dsp_modmap.py` hold those stock
bytes.

Not reproduced here: his 128×128 (AMF × Fine) sweep with zero monotonicity
violations after the fix.

## On the unit

Not flashed.

## Open

- The addresses are fixed, not re-resolved per build. If a remix ever
  harvests LO-FI's code, each poke's `expect` refuses the build.

## Gates

`make check REMIX=lofi-amf-fix` passes; the module composes with
everything (it claims no free space).
