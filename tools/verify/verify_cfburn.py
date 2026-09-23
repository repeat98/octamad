#!/usr/bin/env python3
"""CF BURN: the ColdFire cycle-burn knob is inert and exact.

Runs tools/harness/cfburn_probe.cpp (target ot_cfburn_test): the complete
stock eight-track delay routine, the built image against pristine stock,
frame by frame, with live DELAY tracks beside it. It proves:

  1. INERT  on-chip SRAM 0x80000000..0x8000ffff, the stack, every ring word
            written and every returned register equal stock's, with and
            without CF BURN tracks, at any knob setting;
  2. EXACT  executed instructions = stock + 75 + 5*tracks + BODY*N, with
            N = sum of BURN*STEP + FINE over this frame's snapshot only;
  3. LIVE   the DELAY tracks wrote nonzero ring words and changed their audio,
            a flipped state bit is reported, and stock-vs-stock fails the
            count (the comparison and the meter can both see).

Instructions, not cycles: the port has no caches, bus or DMA timing. The
knob is a meter only when swept on the unit (modules/cfburn/README.md).

    python3 tools/verify/verify_cfburn.py [REMIX]
"""
import importlib.util
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import toolpath  # noqa: E402,F401
from remix import registry  # noqa: E402

IMAGE = ROOT / "out/mainos_bus.bin"
STOCK = ROOT / "out/raw/section_3_MAIN_OS.bin"
BASE = 0x40000400
SITE = 0x40003826


def run(cmd):
    r = subprocess.run([str(c) for c in cmd], cwd=ROOT, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def main():
    remix = sys.argv[1] if len(sys.argv) > 1 else "cfburn"
    if "CF BURN" not in registry.remix(remix).modules:
        print(f"  [ -- ] CF BURN not in {remix}")
        return 0
    mod = registry.by_key("CF BURN")
    spec = importlib.util.spec_from_file_location("cfburn_manifest", ROOT / "modules/cfburn/manifest.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    ident, step, body = m.ID, m.STEP, m.BODY
    src = (ROOT / "modules/cfburn/burn.s").read_text()
    equ = re.search(r"\.equ\s+CFBURN_ID,\s*(0x[0-9a-fA-F]+)", src)
    fails = 0
    if not equ or int(equ.group(1), 16) != ident or mod.menu.fx2_id != ident:
        print(f"  [FAIL] burn.s CFBURN_ID, manifest ID and the menu id disagree")
        fails += 1
    if not IMAGE.is_file():
        print(f"  [FAIL] missing {IMAGE.relative_to(ROOT)}; run make bus REMIX={remix}")
        return 1
    img = IMAGE.read_bytes()
    if img[SITE - BASE:SITE - BASE + 2] != b"\x4e\xf9":
        # Any verifier that reads out/ must know who wrote it last (CLAUDE.md).
        print(f"  [FAIL] {IMAGE.relative_to(ROOT)} has no jmp at 0x{SITE:08x}: not a CF BURN build "
              f"(rebuild with make bus REMIX={remix})")
        return 1
    rc, log = run(["cmake", "--build", "out/emu", "--target", "ot_cfburn_test", "-j8"])
    if rc:
        print(log[-3000:])
        print("  [FAIL] could not build ot_cfburn_test (cmake -S tools/emu/ot_emu -B out/emu first)")
        return 1
    rc, log = run([ROOT / "out/emu/ot_cfburn_test", IMAGE, STOCK, hex(ident), step, body])
    out = ROOT / "out/cfburn"
    out.mkdir(parents=True, exist_ok=True)
    (out / "probe.log").write_text(log)
    for line in log.splitlines():
        if re.match(r"\s+\[(PASS|FAIL|METER|LIVE)\]", line):
            print(line)
    if rc:
        print("\n".join(l for l in log.splitlines() if not re.match(r"(write|read|update)\w*@", l))[-2000:])
        fails += 1
    print(f"\n{fails} failure(s)" if fails else
          "OK: CF BURN inert and exact under the port; the ceiling is measured on the unit")
    return int(bool(fails))


if __name__ == "__main__":
    raise SystemExit(main())
