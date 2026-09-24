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


## 24 September 2026 C3 correction, pending chooser acceptance

❌ The earlier raw type 6 representation above is retracted: stock page
writers index machine slots by type × 6, so T1 SRC edits reached T2 FLEX.
The Part now stores FLEX type 1 and an `MD\x01` signature in that track's
unused NEIGHBOR page-1 slot. The chooser, name, descriptor and dispatch
detours in `md_machine.s` use that signature; the raw-type pokes were
removed.

✅ `python3 tools/verify/verify_md_c3.py` under the specified port staged a
signed T1 Part, turned SRC A/B/F, and measured T1 FLEX
`[64,0,0,127,0,79] -> [73,5,0,127,0,82]` while T2 FLEX stayed
`[64,0,0,127,0,79]`. With the compiled editor, the same gate passed:
T1 `[64,64,0,0,0,0] -> [74,69,0,0,0,3]`, T2 unchanged. The stock
page-2 store is `Part + 0x1da + track*30 + type*6 + slot`
(`PARAM_PAGES.md` §5a/§6).

✅ Post-C3 `verify-md`, both gain probes, `verify-md-transport`
(33,513/33,513 blocks), `verify-md-seq`, and
`make check REMIX=machinedrum` passed with the required environment.
The first `make check` exposed a synthetic hidden-FX2 writer probe on the
internal MD dispatch id; `verify_hidden.py` now skips that inapplicable
probe. The complete rerun passed.

[ ] The new FLEX-plus-signature chooser selection and admission refusals
have not been retested through panel actions. Keep WP-C3 claimed until that
port walk passes. Nothing was flashed.
