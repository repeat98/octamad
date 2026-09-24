#!/usr/bin/env python3
"""Build the Machinedrum core-0 DSP payload from the user's OS update.

The update is an input, never a repository asset.  This builder unpacks the
pinned SysEx through ``modules/machinedrum/extraction.py``, constructs the
same sparse P/X/Y view used by ``md_replay``, asks the layout-driven
relocator for a plan, and writes only ignored files below
``out/machinedrum/build``:

* ``payload_A.mem`` is a flat DSP load-record dump;
* ``source/reloc.txt`` is the relocator's auditable plan;
* ``source/driver.bin`` is the assembled OT-side driver; and
* ``manifest.json`` records the input and generated identities.

The native dispatcher hook is deliberately not part of this packet (that is
WP-B3).  The result is therefore a payload build and dump, not a flashable
OS image.  ``tools/verify/verify_md_payload.py`` compares its relocated P
words with the words ``md_replay`` would have after applying the same plan.
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
MEM = OUT / "payload_A.mem"
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
    # These are the six complete, all-engine cap-4 fetch profiles used by the
    # overnight measurement.  cap-5 includes the c40 crash/partial fetch, so
    # it is never silently folded into the hot-unit choice.
    profiles = sorted((ROOT / "out/md_profile/cap4").glob("*/fetch.txt"))
    if not profiles:
        die("no cap4 fetch profiles; pass --profiles explicitly")
    return [p.parent for p in profiles]


def hot_plan_signature(path: pathlib.Path) -> str:
    hot = allocation("hot_code")
    lines = []
    for line in path.read_text().splitlines():
        parts = line.split()
        if len(parts) != 4 or parts[0] != "M":
            continue
        start, end, new = (int(v, 16) for v in parts[1:])
        if hot["start"] <= new < hot["start"] + hot["words"]:
            lines.append(f"M {start:06x} {end:06x} {new:06x}")
    if not lines:
        die(f"hot plan has no units in {path}")
    return sha(("\n".join(lines) + "\n").encode())


def run_relocator(source: pathlib.Path, profiles: list[pathlib.Path]) -> tuple[str, str]:
    plans = [p / "reloc.txt" for p in profiles]
    missing = [p for p in plans if not p.exists()]
    if missing:
        die("profile(s) have no measured reloc.txt hot plan: "
            + ", ".join(map(str, missing)))
    signatures = {hot_plan_signature(p) for p in plans}
    if len(signatures) != 1:
        die("the twelve-kit hot plans disagree: " + ", ".join(sorted(signatures)))
    hot_signature = next(iter(signatures))
    command = [sys.executable, str(RELOCATOR), "--hot-plan", str(plans[0]),
               str(source)]
    result = subprocess.run(command, cwd=ROOT, text=True,
                            capture_output=True)
    if result.stdout:
        print(result.stdout, end="")
    if result.returncode:
        die(f"relocator failed (exit {result.returncode})\n{result.stderr}")
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")
    return file_sha(source / "reloc.txt"), hot_signature


def run_driver(source: pathlib.Path) -> tuple[list[int], str]:
    command = [sys.executable, str(DRIVER), str(source), "--reloc",
               "--org", "0x3fe00"]
    result = subprocess.run(command, cwd=ROOT, text=True,
                            capture_output=True)
    if result.stdout:
        print(result.stdout, end="")
    if result.returncode:
        die(f"driver assembler failed (exit {result.returncode})\n{result.stderr}")
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")
    words = [int(line, 16) for line in
             (source / "driver.bin").read_text().splitlines() if line]
    return words, file_sha(source / "driver.bin")


def parse_plan(path: pathlib.Path) -> list[tuple[str, tuple[int, ...]]]:
    out = []
    for line in path.read_text().splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        kind = parts[0]
        try:
            if kind == "Q":
                if len(parts) != 5 or parts[1] not in ("X", "Y"):
                    die(f"bad Q relocation line {line!r}")
                values = (0 if parts[1] == "X" else 1,
                          *(int(v, 16) for v in parts[2:]))
            else:
                values = tuple(int(v, 16) for v in parts[1:])
            out.append((kind, values))
        except ValueError as exc:
            die(f"bad reloc line {line!r}: {exc}")
    return out


def apply_plan(original: dict[str, dict[int, int]],
               plan: list[tuple[str, tuple[int, ...]]]):
    """Apply the same operations and ordering as md_replay.cpp.

    Missing source words are zero in the generated sparse view.  ``Z`` is
    represented as zero here, because it is a poison operation in the replay
    harness, not a word that belongs in a load record.
    """
    mem = {space: dict(words) for space, words in original.items()}
    for kind, values in plan:
        if kind == "M":
            start, end, new = values
            words = [mem["P"].get(start + i, 0)
                     for i in range(end - start)]
            for i, word in enumerate(words):
                mem["P"][new + i] = word
        elif kind == "Z":
            start, end = values
            for address in range(start, end):
                mem["P"][address] = 0
        elif kind == "Q":
            area, start, end, new = values
            name = "X" if area == 0 else "Y"
            words = [mem[name].get(start + i, 0)
                     for i in range(end - start)]
            for i, word in enumerate(words):
                mem[name][new + i] = word
            for address in range(start, end):
                mem[name][address] = 0
        elif kind == "I":
            start, end = values
            for i in range(end - start):
                mem["P"][start + i] = original["P"].get(0x135600 + i, 0)
        elif kind == "V":
            old, new = values
            mem["Y"][new] = mem["Y"].get(old, 0)
            mem["Y"][old] = 0
        elif kind == "W":
            address, word = values
            mem["P"][address] = word
        elif kind in ("X", "Y"):
            address, word = values
            mem[kind][address] = word
        else:
            die(f"unknown relocation directive {kind!r}")
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


def validate_proposed_layout(raw: dict[str, dict[int, int]], plan) -> None:
    """Refuse to emit a payload while A2's source/window split is unresolved.

    The relocation used by the replay proof is intentionally a broad test
    placement.  A2's proposed map gives the same destination to the sine
    initializer, so treating that test placement as a loadable payload would
    overwrite the relocated engine/table span.  Keep this guard before any
    payload or manifest is written; the layout decision belongs in the packet
    report, not in an implicit build policy.
    """
    sine = allocation("sine")
    sine_lo, sine_hi = sine["start"], sine["start"] + sine["words"]
    blockers = []
    external_loaded = {
        address for values in raw.values() for address in values
        if EXTERNAL_LO <= address < EXTERNAL_HI
    }
    for kind, values in plan:
        if kind != "M":
            continue
        start, end, new = values
        if (start, end) == (EXTERNAL_LO, EXTERNAL_HI):
            if (new < sine_hi and
                    new + (end - start) > sine_lo):
                # This is the current map's exact full-span collision.  Keep
                # the wording explicit so a future layout change can remove
                # the guard for the right reason.
                blockers.append(
                    f"M {start:06x}..{end:06x} -> {new:06x} places "
                    f"{len(external_loaded):,} source-loaded external words "
                    f"in the sine allocation {sine_lo:06x}..{sine_hi:06x}; "
                    "the relocated init writes all 0x8000 sine words there"
                )
    if blockers:
        print("layout audit: proposed A2 map is not yet an emit-safe B2 map")
        for blocker in blockers:
            print(f"  BLOCKED: {blocker}")
        print("  BLOCKED: the source-space alias/load policy for the external "
              "Y descriptor span must be resolved with the A2 layout sign-off")
        die("no payload written; move the source code/tables into the "
            "window allocation (or revise layout.py) before B2 can pass")


def build_records(raw: dict[str, dict[int, int]], relocated, plan,
                  driver_words: list[int]):
    hot = allocation("hot_code")
    sine = allocation("sine")
    window = allocation("window_code_tables")
    pi = allocation("pi_buffers")
    driver = allocation("driver_code")
    voice_x = allocation("voice_x")
    voice_y = allocation("voice_y_records")
    loop = allocation("loop_words")

    records: list[tuple[str, int, list[int]]] = []

    # md_relocate emits one M per chosen hot unit, after the two broad region
    # moves.  Keep those as separate records: they are the proof that the
    # donor region is made of moved code, not a copied firmware blob.
    hot_moves = [(new, new + (end - start))
                 for kind, values in plan if kind == "M"
                 for start, end, new in [values]
                 if hot["start"] <= new < hot["start"] + hot["words"]]
    if not hot_moves:
        die("relocator selected no hot units for payload-A donor space")
    for start, end in hot_moves:
        if end > hot["start"] + hot["words"]:
            die("hot unit exceeds layout hot_code allocation")
        records.append(("P", start, range_words(relocated, "P", start, end)))

    # These are exact layout allocations.  They are load records rather than
    # a raw image copy, and the hot ranges above have already been zeroed in
    # this post-relocation view.
    for region, space in ((sine, "P"), (window, "P"), (pi, "P")):
        start = region["start"]
        records.append((space, start,
                        range_words(relocated, space, start,
                                    start + region["words"])))

    if len(driver_words) > driver["words"]:
        die(f"driver is {len(driver_words)} words, larger than its "
            f"{driver['words']}-word allocation")
    records.append(("P", driver["start"], driver_words))

    # Keep the update's internal X/Y initialization records (the external
    # aliases were merged into the relocated P sine view), then add the
    # relocated voice and loop state ranges used by the driver.
    for space in ("X", "Y"):
        for start, end in contiguous_ranges({a for a in raw[space]
                                             if a < 0x10000}):
            records.append((space, start,
                            range_words(relocated, space, start, end)))
    records.append(("X", voice_x["start"], range_words(
        relocated, "X", voice_x["start"], voice_x["start"] + voice_x["words"])))
    records.append(("Y", voice_y["start"], range_words(
        relocated, "Y", voice_y["start"], voice_y["start"] + voice_y["words"])))
    records.append(("Y", loop["start"], range_words(
        relocated, "Y", loop["start"], loop["start"] + loop["words"])))

    # Check every record against the three independent address spaces before
    # writing it.  This catches an accidental overlap in the output format as
    # well as a stale layout allocation.
    occupied = defaultdict(dict)
    for space, start, words in records:
        for i, word in enumerate(words):
            address = start + i
            previous = occupied[space].get(address)
            if previous is not None and previous != (word & 0xFFFFFF):
                die(f"output {space}:{address:06x} has conflicting records")
            occupied[space][address] = word & 0xFFFFFF
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
    profiles = profiles or default_profiles()
    profiles = [p.resolve() for p in profiles]
    missing = [p for p in profiles
               if not (p / "fetch.txt").exists() or not (p / "reloc.txt").exists()]
    if missing:
        die("profile(s) have no fetch.txt and measured reloc.txt: "
            + ", ".join(map(str, missing)))
    OUT.mkdir(parents=True, exist_ok=True)
    SOURCE.mkdir(parents=True, exist_ok=True)

    ns, update, records = unpack_update(syx)
    raw, source = source_maps(records)
    write_snapshot(source, SOURCE / "snapshot.bin")
    relocation_sha, hot_signature = run_relocator(SOURCE, profiles)
    plan = parse_plan(SOURCE / "reloc.txt")
    relocated = apply_plan(source, plan)
    driver_words, driver_sha = run_driver(SOURCE)
    validate_proposed_layout(raw, plan)
    output_records = build_records(raw, relocated, plan, driver_words)
    output_records, payload_bytes = write_mem(output_records, MEM)

    if reference is None:
        reference = profiles[0] / "snapshot.bin"
    reference = reference.resolve()
    if not reference.exists():
        die(f"reference snapshot does not exist: {reference}")

    manifest = {
        "format": 1,
        "input": {
            "syx": str(update),
            "syx_sha256": ns["SYX_SHA256"],
            "section_1_DSP.bin_sha256": ns["SECTIONS"]["section_1_DSP.bin"],
        },
        "profiles": [{"path": str(p), "fetch_sha256": file_sha(p / "fetch.txt")}
                     for p in profiles],
        "reference_snapshot": str(reference),
        "reloc_sha256": relocation_sha,
        "hot_plan_sha256": hot_signature,
        "driver_sha256": driver_sha,
        "driver_words": len(driver_words),
        "records": [{"space": space, "start": start,
                     "words": len(words), "sha256": _record_digest(words)}
                    for space, start, words in output_records],
        "payload_A_mem_sha256": sha(payload_bytes),
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
    mem_path = path / "payload_A.mem"
    raw_bytes = mem_path.read_bytes()
    if sha(raw_bytes) != manifest["payload_A_mem_sha256"]:
        die("payload_A.mem hash differs from manifest")
    records = read_mem(mem_path)
    got = [{"space": s, "start": a, "words": len(w),
            "sha256": _record_digest(w)} for s, a, w in records]
    if got != manifest["records"]:
        die("payload_A.mem record map differs from manifest")

    # The reference snapshot is the exact input md_replay loads.  Applying
    # the generated reloc.txt here mirrors md_replay.cpp's M/Z/W/I handling;
    # the comparison is therefore against relocated words, not just against
    # a self-authored output hash.
    reference = pathlib.Path(manifest["reference_snapshot"])
    if not reference.exists():
        die(f"reference snapshot is missing: {reference}")
    snap = list(array.array("I", reference.read_bytes()))
    expected = {"P": {}, "X": {}, "Y": {}}
    for address in range(SNAP_X):
        expected["P"][address] = snap[address]
    for area, base in (("X", SNAP_X), ("Y", SNAP_Y)):
        for address in range(0x20000):
            expected[area][address] = snap[base + address]
    plan = parse_plan(path / "source/reloc.txt")
    expected = apply_plan(expected, plan)

    compared = 0
    for space, start, words in records:
        if space != "P":
            continue
        for i, word in enumerate(words):
            address = start + i
            if expected["P"].get(address, 0) != word:
                die(f"P:{address:06x} differs from md_replay relocation: "
                    f"payload {word:06x}, reference "
                    f"{expected['P'].get(address, 0):06x}")
            compared += 1
    print(f"PASS: {len(records)} load records, {compared:,} P words match "
          "md_replay's relocated view")
    print(f"PASS: payload_A.mem sha256 {sha(raw_bytes)}")
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
    build(a.syx, a.profiles, a.reference)
    return verify()


if __name__ == "__main__":
    raise SystemExit(main())
