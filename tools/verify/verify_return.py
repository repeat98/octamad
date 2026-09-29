#!/usr/bin/env python3
"""verify_return -- RET B, the return channel on core 0 (MIXER.md section 19):
an effect chosen from the pool by the ColdFire's ret_model, run on the AUX B
bus, its wet added to MAIN and CUE at the next frame's head, and fed back into
the AUX buses (the self-send).

The port half (a project, the ColdFire port; OT_PROJECT=<dir>), the `returns`
remix (the strip beside the reverb server and SEND) on the user's project:

  rest     nothing poked: the two wet blocks and both head blocks are zero
  oxide    a DC on the four input channels; AUX B takes IN AB and IN CD; the
           return slot is OXIDE (id 0x1f, IN 48 / OUT 80) at level 100, CUE
           send 60, no self-send. In steady state, 0 LSB:
             WB    = OXIDE's fixed() of AUX B (the slot's model)
             M, Cc = WB at the level / CUE send, mpy's truncation (the head's blocks)
             CUE   = the TX0 CUE pair equals Cc (nothing else feeds it)
  reverb   the tones on the inputs; the slot is the reverb server (id 7) with its
           knobs up: taken, past its role lock, warming (it stays dry for 256 blocks);
           with --long (~350 frames) the wet is not silence and is bounded
  runaway  the same, with the self-send and the levels at their maximum for
           the whole run: the last frames are not pinned at full scale
  reta     RET A on core 1: the same OXIDE model on the AUX A core 0 published through the shared
           window, its wet back through it, 0 LSB at every hop, and into MAIN
  pool     an id off the return's list (0x22) leaves the slot dry: its wet is zero

What it cannot see: a track's audio; the cost on the unit; what the reverb
sounds like as a return (only that it runs and stays bounded).
"""
import argparse, os, pathlib, sys, tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
from remix import registry  # noqa: E402
import verify_dspsite as vds  # noqa: E402
import verify_strip as vst  # noqa: E402
import verify_aux as va  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "modules/oxide"))
import design  # noqa: E402

RETSLOT, RETREC = 0x7ce0, 0x7cf0
WB, WA, MADD, CADD = 0x7dc0, 0x7de0, 0x7e90, 0x7eb0
LEVELS = 0x7c98
FRAME = 30
LEVEL, CUE = 100, 60
fails = 0


def check(label, ok, detail=""):
    global fails
    print(f"  [{'ok' if ok else 'FAIL'}] {label}" + (f"  {detail}" if detail else ""))
    fails += 0 if ok else 1
    return ok


def slot_poke(base, ident, knobs):
    """ret_model bytes: id at +0, the twelve values at +4."""
    return [(base, ident)] + [(base + 4 + i, v) for i, v in enumerate(knobs)]


def steps(pokes):
    return ["--step", f"{FRAME}:poke:" + ";".join(f"{a:#x}={v}" for a, v in pokes)]


def run(name, built, project, frames, sym):
    import wave
    with tempfile.TemporaryDirectory(prefix="ret_") as work:
        work = pathlib.Path(work)
        (work / "built.bin").write_bytes(bytes(built))
        va.write_dc(work / "dc.wav")
        aux, ret, lvl = sym["aux_model"], sym["ret_model"], sym["retlvl_model"]
        # sends: AUX B (bytes 12..23): IN AB, IN CD; [22] RET A, [23] RET B (the self-send)
        b_in = [(aux + 16 + 4 + 8, 127), (aux + 16 + 4 + 9, 64)]
        oxide = b_in + slot_poke(ret, 0x1f, [48, 80, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]) \
            + [(lvl + 4, LEVEL), (lvl + 5, CUE)]
        verb = b_in + slot_poke(ret, 7, [0, 127, 64, 0, 64, 100, 0, 64, 64, 0, 0, 64]) \
            + [(lvl + 4, LEVEL), (lvl + 5, CUE)]
        runaway = [(aux + 16 + 4 + 8, 127), (aux + 16 + 4 + 9, 127), (aux + 16 + 4 + 11, 127)] \
            + slot_poke(ret, 7, [0, 127, 127, 0, 64, 127, 0, 127, 127, 0, 0, 127]) + [(lvl + 4, 127), (lvl + 5, 127)]
        offlist = b_in + slot_poke(ret, 0x22, [0] * 12) + [(lvl + 4, LEVEL), (lvl + 5, CUE)]
        peek = (f"0:X:{WB:x},32;0:X:{WA:x},32;0:X:{MADD:x},32;0:X:{CADD:x},32;0:X:{va.AUX_B:x},32;"
                f"0:X:{RETSLOT:x},2;0:X:{LEVELS:x},4;0:X:7f15,1;0:X:7ca0,32;"
                f"0:X:37000,2;0:X:37010,16;0:X:37020,128;0:X:370a0,128;"
                f"1:X:7ce0,2;1:X:7dc0,32;1:X:7de0,32;1:X:7f15,1")
        # RET A: AUX A (bytes 0..11) takes IN AB and IN CD; the slot is the second of ret_model
        a_in = [(aux + 4 + 8, 127), (aux + 4 + 9, 64)]
        reta = a_in + slot_poke(ret + 16, 0x1f, [48, 80, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]) \
            + [(lvl + 16 + 4, LEVEL), (lvl + 16 + 5, CUE)]
        variants = {"rest": ([], None), "oxide": (oxide, None), "reverb": (verb, "tones"),
                    "runaway": (runaway, "tones"), "pool": (offlist, None), "reta": (reta, None), "skew": (reta, None)}
        procs = {}
        for var, (pokes, audio) in variants.items():
            lazy = ["--dsp-lazy", "1700"] if var == "skew" else []
            procs[var] = va.launch(work, built, project, frames, var, (steps(pokes) if pokes else []) + lazy,
                                   SPAN[0], peek, audio_in=audio)
        codes = {v: p.wait() for v, p in procs.items()}
        if not all(check(f"port: {v} run finished", codes[v] == 0) for v in codes):
            return
        pk = {v: va.peeks((work / v / "run.txt").read_text()) for v in codes}
        import re
        pk1 = {v: {int(a, 16): [int(x, 16) for x in ws.split()]
                   for a, ws in re.findall(r"core 1 X:0x([0-9a-f]+): ((?:[0-9a-f]{6} ?)+)",
                                           (work / v / "run.txt").read_text())} for v in codes}
        z = [0] * 32
        r = pk["rest"]
        check("port: rest: both wet blocks and both head blocks are zero, the slot is dry",
              all(r.get(a) == z for a in (WB, WA, MADD, CADD)) and r.get(RETSLOT) == [0, 0], "")
        o = pk["oxide"]
        aux_b = [va.s24(w) for w in o[va.AUX_B]]
        wet = [va.s24(w) for w in o[WB]]
        # OXIDE's state carries: the slot's first call is the frame the record lands (AUX B
        # is already the DC then), so the wet is fixed() of N blocks of that DC for the N
        # calls since; N is the frame count the run had left, found by search
        found = None
        for n in range(60, frames + 1):
            w = []
            for ch in (0, 1):
                xs = [aux_b[2 * j + ch] for j in range(16)] * n
                w.append(design.fixed(xs, 48, 80)[-16:])
            w = [v for j in range(16) for v in (w[0][j], w[1][j])]
            if w == wet:
                found = n
                break
        check("port: oxide: RET B's wet is OXIDE's fixed() of AUX B (IN 48 / OUT 80) after N calls from its "
              "init, 0 LSB, all sixteen pairs", found is not None,
              f"N = {found}" if found else f"wet {wet[:4]}, no history length in 60..{frames} matches")
        lv = [va.s24(w) for w in o[LEVELS]]
        check("port: oxide: the levels are (v/128)^2 as Q23",
              lv[0] == va.gain(LEVEL) and lv[1] == va.gain(CUE), f"{[hex(x) for x in lv]}")
        mm = [va.s24(w) for w in o[MADD]]
        cc = [va.s24(w) for w in o[CADD]]
        check("port: oxide: MAIN's add is WB at the level (mpy's truncation), 0 LSB",
              mm == [(w * lv[0]) >> 23 for w in wet], f"{mm[:2]} vs {[(w * lv[0]) >> 23 for w in wet[:2]]}")
        check("port: oxide: CUE's add is WB at the CUE send, 0 LSB",
              cc == [(w * lv[1]) >> 23 for w in wet], f"{cc[:2]}")
        t = vst.tx0(work / "oxide" / "run_core0.wav")
        t0 = vst.tx0(work / "rest" / "run_core0.wav")
        tail = 160
        mean = lambda xs: sum(xs) / len(xs)
        dl = [mean(t[s][-tail:]) - mean(t0[s][-tail:]) for s in (0, 1)]
        check("port: oxide: the CUE pair of TX0 moves by the CUE add against the rest run (means over the last "
              "160 samples, within 15%: the wet is still settling, so this is not a 0-LSB check)",
              all(abs(d - c) <= 0.15 * abs(c) for d, c in zip(dl, cc[:2])), f"delta {[round(d) for d in dl]} add {cc[:2]}")
        v = pk["reverb"]
        slot = v.get(RETSLOT)
        count = v.get(0x7f15, [0])[0]
        check("port: reverb: id 7 is taken as a return (its proc is set) and the server runs past its role lock: "
              "its warm-up counter (r7+$15) advanced", bool(slot and slot[0] == 7 and slot[1]) and count > 0x20,
              f"slot {slot}, warm-up count {count}")
        if LONG:
            rw = [va.s24(w) for w in v[WB]]
            check("port: reverb (long): after the 256-block warm-up the wet block is not silence and is inside "
                  "full scale", any(rw) and max(abs(x) for x in rw) < (1 << 23) - 1, f"peak {max(abs(x) for x in rw)}")
        rt = vst.tx0(work / "runaway" / "run_core0.wav")
        pinned = [sum(1 for x in rt[s][-4000:] if abs(x) >= (1 << 23) - 2) for s in (0, 1, 2, 3)]
        check("port: runaway: the self-send and levels at their maximum for the run: the last 4,000 samples "
              "are not pinned at full scale on CUE or MAIN", max(pinned) < 2000, f"pinned counts {pinned}")
        for tag in ("reta", "skew"):
            ra = pk[tag]
            seq = ra.get(0x37000, [0, 0])
            slots_a = [[va.s24(w) for w in ra[0x37020][32 * k:32 * k + 32]] for k in range(4)]
            slots_w = [[va.s24(w) for w in ra[0x370a0][32 * k:32 * k + 32]] for k in range(4)]
            aux_a = [va.s24(w) for w in ra[0x7ca0]]
            check(f"port: {tag}: core 0 publishes AUX A into the exchange: the slot it last published is its AUX A block "
                  "(a constant input, so every frame is the same), seqA advancing", slots_a[seq[0] & 3] == aux_a and seq[0] > 20,
                  f"seqA {seq[0]}")
            c1 = pk1[tag].get(0x7ce0)
            check(f"port: {tag}: core 1 takes the id from the record core 0 forwarded and runs it (id 0x1f, proc set)",
                  bool(c1 and c1[0] == 0x1f and c1[1]), f"core 1 slot {c1}")
            wet1 = [va.s24(w) for w in pk1[tag][0x7dc0]]
            found = None
            for n in range(30, frames + 1):
                w = []
                for ch in (0, 1):
                    xs = [aux_a[2 * j + ch] for j in range(16)] * n
                    w.append(design.fixed(xs, 48, 80)[-16:])
                w = [v for j in range(16) for v in (w[0][j], w[1][j])]
                if w == wet1:
                    found = n
                    break
            check(f"port: {tag}: core 1's wet is OXIDE's fixed() of the AUX A it was handed, 0 LSB, all sixteen pairs",
                  found is not None, f"N = {found}" if found else f"wet {wet1[:4]}")
            check(f"port: {tag}: core 1 publishes its wet: seqW advancing and the last slot is that block",
                  seq[1] > 20 and slots_w[seq[1] & 3] == wet1, f"seqW {seq[1]}")
            wa = [va.s24(w) for w in ra[0x7de0]]
            check(f"port: {tag}: core 0's RET A block is one of the wet slots core 1 published (within four frames)",
                  wa in slots_w and any(wa), "")
            gam = [va.s24(w) for w in ra[LEVELS]]
            mm = [va.s24(w) for w in ra[MADD]]
            check(f"port: {tag}: MAIN's add is RET A's wet at RET A's level, 0 LSB (RET B is dry)",
                  mm == [(w * gam[2]) >> 23 for w in wa], f"{mm[:2]} vs {[(w * gam[2]) >> 23 for w in wa[:2]]}")
        pl = pk["pool"]
        check("port: pool: an id off the return's list (0x22) leaves the slot dry, wet zero",
              pl.get(RETSLOT) == [0x22, 0] and pl.get(WB) == z, f"slot {pl.get(RETSLOT)}")


SPAN = [(0, 0)]
LONG = False


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("remix", nargs="*")
    ap.add_argument("--project", default=os.environ.get("OT_PROJECT", ""))
    ap.add_argument("--frames", type=int, default=150)
    ap.add_argument("--long", action="store_true", help="run long enough for the reverb's 256-block warm-up (~350 frames) and check its wet")
    a = ap.parse_args()
    global LONG
    LONG = a.long
    if a.long:
        a.frames = max(a.frames, 350)
    if not vds.STOCK.exists():
        print("  [SKIP] verify_return: no stock image (make os)")
        return 0
    name = (a.remix or ["returns2"])[0]
    if "MASTER STRIP" not in registry.remix(name).modules:
        print(f"  [--] verify_return: {name} carries no MASTER STRIP")
        return 0
    built, report = vds.build(name)
    print(f"{name}: {len(built):,} bytes built")
    sym = vst.symbols()
    SPAN[0] = va.static(built)
    if a.project:
        run(name, built, a.project, a.frames, sym)
    else:
        print(f"  [SKIP] {name}: port half -- no project (OT_PROJECT=<dir> or --project)")
    print(f"verify_return: {fails} failure(s)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
