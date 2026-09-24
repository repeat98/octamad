#!/usr/bin/env python3
"""Compare original and core-1 relocated MD initialization on twelve captures.

Run md_gate.sh first to generate each capture's current reloc.txt. The init
probe zeros its destinations, runs the MD boot-init path to its RTS, and dumps
sine, P-I, and X/Y voice state. A capture's post-boot snapshot need not equal
a second init run; this gate compares the two runs from the same snapshot.
"""
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
REPLAY = ROOT / "out/md_reference/md_replay"


def run(capture: Path, moved: bool, dump: Path) -> tuple[int, str]:
    env = os.environ.copy()
    env["MD_REPLAY_INIT_DUMP"] = str(dump)
    command = [str(REPLAY), str(capture)]
    if moved:
        command.append("--reloc")
    command.append("--init")
    result = subprocess.run(command, env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True)
    summary = next((line for line in result.stdout.splitlines()
                    if line.startswith("init: ")), "")
    if result.returncode not in (0, 3) or not summary or not dump.exists():
        raise RuntimeError(f"{capture.name} {'moved' if moved else 'plain'}: "
                           f"{result.stdout[-500:]}")
    return result.returncode, summary


def main() -> int:
    captures = sorted((ROOT / "out/md_profile/cap4").glob("c*"))
    captures += sorted((ROOT / "out/md_profile/cap5").glob("c*"))
    if len(captures) != 12:
        raise SystemExit(f"expected 12 captures, found {len(captures)}")
    bad = 0
    with tempfile.TemporaryDirectory(prefix="md-init-") as tmp:
        for capture in captures:
            if not (capture / "reloc.txt").exists():
                raise SystemExit(f"missing {capture / 'reloc.txt'}; run md_gate.sh")
            plain = Path(tmp) / "plain.txt"
            moved = Path(tmp) / "moved.txt"
            run(capture, False, plain)
            run(capture, True, moved)
            left, right = plain.read_bytes(), moved.read_bytes()
            differences = sum(a != b for a, b in zip(left.splitlines(),
                                                       right.splitlines()))
            if len(left) != len(right):
                differences += abs(len(left.splitlines()) - len(right.splitlines()))
            print(f"{capture.name:7s} {differences} initialization differences")
            bad += differences != 0
    return int(bool(bad))


if __name__ == "__main__":
    raise SystemExit(main())
