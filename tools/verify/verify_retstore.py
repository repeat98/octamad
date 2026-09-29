#!/usr/bin/env python3
"""MASTER STRIP's Part storage for the returns and the sends (MIXER.md section 20):
under the port, RET A, RET B, the AUX sends and the returns' levels live in the Part.

    OT_PROJECT=<dir> python3 tools/verify/verify_retstore.py [REMIX]

modules/strip/strip_xport.s keeps five 16-byte cells in each Part window, 80 bytes at
bank + 0x90492 (the audio LFO designer's shapes T2..T6, beside the strip's T7 and T8):
0 RET B's slot, 1 RET A's, 2 AUX A's twelve sends, 3 AUX B's, 4 the levels (RET B's
level and CUE send, RET A's), each as the strip's slots are stored: id, tag 0x53,
checksum, version 1, twelve values. ret_sync (the host-transfer ISR, once a frame) adopts
the window of the part the panel edits after two frames of stillness; ret_store (the
MIXER page's edits on a return) writes it back, to the part's SRAM twin and with the
stock editors' dirty marks. The same cases as verify_stripstore, on the returns' window:

  fresh    nothing written: ret_model and aux_model zero, the levels 100, the window zero
  edit     MIXER, RIGHT, RIGHT, DOWN, A +10 (T1 into AUX A): the model, the window, its
           twin and ret_seen agree in stored form, the edited words are 1
  choose   the delay server onto RETURN A in its SETUP: id 6 in cell 1, valid
  load     a valid window poked in while the unit runs is the models (spare bytes 0),
           the window untouched
  bad      a stale checksum, and an id off the returns' list: the defaults both times
  reload   a record, then zeros: the defaults again
  part1    part 1's window poked and the panel's part set to 1: the models follow
  part4    the panel's part set to 4: an edit reaches the model and no window
  dsp      with the DSP: a loaded record reaches core 0 (the levels, RET B's id, the
           sends) and RET A's id and record reach the exchange (X:0x3701f)

What it cannot see: a Part Save or Reload through the panel, the bank file, the Octakit's
kit windows (part 4 is the guard).
"""
import argparse, contextlib, os, pathlib, re, shutil, subprocess, sys, tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
from remix import registry  # noqa: E402
import verify_dspsite as vds  # noqa: E402
import verify_strip as vst  # noqa: E402
import verify_mixerpages as vmp  # noqa: E402
import verify_aux as va  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
KEY = "MASTER STRIP"
BLOB = 0x400e21e0
PSTRIDE, RWOFF, RTWOFF = 0x18b2, 0x90492, 0x1712
SRAM_PART = 0x100a4ece
DIRTY_BANK, DIRTY_SRAM = 0x95048, 0x100b145e
EDITED_BANK, EDITED_SRAM = 0x9b332, 0x100f8598
PARTSEL = 0x100b14cf
TAG, VERSION = 0x53, 1
OXIDE, DELAY, REVERB = 0x1f, 0x06, 0x07

fails = 0


def check(label, ok, detail=""):
    global fails
    print(f"  [{'ok' if ok else 'FAIL'}] {label}" + (f"  {detail}" if detail else ""))
    fails += 0 if ok else 1
    return ok


def cell(ident, values):
    b = [ident, TAG, 0, VERSION] + list(values) + [0] * (12 - len(values))
    b[2] = -sum(b) & 0xff
    return b


def window(rb, ra, sa, sb, lv):
    return cell(rb[0], rb[1]) + cell(ra[0], ra[1]) + cell(0, sa) + cell(0, sb) + cell(0, lv)


def mcell(ident, values):
    return [ident, 0, 0, 0] + list(values) + [0] * (12 - len(values))


def models(rb, ra, sa, sb, lv):
    """ret_model, aux_model, retlvl_model as the record asks for them."""
    return (mcell(*rb) + mcell(*ra), mcell(0, sa) + mcell(0, sb),
            mcell(0, lv[0:2]) + mcell(0, lv[2:4]))


BOOT = models((0, []), (0, []), [], [], [100, 0, 100, 0])
REC = dict(rb=(OXIDE, [30, 90]), ra=(DELAY, [0, 20, 40, 0, 50, 60, 0, 70, 80, 0, 0, 90]),
           sa=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], sb=[12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1],
           lv=[80, 10, 90, 20])
REC2 = dict(rb=(0, []), ra=(OXIDE, [55, 66]), sa=[0] * 12, sb=[21, 22, 23], lv=[70, 0, 60, 5])
W_A = window(**REC)
W_B = window(**REC2)
M_A = models(**REC)
M_B = models(**REC2)
BAD_SUM = list(W_A)
BAD_SUM[36] = 99                                  # a send in cell 2 changed, the checksum stale
BAD_ID = window((0x22, []), REC["ra"], REC["sa"], REC["sb"], REC["lv"])   # an id off the list
ZEROS = [0] * 80


def win(part):
    return BLOB + RWOFF + part * PSTRIDE


def twin(part):
    return SRAM_PART + RTWOFF + part * PSTRIDE


def poke(addr, data):
    return "poke " + ";".join(f"{addr + i:#x}={b:#x}" for i, b in enumerate(data))


def valid(w):
    return len(w) == 80 and all(w[16 * k + 1] == TAG and w[16 * k + 3] == VERSION
                                and sum(w[16 * k:16 * k + 16]) & 0xff == 0 for k in range(5))


CASES = {
    "fresh": (["wait 600"], 400),
    "edit": (["MIXER", "RIGHT", "RIGHT", "DOWN", "enc 0 10"], 600),
    "choose": (["MIXER", "RIGHT", "RIGHT", "YES", "DOWN", "DOWN", "YES", "NO"], 600),
    "load": ([poke(win(0), W_A), "wait 600"], 400),
    "bad_sum": ([poke(win(0), BAD_SUM), "wait 300"], 300),
    "bad_id": ([poke(win(0), BAD_ID), "wait 300"], 300),
    "reload": ([poke(win(0), W_A), "wait 400", poke(win(0), ZEROS), "wait 400"], 300),
    "part1": ([poke(win(1), W_B), poke(PARTSEL, [1]), "wait 600"], 400),
    "part1_edit": ([poke(win(1), W_B), poke(PARTSEL, [1]), "wait 400", "MIXER", "RIGHT", "RIGHT", "RIGHT",
                    "DOWN", "DOWN", "DOWN", "enc 0 -20"], 600),
    "part4": ([poke(win(0), W_A), poke(PARTSEL, [4]), "wait 400", "MIXER", "RIGHT", "RIGHT", "DOWN",
               "enc 0 10"], 600),
}
DSP_CASES = {"dsp": [poke(win(0), window(**dict(REC, rb=(OXIDE, [30, 90]), ra=(OXIDE, [48, 80])))), "wait 700"]}


def dumps(work, c, sym):
    d = work / c
    spec = [f"{sym['ret_model']:#x},32={d}.ret", f"{sym['aux_model']:#x},32={d}.aux",
            f"{sym['retlvl_model']:#x},32={d}.lvl", f"{sym['ret_seen']:#x},80={d}.seen",
            f"{sym['strip_lock']:#x},1={d}.lock", f"{win(0):#x},80={d}.w0", f"{win(1):#x},80={d}.w1",
            f"{twin(0):#x},80={d}.t0", f"{twin(1):#x},80={d}.t1",
            f"{BLOB + DIRTY_BANK:#x},1={d}.d_bank", f"{DIRTY_SRAM:#x},1={d}.d_sram",
            f"{BLOB + EDITED_BANK:#x},4={d}.e_bank", f"{EDITED_SRAM:#x},4={d}.e_sram", f"{PARTSEL:#x},1={d}.sel"]
    return ";".join(spec)


def port(name, built, project, sym):
    import verify_set as vs
    import ot_project as otp
    if not vds.EMU.exists() or not vds.PY.exists():
        print("  [SKIP] port: the ColdFire port (make emu-cf) or the .venv is missing")
        return
    with tempfile.TemporaryDirectory(prefix="retstore_") as work:
        work = pathlib.Path(work)
        (work / "built.bin").write_bytes(bytes(built))
        proj = work / "src"
        shutil.copytree(pathlib.Path(project).expanduser(), proj,
                        ignore=shutil.ignore_patterns("*.wav", "*.WAV", "*.ot"))
        raw = (proj / "project.work").read_bytes()
        bank = int(re.search(rb"\r\nBANK=(\d+)\r\n", raw).group(1)) + 1
        pat_part, _ = otp.bank_info(proj, bank)
        part = vs.part_of(proj, bank, pat_part[0] + 1)
        card = work / "card.img"
        vs.stage(proj, part, "OCTABAM", "RIG", work / "tree", 64, bank, card)
        args = []
        for c, (steps, tail) in CASES.items():
            vmp.script(work / f"{c}.txt", steps, tail)
            args += ["--scenario", f"{work / c}.log --live-script {work / c}.txt --mem-dump {dumps(work, c, sym)}"]
        shutil.copy2(card, work / "card_built.img")
        runs = [subprocess.Popen(
            [str(vds.EMU), "--image", str(work / "built.bin"), "--card", str(work / "card_built.img"),
             "--set", "OCTABAM", "--project", "RIG", "--load-ms", "90000", "--scenario-jobs", "4"] + args,
            cwd=ROOT, stdout=open(work / "built.txt", "w"), stderr=subprocess.STDOUT)]
        for c, steps in DSP_CASES.items():
            vmp.script(work / f"{c}.txt", steps, 400)
            shutil.copy2(card, work / f"card_{c}.img")
            runs.append(subprocess.Popen(
                [str(vds.EMU), "--image", str(work / "built.bin"), "--card", str(work / f"card_{c}.img"),
                 "--set", "OCTABAM", "--project", "RIG", "--load-ms", "90000", "--dsp",
                 "--live-script", str(work / f"{c}.txt"),
                 "--dsp-peek", "0:X:7c80,24;0:X:7c98,4;0:X:7ce0,2;0:X:3701f,1;0:X:37010,16",
                 "--mem-dump", dumps(work, c, sym)],
                cwd=ROOT, stdout=open(work / f"{c}.log", "w"), stderr=subprocess.STDOUT))
        codes = [p.wait() for p in runs]
        check("port: every load ran", all(c == 0 for c in codes), f"exit codes {codes}")
        R = {}
        for c in list(CASES) + list(DSP_CASES):
            log = (work / f"{c}.log").read_text() if (work / f"{c}.log").exists() else ""
            if not check(f"port: {c}: the panel script ended on quit", "ended on quit" in log,
                         (re.search(r"live script: .*", log) or re.search(r".*$", log)).group(0)[:120]):
                continue
            r = {"log": log}
            for k in ("ret", "aux", "lvl", "seen", "lock", "w0", "w1", "t0", "t1", "d_bank", "d_sram",
                      "e_bank", "e_sram", "sel"):
                r[k] = list((work / f"{c}.{k}").read_bytes())
            R[c] = r
        checks(R)


def checks(R):
    def have(*cs):
        miss = [c for c in cs if c not in R]
        if miss:
            print(f"  [SKIP] needs {miss}")
        return not miss

    mdl = lambda r: (r["ret"], r["aux"], r["lvl"])
    if not have("fresh"):
        return
    base = R["fresh"]
    check("fresh: the models are the defaults (no return, no sends, both levels 100)", mdl(base) == BOOT, mdl(base)[2][:6])
    check("fresh: nothing is written into either window or twin, the edited words are 0",
          all(base[k] == ZEROS for k in ("w0", "w1", "t0", "t1")) and base["e_bank"] == [0] * 4
          and base["e_sram"] == [0] * 4 and base["lock"] == [0])
    nomark = lambda r: (r["d_bank"] == base["d_bank"] and r["d_sram"] == base["d_sram"]
                        and r["e_bank"] == [0] * 4 and r["e_sram"] == [0] * 4)

    if have("edit"):
        r = R["edit"]
        aux = r["aux"]
        want = window((r["ret"][0], r["ret"][4:16]), (r["ret"][16], r["ret"][20:32]), aux[4:16], aux[20:32],
                      [r["lvl"][4], r["lvl"][5], r["lvl"][20], r["lvl"][21]])
        check("edit: A +10 on RETURN A's SND1 moved T1 into AUX A's cell, nothing else",
              aux[4] > 0 and aux[5:16] == [0] * 11 and aux[16:] == [0] * 16, aux[:8])
        check("edit: the window is the models' stored form, all five cells valid", r["w0"] == want and valid(r["w0"]),
              r["w0"][32:40])
        check("edit: its SRAM twin holds the same bytes, and the ISR's look has them (ret_seen)",
              r["t0"] == want and r["seen"] == want)
        check("edit: the bank's edited word and 0x100f8598 are 1", r["e_bank"] == [0, 0, 0, 1]
              and r["e_sram"] == [0, 0, 0, 1], f"{r['e_bank']} {r['e_sram']}")
        check("edit: part 1 untouched, the ISR's look not held off", r["w1"] == ZEROS and r["t1"] == ZEROS
              and r["lock"] == [0])

    if have("choose"):
        r = R["choose"]
        check("choose: the delay server onto RETURN A: cell 1 is id 6, valid; RET B's is none",
              r["ret"][16] == DELAY and r["ret"][0] == 0 and r["w0"][16] == DELAY and valid(r["w0"]),
              f"model {r['ret'][16]} window {r['w0'][16]}")

    if have("load"):
        r = R["load"]
        check("load: a record poked into the window is the models, spare bytes 0", mdl(r) == M_A,
              f"ret {r['ret'][:6]} lvl {r['lvl'][4:6]} {r['lvl'][20:22]}")
        check("load: the window is untouched, no twin write, no dirty mark", r["w0"] == W_A and r["t0"] == ZEROS
              and nomark(r))

    for c, w in (("bad_sum", BAD_SUM), ("bad_id", BAD_ID)):
        if have(c):
            r = R[c]
            check(f"{c}: refused: the defaults, the window left as poked", mdl(r) == BOOT and r["w0"] == w,
                  mdl(r)[2][:6])
    if have("reload"):
        r = R["reload"]
        check("reload: after the record, then zeros, the models are the defaults again",
              mdl(r) == BOOT and r["w0"] == ZEROS)

    if have("part1"):
        r = R["part1"]
        check("part1: the panel's part 1 shows part 1's record; part 0's window is untouched",
              r["sel"] == [1] and mdl(r) == M_B and r["w0"] == ZEROS and r["w1"] == W_B,
              f"sel {r['sel']} lvl {r['lvl'][4:6]}")
    if have("part1_edit"):
        r = R["part1_edit"]
        want = window((r["ret"][0], r["ret"][4:16]), (r["ret"][16], r["ret"][20:32]), r["aux"][4:16],
                      r["aux"][20:32], [r["lvl"][4], r["lvl"][5], r["lvl"][20], r["lvl"][21]])
        check("part1_edit: LEVEL-row edit on RETURN B's OUT lowered its level (70 - 20 steps) and the record "
              "follows it, in part 1's window and twin only",
              r["lvl"][4] < 70 and r["w1"] == want and r["t1"] == want and r["w0"] == ZEROS and r["t0"] == ZEROS,
              f"lvl {r['lvl'][4:6]}")
        check("part1_edit: part 1's dirty bit (bit 1) is newly set, the edited words are 1",
              r["d_bank"][0] == base["d_bank"][0] | 2 and r["d_sram"][0] == base["d_sram"][0] | 2
              and r["e_bank"] == [0, 0, 0, 1] and r["e_sram"] == [0, 0, 0, 1],
              f"{r['d_bank']} {r['d_sram']} (loaded {base['d_bank']} {base['d_sram']})")
    if have("part4"):
        r = R["part4"]
        check("part4: a part that is not stock's four keeps the models to itself: the edit reached the model "
              "and no window, twin or dirty mark", r["aux"][4] > 0 and r["w0"] == W_A and r["t0"] == ZEROS
              and r["w1"] == ZEROS and nomark(r) and r["lock"] == [0], f"aux {r['aux'][:8]} lock {r['lock']}")

    if have("dsp"):
        r = R["dsp"]
        pk = vmp.peek(r["log"])
        gains = pk.get(0x7c80, [])
        want = [va.gain(v) for v in REC["sa"]] + [va.gain(v) for v in REC["sb"]]
        cap = va.gain(100)
        want = [min(g, cap) if i in (10, 11, 22, 23) else g for i, g in enumerate(want)]
        check("dsp: the loaded sends reach core 0 as (v/128)^2 gains, the returns' terms capped at 0.61",
              gains == want, f"got {vmp.hexs(gains[:4])} want {[hex(x) for x in want[:4]]}")
        lv = pk.get(0x7c98, [])
        check("dsp: the levels and CUE sends reach core 0, RET B's first then RET A's",
              lv == [va.gain(v) for v in REC["lv"]], vmp.hexs(lv))
        slot = pk.get(0x7ce0, [])
        check("dsp: RET B's slot runs OXIDE (id and proc set)", len(slot) == 2 and slot[0] == OXIDE and slot[1] != 0,
              vmp.hexs(slot))
        check("dsp: RET A's id and record are forwarded to the exchange (X:0x3701f, 0x37010..)",
              pk.get(0x3701f) == [OXIDE] and pk.get(0x37010, [0] * 16)[:2] == [48 << 16, 80 << 16],
              f"{vmp.hexs(pk.get(0x3701f))} {vmp.hexs(pk.get(0x37010, [])[:2])}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("remix", nargs="*")
    ap.add_argument("--project", default=os.environ.get("OT_PROJECT", ""))
    a = ap.parse_args()
    if not vds.STOCK.exists():
        print("  [SKIP] verify_retstore: no stock image (make os)")
        return 0
    names = a.remix or ["strip"]
    names = [n for n in names if KEY in registry.remix(n).modules]
    if not names:
        print(f"  [--] verify_retstore: no remix selected carries {KEY}")
        return 0
    for name in names:
        built, report = vds.build(name)
        print(f"{name}: {len(built):,} bytes built")
        sym = vst.symbols()
        if a.project:
            port(name, built, a.project, sym)
        else:
            print(f"  [SKIP] {name}: the port runs -- no project (OT_PROJECT=<dir> or --project)")
    print(f"verify_retstore: {fails} failure(s)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
