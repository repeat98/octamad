#!/usr/bin/env python3
"""PMAP PROBE's plumbing under the ColdFire port (not its answer).

    OT_PROJECT=<dir> python3 tools/verify/verify_pmap_probe.py

The probe (modules/pmap-probe) switches both DSP cores to the 16K program map
at boot and plays each core's verdict on MAIN. The port's DSP emulator does
not model the memory switch, so under the port both cores must PASS by
construction: this gate proves the probe reports what it measures and
disturbs nothing else, never that the unit runs the map.

Static, the built image: the three hooks are planted (P:0x40 on both
payloads, P:0x2d5 on A, P:0x333 on B) and the probe's OMR words are what the
source says (`move omr,x0` 0444ba, `move x0,omr` 04c4ba, `ori #$80,omr`
0080fa; the only forms here with no precedent on a unit, by design).

Port, the user's project with the tones on the inputs, the built image
against the same image with the three sites' stock words back:
  verdicts   core 0 and core 1: X:0x7f00 = 0x50A55, X:0x7f01 (errors) = 0,
             X:0x7f02 = 0xC0DE (the routine ran from P:0x3F00); X:0x3fff0
             on core 0 holds core 1's verdict
  others     every TX0 slot but MAIN's pair and the phones is byte-identical;
             the phones (the cue mix of CUE and MAIN) differ only where MAIN does
  tone       MAIN L and MAIN R each differ from the reference by exactly
             +/-0x080000 on every sample of the stretch that runs frames (the
             capture also spans the project load, when neither image runs any),
             the sign flipping every 25 samples: an 882 Hz square, both cores
             reported and heard
What it cannot see: anything about the chip (the port passes regardless of
the map); the fail tone (reachable only when the test fails).
"""
import argparse, contextlib, os, pathlib, re, shutil, subprocess, sys, tempfile, wave

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
from dsp_modmap import BASE, PAYLOADS, modules  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
EMU, PY = ROOT / "out/emu/ot_emu", ROOT / ".venv/bin/python3"
SITES = {"A": ((0x40, 0x57f400, 0x008000), (0x2d5, 0x60f000, 0x000206)),
         "B": ((0x40, 0x57f400, 0x008000), (0x333, 0x56f000, 0x000415))}
OMR = {0x0444ba: "move omr,x0", 0x04c4ba: "move x0,omr", 0x0080fa: "ori #$80,omr"}
PASS, AMP, HALF = 0x50A55, 0x080000, 25
MAIN = (2, 3)
PHONES = (4, 5)
fails = 0


def check(label, ok, detail=""):
    global fails
    print(f"  [{'ok' if ok else 'FAIL'}] {label}" + (f"  {detail}" if detail else ""))
    fails += 0 if ok else 1
    return ok


class Payload:
    def __init__(self, img, tag):
        va, ln = next((v, l) for t, v, l in PAYLOADS if t == tag)
        mods, _ = modules(bytes(img), va, ln)
        self.img, self.recs, self.va = img, [m for m in mods if m[0] == 0], va

    def index(self, addr):
        for _sp, a, cnt, off in self.recs:
            if a <= addr < a + cnt:
                return self.va - BASE + off + (addr - a) * 3
        raise KeyError(addr)

    def word(self, addr):
        i = self.index(addr)
        return self.img[i] | self.img[i + 1] << 8 | self.img[i + 2] << 16

    def put(self, addr, w):
        i = self.index(addr)
        self.img[i:i + 3] = w.to_bytes(3, "little")


def build():
    env = dict(os.environ, REMIX="pmap-probe")
    r = subprocess.run(["make", "bus", "REMIX=pmap-probe"], cwd=ROOT, env=env, capture_output=True, text=True)
    if r.returncode:
        sys.exit("verify_pmap_probe: the build failed:\n" + r.stdout[-2000:] + r.stderr[-2000:])
    return bytearray((ROOT / "out/mainos_bus.bin").read_bytes()), r.stdout


def static(built, report):
    ref = bytearray(built)
    for tag, sites in SITES.items():
        p, q = Payload(built, tag), Payload(ref, tag)
        for site, w0, w1 in sites:
            jsr, target = p.word(site), p.word(site + 1)
            check(f"{tag}: P:0x{site:03x} is a jsr into the probe (0x{jsr:06x} 0x{target:06x})",
                  jsr == 0x0bf080 and target > 0x800)
            q.put(site, w0)
            q.put(site + 1, w1)
            if site == 0x40:
                body = [p.word(target + k) for k in range(40)]
                found = sorted({OMR[w] for w in body if w in OMR})
                check(f"{tag}: the boot's OMR words are the three the source names", found == sorted(OMR.values()),
                      ", ".join(found))
    return ref


def tx0(path):
    w = wave.open(str(path))
    ch, n, data = w.getnchannels(), w.getnframes(), w.readframes(w.getnframes())
    out = {s: [] for s in range(ch)}
    for i in range(n):
        for s in range(ch):
            v = int.from_bytes(data[(i * ch + s) * 3:(i * ch + s) * 3 + 3], "little")
            out[s].append(v - (1 << 24) if v & 0x800000 else v)
    return out


def peeks(log):
    return {(int(c), int(a, 16)): [int(x, 16) for x in ws.split()]
            for c, a, ws in re.findall(r"core (\d) X:0x([0-9a-f]+): ((?:[0-9a-f]{6} ?)+)", log)}


def port(built, ref, project, frames):
    import verify_set as vs
    import ot_project as otp
    if not EMU.exists():
        print("  [SKIP] port: the ColdFire port is missing (make emu-cf)")
        return
    keep = os.environ.get("PMAP_KEEP")
    with (contextlib.nullcontext(keep) if keep else tempfile.TemporaryDirectory(prefix="pmap_")) as work:
        work = pathlib.Path(work)
        work.mkdir(parents=True, exist_ok=True)
        proj = work / "src"
        shutil.copytree(pathlib.Path(project).expanduser(), proj, ignore=shutil.ignore_patterns("*.wav", "*.WAV", "*.ot"))
        raw = (proj / "project.work").read_bytes()
        for key in (b"DIR_AB", b"DIR_CD"):
            raw = re.sub(rb"\r\n" + key + rb"=\d+", b"\r\n" + key + b"=127", raw)
        (proj / "project.work").write_bytes(raw)
        bank = int(re.search(rb"\r\nBANK=(\d+)\r\n", raw).group(1)) + 1
        pat_part, _ = otp.bank_info(proj, bank)
        part = vs.part_of(proj, bank, pat_part[0] + 1)
        card = work / "card.img"
        vs.stage(proj, part, "OCTABAM", "RIG", work / "tree", 64, bank, card)
        runs = {}
        for tag, img in (("built", built), ("ref", ref)):
            (work / f"{tag}.bin").write_bytes(bytes(img))
            shutil.copy2(card, work / f"card_{tag}.img")
            cmd = [str(EMU), "--image", str(work / f"{tag}.bin"), "--card", str(work / f"card_{tag}.img"),
                   "--set", "OCTABAM", "--project", "RIG", "--sequencer", "--internal-clock", "--frames", str(frames),
                   "--load-ms", "20000", "--dsp", "--main-level", "64", "--audio-in", "tones", "--poke-trig", "2",
                   "--audio-out", str(work / tag),
                   "--dsp-peek", "0:X:7f00,3;1:X:7f00,3;0:X:3fff0,1"]
            runs[tag] = subprocess.Popen(cmd, cwd=ROOT, stdout=open(work / f"{tag}.txt", "w"), stderr=subprocess.STDOUT)
        if not all(check(f"port: the {t} image ran", p.wait() == 0) for t, p in runs.items()):
            return
        pk = peeks((work / "built.txt").read_text())
        for core in (0, 1):
            v = pk.get((core, 0x7f00))
            check(f"port: core {core}'s verdict is pass: 0x50A55, 0 errors, the routine ran from P:0x3F00 (0xC0DE)",
                  v == [PASS, 0, 0xC0DE], " ".join(f"{x:06x}" for x in (v or [])))
        check("port: core 0 sees core 1's verdict at X:0x3fff0", pk.get((0, 0x3fff0)) == [PASS],
              " ".join(f"{x:06x}" for x in (pk.get((0, 0x3fff0)) or [])))
        b, r = tx0(work / "built_core0.wav"), tx0(work / "ref_core0.wav")
        n = min(len(b[0]), len(r[0]))
        check(f"port: both captures have the same length within a frame ({len(b[0]):,} / {len(r[0]):,})",
              abs(len(b[0]) - len(r[0])) <= 16 and n > 0)
        # The phones (4/5) are the cue mix of CUE and MAIN, so they carry the tone too.
        others = [s for s in r if s not in MAIN + PHONES and b[s][:n] != r[s][:n]]
        check(f"port: every TX0 slot but MAIN's pair and the phones is byte-identical ({len(r) - 4} slots)",
              not others, f"slots {others} differ" if others else "")
        for s, m in zip(PHONES, MAIN):
            # the capture can frame the phones a sample behind MAIN (verify_strip's lag)
            stray = sum(1 for i in range(1, n) if b[s][i] != r[s][i] and b[m][i] == r[m][i]
                        and b[m][i - 1] == r[m][i - 1])
            check(f"port: phones slot {s} differ only where MAIN does, or did a sample earlier (they mix it)",
                  stray == 0,
                  f"{stray} sample(s) differ where MAIN does not")
        for s, side in zip(MAIN, "LR"):
            d = [b[s][i] - r[s][i] for i in range(n)]
            # The capture spans the project load, when neither image runs frames (both
            # outputs hold still): the tone is in the stretch that runs, to the end.
            k = n
            while k > 0 and d[k - 1]:
                k -= 1
            seg = d[k:]
            if not check(f"port: MAIN {side} carries the tone to the capture's end, at least 100 frames",
                         len(seg) >= 1600, f"{len(seg):,} samples"):
                continue
            runs_, j = [], 0
            while j < len(seg):
                e = j
                while e < len(seg) and (seg[e] > 0) == (seg[j] > 0):
                    e += 1
                runs_.append(e - j)
                j = e
            # The first frames after the load resumes are framed short in the capture on both
            # channels (runs of 8 and 17 seen, 30 Sep 2026): the first two runs are not held
            inner = runs_[2:-1]
            check(f"port: MAIN {side} = the reference +/-0x080000 on every running sample; past the first two "
                  f"runs, every run {HALF} long (an 882 Hz square)",
                  all(abs(x) == AMP for x in seg) and len(inner) > 50 and all(x == HALF for x in inner),
                  f"{len(seg):,} samples from TX0 {k:,}, runs {sorted(set(inner))[:5]}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", default=os.environ.get("OT_PROJECT", ""))
    ap.add_argument("--frames", type=int, default=150)
    a = ap.parse_args()
    built, report = build()
    print(f"pmap-probe: {len(built):,} bytes built")
    ref = static(built, report)
    if a.project:
        port(built, ref, a.project, a.frames)
    else:
        print("  [SKIP] port: no project (OT_PROJECT=<dir> or --project)")
    print(f"verify_pmap_probe: {fails} failure(s)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
