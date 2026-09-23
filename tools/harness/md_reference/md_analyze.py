#!/usr/bin/env python3
"""Summarise an md_profile run: per-engine DSP work and code footprint.

    python3 tools/harness/md_reference/md_analyze.py out/md_profile/cat

Reads <dir>/idle.* and <dir>/m<id>.* (md_profile), the machine names from
out/machinedrum/os163/inventory.json and the disassembly of both DSP images
(modules/machinedrum/extraction.py --disasm).

Work is every cycle outside the known wait loops (md_profile.cpp names them);
"peak" is the busiest 10 ms window. Code is counted in P words: each block
the engine ran that idle did not, walked through the disassembly to its first
flow change (at most 32 instructions, the fork's JIT block cap) -- an
estimate of the executed words, not a coverage trace.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OS = ROOT / "out/machinedrum/os163"
WAIT = {"producer": set(range(0x100092, 0x100099)) | set(range(0xbb, 0xc0)),
        "mixer": set(range(0x3c, 0x45))}
ASM = {"producer": "dsp_1.asm", "mixer": "dsp_2.asm"}
FLOW = re.compile(r"^(bra|jmp|rts|rti|b[a-z]{2}|j[a-z]{2}|jclr|jset|brclr|brset|"
                  r"jsclr|jsset|bsclr|bsset|do|dor|enddo|bsr|jsr|debug|wait|stop)\b")


def load_asm(name):
    ins = {}
    for line in (OS / name).read_text().splitlines():
        m = re.match(r"^([0-9a-f]{6}): (\S+).*;\s*([0-9a-f]{6})(?: ([0-9a-f]{6}))?", line)
        if m:
            ins[int(m.group(1), 16)] = (m.group(2), 2 if m.group(4) else 1)
    return ins


def load(path):
    head, blocks = {}, {}
    for line in path.read_text().splitlines():
        if line.startswith("#"):
            f = line[1:].split()
            head = dict(zip(f[0::2], map(float, f[1::2])))
            continue
        pc, count, cycles, *_ = line.split()
        blocks[int(pc, 16)] = (int(count), int(cycles))
    return head, blocks


def words(blocks, ins):
    covered = set()
    for pc in blocks:
        a, n = pc, 0
        while a in ins and n < 32:
            op, ln = ins[a]
            covered.update(range(a, a + ln))
            a += ln
            n += 1
            if FLOW.match(op):
                break
        if pc not in ins:
            covered.add(pc)
    return covered


def main():
    d = Path(sys.argv[1])
    names = {e["id"]: e["name"] for e in json.loads((OS / "inventory.json").read_text())["engines"]}
    asm = {k: load_asm(v) for k, v in ASM.items()}
    idle = {k: load(d / f"idle.{k}.txt") for k in ASM}
    rows, excl_all = [], {k: {} for k in ASM}
    for f in sorted(d.glob("m*.producer.txt")):
        tag = f.name.split(".")[0]
        row = {"id": int(tag[1:], 16), "name": names.get(int(tag[1:], 16), tag)}
        for k in ASM:
            head, b = load(d / f"{tag}.{k}.txt")
            n = head["samples"]
            work = sum(cy for pc, (c, cy) in b.items() if pc not in WAIT[k]) / n
            new = {pc: v for pc, v in b.items() if pc not in idle[k][1]}
            excl_all[k][row["name"]] = set(words(new, asm[k]))
            row[k] = {"work": work, "peak": head.get("peakWorkPerSample", 0),
                      "new_words": len(excl_all[k][row["name"]]),
                      "new_cycles": sum(v[1] for v in new.values()) / n}
            row["rms"] = head["rms"]
        rows.append(row)

    for k in ASM:
        head, b = load(d / f"idle.{k}.txt")
        idle_work = sum(cy for pc, (c, cy) in b.items() if pc not in WAIT[k]) / head["samples"]
        print(f"{k}: idle work {idle_work:.0f} cycles/sample (of 2,304), "
              f"idle peak {head.get('peakWorkPerSample', 0):.0f}")
    print(f"\n{'engine':8} {'rms':>6} | {'producer work':>13} {'peak':>5} {'new words':>9} | {'mixer work':>10} {'peak':>5}")
    for r in rows:
        p, m = r["producer"], r["mixer"]
        print(f"{r['name']:8} {r['rms']:6.3f} | {p['work']:13.0f} {p['peak']:5.0f} {p['new_words']:9d} | "
              f"{m['work']:10.0f} {m['peak']:5.0f}")
    for k in ASM:
        sets = excl_all[k]
        union = set().union(*sets.values()) if sets else set()
        shared = set.intersection(*sets.values()) if sets else set()
        fams = {}
        for name, s in sets.items():
            fams.setdefault(name[:3], set()).update(s)
        print(f"\n{k}: code run by any engine and not by idle: {len(union)} words; "
              f"run by every engine: {len(shared)}")
        for fam, s in fams.items():
            print(f"    {fam}: {len(s)} words")
        own = {n: len(s - set().union(*(t for m, t in sets.items() if m != n))) for n, s in sets.items()}
        print("    words no other engine runs: " + ", ".join(f"{n} {v}" for n, v in own.items()))


if __name__ == "__main__":
    main()
