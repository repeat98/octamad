#!/usr/bin/env python3
"""Inventory the absolute addresses the executed voice-DSP code references:
the relocation job for running MD engines at OT addresses.

    python3 tools/harness/md_reference/md_addrs.py out/md_profile/cat out/md_profile/load

Executed code is every instruction in a block any profile ran (walked as in
md_analyze). Each operand holding an address is classified:
  target    jmp/jsr/bra/do-loop end (P)
  abs       x:/y:/p: absolute operand
  disp      register + absolute displacement (a table base)
  imm       immediate of 0x100 or more (#$..., often a base for rN)
"""
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import md_analyze as A  # noqa: E402

LINE = re.compile(r"^([0-9a-f]{6}): (\S+)\s*(.*?)\s*;\s*([0-9a-f]{6})(?: ([0-9a-f]{6}))?")


def main():
    asm = A.load_asm("dsp_1.asm")
    full = {}
    for line in (A.OS / "dsp_1.asm").read_text().splitlines():
        m = LINE.match(line)
        if m:
            full[int(m.group(1), 16)] = (m.group(2), m.group(3))
    covered = set()
    for d in sys.argv[1:]:
        for f in Path(d).glob("*.producer.txt"):
            _, b = A.load(f)
            covered |= A.words(b, asm)
    refs = defaultdict(set)          # (kind, space) -> {addr}
    sites = defaultdict(int)
    for pc in sorted(covered):
        if pc not in full:
            continue
        op, args = full[pc]
        for m in re.finditer(r"(?:func|int|label)_([0-9a-f]{6})|>([0-9a-f]{6})\b", args):
            a = int(m.group(1) or m.group(2), 16)
            refs[("target", "p")].add(a); sites["target"] += 1
        for m in re.finditer(r"([xyp]):(?:>|<<?)?\$([0-9a-f]+)(?![0-9a-f,]*\))", args):
            refs[("abs", m.group(1))].add(int(m.group(2), 16)); sites["abs"] += 1
        for m in re.finditer(r"([xyp]):\(r\d[+-]\$([0-9a-f]+)\)", args):
            refs[("disp", m.group(1))].add(int(m.group(2), 16)); sites["disp"] += 1
        for m in re.finditer(r"#>?\$([0-9a-f]+)", args):
            v = int(m.group(1), 16)
            if v >= 0x100:
                refs[("imm", "#")].add(v); sites["imm"] += 1
    print(f"executed voice-DSP words: {len(covered)}")
    for k in sorted(refs):
        v = sorted(refs[k])
        regions = defaultdict(int)
        for a in v:
            regions["%06x" % (a & ~0xfff)] += 1
        print(f"{k[0]:6} {k[1]}: {len(v):4} distinct   by 4K page: "
              + " ".join(f"{r}:{n}" for r, n in sorted(regions.items())))
    print("sites:", dict(sites))


if __name__ == "__main__":
    main()
