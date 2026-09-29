# RECORDER SPACING

A ColdFire code cave, no DSP code: a fixed-RLEN recording is exactly as long
as the gap to the next arm, derived from the current arm with no lane
lookahead and no stored state.

The length converter returns one constant length for a whole loop (82,687 at
128 BPM / RLEN 16) while the sequencer arms at `floor(k × period)` of an
exact fractional period, so consecutive arms are alternately 82,687 and
82,688 samples apart. Where they disagree the buffer's wrap splices two input
moments two samples apart: a −26 dB, ~1 ms scuff on alternate bars (measured
on hardware as OCTABAM82; `git show 3ceba41:docs/history/RTOS_FORK.md` §10.53, §10.56).

    q, r = divmod(RLEN × 15,876,000, tempo24)
    k    = arm / q                                 arm = 0x46c7fa84[track]
    L'   = q + floor((k+1)r/D) − floor(k·r/D)

RLEN is recovered from the stock length, so nothing is kept between passes.

Hook: `0x40006e0c` (the converter's last three instructions, replayed).
Reads: `0x80001814` (tempo24), `0x46c7fa84[track]`, `164(%sp)` (the track).
Writes: nothing but `d4`, the length.

## Measured

- `L'` equals the sequencer's own next spacing on 115,200 (tempo, RLEN, pass)
  triples, as the model and as an instruction-accurate simulation of the
  assembled bytes. Over all 11,208 (tempo, RLEN) pairs in 60.0–200.0: `q`
  equals the stock length at every integer-period tempo (the golden case
  cannot regress) and `|L' − L| ≤ 1` everywhere (the ±1 guard is kept).
- On hardware as OCTABAM83 (with FLEX SEEK BIND and FLEX SEEK BIND CTR):
  zero of 46 bars above 1.25× where 82 had 16; 128 BPM reads identical to
  the stock golden capture (`docs/firmware/RECORDER_CLICK.md`).

Untested: whether this cave alone suffices; the three have only been tested
stacked.

objdump prints every `divu.l` in the source as `remul` (0x4c4x is one
encoding family, named after the remainder form); with the extension word's
Dq and Dr fields equal, ColdFire writes the quotient. `spacing_cave.s` has
the references.

Assemble: `m68k-elf-as -mcpu=5475 -o spacing.o spacing_cave.s` and pin the
`.text` bytes in `manifest.py`; the build re-assembles and compares.
