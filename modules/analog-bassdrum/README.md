# Analog BD

One native Octatrack track machine with a stepped **MODEL: 808 / 909**
selector in SRC SETUP. Both original fixed-point synthesis engines run on
the DSP, upstream of stock AMP and both track FX slots. No recordings are
embedded. This is a development build, not yet qualified on hardware.

| Model / page | A | B | C | D | E | F |
|---|---|---|---|---|---|---|
| 808 SRC | PITCH | DECAY | TONE | ATK | SWEEP | SAT |
| 909 SRC | PITCH | DECAY | TUNE | ATK | TDEP | SAT |
| Both SRC SETUP | MODEL | ACCNT | LPF | LOW | HIGH | — |

Both models use the same Mackie desk stage and output LPF. SAT controls
drive; LOW/HIGH are neutral at 64. LPF is OFF at 0, 500 Hz at 1, **ORIG**
(~6.57 kHz) at 64, and **18 kHz at the new-assignment default of 127**.
Stored patches retain their bytes, including when changing MODEL. Volume
remains on stock AMP. Old patches with both desk bands at zero need them
raised to hear the source.

The 808 is calibrated against the user's 32 clean `_Orig.wav` recordings;
Tape/TapeSat, X/X2 and unlabeled special effects are excluded. Its body
starts near 49 Hz, with a falling pitch envelope and approximately
16–340 ms exponential decay times. ATK sets the transient, TONE shapes it,
and SWEEP controls the pitch excursion. See [DSP808.md](DSP808.md) for the
model, measurements and limits.

The user-approved 909 is calibrated against Drumazon 2 Init. PITCH maps
30–100 Hz, TUNE sets pitch-envelope duration, and TDEP sets its amount.
ATK controls the shaped pulse/noise transient. The release spans about
9–454 ms after an approximately 60 ms initial body stage. See
[DSP909.md](DSP909.md). The comparison patch is PITCH 64, DECAY 32,
TUNE 64, ATK 32, TDEP 64, SAT 0, ACCNT 100, LPF OFF, LOW/HIGH 64.
Selecting a model keeps the existing knobs rather than loading a preset.

## Native integration

The chooser and Part storage follow the measured Machinedrum registration
seams. Parts store FLEX plus `AB\x01` in unused NEIGHBOR page bytes. All eight
tracks can store independent patches; development admission remains **two
instances per Part**. Stock Part save/copy/reload carries the twelve bytes.
The model selector uses the stock stepped-control widget. Double-tapping an
Analog BD track opens SRC SETUP; ordinary tracks keep the stock sample picker.

ColdFire sends control records through the existing source transport; DSP
glue recognizes the signature and renders either engine into the stock
source audio block. Other FLEX tracks call their unmodified renderer. Each
model retains separate state. Both payloads use the already harvested
SPRING REV code region and private X tables/state. Both track FX slots are
available; SPRING REV is excluded from this standalone remix. Its shared
35-word DARK reverb routine is preserved, with stock/patched audio identity
checked on both cores. The optimized kick engines are also held to exact
pre-optimization audio and internal-state hashes.
MACHINEDRUM, SYNTH MACHINE and POLY still conflict with the registration
seams and require a shared registry before composition.

Current load evidence and remaining hardware qualification are in [CPU.md](CPU.md).
Generic DSP pressure acceptance is explicitly blocked until the pricer supports
source engines; the standalone and full-chain benchmarks remain required.

## Reproduce

```
python3 modules/analog-bassdrum/generate.py --check
python3 tools/harness/bd808.py --wav
python3 tools/harness/bd909.py --wav
OT_PROJECT=<stock-project> make check REMIX=analog-bassdrum
OT_PROJECT=<stock-project> AB_SAMPLE808=1 python3 tools/verify/verify_analog_bassdrum_port.py
```

Repeat the port checks with `AB_REVERSE=1` for the opposite core assignment.
WAVs, firmware and reference analysis remain under `out/`, never in commits.
The retained C engine and its gates are legacy development references;
they no longer synthesize admitted voices in the image. [CPU.md](CPU.md),
[SCHEMATIC.md](SCHEMATIC.md) and [REFERENCE.md](REFERENCE.md) retain the earlier
ColdFire research, not the current DSP algorithm specification.
