#!/usr/bin/env python3
"""Validate the opt-in analysis patch and extract a stock-only A/B image.

The comparison image copies ONLY the linked unit and declared hook from the
remixer output. It is a raw emulator input, NOT a flashable firmware file.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import toolpath  # noqa: E402,F401
from remix import registry  # noqa: E402

STOCK_SHA = "164f31224bf61181e3f50e7dec40df9afcae5b16dbf6e4c0d0cc5e986af0a84e"
BASE, HOOK = 0x40000400, 0x40098494


def run(*args):
    return subprocess.check_output([str(x) for x in args], cwd=ROOT, text=True)


def main():
    remix = sys.argv[1] if len(sys.argv) > 1 else "stock-analysis-fast"
    if "STOCK ANALYSIS FAST" not in registry.remix(remix).modules:
        print(f"  [ -- ] STOCK ANALYSIS FAST not in {remix}")
        return
    stock = (ROOT / "out/raw/section_3_MAIN_OS.bin").read_bytes()
    if hashlib.sha256(stock).hexdigest() != STOCK_SHA:
        raise RuntimeError("Unvalidated stock revision: need the verified 1.40C image")
    built = (ROOT / "out/mainos_bus.bin").read_bytes()
    hook = built[HOOK-BASE:HOOK-BASE+8]
    if hook[:2] != bytes.fromhex("4ef9") or hook[6:] != bytes.fromhex("4e71"):
        raise RuntimeError("Selected output does not contain the expected hook")
    target = int.from_bytes(hook[2:6], "big")
    unit = ROOT / "out/linked/stock-analysis-fast/analysis-fast/u.bin"
    code = unit.read_bytes()
    if not code or built[target-BASE:target-BASE+len(code)] != code:
        raise RuntimeError("Linked unit differs from the bytes in the built image")
    if any(stock[target-BASE:target-BASE+len(code)]):
        raise RuntimeError("Candidate code is not in a zero-filled stock cave")
    out = ROOT / "out/stock-profile"
    out.mkdir(exist_ok=True)
    isolated = bytearray(stock)
    isolated[HOOK-BASE:HOOK-BASE+8] = hook
    isolated[target-BASE:target-BASE+len(code)] = code
    candidate = out / "candidate-raw.bin"
    candidate.write_bytes(isolated)
    (out/"candidate-map.json").write_text(json.dumps(dict(
        image_sha256=hashlib.sha256(isolated).hexdigest(),
        cave_address=target, cave_bytes=len(code)), indent=2)+"\n")
    print(f"  [PASS] stock-only comparison: 8-byte hook + {len(code)}-byte cave at {target:#x}")
    run("m68k-elf-as", "-mcpu=5475", "-o", out/"state.o", "tools/harness/stock_analysis_state.s")
    run("m68k-elf-ld", "-Ttext=0x47080000", "-e", "probe_init", "-o", out/"state.elf", out/"state.o")
    run("m68k-elf-objcopy", "-O", "binary", out/"state.elf", out/"state.bin")
    symbols = {s[2]: int(s[0],16) for ln in run("m68k-elf-nm", out/"state.elf").splitlines()
               if len(s := ln.split()) == 3}
    run("cmake", "-B", "out/emu", "-S", "tools/emu/ot_emu")
    run("cmake", "--build", "out/emu", "-j8", "--target", "ot_stock_analysis_test")
    result = run("out/emu/ot_stock_analysis_test", "out/raw/section_3_MAIN_OS.bin",
                 candidate, out/"state.bin", hex(symbols["probe_capture"]))
    (out/"differential.log").write_text(result)
    for ln in result.splitlines():
        if ln.startswith("  ["): print(ln)


if __name__ == "__main__":
    main()
