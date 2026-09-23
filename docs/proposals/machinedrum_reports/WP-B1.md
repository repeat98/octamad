# WP-B1 Module and remix skeleton: report

- **Status:** review
- **Branch and commit:** `machinedrum` @ `f383ecc`
- **Date:** 24 September 2026
- **Agent:** overnight Machinedrum handover

## What was done

Added `modules/machinedrum/manifest.py`, its README, and
`remixes/machinedrum.py`. The manifest is a no-byte `CF_PATCH` skeleton whose
plain resource declaration is derived from `layout.py`: the payload-A donor
span and the proposed shared allocations. The remix omits the bus servers and
SEND, keeps the non-reverb stock inserts plus DELAY, and uses the no-bus
`NONE` fallback; WP-B2 will connect the user's update to the build.

## Acceptance check

```text
$ make modules
machinedrum  cf_patch   [MACHINEDRUM]
  Native Machinedrum core-0 machine skeleton: payload-A donor and shared-window ownership from the proposed layout.
machinedrum  Machinedrum core-0 skeleton: no bus servers, stock inserts, and the proposed payload-A native-machine envelope.
  modules: MACHINEDRUM, FILTER, EQUALIZER, DJ EQ, PHASER, FLANGER, CHORUS, SPATIALIZER, COMB FILTER, COMPRESSOR, LO-FI, DELAY
  unimplemented ids fall back to: NONE

$ make bus REMIX=machinedrum
out/mainos_bus.bin: 1,112,560 bytes, 54 changed
```

`make remix REMIX=machinedrum` was also invoked, but the interactive target
exited with `the remixer needs a terminal` in this session. The control
`make check REMIX=bus` reached its existing dirtystate gate and then failed
all 24 `dsp_host` renders with `MmuHelper: shm_open failed, err 1`; the same
failure remained with `DSP56K_FORCE_INTERPRETER=ON` because that binary is
separate from the rebuilt replay interpreter.

## Measured

- ✅ The registry discovers `MACHINEDRUM` and the remix uses no bus
  participant. The `NONE` fallback is therefore accepted by the registry.
- ✅ `RESOURCE_CLAIMS` derives `P:0x1000–0x1aa4` as the donor span and
  `0x30000–0x40000` as the four contiguous shared allocations in `layout.py`.
  The manifest checks those declared spans for internal overlap.
- ✅ The non-interactive build and collision path passes. Since the manifest
  has no DSP source yet, the build report honestly says the donor region is
  `used 0` and keeps PLATE/SPRING/DARK stock.
- 🟡 The generic remixer ledger does not yet consume shared-window claims;
  B2 must turn this metadata into extraction/placement checks. No native
  Machinedrum bytes are present.
- All B1 results are **pending the user's sign-off** on the proposed layout.

## Retracted

None.

## Open and handover

- WP-B2 must connect `extraction.py` to the manifest and build-time placement,
  consume the donor span, and enforce the shared-window claims without
  copying firmware or samples into Git.
- The terminal-only remixer and the existing `dsp_host` `shm_open` failure
  remain environment limitations for this report; they are not treated as
  successful interactive or audio qualification.
