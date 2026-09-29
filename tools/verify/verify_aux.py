#!/usr/bin/env python3
"""verify_aux -- the AUX passes of MIXER.md section 18: two more buses over the
ten sources the stock mixdown reads, at sends the ColdFire's aux_model gives.

Static (the built image, no project): the tail's pass is there, the sends'
region is zeroed at boot, and both are what the source says (the disassembly
is read, not the assembler's word for it).

The port half (a project, the ColdFire port; OT_PROJECT=<dir>), the built
`strip` image twice on the user's project with a constant on all four input
channels (a DC WAV, so every sample of a frame is the same and a snapshot at
the end of the run cannot fall between two frames):

  rest    aux_model untouched (zeros): nothing but stock's and the strip's
  sends   aux_model poked at frame 30 with twenty-four sends (twelve a bus; the two returns' terms zero)

  identity  every TX0 slot of both cores and every host-port block is
            byte-identical between the two runs: the sends change nothing
            but the two AUX blocks
  rest      X:0x7c80..0x7c93 (the sends) and both AUX blocks are all zero in
            the rest run: the boot zeroed them and a zero send adds nothing
  sends     X:0x7c80.. holds (v/128)^2 as Q23 for the twenty-four sends, and the
            AUX A / AUX B blocks are, for each of the sixteen samples, the
            python sum over the ten sources at those gains -- the two input
            pairs read from the ring where the mixdown reads it (X:0x202 and
            0x437, as P:0x23f..0x24e choose) and the eight tracks as they
            stand -- floor(sum / 2^23), stored limited, 0 LSB, L and R apart

What it cannot see: a track's audio (under the port no track reaches the
mixdown, docs/remixer/EMU.md, so the tracks' terms are zero here and only the
structure of their three-instruction step is read, not run); the cost on the
unit; whether the input ring is stable between the mixdown and the tail on
the chip (the port's DMA is the port's).
"""
import argparse, os, pathlib, re, shutil, subprocess, sys, tempfile, wave

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
from remix import registry  # noqa: E402
import verify_dspsite as vds  # noqa: E402
import verify_strip as vst  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
KEY = "MASTER STRIP"
SENDS_AT, AUX_A, AUX_B = 0x7c80, 0x7ca0, 0x7cc0
FRAME_SENDS = 30
# aux_model's order: AUX A's ten sources (T1..T8, IN AB, IN CD), then AUX B's.
SENDS = [10, 20, 30, 40, 50, 60, 70, 80, 127, 64, 0, 0,
         5, 15, 25, 35, 45, 55, 65, 75, 100, 33, 0, 0]
# The DC on RX0 slots 0..3: IN AB L, R and IN CD L, R (24-bit).
DC = [0x300000, -0x180000, 0x0a0000, -0x2c0000]

fails = 0


def check(label, ok, detail=""):
    global fails
    print(f"  [{'ok' if ok else 'FAIL'}] {label}" + (f"  {detail}" if detail else ""))
    fails += 0 if ok else 1
    return ok


def gain(v):
    """(v/128)^2 as Q23: what tgain writes (mpy: a1 = x*y >> 23)."""
    x = v << 16
    return (x * x) >> 23


def lim(v):
    return max(-(1 << 23), min((1 << 23) - 1, v))


def s24(w):
    return w - (1 << 24) if w & 0x800000 else w


def static(built):
    p = vds.Payload(built, "A")
    tail = p.word(0x35e)                     # the strip's `jsr >tail` over P:0x35d's two words
    d = vds.disasm(p.span(tail, tail + 640), tail)
    text = "\n".join(d)
    norm = re.sub(r"\s+", " ", text)
    check("static: the tail carries the sends' apply (mpy x0,y1,a, signed) and the pass "
          "(nine track/input steps of mac y0,x0,a; the input ring read by r2)",
          "mpy x0,y1,a" in norm and norm.count("mac y0,x0,a x:(r0)+n0,x0") >= 7
          and norm.count("mac y0,x0,b x:(r2)+,x0") >= 2, "")
    # the pass, for the stopwatch: `move x:>$202,b` (auxrun's first) to the next rts
    lo = next(int(l[:6], 16) for l in d if ": move    x:>$202,b" in l)
    hi = next(int(l[:6], 16) for l in d if l[:6].isalnum() and int(l[:6], 16) > lo and ": rts" in l)
    bad = [l for l in d if "mpysu" in l]
    check("static: no mpysu in the tail (every multiplier here is a positive gain in y0/y1)", not bad,
          bad[0] if bad else "")
    return lo, hi


def write_dc(path):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(4)
        w.setsampwidth(3)
        w.setframerate(44100)
        frame = b"".join((v & 0xffffff).to_bytes(3, "little") for v in DC)
        w.writeframes(frame * 44100)


def peeks(log):
    return {int(a, 16): [int(x, 16) for x in ws.split()]
            for a, ws in re.findall(r"core 0 X:0x([0-9a-f]+): ((?:[0-9a-f]{6} ?)+)", log)}


def launch(work, built, project, frames, var, extra, span, peek, audio_in=None):
    """One run of the built image on a copy of the project: the port's process."""
    import verify_set as vs
    import ot_project as otp
    vdir = work / var
    proj = vdir / "src"
    shutil.copytree(pathlib.Path(project).expanduser(), proj,
                    ignore=shutil.ignore_patterns("*.wav", "*.WAV", "*.ot"))
    pw = proj / "project.work"
    raw = pw.read_bytes()
    for key in (b"DIR_AB", b"DIR_CD"):
        raw, n = re.subn(rb"\r\n" + key + rb"=\d+", b"\r\n" + key + b"=127", raw)
        if n != 1:
            raise SystemExit(f"project.work has no {key.decode()} line")
    pw.write_bytes(raw)
    bank = int(re.search(rb"\r\nBANK=(\d+)\r\n", raw).group(1)) + 1
    pat_part, _ = otp.bank_info(proj, bank)
    part = vs.part_of(proj, bank, pat_part[0] + 1)
    card = vdir / "card.img"
    vs.stage(proj, part, "OCTABAM", "RIG", vdir / "tree", 64, bank, card)
    cmd = [str(vds.EMU), "--image", str(work / "built.bin"), "--card", str(card),
           "--set", "OCTABAM", "--project", "RIG", "--sequencer", "--internal-clock",
           "--frames", str(frames), "--load-ms", "20000", "--dsp", "--main-level", "64",
           "--audio-in", audio_in or str(work / "dc.wav"), "--poke-trig", "2",
           "--audio-out", str(vdir / "run"), "--block-dump", str(vdir / "run.dump"),
           "--dsp-stopwatch", f"0:{span[0]:x}:{span[1]:x}", "--dsp-peek", peek] + extra
    return subprocess.Popen(cmd, cwd=ROOT, stdout=open(vdir / "run.txt", "w"), stderr=subprocess.STDOUT)


def port(built, project, frames, sym, span):
    import verify_set as vs
    import ot_project as otp
    import blockdump
    if not vds.EMU.exists() or not vds.PY.exists() or "aux_model" not in sym:
        print("  [SKIP] port half: the ColdFire port, the .venv or the runtime symbols are missing")
        return
    with tempfile.TemporaryDirectory(prefix="aux_") as work:
        work = pathlib.Path(work)
        (work / "built.bin").write_bytes(bytes(built))
        write_dc(work / "dc.wav")
        procs = {}
        for var in ("rest", "sends"):
            extra = []
            if var == "sends":
                base = sym["aux_model"]
                extra = ["--step", f"{FRAME_SENDS}:poke:" + ";".join(f"{base + i:#x}={v}" for i, v in enumerate(SENDS))]
            procs[var] = launch(work, built, project, frames, var, extra, span,
                                f"0:X:{SENDS_AT:x},24;0:X:{AUX_A:x},64;0:X:202,1;0:X:437,1;0:X:8000,4096")
        codes = {v: p.wait() for v, p in procs.items()}
        if not all(check(f"port: {v} run finished", codes[v] == 0) for v in codes):
            return
        logs = {v: (work / v / "run.txt").read_text() for v in codes}
        pk = {v: peeks(logs[v]) for v in logs}
        m = re.search(r"stopwatch: .*mean (\d+) min (\d+) max (\d+)", logs["sends"])
        if m:
            print(f"  [info] the pass (P:0x{span[0]:x}..0x{span[1]:x}, both buses): {m.group(1)} instructions a frame "
                  f"(min {m.group(2)}, max {m.group(3)}), {int(m.group(1)) / 16:.0f} a sample; the port's count, not cycles")
        # identity: the sends change nothing but the two AUX blocks
        a, b = vst.tx0(work / "rest" / "run_core0.wav"), vst.tx0(work / "sends" / "run_core0.wav")
        n = min(len(a[0]), len(b[0]))
        diff = [s for s in a if a[s][:n] != b[s][:n]]
        check("port: identity: every TX0 slot of core 0 is byte-identical with and without sends "
              f"({len(a)} slots, {n:,} frames)", not diff and n > 0, f"slots {diff} differ" if diff else "")
        da, db = (blockdump.classes(blockdump.read(work / v / "run.dump")) for v in ("rest", "sends"))
        differ = sorted(k for k in set(da) | set(db) if da.get(k) != db.get(k))
        # the one class that may differ is the strip's own record burst (the
        # sends ride in its halfwords 21..30, the checksum in 31)
        rec = differ[0] if len(differ) == 1 else None
        words = ok = None
        if rec is not None and len(da[rec]) == len(db[rec]) > 0:
            idx = sorted({i for (_, wa), (_, wb) in zip(da[rec], db[rec]) for i, (x, y) in enumerate(zip(wa, wb)) if x != y})
            ok = bool(idx) and min(idx) >= 21 and all(len(w) == 32 for _, w in da[rec] + db[rec])
            words = idx
        check(f"port: identity: of {len(da)} host-port block classes only the strip's record burst differs, "
              "in its halfwords 21..31 (the sends and the checksum)", bool(ok),
              f"differ {differ[:3]}, words {words}" if not ok else f"32-word blocks, words {words[0]}..{words[-1]}")
        # rest: zeros
        r = pk["rest"]
        check("port: rest: the sends and both AUX blocks are zero (boot zeroed them, no record asked)",
              r.get(SENDS_AT) == [0] * 24 and r.get(AUX_A) == [0] * 64, "")
        # sends
        s = pk["sends"]
        want = [gain(v) for v in SENDS]
        check("port: sends: X:0x7c80.. are (v/128)^2 as Q23 for the twenty-four sends",
              s.get(SENDS_AT) == want,
              "" if s.get(SENDS_AT) == want else f"got {[hex(x) for x in (s.get(SENDS_AT) or [])[:6]]}...")
        ring = s.get(0x8000)
        x202, x437 = s[0x202][0], s[0x437][0]
        r2 = x202
        if x437:
            r2 -= 0x140
        if r2 < 0x8100:
            r2 += 0x240
        ins = [s24(w) for w in ring[r2 - 0x8000:r2 - 0x8000 + 4]] if ring and r2 - 0x8000 + 4 <= len(ring) else None
        print(f"  [info] input ring at X:0x{r2:x} (X:0x202 = 0x{x202:x}, X:0x437 = 0x{x437:x}): {ins}, "
              f"the WAV's {DC}")
        if not check("port: sends: the input ring holds the DC on every sample (four words a sample)",
                     ins is not None and all(s24(w) == ins[i % 4] for i, w in enumerate(ring[r2 - 0x8000:r2 - 0x8000 + 64])
                                             if r2 - 0x8000 + 64 <= len(ring)), ""):
            return
        for name, at, sends in (("AUX A", AUX_A, want[:12]), ("AUX B", AUX_B, want[12:])):
            blk = s.get(AUX_A)
            base = at - AUX_A
            left = lim(sum(g * x for g, x in zip(sends[8:], (ins[0], ins[2]))) >> 23)
            right = lim(sum(g * x for g, x in zip(sends[8:], (ins[1], ins[3]))) >> 23)
            got = blk[base:base + 32]
            exp = [left, right] * 16
            ok = [s24(w) for w in got] == exp
            check(f"port: sends: {name} is g8 * IN AB + g9 * IN CD on all sixteen samples, L and R, 0 LSB "
                  f"(tracks silent)", ok,
                  f"L {left} R {right}; got {[s24(w) for w in got[:4]]}" if not ok else f"L {left}, R {right}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("remix", nargs="*")
    ap.add_argument("--project", default=os.environ.get("OT_PROJECT", ""))
    ap.add_argument("--frames", type=int, default=120)
    a = ap.parse_args()
    if not vds.STOCK.exists():
        print("  [SKIP] verify_aux: no stock image (make os)")
        return 0
    names = a.remix or [n for n in sorted(registry.remix_names()) if KEY in registry.remix(n).modules]
    names = [n for n in names if KEY in registry.remix(n).modules]
    if not names:
        print(f"  [--] verify_aux: no remix selected carries {KEY}")
        return 0
    for name in names[:1]:
        built, report = vds.build(name)
        print(f"{name}: {len(built):,} bytes built")
        sym = vst.symbols()
        span = static(built)
        if a.project:
            port(built, a.project, a.frames, sym, span)
        else:
            print(f"  [SKIP] {name}: port half -- no project (OT_PROJECT=<dir> or --project)")
    print(f"verify_aux: {fails} failure(s)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
