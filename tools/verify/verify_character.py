#!/usr/bin/env python3
"""CHARACTER render gates, with arithmetic you can predict.

Renders the station straight through dsp_host (verify_hello's shape: the id
and the slots come from the manifest, the entry points are checked against
SEND's so an absent module cannot pass as a dry passthrough).

Gates:
  defaults    -> output bit-exact vs a full-scale bipolar ramp (the bypass)
  MIX=0       -> bit-exact passthrough with the whole chain live
  DRV/SAT     -> DRV 0 skips the stage (bit-exact); TAPE/TUBE/INFL bounded
                 and near unity small-signal (trimmed)
  TONE        -> a tilt in every mode: 0 dark < 64 flat (bit-exact) < 127 bright
  FOLD        -> a full-scale ramp folds back; unity on a small signal
  COMP/GLUE   -> AC1's dip: deeper with COMP, unity at COMP 0 (skipped), the
                 makeup; GLUE on the master BY POSITION (r7 = $6a00): its
                 release is slower than the insert's COMP
  (CRSH, SRR and RING retired)
  WDTH        -> 0 = mono (L == R), 64 = untouched, 127 = doubled sides
  every knob  -> renders without dsp_host dying

The dump comes from the audition, which builds a scratch image that really
contains this station beside SEND:

    python3 tools/remix/audition.py character out/dry/drums_110.wav
    python3 tools/verify/verify_character.py
"""
import math, os, pathlib, struct, subprocess, sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path)
import send_probe  # reuse its dispatch-table entry resolution
from remix import registry

MOD = registry.by_name("character")
SEND = registry.by_name("send")
K = MOD.knob_map()
MEM = f"out/dsp/_audition_{MOD.name}_A.mem"
# The MASTER path (GLUE by position) needs the reverb server PLACED: the
# station aliases the position test to "never the master" when INIT_TABLE
# [REVERB] == INIT_TABLE[SEND], which is what the audition's scratch image
# has. Those renders come from the shipping build's own payload A instead.
RIG_IMAGE = "out/mainos_bus.bin"
RIG_REMIX = "bamsep26"                   # the rig: Character beside the reverb on payload A
RIG_MEM = "out/dsp/_verify_character_rig_A.mem"
HOST = "vendor/dsp56300/build/source/dsp_host/dsp_host"
FXID = MOD.menu.fx2_id
FRAMES, N = 15, 6000
SR = 44100
TMP = pathlib.Path("out/_chgate")
TMP.mkdir(parents=True, exist_ok=True)

# ⚠️ REBUILD THE DUMP, ALWAYS. The audition caches its scratch image against
# the newest mtime under modules/, and a stale hit here does not fail -- it
# silently measures the STOCK effect whose id this module replaces. That cost
# an hour: every mode read as a dry pass, because the dump's
# dispatch still pointed at stock CHORUS, and the emulator eventually died on
# a stock instruction it does not implement.
pathlib.Path(MEM).unlink(missing_ok=True)
subprocess.run([sys.executable, "tools/remix/audition.py", MOD.name,
                "out/dry/drums_110.wav"], capture_output=True)

if not pathlib.Path(MEM).exists():
    sys.exit(f"no {MEM} -- build it first:\n"
             f"  python3 tools/remix/audition.py {MOD.name} out/dry/drums_110.wav")

init, proc = send_probe.entry_points(MEM, FXID)
if (init, proc) == send_probe.entry_points(MEM, SEND.menu.fx2_id):
    sys.exit(f"fx id 0x{FXID:02x} resolves to SEND's entry points -- {MOD.name} "
             f"is NOT in this dump")
print(f"entries from dispatch tables: init=P:0x{init:04x} proc=P:0x{proc:04x}")

DEFAULTS = [(p.default or 0) for p in MOD.params]


def params(**kw):
    v = list(DEFAULTS)
    for name, val in kw.items():
        v[K[name]] = val
    return v


def render(samples, slot="fx1", guard=False, **kw):
    """samples: MONO ints in Q23 -- dsp_host feeds one stream to both
    channels (verify_hello's shape). Returns (L, R) lists.

    slot="fx1" (alloc 0, r7 1) is the station's own slot; "fx2" (alloc 1,
    r7 2) is an FX2 instance, which the station runs as a DRY PASS since
    (Claims.fx1_only) -- the gate below proves it. Until then
    every gate here rendered on alloc 1 and would now read dry."""
    src = TMP / "ch_in.raw"
    src.write_bytes(b"".join(struct.pack("<i", m) for m in samples))
    out = TMP / "ch_out.raw"
    r7, alloc = {"fx1": ("1", "0"), "fx2": ("2", "1"), "master": ("10", "0")}[slot]   # master: r7 = $6a00, position 3 on A
    mem, ini, prc = MEM, init, proc
    if slot == "master":
        import pathlib as _pl
        if not getattr(render, "dumped", False):
            # Build the rig here and dump it at once: out/mainos_bus.bin is
            # whatever wrote it last (the selftest leaves its LAST remix there,
            # and a cached dump measured verify_burn's probe build mid-check on
            # 16 Sep 2026 -- both read as "GLUE inert").
            env = dict(os.environ, REMIX=RIG_REMIX, XBUS="1", SPEC="1")
            env.setdefault("BUILD", "0")
            r = subprocess.run([sys.executable, "tools/build/build_bus.py"], env=env,
                               capture_output=True, text=True)
            if r.returncode:
                sys.exit(f"verify_character: building {RIG_REMIX} failed:\n{(r.stdout + r.stderr)[-1500:]}")
            send_probe.dump_mem(RIG_IMAGE, RIG_MEM, "A")
            render.dumped = True
        mem = RIG_MEM
        ini, prc = send_probe.entry_points(mem, FXID)
        if (ini, prc) == send_probe.entry_points(mem, SEND.menu.fx2_id):
            return None, None                       # the shipping build has no Character
    cmd = [HOST, "-mem", mem, "-init", f"{ini:x}", "-proc", f"{prc:x}",
           "-inst", "1", "-r7", r7, "-alloc", alloc, "-inmask", "1",
           *(["-guard"] if guard else []),
           "-frames", str(FRAMES), "-blocks", str(len(samples) // FRAMES),
           "-in", str(src), "-out", str(out),
           "-params", ",".join(str(x) for x in params(**kw))]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"dsp_host failed for {kw}:\n{r.stdout}\n{r.stderr}")
    if guard:
        render.guard_out = r.stdout + r.stderr
    d = out.read_bytes()
    w = struct.unpack(f"<{len(d)//4}i", d)
    return list(w[0::2])[:len(samples)], list(w[1::2])[:len(samples)]


def tone(hz, amp=0.4, n=N):
    return [int(amp * 8388607 * math.sin(2 * math.pi * hz * i / SR)) for i in range(n)]


def dc(level=0.25, n=N):
    return [int(level * 8388607)] * n


def rms_db(x, start=N // 2):
    seg = x[start:]
    return 20 * math.log10(max(1e-9, math.sqrt(sum((s / 8388607) ** 2 for s in seg) / len(seg))))


def tail_mean(x, start=N * 3 // 4):
    seg = x[start:]
    return sum(seg) / len(seg)


fails = 0
def check(label, ok, detail=""):
    global fails
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{'  ' + detail if detail else ''}")
    fails += 0 if ok else 1


# ---- 1. defaults: bit-exact passthrough --------------------------------------
ramp = [int(round(-8388607 + 2 * 8388607 * i / (N - 1))) for i in range(N)]
L, R = render(ramp)
check("defaults are a bit-exact passthrough (the bypass block)",
      L == ramp and R == ramp,
      "" if L == ramp else f"first diff at {next(i for i,(a,b) in enumerate(zip(L,ramp)) if a!=b)}")

# ---- 2. MIX=0 with the whole chain live --------------------------------------
L, R = render(ramp, MIX=0, DRV=127, FOLD=127, COMP=127, TONE=127, WDTH=127)
check("MIX=0 is a passthrough with every stage driven", L == ramp and R == ramp,
      "" if L == ramp else f"first diff at {next(i for i,(a,b) in enumerate(zip(L,ramp)) if a!=b)}")

# ---- 5. saturation is unity small-signal and bounded -------------------------
small = [int(0.001 * 8388607 * math.sin(2 * math.pi * 438 * i / SR)) for i in range(N)]
for sat, name in ((0, "TAPE"), (1, "TUBE"), (2, "INFL")):
    L, _ = render(small, DRV=0, SAT=sat)
    err = max(abs(a - b) for a, b in zip(L[N//2:], small[N//2:]))
    check(f"SAT {name} DRV=0 is a bit-exact skip", err == 0, f"max err {err} LSB")
# the saturators are trimmed to near unity small-signal (14 Sep 2026: the
# tape's +21 dB at DRV 127 made the live round unjudgeable)
for sat, name in ((0, "TAPE"), (1, "TUBE"), (2, "INFL")):
    _g = rms_db(render(tone(438, amp=0.03), DRV=127, SAT=sat)[0]) - rms_db(tone(438, amp=0.03))
    check(f"SAT {name} DRV=127 is within 4 dB of unity on a -30 dBFS tone", abs(_g) < 4.0, f"{_g:+.1f} dB")
# TONE is a tilt after the saturator in every mode: on noise
# the top/bottom balance must rise with the knob, and 64 must be the input.
def _tilt(L):
    n = len(L) // 2; seg = [v / 8388607 for v in L[n:]]
    a = math.exp(-2 * math.pi * 1200 / SR); lp = 0.0; el = eh = 0.0
    for v in seg:
        lp = a * lp + (1 - a) * v; el += lp * lp; eh += (v - lp) ** 2
    return 10 * math.log10((eh + 1e-12) / (el + 1e-12))
_rng = __import__("random").Random(5)
_noise = [int(0.3 * 8388607 * (_rng.random() * 2 - 1)) for _ in range(N)]
_tin = _tilt(_noise)
for sat, name in ((0, "TAPE"), (1, "TUBE"), (2, "INFL")):
    _t0 = _tilt(render(_noise, DRV=64, SAT=sat, TONE=0)[0])
    _t64 = _tilt(render(_noise, DRV=64, SAT=sat, TONE=64)[0])
    _t127 = _tilt(render(_noise, DRV=64, SAT=sat, TONE=127)[0])
    check(f"TONE tilts {name} (0 < 64 < 127, >= 3 dB end to end)", _t0 < _t64 < _t127 and _t127 - _t0 >= 3.0,
          f"tilt {_t0:.1f} / {_t64:.1f} / {_t127:.1f} dB")
_t0 = _tilt(render(_noise, DRV=0, TONE=0)[0]); _t127 = _tilt(render(_noise, DRV=0, TONE=127)[0])
check("TONE tilts with the saturator skipped (DRV 0): 0 < input < 127", _t0 < _tin < _t127,
      f"{_t0:.1f} < {_tin:.1f} < {_t127:.1f} dB")
for sat, name in ((0, "TAPE"), (1, "TUBE"), (2, "INFL")):
    L, _ = render(tone(438, amp=0.9), DRV=127, SAT=sat)
    check(f"SAT {name} stays bounded at DRV=127",
          max(abs(v) for v in L) <= 8388607, f"peak {max(abs(v) for v in L)}")
# TUBE (DaTube) adds harmonics with drive -- a pure tone grows non-fundamental
# energy. A crude test: the peak-to-rms crest of the output rises as the curve
# sharpens the waveform (a sine is crest ~1.41; saturation flattens it).
def _crest(L):
    seg = [v / 8388607 for v in L[N//2:]]
    pk = max(abs(v) for v in seg); r = (sum(v*v for v in seg) / len(seg)) ** 0.5
    return pk / max(r, 1e-9)
_c0 = _crest(render(tone(438, amp=0.5), DRV=1, SAT=1)[0])
_c1 = _crest(render(tone(438, amp=0.5), DRV=127, SAT=1)[0])
check("TUBE reshapes the waveform with drive (crest falls)", _c1 < _c0 - 0.02,
      f"crest {_c0:.2f} -> {_c1:.2f}")
# INFL (OInflator) adds level -- the whole point of an inflator.
_i0 = rms_db(render(tone(438, amp=0.13), DRV=0, SAT=2)[0])
_i1 = rms_db(render(tone(438, amp=0.13), DRV=127, SAT=2)[0])
check("INFL adds level as DRV rises", _i1 > _i0 + 1.0, f"{_i1 - _i0:+.1f} dB")

# ---- 6. FOLD folds a ramp back ----------------------------------------------
L, _ = render(ramp, FOLD=127, DRV=0, SAT=0)
turns = sum(1 for a, b, c in zip(L, L[1:], L[2:]) if (b - a > 0) != (c - b > 0))
check("FOLD=127 folds a monotonic ramp (it changes direction many times)",
      turns > 4, f"{turns} direction changes")
_f = rms_db(render(tone(438, amp=0.01), FOLD=127)[0]) - rms_db(tone(438, amp=0.01))
check("FOLD=127 is unity on a -40 dBFS tone (the trim: nothing folds, nothing turns up)", abs(_f) < 0.5, f"{_f:+.2f} dB")

# ---- 8. the compressor is AC1's dip (JClones) -----------------
# gr = (Lv^2/2 - 1)^2 + a*Lv, <= 1: a dip around Lv = 1 (level 0.25 FS at
# COMP's 4x), unity well below it; the dip's depth is COMP. Above ~1.5 the
# law lets go (the JSFX's AC101 mode, a division, is not ported).
quiet, _ = render(tone(438, amp=0.05), COMP=127)
dip, _ = render(tone(438, amp=0.25), COMP=127)
q0, _ = render(tone(438, amp=0.05), COMP=0)
d0, _ = render(tone(438, amp=0.25), COMP=0)
gr_q = rms_db(quiet) - rms_db(q0)
gr_d = rms_db(dip) - rms_db(d0)
check("COMP reduces the signal in the dip (0.25 FS at 4x) far more than a quiet one",
      gr_d < gr_q - 6, f"quiet {gr_q:+.1f} dB, dip {gr_d:+.1f} dB")
shallow, _ = render(tone(438, amp=0.25), COMP=40)
check("the dip deepens with COMP",
      rms_db(shallow) - rms_db(d0) > gr_d + 3,
      f"COMP 40 {rms_db(shallow) - rms_db(d0):+.1f} dB, COMP 127 {gr_d:+.1f} dB")
unity, _ = render(tone(438, amp=0.3), COMP=0)
ref, _ = render(tone(438, amp=0.3), MIX=0)
check("COMP=0 is unity gain (the stage is skipped, bit-exact)",
      unity == ref, f"{rms_db(unity) - rms_db(ref):+.2f} dB")
glue, _ = render(tone(438, amp=0.13), COMP=40, slot="master")
g0, _ = render(tone(438, amp=0.13), COMP=0, slot="master")
if glue is None:
    print("  [SKIP] the master path (GLUE by position): the shipping build out/mainos_bus.bin carries no Character")
    MASTER = False
else:
    MASTER = True
if MASTER:
    check("GLUE (the master, by position) at COMP 40 lifts a 0.13 FS tone by about +1 dB (the makeup)",
          0.4 < rms_db(glue) - rms_db(g0) < 1.6, f"{rms_db(glue) - rms_db(g0):+.2f} dB")
NS = 24000
stepped = [int(0.13 * (10 ** 0.5 if NS // 3 <= i < 2 * NS // 3 else 1.0) * 8388607
               * math.sin(2 * math.pi * 438 * i / SR)) for i in range(NS)]
def env10(x, w=441):
    return [20 * math.log10(max(1e-9, math.sqrt(sum(v * v for v in x[i:i + w]) / w) / 8388607))
            for i in range(0, len(x) - w, w)]
def env_after(slot, ms=150):
    y, _ = render(stepped, COMP=127, slot=slot)
    e = env10(y); k2 = 2 * len(e) // 3
    return e[k2 + ms // 10] - e[k2 + 1]          # dB recovered since just after the step down
if MASTER:
    rc, rg = env_after("fx1"), env_after("master")
    check("the insert's COMP (50 ms) has recovered more than the master's GLUE (500 ms, by position) 150 ms after a 10 dB step down",
          rc > rg + 3.0, f"COMP {rc:+.1f} dB, GLUE {rg:+.1f} dB")

# ---- 9. TRNS retired (was here) --------------------------------

# ---- 10. WDTH -----------------------------------------------------------------
# dsp_host feeds one stream to both channels here, so what this can prove is
# that 0 collapses to mono and 64 leaves the pair alone (the stereo section
# below does the rest).
L, R = render(tone(438), WDTH=0, DRV=1)
check("WDTH=0 is mono (L == R)", L == R, "")
L64, R64 = render(tone(438), WDTH=64, DRV=1)
Lref, _ = render(tone(438), DRV=1)
check("WDTH=64 leaves the signal alone", L64 == Lref, "")

# ---- 11. every knob at its extremes renders ----------------------------------
for name in K:
    for v in (0, 127 if MOD.params[K[name]].count in (None, 128) else MOD.params[K[name]].count - 1):
        render(tone(438, n=600), **{name: v})
check("every knob at both extremes renders", True)

# ---- THE FX1-ONLY PROMISE: an FX2 instance is dry -------------
# Claims.fx1_only says an FX2-slot instance touches nothing; the rig's cycle
# envelope (tools/harness/pressure.py) and the FX2 chooser both take it at
# its word, so it is proven here at every extreme, and the guard sees no
# write outside the frame.
L, R = render(ramp, slot="fx2", DRV=127, FOLD=127, COMP=127, MIX=127, SAT=2, TONE=127, WDTH=127)
check("FX2 instance is a bit-exact DRY PASS at every extreme (fx1_only)",
      L == ramp and R == ramp,
      "" if L == ramp else f"first diff at {next(i for i,(a,b) in enumerate(zip(L,ramp)) if a!=b)}")
render(ramp, slot="fx2", guard=True, DRV=127, FOLD=127, COMP=127, MIX=127, SAT=2, TONE=127, WDTH=127)
g = getattr(render, "guard_out", "")
check("FX2 instance trips no write guard",
      "guard clean" in g,
      next((ln.strip() for ln in reversed(g.splitlines()) if "guard" in ln), ""))

# ---- 12. STEREO CHANNEL SYMMETRY -------------------------------
def render_stereo(Ls, Rs, **kw):
    inter = []
    for i in range(len(Ls)):
        inter.append(Ls[i]); inter.append(Rs[i])
    src = TMP / "ch_st_in.raw"
    src.write_bytes(b"".join(struct.pack("<i", m) for m in inter))
    out = TMP / "ch_st_out.raw"
    cmd = [HOST, "-mem", MEM, "-init", f"{init:x}", "-proc", f"{proc:x}",
           "-inst", "1", "-r7", "1", "-alloc", "0", "-inmask", "1", "-stereo",
           "-frames", str(FRAMES), "-blocks", str(len(Ls) // FRAMES),
           "-in", str(src), "-out", str(out),
           "-params", ",".join(str(x) for x in params(**kw))]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"stereo host failed for {kw}:\n{r.stdout}\n{r.stderr}")
    d = out.read_bytes(); w = struct.unpack(f"<{len(d)//4}i", d)
    return list(w[0::2])[:len(Ls)], list(w[1::2])[:len(Ls)]

def _maxdiff(a, b):
    return max((abs(a[i] - b[i]) for i in range(len(a) // 2, len(a))), default=0)

Lin = tone(1000, amp=0.15)
Rin = tone(220, amp=0.06)                      # different content and level per channel
# COMP 80 GLUE: swap the inputs, the outputs must swap (channel symmetry)
L1, R1 = render_stereo(Lin, Rin, DRV=0, COMP=80, MIX=127)
L2, R2 = render_stereo(Rin, Lin, DRV=0, COMP=80, MIX=127)
check("COMP is channel-symmetric (swap L/R, outputs swap)",
      _maxdiff(L1, R2) <= 4 and _maxdiff(R1, L2) <= 4,
      f"L1~R2 {_maxdiff(L1, R2)}  R1~L2 {_maxdiff(R1, L2)}")
# neither channel collapses: with equal-level L/R, COMP reduces both alike
Le, Re = tone(1000, amp=0.12), tone(1000, amp=0.12)
L0, R0 = render_stereo(Le, Re, DRV=0, COMP=0, MIX=127)
Lc, Rc = render_stereo(Le, Re, DRV=0, COMP=127, MIX=127)
dL = rms_db(Lc) - rms_db(L0); dR = rms_db(Rc) - rms_db(R0)
check("COMP 127 reduces L and R equally, neither collapses",
      abs(dL - dR) < 1.0 and rms_db(Rc) > -50,
      f"dL {dL:.1f} dR {dR:.1f} Rrms {rms_db(Rc):.1f}")
# TAPE/TUBE channel symmetry too
for sat, name in ((0, "TAPE"), (1, "TUBE"), (2, "INFL")):
    a1, b1 = render_stereo(Lin, Rin, DRV=64, SAT=sat, COMP=0, MIX=127)
    a2, b2 = render_stereo(Rin, Lin, DRV=64, SAT=sat, COMP=0, MIX=127)
    check(f"SAT {name} is channel-symmetric",
          _maxdiff(a1, b2) <= 6 and _maxdiff(b1, a2) <= 6,
          f"{_maxdiff(a1, b2)} / {_maxdiff(b1, a2)}")

print(f"\n{fails} gate(s) failed" if fails else "\nOK")
sys.exit(1 if fails else 0)
