#!/usr/bin/env python3
"""FORCE FILENAME BPM's gate: run the module's own hooks under the ColdFire
port and read the tempo field back (tools/harness/fnbpm_probe.cpp).

The build already asserts every displaced byte, so what is left to prove is
what the code COMPUTES -- and it caught a real defect the first time it ran
(the stored tempo was stashed in %d1, which the parser uses as scratch, so
a name with no number came back as the last character minus 48).

SKIPs rather than fails when the port is not built or the image in out/ is
not a FORCE FILENAME BPM remix: `make check` runs on trees that never asked
for this module. It rebuilds nothing -- run it after `make bus REMIX=...`,
which is where `make check` puts it.
"""
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
PROBE = ROOT / "out/emu/ot_fnbpm_test"
IMAGE = ROOT / "out/mainos_bus.bin"

if not IMAGE.exists():
    print("  [SKIP] verify_fnbpm: no out/mainos_bus.bin (make bus REMIX=...)")
    sys.exit(0)
if not PROBE.exists():
    if shutil.which("cmake") is None:
        print("  [SKIP] verify_fnbpm: the ColdFire port is not built and cmake is absent")
        sys.exit(0)
    build = subprocess.run(
        ["cmake", "-B", "out/emu", "-S", "tools/emu/ot_emu"], cwd=ROOT,
        capture_output=True, text=True)
    if build.returncode == 0:
        build = subprocess.run(
            ["cmake", "--build", "out/emu", "-j8", "--target", "ot_fnbpm_test"],
            cwd=ROOT, capture_output=True, text=True)
    if build.returncode != 0 or not PROBE.exists():
        print("  [SKIP] verify_fnbpm: the ColdFire port would not build here")
        sys.exit(0)

r = subprocess.run([str(PROBE), str(IMAGE)], cwd=ROOT, capture_output=True, text=True)
# The machine prints its peripheral bring-up on construction; the gate lines
# are the ones that start with two spaces and a bracket.
lines = [ln for ln in r.stdout.splitlines()
         if ln.startswith("  [") or ln.startswith("SKIP") or ln.startswith("FORCE")]
if any(ln.startswith("SKIP") for ln in r.stdout.splitlines()):
    print("  [SKIP] verify_fnbpm: out/mainos_bus.bin does not carry the module")
    sys.exit(0)
for ln in lines:
    print(ln if ln.startswith("  [") else "  " + ln)
print(f"  [{'PASS' if r.returncode == 0 else 'FAIL'}] verify_fnbpm: "
      f"the filename's BPM reaches the tempo field")
sys.exit(r.returncode)
