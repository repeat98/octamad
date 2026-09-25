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
- ✅ Resolved (octemu, not the remix): the record transport skipped one
  block in four. Two frames of every sixteen, the mailbox arrived with
  the halves of alternate 32-bit words swapped, so the glue saw seq 0 and
  skipped it. octemu's eDMA model swaps halfword pairs in any 32-byte
  minor loop sent to the DSP port with a 4-byte DSIZE, a rule tuned for
  the stock control block. That block always comes from SRAM
  (`0x80005460–0x8000565f`, logged); the MD mailbox streams from SDRAM
  and is 32 bytes per minor loop whenever a block is 64 halfwords. With
  the rule limited to SRAM sources (the isolated octemu build under
  `out/machinedrum/octemu/isolated/`, `ot-board.c`), a 30 s groove run
  takes `0xf6e0` blocks with 3 gaps, 0 refused and 0 slips, and the
  groove plays. Nothing in the image changed.
- One octemu run froze the UI after boot, with the ColdFire still in its
  ISRs and main idle loop. It happened while the gates loaded the CPU and
  has not been reproduced.
- ✅ Resolved 25 Sep 2026 (below): the MD assignment did not survive an
  octemu reboot (stock FLEX does).

## 25 September 2026: the MD assignment survives a reboot

✅ Measured in octemu (isolated build), writable card, same NVRAM across two
runs:
- stock FLEX chosen through SRC SETUP on T1 survives the reboot;
- MACHINEDRUM chosen the same way came back as the card's STATIC track
  (image `5f88711`);
- with the fix, T1 comes back as the MD (`SYNTH▸P01 TRX-BD`).

Cause, from the disassembly and the reboot: boot keeps the SRAM state only
if the Part validator `0x40002318` repairs nothing in any SRAM Part
(`0x400257a4`: each of the four working and four saved Parts; one repair
and the whole restore is dropped, the card's Parts load). The validator
clamps every machine's page bytes to the STOCK descriptors' ranges
(`0x400d301c`, `0x400d31ae`, ...): FLEX's are PTCH 4..124, LOOP 0..3,
SLIC/LEN/RATE 0..1, TSTR 0..3. An MD track's FLEX slots hold the MD page
(SYN 1–8, VOL, PAN, ENG: 0..127 each), so any MD track failed it.
NEIGHBOR's ranges are 0..127 on all twelve slots, so the signature passes.

Fix: `md_validate` (detour at the validator's entry, eight displaced
bytes) shows the validator FLEX's defaults in the MD track's twelve slot
bytes and puts the MD's bytes back afterwards; every other byte of the
Part is still checked and repaired as stock does. The same validator runs
from the card loader (`0x4008cea0`, result ignored: it only clamped) and
from a tail call at `0x40005a44`; the wrapper covers all three.

Breakpoints over octemu's gdbstub (`out/mdverify/bp/bplog.py`) confirm
the boot order the fix relies on: the validator on the bank's Parts, the
SRAM restore `0x40025770` (validator on the eight SRAM Parts, then
`0x4000fbb4`), then the project load `0x400905d4` with bank mask `0xfffe`
(every bank but the resident one), about 3 s later.

The kit itself still resets to the default kit on reboot: kits and
patterns are not persistent yet (WP-E1).

Gates, all passing on `testset_nofx`: `verify_md_ui.py` (now with ENG),
`verify_md_c3.py`, `verify-md`, `--gain-probe`, `--gain-queue-probe`,
`verify-md-transport`, `verify-md-seq`, `make check REMIX=machinedrum`.
