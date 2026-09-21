#!/usr/bin/env python3
"""PREVIEW VOL gates: a sample preview plays at one level whatever the
active track's AMP VOL, and the track gets its own VOL back when it stops.

    python3 tools/verify/verify_previewvol.py [REMIX] [--project <dir>] [--image IMG] [--work DIR]
    make check REMIX=repitch        # from make verify; OT_PROJECT adds the port cases

1. hooks     both stock preview starters jump into the unit at their REL
             write, and the stub queues AMP VOL 64 and returns after it
2. port      with a project: a copy gets the generated 440 Hz loop on FLEX
             and STATIC slot 1, T1 on that machine, NO trig, and T1's AMP VOL
             (part offset 0x12c) at 0, 64 or 127 in every part. The port
             boots the image, plays, and calls the firmware's own preview
             starter (FLEX 0x40096c54, STATIC 0x400940ac) at frame 300. The
             output after the call must be the same level for all three
             VOLs (and not silent). A FLEX run at VOL 0 then calls the stop
             (0x40096ab0) at frame 900: the live AMP VOL (0x80000810 + 15)
             must be the part's again and the output must fall silent. The
             control runs the STOCK OS at VOL 0: a silent preview there is
             what proves the fixture reaches AMP VOL at all.

Measured once by hand before this gate existed (16 Sep 2026): stock previews
at VOL 0 silent, 64 -> RMS 517,600, 127 -> 2,038,187 (+11.9 dB).
What it cannot see: the panel keys (the port has none; the starters are
called directly, as the UI's preview message does) and hardware timing.
"""
import argparse, math, os, pathlib, re, shutil, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import ot_project as otp  # noqa: E402
import verify_repitch as vr  # noqa: E402  (the loop, the fixture, the card, the wav reader)
from remix import registry  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
STOCK = ROOT / "out/raw/section_3_MAIN_OS.bin"
BASE = 0x40000400
KEY = "PREVIEW VOL"
SITES = {0x40094296: 0x4009429c, 0x40096EB2: 0x40096eb8}    # detour -> return
START = {"flex": "0x40096c54,0,0,-1,1", "static": "0x400940ac,0,0,-1,1,0"}
STOP_FLEX = "0x40096ab0,0"
AMP_VOL = 0x12c           # part-relative: AMP page 1 is the six bytes before FX1's (0x12f)
LANE, LANE_VOL = 0x80000810, 15
CALL, STOP = 300, 900     # frames after the transport start
FRAMES = 1600


def hooks(img):
    """Both sites are `jmp abs.l` into a stub that writes 64 to 15(a0) and
    jumps back to the instruction after the displaced span."""
    rd = lambda a, n: img[a - BASE:a - BASE + n]  # noqa: E731
    ok = True
    for site, back in SITES.items():
        code = rd(site, 6)
        if code[:2] != b"\x4e\xf9":
            print(f"  [FAIL] hooks: 0x{site:08x} is {code.hex()}, not a jmp")
            ok = False
            continue
        stub = int.from_bytes(code[2:], "big")
        body = rd(stub, 24)
        want_vol = bytes.fromhex("117c0040000f")                 # move.b #64,15(a0)
        want_back = b"\x4e\xf9" + back.to_bytes(4, "big")
        if want_vol not in body or want_back not in body:
            print(f"  [FAIL] hooks: stub 0x{stub:08x} for 0x{site:08x} is {body.hex()}")
            ok = False
    print(f"  [{'ok' if ok else 'FAIL'}] hooks: both preview starters queue AMP VOL 64 and return")
    return ok


def fixture(work, project, machine, vol):
    work.mkdir(parents=True, exist_ok=True)
    wav = work / "REPITCH_440_120.wav"
    if not wav.is_file():
        vr.make_loop(wav)
    proj = work / "project"
    vr.build_project(project, proj, 0, 2, 120.0, 64, 127, machine)

    def mut(data):
        for p in range(otp.NPARTS_ALL):
            data[otp.PART_BASE + p * otp.PART_STRIDE + AMP_VOL] = vol
        data[otp.trac_off(0, 0) + 7] &= ~1          # no trig: only the preview sounds
    otp._bank_write(proj, 1, mut, guard=False)
    card = work / "card.img"
    vr.stage(proj, card, wav)
    return card


def rms(v):
    return math.sqrt(sum(a * a for a in v) / max(1, len(v)))


def run(image, work, project, machine, vol, stop=False):
    card = fixture(work, project, machine, vol)
    calls, ats = START[machine], str(CALL)
    if stop:
        calls, ats = f"{calls};{STOP_FLEX}", f"{CALL},{STOP}"
    lane = work / "lane.bin"
    cmd = [str(vr.EMU), "--image", str(image), "--card", str(card), "--set", "OCTABAM", "--project", "RIG",
           "--sequencer", "--internal-clock", "--frames", str(FRAMES), "--load-ms", "20000",
           "--dsp", "--main-level", "64", "--audio-out", str(work / "port"),
           "--call-at", ats, "--call", calls, "--mem-dump", f"{LANE:#x},72={lane}"]
    log = work / "port.txt"
    with open(log, "w") as f:
        f.write(" ".join(cmd) + "\n"); f.flush()
        r = subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
    text = log.read_text()
    returned = len(re.findall(r"^call +: .* returned", text, re.M))
    if r.returncode or "run ended REACHED" not in text or returned != (2 if stop else 1):
        return dict(error=f"port run failed (exit {r.returncode}, {returned} call(s) returned) -- {log}")
    best = None
    for core in (0, 1):
        p = work / f"port_core{core}.wav"
        m = re.search(rf"port_core{core}\.wav, .*?transport start at frame (\d+)", text)
        if not p.is_file() or not m:
            continue
        for x in vr.read_wav24(p):
            x = x[int(m.group(1)):]
            during = rms(x[CALL * 16 + 2000:CALL * 16 + 8000])
            after = rms(x[STOP * 16 + 2000:STOP * 16 + 8000])
            if best is None or during > best[0]:
                best = (during, after)
    if best is None:
        return dict(error=f"no audio written -- {log}")
    return dict(during=best[0], after=best[1], vol=lane.read_bytes()[LANE_VOL], log=log)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("remix", nargs="?", default="repitch")
    ap.add_argument("--project", default=os.environ.get("OT_PROJECT", ""))
    ap.add_argument("--image", default="", help="a built image instead of building the remix")
    ap.add_argument("--work", default=str(ROOT / "out/previewvol"))
    a = ap.parse_args()
    if KEY not in registry.remix(a.remix).modules:
        print(f"  [ -- ] verify_previewvol: {a.remix} carries no {KEY}")
        return 0
    work = pathlib.Path(a.work).resolve()
    work.mkdir(parents=True, exist_ok=True)
    image = work / "image.bin"
    if a.image:
        shutil.copy2(a.image, image)
    else:
        env = dict(os.environ, REMIX=a.remix, XBUS="1", SPEC="1"); env.setdefault("BUILD", "0")
        r = subprocess.run([sys.executable, str(ROOT / "tools/build/build_bus.py")], env=env,
                           capture_output=True, text=True, cwd=ROOT)
        if r.returncode:
            sys.exit(f"verify_previewvol: building {a.remix} failed:\n{(r.stdout + r.stderr)[-1500:]}")
        shutil.copy2(ROOT / "out/mainos_bus.bin", image)

    fails = 0 if hooks(image.read_bytes()) else 1
    if not a.project:
        print("  [SKIP] verify_previewvol: the port cases need a project (OT_PROJECT=<dir> or --project)")
        return 1 if fails else 0
    project = pathlib.Path(a.project).expanduser()
    if not (project / "project.work").is_file():
        sys.exit(f"verify_previewvol: {a.project} is not an Octatrack project directory")
    if not vr.EMU.exists() or not vr.PY.exists() or not STOCK.exists():
        print("  [SKIP] verify_previewvol: the port cases need the port (make emu-cf), the .venv and the stock OS")
        return 1 if fails else 0

    jobs = {(m, v): (image, work / f"{m}-{v}", project, m, v) for m in ("flex", "static") for v in (0, 64, 127)}
    jobs[("stop", 0)] = (image, work / "stop-0", project, "flex", 0, True)
    jobs[("stock", 0)] = (STOCK, work / "stock-0", project, "flex", 0)
    with ThreadPoolExecutor(max_workers=min(8, os.cpu_count() or 4)) as pool:
        futs = {k: pool.submit(run, *args) for k, args in jobs.items()}
        res = {k: f.result() for k, f in futs.items()}
    broken = [k for k, r in res.items() if "error" in r]
    for k in broken:
        print(f"  [FAIL] {k[0]} VOL {k[1]}: {res[k]['error']}")
    if broken:
        return 1

    for m in ("flex", "static"):
        lv = [res[(m, v)]["during"] for v in (0, 64, 127)]
        spread = 20 * math.log10(max(lv) / min(lv)) if min(lv) > 0 else float("inf")
        ok = min(lv) > 1000 and spread < 0.1
        fails += not ok
        print(f"  [{'ok' if ok else 'FAIL'}] {m.upper()} preview at track AMP VOL 0/64/127: RMS "
              + " / ".join(f"{x:,.0f}" for x in lv) + f" (spread {spread:.2f} dB, want < 0.1)")
    s = res[("stop", 0)]
    ok = s["vol"] == 0 and s["during"] > 1000 and s["after"] < 0.01 * s["during"]
    fails += not ok
    print(f"  [{'ok' if ok else 'FAIL'}] FLEX preview stopped: live AMP VOL {s['vol']} (want the part's 0), "
          f"RMS {s['during']:,.0f} -> {s['after']:,.0f}")
    c = res[("stock", 0)]
    ok = c["during"] < 0.01 * res[("flex", 0)]["during"]
    fails += not ok
    print(f"  [{'ok' if ok else 'FAIL'}] control, stock OS: a FLEX preview at AMP VOL 0 is silent "
          f"(RMS {c['during']:,.0f})")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
