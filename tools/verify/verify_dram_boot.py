#!/usr/bin/env python3
"""Boot the image just built under the ColdFire port and check that every
DRAM payload octabam's loader carries actually lands.

For the current REMIX (the image at out/mainos_bus.bin):
  * the boot reaches the RTOS handoff, and the loader's entry ran exactly
    once while its `fatal` hang never did -- so every hash gate passed;
  * the octabam window (out/platform/runtime/runtime.bin, when the remix
    has DRAM units) and Octakit's window (out/runtime/octakit/runtime.bin,
    when OCTAKIT is in the remix) read back equal to the linked runtimes
    -- except for bytes the runtimes themselves write once they run
    (midi-scenes' state words are the known case), which are counted and
    printed, not hidden;
  * with MACHINEDRUM, the loader's PRE-BOOT payload (the combined core-1
    upload, tools/build/md_image.py) reached core 1: its code records --
    the hot code, the driver, the window code and the glue -- read back
    from core 1's P equal to out/machinedrum/build/core1_upload.bin, and
    the MACHINEDRUM id dispatches to the glue there.

SKIPs when the port is not built (`make emu-cf`) or the remix carries no
DRAM payload. What this cannot see: caches (the port has none), the
recorder, and anything after the handoff.
"""
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path)
from remix import platform_build, registry  # noqa: E402

EMU = ROOT / "out/emu/ot_emu"
IMAGE = ROOT / "out/mainos_bus.bin"
remix = registry.remix(os.environ.get("REMIX") or registry.DEFAULT_REMIX)
mods = [registry.modules()[k] for k in remix.modules]
dram = any(u.dram for m in mods for u in getattr(m, "linked", ()))
octakit = "OCTAKIT" in remix.modules
md = "MACHINEDRUM" in remix.modules
if not (dram or octakit or md):
    print(f"  [ -- ] verify_dram_boot: {remix.name} carries no DRAM payload")
    sys.exit(0)
if not EMU.exists():
    print("  [SKIP] verify_dram_boot: the ColdFire port is not built (make emu-cf)")
    sys.exit(0)

# Build THIS remix's image first: `make verify` runs after the remix
# self-test, which builds every remix in turn and leaves the last one at
# out/mainos_bus.bin (and its loader at out/platform/). The first run of
# this check booted `warped` while looking for midi-scenes' loader and
# reported it never ran.
env = dict(os.environ, REMIX=remix.name, XBUS="1", SPEC="1")
env.setdefault("BUILD", "0")
r = subprocess.run([sys.executable, str(ROOT / "tools/build/build_bus.py")], env=env,
                   capture_output=True, text=True, cwd=ROOT)
if r.returncode:
    sys.exit(f"verify_dram_boot: building {remix.name} failed:\n{(r.stdout + r.stderr)[-1500:]}")

nm = subprocess.run(["m68k-elf-nm", str(ROOT / "out/platform/loader.elf")],
                    capture_output=True, text=True).stdout
syms = {f[2]: int(f[0], 16) for f in (l.split() for l in nm.splitlines()) if len(f) == 3}
entry, fatal = syms["octabam_bootstrap"], syms["fatal"]

dumps, expects = [], []
if dram:
    import json
    layout = json.loads((ROOT / "out/platform" / platform_build.LAYOUT).read_text())
    raw = (ROOT / "out/platform/runtime/runtime.bin").read_bytes()
    dumps.append((layout["base"], len(raw), ROOT / "out/_dump_octabam.bin"))
    expects.append(("octabam reserve", raw))
if octakit:
    raw = (ROOT / "out/runtime/octakit/runtime.bin").read_bytes()
    dumps.append((0x45D0DDE0, len(raw), ROOT / "out/_dump_octakit.bin"))
    expects.append(("Octakit window", raw))

peeks = []
if md:
    # The combined core-1 upload, in the payload format (24-bit LE words:
    # space, address, count, data; headers 3 and 4 first). Its P records
    # below 0x30000 and in the window are code the boot does not rewrite.
    up = (ROOT / "out/machinedrum/build/core1_upload.bin").read_bytes()
    w = lambda o: up[o] | up[o + 1] << 8 | up[o + 2] << 16
    o = 6 if up[0] == 3 else 0
    o += 6 if up[o] == 4 else 0
    recs = []
    while w(o) <= 2:
        recs.append((w(o), w(o + 3), [w(o + 9 + 3 * i) for i in range(w(o + 6))]))
        o += 9 + 3 * w(o + 6)
    glue = {l.split()[0]: int(l.split()[1], 16) for l in
            (ROOT / "out/machinedrum/build/glue.sym").read_text().splitlines() if l.strip()}
    for start in (0x591, 0x1F00, 0x34000, 0x36000):
        # The LAST record over an address wins: stock B's own effect records
        # at P:0x591.. load first and the MD's overwrite them.
        rec = [r for r in recs if r[0] == 0 and r[1] <= start < r[1] + len(r[2])]
        if not rec:
            sys.exit(f"verify_dram_boot: no P record at {start:05x} in the core-1 upload")
        words = rec[-1][2][start - rec[-1][1]:start - rec[-1][1] + 64]
        peeks.append((f"1:P:0x{start:x},{len(words)}", f"core 1 P:{start:05x}", words))
    md_id = registry.by_key("MACHINEDRUM").menu.fx2_id
    peeks.append((f"1:X:0x{0x215 + md_id:x},1", "core 1 dispatch init", [glue["gfxinit"]]))
    peeks.append((f"1:X:0x{0x235 + md_id:x},1", "core 1 dispatch proc", [glue["gfxproc"]]))

args = [str(EMU), "--image", str(IMAGE), "--max", "80000000",
        "--watch-pc", f"0x{entry:x},0x{fatal:x}"]
if dumps:
    args += ["--mem-dump", ";".join(f"0x{a:x},{n}={p}" for a, n, p in dumps)]
if peeks:
    args += ["--dsp", "--dsp-peek", ";".join(s for s, _l, _w in peeks)]
r = subprocess.run(args, capture_output=True, text=True, cwd=ROOT)
out = r.stdout
handoff = "HANDOFF" in out
hits = [l for l in out.splitlines() if l.strip().startswith("[") and " at 0x" in l]
entry_hits = sum(1 for l in hits if f"at 0x{entry:x}" in l)
fatal_hits = sum(1 for l in hits if f"at 0x{fatal:x}" in l)
ok = handoff and entry_hits == 1 and fatal_hits == 0
print(f"  [{'PASS' if ok else 'FAIL'}] verify_dram_boot: {remix.name} boots to the handoff; "
      f"loader ran {entry_hits}x, its fatal hang {fatal_hits}x")
for (a, n, p), (label, raw) in zip(dumps, expects):
    got = p.read_bytes() if p.exists() else b""
    diff = [i for i in range(min(len(got), len(raw))) if got[i] != raw[i]]
    fine = len(got) == len(raw) and len(diff) <= 16
    ok &= fine
    print(f"  [{'PASS' if fine else 'FAIL'}] verify_dram_boot: {label} at 0x{a:08x} == linked "
          f"runtime ({n:,} B) except {len(diff)} byte(s) the runtime wrote itself"
          + (f" at +{diff[0]:#x}.." if diff else ""))
for spec, label, want in peeks:
    core, space, rest = spec.split(":", 2)
    addr = int(rest.split(",")[0], 16)
    line = next((l for l in out.splitlines()
                 if l.strip().startswith(f"core {core} {space}:{addr:#07x}:")), "")
    got = [int(x, 16) for x in line.split(":", 2)[-1].split()] if line else []
    fine = got == want
    ok &= fine
    print(f"  [{'PASS' if fine else 'FAIL'}] verify_dram_boot: {label} == the core-1 upload "
          f"({len(want)} word(s))" + ("" if fine else f": got {[hex(x) for x in got[:4]]}.."))
sys.exit(0 if ok else 1)
