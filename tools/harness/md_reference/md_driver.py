#!/usr/bin/env python3
"""Assemble modules/machinedrum/md_driver.asm for one capture's layout.

    python3 tools/harness/md_reference/md_driver.py <capture dir> [--reloc] [--org 0x2000]

Without --reloc the routine tables are at the MD's own addresses; with it,
at the places <capture dir>/reloc.txt moved them to (its M lines, the last
matching move winning, as md_replay applies them). Writes driver.bin (the
words, one per line, hex) and driver.sym (label address) into the capture
dir, and prints the disassembly of what was assembled, since dsp_asm has
mis-encoded forms before (CLAUDE.md).
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ASM = ROOT / "vendor/dsp56300/build/source/dsp_host/dsp_asm"
DIS = ROOT / "out/md_reference/md_dis"
SRC = ROOT / "modules/machinedrum/md_driver.asm"
TABLES = (0x145AF5, 0x145BB6, 0x145C77)


def main():
    args = sys.argv[1:]
    cap = Path(args.pop(0))
    reloc = "--reloc" in args
    org = int(args[args.index("--org") + 1], 0) if "--org" in args else 0x2000

    moves, vmap = [], {}
    if reloc:
        for l in (cap / "reloc.txt").read_text().splitlines():
            if l.startswith("M "):
                _, s, e, n = l.split()
                moves.append((int(s, 16), int(e, 16), int(n, 16)))
            elif l.startswith("V "):
                _, o, n = l.split()
                vmap[int(o, 16)] = int(n, 16)

    def place(a):
        for s, e, n in reversed(moves):
            if s <= a < e:
                return n + a - s
        return a

    src = SRC.read_text()
    for t in TABLES:
        src = src.replace(f"${t:x}", f"${place(t):x}")
    # The loop words (V lines, md_relocate --loopvars).
    for o in (0x140, 0x141, 0x142):
        if o in vmap:
            src = src.replace(f"y:>${o:x}", f"y:>${vmap[o]:x}")
    if 0x153 in vmap:
        src = src.replace("(r1+$153)", f"(r1+${vmap[0x153]:x})")
    tmp = Path(tempfile.mkdtemp())
    (tmp / "d.asm").write_text(src)
    r = subprocess.run([str(ASM), "-in", str(tmp / "d.asm"), "-org", f"{org:x}", "-out", str(tmp / "d.bin"),
                        "-sym", str(tmp / "d.sym")], capture_output=True, text=True)
    if r.returncode or not (tmp / "d.bin").exists():
        sys.exit(r.stdout + r.stderr)
    blob = (tmp / "d.bin").read_bytes()
    words = [blob[i] | blob[i + 1] << 8 | blob[i + 2] << 16 for i in range(0, len(blob), 3)]
    (cap / "driver.bin").write_text("".join(f"{w:06x}\n" for w in words))
    syms = {}
    for l in (tmp / "d.sym").read_text().splitlines():
        if l.strip():
            k, v = l.split()
            syms[k] = int(v, 16)
    (cap / "driver.sym").write_text("".join(f"{k} {v:06x}\n" for k, v in sorted(syms.items(), key=lambda kv: kv[1])))
    print(f"{len(words)} words at {org:04x}; " + ", ".join(f"{k} {v:04x}" for k, v in sorted(syms.items(), key=lambda kv: kv[1])))

    # Disassemble what was assembled.
    snap = tmp / "snap.bin"
    p = [0] * 0x150000
    for i, w in enumerate(words):
        p[org + i] = w
    import array
    snap.write_bytes(array.array("I", p).tobytes())
    out = subprocess.run([str(DIS), str(snap), f"{org:x}-{org + len(words):x}"], capture_output=True, text=True).stdout
    a = org
    lines = {int(l.split()[0], 16): l for l in out.splitlines()}
    bad = []
    while a < org + len(words):
        l = lines[a].split(None, 4)
        print(f"  {a:04x}  {l[2]} {l[3] if l[1] == '2' else '      '}  {l[4]}")
        # The driver never uses max: a max is a mis-encoded cmp (CLAUDE.md).
        if l[4].split()[0] in ("max", "maxm", "dc", "illegal"):
            bad.append(f"{a:04x} {l[4]}")
        a += max(int(l[1]), 1)
    if bad:
        sys.exit("mis-encoded: " + "; ".join(bad))


if __name__ == "__main__":
    main()
