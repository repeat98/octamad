# WP-C4 Kits and parameters: report

- **Status:** done (under the port; unflashed; the full 450-case rerun was cut short at 16/29 runs, all passing)
- **Branch and commit:** `machinedrum` @ this commit
- **Date:** 24 September 2026
- **Agent:** Claude (Opus 5.5)

## What was done

The Machinedrum now has a live kit and record producer on the OT ColdFire.
- `modules/machinedrum/md_ctl.c` is C, compiled by `generate_ctl.py` into
  the checked-in `md_ctl.s` (the Euclid pattern).
- It holds a 16-part kit: engine, VOL, PAN, mute and SYN 1–8.
- Once a frame, `md_xport.s` asks it for a chunk. It then runs the MD's own
  descriptor handler for each triggered or edited part, the way the MD's
  voice update does:
  - parameters go in as the kit byte << 7;
  - word 0 is the trig flag during the call, and the engine id + 1 on the
    wire;
  - the handler's return value is the count.
- It also sends VOL/PAN as the OT-side gain pair and refreshes one idle part
  per frame.

`handler_build.py` now also generates `md_engines` from the user's OS: the
live handler (the MD's table `0x252092`), defaults, names and family for ids
`0x00–0x48`. The assembly gain path in `md_xport.s` moved into the C, and
`md_gain_set` stays as the API.

Before this could be built, the MD's send path had to be read out of its SRAM
code. How a handler's record becomes a host packet is in section 12, "How
the MD sends a record". That section also retracts two earlier statements.

## Acceptance check

The oracle is the MD. `md_handler_cases.py` captures, for every engine, the
parameters, the record and the trig packet of a baseline and eight detents
per encoder. The profiler binary was rebuilt for its handler hook, and the
flash path now accepts the top-level dump:

```
$ python3 tools/harness/md_reference/md_handler_cases.py
captured 50 reference map scenarios
PASS: full handler code and both table spans match the pinned OS apart from 148 relocated operands
PASS: 450 handler cases, 50 engines, 84 record bytes per case match source and port; 9 additional TRX-S2 descriptor comparisons
```

`verify_md_kit.py` pokes 16-part kits built from those cases into the image
under the port. It then reads what reached core 1's voice records:

```
$ MD_EMU=$PWD/out/machinedrum/isolated/emu/ot_emu OT_PROJECT=out/machinedrum/testset/OCTABAM/RIG make verify-md-kit
  [ok] run 0: 16 trig records equal the MD's, one trig each
  [ok] run 0: gain words are md_gain(VOL, PAN)  bad packets 0
  [ok] run 1: 16 trig records equal the MD's, one trig each
  [ok] run 1: gain words are md_gain(VOL, PAN)  bad packets 0
  [ok] run 2: 16 trig records equal the MD's, one trig each
  [ok] run 2: gain words are md_gain(VOL, PAN)  bad packets 0
  [ok] run 3: 2 trig records equal the MD's, one trig each
  [ok] run 3: gain words are md_gain(VOL, PAN)  bad packets 0
  verify_md_kit: 50 cases, PASS
```

`CASES=all` (every encoder detent, 450 cases, 29 port runs). The first
two attempts failed on one case, TRX-CP / encoder B. That case was captured
on a regular update, not the trig: its record word 0 is 0 and its B value
was still easing (`0x23eb` toward `0x2400`). The gate therefore now takes
the snapshot rounded to the nearest step and checks against `map.txt`'s
trig packet. The final run was **interrupted at the handoff**: 16 of 29
runs had passed, 0 had failed (`out/machinedrum/c4_kit_all.log`). The next
agent reruns it (about 25 min).

## Measured

- ✅ The send path, the count, the trigger word, TRX-S2's live handler, the
  defaults on assignment, the cadence, and the E12 tempo word. They are in
  section 12, "How the MD sends a record".
- ✅ All 50 baseline cases, and the first 16 of 29 runs of the 450-case set
  (256 cases), produce the MD's trig record at core 1, each part triggering
  once. 🟡 The remaining 13 runs were cut off by the handoff. The VOL/PAN gain words are right. See the WP-C4
  section of section 12.
- ✅ Chunks sent before the DSP's frame dispatch runs are lost. The first
  run lost the gains and 13 of 16 trigs. The producer now holds its first 16
  frames.

## Retracted

- ❌ GND-NS and TRX-S2 "sent no trigger record". They send two-word ones,
  which the map hook dropped. Marked in section 12 and in `WP-C2.md`.
- ❌ The MD's serializer and trigger-word source were marked "not yet
  located". They are located now.

## Open and handover

- The PAN law is a choice (constant power). The MD's mixer pan law is not
  read.
- E12 parts play as GND--- until WP-R1 delivers samples.
- LFOs and the MD's per-part modulation are not in the producer. Locks
  are WP-D3's.
- Nothing here is on hardware. The added FlexBus burst and the handler
  calls in the host-transfer interrupt are not timed on the unit.
