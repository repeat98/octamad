#!/usr/bin/env python3
"""SCENES P2 under the port: page-2 locks reach the DSP frame through the
crossfader, and a page-2 knob turned with a scene held writes the pool.

    python3 tools/verify/verify_scenesp2.py REMIX --project DIR

Stages the project's card, boots the remix's image in `ot_emu`, and:

  frame   pokes a pool into every bank's part-0 window (scene 0: T1 FX2
          MODE = 1 and TIME = 100; scene 1: TIME = 20), selects scenes 0/1,
          clears both scene-disable bytes, sets the fader and the stock
          weight table, runs 120 frames with the transport on, and reads
          T1's voice record (0x80000110, both pings): at fader 64 MODE must
          snap to the A side (1) and TIME lerp to 60; at fader 0 the B side
          alone: MODE the knob (measured by a run with the pool's count 0),
          TIME 20. The three runs are three boots side by side (each is one
          LOAD PROJECT, ~32 s under Octakit): a pool poked once the
          transport has started never reaches the live lane, with or
          without a transport restart (measured 28 Sep 2026), so each
          needs the machine as it was after the load: the port loads once
          and forks one child per run (`ot_emu --scenario`), the editor
          pass a fourth.
  editor  calls the FX2 page-2 editor `0x4003a9dc(5, 2 ticks)` on T1 with
          scene A held (0x460d169c = 1): the Part byte and the live lane
          must not move; the pool in the Part DB's part-0 window and its
          SRAM twin must hold one entry (scene 0, track 0, slot 5) whose
          value is the knob's plus the ticks' step. Then, on the same boot
          (`ot_emu --step`), the pool is poked to one entry of 50 and the
          call repeated: the same entry updated, count 1.

SKIPs without a project, without the port, or for a remix without SCENES
P2. Under a remix with Octakit the editor call runs through her wrapper
(SCENES P2 KITS): until 28 Sep 2026 SCENES P2's entry detour displaced
twelve bytes and her trampoline continued at entry+8 into a nop, so the
body read a garbage slot and her marker check halted every page-2 turn.
"""
import argparse, os, pathlib, shutil, subprocess, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
from remix import registry  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
EMU = ROOT / "out/emu/ot_emu"
PY = ROOT / ".venv/bin/python3"
OUT = ROOT / "out/scenesp2verify"
BLOB, BANK_STRIDE, PART_STRIDE = 0x400e21e0, 0x9b340, 0x18b2
POOL_OFF, SEL_OFF = 0x90522, 0x8ed90
RECORDS, DBPTR, SRAM_PART = 0x80000110, 0x46c82456, 0x100a4ece
WEIGHTS, FADER, SCENE_HELD = 0x80003c60, 0x460d16c8, 0x460d169c
TRACK_CUR, PART_DISP = 0x80000000, 0x100b14cf
FX2_EDITOR = 0x4003a9dc
LANES = 0x80000810


def pokes_bytes(addr, data):
    return [f"{addr + i:#x}={v:#x}" for i, v in enumerate(data)]


def weights(xf):
    hi = (-258 * xf) & 0xffff
    lo = (0x8000 + 258 * xf) & 0xffff
    w = (hi << 16) | lo
    out = []
    for t in range(10):
        out += pokes_bytes(WEIGHTS + 4 * t, w.to_bytes(4, "big"))
    return out + pokes_bytes(FADER, xf.to_bytes(4, "big"))


def run(cmd, log):
    with open(log, "w") as f:
        f.write(" ".join(cmd) + "\n"); f.flush()
        r = subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
    if r.returncode:
        sys.exit(f"verify_scenesp2: ot_emu exit {r.returncode} -- {log}")
    return log.read_text()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("remix", nargs="?", default=os.environ.get("REMIX"))
    ap.add_argument("--project", default=os.environ.get("OT_PROJECT", ""))
    ap.add_argument("--set-name", default="OCTABAM")
    ap.add_argument("--name", default="SCENESP2")
    ap.add_argument("--image", default="")
    ap.add_argument("--out", default="", help="scratch dir (default out/scenesp2verify)")
    a = ap.parse_args()
    global OUT
    if a.out:
        OUT = pathlib.Path(a.out)
    remix = registry.remix(a.remix)
    if "SCENES P2" not in remix.modules:
        print(f"  [ -- ] verify_scenesp2: {a.remix} carries no SCENES P2"); return 0
    if not a.project:
        print("  [SKIP] verify_scenesp2: no project (OT_PROJECT=<dir> or --project)"); return 0
    if not EMU.is_file():
        print("  [SKIP] verify_scenesp2: no port binary (make emu-cf)"); return 0
    pdir = pathlib.Path(a.project).expanduser()
    if not (pdir / "project.work").is_file():
        sys.exit(f"verify_scenesp2: {pdir} is not a project")
    OUT.mkdir(parents=True, exist_ok=True)
    image = pathlib.Path(a.image) if a.image else OUT / "mainos.bin"
    if not a.image:
        env = dict(os.environ, REMIX=a.remix, XBUS="1", SPEC="1"); env.setdefault("BUILD", "0")
        r = subprocess.run([sys.executable, str(ROOT / "tools/build/build_bus.py")], env=env,
                           capture_output=True, text=True, cwd=ROOT)
        if r.returncode:
            sys.exit(f"verify_scenesp2: building {a.remix} failed:\n{(r.stdout + r.stderr)[-1500:]}")
        shutil.copy2(ROOT / "out/mainos_bus.bin", image)
    copy = OUT / "project"
    if copy.exists():
        shutil.rmtree(copy)
    copy.mkdir(parents=True)
    for f in pdir.iterdir():
        if f.is_file() and f.suffix.lower() == ".work":
            shutil.copy2(f, copy / f.name)
    card = OUT / "card.img"
    r = subprocess.run([str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(copy), a.set_name, a.name,
                        "--tree", str(OUT / "tree"), "--out", str(card)], cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"verify_scenesp2: stage_card failed:\n{r.stdout[-1000:]}{r.stderr[-1000:]}")
    base = [str(EMU), "--image", str(image), "--card", str(card), "--set", a.set_name, "--project", a.name,
            "--load-ms", "90000"]
    fails = 0

    def check(msg, ok):
        nonlocal fails
        print(f"  [{'ok' if ok else 'FAIL'}] {msg}")
        fails += not ok

    # ---- the frame pass ---------------------------------------------------
    # the pool: 'P2', 3 entries -- scene 0 / T1 / FX2 slot 5 (TIME) = 100,
    # scene 1 / T1 / slot 5 = 20, scene 0 / T1 / slot 0 (MODE) = 1 -- in part
    # 0 of every bank (the playing bank is the saved one, not bank 0)
    pool = [0x50, 0x32, 3, 0x00, 0x05, 100, 0x08, 0x05, 20, 0x00, 0x00, 1]

    def frames(tag, pool, xf):
        """One frame run as a scenario: (log, args, dump)."""
        common = []
        for bank in range(16):
            common += pokes_bytes(BLOB + bank * BANK_STRIDE + POOL_OFF, pool)
            common += pokes_bytes(BLOB + bank * BANK_STRIDE + SEL_OFF, [0, 1])
        common += ["0x80000006=0", "0x80000007=0"]
        tag_ = tag.replace(" ", "_")
        dump, log = OUT / f"rec_{tag_}.bin", OUT / f"frames_{tag_}.txt"
        args = ["--sequencer", "--internal-clock", "--frames", "120", "--main-level", "64",
                "--poke-trig", "2", "--poke", ";".join(common + weights(xf)),
                "--mem-dump", f"{RECORDS:#x},1024={dump}"]
        return log, args, dump

    # ---- the editor with a scene held: one boot, both seeds ----------------
    early = f"{TRACK_CUR:#x}=0;{SCENE_HELD + 3:#x}=1;{PART_DISP:#x}=0"
    SEEDS = (None, 50)

    def dumps_for(seed):
        d = OUT / f"editor_{seed}"
        d.mkdir(parents=True, exist_ok=True)
        return d, ";".join([f"{DBPTR:#x},4={d / 'dbptr.bin'}"]
                           + [f"{BLOB + b * BANK_STRIDE + POOL_OFF:#x},12={d / f'pool_{b}.bin'}" for b in range(16)]
                           + [f"{BLOB + b * BANK_STRIDE + 0x8f084:#x},6={d / f'p2_{b}.bin'}" for b in range(16)]
                           + [f"{SRAM_PART + POOL_OFF - 0x8ed80:#x},12={d / 'pool_sram.bin'}",
                              f"{LANES + 0x38:#x},6={d / 'lane.bin'}"])

    def editor():
        """Both seeds as one scenario: (log, args)."""
        steps = []
        for seed in SEEDS:
            pokes = early
            if seed is not None:
                for b in range(16):
                    pokes += ";" + ";".join(pokes_bytes(BLOB + b * BANK_STRIDE + POOL_OFF, [0x50, 0x32, 1, 0, 5, seed]))
            steps += ["--step", f"-:poke:{pokes}", "--step", f"-:call:{FX2_EDITOR:#x},5,2",
                      "--step", f"-:dump:{dumps_for(seed)[1]}"]
        return OUT / "editor.txt", steps

    # the knob alone: the same run with the pool's count 0, so what fader 0
    # (the B side, which holds no MODE lock) must read is measured from the
    # project: T1's MODE is 1 in the stress fixture's part 0 and 0 in
    # OCTABAM89_setgate's (a literal 0 failed `make accept`, 26 Sep 2026)
    # ONE load, four scenarios forked from it (ot_emu --scenario, 29 Sep
    # 2026): the three frame runs and the editor pass each start from the
    # same loaded machine. Until then each was its own LOAD PROJECT (~32 s
    # emulated under Octakit), three side by side and one after.
    specs = {tag: frames(tag, pl, xf)
             for tag, pl, xf in (("knob", pool[:2] + [0] + pool[3:], 0), ("fader 64", pool, 64), ("fader 0", pool, 0))}
    elog, eargs = editor()
    scen = [f"{log} " + " ".join(args) for log, args, _ in specs.values()] + [f"{elog} " + " ".join(eargs)]
    cmd = base + ["--dsp"] + [x for s in scen for x in ("--scenario", s)]
    run(cmd, OUT / "port.txt")
    results = {}
    for tag, (log, _, dump) in specs.items():
        text = log.read_text()
        rec = dump.read_bytes() if dump.is_file() else bytes(1024)
        results[tag] = ("frames run : 120" in text, [rec[ping * 0x200:ping * 0x200 + 64] for ping in (0, 1)])
    editor_text = elog.read_text()
    for tag, (ran, _) in results.items():
        check(f"{tag}: 120 frames ran", ran)
    recs = {tag: r for tag, (_, r) in results.items()}
    knob = recs["knob"]
    knob_mode = knob[0][48]
    check(f"knob alone: both pings read T1 MODE {knob_mode}", knob[1][48] == knob_mode)
    for xf, want_mode, want_time, why in ((64, 1, 60, "the A side, a select snaps"),
                                          (0, knob_mode, 20, "the knob, B alone")):
        for ping, r in enumerate(recs[f"fader {xf}"]):
            check(f"fader {xf}: ping {ping} T1 MODE (hw 24 hi) = {r[48]} (want {want_mode}: {why})",
                  r[48] == want_mode)
            check(f"fader {xf}: ping {ping} T1 TIME (hw 26 lo) = {r[53]} (want {want_time})", r[53] == want_time)

    # ---- the editor's checks ------------------------------------------------
    check(f"editor: both calls returned", editor_text.count("returned, d0") == len(SEEDS))
    for seed in SEEDS:
        d = dumps_for(seed)[0]
        db = int.from_bytes((d / "dbptr.bin").read_bytes(), "big")
        bank = (db - BLOB) // BANK_STRIDE
        got = (d / f"pool_{bank}.bin").read_bytes()
        sram = (d / "pool_sram.bin").read_bytes()
        lane = (d / "lane.bin").read_bytes()
        part = (d / f"p2_{bank}.bin").read_bytes()
        knob = part[5]
        check(f"editor (seed {seed}): pool magic + count 1 in bank {bank}'s part 0 ({got[:3].hex(' ')})",
              got[:3] == bytes([0x50, 0x32, 1]))
        check(f"editor (seed {seed}): entry = scene 0 / T1 / FX2 slot 5 ({got[3:5].hex(' ')})", got[3:5] == bytes([0, 5]))
        start = seed if seed is not None else knob
        check(f"editor (seed {seed}): value {got[5]} moved up from {start} by the ticks", start < got[5] <= start + 4)
        check(f"editor (seed {seed}): the SRAM twin matches ({sram[:6].hex(' ')})", sram[:6] == got[:6])
        check(f"editor (seed {seed}): the Part byte ({knob}) and the lane ({lane[5]}) did not take the turn",
              knob == lane[5] and knob != got[5])
    print(f"verify_scenesp2: {'FAIL' if fails else 'ok'} ({fails} failure(s))")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
