#!/usr/bin/env python3
"""Build and verify the Machinedrum core-1 payload-B load records.

The user's pinned OS update is read at build time. No firmware bytes enter
Git. The same placement plan and relocation used by the twelve-kit replay
gate produce sparse P/X/Y records in the core-1 layout. This is a payload
artifact, not a bootable Octatrack image: the native dispatcher and machine
registration are separate integration work.
"""

from __future__ import annotations

import argparse
import array
import hashlib
import json
import pathlib
import runpy
import struct
import subprocess
import sys
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "out/machinedrum/build"
SOURCE = OUT / "source"
RELOCATOR = ROOT / "tools/harness/md_reference/md_relocate.py"
DRIVER = ROOT / "tools/harness/md_reference/md_driver.py"
EXTRACTION = ROOT / "modules/machinedrum/extraction.py"
MEM = OUT / "payload_B.mem"
MANIFEST = OUT / "manifest.json"

SPACE = {0: "P", 1: "X", 2: "Y"}
SPACE_ID = {v: k for k, v in SPACE.items()}
SNAP_WORDS = 0x190000       # md_replay: P + 0x20000 X + 0x20000 Y
SNAP_X = 0x150000
SNAP_Y = 0x170000
EXTERNAL_LO, EXTERNAL_HI = 0x140000, 0x148000


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha(path: pathlib.Path) -> str:
    return sha(path.read_bytes())


def die(message: str) -> "NoReturn":
    raise SystemExit(f"md-payload: {message}")


def extraction_namespace():
    # runpy follows the repository's existing manifest pattern and avoids
    # importing a module whose output directory or user path is global state.
    return runpy.run_path(str(EXTRACTION))


def unpack_update(syx: pathlib.Path | None):
    ns = extraction_namespace()
    path = ns["find_syx"](str(syx) if syx else None)
    ns["unpack"](path)
    # Only the voice DSP is shipped. The MD mixer DSP contains the original
    # per-track effects and master processing, excluded from this remix.
    records = ns["dsp_records"]("section_1_DSP.bin")
    return ns, pathlib.Path(path), records


def add_raw(raw: dict[str, dict[int, int]], space: str, start: int,
            words: list[int]) -> None:
    dst = raw[space]
    for i, word in enumerate(words):
        address = start + i
        if address in dst and dst[address] != word:
            die(f"section-1 has conflicting {space}:{address:06x} words")
        dst[address] = word & 0xFFFFFF


def source_maps(records):
    """Return the raw P/X/Y maps and a P view of the bridged external RAM.

    The MD update labels parts of the external source as X and Y while the
    reference DSP sees the same physical RAM through P.  The relocator's
    0x140000..0x148000 move is a P-space move, so merge that non-overlapping
    physical source before making its snapshot.
    """
    raw = {name: {} for name in ("P", "X", "Y")}
    for space, address, words in records:
        add_raw(raw, SPACE[space], address, words)

    external = {}
    for address in range(EXTERNAL_LO, EXTERNAL_HI):
        seen = [(name, values[address]) for name, values in raw.items()
                if address in values]
        if not seen:
            continue
        values = {value for _, value in seen}
        if len(values) != 1:
            die("section-1 external P/X/Y aliases disagree at "
                f"0x{address:06x}: {seen}")
        external[address] = seen[0][1]
    p = dict(raw["P"])
    p.update(external)
    return raw, {"P": p, "X": dict(raw["X"]), "Y": dict(raw["Y"])}


def write_snapshot(mem: dict[str, dict[int, int]], path: pathlib.Path) -> None:
    words = [0] * SNAP_WORDS
    for address, value in mem["P"].items():
        if 0 <= address < SNAP_X:
            words[address] = value
    for area, base in (("X", SNAP_X), ("Y", SNAP_Y)):
        for address, value in mem[area].items():
            if 0 <= address < 0x20000:
                words[base + address] = value
    path.write_bytes(array.array("I", words).tobytes())


def default_profiles() -> list[pathlib.Path]:
    profiles = sorted((ROOT / "out/md_profile/cap4").glob("*/reloc.txt"))
    if not profiles:
        die("no cap4 relocation plans; pass --profiles explicitly")
    return [p.parent for p in profiles]


def hot_plan_signature(path: pathlib.Path) -> str:
    lines = [line for line in path.read_text().splitlines()
             if line.startswith("H ")]
    if not lines:
        die(f"hot plan has no H units in {path}")
    return sha(("\n".join(lines) + "\n").encode())


def run_relocator(source: pathlib.Path, profiles: list[pathlib.Path],
                  placement: pathlib.Path) -> tuple[str, str]:
    plans = [p / "reloc.txt" for p in profiles]
    missing = [p for p in plans if not p.exists()]
    if missing:
        die("profile(s) have no measured reloc.txt: "
            + ", ".join(map(str, missing)))
    signatures = {hot_plan_signature(p) for p in plans}
    if len(signatures) != 1:
        die("the capture hot plans disagree: " + ", ".join(sorted(signatures)))
    command = [sys.executable, str(RELOCATOR), "--hot-plan", str(plans[0]),
               "--plan", str(placement), str(source)]
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    if result.stdout:
        print(result.stdout, end="")
    if result.returncode:
        die(f"relocator failed (exit {result.returncode})\n{result.stderr}")
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")
    return file_sha(source / "reloc.txt"), next(iter(signatures))


def run_driver(source: pathlib.Path) -> tuple[list[int], str]:
    command = [sys.executable, str(DRIVER), str(source), "--reloc"]
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    if result.returncode:
        die(f"driver assembler failed (exit {result.returncode})\n{result.stderr}")
    if result.stdout:
        print(result.stdout.splitlines()[0])
    words = [int(line, 16) for line in
             (source / "driver.bin").read_text().splitlines() if line]
    return words, file_sha(source / "driver.bin")


def parse_plan(path: pathlib.Path) -> list[tuple[str, tuple]]:
    out = []
    for line in path.read_text().splitlines():
        parts = line.split()
        if not parts or parts[0].startswith("#"):
            continue
        kind = parts[0]
        if kind in ("T", "Q"):
            if len(parts) != 5 or parts[1] not in ("X", "Y"):
                die(f"bad {kind} relocation line {line!r}")
            values = (parts[1], *(int(v, 16) for v in parts[2:]))
        elif kind in ("M", "H", "V", "W", "X", "Y", "I"):
            values = tuple(int(v, 16) for v in parts[1:])
        else:
            die(f"unknown relocation directive {line!r}")
        out.append((kind, values))
    return out


def apply_plan(original: dict[str, dict[int, int]],
               plan: list[tuple[str, tuple]]):
    """Build the destination words using md_replay's directive order."""
    mem = {space: dict(words) for space, words in original.items()}
    for kind, values in plan:
        if kind == "M":
            start, end, new = values
            words = [mem["P"].get(start + i, 0) for i in range(end - start)]
            for i, word in enumerate(words):
                mem["P"][new + i] = word
        elif kind == "T":
            area, start, end, new = values
            for i in range(end - start):
                mem[area][new + i] = mem["P"].get(start + i, 0)
        elif kind == "Q":
            area, start, end, new = values
            words = [mem[area].get(start + i, 0) for i in range(end - start)]
            for i, word in enumerate(words):
                mem[area][new + i] = word
            for address in range(start, end):
                mem[area][address] = 0
        elif kind == "V":
            old, new = values
            mem["Y"][new] = mem["Y"].get(old, 0)
            mem["Y"][old] = 0
        elif kind in ("W", "X", "Y"):
            address, word = values
            area = "P" if kind == "W" or address >= 0x30000 else kind
            mem[area][address] = word
        elif kind in ("H", "I"):
            pass
    return mem


def contiguous_ranges(addresses: set[int]):
    if not addresses:
        return
    ordered = sorted(addresses)
    start = previous = ordered[0]
    for address in ordered[1:]:
        if address != previous + 1:
            yield start, previous + 1
            start = address
        previous = address
    yield start, previous + 1


def allocation(name: str) -> dict:
    layout = runpy.run_path(str(ROOT / "modules/machinedrum/layout.py"))["LAYOUT"]
    return next(r for r in layout["allocations"] if r["name"] == name)


def range_words(mem: dict[str, dict[int, int]], space: str, start: int,
                end: int) -> list[int]:
    return [mem[space].get(address, 0) for address in range(start, end)]


def build_records(raw: dict[str, dict[int, int]], relocated,
                  plan: list[tuple[str, tuple]], driver_words: list[int]):
    """Emit every relocation destination and initialized low MD word."""
    owned = {space: set() for space in ("P", "X", "Y")}
    for kind, values in plan:
        if kind == "M":
            start, end, new = values
            owned["P"].update(range(new, new + end - start))
        elif kind in ("T", "Q"):
            area, start, end, new = values
            owned[area].update(range(new, new + end - start))
        elif kind in ("W", "X", "Y"):
            address, _word = values
            area = "P" if kind == "W" or address >= 0x30000 else kind
            owned[area].add(address)
        elif kind == "V":
            _old, new = values
            owned["Y"].add(new)
    # Only X:0..ff and Y:0..13f are swapped with the stock OT.
    # The update's higher internal records include MD loop/DMA scratch and
    # old output buffers; the replacement driver owns their new addresses.
    owned["X"].update(a for a in raw["X"] if a < 0x100)
    owned["Y"].update(a for a in raw["Y"] if a < 0x140)
    driver = allocation("driver_code")
    if len(driver_words) > driver["words"]:
        die(f"driver has {len(driver_words)} words but only "
            f"{driver['words']} are allocated")
    owned["P"].update(range(driver["start"], driver["start"] + len(driver_words)))
    records = []
    for area in ("P", "X", "Y"):
        for start, end in contiguous_ranges(owned[area]):
            words = []
            for address in range(start, end):
                if area == "P" and driver["start"] <= address < driver["start"] + len(driver_words):
                    word = driver_words[address - driver["start"]]
                else:
                    word = relocated[area].get(address, 0)
                words.append(word)
            records.append((area, start, words))
    if not any(area == "P" and start <= driver["start"] < start + len(words)
               for area, start, words in records):
        die("driver is absent from payload")
    layout = runpy.run_path(str(ROOT / "modules/machinedrum/layout.py"))["LAYOUT"]
    allowed = {area: [] for area in ("P", "X", "Y")}
    for region in layout["allocations"]:
        area = "P" if region["space"] == "shared" else region["space"]
        allowed[area].append((region["start"], region["start"] + region["words"]))
    allowed["X"].append((0, 0x100))
    allowed["Y"].append((0, 0x140))
    for area, start, words in records:
        for address in range(start, start + len(words)):
            if not any(lo <= address < hi for lo, hi in allowed[area]):
                die(f"payload {area}:{address:06x} is outside the core-1 layout")
    return records


def write_mem(records: list[tuple[str, int, list[int]]], path: pathlib.Path):
    # Sort only for reproducibility; records remain split at the meaningful
    # allocation boundaries above.
    records = sorted(records, key=lambda item: (SPACE_ID[item[0]], item[1]))
    out = bytearray()
    for space, start, words in records:
        out += struct.pack("<BII", SPACE_ID[space], start, len(words))
        for word in words:
            out += struct.pack("<I", word & 0xFFFFFF)
    out += struct.pack("<BII", 0xFF, 0, 0)
    path.write_bytes(out)
    return records, bytes(out)


def _record_digest(words: list[int]) -> str:
    return sha(b"".join(struct.pack("<I", w & 0xFFFFFF) for w in words))


def build(syx: pathlib.Path | None = None,
          profiles: list[pathlib.Path] | None = None,
          reference: pathlib.Path | None = None):
    profiles = [p.resolve() for p in (profiles or default_profiles())]
    placement = ROOT / "out/machinedrum/plan.json"
    if not placement.exists():
        die(f"placement plan is missing: {placement}")
    OUT.mkdir(parents=True, exist_ok=True)
    SOURCE.mkdir(parents=True, exist_ok=True)
    ns, update, extracted = unpack_update(syx)
    raw, source = source_maps(extracted)
    write_snapshot(source, SOURCE / "snapshot.bin")
    relocation_sha, hot_signature = run_relocator(SOURCE, profiles, placement)
    plan = parse_plan(SOURCE / "reloc.txt")
    relocated = apply_plan(source, plan)
    driver_words, driver_sha = run_driver(SOURCE)
    output_records = build_records(raw, relocated, plan, driver_words)
    output_records, payload_bytes = write_mem(output_records, MEM)
    manifest = {
        "format": 2,
        "core": 1,
        "input": {
            "syx": str(update),
            "syx_sha256": ns["SYX_SHA256"],
            "section_1_DSP.bin_sha256": ns["SECTIONS"]["section_1_DSP.bin"],
        },
        "profiles": [{"path": str(p), "reloc_sha256": file_sha(p / "reloc.txt")}
                     for p in profiles],
        "placement_sha256": file_sha(placement),
        "source_snapshot_sha256": file_sha(SOURCE / "snapshot.bin"),
        "reloc_sha256": relocation_sha,
        "hot_plan_sha256": hot_signature,
        "driver_sha256": driver_sha,
        "driver_words": len(driver_words),
        "records": [{"space": space, "start": start,
                     "words": len(words), "sha256": _record_digest(words)}
                    for space, start, words in output_records],
        "payload_B_mem_sha256": sha(payload_bytes),
        "reloc_counts": {kind: sum(1 for k, _ in plan if k == kind)
                         for kind in sorted({k for k, _ in plan})},
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"wrote    {MEM.relative_to(ROOT)} ({len(payload_bytes):,} bytes)")
    print(f"manifest {MANIFEST.relative_to(ROOT)}")
    return manifest


def read_mem(path: pathlib.Path):
    data = path.read_bytes()
    off, out = 0, []
    while off + 9 <= len(data):
        sp, start, count = struct.unpack_from("<BII", data, off)
        off += 9
        if sp == 0xFF:
            if count or start or off != len(data):
                die(f"bad terminator in {path}")
            return out
        if sp not in SPACE:
            die(f"unknown space {sp} in {path}")
        end = off + count * 4
        if end > len(data):
            die(f"short record in {path}")
        words = list(struct.unpack_from(f"<{count}I", data, off))
        off = end
        out.append((SPACE[sp], start, words))
    die(f"no terminator in {path}")


def verify(path: pathlib.Path = OUT) -> int:
    manifest = json.loads((path / "manifest.json").read_text())
    mem_path = path / "payload_B.mem"
    raw_bytes = mem_path.read_bytes()
    if sha(raw_bytes) != manifest["payload_B_mem_sha256"]:
        die("payload_B.mem hash differs from manifest")
    records = read_mem(mem_path)
    got = [{"space": s, "start": a, "words": len(w),
            "sha256": _record_digest(w)} for s, a, w in records]
    if got != manifest["records"]:
        die("payload_B.mem record map differs from manifest")
    source_path = path / "source/snapshot.bin"
    if file_sha(source_path) != manifest["source_snapshot_sha256"]:
        die("source snapshot hash differs from manifest")
    snap = memoryview(source_path.read_bytes()).cast("I")
    expected = {"P": {}, "X": {}, "Y": {}}
    for address in range(SNAP_X):
        if snap[address]:
            expected["P"][address] = snap[address]
    for area, base in (("X", SNAP_X), ("Y", SNAP_Y)):
        for address in range(0x20000):
            if snap[base + address]:
                expected[area][address] = snap[base + address]
    expected = apply_plan(expected, parse_plan(path / "source/reloc.txt"))
    driver = [int(line, 16) for line in
              (path / "source/driver.bin").read_text().splitlines() if line]
    driver_start = allocation("driver_code")["start"]
    compared = 0
    for area, start, words in records:
        for i, word in enumerate(words):
            address = start + i
            want = (driver[address - driver_start]
                    if area == "P" and driver_start <= address < driver_start + len(driver)
                    else expected[area].get(address, 0))
            if word != want:
                die(f"{area}:{address:06x} differs from source relocation: "
                    f"payload {word:06x}, expected {want:06x}")
            compared += 1
    print(f"PASS: {len(records)} load records, {compared:,} words match "
          "the core-1 relocation")
    print(f"PASS: payload_B.mem sha256 {sha(raw_bytes)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--syx", type=pathlib.Path,
                    help="user's pinned Machinedrum OS update")
    ap.add_argument("--profiles", nargs="+", type=pathlib.Path,
                    help="capture directories containing fetch.txt")
    ap.add_argument("--reference", type=pathlib.Path,
                    help="md_profile snapshot used by the verification")
    ap.add_argument("--verify", action="store_true",
                    help="verify an existing out/machinedrum/build")
    a = ap.parse_args()
    if a.verify:
        return verify()
    build(a.syx, a.profiles)
    return verify()


if __name__ == "__main__":
    raise SystemExit(main())
