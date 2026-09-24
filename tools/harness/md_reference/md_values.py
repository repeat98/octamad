#!/usr/bin/env python3
"""Compare one-block md_replay RAM read-value traces across relocation.

Build the interpreter replay with md_reads.sh, then run it once plain and
once with --reloc --driver using MD_REPLAY_VALUES=<path> and
MD_REPLAY_VALUE_BLOCK=<zero-based block>. This tool maps moved PCs, data
addresses and pointer-looking values back through reloc.txt. It reports
the first aligned read whose value differs for a reason other than the
address move. Non-pointer data that happens to equal a moved address is
ambiguous and must be inspected at the reported instruction.
"""
import argparse
import difflib
from pathlib import Path


def relocation(path):
    code, data, loop = [], [], {}
    for line in path.read_text().splitlines():
        parts = line.split()
        if not parts:
            continue
        kind = parts[0]
        if kind == "M":
            old, end, new = (int(x, 16) for x in parts[1:])
            code.append((old, end, new))
            data.append((None, old, end, new))
        elif kind in ("T", "Q"):
            area = parts[1]
            old, end, new = (int(x, 16) for x in parts[2:])
            data.append((area, old, end, new))
        elif kind == "V":
            old, new = (int(x, 16) for x in parts[1:])
            loop[new] = old
    return code, data, loop


def old_address(value, area, spans, loop=None):
    if area == "Y" and loop and value in loop:
        return loop[value]
    for space, old, end, new in spans:
        if (space is None or space == area) and new <= value < new + end - old:
            return old + value - new
    return value


def possible_old_values(value, spans, loop):
    """A pointer's home can differ from the space holding the pointer."""
    out = {value}
    if value in loop:
        out.add(loop[value])
    for _space, old, end, new in spans:
        if new <= value < new + end - old:
            out.add(old + value - new)
    return out


def events(path, code, data, loop, moved):
    out = []
    code_spans = [(None, *span) for span in code]
    for line in path.read_text().splitlines():
        block, pc, area, addr, value = line.split()
        pc, addr, value = (int(x, 16) for x in (pc, addr, value))
        if moved:
            pc = old_address(pc, "P", code_spans)
            addr = old_address(addr, area, data, loop)
        if pc >= 0x100000:  # omit MD loop and the replacement driver
            out.append((int(block), pc, area, addr, value))
    return out


def fmt(event):
    block, pc, area, addr, value = event
    return f"block {block} P:{pc:06x} {area}:{addr:06x} -> {value:06x}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plain", type=Path)
    parser.add_argument("moved", type=Path)
    parser.add_argument("reloc", type=Path)
    parser.add_argument("--plain-reloc", type=Path,
                        help="map the first trace too, when it is a relocated control")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    code, data, loop = relocation(args.reloc)
    if args.plain_reloc:
        plain_code, plain_data, plain_loop = relocation(args.plain_reloc)
        plain = events(args.plain, plain_code, plain_data, plain_loop, True)
    else:
        plain = events(args.plain, code, data, loop, False)
    moved = events(args.moved, code, data, loop, True)
    key = lambda e: e[:4]
    matcher = difflib.SequenceMatcher(None, [key(e) for e in plain],
                                      [key(e) for e in moved], autojunk=False)
    aligned = 0
    pointer_only = 0
    different = 0
    for tag, a, b, c, d in matcher.get_opcodes():
        if tag != "equal":
            continue
        for left, right in zip(plain[a:b], moved[c:d]):
            aligned += 1
            if left[4] == right[4]:
                continue
            if left[4] in possible_old_values(right[4], data, loop):
                pointer_only += 1
                continue
            different += 1
            if different <= args.limit:
                print(f"#{different} {fmt(left)} | moved {right[4]:06x}")
    print(f"engine reads: plain {len(plain)}, moved {len(moved)};"
          f" aligned {aligned}, pointer-equivalent {pointer_only},"
          f" other value differences {different}")


if __name__ == "__main__":
    main()
