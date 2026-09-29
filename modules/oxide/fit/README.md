# How OXIDE's model was measured

The research scripts as they ran on 28-29 Sep 2026, kept for provenance and
to refit (7.5 IPS, CCIR, another tape). They need the plugin installed
(`/Library/Audio/Plug-Ins/VST3/uaudio_oxide_tape.vst3`) and a Python with
`pedalboard numpy scipy`; nothing in the build or the gates imports them.
Each step writes a JSON/NPZ beside itself that later steps read; no
plugin output is checked in. `run.sh` runs a script and drops the plugin's
logger banner. `../design.py` holds the numbers the last step produced.

| step | script | writes | what it establishes |
|---|---|---|---|
| host | `oxide.py` | | loads the VST3; `tone()` / `tone_c()` fit the fundamental and harmonics of a steady sine by least squares (so a non-harmonic residual is reported, not hidden) |
| 1 | `phase1.py` | `phase1.json` | complex response 2 Hz-21.5 kHz at -30/-40 dBFS: linear there |
| 2 | `ir1.py` | `ir1.npz` | 2^19-sample impulse responses (noise reduction on: silence is exact zeros); agree with step 1 to 0.15 dB / 0.3 deg |
| 3 | `an3.py` | | the excess phase over minimum phase |
| 4 | `batch2.py` | `batch2.json` | gain and harmonics vs level at six frequencies; the 1 kHz curve is the split's reference |
| 5 | `batch5.py`, `fitsplit5.py` | `batch5.json`, `split5.json` | gain vs level at 64 frequencies, split into pre/post magnitude (static-curve assumption; 0.01-0.03 dB per frequency) |
| 6 | `batch6.py`, `split6.py` | `batch6.json`, `split6.json` | the split down to 5 Hz; H1/H3/H5 complex at 21 frequencies |
| 7 | `fiteq2.py` | `E1_4.json`, `E2_4.json` | the first magnitude-only model (still imported by `solve2.py`) |
| 8 | `fitlin.py`, `fitlin2.py`, `fitlin3.py` | `Hmeas.npy`, `stage1.json` | the total linear response: minimum-phase sections to 0.01 dB, then the sign-flipped 52.6 Hz and the 5.75 kHz all-passes (0.36 deg RMS) |
| 9 | `fitsplit6.py`, `place2.py` | `e1e2.json` | which side of the curve each part sits on, from the H3/H5 phases with the measured total removed |
| 10 | `fitE1.py` | `fitE1.json` | the full pre filter: split magnitude 0.04 dB, H3/H5 phase 0.5/0.3 deg |
| 11 | `compact.py` | `compactE1.json` | compact pre filters (the shipped one: first-order high-pass x first-order shelf) |
| 12 | `fo.py`, `fo2.py` | `fo.json` | compact post filters: low shelf + first-order high shelf + all-pass (+2 samples of latency in the fit only) |
| 13 | `final.py` | `final.json` | the curve solved by least squares on sines (`model2.py`, `solve3.py`), resampled to 33 points; the model scored against the plugin |

`lin.py` holds the digital sections (RBJ cookbook plus first-order and
all-pass forms); `sigs.py` the test signals (pink noise, a synthetic drum
bus, the two-tone).
