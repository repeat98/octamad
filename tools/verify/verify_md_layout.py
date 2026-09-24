#!/usr/bin/env python3
"""Audit the Machinedrum core-1 code and table placement.

This is intentionally a read-only audit of the user's pinned update.  It
does not emit a payload, change the layout, or add a generic build target.
The static code set is the relocator's reachable set, including its explicit
boot-init root; it is a conservative placement input, not a runtime claim.
The capacity gate checks the measured relocation map against layout.py.
"""

from __future__ import annotations

import array
import pathlib
import re
import runpy
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "build"))
import md_payload as payload  # noqa: E402


def reachable_words(snapshot: pathlib.Path, relocator: dict) -> set[int]:
    words = set()
    for address, (length, *_rest) in reachable_code(snapshot, relocator).items():
        words.update(range(address, address + length))
    return words


def reachable_code(snapshot: pathlib.Path, relocator: dict) -> dict:
    """Instruction start -> (length, word A, word B, text) for the static code set."""
    values = array.array("I", snapshot.read_bytes())
    table = relocator["decode"](snapshot)
    entries = {relocator["LOOP"][0], relocator["INIT_ENTRY"]}
    for base, count in relocator["TABLES"]:
        for i in range(count):
            value = values[base + i]
            if relocator["in_code_region"](value):
                entries.add(value)

    code = {}
    work = list(entries)
    while work:
        address = work.pop()
        while address in table and address not in code:
            length, _word_a, _word_b, text = table[address]
            code[address] = table[address]
            op = text.split()[0] if text else ""
            for target in relocator["targets"](text):
                if relocator["in_code_region"](target) and target not in code:
                    work.append(target)
            for match in re.findall(r"#>\$([0-9a-f]{6})", text):
                target = int(match, 16)
                if (relocator["in_code_region"](target)
                        and target not in code and target not in entries):
                    entries.add(target)
                    work.append(target)
            if relocator["END"].match(op):
                break
            address += length
    return code


def hot_source_words(path: pathlib.Path, allocation: dict) -> set[int]:
    words = set()
    for line in path.read_text().splitlines():
        parts = line.split()
        if len(parts) != 4 or parts[0] != "M":
            continue
        start, end, new = (int(value, 16) for value in parts[1:])
        if allocation["start"] <= new < allocation["start"] + allocation["words"]:
            words.update(range(start, end))
    return words


def main() -> int:
    _namespace, _update, records = payload.unpack_update(None)
    raw, source = payload.source_maps(records)
    relocator = runpy.run_path(str(ROOT / "tools/harness/md_reference/md_relocate.py"))
    with tempfile.TemporaryDirectory(prefix="md-layout-") as temporary:
        snapshot = pathlib.Path(temporary) / "snapshot.bin"
        payload.write_snapshot(source, snapshot)
        code = reachable_words(snapshot, relocator)

    profiles = payload.default_profiles()
    plan = profiles[0] / "reloc.txt"
    hot = hot_source_words(plan, payload.allocation("hot_code"))
    external_code = {address for address in code if any(
        start <= address < end for start, end, _new in relocator["REGIONS"])}
    internal_code = code - external_code
    if not hot <= external_code:
        print("FAIL: measured hot split contains words outside external code")
        return 1
    remaining = external_code - hot
    print(f"static reachable code: {len(code):,} words")
    print(f"internal low-P loop excluded from packing: {len(internal_code):,} words")
    print(f"external source code: {len(external_code):,} words")
    print(f"measured hot split: {len(hot):,} source words")
    print(f"post-hot code: {len(remaining):,} words")

    for start, end in ((0x100000, 0x103DBA), (0x140000, 0x148000)):
        loaded = {address for values in raw.values() for address in values
                  if start <= address < end}
        print(f"source {start:06x}..{end - 1:06x}: "
              f"code {len(code & set(range(start, end))):,}, "
              f"loaded {len(loaded):,}, gaps {end - start - len(loaded):,}")

    for space in ("P", "X", "Y"):
        loaded = {address for address in raw[space]
                  if 0x140000 <= address < 0x148000}
        print(f"{space} external records: {len(loaded):,}; "
              f"code aliases {len(loaded & code):,}; "
              f"non-code {len(loaded - code):,}")

    layout_ns = runpy.run_path(str(ROOT / "modules/machinedrum/layout.py"))
    window = payload.allocation("window_code")
    window_start = window["start"]
    window_end = window_start + window["words"]
    tables = {space: layout_ns["table_spans"](space)
              for space in ("X", "Y", "W")}
    pi = payload.allocation("pi_buffers")
    tables["Y"].append((pi["start"], pi["start"] + pi["words"]))
    mapped_code = set()
    table_words = 0
    for line in plan.read_text().splitlines():
        fields = line.split()
        if len(fields) == 4 and fields[0] == "M":
            old, end, new = (int(value, 16) for value in fields[1:])
            if window_start <= new < window_end:
                if new + end - old > window_end:
                    print(f"FAIL: mapped code exceeds window at {new:#x}")
                    return 1
                mapped_code.update(range(new, new + end - old))
        elif len(fields) == 5 and fields[0] == "T":
            space = fields[1]
            old, end, new = (int(value, 16) for value in fields[2:])
            if not any(lo <= new and new + end - old <= hi
                       for lo, hi in tables[space]):
                print(f"FAIL: table {old:#x}..{end:#x} outside {space} allocation")
                return 1
            table_words += end - old
    print(f"mapped window code: {len(mapped_code):,}/{window['words']:,} words")
    print(f"mapped tables and P-I buffers: {table_words:,} words")
    print("PASS: mapped code and tables fit the core-1 allocations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
