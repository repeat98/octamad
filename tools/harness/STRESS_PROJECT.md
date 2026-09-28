# Stress project for a remix

Generate a local Octatrack project with eight simultaneous FLEX tracks, three active LFOs per track, 15 locked parameter slots per step (14 on the tracks `verify_set` probes), and the remix's costly DSP paths:

```sh
python3 tools/harness/stress_project.py --remix bottleservice            # writes out/stress-project
python3 tools/harness/stress_project.py --remix miniverb --layout   # print the placement, write nothing
```

The script copies only local `.work` and `.strd` files from `template_project/Drum Template TGM`, inserts a generated stereo loop, sets 120 BPM, and writes `out/stress-project`. It refuses to overwrite an existing output. Use `--source` for another locally saved Octatrack project and `--out` for a new destination. No project file or stock firmware is committed.

The placement is derived from the selection (`layout`):

- each server on the first track of its core (payload B serves T1-4, A T5-8: T1 and T5);
- SEND on every other FX2 slot when the remix carries it; otherwise the remix's FX2 inserts round-robin, dearest first; otherwise NONE;
- per core, the FX1 combination with the most different modules that prices under the static wall beside that core's FX2, then the dearest such set (the pressure pricer's arithmetic, `tools/harness/pressure.py`).

Every knob sits at its module's dearest setting (`schema.Module.dear`; the defaults for a module without one), and a MODE select walks its positions with the Part and the track, so switching A01-A04 also changes engines. For bamsep26 on 27 Sep 2026: T1 Modulation + BusDelay, T2 Modulation + SEND, T3 Character + SEND, T4 Spectrum + SEND, T5 Modulation + BusVerb, T6 Modulation, T7 Character, T8 Spectrum, all + SEND. `STRESS_README.txt` in the output records the placement, counts and the audio hash.

Bank A is the test bank. A01 has 16 locked trigs on each track, A02 has 32, A03 has 64, and A04 has 16 trigs plus 48 trigless lock steps per track. Each pattern selects its matching Part. Other banks are cleared of inherited trigs and locks. All bank Parts, including saved mirrors, carry the same eight-track layout.

The generator reads every written bank back and checks effect IDs, FLEX types, LFO depths, pattern-to-Part mapping, trig/lock counts, and checksums.

FX2 slot 0 (DEL) on T2 and on every server's track has no lock or LFO: `verify_set` sends CC 40 there and reads back the value it sent. Those tracks' third LFO targets FX1 instead; all 24 LFOs remain active.

For a local playback check, create `out/stress-run`, stage the card there, and run the port:

```sh
mkdir -p out/stress-run
python3 tools/emu/ot_emu/stage_card.py out/stress-project OCTABAM STRESS \
  --tree out/stress-run/card-tree --out out/stress-run/card.img \
  --audio out/stress-project/AUDIO/STRESS_LOOP.wav:STRESS/AUDIO/STRESS_LOOP.wav
out/emu/ot_emu --image out/mainos_bus.bin --card out/stress-run/card.img \
  --set OCTABAM --project STRESS --sequencer --internal-clock \
  --frames 2500 --load-ms 90000 --dsp --main-level 64 \
  --audio-out out/stress-run/smoke
```

Check for `run ended REACHED` and nonzero audio. On hardware, copy the generated `.work` and `.strd` files into a project directory under your set, and keep the generated `AUDIO` folder inside that project so `AUDIO/STRESS_LOOP.wav` resolves. Select A01, then switch through A02-A04. Lower monitoring level before starting: eight tracks at their dearest settings sum loudly. Watch for a freeze, dropout, incorrect Part/effect mode, or a parameter that stops following locks or LFOs. Repeat after each feature change and compare with the same image and project. The emulator run checks loading and short playback; a long hardware soak and manual pattern switching remain separate checks.
