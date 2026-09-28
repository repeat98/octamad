# CF METER

A probe. It measures, on the unit, how long the ColdFire's frame interrupt
takes and how much time main's idle loop gets (with
[CF METER IDLE](../cfmeter-idle/README.md)), and prints the numbers as
audio on track 8. It is the instrument for pricing ColdFire voice engines
such as [SYNTH MACHINE](../synth/README.md): the synth renders inside the
frame interrupt.

## How it works

- **Clock.** DMA timer 3, `0xfc07c00c`. The firmware sets `DTMR3 =
  0x000b` at `0x400209c0` (enabled, internal bus clock, prescaler 1,
  reference `0xffffffff`) and timestamps with it at `0x4000169a`. At the
  132 MHz bus clock one count is 7.58 ns; slot 5 prints the frame period
  in counts, which checks that rate against 16 / 44,100 s.
- **Frame interrupt, entry.** Main installs vector `0x41` with `pea
  0x4000aad0` at `0x4001fbf8`; the build rewrites the operand to `m_isr`.
  `m_isr` stamps the entry, busy-waits BURN × 2 µs (BURN = T8's FX2
  page-1 slot 0, read from the live lane `0x80000a20`) while T8's live
  FX2 id (`0x80000ed3`) is CF METER's `0x0e`, and enters the stock
  handler.
- **Frame interrupt, exit.** Every exit of the stock handler runs its
  epilogue at `0x4000d9a6` (`moveml`, `lea`, `rte`); `m_tail` replaces it:
  duration = exit − entry into a sum, a count and a maximum, then the
  epilogue. USB AUDIO's producer (`0x4000d9a0`, the instruction before)
  is inside the measured span.
- **Publisher.** In `m_tail`, every 125 ms (16,500,000 counts): eight
  values into a table, the displayed slot k advanced. Every frame, while
  T8's live FX2 is CF METER: N_k
  into T8's FX2 page-2 lane bytes `+0x38/+0x39` (word `$c`) and 8192 into
  `+0x3a/+0x3b` (word `$d`). The copier `0x4000cae8` delivers them to the
  DSP record (`docs/firmware/PARAM_PAGES.md` §5c, §6).
- **Readout.** The DSP insert (`meter_out.asm`, FX2 id `0x0e`, 29 words)
  writes L = word `$c` / 2 and R = word `$d` / 2 as a square wave that
  flips sign every block, replacing the track's audio. N = 8192 ×
  rms(L) / rms(R), whatever the gain after the slot.

| k | N |
|---|---|
| 0 | 0 (sync) |
| 1 | 8192 (reference; L/R = 1) |
| 2 | idle counts / segment × 16384 (0 without CF METER IDLE) |
| 3 | frame interrupt, mean duration, counts / 4 |
| 4 | frame interrupt, longest in the segment, counts / 4 |
| 5 | frame period (segment / interrupts), counts / 4 |
| 6 | the idle loop's shortest step, counts |
| 7 | BURN, counts / 4 |

`tools/harness/cfmeter.py` decodes a capture (a WAV, T8 on USB channels
15/16 by default) or the port's `--block-dump`.

## Measured under the port (remix `cfmeter-port`, 27 Sep 2026)

`OCTABAM89_setgate` with T8 FX2 = CF METER, 12,000 frames,
`verify_set.py cfmeter-port`, decoded with `cfmeter.py --dump`:

| BURN | interrupt mean | longest | period |
|---|---|---|---|
| 20 | 193.6 µs | 193.8 µs | 362.8 µs |
| 0 | 153.6 µs | 153.8 µs | 362.8 µs |

The difference is 40.0 µs, BURN 20 × 2 µs. The port prices every
instruction at one step of its own clock, so its durations are not the
unit's; the run proves the chain (lane → DSP record → insert → read-back
→ decoder) and the BURN arithmetic.

## Not measured

- Every number on the unit.
- Whether DTIM3 runs at 132 MHz on the unit (slot 5 answers it).
- Interrupts shorter than the idle loop's threshold (2 × its shortest
  step + 8 counts) count as idle time.
