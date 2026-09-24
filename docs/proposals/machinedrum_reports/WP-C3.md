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

[x] `python3 tools/verify/verify_md_ui.py` drove SRC SETUP through
`tools/harness/md_panel.py`: FUNC+SRC, six DOWN presses and YES assigned
T1 as FLEX plus `MD\x01`, leaving T2's FLEX slot unchanged. The same
panel sequence refused a second MD on T2 and an MD on T5; T1's signature
survived both attempts. The script asserts the Part RAM bytes and every
panel event reached the port. Nothing was flashed.

The first REC+TRIG 5 editor probe found that the `md_trig_key` detour
overwrote two bytes of the following stock instruction. Execution ended
`ILLEGAL` at `0x40060cea`. Changing its `pad_to` from 10 to 8 leaves the
instruction intact; the same panel sequence then ran through all events
and recorded step 5. The six required regressions passed after the fix.

## 25 September 2026: the MD was never dispatched from a fresh assignment

❌ Retracted: "the frame builder substitutes internal DSP dispatch id `0x1e`
into that frame's FX2 setup word". `md_pack_fx2` (site `0x4000d146`) wrote
the id into a compact per-track copy at `0x80001b80`, which the DSP never
reads.

✅ Measured under the port and octemu:
- Each track's DSP record takes its FX2 id from the live byte
  `0x80000ecc + track` (stock `0x40004d38–0x40004d46`, word `+0x1c` of the
  track's 32-word block; the DSP copies it at `P:0x089–0x08c` of payload B).
  Stock refreshes that byte from the Part's FX2, `Part + 8 + track`
  (`0x4000938e`, `0x4000c41e`).
- The gates passed only because their project,
  `out/machinedrum/testset/OCTABAM/RIG`, stores `0x1e` as T1's FX2 in every
  Part, left over from the FX2-id gates. `ot_emu --watch-mem` traces T1's
  live `0x1e` to the card load (`pc 0x400165dc`).
- In octemu, on a card whose T1 FX2 is 0, core 1 never ran the glue
  (`X:0x36300` owner stayed `0xffffff`) and T1 was silent.

Fix: `md_pack_fx2` sets the MD track's live byte to `0x1e` every frame, and
gives a T1–T4 track that is no longer MD its Part's FX2 back. The Part's
FX2 is still never written. octemu then dispatches the MD (owner 0,
`0x6004` blocks applied, audio on T1).

✅ With `OT_PROJECT=out/machinedrum/testset_nofx/OCTABAM/RIG` (RIG with T1's
FX2 set to `0x08`), all of these pass: `verify-md`, `--gain-probe`,
`--gain-queue-probe`, `verify-md-transport`, `verify-md-seq`,
`verify_md_ui.py`, `verify_md_c3.py` and `make check REMIX=machinedrum`.
Use that project for MD gates from now on.

Open (octemu, same run):
- The record transport skips blocks: after 30 s, `gaps 0x9ffc` against
  `napply 0x6004`. Their sum is exactly `0x10000`, so this may be a single
  sequence jump rather than steady loss; not yet resolved. The audio has
  only a few hits.
- One octemu run froze the UI after boot, with the ColdFire still in its
  ISRs and main idle loop. It happened while the gates loaded the CPU and
  has not been reproduced.
- The MD assignment does not survive an octemu reboot (stock FLEX does).
