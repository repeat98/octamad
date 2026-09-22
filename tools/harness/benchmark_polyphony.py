#!/usr/bin/env python3
"""Benchmark stock mono playback against the selectable four-voice POLY machine.

Both fixtures put one looping sample on all eight audio tracks with TSTR OFF
and trigs on steps 1-4.  The stock run stores FLEX (type 1); the patched run
stores POLY (type 5).  By the fourth trig, POLY must have preserved three old
states per track while the stock primary carries the newest trigger.

Results are ColdFire instructions per 16-sample firmware frame.  They are
instruction counts, not hardware cycle/deadline measurements.
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
POSITION_OFF = 68
SETUP_OFF, VALUES_OFF, TRACK_STRIDE = 0x1E3, 0x033, 30


def configure_tracks(project: pathlib.Path, machine: int) -> None:
    """Put the selected sample machine and four early trigs on all tracks."""
    def mut(data):
        for part in range(otp.NPARTS_ALL):
            base = otp.PART_BASE + part * otp.PART_STRIDE
            for track in range(8):
                data[base + otp.MTYPE_OFF + track] = machine
                data[base + 0x2D3 + track * 5 + 1] = 0             # slot 1
                setup = base + SETUP_OFF + track * TRACK_STRIDE + 6
                data[setup + fixture.LOOP_SLOT] = 1
                data[setup + fixture.TSTR_SLOT] = 0                 # OFF
                values = base + VALUES_OFF + track * TRACK_STRIDE + 6
                data[values + fixture.PTCH_SLOT] = 64               # neutral
                data[values + fixture.RATE_SLOT] = 127              # forward
        for track in range(8):
            tr = otp.trac_off(0, track)
            data[tr:tr + 64] = bytes(64)                           # clear all masks
            data[tr + 7] = 0x0F                                   # only A01-A04
            data[tr + 0x59:tr + 0x59 + 64 * 32] = bytes([0xFF]) * (64 * 32)
            data[tr + 0x890:tr + 0x910] = bytes(0x80)              # no retrig/conditions
    otp._bank_write(project, 1, mut, guard=False)


def symbol(elf: pathlib.Path, name: str) -> int:
    text = subprocess.check_output(["m68k-elf-nm", "-n", str(elf)], text=True)
    match = re.search(rf"^([0-9a-fA-F]+)\s+\w\s+{re.escape(name)}$", text, re.M)
    if not match:
        raise SystemExit(f"benchmark_polyphony: missing {name} in {elf}")
    return int(match.group(1), 16)


def stage_fixture(source, work, label, machine, wav):
    project = work / f"project-{label}"
    fixture.build_project(source, project, 0, 0, 120.0, 64, 127, "flex")
    configure_tracks(project, machine)
    card = work / f"{label}.card.img"
    tree = work / f"tree-{label}"
    if tree.exists():
        shutil.rmtree(tree)
    stage = [sys.executable, str(ROOT / "tools/emu/ot_emu/stage_card.py"),
             str(project), "OCTABAM", "POLYBENCH", "--tree", str(tree),
             "--out", str(card), "--audio", f"{wav}:{fixture.SAMPLE_REL}"]
    subprocess.run(stage, cwd=ROOT, check=True)
    return card


def run(label, image, card, frames, work, extra_at=None, next_at=None):
    voice_dump = work / f"{label}-voices.bin"
    dumps = f"{VOICE:#x},{VOICE_SIZE * 8}={voice_dump}"
    extra_dump = next_dump = None
    if extra_at is not None:
        extra_dump = work / f"{label}-extra-voices.bin"
        next_dump = work / f"{label}-next.bin"
        dumps += f";{extra_at:#x},{VOICE_SIZE * 24}={extra_dump}"
        dumps += f";{next_at:#x},8={next_dump}"
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
    info = {"instructions": int(match.group(1)), "per_frame": float(match.group(2)),
            "active_primary": sum(voices[i * VOICE_SIZE] != 0 for i in range(8)),
            "audio": str(pathlib.Path(audio_match.group(1)).relative_to(ROOT)),
            "transport_start": int(audio_match.group(2)),
            "log": str(log.relative_to(ROOT))}
    if extra_dump:
        extra = extra_dump.read_bytes()
        info["active_extra"] = sum(extra[i * VOICE_SIZE] != 0 for i in range(24))
        info["next_slots"] = list(next_dump.read_bytes())
        diversity = []
        for track in range(8):
            positions = [int.from_bytes(voices[track * VOICE_SIZE + POSITION_OFF:
                                               track * VOICE_SIZE + POSITION_OFF + 4], "big")]
            for slot in range(3):
                base = (track * 3 + slot) * VOICE_SIZE + POSITION_OFF
                positions.append(int.from_bytes(extra[base:base + 4], "big"))
            diversity.append(len(set(positions)))
        info["distinct_positions_per_track"] = diversity
    return info


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, help="source Octatrack project directory")
    parser.add_argument("--image", default="out/mainos_bus.bin", help="built POLY image")
    parser.add_argument("--frames", type=int, default=1400)
    parser.add_argument("--work", default="out/polyphony-benchmark")
    args = parser.parse_args()
    work = pathlib.Path(args.work).resolve()
    work.mkdir(parents=True, exist_ok=True)
    wav = work / "POLY_440_120.wav"
    fixture.make_loop(wav)
    source = pathlib.Path(args.project).expanduser().resolve()
    mono_card = stage_fixture(source, work, "mono", 1, wav)
    poly_card = stage_fixture(source, work, "poly", 5, wav)

    poly = pathlib.Path(args.image).resolve()
    if not EMU.is_file() or not STOCK.is_file() or not poly.is_file():
        raise SystemExit("benchmark_polyphony: build the emulator, raw OS, and POLY image first")
    runtime_elf = ROOT / "out/platform/runtime/runtime.elf"
    extra_at = symbol(runtime_elf, "poly_extra_voices")
    next_at = symbol(runtime_elf, "poly_next")
    mono = run("mono", STOCK, mono_card, args.frames, work)
    four = run("four-voice", poly, poly_card, args.frames, work, extra_at, next_at)
    if mono["active_primary"] != 8 or four["active_primary"] != 8:
        raise SystemExit(f"benchmark_polyphony: primary voices not sustained: mono={mono}, poly={four}")
    if four["active_extra"] != 24 or any(n != 0 for n in four["next_slots"]):
        raise SystemExit(f"benchmark_polyphony: allocator did not retain 3 voices/track: {four}")
    if any(n < 4 for n in four["distinct_positions_per_track"]):
        raise SystemExit(f"benchmark_polyphony: voice positions did not diverge: {four}")

    delta = four["per_frame"] - mono["per_frame"]
    ratio = four["per_frame"] / mono["per_frame"]
    result = {"frames": args.frames, "frame_samples": 16, "trig_steps": [1, 2, 3, 4],
              "mono": mono, "four_voice": four, "delta_per_frame": delta,
              "ratio": ratio,
              "interpretation": "ColdFire instruction count; not hardware cycles"}
    (work / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(f"mono       {mono['per_frame']:.0f} instructions / 16-sample frame")
    print(f"four-voice {four['per_frame']:.0f} instructions / 16-sample frame")
    print(f"delta      {delta:+.0f} ({ratio:.2f}x mono)")
    print("allocator  8 primary + 24 extension voices active; four distinct positions/track")
    print(f"result     {work / 'result.json'}")


if __name__ == "__main__":
    main()
