# WP-A6 The cycle report at OT addresses: report

- **Status:** review (port measured 25 Sep 2026; hardware ceiling still open)
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


## 25 September 2026: the cost under the firmware's own dispatch

`tools/harness/md_cost.py` (the port, `testset_nofx` with T1 signed MD):
- a 16-part kit is poked into `md_kit` after the load;
- a pattern with every assigned lane on every step goes into
  `md_patterns[0]`;
- the sequencer runs at 300 BPM for 1,400 frames;
- the port's stopwatch times the glue's driver call (`jsr` at `P:0x360fb`
  → `gdone`). That is half of the sixteen slots a call and one call a
  frame; 1,397 calls in 1,400 frames.

The unit is executed DSP instructions; the port models no stall.

✅ Driver, instructions per sample:

| kit | mean | worst frame |
|---|---|---|
| default 8 TRX (slots 0–7) | 676 | 1,198 |
| 16 TRX | 1,073 | 1,145 |
| 16 EFM | 1,227 | 1,262 |
| mixed 16 (TRX, EFM, P-I) | 1,252 | 1,381 |
| 16 P-I | 1,400 | 1,462 |
| 16 × EFM-CB (the heaviest voice, WP-R5) | 1,534 | 1,571 |

✅ The glue around the driver, measured with 16 × EFM-CB, every lane on
every step:
- **The record packets** (`gmine` → `gnotrg`): 288 instructions on a plain
  frame, up to 3,239 on a frame carrying all sixteen trig records.
- **The mix and output copy** (`gdone` → `gcpylp`): 2,323 instructions on
  the frames that mix a 32-sample period, 36 on the others (76 a sample
  on average; statically 32 × (2 + 16 × 4 + 3) = 2,208 for the mix).

**The worst frame of the heaviest kit:** 25,136 + 3,239 + 2,407 = 30,782
instructions, about 1,924 a sample.

🟡 **In cycles.** The same port unit read BusVerb at 1,109 instructions
a sample where the hardware burn sweep measured about 1,650 cycles
(`CHIP.md` §2), a ratio of about 0.68. On that ratio:
- the heaviest kit's worst frame is about 2,830 cycles/sample;
- a 16-TRX kit's worst frame (18,327 + 3,239 + 2,407, about 1,498 a
  sample) is about 2,200;
- the default kit's is about 1,960.

Against core 1's measured usable ceiling of about 3,120 cycles/sample
(`CHIP.md` §2, all effect work on the core), a full MD fits in every
kit tried, with roughly 290 (16 × EFM-CB) to 1,100 (default) cycles left.
The MD's instruction mix is not BusVerb's, so the ratio is the weak
link; the earlier interpreter estimates in this report (1,074–1,683
cycles/sample for the voices of captured 16-part kits) are the same size.

❌ Retracted from the first run of the tool: windows that end at the
dispatcher's `P:0x303` (`1:302:303`, `1:3600d:303`). MD code passes
through that address too: pairs of 23 and 46 instructions, and "the last
calls cost 69". Only the glue-internal windows above are valid.

**Consequences:**
- **Stock FX back on T1–T4 (option 1)** has cycle room only as far as
  the kit allows. One stock FILTER costs about 192 cycles/sample on the
  unit, so four FILTERs (768) fit beside a TRX kit but not beside 16 P-I
  or 16 × EFM-CB. It would need a per-kit admission cap (WP-E3), on top
  of moving MD code out of the private P those effects need.
- **The driver renders slots 0–7 in one frame and 8–15 in the next.** A
  kit with its heavy voices all in 0–7 (the default kit) has a worst
  frame nearly twice its mean. Interleaving the halves would flatten
  that; it is a driver change, not done.
- **The hardware ceiling with the MD running is not measured.** It needs
  a burn control on core 1 in a flash image.
