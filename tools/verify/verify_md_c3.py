#!/usr/bin/env python3
"""Under-port regression: an MD SRC edit stays in T1's FLEX page slot."""
import os
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/hw"))
sys.path.insert(0, str(ROOT / "tools/harness"))
import ot_project as otp
from md_panel import key, run_scripted

OUT = ROOT / "out/mdverify/c3"
PART = 0x400e21e0 + 0x8ed80
PART_BYTES = 0x18b2
T1_FLEX = 0x2a + 6
T2_FLEX = 0x2a + 30 + 6
SIG = 0x2a + 18


def run(tag, image, card_base, edits, emu):
    card = OUT / f"{tag}.img"
    shutil.copy2(card_base, card)
    dump = OUT / f"{tag}.part"
    cmd = [str(emu), "--image", str(image), "--card", str(card),
           "--set", "OCTABAM", "--project", "RIG", "--load-ms", "20000",
           "--dsp", "--mem-dump", f"{PART:#x},{PART_BYTES}={dump}"]
    script = key(0x10) + key(0x22)
    if edits:
        script += [(2, "enc 0 10"), (2, "enc 1 5"), (2, "enc 5 3")]
    script += [(4, "quit")]
    rc, sent = run_scripted(cmd, script, OUT / f"{tag}.log", cwd=ROOT, timeout=600)
    if rc or len(sent) != len(script) or not dump.is_file():
        raise RuntimeError(f"{tag}: port rc={rc}, sent={len(sent)}/{len(script)}, dump={dump.is_file()}")
    return dump.read_bytes()


def main():
    project = os.environ.get("OT_PROJECT")
    if not project:
        raise SystemExit("OT_PROJECT is required")
    emu = pathlib.Path(os.environ["MD_EMU"])
    OUT.mkdir(parents=True, exist_ok=True)
    fixture = OUT / "project"
    if fixture.exists():
        shutil.rmtree(fixture)
    shutil.copytree(project, fixture)
    for part in range(1, 5):
        otp.set_md_machine(fixture, 1, part, 1, guard=False)
    card = OUT / "base.img"
    subprocess.run([sys.executable, str(ROOT / "tools/emu/ot_emu/stage_card.py"),
                    str(fixture), "OCTABAM", "RIG", "--tree", str(OUT / "tree"),
                    "--out", str(card)], check=True, cwd=ROOT, capture_output=True)
    image = OUT / "image.bin"
    shutil.copy2(ROOT / "out/mainos_bus.bin", image)
    before = run("before", image, card, False, emu)
    after = run("after", image, card, True, emu)
    assert after[0x22] == 1 and after[SIG:SIG + 3] == b"MD\x01", (
        "MD type/signature absent in working Part")
    assert before[T2_FLEX:T2_FLEX + 6] == after[T2_FLEX:T2_FLEX + 6], (
        f"T2 FLEX slot changed: {before[T2_FLEX:T2_FLEX + 6].hex()} -> "
        f"{after[T2_FLEX:T2_FLEX + 6].hex()}")
    assert before[T1_FLEX:T1_FLEX + 6] != after[T1_FLEX:T1_FLEX + 6], (
        "SRC knob edit did not reach T1 FLEX slot")
    print(f"T1 FLEX {list(before[T1_FLEX:T1_FLEX + 6])} -> "
          f"{list(after[T1_FLEX:T1_FLEX + 6])}")
    print(f"T2 FLEX unchanged: {list(after[T2_FLEX:T2_FLEX + 6])}")
    print("verify_md_c3: PASS")


if __name__ == "__main__":
    main()
