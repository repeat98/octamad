#!/usr/bin/env python3
"""Prove the MD chooser and editor through panel events and RAM state."""
import os
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/hw"))
sys.path.insert(0, str(ROOT / "tools/harness"))
import ot_project as otp
from md_panel import run_scripted

OUT = ROOT / "out/mdverify/ui_gate"
PART = 0x400e21e0 + 0x8ed80
T1_FLEX = 0x2a + 6
T2_FLEX = 0x2a + 30 + 6
SIG = 0x2a + 18


def symbols():
    lines = subprocess.check_output(
        ["m68k-elf-nm", str(ROOT / "out/platform/runtime/runtime.elf")], text=True)
    return {line.split()[-1]: int(line.split()[0], 16)
            for line in lines.splitlines() if len(line.split()) == 3}


def stage(source, name, signed):
    fixture = OUT / name
    if fixture.exists():
        shutil.rmtree(fixture)
    shutil.copytree(source, fixture)
    if signed:
        for part in range(1, 5):
            otp.set_md_machine(fixture, 1, part, 1, guard=False)
    card = OUT / (name + ".img")
    subprocess.run([sys.executable, str(ROOT / "tools/emu/ot_emu/stage_card.py"),
                    str(fixture), "OCTABAM", "RIG", "--tree", str(OUT / (name + "_tree")),
                    "--out", str(card)], check=True, cwd=ROOT, capture_output=True)
    return fixture, card


def run(name, card_base, emu, image, spans, script, sequencer=False):
    here = OUT / name
    here.mkdir(parents=True, exist_ok=True)
    card = here / "card.img"
    shutil.copyfile(card_base, card)
    dump = ";".join(f"{addr:#x},{size}={here / (key + '.bin')}"
                    for key, (addr, size) in spans.items())
    cmd = [str(emu), "--image", str(image), "--card", str(card), "--set", "OCTABAM",
           "--project", "RIG", "--load-ms", "20000", "--dsp"]
    if sequencer:
        cmd += ["--sequencer", "--frames", "20000"]
    cmd += ["--mem-dump", dump]
    rc, sent = run_scripted(cmd, script, here / "port.log", cwd=ROOT, timeout=600)
    log = (here / "port.log").read_text()
    assert rc == 0 and len(sent) == len(script), (name, rc, sent)
    assert "run ended ILLEGAL" not in log, name
    assert ("run ended REACHED" if sequencer else "ended on quit") in log, name
    return {key: (here / (key + ".bin")).read_bytes() for key in spans}


def choose_script(track=None):
    script = []
    if track is not None:
        script += [(1.0, f"key {0x10 + track:#x} down"),
                   (0.3, f"key {0x10 + track:#x} up")]
        first = 0.3
    else:
        first = 1.0
    script += [(first, "key 0x2d down"), (0.3, "key 0x22 down"),
               (0.3, "key 0x22 up"), (0.3, "key 0x2d up")]
    for _ in range(6):
        script += [(0.2, "key 0x20 down"), (0.2, "key 0x20 up")]
    script += [(0.4, "key 0x31 down"), (0.3, "key 0x31 up"), (1.0, "quit")]
    return script


def main():
    project = os.environ.get("OT_PROJECT")
    emu = os.environ.get("MD_EMU")
    if not project or not emu:
        raise SystemExit("MD_EMU and OT_PROJECT are required")
    OUT.mkdir(parents=True, exist_ok=True)
    image = ROOT / "out/mainos_bus.bin"
    source = pathlib.Path(project)
    if not source.is_absolute():
        source = ROOT / source
    unsigned, card = stage(source, "unsigned", False)
    saved = (unsigned / "bank01.work").read_bytes()
    base = otp.PART_BASE + 9
    assert saved[base + 0x22] == 0 and saved[base + SIG:base + SIG + 3] != b"MD\x01"
    t2_before = saved[base + T2_FLEX:base + T2_FLEX + 6]

    selected = run("choose", card, emu, image,
                   {"part": (PART, 0x100)}, choose_script())["part"]
    assert selected[0x22] == 1 and selected[SIG:SIG + 3] == b"MD\x01"
    assert selected[T2_FLEX:T2_FLEX + 6] == t2_before
    print("chooser: T1 FLEX + MD signature; T2 FLEX slot unchanged")

    _, signed_card = stage(source, "signed", True)
    for track in (1, 4):
        refused = run(f"refuse_t{track + 1}", signed_card, emu, image,
                      {"part": (PART, 0x120)}, choose_script(track))["part"]
        assert refused[0x22] == 1 and refused[SIG:SIG + 3] == b"MD\x01"
        assert refused[0x22 + track] == 0
        sig = SIG + 30 * track
        assert refused[sig:sig + 3] != b"MD\x01"
    print("admission: second MD on T2 and any MD on T5 refused")
    sym = symbols()
    edit = [(1.0, "key 0x10 down"), (0.4, "key 0x01 down"),
            (0.3, "key 0x01 up"), (0.3, "key 0x10 up"),
            (0.5, "enc 0 5"), (0.5, "key 0x29 down"),
            (0.3, "key 0x04 down"), (0.3, "key 0x04 up"),
            (0.3, "key 0x29 up"), (1.0, "quit")]
    state = run("edit", signed_card, emu, image,
                {"ui": (sym["md_ui"], 500), "kit": (sym["md_kit"], 192),
                 "pattern": (sym["md_patterns"], 384),
                 "part": (PART, 0x100), "mask": (0x400e21e0, 8),
                 "name": (sym["md_ui_name"], 12),
                 "desc_ptr": (sym["md_desc_p"], 4)}, edit, sequencer=True)
    ui, kit, pat = state["ui"], state["kit"], state["pattern"]
    assert ui[0] == 1, f"part selection: {ui[0]}"
    assert kit[12 + 4] == 0x45 and state["part"][T1_FLEX] == 0x45
    assert int.from_bytes(pat[8:12], "big") & 0x10
    assert state["mask"][7] & 0x10
    assert state["name"].startswith(b"P02 TRX-SD\x00")
    desc = ui[40:40 + 0x1ca]
    assert desc[0x4e + 6 * 8:0x4e + 6 * 8 + 3] == b"VOL"
    assert desc[0x4e + 6 * 10:0x4e + 6 * 10 + 3] == b"ENG"
    assert int.from_bytes(state["desc_ptr"], "big") == sym["md_ui"] + 40 + 0x38
    print("editor: part 2 selected, SYN 1 = 69, step 5 recorded, name and page 2 present")

    page2 = [(1.0, "key 0x10 down"), (0.3, "key 0x10 up"),
             (0.3, "key 0x2d down"), (0.3, "key 0x22 down"),
             (0.3, "key 0x22 up"), (0.3, "key 0x2d up"),
             (0.5, "enc 0 5"), (1.0, "quit")]
    state2 = run("page2", signed_card, emu, image,
                 {"kit": (sym["md_kit"], 192), "part": (PART, 0x300)}, page2)
    assert state2["kit"][4 + 6] == 5
    assert state2["part"][0x1da + 6] == 5
    print("page 2: A knob changes part 1 SYN 7 and its FLEX page-2 slot to 5")

    # ENG is SETUP's E: stock gears a select there at 819 per step (about
    # four detents); md_ui.c gears it at one detent per engine.
    eng = page2[:6] + [(0.5, "enc 4 1"), (1.0, "quit")]
    state3 = run("eng", signed_card, emu, image,
                 {"kit": (sym["md_kit"], 192), "part": (PART, 0x300)}, eng)
    assert state3["kit"][0] == 0x11, f"engine {state3['kit'][0]:#x}"
    assert state3["part"][0x1da + 6 + 4] == 5, state3["part"][0x1da + 6:0x1da + 12].hex()
    assert state3["kit"][4 + 6] == 0x40            # TRX-SD's SYN 7 default
    print("page 2: one E detent changes part 1 from TRX-BD to TRX-SD with its defaults")
    print("verify_md_ui: PASS")


if __name__ == "__main__":
    main()
