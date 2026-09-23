# WP-R5 c47_2 default-kit cost: report

- **Status:** done
- **Branch and commit:** `machinedrum` @ `PENDING`
- **Date:** 2026-09-24
- **Agent:** Codex

## What was done

The existing interpreter replay was instrumented temporarily around each
voice render to accumulate cycles, engine words and instructions by slot and
current DSP-side engine value. The source was restored exactly and the clean
interpreter binary rebuilt after the measurement. The result is that slot 6
(track 7), default EFM-CB, is the heaviest untouched voice in `c47_2`.

## Acceptance check

The normal JIT replay remains at the capture's known slot-0 residual:

```
$ out/md_reference/md_replay out/md_profile/cap4/c47_2 2>&1 | grep -E '^(slot |blocks:)'
slot 0: 2007 identical, 87 differ
blocks: 33415 identical, 87 differ (first difference at block 864)
```

## Measured

The clean interpreter fetch summary was:

```
$ MD_REPLAY_FETCH=2 out/md_reference_interp/md_replay out/md_profile/cap4/c47_2 2>&1 | grep -E '^(fetch:|fetch hottest|fetch all|slot |blocks:)'
fetch: 2093 periods; per sample: mean 1212.1 cycles, 985.8 engine words fetched; worst 10 ms 1214.7 cycles with 987.7 words fetched (most words in any 10 ms: 987.7)
fetch hottest 256 words carry 38.2%
fetch hottest 512 words carry 64.2%
fetch hottest 1024 words carry 91.4%
fetch hottest 2048 words carry 96.6%
fetch hottest 2724 words carry 98.8%
fetch all 3694 words executed
slot 0: 2007 identical, 87 differ
blocks: 33415 identical, 87 differ (first difference at block 864)
```

The temporary slot probe used the same capture and interpreter with
`MD_REPLAY_FETCH=2 MD_REPLAY_SLOT_COST=1`. The table reports the stable
post-assignment totals; slot 0 and slot 1 are the two assigned voices, while
slots 2–15 remain the default kit.

| Track | DSP current | Catalog/SysEx engine | Renders | Mean cycles | Mean engine words |
|---:|---:|---|---:|---:|---:|
| 1 | `0x48` | P-I-CC (`0x47`, assigned) | 1,952 | 2,937.144 | 2,465.104 |
| 2 | `0x49` | P-I-HH (`0x48`, assigned) | 1,952 | 2,944.191 | 2,478.145 |
| 3 | `0x22` | EFM-SD (`0x21`) | 2,094 | 2,881 | 2,219 |
| 4 | `0x23` | EFM-XT (`0x22`) | 2,094 | 2,431 | 1,828 |
| 5 | `0x24` | EFM-CP (`0x23`) | 2,094 | 2,525 | 1,904 |
| 6 | `0x25` | EFM-RS (`0x24`) | 2,094 | 3,433 | 2,620 |
| 7 | `0x26` | **EFM-CB (`0x25`)** | 2,094 | **3,946** | **2,983** |
| 8 | `0x27` | EFM-HH (`0x26`) | 2,094 | 3,099 | 2,388 |
| 9 | `0x28` | EFM-CY (`0x27`) | 2,094 | 3,073 | 2,739 |
| 10 | `0x31` | E12-BD (`0x30`) | 2,094 | 1,392 | 1,254 |
| 11 | `0x32` | E12-SD (`0x31`) | 2,094 | 1,802 | 1,635 |
| 12 | `0x33` | E12-HT (`0x32`) | 2,094 | 1,512 | 1,355 |
| 13 | `0x34` | E12-LT (`0x33`) | 2,094 | 1,520 | 1,355 |
| 14 | `0x35` | E12-CP (`0x34`) | 2,094 | 1,512 | 1,355 |
| 15 | `0x36` | E12-RS (`0x35`) | 2,093 | 1,803 | 1,636 |
| 16 | `0x37` | E12-CB (`0x36`) | 2,093 | 1,512 | 1,355 |

✅ The table and the aggregate fetch summary were added to section 12 of
`MACHINEDRUM_MACHINE.md`. The engine-name translation is *inferred* from
the one-step DSP-current/catalog offset visible in the same capture and the
catalog in `out/machinedrum/os163/inventory.json`; no firmware or extracted
bytes were added.

## Retracted

None.

## Open and handover

- The packet's measurement is complete. It does not qualify the voice on
  hardware and does not select a layout or cycle-budget decision.
- The temporary diagnostic is gone; `md_replay.cpp` has no diff and the
  clean interpreter target was rebuilt.
- The next packet is WP-R2, measuring the TRX-S2 first-render residual.
