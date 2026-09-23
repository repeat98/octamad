#!/usr/bin/env python3
"""Summarize exact stock-firmware PC counts. Counts are not hardware cycles.

Use --pcs on an ot_emu --coverage output. Unnamed windows remain addresses;
we never infer a function boundary just because a nearby address has a name.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
# Half-open boundaries verified against 1.40C disassembly; exclusive counts
# exclude callees, so these scopes never double count nested function work.
SCOPES = (
    ("sample analysis", 0x40098388, 0x400985AC),
    ("frame builder ISR (exclusive)", 0x4000AAD0, 0x4000D9B0),
    ("eight-track delay", 0x400031A0, 0x4000385A),
    ("correlation search", 0x4009871C, 0x40098A2C),
    ("voice renderer (exclusive)", 0x40007960, 0x40008F82),
)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def distribution(values):
    values = sorted(values)
    if not values:
        raise ValueError("no complete frames")
    return dict(n=len(values), mean=sum(values)/len(values),
                p95=values[math.ceil(.95*len(values))-1],
                p99=values[math.ceil(.99*len(values))-1], maximum=values[-1])


def detailed(prefix, counts, image, expected_frames):
    keys = ("frame", "cpu", "dsp0", "dsp1", "skipped0", "skipped1", "complete")
    lines = Path(str(prefix)+".frames.tsv").read_text().splitlines()
    if not lines or lines[0].split() != list(keys):
        raise ValueError("invalid frame table header")
    rows = []
    for line in lines[1:]:
        values = list(map(int, line.split()))
        if len(values)!=len(keys) or min(values)<0 or values[-1] not in (0,1):
            raise ValueError("invalid frame table row")
        rows.append(dict(zip(keys,values)))
    if not rows or sum(r["cpu"] for r in rows) != sum(counts.values()):
        raise ValueError("CPU frame/PC accounting mismatch")
    if any(b["frame"] != a["frame"]+1 for a,b in zip(rows,rows[1:])):
        raise ValueError("non-contiguous frame buckets")
    if rows[0]["frame"]!=0 or rows[-1]["frame"]!=expected_frames:
        raise ValueError("frame table does not cover --frames; incomplete run or wrong denominator")
    if rows[0]["complete"] or rows[-1]["complete"]:
        raise ValueError("boundary buckets must be excluded from percentiles")
    result = {key: distribution([r[key] for r in rows if r["complete"]])
              for key in ("cpu", "dsp0", "dsp1", "skipped0", "skipped1")}
    sys.path.insert(0,str(ROOT/"tools/build"))
    import dsp_modmap
    result["dsp_regions"] = []
    for core, (tag, va, length) in enumerate(dsp_modmap.PAYLOADS):
        pcs = read_counts(str(prefix)+f".dsp{core}.tsv")
        if sum(pcs.values()) != sum(r[f"dsp{core}"] for r in rows):
            raise ValueError(f"DSP{core} frame/PC accounting mismatch")
        mods, _ = dsp_modmap.modules(image, va, length)
        regions = [dict(start=f"P:{addr:05x}", end=f"P:{addr+n:05x}",
                        instructions=sum(v for pc,v in pcs.items() if addr<=pc<addr+n))
                   for space,addr,n,_ in mods if space==0]
        regions.sort(key=lambda x:-x["instructions"])
        result["dsp_regions"].append(dict(core=core, payload=tag, total=sum(pcs.values()),
                                         regions=regions))
    return result


def read_counts(path):
    counts = {}
    for line in Path(path).read_text().splitlines():
        addr, count = line.split()
        pc, n = int(addr, 16), int(count)
        if pc in counts or n < 0 or not 0<=pc<=0xffffffff:
            raise ValueError(f"duplicate/invalid PC or negative count: {line}")
        counts[pc] = n
    return counts


def windows(counts, size=256):
    result = defaultdict(int)
    for pc, n in counts.items():
        result[pc // size * size] += n
    return sorted(result.items(), key=lambda item: (-item[1], item[0]))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    select = ap.add_mutually_exclusive_group(required=True)
    select.add_argument("--pcs", type=Path)
    select.add_argument("--prefix", type=Path, help="ot_emu --work-profile output prefix")
    ap.add_argument("--frames", type=int, required=True)
    ap.add_argument("--image", type=Path, default=ROOT / "out/raw/section_3_MAIN_OS.bin")
    ap.add_argument("--json", type=Path)
    ap.add_argument("--card", type=Path, help="include workload image hash")
    ap.add_argument("--candidate-map", type=Path, help="include relocated analysis code in its scope")
    args = ap.parse_args()
    if args.frames <= 0:
        ap.error("--frames must be positive")
    pcs_path = args.pcs or Path(str(args.prefix)+".cpu.tsv")
    counts = read_counts(pcs_path)
    total = sum(counts.values())
    rows = [dict(start=f"0x{pc:08x}", end=f"0x{pc+256:08x}",
                 instructions=n, per_frame=n/args.frames,
                 share_percent=100*n/total if total else 0)
            for pc, n in windows(counts)]
    report = dict(units="ColdFire executed instructions; not hardware cycles",
                  image_sha256=digest(args.image), pcs_sha256=digest(pcs_path),
                  frames=args.frames, total=total, per_frame=total/args.frames,
                  address_windows=rows)
    report["scopes"] = sorted([
        dict(name=name, start=hex(start), end=hex(end),
             instructions=(n := sum(v for pc,v in counts.items() if start<=pc<end)),
             per_frame=n/args.frames, share_percent=100*n/total if total else 0)
        for name,start,end in SCOPES], key=lambda row:-row["instructions"])
    if args.candidate_map:
        placement = json.loads(args.candidate_map.read_text())
        if placement["image_sha256"] != report["image_sha256"]:
            raise ValueError("candidate map/image hash mismatch")
        start, size = placement["cave_address"], placement["cave_bytes"]
        extra = sum(v for pc,v in counts.items() if start<=pc<start+size)
        row = next(r for r in report["scopes"] if r["name"] == "sample analysis")
        row["instructions"] += extra
        row["per_frame"] = row["instructions"]/args.frames
        row["share_percent"] = 100*row["instructions"]/total if total else 0
        row["cave"] = dict(start=hex(start), bytes=size, instructions=extra)
        report["scopes"].sort(key=lambda r:-r["instructions"])
    if args.prefix:
        report["complete_frames"] = detailed(args.prefix, counts, args.image.read_bytes(), args.frames)
    if args.card:
        report["card_sha256"] = digest(args.card)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2) + "\n")
    print(f"{total:,} instructions / {args.frames} frames = {total/args.frames:,.1f}/frame")
    for row in report["scopes"]:
        print(f"{row['name']}: {row['per_frame']:.1f}/frame ({row['share_percent']:.2f}%)")
    if args.prefix:
        for key,value in report["complete_frames"].items():
            if key != "dsp_regions": print(f"{key}: {value}")
    for row in rows[:12]:
        print(f"{row['start']}..{row['end']}  {row['per_frame']:9.1f}/frame  {row['share_percent']:5.2f}%")


if __name__ == "__main__":
    main()
