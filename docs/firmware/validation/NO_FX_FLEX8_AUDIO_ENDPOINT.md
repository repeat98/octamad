# No-effects FLEX-8 audio endpoint (23 September 2026)

The 5,600-frame stock/candidate/stock run in
`out/optimization/aba-no-fx-flex8-5600/` used card SHA-256
`772ea561eecfe78021c02c14024a0b30f4a66ab422668076369deb9800b4cee4`,
stock image `164f31224bf61181e3f50e7dec40df9afcae5b16dbf6e4c0d0cc5e986af0a84e`,
candidate image `4d4c2b854278643598daf8c2a0c09feaffc6f8a6dfb4831d187e902b0087f740`,
and emulator `4fdcca2094ff91107e22042e91da985a0e8c179291512913e7ba4235ec9be749`.
`result.json` holds the full commands and source hashes. This is a no-effects
fixture, separate from the inherited seven-delay pilot card.

**Strict whole-WAV equivalence: FAIL.** Stock A and stock B reproduce the
same audio and CPU PC table. Candidate executes 0.613% fewer ColdFire
instructions, but its eight-channel 24-bit WAV has 986,968 sample frames
versus stock's 986,969. The entire common 986,968-frame PCM prefix is
byte-identical; there is no differing sample or channel within it. Stock's
sole extra final frame is nonzero, so the full files must not be called equal.
All runs report transport start at ESAI frame 897370 and 5,600 delivered CPU
frames. Thus stock captured 89,599 post-start samples and candidate 89,598,
both short of `5600 * 16 = 89,600` at the stop boundary.

**Common fixed window: PASS as a separate observation.** The first 5,599
complete 16-sample frames after transport start are present in both captures:
89,584 samples per channel, 2,150,016 interleaved PCM bytes. All three SHA-256 hashes
are `16e61c5cab92d1f19797e00b6608d759c68526e225dceb9949cc1fc45658c7cd`.
This observation does not change the strict gate's FAIL result.

The emulator's `Rtos::runInternal` checks a CPU-frame target; the frame count
increments when the ColdFire acknowledges the frame interrupt. `DspPair`
appends an ESAI TX sample when its independent DSP execution reaches that
sample edge. CPU instructions and idle skips advance DSP execution by
different paths. Stopping at the same CPU interrupt count can therefore leave
the capture one DSP sample apart. This mechanism explains the observed
endpoint length difference without requiring an arithmetic mismatch, but the
run does not prove all internal state equal. There is no current CLI mode that
stops at a fixed output-sample count.

PC accounting also reflects changed scheduling: the first per-frame difference
appears at CPU frame 33. Inclusive analysis instructions fall from 29,418,405
to 28,086,147, a saving of 1,332,258; the whole run saves 1,332,256.
Exclusive renderer and delay totals match exactly, but 89 PC addresses outside
the analysis scope have redistributed counts (absolute delta 1,904). The net
two-instruction difference outside analysis is not full state equivalence.

## Overshoot and fixed 5,600-frame audio gate

A separate stock/candidate/stock run at
`out/optimization/aba-no-fx-flex8-overshoot-5602/` deliberately let the
CPU run to 5,602 frame acknowledgements. All three captures start transport
at output sample 897370 and contain the **predeclared** first 5,600 complete
post-start frames, 89,600 samples per channel. The explicit checker
`python3 tools/harness/verify_audio_window.py --run
out/optimization/aba-no-fx-flex8-overshoot-5602 --frames 5600` passes:
all three non-silent, eight-channel 24-bit PCM windows are byte-identical
(SHA-256 `be483607340fa456c83ab40a08848e9a12de680f13bbc5c0b477849878997de2`).
Its three verifier tests pass. Stock A/B whole captures have 987001
samples, candidate 987000; therefore the benchmark's strict whole-file gate
still exits nonzero. The fixed-window PASS and full-file FAIL are both
retained; neither is renamed as the other.

This resolves the original capture shortfall for the selected audio interval
but does not prove state equivalence for every interrupt timing or project.
A future fixed-output-sample stop/capture mode would make the distinction
native in the emulator. CPU profiling must continue to use its separately
declared CPU-frame window.
