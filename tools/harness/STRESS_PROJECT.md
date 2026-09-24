# Stress project for bamsep26

Generate a local Octatrack project with eight simultaneous FLEX tracks, three active LFOs per track, 15 locked parameter slots per step, and the rig's costly DSP paths:

```sh
python3 tools/harness/stress_project.py
```

The script copies only local `.work` and `.strd` files from `template_project/Drum Template TGM`, inserts a generated stereo loop, sets 120 BPM, and writes `out/stress-project`. It refuses to overwrite an existing output. Use `--source` for another locally saved Octatrack project and `--out` for a new destination. No project file or stock firmware is committed.

Bank A is the test bank. A01 has 16 locked trigs on each track, A02 has 32, A03 has 64, and A04 has 16 trigs plus 48 trigless lock steps per track. Each pattern selects its matching Part, so switching A01–A04 also changes Modulation, Spectrum, Character, BusDelay, and BusVerb modes. Other banks are cleared of inherited trigs and locks. All bank Parts, including saved mirrors, carry the same eight-track rig layout. T1 hosts BusDelay, T5 hosts BusVerb, and T5–T8 run four Character instances beside the reverb.

The generator reads every written bank back and checks effect IDs, FLEX types, LFO depths, pattern-to-Part mapping, trig/lock counts, and checksums. The generated `STRESS_README.txt` records counts and the audio hash.

For a local playback check, create `out/stress-run`, stage the card there, and run the port:

```sh
mkdir -p out/stress-run
python3 tools/emu/ot_emu/stage_card.py out/stress-project OCTABAM STRESS \
  --tree out/stress-run/card-tree --out out/stress-run/card.img \
  --audio out/stress-project/AUDIO/STRESS_LOOP.wav:AUDIO/STRESS_LOOP.wav
out/emu/ot_emu --image out/mainos_bus.bin --card out/stress-run/card.img \
  --set OCTABAM --project STRESS --sequencer --internal-clock \
  --frames 2500 --load-ms 20000 --dsp --main-level 64 \
  --audio-out out/stress-run/smoke
```

Check for `run ended REACHED` and nonzero audio. On hardware, copy the generated `.work` and `.strd` files into a project directory under your set, and copy the generated `AUDIO` folder to the set root so `../AUDIO/STRESS_LOOP.wav` resolves. Select A01, then switch through A02–A04. Lower monitoring level before starting: eight tracks and the bus effects may sum loudly. Watch for a freeze, dropout, incorrect Part/effect mode, or a parameter that stops following locks or LFOs. Repeat after each feature change and compare with the same image and project. The emulator run checks loading and short playback; a long hardware soak and manual pattern switching remain separate checks.




