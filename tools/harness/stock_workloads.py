#!/usr/bin/env python3
"""Build small, controlled stock playback cards and verify their activity.

Example:
  python3 tools/harness/stock_workloads.py --out out/optimization/workloads/run-1 --smoke

Only the pilot and idle/1/4/8 FLEX, TSTR OFF cases are validated here. The
manifest lists further workload families as pending rather than claiming them.
All generated assets live in ignored out/; existing projects are read-only.
"""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "tools/verify")]
import toolpath  # noqa: E402,F401
import ot_project as otp  # noqa: E402
import verify_repitch as repitch  # noqa: E402

PILOT = ROOT / "out/polyphony-benchmark-1100/mono.card.img"
PILOT_SHA256 = "0c2cfde19ad942503b4dcaf8e05ad9f256e37c908ced943e3c915bf889d10c94"
SOURCE = ROOT / "template_project/Drum Template TGM"
STOCK = ROOT / "out/raw/section_3_MAIN_OS.bin"
EMU = ROOT / "out/emu/ot_emu"
SAMPLE_REL = repitch.SAMPLE_REL
VOICE, VOICE_SIZE = 0x800049D8, 168
LIVE_FX1, LIVE_FX2 = 0x80000EC4, 0x80000ECC
SETUP_OFF, VALUES_OFF, STRIDE = repitch.SETUP_OFF, repitch.VALUES_OFF, repitch.STRIDE6
CASES = {"idle": 0, "flex-1": 1, "flex-4": 4, "flex-8": 8}
PENDING = [
    "STATIC: matched playback and ATA/DMA path evidence",
    "TSTR NORMAL/BEAT, stereo/mono, reverse and altered pitch/rate",
    "sample format, loop/slice boundaries and retrigs",
    "delay dry/wet, feedback/tails, freeze and live parameter/tempo changes",
    "LFOs, locks, scenes, Part/pattern changes and external MIDI events",
    "recorder/Pickup concurrency and the user's overload project",
    "30-second musical and 5-minute soak runs",
]


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as src:
        for block in iter(lambda: src.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def source_hashes(source: Path) -> dict[str, str]:
    """Record only project files actually copied by build_project."""
    files = sorted(p for p in source.iterdir() if p.is_file() and p.suffix.lower() in (".work", ".strd"))
    if not (source / "project.work").is_file() or not (source / "bank01.work").is_file():
        raise ValueError(f"source needs project.work and bank01.work: {source}")
    return {p.name: digest(p) for p in files}


def configure_bank(project: Path, active: int) -> None:
    """Set both stored/current Parts and every bank; only A01 has test trigs."""
    if active not in (0, 1, 4, 8):
        raise ValueError("active track count must be 0, 1, 4 or 8")

    def mutate(data: bytearray) -> None:
        for part in range(otp.NPARTS_ALL):
            base = otp.PART_BASE + part * otp.PART_STRIDE
            for track in range(8):
                data[base + otp.FX1_OFF + track] = 0  # stock NONE
                data[base + otp.FX2_OFF + track] = 0  # stock NONE
                data[base + otp.MTYPE_OFF + track] = 1  # FLEX
                data[base + 0x2D3 + track * 5 + 1] = 0  # FLEX slot 1
                data[base + 0x01B + 2 * track] = 64  # track level
                for off, stride in ((otp.P1_OFF, otp.TRACK_STRIDE), (otp.P2_OFF, otp.P2_STRIDE)):
                    at = base + off + track * stride
                    data[at:at + 12] = bytes(12)
                setup = base + SETUP_OFF + track * STRIDE + 6
                data[setup + repitch.LOOP_SLOT] = 1
                data[setup + repitch.TSTR_SLOT] = 0
                values = base + VALUES_OFF + track * STRIDE + 6
                data[values + repitch.PTCH_SLOT] = 64
                data[values + repitch.RATE_SLOT] = 127
        for track in range(8):
            tr = otp.trac_off(0, track)
            data[tr:tr + 64] = bytes(64)
            data[tr + 0x59:tr + 0x59 + 64 * 32] = bytes([0xFF]) * (64 * 32)
            data[tr + 0x890:tr + 0x910] = bytes(0x80)
            if track < active:
                data[tr + 7] = 0x0F  # A01 steps 1-4

    for bank in range(1, 17):
        otp._bank_write(project, bank, mutate, guard=False)


def verify_project(project: Path, active: int) -> None:
    for bank in range(1, 17):
        for suffix in ("work", "strd"):
            path = project / f"bank{bank:02d}.{suffix}"
            if not path.exists():
                continue
            data = path.read_bytes()
            assert int.from_bytes(data[-2:], "big") == sum(data[0x10:-2]) & 0xFFFF, path
            for part in range(otp.NPARTS_ALL):
                base = otp.PART_BASE + part * otp.PART_STRIDE
                assert data[base + otp.FX1_OFF:base + otp.FX1_OFF + 8] == bytes(8), (path, part, "FX1")
                assert data[base + otp.FX2_OFF:base + otp.FX2_OFF + 8] == bytes(8), (path, part, "FX2")
                assert data[base + otp.MTYPE_OFF:base + otp.MTYPE_OFF + 8] == bytes([1]) * 8, (path, part, "machine")
                for track in range(8):
                    setup = base + SETUP_OFF + track * STRIDE + 6
                    values = base + VALUES_OFF + track * STRIDE + 6
                    assert data[setup + repitch.TSTR_SLOT] == 0, (path, part, track, "TSTR")
                    assert data[values + repitch.PTCH_SLOT] == 64, (path, part, track, "pitch")
                    assert data[values + repitch.RATE_SLOT] == 127, (path, part, track, "rate")
            if bank == 1:
                for track in range(8):
                    tr = otp.trac_off(0, track)
                    assert data[tr:tr + 64] == bytes(7) + bytes([15 if track < active else 0]) + bytes(56), (path, track, "trigs")


def stage_case(source: Path, out: Path, name: str, active: int, sample: Path) -> dict:
    work = out / name
    work.mkdir(exist_ok=False)
    project = work / "project"
    repitch.build_project(source, project, 0, 0, 120.0, 64, 127, "flex")
    configure_bank(project, active)
    verify_project(project, active)
    card, tree = work / "card.img", work / "tree"
    command = [sys.executable, str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(project),
               "OCTABAM", name.upper().replace("-", ""), "--tree", str(tree),
               "--out", str(card), "--audio", f"{sample}:{SAMPLE_REL}"]
    subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)
    staged = list(tree.rglob("bank01.work"))
    assert len(staged) == 1, f"expected one staged bank01.work: {staged}"
    # Inspect the card staging result too; it is what the loader reads.
    staged_bank = staged[0].read_bytes()
    original_bank = (project / "bank01.work").read_bytes()
    assert staged_bank == original_bank, "staging changed bank01.work"
    return {
        "name": name, "card": str(card.relative_to(ROOT)), "card_sha256": digest(card),
        "project_sha256": {p.name: digest(p) for p in sorted(project.iterdir()) if p.is_file()},
        "sample_sha256": digest(sample), "stage_command": command,
        "expected": {"machine": "FLEX", "active_primary_voices": active,
                     "fx1_ids": [0] * 8, "fx2_ids": [0] * 8, "tstr": "OFF",
                     "pitch": 64, "rate": 127, "loop": True, "trig_steps": [1, 2, 3, 4] if active else [],
                     "track_level": 64, "master_track": False, "bpm": 120,
                     "sample_format": "stereo PCM16 44100 Hz", "scene_lfo_input": "inherited; not controlled"},
        "checks": {"bank_checksums": "passed", "all_bank_part_fx_ids": "zero",
                   "A01_trig_masks": "passed", "staged_bank_byte_identity": "passed"},
    }


def smoke_case(case: dict, out: Path, frames: int) -> dict:
    """Check real post-transport IDs and voices, with a short stock run."""
    name = case["name"]
    work = out / name
    dump = work / "live.bin"
    command = [str(EMU), "--image", str(STOCK), "--card", str(ROOT / case["card"]),
               "--set", "OCTABAM", "--project", name.upper().replace("-", ""),
               "--sequencer", "--internal-clock", "--frames", str(frames),
               "--load-ms", "20000", "--dsp", "--main-level", "64",
               "--mem-dump", f"{LIVE_FX1:#x},16={dump};{VOICE:#x},{VOICE_SIZE * 8}={work / 'voices.bin'}"]
    log = work / "smoke.log"
    with log.open("w") as f:
        f.write(" ".join(command) + "\n")
        f.flush()
        result = subprocess.run(command, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
    text = log.read_text()
    assert result.returncode == 0 and "run ended REACHED" in text, f"incomplete smoke: {log}"
    live = dump.read_bytes()
    assert live == bytes(16), f"post-transport live FX IDs nonzero: {live.hex()} ({log})"
    voices = (work / "voices.bin").read_bytes()
    assert len(voices) == VOICE_SIZE * 8
    active = [i + 1 for i in range(8) if voices[i * VOICE_SIZE] != 0]
    expected = list(range(1, case["expected"]["active_primary_voices"] + 1))
    assert active == expected, f"post-transport active voices {active} != {expected} ({log})"
    return {"command": command, "log": str(log.relative_to(ROOT)),
            "live_fx1_ids": list(live[:8]), "live_fx2_ids": list(live[8:]),
            "active_primary_tracks": active, "activity": "post-transport checked",
            "model_limit": "ATA/DMA streaming activity not established"}


def profile_case(case: dict, out: Path, frames: int) -> dict:
    """Count stock PCs to distinguish the rendered voices from background work."""
    work = out / case["name"]
    prefix = work / "profile"
    if Path(str(prefix) + ".cpu.tsv").exists():
        raise FileExistsError(f"profile already exists for {case['name']}")
    command = [str(EMU), "--image", str(STOCK), "--card", str(ROOT / case["card"]),
               "--set", "OCTABAM", "--project", case["name"].upper().replace("-", ""),
               "--sequencer", "--internal-clock", "--frames", str(frames),
               "--load-ms", "20000", "--dsp", "--main-level", "64",
               "--work-profile", str(prefix)]
    log = work / "profile.log"
    with log.open("w") as f:
        f.write(" ".join(command) + "\n")
        f.flush()
        result = subprocess.run(command, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
    assert result.returncode == 0 and "run ended REACHED" in log.read_text(), f"incomplete profile: {log}"
    summary = work / "profile.json"
    subprocess.run([sys.executable, str(ROOT / "tools/harness/profile_stock.py"),
                    "--prefix", str(prefix), "--frames", str(frames), "--image", str(STOCK),
                    "--card", str(ROOT / case["card"]), "--json", str(summary)],
                   cwd=ROOT, check=True, capture_output=True, text=True)
    data = json.loads(summary.read_text())
    scopes = {scope["name"]: scope["per_frame"] for scope in data["scopes"]}
    return {"command": command, "log": str(log.relative_to(ROOT)),
            "summary": str(summary.relative_to(ROOT)), "total_cpu_per_frame": data["per_frame"],
            "voice_renderer_per_frame": scopes["voice renderer (exclusive)"],
            "sample_analysis_per_frame": scopes["sample analysis"],
            "profile_reader_sha256": digest(ROOT / "tools/harness/profile_stock.py"),
            "units": "emulator instructions per 16-sample frame; not hardware cycles"}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", type=Path, default=SOURCE)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--smoke", action="store_true", help="run each case under stock emulator")
    ap.add_argument("--profile", action="store_true", help="also collect per-PC profiles for new cases")
    ap.add_argument("--profile-existing", action="store_true", help="profile cases from an existing manifest")
    ap.add_argument("--frames", type=int, default=1400)
    args = ap.parse_args()
    out = args.out.resolve()
    if not out.is_relative_to(ROOT / "out"):
        ap.error("--out must be beneath ignored repo out/")
    if args.frames < 2:
        ap.error("--frames must be at least 2")
    if args.profile_existing:
        manifest_path = out / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        for case in manifest["cases"]:
            if "smoke" not in case or "profile" in case:
                raise RuntimeError(f"expected smoke without profile: {case['name']}")
            print(f"profile {case['name']}", flush=True)
            case["profile"] = profile_case(case, out, args.frames)
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        return
    if out.exists():
        ap.error("--out must be a fresh directory for generation")
    source = args.source.resolve()
    src_hash = source_hashes(source)
    if digest(PILOT) != PILOT_SHA256:
        raise RuntimeError("preserved pilot card hash differs; do not silently replace the regression fixture")
    if args.smoke and (not STOCK.is_file() or not EMU.is_file()):
        raise RuntimeError("smoke needs the local stock image and existing emulator")
    out.mkdir(parents=True)
    sample = out / "tone.wav"
    repitch.make_loop(sample)
    manifest = {
        "schema": 1, "firmware": "stock 1.40C", "hardware_measured": False,
        "source_project": str(source), "source_project_sha256": src_hash,
        "generator_sha256": digest(Path(__file__)),
        "sample": str(sample.relative_to(ROOT)), "sample_sha256": digest(sample),
        "event_schedule": [], "event_schedule_sha256": hashlib.sha256(b"[]").hexdigest(),
        "pilot": {"card": str(PILOT.relative_to(ROOT)), "card_sha256": PILOT_SHA256,
                  "set": "OCTABAM", "project": "POLYBENCH", "machine": "FLEX",
                  "active_tracks": 8, "FX1": [4] * 8, "FX2": [8] * 7 + [20],
                  "status": "preserved exact bytes; prior A/B/A activity in STOCK_PROFILE.md"},
        "cases": [], "pending": PENDING,
        "tiers": {"smoke": f"{args.frames} frames", "musical": "pending >=30 seconds",
                  "soak": "pending >=5 minutes"},
    }
    manifest_path = out / "manifest.json"
    for name, active in CASES.items():
        print(f"staging {name}", flush=True)
        case = stage_case(source, out, name, active, sample)
        manifest["cases"].append(case)
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        if args.smoke or args.profile:
            print(f"smoke {name}", flush=True)
            case["smoke"] = smoke_case(case, out, args.frames)
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        if args.profile:
            print(f"profile {name}", flush=True)
            case["profile"] = profile_case(case, out, args.frames)
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    if source_hashes(source) != src_hash:
        raise RuntimeError("source project changed while generating fixtures")
    print(manifest_path)


if __name__ == "__main__":
    main()
