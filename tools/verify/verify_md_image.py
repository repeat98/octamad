#!/usr/bin/env python3
"""The Machinedrum on core 1, end to end under the ColdFire port (WP-B3/B4).

    python3 tools/verify/verify_md_image.py [--project DIR] [--frames 700]
    OT_PROJECT=DIR [MD_EMU=path/to/ot_emu] make verify-md

Builds REMIX=machinedrum, copies the project with MACHINEDRUM (id 0x1e) in
T1's FX2 slot of every part of every bank, stages it, boots the image under
the port with both DSP cores and the sequencer running, and samples the glue
at the end of every gfxproc call (tools/build/md_image.py writes its
symbols). Then:

  owner      the instance belongs to T1 (gfxinit ran on T1's FX2 slot);
  trigger    the OT's trigs on T1 reached slot 0 (the glue's trig count),
             and slot 0's engine is TRX-BD (routine index 0x11);
  reference  slot 0's 32-sample blocks equal the MD reference's own output
             for the same trigger (c10's slot-0 "O" lines, md_profile), bit
             for bit, for every period before the OT's second trig retriggers
             it (c10 has no retrigger there);
  audio      T1's post-FX2 read-back (core 1 -> the ColdFire) carries the
             glue's output blocks verbatim.

THE EMULATOR PIN MATTERS. The port built from a dsp56300 older than the
repo's pin (scripts/setup.sh DSP56300_PIN) diverged from the reference at
period 25 with a sign flip (24 Sep 2026, c051afad); the same image on a port
built from the current pin plus tools/patches/dsp56300.patch matched every
period up to the retrigger. A FAIL at `reference` names the port it ran:
rebuild the port (`scripts/setup.sh`, then `make emu-cf`) before believing
it. MD_EMU points the gate at another port binary.

SKIPs without a project, the port, the MD payload artifact
(tools/build/md_payload.py) or the c10 capture. What it cannot see: the
unit's timing, the other core's real concurrency, E12 samples (not loaded).
"""
import argparse
import os
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
import runpy  # noqa: E402

OUT = ROOT / "out/mdverify"
EMU = pathlib.Path(os.environ.get("MD_EMU") or ROOT / "out/emu/ot_emu")
MDB = ROOT / "out/machinedrum/build"
C10 = ROOT / "out/md_profile/cap4/c10/log.txt"
LAYOUT = runpy.run_path(str(ROOT / "modules/machinedrum/layout.py"))["LAYOUT"]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--project", default=os.environ.get("OT_PROJECT", ""))
    ap.add_argument("--frames", type=int, default=700)
    ap.add_argument("--load-ms", type=int, default=20000)
    a = ap.parse_args()
    if not a.project:
        print("  [SKIP] verify_md_image: no project (OT_PROJECT=<dir> or --project)")
        return 0
    for need, what in ((EMU, "the ColdFire port (make emu-cf)"),
                       (MDB / "payload_B.mem", "the MD payload (tools/build/md_payload.py)"),
                       (C10, "the c10 capture (md_profile)")):
        if not need.exists():
            print(f"  [SKIP] verify_md_image: no {what}")
            return 0
    import verify_set as vs
    import ot_project as otp

    OUT.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, REMIX="machinedrum", XBUS="1", SPEC="1")
    env.setdefault("BUILD", "0")
    r = subprocess.run([sys.executable, str(ROOT / "tools/build/build_bus.py")], env=env,
                       capture_output=True, text=True, cwd=ROOT)
    if r.returncode:
        sys.exit(f"verify_md_image: building machinedrum failed:\n{(r.stdout + r.stderr)[-1500:]}")
    image = OUT / "image.bin"
    shutil.copy2(ROOT / "out/mainos_bus.bin", image)

    src = pathlib.Path(a.project).expanduser()
    proj = OUT / "project"
    if proj.exists():
        shutil.rmtree(proj)
    shutil.copytree(src, proj)
    otp.set_fx(proj, "fx2", 1, "MACHINEDRUM", page=[100, 0, 0, 0, 0, 0], guard=False)
    bank = 1
    part = vs.part_of(proj, bank, vs.otp.bank_info(proj, bank)[0][0] + 1)
    paths = vs.sample_paths(proj)
    audio = []
    for t in range(8):
        kind = vs.TYPE_NAME.get(part["mtype"][t])
        if kind not in ("STATIC", "FLEX"):
            continue
        rel = paths.get((kind, (part["static"] if kind == "STATIC" else part["flex"])[t] + 1))
        if not rel:
            continue
        # "../AUDIO/x.wav" is the set's AUDIO folder; a project copied on its
        # own may keep that folder inside itself instead.
        found = next((f for f in (src / rel, src / rel[3:]) if f.is_file()), None)
        if found is None:
            continue
        spec = f"{found.resolve()}:{rel[3:] if rel.startswith('../') else 'RIG/' + rel}"
        if spec not in audio:
            audio.append(spec)
    card = OUT / "card.img"
    cmd = [sys.executable, str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(proj), "OCTABAM", "RIG",
           "--tree", str(OUT / "tree"), "--out", str(card)]
    for x in audio:
        cmd += ["--audio", x]
    # THE TRIG FLAG IS A SAMPLE VOICE STARTING (bit 16 of the track state's
    # word $1e): a T1 without a sample never sets it, and the fixed trigger
    # never fires. Say so rather than failing on "0 trigs" later.
    kind1 = vs.TYPE_NAME.get(part["mtype"][0])
    if not any(x.split(":", 1)[0] for x in audio) or kind1 not in ("STATIC", "FLEX"):
        print(f"  [SKIP] verify_md_image: T1 of bank {bank}'s first part is {kind1} with no "
              f"staged sample -- the fixed trigger keys on a sample voice starting")
        return 0
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    if r.returncode:
        sys.exit(f"verify_md_image: staging the card failed:\n{r.stdout[-800:]}{r.stderr[-800:]}")

    g, d = LAYOUT["glue"], LAYOUT["driver"]
    sym = {l.split()[0]: int(l.split()[1], 16)
           for l in (MDB / "glue.sym").read_text().splitlines() if l.strip()}
    samples, dump, log = OUT / "glue.txt", OUT / "port.dump", OUT / "port.txt"
    spans = (f"X:{g['TRIGS']:x},1;X:{g['OWNER']:x},1;Y:{d['HALF']:x},1;Y:{d['ENG']:x},1;"
             f"Y:{d['OUTBUF']:x},32;X:0,32")
    cmd = [str(EMU), "--image", str(image), "--card", str(card), "--set", "OCTABAM", "--project", "RIG",
           "--sequencer", "--internal-clock", "--frames", str(a.frames), "--load-ms", str(a.load_ms),
           "--dsp", "--block-dump", str(dump),
           "--dsp-sample", f"1:{sym['gcpylp']:x}:{samples}:1000000={spans}"]
    with open(log, "w") as f:
        f.write(" ".join(cmd) + "\n"); f.flush()
        r = subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
    if r.returncode:
        sys.exit(f"verify_md_image: ot_emu exit {r.returncode} -- {log}")
    text = log.read_text()

    fails = 0

    def check(label, ok, detail=""):
        nonlocal fails
        fails += 0 if ok else 1
        print(f"  [{'ok' if ok else 'FAIL'}] {label}{'  ' + detail if detail else ''}")

    import re
    ran = re.search(r"frames run : (\d+) since transport start \(target (\d+)\), run ended (\w+)", text)
    check("load: the project loaded and the frames ran", ran is not None and ran.group(3) == "REACHED",
          f"frames {ran.group(1)}/{ran.group(2)}" if ran else "no frames line")
    rows = []
    for line in samples.read_text().splitlines():
        p = line.split("|")
        rows.append([[int(x, 16) for x in s.split()] for s in p[1:]])
    check("glue: gfxproc ran every frame", len(rows) >= a.frames, f"{len(rows)} calls")
    if not rows:
        return 1
    trigs, owner = rows[-1][0][0], rows[-1][1][0]
    check("owner: the instance is T1's (gfxinit on T1's FX2)", owner == 0, f"owner offset {owner:#x}")
    eng = [r[3][0] for r in rows if r[0][0] >= 1]
    check("trigger: the OT's trigs on T1 reached slot 0 as TRX-BD", trigs >= 1 and eng and eng[-1] == 0x11,
          f"{trigs} trig(s), slot 0 engine {eng[-1] if eng else 0:#x}")

    # reference: slot 0's block after each call that rendered slots 0-7
    ours, second, prev = [], None, None
    for r in rows:
        half, blk, n = r[2][0], r[4], r[0][0]
        if half == 8 and blk != prev:
            ours.append(blk)
            if n >= 2 and second is None:
                second = len(ours) - 1
        prev = blk if half == 8 else prev
    ref = []
    with open(C10) as fh:
        for line in fh:
            if line.startswith("O 0 "):
                ref.append([int(x, 16) for x in line.split()[2:]])
    fo = next((i for i, b in enumerate(ours) if any(b)), None)
    fr = next((i for i, b in enumerate(ref) if any(b)), None)
    if fo is None or fr is None:
        check("reference: slot 0 rendered", False)
    else:
        upto = (second - fo) if second is not None else min(len(ours) - fo, len(ref) - fr)
        same = next((k for k in range(upto) if ours[fo + k] != ref[fr + k]), upto)
        check("reference: slot 0 == the MD's own render until the OT retriggers it", same == upto and upto >= 16,
              f"{same} of {upto} periods bit-identical ({EMU})")
    # audio: T1's read-back carries the glue's output blocks
    sys.path.insert(0, str(ROOT / "tools/harness"))
    import blockdump as bd
    # Every T1 read-back block (one per frame, the upper 16 bits of each
    # sample) must be one the glue left in X:0 at the end of a call; a frame
    # split at a trig has two calls, and its first leaves a partial block.
    back = [tuple(w[0:64:2]) for dd, _f, _c, core, ram, w in bd.read(dump)
            if dd == "<" and core == 1 and ram in (0x80003190, 0x80003590)]
    outs = {tuple((x >> 8) & 0xffff for x in r[5]) for r in rows}
    live = [b for b in back if any(b)]
    hit = sum(1 for b in live if b in outs)
    check("audio: T1's post-FX2 read-back is the Machinedrum mix", live and hit == len(live),
          f"{hit} of {len(live)} non-silent read-back blocks are glue output blocks")
    print(f"  verify_md_image: {'PASS' if not fails else f'{fails} FAILED'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
