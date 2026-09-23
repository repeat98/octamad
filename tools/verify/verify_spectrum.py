#!/usr/bin/env python3
"""SPECTRUM render gates, with arithmetic you can predict.

Renders the station straight through dsp_host (verify_hello's shape: the id
and the slots come from the manifest, the entry points are checked against
SEND's so an absent module cannot pass as a dry passthrough).

Gates:
  defaults    -> output bit-exact vs a full-scale bipolar ramp (the bypass)
  LP slope    -> a low cutoff: 2 kHz vs 4 kHz attenuate by ~12 dB/oct (2-pole)
  HP at DC    -> 0;   BP at DC -> 0;   NOTCH at DC -> DC (lp + hp = x)
  base/width  -> BASE up kills DC through B (SER); WDTH down kills 8 kHz
  RING at DC  -> A*B*2 with A = B = DC: 2*DC^2, to 1 LSB after settling
  VOWEL       -> renders, and differs across FREQ (A vs I)
  every knob  -> renders without dsp_host dying
  SEM core:
  four modes  -> LP/BP/HP/NTCH are four different responses at one FREQ/RES
  BP tracks   -> the BP peak sits on the FREQ taper (108 / 600 / 2983 Hz at
                 FREQ 32 / 64 / 96), tones a third of an octave either side lower
  taper top   -> FREQ 127 reaches 15 kHz: at RES 64 the LP peaks ABOVE 1 kHz
                 there (the old core's ceiling was 7.2 kHz)
  RES 127     -> bounded: a 0.5 FS tone at fc peaks below full scale and the
                 tail does not sit on the rails (it self-oscillates, it does not
                 latch); the same through the VOWL bank
  VOWL bank   -> five vowels: each F1 and F2 is a PEAK within a quarter octave
                 of the Peterson-Barney table, and each vowel is loudest at its
                 own F1 among the five
  LADR (13 Sep 2026, the linear zero-delay Moog ladder, MODE 5):
  4-pole      -> 2 kHz vs 4 kHz at FREQ 64 differ by ~24 dB (LP reads ~12)
  DC          -> DC (unity at RES 0);  distinct from LP: 4 kHz > 10 dB lower
  ISO         -> Capacitor2 tracks its transcription; LOW cut; ENV/LFO move the cutoff
  resonance   -> the tone at fc rises monotonically RES 0 < 64 < 100 < 127
  RES 127     -> bounded at 0.13 and 0.5 FS (below full scale, no rail)

The dump comes from the audition, which builds a scratch image that really
contains this station beside SEND:

    python3 tools/remix/audition.py spectrum out/dry/drums_110.wav
    python3 tools/verify/verify_spectrum.py
"""
import math, pathlib, struct, subprocess, sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path)
import send_probe  # reuse its dispatch-table entry resolution
from remix import registry

MOD = registry.by_name("spectrum")
SEND = registry.by_name("send")
K = MOD.knob_map()
MEM = f"out/dsp/_audition_{MOD.name}_A.mem"
HOST = "vendor/dsp56300/build/source/dsp_host/dsp_host"
FXID = MOD.menu.fx2_id
FRAMES, N = 15, 6000
SR = 44100
TMP = pathlib.Path("out/_fsgate")
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


LP = 1   # MODE 0 is LADR since 14 Sep 2026 ("moog is best, first in list")


def render(samples, slot="fx1", guard=False, **kw):
    """samples: MONO ints in Q23 -- dsp_host feeds one stream to both
    channels (verify_hello's shape). Returns (L, R) lists.

    slot="fx1" (alloc 0, r7 1) is the station's own slot; "fx2" (alloc 1,
    r7 2) is an FX2 instance, which the station runs as a DRY PASS since
    (Claims.fx1_only) -- the gate below proves it. Until then
    every gate here rendered on alloc 1 and would now read dry."""
    kw.setdefault("MODE", LP)
    src = TMP / "fs_in.raw"
    src.write_bytes(b"".join(struct.pack("<i", m) for m in samples))
    out = TMP / "fs_out.raw"
    r7, alloc = ("1", "0") if slot == "fx1" else ("2", "1")
    cmd = [HOST, "-mem", MEM, "-init", f"{init:x}", "-proc", f"{proc:x}",
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
L, R = render(ramp, MODE=0)
check("defaults are a bit-exact passthrough (the bypass block)",
      L == ramp and R == ramp,
      "" if L == ramp else f"first diff at {next(i for i,(a,b) in enumerate(zip(L,ramp)) if a!=b)}")

# ---- 2. LP slope: low cutoff, 2 kHz vs 4 kHz ---------------------------------
lo = rms_db(render(tone(2000), FREQ=30, RES=0)[0])
hi = rms_db(render(tone(4000), FREQ=30, RES=0)[0])
slope = lo - hi
check("LP is a 2-pole: 2 kHz vs 4 kHz differ by ~12 dB at FREQ=30",
      9 <= slope <= 15, f"{slope:.1f} dB/oct")

# ---- 3. DC through the modes --------------------------------------------------
d_lp = tail_mean(render(dc(), FREQ=64)[0])
d_bp = tail_mean(render(dc(), FREQ=64, MODE=2)[0])
dcv = int(0.25 * 8388607)
check("BP at DC -> 0", abs(d_bp) < 64, f"{d_bp:.0f} LSB")
check("LP at DC -> DC", abs(d_lp - dcv) < 256, f"{d_lp:.0f} vs {dcv}")
d_hp = tail_mean(render(dc(), FREQ=64, MODE=1, SHPE=127)[0])
check("SEM SHPE 127 (HP) at DC -> 0", abs(d_hp) < 64, f"{d_hp:.0f} LSB")
hp_hi = rms_db(render(tone(4000, 0.2), FREQ=64, MODE=1, SHPE=127)[0]) - rms_db(tone(4000, 0.2))
hp_lo = rms_db(render(tone(200, 0.2), FREQ=64, MODE=1, SHPE=127)[0]) - rms_db(tone(200, 0.2))
check("SEM SHPE 127 at FREQ=64 passes 4 kHz within 3 dB", abs(hp_hi) < 3, f"{hp_hi:.1f} dB")
check("SEM SHPE 127 at FREQ=64 cuts 200 Hz by more than 12 dB", hp_lo < -12, f"{hp_lo:.1f} dB")
d_nt = tail_mean(render(dc(), FREQ=64, MODE=1, SHPE=64)[0])
check("SEM SHPE 64 (notch) at DC -> DC", abs(d_nt - dcv) < 256, f"{d_nt:.0f} vs {dcv}")
nt_c = rms_db(render(tone(966, 0.2), FREQ=64, MODE=1, SHPE=64)[0]) - rms_db(tone(966, 0.2))
nt_hi = rms_db(render(tone(8000, 0.2), FREQ=64, MODE=1, SHPE=64)[0]) - rms_db(tone(8000, 0.2))
check("SEM SHPE 64 at FREQ=64 cuts its own cutoff by more than 10 dB", nt_c < -10, f"{nt_c:.1f} dB")
check("SEM SHPE 64 at FREQ=64 passes 8 kHz within 3 dB", abs(nt_hi) < 3, f"{nt_hi:.1f} dB")
lp0 = render(tone(1000, 0.2), FREQ=64, MODE=1)[0]; lp1 = render(tone(1000, 0.2), FREQ=64, MODE=1, SHPE=0)[0]
check("SEM SHPE 0 is the LP of before (MODE 1 default)", lp0 == lp1, "")

# ---- 4. ISO: Airwindows Capacitor2 ------------------------------
# LOW = FREQ (127 open), COLR = RES (the dielectric); no HIGH cut (option B). Against the
# transcription modules/spectrum/capacitor2_ref.py after its chase settles.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "modules/spectrum"))
import capacitor2_ref as _C2
_c_open = rms_db(render(tone(1000, 0.2), MODE=3, FREQ=127, RES=0)[0]) - rms_db(tone(1000, 0.2))
check("ISO open (LOW 127, COLR 0) passes 1 kHz at the plugin's trim, -2.1 dB (1.5/cbrt(7))", abs(_c_open + 2.1) < 1.0, f"{_c_open:+.2f} dB")
_c_lo = rms_db(render(tone(4000, 0.2), MODE=3, FREQ=40, RES=0)[0]) - rms_db(render(tone(100, 0.2), MODE=3, FREQ=40, RES=0)[0])
check("ISO LOW 40 cuts 4 kHz by > 12 dB against 100 Hz", _c_lo < -12, f"{_c_lo:.1f} dB")
for _f, _c in ((127, 0), (60, 64), (90, 127)):
    _src = tone(440, 0.3)
    _L, _ = render(_src, MODE=3, FREQ=_f, RES=_c)
    _ref = _C2.Capacitor2(_f / 128, 0.0, _c / 128, octabam=True); _rL, _ = _ref.process([v / 8388607 for v in _src], [v / 8388607 for v in _src])
    _me = sum(abs(_L[i] / 8388607 - _rL[i]) for i in range(N // 2, N)) / (N - N // 2)
    _lv = rms_db(_L) - 20 * math.log10(max(1e-9, math.sqrt(sum(v * v for v in _rL[N // 2:]) / (N - N // 2))))
    check(f"ISO LOW {_f} COLR {_c} tracks Capacitor2 (mean |err| < 0.02, level within 1 dB)",
          _me < 0.02 and abs(_lv) < 1.0, f"mean |err| {_me:.4f}, level {_lv:+.2f} dB")

# ---- 5. ENV and LFO onto the cutoff ---------
_quiet = rms_db(render(tone(3000, 0.02), FREQ=80, ENV=0)[0]) - rms_db(tone(3000, 0.02))
_loud = rms_db(render(tone(3000, 0.4), FREQ=80, ENV=0)[0]) - rms_db(tone(3000, 0.4))
check("ENV -64 closes the LP on a loud tone more than a quiet one (3 kHz at FREQ 80)", _loud < _quiet - 6, f"loud {_loud:.1f}, quiet {_quiet:.1f} dB")
_y, _ = render(tone(2000, 0.2), FREQ=64, LDP=127, LSP=110)
_w = [rms_db(_y[i:i + 400], 0) for i in range(N // 2, N - 400, 200)]
check("LDP +63 at LSP 110 sweeps the LP across a 2 kHz tone (> 6 dB swing)", max(_w) - min(_w) > 6, f"{max(_w) - min(_w):.1f} dB swing")
_y0, _ = render(tone(2000, 0.2), FREQ=64, RES=1)
_w0 = [rms_db(_y0[i:i + 400], 0) for i in range(N // 2, N - 400, 200)]
check("LDP 0 (64) leaves the level still (< 1 dB swing)", max(_w0) - min(_w0) < 1, f"{max(_w0) - min(_w0):.1f} dB swing")

# ---- 6. VOWEL renders and morphs ---------------------------------------------
va = rms_db(render(tone(1100), MODE=4, FREQ=0, RES=90)[0])     # A: F2 1090
vi = rms_db(render(tone(1100), MODE=4, FREQ=64, RES=90)[0])    # I: F2 2290
check("VOWEL A vs I differ at 1.1 kHz", abs(va - vi) > 3, f"A {va:.1f}  I {vi:.1f} dBFS")

# ---- 6b. the SEM core: two modes at one setting ----------------------------
# FREQ 64 is fc = 949 Hz on the taper (60 * 250^(64/128)); RES 64 is Q ~ 3.
lv = {m: {hz: rms_db(render(tone(hz, 0.2), FREQ=64, RES=64, MODE=m)[0])
          for hz in (100, 949, 4000)} for m in range(1, 3)}
check("LP passes 100 Hz and cuts 4 kHz by > 20 dB (FREQ 64)",
      lv[1][100] - lv[1][4000] > 20, f"{lv[1][100] - lv[1][4000]:.1f} dB")
check("BP peaks at 949 Hz, both skirts > 15 dB down",
      lv[2][949] - lv[2][100] > 15 and lv[2][949] - lv[2][4000] > 15,
      f"949 Hz {lv[2][949]:.1f}, 100 Hz {lv[2][100]:.1f}, 4 kHz {lv[2][4000]:.1f} dBFS")

# ---- 6c. the BP peak sits on the taper ----------------------------------------
# fc = 60 * 250^(FREQ/128): 239 / 949 / 3773 Hz. RES 100 is Q ~ 12 (+21 dB at
# fc), so the tone is small (0.02 FS) -- at 0.2 FS the peak would sit on the
# limiter and the skirts would read only a dB or two lower.
for freq, fc in ((32, 239), (64, 949), (96, 3773)):
    at = rms_db(render(tone(fc, 0.02), FREQ=freq, RES=100, MODE=2)[0])
    below = rms_db(render(tone(fc / 1.26, 0.02), FREQ=freq, RES=100, MODE=2)[0])
    above = rms_db(render(tone(fc * 1.26, 0.02), FREQ=freq, RES=100, MODE=2)[0])
    check(f"BP peak at FREQ {freq} is at {fc} Hz (a third-octave either side > 3 dB lower)",
          at - below > 3 and at - above > 3, f"{at:.1f} vs {below:.1f} / {above:.1f} dBFS")

# ---- 6d. the taper top: 15 kHz, no ceiling ------------------------------------
top = rms_db(render(tone(15000, 0.2), FREQ=127, RES=64)[0])
mid = rms_db(render(tone(1000, 0.2), FREQ=127, RES=64)[0])
check("FREQ 127 LP at RES 64 peaks at 15 kHz (louder than 1 kHz)", top > mid,
      f"15 kHz {top:.1f}, 1 kHz {mid:.1f} dBFS")

# ---- 6e. RES 127 is bounded ---------------------------------------------------
# RES 127 is R = 0.0149, Q ~ 34 (+30 dB at fc (949 Hz)). A 0.02 FS tone at fc (949 Hz) comes out
# near -7 dBFS in a linear core: below full scale, never on a rail. A 0.5 FS
# tone at fc (949 Hz) clips in ANY linear SVF (the float reference too); what the core
# owes there is to clamp and let go -- the burst stops and the tail decays,
# no state latched on a rail.
def bounded(label, out):
    tail = out[N // 2:]
    pk = max(abs(v) for v in tail)
    rail = sum(1 for v in tail if abs(v) >= 0x7ffff0) / len(tail)
    check(label, pk < 0x7ffff0 and rail < 0.01,
          f"peak {20 * math.log10(max(pk, 1) / 8388607):+.1f} dBFS, {rail * 100:.2f}% of the tail on a rail")
bounded("RES 127 LP at fc (949 Hz), 0.02 FS in: below full scale, never on the rails",
        render(tone(949, 0.02), FREQ=64, RES=127)[0])
bounded("RES 127 BP at fc (949 Hz), 0.02 FS in: below full scale, never on the rails",
        render(tone(949, 0.02), FREQ=64, RES=127, MODE=2)[0])
bounded("RES 127 VOWL a at F1, 0.1 FS in (x8 makeup): below full scale, never on the rails",
        render(tone(730, 0.1), FREQ=0, RES=127, MODE=4)[0])
burst = tone(949, 0.5, N // 2) + [0] * (N // 2)
for m, mn in ((1, "LP"), (2, "BP")):
    out = render(burst, FREQ=64, RES=127, MODE=m)[0]
    hit = max(abs(v) for v in out[N // 4:N // 2]) >= 0x7ffff0
    # Q ~ 34 at 600 Hz rings with tau = Q / (pi fc) = 18 ms = 794 samples, so
    # each eighth of the render (750 samples) after the burst is ~8 dB quieter
    # than the one before; a latched state would hold level.
    e7 = 20 * math.log10(max(1e-9, math.sqrt(sum((v / 8388607) ** 2 for v in out[N * 6 // 8:N * 7 // 8]) / (N // 8))))
    e8 = rms_db(out, start=N * 7 // 8)
    check(f"RES 127 {mn}: a 0.5 FS burst at fc (949 Hz) clips, then lets go (rings down ~8 dB per 17 ms)",
          hit and e8 < e7 - 5 and e8 < -20,
          f"{'clipped' if hit else 'NOT clipped'}, seventh eighth {e7:.1f}, last {e8:.1f} dBFS")

# ---- 6f. the VOWL bank: five vowels on the Peterson-Barney table --------------
VOWELS = (("a", 0, 730, 1090), ("e", 32, 530, 1840), ("i", 64, 270, 2290),
          ("o", 96, 570, 840), ("u", 127, 300, 870))
own = {}
for name, freq, f1, f2 in VOWELS:
    for fn, fk in (("F1", f1), ("F2", f2)):
        at = rms_db(render(tone(fk, 0.2), FREQ=freq, RES=100, MODE=4)[0])
        lo_ = rms_db(render(tone(fk / 1.19, 0.2), FREQ=freq, RES=100, MODE=4)[0])
        hi_ = rms_db(render(tone(fk * 1.19, 0.2), FREQ=freq, RES=100, MODE=4)[0])
        check(f"VOWL {name} {fn} is a peak at {fk} Hz (a quarter octave either side lower)",
              at > lo_ and at > hi_, f"{at:.1f} vs {lo_:.1f} / {hi_:.1f} dBFS")
        if fn == "F1":
            own[name] = at
    others = [rms_db(render(tone(o1, 0.2), FREQ=freq, RES=100, MODE=4)[0])
              for on, _, o1, _ in VOWELS if on != name]
    check(f"VOWL {name} is loudest at its own F1 among the five", own[name] > max(others),
          f"own {own[name]:.1f}, best other {max(others):.1f} dBFS")

# ---- 6g. LADR: the linear zero-delay Moog ladder ----------------
# MODE 5 is the 4-pole (audiojs/filter moogLadder without its tanh): 24 dB/oct
# where LP is 12, resonance k = 4 * 0.975 * RES/128 (the linear ladder
# oscillates at k = 4), bounded at RES 127 by the limiting stores. Proven
# against a float reference of the same equations (levels to
# 0.01 dB, peak error < 0.01 FS at the self-oscillating edge); these gates pin
# the shape so a regression shows.
# Measured at FREQ 64 (fc 949 Hz since the 60 Hz floor), not the LP gate's FREQ 30: four poles put
# 2 kHz 100 dB under fc = 109 Hz, below the 24-bit floor, and both tones read
# the floor (the first draft of this gate measured -0.0 dB/oct that way).
l_lo = rms_db(render(tone(2000), FREQ=64, RES=0, MODE=0)[0])
l_hi = rms_db(render(tone(4000), FREQ=64, RES=0, MODE=0)[0])
p_lo = rms_db(render(tone(2000), FREQ=64, RES=0)[0])
p_hi = rms_db(render(tone(4000), FREQ=64, RES=0)[0])
l_slope, p_slope = l_lo - l_hi, p_lo - p_hi
check("LADR is a 4-pole: 2 kHz vs 4 kHz differ by ~24 dB at FREQ=64 (LP reads ~12 there)",
      19 <= l_slope <= 29 and 9 <= p_slope <= 15 and l_slope > p_slope + 6,
      f"LADR {l_slope:.1f} dB/oct vs LP {p_slope:.1f}")
d_ld = tail_mean(render(dc(), FREQ=64, MODE=0)[0])
check("LADR at DC -> DC (a low-pass, unity at RES 0)", abs(d_ld - dcv) < 256, f"{d_ld:.0f} vs {dcv}")
l4k = rms_db(render(tone(4000, 0.2), FREQ=64, RES=64, MODE=0)[0])
check("LADR cuts 4 kHz at FREQ 64 by > 10 dB more than LP does (distinct from LP)",
      lv[1][4000] - l4k > 10, f"LP {lv[1][4000]:.1f}, LADR {l4k:.1f} dBFS")
lr = {res: rms_db(render(tone(949, 0.02), FREQ=64, RES=res, MODE=0)[0]) for res in (0, 64, 100, 127)}
check("LADR resonance grows with RES: the tone at fc rises RES 0 < 64 < 100 < 127",
      lr[0] < lr[64] < lr[100] < lr[127] and lr[127] - lr[0] > 15,
      " / ".join(f"RES {r} {v:.1f}" for r, v in lr.items()) + " dBFS")
bounded("RES 127 LADR at fc, 0.13 FS in: below full scale, never on the rails",
        render(tone(600, 0.13), FREQ=64, RES=127, MODE=0)[0])
bounded("RES 127 LADR at fc, 0.5 FS in: below full scale, never on the rails",
        render(tone(600, 0.5), FREQ=64, RES=127, MODE=0)[0])

# ---- 6h. LADR at the top of the dial stays bounded with resonance ------------
import random as _rnd
_rnd.seed(7)
_wn = [int(_rnd.uniform(-0.3, 0.3) * 8388607) for _ in range(N)]
_l0 = rms_db(render(_wn, FREQ=127, RES=0, MODE=0)[0])
for _res in (64, 100, 127):
    _y = render(_wn, FREQ=127, RES=_res, MODE=0)[0]
    _lr = rms_db(_y)
    _rail = sum(1 for v in _y[N // 2:] if abs(v) >= 0x7ffff0) / (N - N // 2)
    # the linear ladder's passband sits at 1/(1+k): -9 dB at RES 64, the Moog law
    check(f"LADR FREQ 127 RES {_res} on noise: bounded (within 12 dB of RES 0, no rail)",
          abs(_lr - _l0) < 12 and _rail == 0, f"RES 0 {_l0:.1f}, RES {_res} {_lr:.1f} dBFS, rail {_rail*100:.1f}%")
_y = render(_wn, FREQ=64, RES=100, LDP=127, LSP=127, MODE=0)[0]
_lr = rms_db(_y); _rail = sum(1 for v in _y[N // 2:] if abs(v) >= 0x7ffff0) / (N - N // 2)
check("LADR FREQ 64 RES 100 under LDP 127 LSP 127: bounded (no rail, < RES 0 + 6 dB)",
      _rail == 0 and _lr < _l0 + 6, f"{_lr:.1f} dBFS, rail {_rail*100:.1f}%")

# ---- 7. every knob at its extremes renders -----------------------------------
for name in K:
    for v in (0, 127 if MOD.params[K[name]].count in (None, 128) else MOD.params[K[name]].count - 1):
        render(tone(438, n=600), **{name: v})
check("every knob at both extremes renders", True)

# ---- THE FX1-ONLY PROMISE: an FX2 instance is dry -------------
# Claims.fx1_only says an FX2-slot instance touches nothing; the rig's cycle
# envelope (tools/harness/pressure.py) and the FX2 chooser both take it at
# its word, so it is proven here at every extreme, and the guard sees no
# write outside the frame.
L, R = render(ramp, slot="fx2", FREQ=30, RES=110, MODE=2, ENV=127, LDP=127)
check("FX2 instance is a bit-exact DRY PASS at every extreme (fx1_only)",
      L == ramp and R == ramp,
      "" if L == ramp else f"first diff at {next(i for i,(a,b) in enumerate(zip(L,ramp)) if a!=b)}")
render(ramp, slot="fx2", guard=True, FREQ=30, RES=110, MODE=2, ENV=127, LDP=127)
g = getattr(render, "guard_out", "")
check("FX2 instance trips no write guard",
      "guard clean" in g,
      next((ln.strip() for ln in reversed(g.splitlines()) if "guard" in ln), ""))

print(f"\n{fails} gate(s) failed" if fails else "\nOK")
sys.exit(1 if fails else 0)
