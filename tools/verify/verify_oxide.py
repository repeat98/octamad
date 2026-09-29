#!/usr/bin/env python3
"""OXIDE render gates: the DSP code against its bit-level twin, at 0 LSB.

modules/oxide/design.py carries the fitted tape model twice: `reference()`,
the float model the fit produced, and `fixed()`, every instruction of
oxide.asm replayed on integers. This gate holds the emulator's render to
`fixed()` exactly, so a mis-encoded instruction, a coefficient that drifted
from the design, a channel that reads the other's state or a stale
extension byte cannot pass; and it reports how far `fixed()` sits from
`reference()`, which is the price of 24 bits.

  1. the coefficient ring's order in oxide.asm is design.RING
  2. the source assembled alone and disassembled: no mpysu/macsu form, and
     every line comes back as written (dsp_asm drops XY parallel moves and
     re-encodes operand orders silently -- CLAUDE.md, DSP.md 8)
  3. renders in a scratch image that really contains OXIDE (the SEND-alias
     guard: an absent id renders a plausible passthrough), stereo with
     different material per channel, five knob settings, 16-frame blocks:
     every sample equal to design.fixed()
  4. silence in -> exact zeros out
  5. fixed() vs reference(): residual below -75 dB on drums and noise
  6. the per-sample instruction count from dsp_host's meter

    python3 tools/verify/verify_oxide.py
"""
import math
import pathlib
import random
import re
import struct
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path)
from remix import audition  # noqa: E402
import send_probe  # noqa: E402
from remix import registry  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "modules/oxide"))
import design  # noqa: E402

MOD = registry.by_name("oxide")
SEND = registry.by_name("send")
KNOBS = MOD.knob_map()
ASM = ROOT / MOD.dsp.asm
HOST = ROOT / "vendor/dsp56300/build/source/dsp_host/dsp_host"
DSPASM = ROOT / "vendor/dsp56300/build/source/dsp_host/dsp_asm"
DIS = ROOT / "vendor/dsp56300/build/source/disassemble/dsp56kDisassemble"
SR = 44100
FRAMES = 16                                   # the hardware's block
SCRATCH = pathlib.Path(tempfile.mkdtemp(prefix="verify_oxide."))

fails = 0


def gate(name, ok, detail=""):
    global fails
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))
    if not ok:
        fails += 1


# ---- 1. the coefficient ring ----------------------------------------------
# The numbers themselves reach the DSP through the P table (design.ptable())
# and the renders below would miss by thousands of LSB if one were wrong;
# what the renders cannot name is WHICH, so the order oxd_ch assumes, as its
# header documents it, is checked against design.RING here.
print("coefficient ring:")
doc = {}
for line in ASM.read_text().splitlines():
    if line.startswith(";"):
        for off, name in re.findall(r"\$(2[0-9a-f])\s+([A-Z][A-Z0-9]+)", line):
            doc[int(off, 16) - 0x20] = name
order = tuple(doc[i] for i in sorted(doc))
gate("the ring documented in oxide.asm is design.RING", order == design.RING,
     " ".join(order))
gate("no coefficient left as an immediate", "COEF" not in ASM.read_text())

# ---- 1b. the M registers leave linear ---------------------------------------
# proc may wrap m3 for the coefficient ring but must put it back before its
# last rts: the next effect on the core inherits it (dsp_host calls proc alone
# and cannot see this; Character restores its rings the same way).
print("address modes:")
body = [l.split(";")[0].strip() for l in ASM.read_text().splitlines()]
body = [l for l in body if l]
writes = [(i, l) for i, l in enumerate(body) if re.match(r"move\s+#.*,m[0-7]$", l)]
last = {}
for i, l in writes:
    last[l.split(",")[-1]] = l
bad = [f"{r}: {l}" for r, l in last.items() if not re.search(r"#>?\$f{6}\b", l)]
gate("every M register a proc writes ends linear ($ffffff)", not bad, "; ".join(bad) or ", ".join(sorted(last)))

# ---- 2. assemble alone, disassemble, compare --------------------------------
print("round trip:")
src_lines = []
for line in ASM.read_text().splitlines():
    code = line.split(";")[0].rstrip()
    if code.startswith((" ", "\t")) and code.strip() and code.split()[0] != "nop":
        src_lines.append(" ".join(code.split()))       # the disassembler does not print nops
subprocess.run([str(DSPASM), "-in", str(ASM), "-org", "1000", "-out", str(SCRATCH / "o.bin"),
                "-sym", str(SCRATCH / "o.sym")], check=True, capture_output=True)
dis = subprocess.run([str(DIS), "-in", str(SCRATCH / "o.bin"), "-pc", "1000", "-le"],
                     capture_output=True, text=True).stdout
dis_lines = [" ".join(l[8:].split(";")[0].split()) for l in dis.splitlines()
             if re.match(r"^[0-9a-f]{6}: ", l)]
su = [l for l in dis_lines if re.match(r"(mpy|mac)[r]?su|(mpy|mac)[r]?uu", l)]
gate("no mpysu / macsu in the module", not su, "; ".join(su))
labels = {n for n, _ in (l.split() for l in (SCRATCH / "o.sym").read_text().split("\n") if l)}


def norm(s):
    s = s.replace("#>", "#").replace(">", "").replace("<", "")
    return re.sub(r"\$0*([0-9a-f])", r"$\1", s.lower())


diffs = []
for s, d in zip(src_lines, dis_lines):
    if any(re.search(rf"\b{re.escape(lb)}\b", s) for lb in labels):
        if s.split()[0] != d.split()[0]:
            diffs.append(f"{s!r} -> {d!r}")
    elif norm(s) != norm(d):
        diffs.append(f"{s!r} -> {d!r}")
gate(f"{len(src_lines)} instructions come back as written",
     not diffs and len(src_lines) == len(dis_lines),
     "; ".join(diffs[:4]) or f"{len(dis_lines)} disassembled")

# ---- 3. renders -------------------------------------------------------------
print("renders (dsp_host vs design.fixed, 0 LSB):")
MEM = audition._ensure_insert_mem(MOD, log=lambda *a: None)
init, proc = send_probe.entry_points(str(MEM), MOD.menu.fx2_id)
if (init, proc) == send_probe.entry_points(str(MEM), SEND.menu.fx2_id):
    sys.exit(f"fx id 0x{MOD.menu.fx2_id:02x} resolves to SEND's entry points: "
             f"OXIDE is not in {MEM}")
print(f"  entries init=P:0x{init:04x} proc=P:0x{proc:04x} (fx id 0x{MOD.menu.fx2_id:02x})")


def q24(x):
    return [max(-8388608, min(8388607, round(v * 8388607))) for v in x]


def signals():
    """Stdlib only (the checks run on bare python3): kick + chord, noise,
    a full-scale ramp, sines at 40 Hz and 5 kHz."""
    rng = random.Random(7)
    n = SR // 2
    kick = [0.0] * n
    for k in range(0, n, SR // 8):
        for i in range(min(n - k, SR // 8)):
            tt = i / SR
            kick[k + i] += math.sin(2 * math.pi * (45 * tt + 90 * (1 - math.exp(-tt * 30)) / 30)) * math.exp(-tt * 9)
    chord = [0.25 * sum(math.sin(2 * math.pi * f * i / SR) for f in (220, 277, 330)) for i in range(n)]
    d = [a + b for a, b in zip(kick, chord)]
    pk = max(abs(v) for v in d); drums = [v / pk for v in d]
    noise = [max(-1.0, min(1.0, rng.gauss(0, 1) / 3)) for _ in range(n)]
    ramp = [-1 + 2 * i / (n - 1) for i in range(n)]
    sine = lambda f, a=1.0: [a * math.sin(2 * math.pi * f * i / SR) for i in range(n)]
    g12 = 10 ** (-12 / 20)
    return {"drums | noise": (drums, noise),
            "ramp | 40 Hz sine": (ramp, sine(40)),
            "5 kHz sine | drums -12 dB": (sine(5000), [v * g12 for v in drums])}


def render(L, R, knob_in, knob_out, meter=None):
    inp = SCRATCH / "in.raw"; out = SCRATCH / "out.raw"
    inp.write_bytes(b"".join(struct.pack("<ii", a, b) for a, b in zip(L, R)))
    params = [0] * 6
    params[KNOBS["IN"]] = knob_in; params[KNOBS["OUT"]] = knob_out
    cmd = [str(HOST), "-mem", str(MEM), "-init", f"{init:x}", "-proc", f"{proc:x}",
           "-inst", "1", "-r7", "2", "-alloc", "1", "-stereo",
           "-frames", str(FRAMES), "-blocks", str(len(L) // FRAMES),
           "-in", str(inp), "-out", str(out), "-params", ",".join(map(str, params))]
    if meter:
        cmd += ["-meter", str(meter)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"dsp_host failed:\n{r.stdout}\n{r.stderr}")
    w = struct.unpack(f"<{out.stat().st_size // 4}i", out.read_bytes())
    return list(w[0::2]), list(w[1::2])


SETTINGS = ((design.IN_ZERO, design.OUT_ZERO), (0, 0), (127, 127), (96, 64), (24, 100))
sigs = signals()
for name, (l, r) in sigs.items():
    L, R = q24(l), q24(r)
    n = len(L) // FRAMES * FRAMES
    L, R = L[:n], R[:n]
    for ki, ko in SETTINGS:
        oL, oR = render(L, R, ki, ko)
        eL, eR = design.fixed(L, ki, ko), design.fixed(R, ki, ko)
        errL = max(abs(a - b) for a, b in zip(oL, eL))
        errR = max(abs(a - b) for a, b in zip(oR, eR))
        first = next((i for i in range(n) if oL[i] != eL[i] or oR[i] != eR[i]), None)
        gate(f"{name:26s} IN {ki:3d} OUT {ko:3d}", errL == 0 and errR == 0,
             f"max |err| L {errL} R {errR} LSB" + (f", first at {first}" if first is not None else ""))

# ---- 4. silence --------------------------------------------------------------
print("silence:")
z = [0] * (FRAMES * 64)
oL, oR = render(z, z, 127, 127)
gate("silence in, IN 127 OUT 127: exact zeros out", not any(oL) and not any(oR))

# ---- 5. how far the 24-bit engine sits from the fitted model ----------------
print("fixed() vs the float model:")
try:
    import numpy as np
    import scipy  # noqa: F401  (design.reference needs it)
except ImportError:
    np = None
    print("  [SKIP] numpy/scipy not installed: the float model cannot run")
if np is not None:
    for name, x in (("drums 0 dBFS", sigs["drums | noise"][0]), ("noise", sigs["drums | noise"][1]),
                    ("drums -12 dBFS", sigs["5 kHz sine | drums -12 dB"][1])):
        xi = q24(x)
        fx = np.array(design.fixed(xi)) / 8388608.0
        rf = np.clip(design.reference(np.array(xi) / 8388608.0), -1, 1)   # the DSP's store limits
        s = slice(SR // 10, None)
        res = 20 * np.log10(np.std(fx[s] - rf[s]) / np.std(rf[s]))
        gate(f"{name:16s} residual below -75 dB", res < -75, f"{res:.1f} dB")

# ---- 6. cost -----------------------------------------------------------------
print("cost:")
meter = SCRATCH / "meter.txt"
L, R = q24(sigs["drums | noise"][0][:FRAMES * 64]), q24(sigs["drums | noise"][1][:FRAMES * 64])
render(L, R, 127, 127, meter=meter)
counts = [int(l.split()[1]) for l in meter.read_text().split("\n") if l.strip() and not l.startswith("#")]
per = max(counts) / FRAMES
print(f"  dsp_host meter: {max(counts)} instructions per {FRAMES}-frame block, max = {per:.1f} per stereo sample")

print("\nALL GATES PASSED" if fails == 0 else f"\n{fails} GATE(S) FAILED")
sys.exit(1 if fails else 0)
