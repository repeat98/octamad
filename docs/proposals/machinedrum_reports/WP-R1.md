# WP-R1 E12 sample delivery: report

- **Status:** review
- **Branch and commit:** `machinedrum` @ `PENDING`
- **Date:** 2026-09-24
- **Agent:** Codex

## What was done

The E12 descriptor table at `P:0x103d7b` was decoded and cross-checked against
the sample block boundary. A temporary interpreter-only trace followed the
executed `x:(r3)+` reads into that block through the full `cap4/c37_16`
capture, measuring both the read rate and address order. Two delivery designs
are recorded; D4 remains for the user.

## Acceptance check

Both replay modes remain bit-identical on the E12-heavy capture after the
temporary trace was removed:

```
$ out/md_reference/md_replay out/md_profile/cap4/c37_16 2>&1 | grep -E '^(slot |blocks:)'
blocks: 33504 identical, 0 differ

$ out/md_reference_interp/md_replay out/md_profile/cap4/c37_16 2>&1 | grep -E '^(slot |blocks:)'
blocks: 33504 identical, 0 differ
```

The descriptor extraction was:

```
$ out/md_reference/md_dis out/md_profile/cap4/c37_16/snapshot.bin 103d7b-103dba | awk 'NR%3==1 {a=$3; addr=$1} NR%3==2 {print addr, a, $3}'
103d7b 103dba 0020f0
103d7e 104eba 001f3a
103d81 105edf 0016ea
103d84 106adc 00dfe8
103d87 10db58 002fd2
103d8a 10f3c9 0009d4
103d8d 10f93b 000ca4
103d90 110015 002b1a
103d93 11162a 007f14
103d96 11563c 00d43e
103d99 11c0e3 00cf54
103d9c 122915 0011fa
103d9f 12329a 00808e
103da2 127369 0008d2
103da5 12785a 001010
103da8 1280ea 003b84
103dab 129f34 001eee
103dae 12af33 002e8a
103db1 12c700 0036cc
103db4 12e2ee 00ab08
103db7 1338fa 003108
```

The full trace ran as follows; its temporary diagnostic and output are not
part of the source tree:

```
$ MD_REPLAY_FETCH=1 MD_REPLAY_SAMPLE_WATCH=1 out/md_reference_interp/md_replay out/md_profile/cap4/c37_16 > /private/tmp/md-r1-full.txt 2>&1
$ awk '$1 ~ /^(1038c2|1038c3|103bd3|103bd4|103bf3|103bf4)$/' out/md_profile/cap4/c37_16/fetch.txt
1038c3 1 331398
1038c2 1 331398
103bd4 1 264894
103bd3 1 264894
103bf4 1 94520
103bf3 1 94520
fetch: 2093 periods; per sample: mean 1032.1 cycles, 903.4 engine words fetched; worst 10 ms 1131.2 cycles with 995.8 words fetched (most words in any 10 ms: 995.8)
blocks: 33504 identical, 0 differ
```

## Measured

- ✅ The 21 descriptors are `[start word, length in samples, 0]` triples:

  | # | Start word | Length (samples) |
  |---:|---:|---:|
  | 1 | `0x103dba` | `0x20f0` |
  | 2 | `0x104eba` | `0x1f3a` |
  | 3 | `0x105edf` | `0x16ea` |
  | 4 | `0x106adc` | `0xdfe8` |
  | 5 | `0x10db58` | `0x2fd2` |
  | 6 | `0x10f3c9` | `0x9d4` |
  | 7 | `0x10f93b` | `0xca4` |
  | 8 | `0x110015` | `0x2b1a` |
  | 9 | `0x11162a` | `0x7f14` |
  | 10 | `0x11563c` | `0xd43e` |
  | 11 | `0x11c0e3` | `0xcf54` |
  | 12 | `0x122915` | `0x11fa` |
  | 13 | `0x12329a` | `0x808e` |
  | 14 | `0x127369` | `0x8d2` |
  | 15 | `0x12785a` | `0x1010` |
  | 16 | `0x1280ea` | `0x3b84` |
  | 17 | `0x129f34` | `0x1eee` |
  | 18 | `0x12af33` | `0x2e8a` |
  | 19 | `0x12c700` | `0x36cc` |
  | 20 | `0x12e2ee` | `0xab08` |
  | 21 | `0x1338fa` | `0x3108` |

  ✅ The lengths total `397,896` samples (`9.02 s` at 44.1 kHz); the
  corresponding packed sample block is `201,804` P words and ends at
  `0x135206`.
- ✅ The six observed sample-read instructions and full-capture counts were:

  | P address | Instruction | Reads |
  |---:|---|---:|
  | `0x1038c2` | `move x:(r3)+,a` | `331,398` |
  | `0x1038c3` | `move x:(r3)+,b` | `331,398` |
  | `0x103bd3` | `move x:(r3)+,a` | `264,894` |
  | `0x103bd4` | `move x:(r3)+,b` | `264,894` |
  | `0x103bf3` | `move x:(r3)+,a` | `94,520` |
  | `0x103bf4` | `move x:(r3)+,b` | `94,520` |

  ✅ The sum is `1,381,624` 24-bit P-word reads over `2,093` rendered
  periods. The trace's `R3` addresses ranged from `0x103dba` through
  `0x1351c1`, entirely inside the descriptor-defined sample block.
- ✅ Sample traffic was present in `1,952` periods (trace period tags
  `143–2094`). Reads per 32-sample period were `272`–`884`, with median
  `680` and mean `707.8` over active periods (`660.1` including the quiet
  opening). The maximum observed rate is `1,218,263` P words/s; active
  mean is `975,436` P words/s, approximately `2.93 MB/s` when packed as
  24-bit words.
- ✅ Of `1,379,672` within-period address deltas, `1,361,306` were `+1`
  (`98.67%`). There were `8,088` negative jumps and `10,278` other jumps
  between bursts. The reducer saw `20,318` sequential runs, with median
  and maximum length `68` words. The access pattern is sequential within
  bursts, with jumps at voice/sample boundaries.
- *inferred* A useful cache unit is therefore a 68-word sequential burst.
  The largest observed period contains `884 = 13 × 68` reads, so a cache
  needs at least 884 words before look-ahead, double-buffering, descriptor
  translation, and underrun margin. This is a working-set estimate, not a
  hardware cache qualification.
- ✅ These measurements and the design options below were added to section
  12 of `MACHINEDRUM_MACHINE.md`.

### D4 design options

1. **ColdFire SDRAM streaming ring.** Keep the full `201,804`-word asset in
   ColdFire SDRAM and feed a shared-window ring ahead of `R3`. The measured
   active demand is about `0.98M` packed 24-bit words/s (`2.93 MB/s`), with
   a measured peak of `1.22M` words/s (`3.65 MB/s`). This preserves the
   proposed layout, but the ColdFire/DSP DMA latency, ring size, and
   underrun behavior are unmeasured and require hardware or a bus model.
2. **Per-kit burst cache in the shared window.** Stage 68-word sequential
   bursts and refill them from SDRAM on boundary jumps. The observed
   maximum working set is at least 884 words before look-ahead. The A2
   proposal has no free shared-window words: `0x30000–0x3ffff` is fully
   allocated to the sine, code/tables, P-I buffers, and driver code. This
   option therefore costs a layout trade-off or a lower P-I/table budget;
   its refill latency is also unmeasured.

## Retracted

None. This packet makes the earlier asset-size and descriptor-boundary
measurements more operational; it does not establish the machine-to-sample
name mapping or hardware timing.

## Open and handover

- **D4 is for the user.** Choose the streaming ring or the shared-window
  burst cache, with the measured bandwidth and the proposed-layout cost
  above. Do not assign E12 engines until the delivery path is selected and
  its underrun behavior is tested.
- The E12 machine-to-sample mapping and listening check remain open. The
  next packet is WP-A3, and its result must be labelled pending the user's
  layout sign-off.
