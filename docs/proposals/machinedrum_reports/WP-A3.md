# WP-A3 Layout-driven relocation and driver: report

- **Status:** blocked
- **Branch and commit:** `machinedrum` @ `cab97a3`
- **Date:** 24 September 2026
- **Agent:** overnight Machinedrum handover

## What was done

`md_relocate.py` and `md_driver.py` now consume `modules/machinedrum/layout.py`:
the source spans land at `P:0x38000` and `P:0x30000`, hot units at `P:0x1000`,
loop/scratch storage at the proposed Y addresses, and the driver at
`P:0x3fe00`. The driver now loads the proposed `X/Y:0x3400` voice home through
`r6`; the relocator copies those records and translates host writes.

## Acceptance check

The layout check passed, but the actual proposed voice-home gate did not.
The earlier passing gate was run before the driver stopped using the replay
placeholder `0x800`, so it is retracted as an A2 qualification.

```text
$ python3 modules/machinedrum/layout.py
PASS: 12 MD allocations are internally non-overlapping
PASS: source budgets fit with max_pi_voices=6
REVIEW: 8 stock conflicts remain explicitly listed

$ full twelve-kit gate, with voice home X/Y:0x3400
cap4/c01_16  33513/0 -> 22526/10987 (first difference at block 2272)
cap4/c10      33513/0 -> 32262/1251 (first difference at block 2432)
cap4/c10_3    33508/0 -> 32257/1251 (first difference at block 2400)
cap4/c1d_16   31555/1951 -> 19354/14152 (first difference at block 0)
cap4/c37_16   33504/0 -> 33504/0
cap4/c47_2    33415/87 -> 33415/87
cap5/c10_16   33506/0 -> 22296/11210 (first difference at block 2305)
cap5/c20_16   33499/0 -> 8253/25246 (first difference at block 0)
cap5/c24_16   33505/0 -> 23027/10478 (first difference at block 0)
cap5/c30_16   33513/0 -> 33474/39 (first difference at block 3919)
cap5/c40_16   full run did not finish before the diagnostic process was stopped
cap5/c42_16   full run did not finish before the diagnostic process was stopped
```

The two bounded checks for the remaining kits completed their first block
exactly (`1/1` each); they do not qualify a full run. The process was stopped
with its children after more than a minute without progress.

The second diagnostic attempt narrowed c10 and c01 with `MD_REPLAY_STATEDIFF`
and output diffs; it reproduced the same first differences after the record
base had moved to `0x3400`, rather than a relocation parser failure.

## Measured

- ✅ The relocator emits `100000–103dba → 38000`,
  `140000–148000 → 30000`, `140–142 → 0c00–0c02`, and X/Y voice-record
  copies `0x800–0xc00 → 0x3400–0x3800`. The driver assembles 192 words at
  `P:0x3fe00`.
- ✅ c37_16 remains `33504/0`, and c47_2 remains `33415/87`, under the
  proposed voice home.
- ❌ c01_16, c10, c10_3, c1d_16, c10_16, c20_16, c24_16, and c30_16 fail the
  twelve-kit acceptance counts as shown above. This retracts the previous
  report’s “10 unchanged kits” claim: that result used voice base `0x800`.
- ✅ The diagnostic `MD_REPLAY_STATEDIFF=1` on relocated c10 begins with the
  expected pre-write record difference at block 2272 and ends at
  `32262 identical, 1251 differ`; it does not silently use the old voice
  block.
- All new A3 evidence is in section 12 of `MACHINEDRUM_MACHINE.md` and is
  **pending the user’s sign-off**.

## Retracted

- ❌ The prior WP-A3 report and section-12 entry said the twelve-kit gate
  passed at the proposed addresses. That was true only for the legacy
  `0x800` voice base and is corrected above.

## Open and handover

- **Blocked after two honest diagnostic attempts:** the user must choose the
  A2 voice-home policy: `A_move_base_fx1`, `B_swap_pi_x_words`, or
  `C_batch_overwrite_curve_table`. Once chosen, rerun the full twelve-kit
  gate at that address policy.
- The shared-window ownership conflicts and six P-I-voice cap also remain
  user decisions. No alternate layout was selected overnight.
- WP-A4’s independent relocated-init check passes the proposed six-voice
  initialized spans, but it is review-only while this A3 gate is blocked.
