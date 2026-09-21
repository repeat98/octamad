#!/usr/bin/env python3
"""Which r7 slots a DSP module writes: fill its instance block with a marker,
render it under dsp_host with a tone through its own SEND (or the first knob
named), and read the block back.

    python3 tools/harness/slot_census.py "DELAY SERVER" [blocks] [--image out/mainos_bus.bin]

Prints the raw slots written and the ones untouched below $90. A displacement
scan of the source misses pointer walks, the build's substituted bodies and
unpadded spellings (`x:(r7-$b)` is raw $3e in BusDelay's rebased region); this
reads the memory. 21 Sep 2026: found GRAIN's pitch words at $3e/$3f under a
relocation that a scan had called free.
"""
import math, pathlib, re, struct, subprocess, sys, tempfile
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa
import send_probe  # noqa
from remix import registry  # noqa
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "verify"))
import verify_dirtystate as vd  # noqa

key = sys.argv[1] if len(sys.argv) > 1 else "DELAY SERVER"
blocks = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 1200
image = pathlib.Path(sys.argv[sys.argv.index("--image") + 1]) if "--image" in sys.argv else pathlib.Path("out/mainos_bus.bin")
mod = registry.by_key(key)
tmp = pathlib.Path(tempfile.mkdtemp())
pl = "B" if mod.dsp and getattr(mod.dsp, "payload", None) == "B" else None
mem = init = proc = None
for p in ("B", "A"):
    m = send_probe.dump_mem(image, tmp / f"{p}.mem", p)
    try:
        init, proc = send_probe.entry_points(m, mod.menu.fx2_id); mem = m; pl = p; break
    except Exception:
        continue
if mem is None: sys.exit(f"{key}: no entry points in either payload")
params = [(p.default or 0) for p in mod.params]
km = mod.knob_map_all()
for k in ("SEND", "MIX", "WET"):
    if k in km: params[km[k]] = 100; break
FILL = 0x123456
filled = vd.mem_with_fill(mem, FILL, tmp / "fill.mem")
n = vd.FRAMES * blocks
tone = b"".join(struct.pack("<ii", *([int(0.3 * 8388607 * math.sin(2 * math.pi * 438 * i / 44100))] * 2)) for i in range(n))
src = tmp / "in.raw"; src.write_bytes(tone); out = tmp / "out.raw"
peek = ",".join(f"{vd.R7 + i:x}" for i in range(0x100))
cmd = [str(vd.HOST), "-mem", str(filled), "-init", f"{init:x}", "-proc", f"{proc:x}", "-inst", "1", "-r7", "1",
       "-alloc", "0", "-inmask", "1", "-stereo", "-frames", str(vd.FRAMES), "-blocks", str(blocks),
       "-in", str(src), "-out", str(out), "-params", ",".join(str(x) for x in params), "-peekx", peek]
r = subprocess.run(cmd, capture_output=True, text=True); txt = r.stdout + r.stderr
if r.returncode: sys.exit(f"dsp_host exit {r.returncode}: {txt[-300:]}")
vals = {int(m.group(1), 16): int(m.group(2), 16) for m in re.finditer(r"X:0x([0-9a-f]+) = 0x([0-9a-f]+)", txt)}
written = sorted(a - vd.R7 for a, v in vals.items() if vd.R7 <= a < vd.R7 + 0x100 and v != FILL)
nz = [l for l in txt.splitlines() if "non-zero output" in l]
print(f"{key} on payload {pl}, {blocks} blocks; {nz[0].strip() if nz else ''}")
print("written (raw):  ", " ".join(f"{s:02x}" for s in written))
print("untouched < $90:", " ".join(f"{s:02x}" for s in range(0x90) if s not in written))
high = [s for s in written if s >= 0x84]
print("at $84 or above:", " ".join(f"{s:02x}" for s in high) if high else "none")
