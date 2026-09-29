#!/usr/bin/env python3
"""BusDelay's tempo snap against the tempo word the frame builder publishes.

The DSP derives the MIDI-clock period from stock's tempo24 (record halfword
31, `r6+$13`) with a 24-step `div` whose dividend must be loaded doubled:
the plain constant yields half the period, and every division M <= 12 then
snaps to the same TIME through 2M, so only a division with no double in the
table (16, 18, 24 clocks) can see it. An impulse through BusDelay on T1
(FDBK 0) is timed by its echo:

    120 BPM, TIME 43  -> 11,025 samples (1/8 = 12 clocks; ambiguous, kept as the base)
    200 BPM, TIME 51  -> 13,230 samples (1/4 = 24 clocks; a halved period leaves it free at 13,120)
     96.5 BPM, TIME 43 -> 11,072 samples (no division within free/16: free-running)
    120 BPM, TIME 86  -> 22,050 samples (1/4 -- past the old 16K line; the 32K lines, 15 Sep 2026)
    120 BPM, TIME 115 -> 29,400 samples (1/2T = 32 clocks, a division the 16K line never held)

TIME is 64 + knob*256 samples (was *128 until the 32K lines).

Builds the remix's image to a private copy (the selftest leaves whichever
remix it built last at out/mainos_bus.bin) and renders it through rig_render
(both cores). Skips a remix without BusDelay.
"""
import os, pathlib, shutil, subprocess, sys, wave

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path)
from remix import registry  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "out/tempoverify"
IMPULSE_AT = 4410
CASES = ((120.0, 43, 11025), (200.0, 51, 13230), (96.5, 43, 11072), (120.0, 86, 22050), (120.0, 115, 29400))


def impulse(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 44100
    frames = bytearray()
    for i in range(n):
        frames += (4000000 if i == IMPULSE_AT else 0).to_bytes(3, "little", signed=True) * 2
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2); w.setsampwidth(3); w.setframerate(44100); w.writeframes(bytes(frames))


def echo_spacing(path):
    w = wave.open(str(path)); n = w.getnframes(); raw = w.readframes(n)
    L = [int.from_bytes(raw[i * 6:i * 6 + 3], "little", signed=True) for i in range(n)]
    peaks = [i for i in range(1, n - 1) if abs(L[i]) > 200000 and abs(L[i]) >= abs(L[i - 1]) and abs(L[i]) >= abs(L[i + 1])]
    starts = []
    for p in peaks:
        if not starts or p - starts[-1] > 50:
            starts.append(p)
    return starts[1] - starts[0] if len(starts) >= 2 else None


def main():
    remix = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("REMIX")
    if "DELAY SERVER" not in registry.remix(remix).modules:
        print(f"  [ -- ] verify_tempo: {remix} carries no BusDelay")
        return 0
    OUT.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, REMIX=remix, XBUS="1", SPEC="1"); env.setdefault("BUILD", "0")
    r = subprocess.run([sys.executable, str(ROOT / "tools/build/build_bus.py")], env=env,
                       capture_output=True, text=True, cwd=ROOT)
    if r.returncode:
        sys.exit(f"verify_tempo: building {remix} failed:\n{(r.stdout + r.stderr)[-1500:]}")
    image = OUT / "image.bin"; shutil.copy2(ROOT / "out/mainos_bus.bin", image)
    stems = OUT / "stems"; impulse(stems / "T1.wav")
    fails = 0
    for tempo, knob, want in CASES:
        out = OUT / f"t{tempo:g}_k{knob}"
        cmd = [sys.executable, str(ROOT / "tools/harness/rig_render.py"), "--image", str(image),
               "--remix", remix, "--tracks", "T1=D", "--set", "T1:DEL=127", "--set", f"T1:TIME={knob}",
               "--set", "T1:FDBK=0", "--set", "T1:WET=127", "--set", "T1:PING=0", "--stems", str(stems),
               "--tail", "0", "--tempo", str(tempo), "--mixer", "off", "--amp", "1.0", "--out", str(out)]
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        if r.returncode:
            sys.exit(f"verify_tempo: rig_render failed:\n{r.stdout[-1500:]}{r.stderr[-1500:]}")
        got = echo_spacing(out / "T1.wav")
        ok = got is not None and abs(got - want) <= 1      # the engine's own read is +-1 sample
        fails += 0 if ok else 1
        print(f"  [{'ok' if ok else 'FAIL'}] {tempo:g} BPM, TIME {knob}: echo at {got} samples (want {want})")
    print(f"verify_tempo: {len(CASES)} cases, {fails} failure(s)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
