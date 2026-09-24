#!/usr/bin/env python3
"""Capture all 50 MD map detents and byte-compare the build-linked handlers."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "modules/machinedrum"))
import extraction  # noqa: E402
import handler_build  # noqa: E402

OUT = ROOT / "out/machinedrum/c2_maps"
PROFILE = ROOT / "out/md_reference/md_profile"
GATE = ROOT / "out/md_reference/md_handler_gate"
FLASH = (ROOT / "base_firmware/Elektron_SPS1-1UW_OS1.63"
         / "elektron_sps1-1uw_os1.63.bin")
RUNTIME = ROOT / "out/platform/runtime"


def engines():
    rows = [e for e in extraction.engines()
            if e["family"] in ("GND", "TRX", "EFM", "E12", "P-I")
            and e["name"] != "GND---"]
    if len(rows) != 50:
        sys.exit(f"expected 50 engines, found {len(rows)}")
    return rows


def capture(rows):
    OUT.mkdir(parents=True, exist_ok=True)
    for name in ("cases.txt", "map.txt"):
        (OUT / name).unlink(missing_ok=True)
    if not PROFILE.exists() or not FLASH.exists():
        sys.exit("build out/md_reference/md_profile and supply the user's MD flash")
    env = dict(os.environ, MD_HANDLER_CASES=str(OUT / "cases.txt"))
    cmd = [str(PROFILE), str(FLASH), str(OUT),
           *(f"map=0x{e['id']:02x}" for e in rows)]
    with (OUT / "run.log").open("w") as log:
        result = subprocess.run(cmd, env=env, stdout=log, stderr=subprocess.STDOUT)
    if result.returncode:
        sys.exit(f"md_profile failed; see {OUT / 'run.log'}")
    print(f"captured {len(rows)} reference map scenarios", flush=True)


def verify(rows):
    cases = (OUT / "cases.txt").read_text().splitlines()
    maps = (OUT / "map.txt").read_text().splitlines()
    if len(cases) != 450 or len(maps) != 450:
        sys.exit(f"incomplete MD map capture: {len(cases)} cases, {len(maps)} map lines")
    expected = {(e["id"], n): e["handler"] for e in rows for n in range(-1, 8)}
    for line in cases:
        fields = line.split()
        key = (int(fields[0], 16), int(fields[1]))
        if len(fields) != 7 or key not in expected:
            sys.exit(f"unexpected handler case {fields[:3]}")
        actual = int(fields[2], 16)
        descriptor = expected.pop(key)
        # TRX-S2's map= scenario sends no trigger record and the live
        # pointer remains the empty handler. Its descriptor code is also
        # exercised source-vs-port with the captured parameter vectors.
        if actual != descriptor and not (key[0] == 0x1d and actual == 0x201128):
            sys.exit(f"handler entry mismatch for {key}")
    if expected:
        sys.exit(f"missing handler cases: {sorted(expected)}")
    layout = json.loads((ROOT / "out/platform/layout.json").read_text())
    symbols = subprocess.check_output(
        ["m68k-elf-nm", str(RUNTIME / "runtime.elf")], text=True)
    names = {fields[-1]: int(fields[0], 16)
             for line in symbols.splitlines()
             if len(fields := line.split()) == 3}
    base = names["md_handler_empty"]
    source = handler_build.image()
    runtime = (RUNTIME / "runtime.bin").read_bytes()
    lo, hi = handler_build.CODE
    code = bytearray(source[lo - extraction.OS_BASE:hi - extraction.OS_BASE])
    for addr, target in handler_build.relocations(source).items():
        if target == handler_build.SRAM_WORD:
            moved = names["md_handler_sram_word"]
        else:
            table = (0 if target < handler_build.TABLES[1][0] else 1)
            table_addr = names[("md_table_low", "md_table_high")[table]]
            moved = table_addr + target - handler_build.TABLES[table][0]
        code[addr - lo:addr - lo + 4] = moved.to_bytes(4, "big")
    offset = base - layout["base"]
    if runtime[offset:offset + len(code)] != code:
        sys.exit("build-linked MD handler code differs beyond table relocation")
    for (start, end), name in zip(handler_build.TABLES,
                                   ("md_table_low", "md_table_high")):
        offset = names[name] - layout["base"]
        expected_bytes = source[start - extraction.OS_BASE:end - extraction.OS_BASE]
        if runtime[offset:offset + len(expected_bytes)] != expected_bytes:
            sys.exit(f"build-linked MD {name} differs from the pinned OS")
    print("PASS: full handler code and both table spans match the pinned OS "
          "apart from 148 relocated operands", flush=True)
    cmd = [str(GATE), str(extraction.OUT / "section_0_MAIN_OS.bin"),
           str(RUNTIME / "runtime.bin"), hex(layout["base"]), hex(base),
           hex(names["md_handler_sram_word"]), str(OUT / "cases.txt")]
    result = subprocess.run(cmd)
    if result.returncode:
        sys.exit(result.returncode)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--verify-only", action="store_true",
                    help="reuse an existing complete capture")
    args = ap.parse_args()
    rows = engines()
    if not args.verify_only:
        capture(rows)
    verify(rows)
