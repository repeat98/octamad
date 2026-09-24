# WP-C3 — machine registration

24 September 2026, branch `machinedrum`.

The Part now stores MACHINEDRUM as raw machine type 6. Type 5 is reserved
for POLY and its row refuses assignment in this remix. `md_machine.s`
extends both machine chooser paths, the project loader bound, the playback
descriptor lookup, and the live/configuration compatibility paths. Both
chooser commits admit only T1–T4 and at most one MD track in the active
Part. A rejected assignment retains the previous machine and shows
`MD: T1-T4, 1/PART`.

The ColdFire frame builder sees type 6 and substitutes internal DSP dispatch
id `0x1e` into that frame's FX2 setup word. It does not modify the Part's
FX2 choice. The remix hides MACHINEDRUM from the FX2 chooser, and the DSP
proof gain no longer depends on an FX2 parameter. This is a bridge through
the existing FX2 DSP dispatch; it is not yet a separate pre-FX machine
render point. On T1–T4, the stock effect code was donated to the MD payload,
so selecting other FX there does not yet provide the planned OT FX chain.

Headless Octemu walk, using the parent `../octemu` QEMU, the patched OS,
the local T1 sample/trig project and a fresh NVRAM:

| Gesture/check | Observed result |
|---|---|
| SRC SETUP, move to MACHINEDRUM, YES on T1 | Main page shows `MACHINEDRUM` |
| FX2 SETUP on the same track | MACHINEDRUM absent; `NONE` selected |
| PLAY on T1 | Repeating TRX-BD output, 4,556 peak in 16-bit main WAV, 224,562 nonzero samples |
| Try MACHINEDRUM on T2 in the same Part | `MD: T1-T4, 1/PART` popup; T2 stays STATIC |
| Try MACHINEDRUM on T5 | Refused; T5 stays STATIC |

The machine-only audio recording is
`out/machinedrum/octemu/machine_hidden_play.wav` (ignored), and the admission
walk/screenshot is under `out/machinedrum/octemu/`. `make bus
REMIX=machinedrum` and `make check REMIX=machinedrum` succeed. With the
isolated Octemu build against DSP pin `8ccdd843`, the project-specific
`make verify-md` gate passes: 348/348 TRX-BD periods are bit-identical and
694/694 post-FX2 readback blocks are non-silent. The shared parent Octemu
vendor checkout is still at the older `c051afad` pin and fails the known
WP-R4 parity test at period 25; the isolated pinned build is under ignored
`out/machinedrum/isolated/`.

This completes the registration packet's selection and admission exit. The
16-part kit editor, live record producer, internal sequencer, project
extension and hardware deadline remain later packets.
