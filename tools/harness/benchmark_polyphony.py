#!/usr/bin/env python3
"""Benchmark stock mono rendering against the four-voice polyphony prototype.

The fixture puts one looping FLEX sample on all eight audio tracks, with
TSTR OFF and a step-1 trig. The same card image runs under stock 1.40C and
the built polyphony-proto image. Results are ColdFire instructions per
16-sample frame; they are instruction counts, not hardware cycle counts.
"""

import argparse
import json
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools/verify"))
import toolpath  # noqa: E402,F401
import ot_project as otp  # noqa: E402
import verify_repitch as fixture  # noqa: E402

EMU = ROOT / "out/emu/ot_emu"
STOCK = ROOT / "out/raw/section_3_MAIN_OS.bin"
VOICE = 0x800049D8
VOICE_SIZE = 168
SETUP_OFF, VALUES_OFF, TRACK_STRIDE = 0x1E3, 0x033, 30


def all_tracks(project: pathlib.Path) -> None:
    """Extend verify_repitch's T1 FLEX fixture to all eight audio tracks."""
    def mut(data):
        for part in range(otp.NPARTS_ALL):
            base = otp.PART_BASE + part * otp.PART_STRIDE
            for track in range(8):
                data[base + otp.MTYPE_OFF + track] = 1              # FLEX
                data[base + 0x2D3 + track * 5 + 1] = 0             # slot 1
                setup = base + SETUP_OFF + track * TRACK_STRIDE + 6
                data[setup + fixture.LOOP_SLOT] = 1
                data[setup + fixture.TSTR_SLOT] = 0                 # OFF
                values = base + VALUES_OFF + track * TRACK_STRIDE + 6
                data[values + fixture.PTCH_SLOT] = 64               # neutral
                data[values + fixture.RATE_SLOT] = 127              # forward
        for track in range(8):
            data[otp.trac_off(0, track) + 7] |= 1                   # A01 step 1
    otp._bank_write(project, 1, mut, guard=False)


def symbol(elf: pathlib.Path, name: str) -> int:
    text = subprocess.check_output(["m68k-elf-nm", "-n", str(elf)], text=True)
    match = re.search(rf"^([0-9a-fA-F]+)\s+\w\s+{re.escape(name)}$", text, re.M)
    if not match:
        raise SystemExit(f"benchmark_polyphony: missing {name} in {elf}")
    return int(match.group(1), 16)


def run(label, image, card, frames, work, primed_at=None):
    voice_dump = work / f"{label}-voices.bin"
    dumps = f"{VOICE:#x},{VOICE_SIZE * 8}={voice_dump}"
    primed_dump = None
    if primed_at is not None:
        primed_dump = work / f"{label}-primed.bin"
        dumps += f";{primed_at:#x},8={primed_dump}"
    cmd = [str(EMU), "--image", str(image), "--card", str(card),
           "--set", "OCTABAM", "--project", "POLYBENCH", "--sequencer",
           "--internal-clock", "--frames", str(frames), "--load-ms", "20000",
           "--dsp", "--main-level", "64", "--mem-dump", dumps,
           "--audio-out", str(work / label)]
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    log = work / f"{label}.log"
    log.write_text(" ".join(cmd) + "\n" + result.stdout + result.stderr)
    if result.returncode or "run ended REACHED" not in result.stdout:
        raise SystemExit(f"benchmark_polyphony: {label} run failed; see {log}")
    match = re.search(r"cpu\s*:\s*(\d+) ColdFire instructions.*?\(([\d.]+) per frame", result.stdout)
    if not match:
        raise SystemExit(f"benchmark_polyphony: no CPU count in {log}")
    audio_match = re.search(r"audio out\s+:\s+(\S+), .*?transport start at frame (\d+)", result.stdout)
    if not audio_match:
        raise SystemExit(f"benchmark_polyphony: no audio output summary in {log}")
    voices = voice_dump.read_bytes()
    active = sum(voices[i * VOICE_SIZE] != 0 for i in range(8))
    primed = sum(v != 0 for v in primed_dump.read_bytes()) if primed_dump else None
    return {"instructions": int(match.group(1)), "per_frame": float(match.group(2)),
            "active_tracks": active, "primed_tracks": primed,
            "audio": str(pathlib.Path(audio_match.group(1)).relative_to(ROOT)),
            "transport_start": int(audio_match.group(2)), "log": str(log.relative_to(ROOT))}


def compare_audio(mono, four, frames):
    """Compare transport-aligned audio, allowing the port's per-lane ring
    phase to differ by at most two samples between separately booted runs."""
    a = fixture.read_wav24(ROOT / mono["audio"])
    b = fixture.read_wav24(ROOT / four["audio"])
    count = frames * 16
    rows = []
    for slot, (left, right) in enumerate(zip(a, b)):
        source = left[mono["transport_start"]:mono["transport_start"] + count]
        candidates = []
        for shift in (0, -1, 1, -2, 2):
            start = four["transport_start"] + shift
            target = right[start:start + count]
            diffs = [abs(x - y) for x, y in zip(source, target)]
            candidates.append((max(diffs, default=0), sum(d != 0 for d in diffs), shift))
        maximum, different, shift = min(candidates)
        rows.append({"slot": slot, "poly_shift_samples": shift,
                     "max_abs_difference": maximum, "different_samples": different})
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, help="source Octatrack project directory")
    parser.add_argument("--image", default="out/mainos_bus.bin", help="built polyphony image")
    parser.add_argument("--frames", type=int, default=1200)
    parser.add_argument("--work", default="out/polyphony-benchmark")
    args = parser.parse_args()
    work = pathlib.Path(args.work).resolve()
    work.mkdir(parents=True, exist_ok=True)
    project = work / "project"
    wav = work / "POLY_440_120.wav"
    fixture.make_loop(wav)
    fixture.build_project(pathlib.Path(args.project).expanduser().resolve(), project,
                          0, 0, 120.0, 64, 127, "flex")
    all_tracks(project)
    card = work / "card.img"
    tree = work / "tree"
    if tree.exists():
        shutil.rmtree(tree)
    stage = [sys.executable, str(ROOT / "tools/emu/ot_emu/stage_card.py"),
             str(project), "OCTABAM", "POLYBENCH", "--tree", str(tree),
             "--out", str(card), "--audio", f"{wav}:{fixture.SAMPLE_REL}"]
    subprocess.run(stage, cwd=ROOT, check=True)

    poly = pathlib.Path(args.image).resolve()
    if not EMU.is_file() or not STOCK.is_file() or not poly.is_file():
        raise SystemExit("benchmark_polyphony: build the emulator, raw OS, and polyphony image first")
    runtime_elf = ROOT / "out/platform/runtime/runtime.elf"
    primed_at = symbol(runtime_elf, "poly_primed")
    mono = run("mono", STOCK, card, args.frames, work)
    four = run("four-voice", poly, card, args.frames, work, primed_at)
    if mono["active_tracks"] != 8 or four["active_tracks"] != 8 or four["primed_tracks"] != 8:
        raise SystemExit(f"benchmark_polyphony: fixture did not sustain eight tracks: mono={mono}, poly={four}")
    audio = compare_audio(mono, four, args.frames)
    if any(row["max_abs_difference"] for row in audio):
        raise SystemExit(f"benchmark_polyphony: four-voice average differs from mono audio: {audio}")
    delta = four["per_frame"] - mono["per_frame"]
    ratio = four["per_frame"] / mono["per_frame"]
    result = {"frames": args.frames, "frame_samples": 16, "mono": mono,
              "four_voice": four, "delta_per_frame": delta, "ratio": ratio,
              "audio_comparison": audio,
              "interpretation": "ColdFire instruction count; not hardware cycles"}
    (work / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(f"mono       {mono['per_frame']:.0f} instructions / 16-sample frame")
    print(f"four-voice {four['per_frame']:.0f} instructions / 16-sample frame")
    print(f"delta      {delta:+.0f} ({ratio:.2f}x mono); 8/8 tracks active and primed")
    print("audio      exact after per-lane port ring alignment (shift at most 2 samples)")
    print(f"result     {work / 'result.json'}")


if __name__ == "__main__":
    main()
