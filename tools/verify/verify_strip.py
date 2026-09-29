#!/usr/bin/env python3
"""MASTER STRIP: under the port, MAIN is OXIDE's model of the stock MAIN.

    python3 tools/verify/verify_strip.py [REMIX]            # default: every remix carrying MASTER STRIP
    OT_PROJECT=<dir> python3 tools/verify/verify_strip.py   # + the port half

The strip is not an identity, so verify_dspsite's "byte-identical to the
image without the jump" is the wrong reference for it; this is its own gate.

Static, from the built image alone:

  id        the strip reaches its insert through the stock dispatch tables at
            a fixed id (boot.asm / head.asm / tail.asm read X:0x234 and
            X:0x254): OXIDE must be id 0x1f, and those two words must be
            OXIDE's init and proc
  record    the boot body writes the record the model below is run with

The port half (a project, the ColdFire port): the built image and the same
image with EVERY site's stock words put back (the bodies never run) on one
staged card, both input pairs at DIR 127 and the port's tones on them, so
MAIN is audible. Then, over every ESAI frame of core 0's TX0 and every
host-port block:

  other     every TX0 word but MAIN's pair (slots 2/3) and the phones pair
            (slots 4/5) is byte-identical: the strip touched nothing else, and
            nothing it clobbered changed what stock does next
  phones    the phones pair is stock's cue mix (P:0x33f..0x359: a gain on CUE
            plus a gain on MAIN, both ramped from Y:0x40, stored limited) of
            the processed MAIN: it differs from the reference only where MAIN
            does, and there by MAIN's own change at the reference's gain
            (within the truncation of the store) -- the phones' MAIN share
            hears the insert, as MIXER.md section 3 asks. Sample 0 of every
            frame included: the first version ran the whole pass before
            stock's tail and the output DMA took that sample two frames stale
  main      slots 2/3 of the built run are design.fixed() of the reference
            run's slots 2/3 at IN 48 / OUT 80, sample for sample, 0 LSB: the
            insert ran once per sample, in order, with its state carried
  pack      exactly one host-port block class differs, the recorder/USB pack
            (P:0x2df..: MAIN's 16 pairs then CUE's, two 16-bit words a
            sample): its CUE half is identical and its MAIN half, over every
            frame, is design.fixed() of the reference's, 0 LSB -- the
            recorder and USB audio hear the insert
  audible   the reference MAIN is not silence
  control   the same model at IN 49 does NOT match: the comparison can fail

What it cannot see: track audio (under the port no track reaches the mixdown
yet, docs/remixer/EMU.md, so MAIN carries the inputs only); the metronome
click (the fixture has it off; tail.asm puts it back on the processed MAIN
by a difference nothing here exercises); the MASTER TRACK path (verify_set
forces it off, MIXER.md section 6); and the unit's DMA timing: the port's
reproduced the stale phones sample, but a margin measured here is the
port's, not the chip's.
"""
import argparse, contextlib, os, pathlib, re, shutil, subprocess, sys, tempfile, wave

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
from remix import registry  # noqa: E402
from dsp_modmap import BASE, PAYLOADS, modules  # noqa: E402
import verify_dspsite as vds  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "modules/oxide"))
import design  # noqa: E402

KEY, INSERT, INSERT_ID = "MASTER STRIP", "OXIDE", 0x1f
INIT_TABLE, PROC_TABLE = 0x215, 0x235
RECORD = 0x7c80
IN_KNOB, OUT_KNOB = 48, 80            # boot.asm's record
MAIN = (2, 3)                         # TX0 slots: MAIN L/R (ring words 2/3)
PHONES = (4, 5)                       # the cue mix (P:0x33f..): g_cue CUE + g_main MAIN, per sample
PACK_WORDS = 128                      # a pack block: MAIN's 16 pairs, then CUE's, 4 words a pair
SAMPLE0_PATH = "0:238:35a"            # core 0, the mixdown's start to the cue mix's end

fails = 0


def check(label, ok, detail=""):
    global fails
    print(f"  [{'ok' if ok else 'FAIL'}] {label}" + (f"  {detail}" if detail else ""))
    fails += 0 if ok else 1
    return ok


def x_word(img, addr, tag="A"):
    """X word `addr` of a payload as the image uploads it (an X record)."""
    va, ln = next((v, l) for t, v, l in PAYLOADS if t == tag)
    mods, _ = modules(bytes(img), va, ln)
    for sp, a, cnt, off in mods:
        if sp == 1 and a <= addr < a + cnt:
            i = va - BASE + off + (addr - a) * 3
            return img[i] | img[i + 1] << 8 | img[i + 2] << 16
    return None


def static(name, built, report):
    ins = registry.by_key(INSERT)
    check(f"{name}: {INSERT} is id 0x{INSERT_ID:02x}, the id the strip's bodies read",
          ins.menu is not None and ins.menu.fx2_id == INSERT_ID,
          f"got 0x{ins.menu.fx2_id:02x}" if ins.menu else "no menu entry")
    m = re.search(rf"{INSERT}\s+P:0x([0-9a-f]+)\.\.0x([0-9a-f]+)", report.split("-- payload A --")[-1]
                  if "-- payload A --" in report else report)
    lo, hi = (int(m.group(1), 16), int(m.group(2), 16)) if m else (None, None)
    init, proc = x_word(built, INIT_TABLE + INSERT_ID), x_word(built, PROC_TABLE + INSERT_ID)
    check(f"{name}: X:0x{INIT_TABLE + INSERT_ID:03x} / X:0x{PROC_TABLE + INSERT_ID:03x} are "
          f"{INSERT}'s init and proc", lo is not None and init is not None and proc is not None
          and lo <= init < hi and lo <= proc < hi,
          f"init P:0x{init or 0:05x} proc P:0x{proc or 0:05x}, {INSERT} at "
          + (f"P:0x{lo:05x}..0x{hi:05x}" if lo is not None else "?"))
    bt = vds.Payload(built, "A")
    d = next(d for d in registry.by_key(KEY).dsp_sites if d.label == "boot")
    body = bt.span(bt.word(d.site + 1), bt.word(d.site + 1) + 16)
    want = [0x44f400, IN_KNOB << 16, 0x447000, RECORD, 0x44f400, OUT_KNOB << 16, 0x447000, RECORD + 1]
    check(f"{name}: the boot body writes IN {IN_KNOB} / OUT {OUT_KNOB} to X:0x{RECORD:04x}",
          any(body[i:i + len(want)] == want for i in range(len(body) - len(want) + 1)))


def s24(hi, lo):
    """One sample of the pack (func_00055a): the high word carries bits 23..8,
    the low word's top byte bits 7..0, as the host port hands them over."""
    return (hi - 65536 if hi & 0x8000 else hi) * 256 + (lo >> 8)


def pack_main(blocks):
    """(L, R) of the MAIN half of a pack class's blocks, frames in order."""
    left, right = [], []
    for _, w in blocks:
        for j in range(16):
            left.append(s24(w[4 * j], w[4 * j + 1]))
            right.append(s24(w[4 * j + 2], w[4 * j + 3]))
    return left, right


def tx0(path):
    """{slot: [signed 24-bit samples]} of an --audio-out capture."""
    w = wave.open(str(path))
    ch, n, data = w.getnchannels(), w.getnframes(), w.readframes(w.getnframes())
    out = {s: [] for s in range(ch)}
    for i in range(n):
        base = i * 3 * ch
        for s in range(ch):
            v = int.from_bytes(data[base + 3 * s:base + 3 * s + 3], "little")
            out[s].append(v - (1 << 24) if v & 0x800000 else v)
    return out


@contextlib.contextmanager
def _keep():
    """STRIP_KEEP=<dir>: keep the port run's files there (for a look after a failure)."""
    d = pathlib.Path(os.environ["STRIP_KEEP"]); d.mkdir(parents=True, exist_ok=True)
    yield str(d)


# The fixtures, each the user's project with these project.work keys set: the
# input pairs at DIR 127 carry the port's tones into MAIN; `click` adds the
# metronome on MAIN only (CUE stays silent, so the phones' gain is checkable)
# at a volume where tones plus click do not clip.
VARIANTS = (
    ("tones", {b"DIR_AB": b"127", b"DIR_CD": b"127"}),
    ("click", {b"DIR_AB": b"127", b"DIR_CD": b"127", b"METRONOME_ENABLED": b"1",
               b"METRONOME_MAIN_VOLUME": b"64", b"METRONOME_CUE_VOLUME": b"0"}),
)


def align(pack, ring):
    """The TX0 index of the pack stream's first sample: the offset near the
    capture's end where the two agree most (everywhere, with no click)."""
    n, m = len(ring), len(pack)
    best = max(range(max(0, n - m - 256), n - m + 1),
               key=lambda o: sum(1 for i in range(0, m, 7) if ring[o + i] == pack[i]))
    return best


def lim24(v):
    return max(-(1 << 23), min((1 << 23) - 1, v))


def port_half(name, built, project, frames):
    import verify_set as vs
    import ot_project as otp
    import blockdump
    if not vds.EMU.exists() or not vds.PY.exists():
        print("  [SKIP] port half: the ColdFire port (make emu-cf) or the .venv is missing")
        return
    stock = vds.STOCK.read_bytes()
    ref = bytearray(built)
    for d in registry.by_key(KEY).dsp_sites:
        sp, rp = vds.Payload(stock, "A"), vds.Payload(ref, "A")
        for a in range(d.site, d.site + d.words):
            i, j = rp.index(a), sp.index(a)
            ref[i:i + 3] = stock[j:j + 3]
    with (tempfile.TemporaryDirectory(prefix="strip_") if not os.environ.get("STRIP_KEEP") else _keep()) as work:
        work = pathlib.Path(work)
        (work / "built.bin").write_bytes(bytes(built))
        (work / "ref.bin").write_bytes(bytes(ref))
        runs = {}
        for var, keys in VARIANTS:
            vdir = work / var
            proj = vdir / "src"
            shutil.copytree(pathlib.Path(project).expanduser(), proj,
                            ignore=shutil.ignore_patterns("*.wav", "*.WAV", "*.ot"))
            pw = proj / "project.work"
            raw = pw.read_bytes()
            for key, val in keys.items():
                raw, n = re.subn(rb"\r\n" + key + rb"=\d+", b"\r\n" + key + b"=" + val, raw)
                if n != 1:
                    print(f"  [SKIP] port half: project.work has no {key.decode()} line")
                    return
            pw.write_bytes(raw)
            bank = int(re.search(rb"\r\nBANK=(\d+)\r\n", raw).group(1)) + 1
            pat_part, _ = otp.bank_info(proj, bank)
            part = vs.part_of(proj, bank, pat_part[0] + 1)
            card = vdir / "card.img"
            vs.stage(proj, part, "OCTABAM", "RIG", vdir / "tree", 64, bank, card)
            for tag in ("built", "ref"):
                shutil.copy2(card, vdir / f"card_{tag}.img")
                cmd = [str(vds.EMU), "--image", str(work / f"{tag}.bin"), "--card", str(vdir / f"card_{tag}.img"),
                       "--set", "OCTABAM", "--project", "RIG", "--sequencer", "--internal-clock",
                       "--frames", str(frames), "--load-ms", "20000", "--dsp", "--main-level", "64",
                       "--audio-in", "tones", "--poke-trig", "2", "--audio-out", str(vdir / tag),
                       "--block-dump", str(vdir / f"{tag}.dump"), "--dsp-stopwatch", SAMPLE0_PATH]
                runs[var, tag] = subprocess.Popen(cmd, cwd=ROOT, stdout=open(vdir / f"{tag}.txt", "w"),
                                                  stderr=subprocess.STDOUT)
        codes = {k: p.wait() for k, p in runs.items()}
        for var, _ in VARIANTS:
            print(f"  -- {var} --")
            if not all([check(f"port: {var}: {tag} image ran", codes[var, tag] == 0) for tag in ("built", "ref")]):
                continue
            port_checks(var, work / var, blockdump)


def port_checks(var, vdir, blockdump):
    b, r = tx0(vdir / "built_core0.wav"), tx0(vdir / "ref_core0.wav")
    n = len(r[0])
    check(f"port: {var}: both captures have the same length ({n:,} frames)", len(b[0]) == n and n > 0)
    others = [s for s in r if s not in MAIN + PHONES and b[s] != r[s]]
    check(f"port: {var}: every TX0 slot but MAIN and the phones byte-identical ({len(r) - 4} slots)",
          not others, f"slots {others} differ" if others else "")
    cue_silent = not any(r[0]) and not any(r[1])
    for s, m, side in zip(PHONES, MAIN, "LR"):
        stray = sum(1 for i in range(n) if b[s][i] != r[s][i] and b[m][i] == r[m][i])
        # With CUE silent (both runs: slots 0/1 are checked identical above) the
        # phones sample is trunc(g * MAIN); g is read off the reference where MAIN
        # is large enough to pin it, and must carry the processed MAIN too.
        far, tested = 0, 0
        for i in range(n if cue_silent else 0):
            rm, bm = r[m][i], b[m][i]
            if b[s][i] == r[s][i] or abs(rm) < 256:
                continue
            tested += 1
            if abs(b[s][i] - r[s][i] / rm * bm) > 2 + abs(bm) / abs(rm):
                far += 1
        check(f"port: {var}: phones {side} changes only where MAIN {side} does"
              + (", by MAIN's change at the reference's gain" if cue_silent else
                 " (CUE is not silent: the gain is not checked)"),
              stray == 0 and far == 0 and (tested > 0 or not cue_silent),
              f"{stray} changed where MAIN did not, {far} of {tested} off the gain")
    ca, cr = (blockdump.classes(blockdump.read(vdir / f"{t}.dump")) for t in ("built", "ref"))
    differ = sorted(k for k in set(ca) | set(cr) if k not in ca or k not in cr or ca[k] != cr[k])
    pack = differ[0] if len(differ) == 1 else None
    ok = (pack is not None and len(ca[pack]) == len(cr[pack]) > 0
          and all(len(w) == PACK_WORDS for _, w in ca[pack] + cr[pack])
          and [f for f, _ in ca[pack]] == list(range(ca[pack][0][0], ca[pack][0][0] + len(ca[pack]))))
    check(f"port: {var}: one host-port block class of {len(cr)} differs, {PACK_WORDS}-word blocks, every frame",
          ok, f"{len(differ)} differ: {differ[:3]}" if not ok else
          f"dir {pack[0]} ch {pack[1]} core {pack[2]} ram 0x{pack[3]:08x}, {len(ca[pack])} blocks")
    if not ok:
        return
    check(f"port: {var}: the pack's CUE half identical",
          all(list(wb[64:]) == list(wr[64:]) for (_, wb), (_, wr) in zip(ca[pack], cr[pack])))
    bp, rp = pack_main(ca[pack]), pack_main(cr[pack])
    for side, bs, rs in zip("LR", bp, rp):
        want = design.fixed(rs, IN_KNOB, OUT_KNOB)
        bad = [i for i in range(len(bs)) if bs[i] != want[i]]
        check(f"port: {var}: the pack's MAIN {side} (recorder, USB) = {INSERT}'s fixed() of the "
              f"reference's, 0 LSB", not bad and any(rs),
              f"{len(bad):,} of {len(bs):,} differ" if bad else
              f"{len(bs):,} samples, {sum(1 for x in rs if x):,} non-zero")
    for tag in ("ref", "built"):
        m = re.search(r"stopwatch: .*mean (\d+) min (\d+) max (\d+)", (vdir / f"{tag}.txt").read_text())
        if m:
            print(f"  [info] port: {var}: {tag}: mixdown start to cue mix end (P:0x238..0x35a, the path "
                  f"to sample 0's writes), instructions per frame mean {m.group(1)} max {m.group(3)}")
    audible = sum(1 for i in range(n) if r[MAIN[0]][i] or r[MAIN[1]][i])
    check(f"port: {var}: the reference MAIN is audible ({audible:,} non-zero frames)", audible > 1000)
    if var == "tones":
        # No click: MAIN out is the pack's MAIN, over the whole capture.
        for s, side in zip(MAIN, "LR"):
            want = design.fixed(r[s], IN_KNOB, OUT_KNOB)
            bad = [i for i in range(n) if b[s][i] != want[i]]
            check(f"port: {var}: MAIN {side} = {INSERT}'s fixed() of the stock MAIN at IN {IN_KNOB} / "
                  f"OUT {OUT_KNOB}, 0 LSB", not bad,
                  f"{len(bad):,} of {n:,} differ, first at frame {bad[0]}: got {b[s][bad[0]]} "
                  f"want {want[bad[0]]} (in {r[s][bad[0]]})" if bad else f"{n:,} samples")
            if s == MAIN[0]:
                other = design.fixed(r[s], IN_KNOB + 1, OUT_KNOB)
                check(f"port control: {var}: the same model at IN 49 does not match", other != b[s])
            changed = sum(1 for i in range(n) if b[s][i] != r[s][i])
            print(f"  [info] port: {var}: MAIN {side}: {changed:,} of {n:,} samples changed by the strip")
        return
    # The click: stock adds it to MAIN after the pack, so the reference's pack is
    # MAIN before the click and its TX0 MAIN after; the click is their difference.
    # MAIN out must be the insert's output plus that click, stored limited.
    for s, side, bs, rs in zip(MAIN, "LR", bp, rp):
        off = align(rs, r[s])
        m = len(rs)
        click = [r[s][off + i] - rs[i] for i in range(m)]
        heard = sum(1 for c in click if c)
        check(f"port: {var}: the click is on the reference MAIN {side} ({heard:,} of {m:,} samples)", heard > 16)
        proc = design.fixed(rs, IN_KNOB, OUT_KNOB)
        want = [lim24(proc[i] + click[i]) for i in range(m)]
        bad = [i for i in range(m) if b[s][off + i] != want[i]]
        check(f"port: {var}: MAIN {side} = {INSERT}'s fixed() of the pack's MAIN plus the click, 0 LSB",
              not bad, f"{len(bad):,} of {m:,} differ, first at {bad[0]}: got {b[s][off + bad[0]]} "
              f"want {want[bad[0]]} (click {click[bad[0]]})" if bad else f"{m:,} samples from TX0 {off:,}")
        if s == MAIN[0]:
            check(f"port control: {var}: the insert's output without the click does not match",
                  any(b[s][off + i] != lim24(proc[i]) for i in range(m)))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("remix", nargs="*")
    ap.add_argument("--project", default=os.environ.get("OT_PROJECT", ""))
    ap.add_argument("--frames", type=int, default=300)
    a = ap.parse_args()
    if not vds.STOCK.exists():
        print("  [SKIP] verify_strip: no stock image (make os)")
        return 0
    names = a.remix or [n for n in sorted(registry.remix_names()) if KEY in registry.remix(n).modules]
    names = [n for n in names if KEY in registry.remix(n).modules]
    if not names:
        print(f"  [--] verify_strip: no remix selected carries {KEY}")
        return 0
    for name in names:
        built, report = vds.build(name)
        print(f"{name}: {len(built):,} bytes built")
        static(name, built, report)
        if a.project:
            port_half(name, built, a.project, a.frames)
        else:
            print(f"  [SKIP] {name}: port half -- no project (OT_PROJECT=<dir> or --project)")
    print(f"verify_strip: {fails} failure(s)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
