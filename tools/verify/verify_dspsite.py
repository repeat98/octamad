#!/usr/bin/env python3
"""DSP sites (schema.DspSite): the splice does what it declares and nothing else.

    python3 tools/verify/verify_dspsite.py [REMIX ...]      # default: every remix that carries a site
    OT_PROJECT=<dir> python3 tools/verify/verify_dspsite.py  # + the port half

For each remix that carries a DSP site the remix is built and, independently
of the build's own arithmetic, from the image alone:

  planted     the words at the site are the long jump the site declares, to an
              entry inside the harvested region; the words after it are nops
  only        every P word of the payload that differs from the stock image lies
              at a site or inside the region -- the splice touched nothing else
  copy        a copy body is the stock span with EXACTLY the declared fixes, each
              one recomputed here (loop end + distance moved; `bra` -> `jmp`)
  replay      an `identity` asm body begins with the displaced stock words
  disassembly the copy's instruction stream (the vendored disassembler) equals
              the stock span's line for line, branch targets compared relative
              to each span's own start; only a declared `bra`->`jmp` exit may differ

and, with a project (OT_PROJECT / --project) and the ColdFire port
(`make emu-cf`), for a remix whose sites are all identities (a COPY body, or an
asm body declared `identity`): the built image and the same image with the jumps removed run
one card under the port, and core 0's TX0 (every ESAI frame) and every
host-port block must be byte-identical, with MAIN and CUE audible so the
comparison is not of silence. The fixture is a scratch copy of the project
with DIR AB/CD at 127, so the port's input tones reach the mixdown; the
project on disk is not touched. An asm body that does work is a
behaviour change on purpose and has its own module's gate.

What this cannot see: track audio through the copy when the project plays no
samples (the code is the same words, so only an address operand could
differ, and those are what the checks above pin), and anything on the unit.
"""
import argparse, hashlib, os, pathlib, re, shutil, subprocess, sys, tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path)
from remix import registry  # noqa: E402
from dsp_modmap import BASE, PAYLOADS, modules  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
PY = ROOT / ".venv/bin/python3"
EMU = ROOT / "out/emu/ot_emu"
DIS = ROOT / "vendor/dsp56300/build/source/disassemble/dsp56kDisassemble"
STOCK = ROOT / "out/raw/section_3_MAIN_OS.bin"
JUMPS = {"jmp": 0x0af080, "jsr": 0x0bf080}

fails = 0


def check(label, ok, detail=""):
    global fails
    print(f"  [{'ok' if ok else 'FAIL'}] {label}" + (f"  {detail}" if detail else ""))
    fails += 0 if ok else 1


class Payload:
    """P-space words of one payload of an image, by DSP address."""

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

    def span(self, lo, hi):
        return [self.word(a) for a in range(lo, hi)]

    def all_words(self):
        return {a: self.word(a) for _sp, base, cnt, _off in self.recs for a in range(base, base + cnt)}


def disasm(words, pc):
    with tempfile.TemporaryDirectory() as d:        # per process: never a fixed /tmp name
        p = pathlib.Path(d) / "w.bin"
        p.write_bytes(b"".join(w.to_bytes(3, "little") for w in words))
        r = subprocess.run([str(DIS), "-in", str(p), "-pc", f"{pc:x}", "-le"],
                           capture_output=True, text=True)
    return [l for l in r.stdout.splitlines() if re.match(r"^[0-9a-f]{6}:|^func_[0-9a-f]{6}:", l)]


def normalised(lines, base):
    """Instruction text with every address made relative to `base`, the raw
    words dropped: two copies of one code stream compare equal."""
    out = []
    for l in lines:
        m = re.match(r"^([0-9a-f]{6}):\s*(.*?)\s*(?:;.*)?$", l)
        if not m:
            continue                                   # a label line: its address is the next line's
        addr, text = int(m.group(1), 16), m.group(2)
        text = re.sub(r"func_([0-9a-f]{6})", lambda g: f"@{int(g.group(1), 16) - base:+d}", text)
        text = re.sub(r">\$([0-9a-f]+)", lambda g: f">@{int(g.group(1), 16) - base:+d}"
                      if text.startswith("do ") else g.group(0), text)
        out.append((addr - base, text, m.group(2)))      # relative text, and the raw text
    return out


def build(name):
    env = dict(os.environ, REMIX=name, XBUS="1", SPEC="1"); env.setdefault("BUILD", "0")
    r = subprocess.run([sys.executable, str(ROOT / "tools/build/build_bus.py")], env=env,
                       capture_output=True, text=True, cwd=ROOT)
    if r.returncode:
        sys.exit(f"verify_dspsite: building {name} failed:\n{(r.stdout + r.stderr)[-1500:]}")
    return (ROOT / "out/mainos_bus.bin").read_bytes(), r.stdout


def region_of(report, tag):
    """(lo, hi) of the harvested region a payload's report block names."""
    block = report.split(f"-- payload {tag} --")[1].split("-- payload")[0]
    runs = [(int(a, 16), int(b, 16)) for a, b in re.findall(r"region P:0x([0-9a-f]+)\.\.0x([0-9a-f]+)", block)]
    runs += [(int(a, 16), int(b, 16)) for a, b in re.findall(r"run \d+ P:0x([0-9a-f]+)\.\.0x([0-9a-f]+)", block)]
    return runs


def structural(name, stock_img, built=None, report=None):
    rmx = registry.remix(name)
    mods = [registry.by_key(k) for k in rmx.modules if registry.by_key(k).dsp_sites]
    if built is None:
        built, report = build(name)
        print(f"{name}: {len(built):,} bytes built")
    for tag in sorted({p for m in mods for d in m.dsp_sites for p in d.payloads}):
        st, bt = Payload(stock_img, tag), Payload(built, tag)
        runs = region_of(report, tag)
        in_region = lambda a: any(lo <= a < hi for lo, hi in runs)
        site_words = set()
        for m in mods:
            for d in m.dsp_sites:
                if tag not in d.payloads:
                    continue
                who = f"{tag}/{m.key}/{d.label}"
                w = bt.span(d.site, d.site + d.words)
                site_words |= set(range(d.site, d.site + d.words))
                entry = w[1]
                check(f"{who}: planted {d.kind} P:0x{d.site:05x}+{d.words}",
                      w[0] == JUMPS[d.kind] and all(x == 0 for x in w[2:]) and in_region(entry),
                      f"-> P:0x{entry:05x}")
                if d.copy is None:
                    if d.identity:
                        st_w = st.span(d.site, d.site + d.words)
                        check(f"{who}: the identity body replays the {d.words} displaced word(s)",
                              bt.span(entry, entry + d.words) == st_w)
                    continue
                lo, hi = d.copy
                stock_span, body = st.span(lo, hi), bt.span(entry, entry + (hi - lo))
                want = list(stock_span)
                for f in d.fixes:
                    i = f.addr - lo
                    want[i] = (stock_span[i] + (entry - lo)) if f.kind == "loop_end" else (0x0c0000 | f.target)
                check(f"{who}: copy of P:0x{lo:05x}..0x{hi:05x} = stock + {len(d.fixes)} fix(es)",
                      body == want,
                      "" if body == want else
                      f"differs at {[hex(lo + i) for i, (a, b) in enumerate(zip(body, want)) if a != b][:6]}")
                # the instruction streams, relative to each span's own start
                a = normalised(disasm(stock_span, lo), lo)
                b = normalised(disasm(body, entry), entry)
                declared = {f.addr - lo for f in d.fixes if f.kind == "bra_to_jmp"}
                target = {f.addr - lo: f.target for f in d.fixes if f.kind == "bra_to_jmp"}
                diff = [(x, y) for x, y in zip(a, b) if x[:2] != y[:2]]
                ok = len(a) == len(b) and all(
                    x[0] in declared and x[1].startswith("bra") and y[1].startswith("jmp")
                    and y[2].endswith(f"func_{target[x[0]]:06x}")       # ... to the declared place
                    for x, y in diff) and {x[0] for x, _ in diff} == declared
                check(f"{who}: the copy's instruction stream is stock's ({len(a)} instructions)"
                      f", differing only at the {len(declared)} declared exit(s)", ok,
                      "" if ok else f"{[(x[:2], y[:2]) for x, y in diff][:3]}")
        sw, bw = st.all_words(), bt.all_words()
        extra = sorted(a for a in bw if a in sw and sw[a] != bw[a] and a not in site_words and not in_region(a))
        check(f"{tag}: no other stock P word changed outside the site and the region", not extra,
              f"{[hex(a) for a in extra[:8]]}" if extra else "")
    return built, mods


def selftest(name, stock_img):
    """The gate must FAIL on a splice that is wrong. Corrupt a built image four
    ways -- a body word, an unrelated stock word, a loop end, the exit's
    target -- and require each to be caught (the checks silent, only counted)."""
    global fails
    import contextlib, io
    built, report = build(name)
    mods = [registry.by_key(k) for k in registry.remix(name).modules if registry.by_key(k).dsp_sites]
    d = next(d for m in mods for d in m.dsp_sites if d.copy is not None and "A" in d.payloads)
    bt = Payload(built, "A")
    entry = bt.word(d.site + 1)
    lo, hi = d.copy
    fix_end = next(f for f in d.fixes if f.kind == "loop_end")
    fix_exit = next(f for f in d.fixes if f.kind == "bra_to_jmp")
    non_fix = next(a for a in range(lo + 8, hi) if a not in {f.addr for f in d.fixes})
    unrelated = next(a for a in sorted(Payload(stock_img, "A").all_words()) if 0x100 <= a < 0x180)
    ident = next((d2 for m in mods for d2 in m.dsp_sites if d2.identity and "A" in d2.payloads), None)
    cases = [("a word inside the copied body", entry + (non_fix - lo)),
             ("an unrelated stock word", unrelated),
             ("a loop end that no longer follows the copy", entry + (fix_end.addr - lo)),
             ("the exit's jump target", entry + (fix_exit.addr - lo))]
    if ident is not None:
        cases.append(("the displaced instruction an identity body replays", bt.word(ident.site + 1)))
    caught = 0
    for what, addr in cases:
        img = bytearray(built)
        i = Payload(img, "A").index(addr)
        img[i] ^= 0x01
        before = fails
        with contextlib.redirect_stdout(io.StringIO()):
            structural(name, stock_img, bytes(img), report)
        got, fails = fails - before, before
        print(f"  [{'ok' if got else 'FAIL'}] selftest: a flipped bit in {what} (P:0x{addr:05x}) is "
              + (f"caught by {got} check(s)" if got else "NOT caught"))
        caught += bool(got)
    if caught != len(cases):
        fails += 1


# ---- the port half --------------------------------------------------------------
def port_half(name, built, mods, project, frames, control=False):
    import verify_set as vs
    import blockdump
    if not EMU.exists() or not PY.exists():
        print("  [SKIP] port half: the ColdFire port (make emu-cf) or the .venv is missing")
        return
    if any(d.copy is None and not d.identity for m in mods for d in m.dsp_sites):
        print(f"  [SKIP] port half for {name}: an asm body that does work changes behaviour "
              f"on purpose; its module's gate holds it")
        return
    pdir = pathlib.Path(project).expanduser()
    with tempfile.TemporaryDirectory(prefix="dspsite_") as work:
        work = pathlib.Path(work)
        proj = work / "src"
        shutil.copytree(pdir, proj, ignore=shutil.ignore_patterns("*.wav", "*.WAV", "*.ot"))
        pw = proj / "project.work"
        raw = pw.read_bytes()
        for key in (b"DIR_AB", b"DIR_CD"):
            raw, n = re.subn(key + rb"=\d+", key + b"=127", raw)
            if n != 1:
                print(f"  [SKIP] port half: project.work has no {key.decode()} line")
                return
        pw.write_bytes(raw)
        # the reference: the same image with every site's stock words back
        stock = STOCK.read_bytes()
        ref = bytearray(built)
        for m in mods:
            for d in m.dsp_sites:
                for tag in d.payloads:
                    sp, rp = Payload(stock, tag), Payload(ref, tag)
                    for a in range(d.site, d.site + d.words):
                        i, j = rp.index(a), sp.index(a)
                        ref[i:i + 3] = stock[j:j + 3]
        bank = int(re.search(rb"\r\nBANK=(\d+)\r\n", raw).group(1)) + 1
        import ot_project as otp
        pat_part, _ = otp.bank_info(proj, bank)
        part = vs.part_of(proj, bank, pat_part[0] + 1)
        card = work / "card.img"
        vs.stage(proj, part, "OCTABAM", "RIG", work / "tree", 64, bank, card)
        images = [("built", bytes(built)), ("ref", bytes(ref))]
        if control:
            # the comparison must be able to fail: the built image with one
            # instruction word inside the first copied body changed. It has to
            # be a word the FIXTURE exercises: the tracks are silent, so a `mac`
            # of a track slot (P:0x266, measured 29 Sep 2026) changed nothing and
            # the first version of this control failed on it. P:0x26e is the
            # input pair's term of the plain path; bit 4 turns `mac y0,x0,a` into
            # `mac x0,y1,a`, the wrong coefficient on audible samples.
            d0 = next(d for m in mods for d in m.dsp_sites
                      if d.copy is not None and d.copy[0] <= 0x26e < d.copy[1])
            bad = bytearray(built)
            bp = Payload(bad, sorted(d0.payloads)[0])
            i = bp.index(bp.word(d0.site + 1) + (0x26e - d0.copy[0]))
            assert bp.word(bp.word(d0.site + 1) + (0x26e - d0.copy[0])) == 0x44dad2, "P:0x26e moved"
            bad[i] ^= 0x10
            images.append(("bad", bytes(bad)))
        runs = {}
        for tag, img in images:
            (work / f"{tag}.bin").write_bytes(img)
            shutil.copy2(card, work / f"card_{tag}.img")
            cmd = [str(EMU), "--image", str(work / f"{tag}.bin"), "--card", str(work / f"card_{tag}.img"),
                   "--set", "OCTABAM", "--project", "RIG", "--sequencer", "--internal-clock",
                   "--frames", str(frames), "--load-ms", "20000", "--dsp", "--main-level", "64",
                   "--audio-in", "tones", "--poke-trig", "2",
                   "--block-dump", str(work / f"{tag}.dump"), "--audio-out", str(work / tag),
                   "--dsp-stopwatch", "0:238:2d5"]
            runs[tag] = (subprocess.Popen(cmd, cwd=ROOT, stdout=open(work / f"{tag}.txt", "w"),
                                          stderr=subprocess.STDOUT), work / f"{tag}.txt")
        for tag, (proc, _) in runs.items():
            ok = proc.wait() == 0
            if tag != "bad":
                check(f"port: {tag} image ran", ok)
        wa, wb = (work / "built_core0.wav").read_bytes(), (work / "ref_core0.wav").read_bytes()
        check(f"port: core 0's TX0 (every ESAI frame) byte-identical, {len(wa):,} bytes", wa == wb and len(wa) > 44)
        # not silence: MAIN L/R (slots 2 and 3) carry the tones
        import wave, array
        w = wave.open(str(work / "built_core0.wav"))
        ch, n = w.getnchannels(), w.getnframes()
        data = w.readframes(n)
        nz = sum(1 for i in range(0, n) if any(data[i * 3 * ch + 3 * s:i * 3 * ch + 3 * s + 3] != b"\0\0\0" for s in (2, 3)))
        check(f"port: MAIN was audible ({nz:,} non-zero frames), so the comparison is not of silence", nz > 1000)
        ca, cb = blockdump.classes(blockdump.read(work / "built.dump")), blockdump.classes(blockdump.read(work / "ref.dump"))
        bad = [k for k in set(ca) | set(cb)
               if k not in ca or k not in cb or dict(ca[k]) != dict(cb[k])]
        check(f"port: every host-port block class identical ({len(ca)} classes)", not bad, f"{bad[:3]}" if bad else "")
        if control:
            wbad = (work / "bad_core0.wav").read_bytes() if (work / "bad_core0.wav").exists() else b""
            check("port control: a copy with one corrupted instruction makes core 0's TX0 differ",
                  wbad != wb)
        for tag, (_, txt) in runs.items():
            m = re.search(r"stopwatch: .*mean (\d+) min (\d+) max (\d+)", txt.read_text())
            if m:
                print(f"  [info] port: {tag}: the mixdown P:0x238..0x2d5, instructions per 16-sample frame "
                      f"mean {m.group(1)} min {m.group(2)} max {m.group(3)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("remix", nargs="*")
    ap.add_argument("--project", default=os.environ.get("OT_PROJECT", ""))
    ap.add_argument("--frames", type=int, default=300)
    ap.add_argument("--selftest", action="store_true",
                    help="also corrupt a built image four ways and require the gate to fail each")
    a = ap.parse_args()
    if not STOCK.exists():
        print("  [SKIP] verify_dspsite: no stock image (make os)")
        return 0
    names = a.remix or [n for n in sorted(registry.remix_names())
                        if any(registry.by_key(k).dsp_sites for k in registry.remix(n).modules)]
    if not names:
        print("  [SKIP] verify_dspsite: no remix carries a DSP site")
        return 0
    stock_img = STOCK.read_bytes()
    for name in names:
        built, mods = structural(name, stock_img)
        if a.selftest:
            selftest(name, stock_img)
        if a.project:
            port_half(name, built, mods, a.project, a.frames, control=a.selftest)
        else:
            print(f"  [SKIP] {name}: port half -- no project (OT_PROJECT=<dir> or --project)")
    print(f"verify_dspsite: {fails} failure(s)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
