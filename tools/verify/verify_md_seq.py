#!/usr/bin/env python3
"""The Machinedrum's embedded sequencer under the ColdFire port (WP-D3).

    python3 tools/verify/verify_md_seq.py [--project DIR] [--frames 2400]
    OT_PROJECT=DIR [MD_EMU=path/to/ot_emu] make verify-md-seq

The whole machine path, no test pokes into the kit: T1 of every Part of bank
1 is MACHINEDRUM (raw machine type 6), so the frame builder's hook names T1
as the MD track and the control engine loads its default kit; pattern A01
is LEN 16 at 1X and the project runs at 300 BPM (one step = 137.8 frames).
The gate pokes one MD pattern into md_patterns[0] (bank A, pattern 1):

  lane 1 (TRX-BD)  steps 1 3 5 7 9 11 13 15
  lane 2 (TRX-SD)  steps 2 6 10 14, VOL locked to 0 on step 6
  lane 3 (TRX-CH)  steps 4 12, SYN 1 locked to 0 on step 4

and samples core 1 at glue label gnotrg every frame (Y voice records and
both gain tables). Checks:

  kit      the default kit reached the voices: routine index engine + 1 on
           each lane's trig (0x11, 0x12, 0x17);
  steps    each lane's trigs arrive once per programmed step, on the step
           grid (137.8 frames at 300 BPM, 1X) within two frames, across the
           pattern's wrap, anchored on lane 1's step 3 (step 1, due at PLAY,
           falls in the producer's startup hold in a run from boot);
  lock     lane 3's step-4 record (SYN 1 locked to 0) differs from its
           step-12 record, which carries the kit's value again (the handler
           derives several words from one parameter);
  vol lock part 2's gain pair is zero after its step-6 trig and back to
           md_gain(100, 64) after its step-10 trig;
  audio    T1's post-FX2 read-back is non-silent on most frames: the lanes'
           voices reach the track's output.

What it cannot see: the unit's timing, and a swing grid (the fixture has
none). SKIPs without a project, the port or the MD payload.
"""
import argparse
import os
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import verify_md_kit as kit  # noqa: E402

OUT = ROOT / "out/mdverify/seq"
BPM = 300
STEP_FRAMES = 44100 * 60 / (BPM * 4) / 16          # 137.8 frames per 1X step
HOLD = 20                                          # the producer's startup hold, in rows


def lanes():
    """{lane: [steps 0-based]}, locks [(step, part, param, value)]."""
    return ({0: list(range(0, 16, 2)), 1: [1, 5, 9, 13], 2: [3, 11]},
            [(5, 1, 8, 0), (3, 2, 0, 0)])


def pattern_blob():
    trig, locks = lanes()
    blob = bytearray()
    for p in range(16):
        bits = 0
        for s in trig.get(p, ()):
            bits |= 1 << s
        blob += (bits & 0xffffffff).to_bytes(4, "big") + (bits >> 32).to_bytes(4, "big")
    entries = [bytes(l) for l in locks] + [bytes((0, 0xff, 0, 0))] * (64 - len(locks))
    return bytes(blob) + b"".join(entries)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--project", default=os.environ.get("OT_PROJECT", ""))
    ap.add_argument("--frames", type=int, default=2400)
    a = ap.parse_args()
    if not a.project:
        print("  [SKIP] verify_md_seq: no project (OT_PROJECT=<dir> or --project)")
        return 0
    if not kit.EMU.exists() or not (kit.MDB / "payload_B.mem").exists():
        print("  [SKIP] verify_md_seq: no port or MD payload")
        return 0
    import ot_project as otp
    OUT.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, REMIX="machinedrum", XBUS="1", SPEC="1")
    env.setdefault("BUILD", "0")
    r = subprocess.run([sys.executable, str(ROOT / "tools/build/build_bus.py")], env=env,
                       capture_output=True, text=True, cwd=ROOT)
    if r.returncode:
        sys.exit(f"verify_md_seq: building machinedrum failed:\n{(r.stdout + r.stderr)[-1500:]}")
    image = OUT / "image.bin"
    shutil.copy2(ROOT / "out/mainos_bus.bin", image)
    proj = OUT / "project"
    if proj.exists():
        shutil.rmtree(proj)
    shutil.copytree(pathlib.Path(a.project).expanduser(), proj)
    for part in range(1, 5):
        otp.set_machine_type(proj, 1, part, 1, 6, guard=False)
    otp.set_pattern_scale(proj, 1, 0, 16, 2, guard=False)
    otp.set_tempo(proj, BPM)
    card = OUT / "card.img"
    r = subprocess.run([sys.executable, str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(proj),
                        "OCTABAM", "RIG", "--tree", str(OUT / "tree"), "--out", str(card)],
                       capture_output=True, text=True, cwd=ROOT)
    if r.returncode:
        sys.exit(f"verify_md_seq: staging the card failed:\n{r.stdout[-800:]}{r.stderr[-800:]}")
    cf, glue = kit.symbols()
    poke = ";".join(f"{cf['md_patterns'] + i:#x}={b:#x}" for i, b in enumerate(pattern_blob()))
    g = kit.LAYOUT["glue"]
    samples, log = OUT / "samples.txt", OUT / "port.txt"
    spans = f"Y:{kit.VOICE_Y:x},192;X:{g['GAIN']:x},16;X:{g['GAINR']:x},16"
    cmd = [str(kit.EMU), "--image", str(image), "--card", str(card), "--set", "OCTABAM",
           "--project", "RIG", "--sequencer", "--internal-clock", "--frames", str(a.frames),
           "--load-ms", "20000", "--dsp", "--block-dump", str(OUT / "port.dump"),
           "--dsp-sample", f"1:{glue['gnotrg']:x}:{samples}:1000000={spans}",
           "--poke-early", poke]
    with open(log, "w") as f:
        f.write(" ".join(cmd) + "\n"); f.flush()
        r = subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
    if r.returncode:
        sys.exit(f"verify_md_seq: ot_emu exit {r.returncode} -- {log}")
    rows = []
    for line in samples.read_text().splitlines():
        p = line.split("|")
        rows.append([[int(x, 16) for x in s.split()] for s in p[1:]])
    fails = 0

    def check(label, ok, detail=""):
        nonlocal fails
        fails += 0 if ok else 1
        print(f"  [{'ok' if ok else 'FAIL'}] {label}{'  ' + detail if detail else ''}")

    def arrivals(p):
        recs = [r[0][0x40 * p:0x40 * p + 0x40] for r in rows]
        return [(k, rec) for k, rec in enumerate(recs)
                if rec[0] and (k == 0 or not recs[k - 1][0])]

    hits = {p: arrivals(p) for p in range(3)}
    want_id = {0: 0x11, 1: 0x12, 2: 0x17}
    check("kit: the default kit's engines trigger on lanes 1-3",
          all(hits[p] and all(rec[0] == want_id[p] for _, rec in hits[p]) for p in range(3)),
          " ".join(f"lane {p + 1}: {sorted({rec[0] for _, rec in hits[p]})}" for p in range(3)))
    trig, locks = lanes()
    ok, detail = True, []
    # The anchor: lane 1's step 3. Step 1 is due at PLAY, which falls inside
    # the producer's startup hold (MD_START_FRAMES) in a run from boot, so it
    # arrives when the hold ends; every later step is on the grid.
    anchor = hits[0][1][0] - 2 * STEP_FRAMES if len(hits[0]) > 1 else None
    for p in range(3):
        frames = [k for k, _ in hits[p] if k > HOLD]
        if not frames or anchor is None:
            ok = False
            continue
        expect = [s * STEP_FRAMES for n in range(4) for s in (x + 16 * n for x in trig[p])]
        expect = [e for e in expect if e + anchor > HOLD][:len(frames)]
        err = max(abs(f - anchor - e) for f, e in zip(frames, expect))
        if err > 2 or len(frames) != len(expect):
            ok = False
        detail.append(f"lane {p + 1}: {len(frames)} trigs, max error {err:.1f} frames")
    check("steps: every lane trigs on its programmed steps, across the wrap", ok and
          len(hits[0]) >= 8, "; ".join(detail))
    ch = [rec for _, rec in hits[2]]
    if len(ch) >= 2:
        diff = [i for i in range(16) if ch[0][i] != ch[1][i]]
        check("lock: lane 3's locked step differs from its unlocked one", bool(diff) and
              diff[0] > 0, f"differing words {diff}")
    else:
        check("lock: lane 3 has two trigs", False, f"{len(ch)}")
    # part 2's gains: zero between its step-6 trig and its step-10 trig
    sd = [k for k, _ in hits[1]]
    full = (kit.md_gain(100, 64, 0), kit.md_gain(100, 64, 1))
    if len(sd) >= 3:
        mid = rows[min(sd[1] + 20, len(rows) - 1)]
        after = rows[min(sd[2] + 20, len(rows) - 1)]
        check("vol lock: part 2 is silent after its locked trig, restored after the next",
              (mid[1][1], mid[2][1]) == (0, 0) and (after[1][1], after[2][1]) == full,
              f"after step 6 {mid[1][1]:#x}/{mid[2][1]:#x}, after step 10 "
              f"{after[1][1]:#x}/{after[2][1]:#x} (want {full[0]:#x}/{full[1]:#x})")
    else:
        check("vol lock: lane 2 has three trigs", False, f"{len(sd)}")
    # audio: T1's post-FX2 read-back (core 1 -> the ColdFire) carries sound
    # once the lanes play: the glue's mix replaces T1's output.
    sys.path.insert(0, str(ROOT / "tools/harness"))
    import blockdump as bd
    back = [w[0:64:2] for dd, _f, _c, core, ram, w in bd.read(OUT / "port.dump")
            if dd == "<" and core == 1 and ram in (0x80003190, 0x80003590)]
    live = [b for b in back if any(b)]
    peak = max((abs(((x & 0xffff) ^ 0x8000) - 0x8000) for b in live for x in b), default=0)
    check("audio: T1's read-back carries the MD mix while the lanes play",
          len(live) > len(back) // 2, f"{len(live)} of {len(back)} blocks non-silent, peak {peak}")
    print(f"  verify_md_seq: {'PASS' if not fails else f'{fails} FAILED'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
