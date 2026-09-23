# WP-A2 The layout: report

- **Status:** review
- **Branch and commit:** `machinedrum` @ `PENDING`
- **Date:** 23 September 2026
- **Agent:** overnight Machinedrum handover

## What was done

Added `modules/machinedrum/layout.py` as a plain dictionary plus a small
standalone overlap/capacity check. The selected proposal puts hot code in
the `P:0x1000–0x1aa3` donor span, puts the 1K voice X/Y block at `0x3400`,
uses the shared window for the sine, packed code/tables, six P-I buffers and
the driver, and uses private Y for the remaining Y-only table budget. The
driver scratch addresses are concrete: loop words at `Y:0x0c00`, `OUTBUF`
at `Y:0x0d00`, `MDSAVE` at `Y:0x0f20`, and `STASH` at `Y:0x1800`.

The file records every stock conflict found by WP-A1 and gives the three
voice-home choices: sacrifice the `0x3400` FX1 slot (selected), move the
P-I X words while leaving records at `0x800`, or save/restore the overlapping
read-only curve table during the batch. This packet remains in `review`:
the map is internally consistent, but stock-slot ownership and the maximum
P-I count are user decisions.

## Acceptance check

```
$ python3 modules/machinedrum/layout.py
PASS: 12 MD allocations are internally non-overlapping
PASS: source budgets fit with max_pi_voices=6
REVIEW: 8 stock conflicts remain explicitly listed
```

The check is intentionally split: it proves that the proposed MD ranges do
not overlap one another, while reporting stock ownership conflicts for the
user rather than pretending they are resolved.

## Twelve-kit gate

The required gate was run after adding the layout file. It exercised the
current legacy relocator/driver addresses (WP-A3 has not wired this dictionary
yet) and wrote only ignored `out/` artifacts. Baseline → relocated replay
results were:

```
cap4/c01_16  33513/0 -> 33513/0
cap4/c10      33513/0 -> 33513/0
cap4/c10_3    33508/0 -> 33508/0
cap4/c1d_16   31555/1951 -> 31554/1952
cap4/c37_16   33504/0 -> 33504/0
cap4/c47_2    33415/87 -> 33415/87
cap5/c10_16   33506/0 -> 33504/2
cap5/c20_16   33499/0 -> 33499/0
cap5/c24_16   33505/0 -> 33505/0
cap5/c30_16   33513/0 -> 33513/0
cap5/c40_16   33505/0 -> 33505/0
cap5/c42_16   33505/0 -> 33505/0
```

The replay command reports its left number as identical blocks and its right
number as differing blocks. Ten kits preserved their baseline result; the
current relocator/driver adds one differing block for `cap4/c1d_16` and two
for `cap5/c10_16`. This is a measured gate result, not a claim that the
proposed layout is qualified: A3 must rerun it after consuming `layout.py`.

## Measured

- ✅ The source budgets come from the measurements in
  `MACHINEDRUM_MACHINE.md` §12: engine code 15,621, hot donor 2,724,
  tables up to 28,061, sine 32,768, and P-I buffers 1,536 per voice.
- ✅ The current `md_driver.py` assembly is 192 words; the proposal reserves
  512 words for driver code. The size command was run against
  `out/md_profile/cap4/c10` and writes only to ignored `out/`.
- ✅ The Python check reports 12 internal allocations with no overlap.
- ✅ The required twelve-kit gate ran after the layout change; its exact
  baseline/relocated counts and the two changed profiles are recorded above.
- *inferred* The 40,960-word combined code/table budget (23,040 shared plus
  17,920 private Y) covers the 40,958-word maximum after moving the 2,724
  hot words, with two words of arithmetic headroom before future alignment.
- *inferred* Six P-I voices consume `6 × 1,536 = 9,216` shared words. A
  larger N, a different table packing, or a different stock-slot policy must
  be rechecked before implementation.
- All new layout evidence is in `MACHINEDRUM_MACHINE.md` §12 above.

## Retracted

None.

## Open and handover

- **User sign-off required:** accept or reject the selected voice home
  `X/Y:0x3400–0x37ff`, which forfeits the `0x3400–0x3fff` FX1 slot. The
  alternatives are `B_swap_pi_x_words` and `C_batch_overwrite_curve_table`
  in `layout.py`, with their measured/inferred costs beside them.
- **User sign-off required:** decide whether this MD-only core-0 image may
  relocate/surrender the shared-window stock reservations and both private
  T5/T6 FX2 slots used by the proposal. Core 1 remains stock in the stated
  project plan, so this is not a resolved compatibility claim.
- **User sign-off required:** accept the initial `max_pi_voices=6` budget or
  request a different N after a real packed-data measurement.
- WP-A3 must make the relocator and driver consume this dictionary, then
  rerun the twelve-kit gate at the chosen addresses. Every result from A3 and
  later packets that uses this map is pending the user's sign-off.
