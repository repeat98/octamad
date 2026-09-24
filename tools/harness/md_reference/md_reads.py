#!/usr/bin/env python3
"""Classify the Machinedrum's data spans by the memory space they are read through.

    python3 tools/harness/md_reference/md_reads.py <reads.txt> [<reads.txt> ...]

Each reads.txt comes from md_replay built with -DMD_REPLAY_READS (see
md_reads.sh) and run on one capture: runs "<start> <end> <PXY>" over the MD's
external RAM 0x100000-0x14ffff. The union over all captures is classified:

  * tables: every maximal run of loaded, non-code words in the two source
    spans (0x100000-0x103db9, 0x140000-0x147fff). A table is addressed by
    base plus index, so it moves whole: a run read through one space only
    can go to that core's private memory, a run read through more than one
    space (or through P) needs the shared window, and a run never read in
    these captures is unclassified;
  * the boot-built sine 0x148000-0x14ffff and the P-I buffers
    0x135600-0x13b5ff: which words are read, and through which space.

A run's class is only as good as the captures: a word that no capture reads
proves nothing about the space it would be read through.
"""

from __future__ import annotations

import array
import pathlib
import runpy
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools" / "build"))
sys.path.insert(0, str(ROOT / "tools" / "verify"))
import md_payload as payload  # noqa: E402
from verify_md_layout import reachable_words  # noqa: E402

SPANS = ((0x100000, 0x103DBA), (0x140000, 0x148000))
SINE = (0x148000, 0x150000)
PI = (0x135600, 0x13B600)
BIT = {"P": 1, "X": 2, "Y": 4}
NAME = {0: "unread", 1: "P", 2: "X", 3: "PX", 4: "Y", 5: "PY", 6: "XY", 7: "PXY"}


def load_reads(paths):
    flags = {}
    for path in paths:
        for line in pathlib.Path(path).read_text().splitlines():
            start, end, spaces = line.split()
            bits = sum(BIT[c] for c in spaces)
            for a in range(int(start, 16), int(end, 16)):
                flags[a] = flags.get(a, 0) | bits
    return flags


def runs(words):
    words = sorted(words)
    out = []
    for a in words:
        if out and out[-1][1] == a:
            out[-1][1] = a + 1
        else:
            out.append([a, a + 1])
    return out


def main() -> int:
    paths = sys.argv[1:]
    if not paths:
        print(__doc__)
        return 2
    flags = load_reads(paths)

    _namespace, _update, records = payload.unpack_update(None)
    raw, source = payload.source_maps(records)
    relocator = runpy.run_path(str(ROOT / "tools/harness/md_reference/md_relocate.py"))
    with tempfile.TemporaryDirectory(prefix="md-reads-") as temporary:
        snapshot = pathlib.Path(temporary) / "snapshot.bin"
        payload.write_snapshot(source, snapshot)
        code = reachable_words(snapshot, relocator)
    loaded = {a for values in raw.values() for a in values}

    print(f"captures: {len(paths)}")
    totals = {}
    detail = []
    for lo, hi in SPANS:
        data = {a for a in loaded if lo <= a < hi} - code
        for start, end in runs(data):
            bits = 0
            read = 0
            for a in range(start, end):
                if flags.get(a):
                    bits |= flags[a]
                    read += 1
            cls = NAME[bits]
            totals[cls] = totals.get(cls, 0) + (end - start)
            detail.append((start, end, cls, read))
    print("tables (maximal runs of loaded non-code words), words by class:")
    for cls in sorted(totals, key=lambda c: -totals[c]):
        n = sum(1 for d in detail if d[2] == cls)
        print(f"  {cls:6s} {totals[cls]:6,} words in {n} runs")
    one_space = totals.get("X", 0) + totals.get("Y", 0)
    window = sum(v for k, v in totals.items() if k not in ("X", "Y", "unread"))
    print(f"  single-space (X or Y only): {one_space:,}; needs the window: {window:,}; "
          f"unread: {totals.get('unread', 0):,}")
    print("  the largest runs:")
    for start, end, cls, read in sorted(detail, key=lambda d: d[0] - d[1])[:12]:
        print(f"    {start:06x}..{end - 1:06x} {end - start:6,} words {cls:6s} ({read:,} read)")

    for label, (lo, hi) in (("sine", SINE), ("P-I buffers", PI)):
        by = {}
        for a in range(lo, hi):
            cls = NAME[flags.get(a, 0)]
            by[cls] = by.get(cls, 0) + 1
        read = [a for a in range(lo, hi) if flags.get(a)]
        span = f"{read[0]:06x}..{read[-1]:06x}" if read else "none"
        print(f"{label} {lo:06x}..{hi - 1:06x}: read {len(read):,} of {hi - lo:,} words, "
              f"first..last read {span}; by class "
              + ", ".join(f"{k} {v:,}" for k, v in sorted(by.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
