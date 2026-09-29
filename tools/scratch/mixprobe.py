#!/usr/bin/env python3
"""MIXER.md step 1, as a throwaway probe: run the stock mixdown from a copy.

    mixprobe.py patch IN.bin OUT.bin [--new 0x1020]

Copies payload A's mixdown block P:0x238..0x2d4 (157 words) to P:NEW, fixes
the three operands that name an address (two DO loop ends, the exit BRA that
becomes a short JMP to P:0x2d5), and plants `jmp >NEW` over P:0x238 (a
2-word `move x:>$205,r0`, whose copy is the first instruction at NEW).
Nothing else in the image changes. The words are copied, never re-assembled
(`dsp_asm` mis-encodes some instructions silently; a copy of the author's own
words needs no assembler). Superseded by schema.DspSite and verify_dspsite.py.
"""
import argparse, pathlib, subprocess, sys, tempfile

sys.path.insert(0, str(pathlib.Path("tools/build").resolve()))
from dsp_modmap import BASE, PAYLOADS, modules, w24  # noqa: E402

SITE, END = 0x238, 0x2d5            # block is [SITE, END)
EXIT = 0x2d5
DIS = "vendor/dsp56300/build/source/disassemble/dsp56kDisassemble"


class Payload:
    def __init__(self, img, tag="A"):
        self.img = img
        for t, va, ln in PAYLOADS:
            if t == tag:
                self.va = va
        mods, blob = modules(bytes(img), *[(va, ln) for t, va, ln in PAYLOADS if t == tag][0])
        self.recs = [m for m in mods if m[0] == 0]

    def loc(self, addr):
        for sp, a, cnt, data in self.recs:
            if a <= addr < a + cnt:
                return self.va - BASE + data + (addr - a) * 3
        sys.exit(f"P:{addr:#x} is in no record")

    def rd(self, addr):
        i = self.loc(addr)
        return self.img[i] | self.img[i + 1] << 8 | self.img[i + 2] << 16

    def wr(self, addr, v):
        i = self.loc(addr)
        self.img[i], self.img[i + 1], self.img[i + 2] = v & 0xff, v >> 8 & 0xff, v >> 16 & 0xff


def disasm(words, pc):
    b = b"".join(w.to_bytes(3, "little") for w in words)
    with tempfile.TemporaryDirectory() as d:        # per process: never a fixed /tmp name
        p = pathlib.Path(d) / "words.bin"
        p.write_bytes(b)
        return subprocess.run([DIS, "-in", str(p), "-pc", f"{pc:x}", "-le"],
                              capture_output=True, text=True).stdout


def patch(args):
    img = bytearray(pathlib.Path(args.inp).read_bytes())
    pa = Payload(img)
    new = int(args.new, 0)
    n = END - SITE
    blk = [pa.rd(SITE + i) for i in range(n)]
    # the site must be what we think it is
    assert blk[0] == 0x60f000 and blk[1] == 0x000205, "P:0x238 is not `move x:>$205,r0`"
    d = new - SITE
    # the new home must lie in the harvested region beyond what the build placed
    # (hello: P:0x1000..0x101a used, region ends 0x1aa4 -- the build report's
    # ledger; the words there still hold the unreachable stock PLATE code)
    assert 0x101a <= new and new + n <= 0x1aa4, f"P:{new:#x}+{n} is outside the free part of the region"
    fixes = []
    for i, w in enumerate(blk):
        a = SITE + i
        if (w & 0xff00ff) == 0x060080 and i + 1 < n and blk[i + 1] < END:     # do #imm,>LA
            fixes.append((a + 1, blk[i + 1], blk[i + 1] + d, "do end"))
    # the exit: the last BRA of the plain path at 0x291 (`bra 0x2d5`)
    assert blk[0x291 - SITE] == 0x050c84, "P:0x291 is not the exit bra"
    fixes.append((0x291, 0x050c84, 0x0c0000 | EXIT, "exit bra -> jmp $2d5"))
    body = list(blk)
    for a, old, newv, why in fixes:
        body[a - SITE] = newv
        print(f"  fix P:{a:#05x} {old:#08x} -> {newv:#08x}  ({why})")
    assert len(fixes) == 3, fixes
    for i, w in enumerate(body):
        pa.wr(new + i, w)
    # the site
    pa.wr(SITE, 0x0af080)
    pa.wr(SITE + 1, new)
    pathlib.Path(args.out).write_bytes(img)
    print(f"mixdown P:{SITE:#x}..{END - 1:#x} ({n} words) copied to P:{new:#x}..{new + n - 1:#x}; "
          f"jmp >{new:#x} at P:{SITE:#x}")
    # show the result so the relocation is read, not trusted
    print(disasm([pa.rd(SITE), pa.rd(SITE + 1)], SITE).strip())
    print("--- the copy, stock vs relocated (address-normalised diff) ---")
    a = disasm(blk, SITE).splitlines()
    b = disasm([pa.rd(new + i) for i in range(n)], new).splitlines()
    import re
    norm = lambda s, base: re.sub(r"^[0-9a-f]{6}:", lambda m: f"{int(m.group(0)[:-1], 16) - base:04x}:", s)
    diffs = [(x, y) for x, y in zip((norm(s, SITE) for s in a), (norm(s, new) for s in b)) if x != y]
    for x, y in diffs:
        print(" stock:", x[:100]); print("   new:", y[:100])
    print(f"{len(diffs)} differing line(s)")


ap = argparse.ArgumentParser()
sub = ap.add_subparsers(dest="cmd", required=True)
p = sub.add_parser("patch"); p.add_argument("inp"); p.add_argument("out"); p.add_argument("--new", default="0x1020")
args = ap.parse_args()
{"patch": patch}[args.cmd](args)
