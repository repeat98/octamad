#!/usr/bin/env python3
"""Summarise md_profile's map scenarios: which voice-record word each named
parameter (encoders A-H) moves, per engine.

    python3 tools/harness/md_reference/md_mapsummary.py out/md_profile/map
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def main():
    inv = json.loads((ROOT / "out/machinedrum/os163/inventory.json").read_text())
    engines = {e["id"]: e for e in inv["engines"]}
    maps = {}
    for line in (Path(sys.argv[1]) / "map.txt").read_text().splitlines():
        f = line.split()
        m = maps.setdefault(int(f[0], 16), {})
        m["base" if f[1] == "base" else f[1][-1]] = f[2:]
    named = mapped = 0
    missing = []
    for i, m in sorted(maps.items()):
        e = engines[i]
        row = []
        for k, enc in enumerate("ABCDEFGH"):
            name = e["params"][k]
            if not name:
                continue
            named += 1
            ch = m.get(enc, ["-"])
            if ch == ["-"]:
                row.append(f"{name}=?")
                missing.append(f"{e['name']}.{name}")
            else:
                mapped += 1
                row.append(f"{name}=" + ",".join(c.split(":")[0] for c in ch))
        print(f"{e['name']:7} rec{len(m.get('base', [])):2}  " + " ".join(row))
    print(f"\nnamed parameters {named}, mapped to a record word {mapped}")
    print("unmapped: " + " ".join(missing))


if __name__ == "__main__":
    main()
