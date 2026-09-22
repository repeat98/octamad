#!/usr/bin/env python3
"""THE ONE AUX BUS, measured on both cores (the hardwired rig).

Every case below renders through tools/harness/dsp_host with BOTH payloads booted
(docs/remixer/HARNESS.md "Two cores"): the senders and the delay on payload B where
the unit runs them, the reverb on payload A, so the chain buffer and its
liveness stamp cross the real core boundary. The image is the rig remix
(bamsep26) as SPEC -- the stations must be in it. Since 20 Sep 2026 each
engine's wet comes out on the track that hosts it (the hosts are not fed, so
a host's stream IS its engine's wet*WET); there is no return station.

  chain        both engines: T5 (reverb host) prints the reverb, stereo;
               T1 (delay host) prints the delay
  the delay reaches the reverb
               T5's print with the delay in the layout != without it
  passthrough  delay WET 0 with both engines == reverb only fed the tone two
               blocks later (the chain buffer's own latency), within -80 dB
  delay only   no reverb in the layout: T1 prints the delay
  reverb only  no delay: T5 prints the reverb (it reads the aux directly)
  WET 0        a host at WET 0 prints nothing but its (silent) dry
  the reverb takes nothing out
               T1's print is bit-identical with the reverb at WET 0, at WET
               127 and with no reverb at all
  T8 refused   a SEND at core-0 position 3 (track 8) with SEND 127 changes
               nothing (the master's input is the mix, the hosts' wet
               included: a send from it would loop the bus)
  T4 sends     the mirror position on core 1 does
  old bytes    a Character with slot 4 stored 127 (RET in a pre-20-Sep
               part), on T8 or T4, prints nothing of its own and changes
               neither host; a station with the old send bytes (slots 4/5 =
               127) contributes nothing to the bus
  skew         the chain case under four interleaves: identical

What this cannot show: the chip's timing (lock-step, or a guessed -skew),
and anything the ColdFire does (knobs are poked into r6).

    make verify-onebus            # ~2 min
"""
import filecmp
import math
import os
import pathlib
import shutil
import struct
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path)
import send_probe  # noqa: E402
from remix import registry  # noqa: E402

REMIX = "bamsep26"
OUT = ROOT / "out/dsp"
SCRATCH = OUT / "_onebus"
IMAGE = ROOT / "out/mainos_bus.bin"
FRAMES = send_probe.FRAMES
PAD = send_probe.WARMUP_BLOCKS * FRAMES
SR = 44100
BLOCKS = 900
TONE_HZ = 438.75
SKEWS = (1, 37, 333, -250)


def knobs(key, **kw):
    m = registry.by_key(key)
    v = [(p.default or 0) & 0x7f for p in m.params] + [0] * 12
    km = m.knob_map_all()
    for n, x in kw.items():
        if n not in km:
            sys.exit(f"{key} has no knob {n!r}")
        v[km[n]] = x
    return v[:12]


def build(env, log):
    r = subprocess.run([sys.executable, "tools/build/build_bus.py"], cwd=ROOT,
                       env={**os.environ, "REMIX": REMIX, **env}, capture_output=True, text=True)
    log.write_text(r.stdout + r.stderr)
    if r.returncode != 0:
        sys.exit(f"build failed ({env}): see {log}")


def tone_file(path, blocks, amp=0.4, start=0):
    """a tone from sample PAD + start on; `start` shifts it later"""
    w = 2 * math.pi * TONE_HZ / SR
    with open(path, "wb") as f:
        for i in range(blocks * FRAMES):
            v = amp * math.sin(w * (i - PAD - start)) if i >= PAD + start else 0.0
            f.write(struct.pack("<i", int(v * 8388607)))


class Inst:
    """one effect instance: key, core, fx slot (1|2), position on its core"""
    def __init__(self, key, core, pos, fx=2, fed=False, **kw):
        self.key, self.core, self.pos, self.fx, self.fed = key, core, pos, fx, fed
        self.params = knobs(key, **kw)


def run(mems, insts, skew=None, tag="r", tone="tone.raw"):
    ep = {}
    for c, m in mems.items():
        ep[c] = {}
        for i in insts:
            fid = registry.by_key(i.key).menu.fx2_id
            ep[c][i.key] = send_probe.entry_points(m, fid)
        sid = send_probe.entry_points(m, send_probe.SERVER_ID["S"])
        for i in insts:
            if i.core == c and i.key != "SEND" and ep[c][i.key] == sid:
                sys.exit(f"{i.key} is not in payload {'AB'[c]} (its entry is SEND's)")
    out = SCRATCH / f"{tag}.raw"
    cmd = [str(send_probe.HOST), "-mem", str(mems[0]), "-memB", str(mems[1]),
           "-init", ",".join(f"{ep[i.core][i.key][0]:x}" for i in insts),
           "-proc", ",".join(f"{ep[i.core][i.key][1]:x}" for i in insts),
           "-inst", str(len(insts)),
           "-core", ",".join(str(i.core) for i in insts),
           "-alloc", ",".join(str(2 * i.pos + (i.fx - 1)) for i in insts),
           "-r7", ",".join(str(1 + 3 * i.pos + (i.fx - 1)) for i in insts),   # three r7 bumps per track (COLDFIRE_PORT.md O11)
           "-audioidx", ",".join(str(k) for k, _ in enumerate(insts)),
           "-audio", "9000",
           "-inmask", str(sum(1 << k for k, i in enumerate(insts) if i.fed)),
           "-frames", str(FRAMES), "-blocks", str(BLOCKS),
           "-in", str(SCRATCH / tone), "-out", str(out)]
    for i in insts:
        cmd += ["-params", ",".join(map(str, i.params))]
    if skew is not None:
        cmd += ["-skew", str(skew)]
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"dsp_host failed:\n{r.stdout[-2500:]}{r.stderr[-1000:]}")
    streams = []
    for k in range(len(insts)):
        p = out if k == 0 else pathlib.Path(f"{out}.i{k}")
        raw = p.read_bytes()
        a = struct.unpack(f"<{len(raw) // 4}i", raw)
        streams.append((list(a[0::2])[PAD:], list(a[1::2])[PAD:]))
    return streams


def rms_db(x):
    return 20 * math.log10(max(1e-9, math.sqrt(sum((v / 8388607) ** 2 for v in x) / max(1, len(x)))))


def peak(x):
    return max((abs(v) for v in x), default=0)


def best_lag(ref, got, scale=1.0, lo=0, hi=96):
    best = None
    for lag in range(lo, hi + 1):
        n = min(len(ref) - lag, len(got) - lag)
        if n <= 0:
            continue
        r, g = ref[:n], got[lag:lag + n]
        res = sum((gi - ri * scale) ** 2 for gi, ri in zip(g, r))
        den = sum(ri * ri for ri in r) or 1
        db = 10 * math.log10(max(1e-12, res / den))
        if best is None or db < best[1]:
            best = (lag, db)
    return best


fails = 0


def check(label, ok, detail=""):
    global fails
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{'  ' + detail if detail else ''}")
    fails += 0 if ok else 1


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    snap = SCRATCH / "mainos_bus.snapshot.bin"
    had = IMAGE.is_file()
    if had:
        shutil.copy2(IMAGE, snap)
    try:
        build({"XBUS": "1", "SPEC": "1"}, SCRATCH / "build_spec.log")
        A = send_probe.dump_mem(IMAGE, SCRATCH / "spec_A.mem", "A")
        B = send_probe.dump_mem(IMAGE, SCRATCH / "spec_B.mem", "B")
    finally:
        if had:
            shutil.copy2(snap, IMAGE)
    mems = {0: A, 1: B}
    tone_file(SCRATCH / "tone.raw", BLOCKS)
    tone_file(SCRATCH / "tone45.raw", BLOCKS, start=3 * FRAMES)

    # the rig's shape: T5 reverb (core 0 pos 0), T6 send, T1 delay (core 1
    # pos 0), T2 send. Neither host is fed, so a host's stream is its
    # engine's wet*WET and nothing else.
    # PING 0 keeps the delay's repeats on one channel, so the chain's MONO
    # average of a 438 Hz tone does not cancel between alternate repeats
    # (measured -9 dB at PING 127 with TIME 40: test artefact, not engine).
    R = lambda **k: Inst("REVERB SERVER", 0, 0, **k)   # noqa: E731  (the tank mod is pinned since 15 Sep 2026; no MOD knob)
    D = lambda **k: Inst("DELAY SERVER", 1, 0, PING=0, TIME=20, **k)   # noqa: E731  (5,184 samples: the first repeat lands inside BLOCKS; TIME is 64 + knob*256 since the 32K lines)
    S6 = lambda **k: Inst("SEND", 0, 1, fed=True, SEND=100, **k)   # noqa: E731
    S2 = lambda **k: Inst("SEND", 1, 1, fed=True, SEND=100, **k)   # noqa: E731

    print("== the chain: T2/T6 send, T1 delay -> T5 reverb; each host prints its wet ==")
    both = [R(), S6(), D(), S2()]
    st = run(mems, both, tag="both")
    t5, t1 = st[0], st[2]
    check("T5 (reverb host) prints the reverb", rms_db(t5[0]) > -45, f"rms {rms_db(t5[0]):.1f} dB")
    check("T5's print is stereo (L != R)", t5[0] != t5[1])
    check("T1 (delay host) prints the delay", rms_db(t1[0]) > -40, f"rms {rms_db(t1[0]):.1f} dB")
    for sk in SKEWS:
        s2 = run(mems, both, skew=sk, tag="bothsk")
        check(f"chain under skew {sk:5d}: both hosts identical", s2[0] == t5 and s2[2] == t1)

    print("\n== the chain is real: the delay's repeats reach the reverb ==")
    ronly = [R(), S6(), S2()]
    st_r = run(mems, ronly, tag="ronly")
    check("reverb only: T5 prints the reverb (it reads the aux directly)", rms_db(st_r[0][0]) > -40,
          f"rms {rms_db(st_r[0][0]):.1f} dB")
    check("both != reverb only (the reverb hears the delay)", t5 != st_r[0])

    print("\n== the passthrough: delay WET 0 == no delay, three blocks later ==")
    # The chain buffer costs three blocks (two until 22 Sep 2026), and the
    # reverb is time-variant even at MOD 0 (a fixed-depth allpass
    # modulator), so the reference is NOT the reverb-only output shifted --
    # it is the reverb-only run fed the SAME tone three blocks later, which
    # the chain then reproduces sample for sample. What is left is one auto-gain table against the other:
    # rounding, -100 dB or so.
    pt = [R(), S6(), D(WET=0), S2()]
    st_p = run(mems, pt, tag="pass")
    st_r45 = run(mems, ronly, tag="ronly45", tone="tone45.raw")
    lag, db = best_lag(st_r45[0][0], st_p[0][0], lo=0, hi=2)
    check(f"delay WET 0: T5 == reverb-only fed the tone 3 blocks later (lag {lag})",
          lag == 0 and db < -80, f"residual {db:.1f} dB")

    print("\n== delay only, and WET 0 ==")
    donly = [S6(), D(), S2()]
    st_d = run(mems, donly, tag="donly")
    check("delay only: T1 prints the delay", rms_db(st_d[1][0]) > -40,
          f"rms {rms_db(st_d[1][0]):.1f} dB")
    nr0 = [R(WET=0), S6(), D(WET=0), S2()]
    st_h0 = run(mems, nr0, tag="wet0")
    check("T5 with WET 0 prints nothing but its (silent) dry", peak(st_h0[0][0] + st_h0[0][1]) == 0)
    check("T1 with WET 0 prints nothing but its (silent) dry", peak(st_h0[2][0] + st_h0[2][1]) == 0)

    print("\n== the reverb takes nothing out of the delay ==")
    d_r0 = [R(WET=0), S6(), D(), S2()]
    st_dr0 = run(mems, d_r0, tag="d_rwet0")
    check("T1's print with the reverb at WET 0 == delay only, bit for bit", st_dr0[2] == st_d[1])
    check("T1's print with the reverb at WET 127 == delay only, bit for bit", t1 == st_d[1])

    print("\n== the send is refused on track 8, and only there ==")
    t8 = [R(), S6(), Inst("SEND", 0, 3, fed=True, SEND=127), D(), S2()]
    st_8 = run(mems, t8, tag="t8")
    check("a SEND on T8 (core 0 pos 3) at SEND 127 changes both hosts NOT AT ALL",
          st_8[0] == t5 and st_8[3] == t1)
    t4 = [R(), S6(), D(), S2(), Inst("SEND", 1, 3, fed=True, SEND=127)]
    st_4 = run(mems, t4, tag="t4")
    check("a SEND on T4 (core 1 pos 3, the mirror) DOES change T5's print", st_4[0] != t5)

    print("\n== a stored return byte is inert ==")
    # Character page-1 slot 4 was RET until 20 Sep 2026; a pre-20-Sep part
    # stores 127 there (the stamped default). On T8 (the old master) and on
    # T4 (the mirror) it must print nothing and touch neither host.
    for core, name in ((0, "T8"), (1, "T4")):
        c = Inst("CHARACTER", core, 3, fx=1)
        c.params[4] = 127
        lay = [R(), S6(), D(), S2(), c]
        st_c = run(mems, lay, tag=f"oldret{name}")
        check(f"a Character with slot 4 = 127 on {name} prints nothing of its own",
              peak(st_c[4][0] + st_c[4][1]) == 0, f"peak {peak(st_c[4][0] + st_c[4][1])}")
        check(f"... and both hosts print exactly as without it", st_c[0] == t5 and st_c[2] == t1)

    print("\n== the stations have no sends ==")
    # a Spectrum station on T6's FX1 with the OLD send bytes stored (slots 4
    # and 5 at 127, what a pre-rig part holds) beside T6's SEND at SEND 100
    stn = [R(), Inst("SPECTRUM", 0, 1, fx=1, fed=True), S6(), D(), S2()]
    stn[1].params[4] = 127
    stn[1].params[5] = 127
    st_s = run(mems, stn, tag="station")
    check("a station with stored send bytes 127/127 contributes nothing (both hosts identical)",
          st_s[0] == t5 and st_s[3] == t1)

    if fails:
        sys.exit(f"\none-aux gate: {fails} FAILURE(S)")
    print("\none-aux gate: every property holds on both cores.")
    print("  ⚠️  Lock-step and a guessed skew are not the chip's timing; the")
    print("     ColdFire is not here at all. Stamp every project before play.")


if __name__ == "__main__":
    main()
