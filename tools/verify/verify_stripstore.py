#!/usr/bin/env python3
"""MASTER STRIP's Part storage: under the port, the strip's settings live in the Part.

    OT_PROJECT=<dir> python3 tools/verify/verify_stripstore.py [REMIX]

modules/strip/strip_xport.s keeps the two slots' effects and knobs in each
Part window, 32 bytes at bank + 0x904e2 (the audio LFO designer's shapes T7
and T8), each slot as modelled but for its spare bytes: the tag 0x53, the
checksum byte that makes the sixteen sum to 0 mod 256, the version 1. The
Part is the truth and strip_model its cache: strip_sync (the host-transfer
chain's ISR, once a frame) adopts the window of the part the panel edits
(0x100b14cf) when it has held one new value for two frames, and strip_store
(the MIXER page's three edits) writes the model back to the window, to the
part's SRAM twin and the stock editors' dirty marks. One load of the
project, then a panel script per case (`ot_emu --scenario --live-script`, the
`poke` line changing the window while the unit runs):

  fresh     nothing written, nothing edited: the model is the boot default (OXIDE
            IN 48 / OUT 80, slot 2 empty), the window is the project's own
            (zero); the edited words (0x9b332 in the bank, 0x100f8598) are 0.
            Part 0's dirty bit (0x95048, 0x100b145e) is already set by the load
            itself, so the marks below are read against this case's
  edit      MIXER, RIGHT, A +10: the window is the model's stored form, both
            slots valid, its twin the same bytes, the two edited words 1;
            part 1's window untouched
  choose    NONE onto INS 1 in its SETUP: the window holds it (id 0, valid)
  load      a valid record poked into the window while the unit runs: the model
            is that record, the window untouched (nothing is written back on a
            read), the model's spare bytes 0
  bad       the same record with one value changed and the checksum stale, then a
            random designer's shape: the boot default both times, the window
            untouched
  reload    a record poked in, then the window poked to zeros (a Part Reload
            to a blank Part): the model follows the record, then the default
  part1     part 1's window poked with a record and the panel's part set to 1:
            the model is that record, part 0's window untouched; an edit
            there lands in part 1's window and twin and sets bit 1 of the
            dirty bytes and the two edited words
  part4     the panel's part set to 4 (a kit window, not stock's): the model
            keeps to itself, an edit writes no window, no twin and no dirty
            mark, and the ISR's look is not left held off (strip_lock 0)
  dsp       with the DSP: a record poked in reaches core 0 as the slot's record
            (X:0x7c20, IN and OUT as v << 16) and slot 2 runs nothing (X:0x7c12)

What it cannot see: a Part Save or Reload through the panel (the port has no
card writes and did not reach the PART menu; the poke of the window is what
those stock routines do to it, memcpy of the whole Part), the bank file
(stock's own save copies the window), the Octakit's kit windows (part 4 is
the guard), or a real project's designer shapes (the fixture has none drawn).
"""
import argparse, contextlib, os, pathlib, re, shutil, subprocess, sys, tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
from remix import registry  # noqa: E402
import verify_dspsite as vds  # noqa: E402
import verify_strip as vst  # noqa: E402
import verify_mixerpages as vmp  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
KEY = "MASTER STRIP"
BLOB = 0x400e21e0                     # the bank's DB as the port loads bank 1
PSTRIDE, WOFF, TWOFF = 0x18b2, 0x904e2, 0x1762
SRAM_PART = 0x100a4ece
DIRTY_BANK, DIRTY_SRAM = 0x95048, 0x100b145e
EDITED_BANK, EDITED_SRAM = 0x9b332, 0x100f8598
PARTSEL = 0x100b14cf
TAG, VERSION = 0x53, 1
OXIDE, NONE = 0x1f, 0
BOOT = [OXIDE, 0, 0, 0, 48, 80] + [0] * 10 + [0] * 16       # strip_model's boot state

fails = 0


def check(label, ok, detail=""):
    global fails
    print(f"  [{'ok' if ok else 'FAIL'}] {label}" + (f"  {detail}" if detail else ""))
    fails += 0 if ok else 1
    return ok


def stored(ident, values):
    """A slot as the Part keeps it: id, tag, checksum, version, twelve values."""
    b = [ident, TAG, 0, VERSION] + list(values) + [0] * (12 - len(values))
    b[2] = -sum(b) & 0xff
    return b


def model(ident, values):
    """A slot as strip_model holds it: the spare bytes 0."""
    return [ident, 0, 0, 0] + list(values) + [0] * (12 - len(values))


R_A = stored(OXIDE, [20, 100]) + stored(NONE, [])
R_B = stored(NONE, []) + stored(OXIDE, [33, 44])
M_A = model(OXIDE, [20, 100]) + model(NONE, [])
M_B = model(NONE, []) + model(OXIDE, [33, 44])
BAD_SUM = list(R_A)
BAD_SUM[4] = 21                                   # a value changed, the checksum stale
SHAPE = [(i * 37 + 5) & 0x7f for i in range(32)]  # a designer's shapes: 0..127 steps
ZEROS = [0] * 32


def win(part):
    return BLOB + WOFF + part * PSTRIDE


def twin(part):
    return SRAM_PART + TWOFF + part * PSTRIDE


def poke(addr, data):
    return "poke " + ";".join(f"{addr + i:#x}={b:#x}" for i, b in enumerate(data))


def valid(slot):
    return (len(slot) == 16 and slot[1] == TAG and slot[3] == VERSION and sum(slot) & 0xff == 0)


# case: (steps, tail ms, --dsp)
CASES = {
    "fresh": (["wait 600"], 400),
    "edit": (["MIXER", "RIGHT", "enc 0 10"], 600),
    "choose": (["MIXER", "RIGHT", "YES", "UP", "YES", "NO"], 600),
    "load": ([poke(win(0), R_A), "wait 600"], 400),
    "bad": ([poke(win(0), BAD_SUM), "wait 300"], 300),
    "shape": ([poke(win(0), SHAPE), "wait 300"], 300),
    "reload": ([poke(win(0), R_A), "wait 400", poke(win(0), ZEROS), "wait 400"], 300),
    "part1": ([poke(win(1), R_B), poke(PARTSEL, [1]), "wait 600"], 400),
    "part1_edit": ([poke(win(1), R_B), poke(PARTSEL, [1]), "wait 400", "MIXER", "RIGHT", "DOWN", "enc 0 10"], 600),
    "part4": ([poke(win(0), R_A), poke(PARTSEL, [4]), "wait 400", "MIXER", "RIGHT", "enc 0 10"], 600),
}
DSP_CASES = {"dsp": [poke(win(0), R_A), "wait 600"]}


def dumps(work, c, sym):
    d = work / c
    spec = [f"{sym['strip_model']:#x},32={d}.model", f"{sym['strip_seen']:#x},32={d}.seen",
            f"{sym['strip_lock']:#x},1={d}.lock", f"{win(0):#x},32={d}.w0", f"{win(1):#x},32={d}.w1",
            f"{twin(0):#x},32={d}.t0", f"{twin(1):#x},32={d}.t1",
            f"{BLOB + DIRTY_BANK:#x},1={d}.d_bank", f"{DIRTY_SRAM:#x},1={d}.d_sram",
            f"{BLOB + EDITED_BANK:#x},4={d}.e_bank", f"{EDITED_SRAM:#x},4={d}.e_sram",
            f"{PARTSEL:#x},1={d}.sel"]
    return ";".join(spec)


def port(name, built, project, sym):
    import verify_set as vs
    import ot_project as otp
    if not vds.EMU.exists() or not vds.PY.exists():
        print("  [SKIP] port: the ColdFire port (make emu-cf) or the .venv is missing")
        return
    keep = os.environ.get("STRIPSTORE_KEEP")
    with (contextlib.nullcontext(keep) if keep else tempfile.TemporaryDirectory(prefix="stripstore_")) as work:
        work = pathlib.Path(work)
        work.mkdir(parents=True, exist_ok=True)
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
                 "--live-script", str(work / f"{c}.txt"), "--dsp-peek", "0:X:7c10,4;0:X:7c20,2;0:X:7c30,2",
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
            for k in ("model", "seen", "lock", "w0", "w1", "t0", "t1", "d_bank", "d_sram", "e_bank", "e_sram", "sel"):
                r[k] = list((work / f"{c}.{k}").read_bytes())
            R[c] = r
        checks(R)


def checks(R):
    def have(*cs):
        miss = [c for c in cs if c not in R]
        if miss:
            print(f"  [SKIP] needs {miss}")
        return not miss

    if have("fresh"):
        r = R["fresh"]
        check("fresh: the model is the boot default (OXIDE IN 48 / OUT 80, slot 2 empty)",
              r["model"] == BOOT, r["model"])
        check("fresh: nothing is written into either window or twin, the edited words are 0",
              r["w0"] == ZEROS and r["w1"] == ZEROS and r["t0"] == ZEROS and r["t1"] == ZEROS
              and r["e_bank"] == [0] * 4 and r["e_sram"] == [0] * 4 and r["lock"] == [0],
              f"w0 {r['w0'][:8]} e_bank {r['e_bank']} e_sram {r['e_sram']}")
        base = r
    else:
        base = None
    if base is None:
        return
    nomark = lambda r: (r["d_bank"] == base["d_bank"] and r["d_sram"] == base["d_sram"]
                        and r["e_bank"] == [0] * 4 and r["e_sram"] == [0] * 4)

    if have("edit"):
        r = R["edit"]
        m = r["model"]
        check("edit: A +10 moved slot 1's IN off 48 and left slot 2 empty",
              m[4] != 48 and m[16:] == [0] * 16, m[:16])
        want = stored(m[0], m[4:16]) + stored(m[16], m[20:32])
        check("edit: the window is the model's stored form, both slots valid",
              r["w0"] == want and valid(r["w0"][:16]) and valid(r["w0"][16:]), r["w0"])
        check("edit: its SRAM twin holds the same bytes, and the ISR's look has them (strip_seen)",
              r["t0"] == want and r["seen"] == want)
        check("edit: the bank's edited word and 0x100f8598 are 1, part 0's dirty bit still set",
              r["e_bank"] == [0, 0, 0, 1] and r["e_sram"] == [0, 0, 0, 1]
              and r["d_bank"][0] & 1 == 1 and r["d_sram"][0] & 1 == 1,
              f"{r['d_bank']} {r['d_sram']} {r['e_bank']} {r['e_sram']}")
        check("edit: part 1's window and twin untouched", r["w1"] == ZEROS and r["t1"] == ZEROS)
        check("edit: strip_lock is 0 (the ISR's look is not held off)", r["lock"] == [0])

    if have("choose"):
        r = R["choose"]
        check("choose: NONE onto INS 1: the model's slot 1 is id 0, and the window keeps it, valid",
              r["model"][0] == 0 and r["w0"][0] == 0 and valid(r["w0"][:16]) and valid(r["w0"][16:]),
              f"model {r['model'][:8]} window {r['w0'][:8]}")

    if have("load"):
        r = R["load"]
        check("load: a record poked into the window is the model, spare bytes 0", r["model"] == M_A, r["model"])
        check("load: the window is untouched (nothing is written back on a read)", r["w0"] == R_A)
        check("load: no dirty mark and no twin write from a read", nomark(r) and r["t0"] == ZEROS,
              f"{r['d_bank']} {r['e_bank']}")

    if have("bad"):
        r = R["bad"]
        check("bad: a stale checksum is refused: the boot default", r["model"] == BOOT, r["model"])
        check("bad: the window is left as it was", r["w0"] == BAD_SUM)
    if have("shape"):
        r = R["shape"]
        check("shape: a designer's steps are refused: the boot default", r["model"] == BOOT, r["model"])
        check("shape: the window is left as it was", r["w0"] == SHAPE)

    if have("reload"):
        r = R["reload"]
        check("reload: after the record, then zeros in the window, the model is the boot default again",
              r["model"] == BOOT and r["w0"] == ZEROS, r["model"])

    if have("part1"):
        r = R["part1"]
        check("part1: the panel's part 1 shows part 1's record", r["sel"] == [1] and r["model"] == M_B, r["model"])
        check("part1: part 0's window and part 1's are as poked", r["w0"] == ZEROS and r["w1"] == R_B)
    if have("part1_edit"):
        r = R["part1_edit"]
        m = r["model"]
        want = stored(m[0], m[4:16]) + stored(m[16], m[20:32])
        check("part1_edit: A +10 on INS 2 (OXIDE 33 / 44 there) moved its IN and the record follows it",
              m[16] == OXIDE and m[20] != 33 and m[:16] == model(NONE, []), m)
        check("part1_edit: the edit is in part 1's window and twin, part 0's are untouched",
              r["w1"] == want and r["t1"] == want and r["w0"] == ZEROS and r["t0"] == ZEROS)
        check("part1_edit: part 1's dirty bit (bit 1) is newly set in the bank and in SRAM, part 0's is as "
              "the load left it, the edited words are 1",
              r["d_bank"][0] == base["d_bank"][0] | 2 and r["d_sram"][0] == base["d_sram"][0] | 2
              and r["e_bank"] == [0, 0, 0, 1] and r["e_sram"] == [0, 0, 0, 1],
              f"{r['d_bank']} {r['d_sram']} (loaded {base['d_bank']} {base['d_sram']})")

    if have("part4", "edit"):
        r = R["part4"]
        check("part4: a part that is not stock's four keeps the model to itself: the edit reached "
              "the model (IN 20 + the stock step) and no window, twin or dirty mark",
              r["model"][4] == 20 + R["edit"]["model"][4] - 48 and r["w0"] == R_A
              and r["w1"] == ZEROS and r["t0"] == ZEROS and r["t1"] == ZEROS and nomark(r)
              and r["lock"] == [0],
              f"model {r['model'][:8]} d_bank {r['d_bank']} lock {r['lock']}")

    if have("dsp"):
        r = R["dsp"]
        pk = vmp.peek(r["log"])
        want_in, want_out = M_A[4] << 16, M_A[5] << 16
        check("dsp: a record poked into the window reaches core 0 as slot 1's record: IN and OUT as v << 16",
              pk.get(0x7c20) == [want_in, want_out], vmp.hexs(pk.get(0x7c20)))
        st = pk.get(0x7c10, [])
        check("dsp: slot 1 runs OXIDE and slot 2 nothing (X:0x7c10 id and proc, X:0x7c12 id and proc)",
              len(st) == 4 and st[0] == OXIDE and st[1] != 0 and st[2:4] == [0, 0], vmp.hexs(st))
        check("dsp: the model is the record", r["model"] == M_A, r["model"])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("remix", nargs="*")
    ap.add_argument("--project", default=os.environ.get("OT_PROJECT", ""))
    a = ap.parse_args()
    if not vds.STOCK.exists():
        print("  [SKIP] verify_stripstore: no stock image (make os)")
        return 0
    names = a.remix or [n for n in sorted(registry.remix_names()) if KEY in registry.remix(n).modules]
    names = [n for n in names if KEY in registry.remix(n).modules]
    if not names:
        print(f"  [--] verify_stripstore: no remix selected carries {KEY}")
        return 0
    for name in names:
        built, report = vds.build(name)
        print(f"{name}: {len(built):,} bytes built")
        sym = vst.symbols()
        if a.project:
            port(name, built, a.project, sym)
        else:
            print(f"  [SKIP] {name}: the port runs -- no project (OT_PROJECT=<dir> or --project)")
    print(f"verify_stripstore: {fails} failure(s)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
