#!/usr/bin/env python3
"""Assemble modules/machinedrum/md_driver.asm for one capture's layout.

    python3 tools/harness/md_reference/md_driver.py <capture dir> [--reloc] [--org 0x2000]

Without --reloc the routine tables are at the MD's own addresses; with it,
at the places <capture dir>/reloc.txt moved them to (its M and T lines, the
last matching move winning, as md_replay applies them). Writes driver.bin (the
words, one per line, hex) and driver.sym (label address) into the capture
dir, the filled placeholders as driver.cfg, and prints the disassembly of what was assembled, since dsp_asm has
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
TABLES = (0x145AF5, 0x145BB6, 0x145C77)   # init, trigger, render

sys.path.insert(0, str(ROOT / "modules/machinedrum"))
from layout import LAYOUT


def main():
    args = sys.argv[1:]
    cap = Path(args.pop(0))
    reloc = "--reloc" in args
    org = int(args[args.index("--org") + 1], 0) if "--org" in args else LAYOUT["driver"]["code"]

    moves, vmap = [], {}
    if reloc:
        for l in (cap / "reloc.txt").read_text().splitlines():
            if l.startswith("M "):
                _, s, e, n = l.split()
                moves.append((int(s, 16), int(e, 16), int(n, 16)))
            elif l.startswith("T "):
                _, _space, s, e, n = l.split()
                moves.append((int(s, 16), int(e, 16), int(n, 16)))
            elif l.startswith("V "):
                _, o, n = l.split()
                vmap[int(o, 16)] = int(n, 16)

    def place(a):
        for s, e, n in reversed(moves):
            if s <= a < e:
                return n + a - s
        return a

    # The placeholders. Loop words from the V lines (md_relocate's layout
    # mapping) or at the proposed OT addresses. The driver's own storage in Y
    # is not part of the MD snapshot; the replay's poison runs showed the
    # selected scratch ranges are clean.
    driver = LAYOUT["driver"]
    voice_y = next(r for r in LAYOUT["allocations"] if r["name"] == "voice_y_records")
    vals = {
        "LV140": vmap.get(0x140, driver["LV140"]),
        "LV141": vmap.get(0x141, driver["LV141"]),
        "LV142": vmap.get(0x142, driver["LV142"]),
        "ENG": vmap.get(0x153, driver["ENG"]),
        "HALF": driver["HALF"],
        "TMP": driver["TMP"],
        "OUTBUF": driver["OUTBUF"],
        "STASH": driver["STASH"],
        "MDSAVE": driver["MDSAVE"],
        "PHASE": driver["PHASE"],
        "VOICE": voice_y["start"],
        "INIT": place(TABLES[0]), "TRIG": place(TABLES[1]), "RENDER": place(TABLES[2]),
        "EMPTY": place(0x10008F),
        # 1 when the driver carries the MD's whole low image across calls.
        "MDFULL": 1 if "move    #$0,r0\n        move    #>@MDSAVE@,r4" in SRC.read_text() else 0,
    }
    src = SRC.read_text()
    for k, v in vals.items():
        src = src.replace(f"@{k}@", f"${v:x}")
    left = re.findall(r"@[A-Z0-9]+@", src)
    if left:
        sys.exit(f"unfilled placeholders: {sorted(set(left))}")
    # dsp_asm resolves labels by prefix (CLAUDE.md): refuse any label that
    # is a prefix of another.
    labels = re.findall(r"^([A-Za-z_][A-Za-z0-9_]*):", src, re.M)
    clash = [(a, b) for a in labels for b in labels if a != b and b.startswith(a)]
    if clash:
        sys.exit(f"label is a prefix of another: {clash}")
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
    (cap / "driver.cfg").write_text("".join(f"{k} {v:06x}\n" for k, v in vals.items()))
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
