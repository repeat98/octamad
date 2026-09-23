# WP-A6 The cycle report at OT addresses: report

- **Status:** blocked
- **Branch and commit:** `machinedrum` @ `cab97a3`
- **Date:** 24 September 2026
- **Agent:** overnight Machinedrum handover

## What was done

The interpreter was rebuilt from the current replay source and run with
`MD_REPLAY_FETCH=1`, `--reloc`, and `--driver` at the proposed layout. The
fetch hook measures shared-window code and the relocated driver; private hot-P
fetches are deliberately outside that hook. The driver listing was also
counted for the low-memory swap, while the stereo mix remains a D1/WP-A5
decision.

## Acceptance check

```text
$ MD_REPLAY_FETCH=1 out/md_reference_interp/md_replay <capture> --reloc --driver
cap4/c01_16  fetch: mean 1074.1; worst 1142.6 cycles/sample; 907.2 shared words at worst
cap4/c10      fetch: mean 326.3;  worst 333.0;  207.5 shared words
cap4/c10_3    fetch: mean 498.5;  worst 518.0;  348.0 shared words
cap4/c1d_16   fetch: mean 1365.5; worst 1439.8; 617.4 shared words
cap4/c37_16   fetch: mean 1209.6; worst 1307.6; 545.0 shared words
cap4/c47_2    fetch: mean 1388.5; worst 1391.1; 533.4 shared words
cap5/c10_16   fetch: mean 1309.1; worst 1346.0; 995.5 shared words
cap5/c20_16   fetch: mean 1666.3; worst 1683.3; 373.4 shared words
cap5/c24_16   fetch: mean 1256.9; worst 1515.5; 609.4 shared words
cap5/c30_16   fetch: mean 1064.4; worst 1670.5; 373.0 shared words
cap5/c42_16   fetch: mean 1462.1; worst 1498.1; 575.0 shared words
cap5/c40_16   rc=139; invalid DSP memory reads; no fetch summary
```

The full command output also reports the relocated driver at `P:0x3fe00` and
the output comparison counts. The c40 failure reproduced on a retry. The
adjusted worst successful row is c10_16 at *inferred* `1,346.0 + 995.5 =
2,341.5` cycles/sample before the stereo mix.

## Measured

- ✅ The eleven completed runs and their adjusted rows are recorded in
  section 12 of `MACHINEDRUM_MACHINE.md`.
- ✅ `md_driver.py` disassembles 192 driver words at `P:0x3fe00`.
- ✅ The eight swap loops execute 1,224 word copies per 16-sample call and
  2,448 move instructions per call. At two calls per 32-sample period this
  is 4,896 move instructions per period; conversion to hardware cycles is
  *inferred*.
- ✅ `MD_REPLAY_FETCH=2` measured 201.4–201.9 driver words per sample on
  the eleven completed runs. Carrying the whole low image instead of the
  current 36 MD words adds 540 words in each direction per call; the prior
  `~70 cycles/sample` cost remains *estimated*.
- 🟡 The mix is not implemented. Option A reads 16 × 32 slot words and
  writes 16 interleaved stereo frames per 32-sample period; its cycle cost is
  unmeasured.
- All results are **pending the user's sign-off** on A2 and D1.

## Retracted

None. The c40 row is omitted rather than treating a stale ignored fetch file
as a new measurement.

## Open and handover

- **Blocked on WP-A5/D1:** the user must choose the stereo mix policy and the
  resulting measured cost before A6 can claim the `~2,500` acceptance limit.
- c40_16 needs an interpreter/debug follow-up after the A2 voice-home choice;
  its two `rc=139` runs reached invalid DSP memory reads before a fetch table.
- WP-A3 is independently blocked on the A2 voice-home choice. No result here
  qualifies a flash image or hardware behavior.
