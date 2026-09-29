#!/usr/bin/env python3
"""MASTER STRIP's MIDI CC (MIXER.md section 21): under the port, a CC writes a mixer model
and the Part keeps it.

    OT_PROJECT=<dir> python3 tools/verify/verify_mixcc.py [REMIX]

modules/strip/strip_xport.s detours the stock CC handler's entry (0x4000e79c, where every
chain of CC handlers ends): CC 74..85 are AUX A's twelve sends, 86..95 AUX B's first ten,
102 and 103 AUX B's sends from RET A and RET B, 104..107 RET B's level and CUE send and
RET A's; the value is masked to 0..127, written into aux_model / retlvl_model and kept by
ret_store_cc (the window, the part's SRAM twin, the stock editors' marks; no refresh call).
Any channel, only while AUDIO CC IN is on. Every other CC, 96..101 and 108..111 included,
runs the stock handler's own code, its displaced prologue replayed.

  cc        ten CCs (one per group and the ends) at frames 20..29: the models hold exactly
            those values and nothing else, the window is their stored form, its twin the
            same, the edited words 1, the ISR's look not held off
  notmine   CC 96, 100, 108, 111: the models are the defaults, the window and twin zero,
            no dirty mark
  stock     the stock CC 40 and 7: the models and windows untouched (stock marks the Part
            itself)
  off       AUDIO CC IN poked to 0: CC 74 is ignored
  dsp       with the DSP: the CCs reach core 0 as the gains and the levels
What it cannot see: the stock handler's own effect for the CCs it takes (only that the
mixer does not swallow them: CC 7 and 40 are sent and the run continues), and a real
controller's channel.
"""
import argparse, os, pathlib, re, shutil, subprocess, sys, tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
from remix import registry  # noqa: E402
import verify_dspsite as vds  # noqa: E402
import verify_strip as vst  # noqa: E402
import verify_mixerpages as vmp  # noqa: E402
import verify_retstore as vrs  # noqa: E402
import verify_aux as va  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
KEY = "MASTER STRIP"
CCIN = 0x80000049
fails = 0

# (cc, value): AUX A T1 and RET B, AUX B T1 and IN CD, its RET A and RET B, then the levels
TAKEN = [(74, 33), (85, 44), (86, 55), (95, 66), (102, 77), (103, 88), (104, 90), (105, 11), (106, 22), (107, 33)]
NOTMINE = [(96, 50), (100, 60), (108, 70), (111, 80)]
STOCK = [(40, 90), (7, 100)]


def check(label, ok, detail=""):
    global fails
    print(f"  [{'ok' if ok else 'FAIL'}] {label}" + (f"  {detail}" if detail else ""))
    fails += 0 if ok else 1
    return ok


def midi(path, ccs, chan=0, start=20):
    path.write_text("\n".join(f"{start + i} B{chan:X} {cc:02X} {v:02X}" for i, (cc, v) in enumerate(ccs)) + "\n")


def expected():
    aux = [0] * 32
    lvl = vrs.BOOT[2][:]
    for cc, v in TAKEN:
        if cc <= 85:
            aux[4 + cc - 74] = v
        elif cc <= 95:
            aux[20 + cc - 86] = v
        elif cc <= 103:
            aux[20 + 10 + cc - 102] = v
        else:
            lvl[[4, 5, 20, 21][cc - 104]] = v
    return aux, lvl


def dumps(work, c, sym):
    return vrs.dumps(work, c, sym)


def port(name, built, project, sym):
    import verify_set as vs
    import ot_project as otp
    with tempfile.TemporaryDirectory(prefix="mixcc_") as work:
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
        midi(work / "cc.mid", TAKEN)
        midi(work / "notmine.mid", NOTMINE)
        midi(work / "off.mid", [(74, 50)])
        midi(work / "stock.mid", STOCK)
        args = []
        for c, extra in (("cc", ""), ("notmine", ""), ("stock", ""), ("off", f" --poke {CCIN:#x}=0")):
            args += ["--scenario", f"{work / c}.log --sequencer --internal-clock --frames 90 --midi {work / c}.mid"
                     f" --mem-dump {dumps(work, c, sym)}{extra}"]
        shutil.copy2(card, work / "card_built.img")
        runs = [subprocess.Popen(
            [str(vds.EMU), "--image", str(work / "built.bin"), "--card", str(work / "card_built.img"),
             "--set", "OCTABAM", "--project", "RIG", "--load-ms", "90000", "--scenario-jobs", "4"] + args,
            cwd=ROOT, stdout=open(work / "built.txt", "w"), stderr=subprocess.STDOUT)]
        shutil.copy2(card, work / "card_dsp.img")
        runs.append(subprocess.Popen(
            [str(vds.EMU), "--image", str(work / "built.bin"), "--card", str(work / "card_dsp.img"),
             "--set", "OCTABAM", "--project", "RIG", "--load-ms", "90000", "--dsp", "--sequencer",
             "--internal-clock", "--frames", "120", "--midi", str(work / "cc.mid"),
             "--dsp-peek", "0:X:7c80,24;0:X:7c98,4", "--mem-dump", dumps(work, "dsp", sym)],
            cwd=ROOT, stdout=open(work / "dsp.log", "w"), stderr=subprocess.STDOUT))
        codes = [p.wait() for p in runs]
        check("port: every load ran", all(c == 0 for c in codes), f"exit codes {codes}")
        R = {}
        for c in ("cc", "notmine", "stock", "off", "dsp"):
            log = (work / f"{c}.log").read_text() if (work / f"{c}.log").exists() else ""
            r = {"log": log}
            for k in ("ret", "aux", "lvl", "seen", "lock", "w0", "w1", "t0", "t1", "d_bank", "d_sram",
                      "e_bank", "e_sram", "sel"):
                r[k] = list((work / f"{c}.{k}").read_bytes())
            R[c] = r
        checks(R)


def checks(R):
    base_d = R["notmine"]
    aux_w, lvl_w = expected()
    r = R["cc"]
    check("cc: the ten CCs are in the models and nothing else is (AUX A's cell, AUX B's cell, the levels)",
          r["aux"] == aux_w and r["lvl"] == lvl_w and r["ret"] == [0] * 32, f"aux {r['aux'][:16]} {r['aux'][16:]} lvl {r['lvl'][:6]}")
    want = vrs.window((r["ret"][0], r["ret"][4:16]), (r["ret"][16], r["ret"][20:32]), r["aux"][4:16],
                      r["aux"][20:32], [r["lvl"][4], r["lvl"][5], r["lvl"][20], r["lvl"][21]])
    check("cc: the window is the models' stored form (all five cells valid), its SRAM twin and the ISR's look the same",
          r["w0"] == want and vrs.valid(r["w0"]) and r["t0"] == want and r["seen"] == want)
    check("cc: the edited words are 1, part 1 untouched, the ISR's look not held off",
          r["e_bank"] == [0, 0, 0, 1] and r["e_sram"] == [0, 0, 0, 1] and r["w1"] == [0] * 80
          and r["t1"] == [0] * 80 and r["lock"] == [0], f"{r['e_bank']} {r['e_sram']}")
    r = base_d
    check("notmine: CC 96, 100, 108, 111 (data entry, NRPN, and numbers no one takes) change no model, write no "
          "window, mark nothing",
          r["ret"] == [0] * 32 and r["aux"] == [0] * 32 and r["lvl"] == vrs.BOOT[2] and r["w0"] == [0] * 80
          and r["t0"] == [0] * 80 and r["e_bank"] == [0] * 4 and r["e_sram"] == [0] * 4, f"aux {r['aux'][:8]}")
    r = R["stock"]
    check("stock: the stock CC 40 and 7 (which the stock handler takes) leave the mixer's models and windows alone",
          r["ret"] == [0] * 32 and r["aux"] == [0] * 32 and r["lvl"] == vrs.BOOT[2] and r["w0"] == [0] * 80
          and r["t0"] == [0] * 80, f"aux {r['aux'][:8]} lvl {r['lvl'][:6]}")
    r = R["off"]
    check("off: with AUDIO CC IN off, CC 74 is ignored", r["aux"] == [0] * 32 and r["w0"] == [0] * 80, f"aux {r['aux'][:8]}")
    r = R["dsp"]
    pk = vmp.peek(r["log"])
    gains = pk.get(0x7c80, [])
    want = [va.gain(v) for v in aux_w[4:16]] + [va.gain(v) for v in aux_w[20:32]]
    want = [min(g, va.gain(100)) if i in (10, 11, 22, 23) else g for i, g in enumerate(want)]
    check("dsp: the CCs reach core 0 as the gains ((v/128)^2, the returns' terms capped) and the levels",
          gains == want and pk.get(0x7c98) == [va.gain(lvl_w[4]), va.gain(lvl_w[5]), va.gain(lvl_w[20]), va.gain(lvl_w[21])],
          f"{vmp.hexs(gains[:2])} {vmp.hexs(pk.get(0x7c98))}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("remix", nargs="*")
    ap.add_argument("--project", default=os.environ.get("OT_PROJECT", ""))
    a = ap.parse_args()
    if not vds.STOCK.exists():
        print("  [SKIP] verify_mixcc: no stock image (make os)")
        return 0
    names = [n for n in (a.remix or ["strip"]) if KEY in registry.remix(n).modules]
    if not names:
        print(f"  [--] verify_mixcc: no remix selected carries {KEY}")
        return 0
    for name in names:
        built, report = vds.build(name)
        print(f"{name}: {len(built):,} bytes built")
        sym = vst.symbols()
        if a.project:
            port(name, built, a.project, sym)
        else:
            print(f"  [SKIP] {name}: the port runs -- no project (OT_PROJECT=<dir> or --project)")
    print(f"verify_mixcc: {fails} failure(s)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
