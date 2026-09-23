#!/usr/bin/env python3
"""Relocate the Machinedrum voice DSP's code and tables, for md_replay --reloc.

    python3 tools/harness/md_reference/md_relocate.py <capture dir> [profile dirs...]

The engine code lives in two external regions of the MD's unified external
RAM. This moves each region by its own offset (REGIONS below) and patches every
address that points into a moved region:

  * code is found by recursive descent (md_dis decodes every address of the
    snapshot): from the voice loop head (P:64) and every entry of the three
    routine tables (init 0x145af5, trigger 0x145bb6, render 0x145c77, 193
    each). Branches and calls continue at both target and fall-through;
    rts/rti/jmp/bra end a path. Long immediates that point into a code
    region are taken as extra entry points (the indirect jsr (rN) targets);
  * in every code instruction of two words, word B is patched when it holds a
    moved address: a jump/loop target, an absolute or displacement operand,
    or a #> immediate;
  * the routine tables are patched entry by entry.

  * the snapshot's live state: every word of internal X and Y holding an
    address in a moved region (per-voice pointers set by init code that ran
    before the snapshot; on the OT, init runs after relocation instead).
    A value test cannot tell a pointer from data that happens to fall in the
    range, so a live patch is a guess the replay has to confirm.

Writes <capture dir>/reloc.txt, which md_replay --reloc applies:
  M <old start> <old end> <new start>     move a region (end exclusive)
  W <new addr> <value>                    a patched P word at its new place
                                          (or in place, below the regions)
  X|Y <addr> <value>                      a patched live-state word
With profile dirs, it also checks that every word those runs executed was
found as code (a hole means the descent missed a path).
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DIS = ROOT / "out/md_reference/md_dis"

# old start, old end (exclusive), new start. The new places sit in the
# emulator's bridged external RAM at 0x30000.., where P, X and Y alias, as
# they do in the OT's shared window.
REGIONS = [
    (0x100000, 0x103DBA, 0x3B000),   # engine code, its tables, the E12 sample descriptors (0x103d7b)
    (0x140000, 0x148000, 0x30000),   # tables, engine code, routine tables
]
LOOP = (0x64, 0xE8)
TABLES = [(0x145AF5, 193), (0x145BB6, 193), (0x145C77, 193)]

CC = "(cc|hs|ge|ne|pl|nn|ec|lc|gt|cs|lo|lt|eq|mi|nr|es|ls|le)"
END = re.compile(r"^(rts|rti|jmp|bra|illegal|stop|debug)$")
BRANCH = re.compile(rf"^(b{CC}|j{CC}|bs{CC}|js{CC}|bsr|jsr|brclr|brset|bsclr|bsset|jclr|jset|jsclr|jsset|bra|jmp)$")


def moved(a):
    for s, e, n in REGIONS:
        if s <= a < e:
            return n + (a - s)
    return None


def in_code_region(a):
    return moved(a) is not None or LOOP[0] <= a < LOOP[1]


def decode(snapshot):
    ranges = [f"{LOOP[0]:x}-{LOOP[1]:x}"] + [f"{s:x}-{e:x}" for s, e, _ in REGIONS]
    out = subprocess.run([str(DIS), str(snapshot)] + ranges, capture_output=True, text=True, check=True).stdout
    table = {}
    for line in out.splitlines():
        a, ln, wa, wb, text = line.split(" ", 4)
        table[int(a, 16)] = (int(ln), int(wa, 16), int(wb, 16), text.strip())
    return table


def targets(text):
    return [int(m, 16) for m in re.findall(r"(?:func|int|label|loc)_([0-9a-f]{6})", text)] + \
           [int(m, 16) for m in re.findall(r"(?<![xyl]:)>\$([0-9a-f]{5,6})\b", text)
            if re.match(r"^(j|b|do|dor)", text)]


def main():
    cap = Path(sys.argv[1])
    snap = cap / "snapshot.bin"
    P = memoryview(snap.read_bytes()).cast("I")
    table = decode(snap)

    entries = {LOOP[0]}
    for base, n in TABLES:
        for i in range(n):
            v = P[base + i]
            if in_code_region(v):
                entries.add(v)
    code, work = {}, list(entries)
    while work:
        a = work.pop()
        while a in table and a not in code:
            ln, wa, wb, text = table[a]
            code[a] = table[a]
            op = text.split()[0] if text else ""
            for t in targets(text):
                if in_code_region(t) and t not in code:
                    work.append(t)
            for m in re.findall(r"#>\$([0-9a-f]{6})", text):
                v = int(m, 16)
                if in_code_region(v) and v not in code and v not in entries:
                    entries.add(v)
                    work.append(v)
            if END.match(op) and "(r" not in text.split(None, 1)[-1]:
                break
            if END.match(op):
                break
            a += ln

    patches = {}
    kinds = {}
    for a, (ln, wa, wb, text) in code.items():
        if ln != 2:
            continue
        m = moved(wb)
        if m is None:
            continue
        kind = ("target" if BRANCH.match(text.split()[0]) else
                "loop" if text.startswith(("do", "dor")) else
                "imm" if "#>$" in text else
                "disp" if re.search(r"\(r\d[+-]\$", text) else "abs")
        kinds[kind] = kinds.get(kind, 0) + 1
        patches[a + 1] = m
    for base, n in TABLES:
        for i in range(n):
            m = moved(P[base + i])
            if m is not None:
                patches[base + i] = m
                kinds["table"] = kinds.get("table", 0) + 1

    live = []
    X = P[0x150000:0x170000]
    Y = P[0x170000:0x190000]
    for area, mem in (("X", X), ("Y", Y)):
        for i, v in enumerate(mem):
            m = moved(v)
            if m is not None:
                live.append((area, i, m))
    # Not the working RAM above the moved regions (0x148000..): a scan there
    # "found" 60 pointers in c10 that were two curve tables (step ~0x63c)
    # crossing the code ranges, and patching them broke single samples.
    kinds["live"] = len(live)

    words = set()
    for a, (ln, *_rest) in code.items():
        words.update(range(a, a + ln))
    print(f"code: {len(code)} instructions, {len(words)} words, from {len(entries)} entry points")
    print("patches: " + ", ".join(f"{k} {v}" for k, v in sorted(kinds.items())))

    if len(sys.argv) > 2:
        sys.path.insert(0, str(Path(__file__).parent))
        import md_analyze as A
        asm = A.load_asm("dsp_1.asm")
        executed = set()
        for d in sys.argv[2:]:
            for f in Path(d).glob("*.producer.txt"):
                _, b = A.load(f)
                executed |= {w for w in A.words(b, asm) if in_code_region(w)}
        holes = sorted(executed - words)
        print(f"executed words in the code regions: {len(executed)}, not found as code: {len(holes)}"
              + (" e.g. " + " ".join(f"{h:06x}" for h in holes[:12]) if holes else ""))

    with (cap / "reloc.txt").open("w") as f:
        for s, e, n in REGIONS:
            f.write(f"M {s:06x} {e:06x} {n:06x}\n")
        for a, v in sorted(patches.items()):
            f.write(f"W {moved(a) if moved(a) is not None else a:06x} {v:06x}\n")
        for area, a, v in live:
            f.write(f"{area} {a:06x} {v:06x}\n")
    print(f"wrote {cap / 'reloc.txt'}")


if __name__ == "__main__":
    main()
