"""Build a loader-appended DRAM runtime from its recipe (schema.Runtime).

The recipe is emuyia/ems-octakit's `firmware.json` (interface_version 1),
read from a git submodule. This module implements the OS-image half of her
`build.py` in octabam's shape -- fixed-address writes asserted against stock
before they land, plus an append -- and re-derives every identity her
recipe pins. Toolchain: m68k-elf-gcc/as/ld/objcopy (`make setup`). Her
recipe pins gcc 16.1.0; the rebuilt runtime's sha256 is the check, and
16.2.0 reproduces her bytes (measured). A compiler that does not fails with
both digests in the message.

In order, each step verified against the recipe:
  1. slice Elektron's own routines out of the user's stock image (copied or
     PC-relative-relocated per `stock_operations`) into work/stock/NNNN.bin;
     the `.S` sources `.incbin` them, so the repo carries none of them;
  2. assemble/compile every listed source, link with her linker script,
     extract `.runtime`  -> must match `append.runtime.raw`;
  3. pack it with the firmware's own aPLib variant (her encoder, ported
     below, deterministic)  -> must match `append.runtime.packed`;
  4. link again with the packed blob and its rolling hash, extract
     `.early`+`.stage`  -> must match `append` (loader + stage + runtime);
  5. hand the caller the sparse writes (each guard's sha256 checked against
     stock, each write's expect bytes taken from stock) and the append.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]

# The build's memo. Every entry is keyed by the sha256 of its COMPLETE input
# (the bytes handed to the packer; the recipe, every source file, the stock
# image, the toolchain version for a runtime) and holds bytes the recipe or
# the packer's own determinism pins, so a hit is what a cold run would have
# produced, and a runtime hit is re-verified against the recipe's identities
# before it is used. A build that cannot write here builds cold.
# OCTABAM_NO_CACHE=1 builds cold; OCTABAM_CACHE=<dir> names the directory
# (check_shards.py hands its worktrees the parent's). (28 Sep 2026: the
# packer was 55% of every build and the runtime's 75 compiles another 22%,
# with identical inputs on every one of the ~8 builds a `make check-remix`
# runs; a warm build is 1.7 s where a cold one was 9.)
CACHE = pathlib.Path(os.environ.get("OCTABAM_CACHE") or ROOT / "out/cache")


def _cache_on():
    return os.environ.get("OCTABAM_NO_CACHE", "") not in ("1", "yes", "true")


def _cache_read(kind, key):
    if not _cache_on():
        return None
    p = CACHE / kind / key
    try:
        return p.read_bytes() if p.is_file() else None
    except OSError:
        return None


def _cache_write(kind, key, data):
    if not _cache_on():
        return
    try:
        d = CACHE / kind
        d.mkdir(parents=True, exist_ok=True)
        tmp = d / f"{key}.{os.getpid()}.tmp"
        tmp.write_bytes(data)
        tmp.replace(d / key)
    except OSError:
        pass

TOOLS = ("m68k-elf-gcc", "m68k-elf-as", "m68k-elf-ld", "m68k-elf-objcopy")

# ---- her packer: the firmware's aPLib variant, ported from patcher/src/lib.rs
MAX_OFFSET_FOR_LEN2 = 0x0D00
MAX_MATCH_LEN = 0x8000
HASH3_BITS = 20
HASH3_SIZE = 1 << HASH3_BITS
HASH3_MASK = HASH3_SIZE - 1
HASH2_SIZE = 1 << 16
PACKED_MAGIC = b"GKA3"


def _hash3(b, i):
    key = (b[i] << 16) | (b[i + 1] << 8) | b[i + 2]
    return ((key * 2654435761) & 0xFFFFFFFF) >> (32 - HASH3_BITS) & HASH3_MASK


def _hash2(b, i):
    return (b[i] << 8) | b[i + 1]


def _match_length(data, cand, pos):
    offset = pos - cand
    limit = min(len(data) - pos, MAX_MATCH_LEN)
    direct = min(offset, limit)
    n = 0
    while n < direct and data[cand + n] == data[pos + n]:
        n += 1
    if n == direct and n < limit:
        while n < limit and data[cand + (n % offset)] == data[pos + n]:
            n += 1
    return n


def _greedy_parse(data, max_candidates):
    if not data:
        return []
    head3 = [-1] * HASH3_SIZE
    head2 = [-1] * HASH2_SIZE
    chain3 = [-1] * len(data)
    chain2 = [-1] * len(data)
    ops = []
    pos = 0
    n = len(data)
    while pos < n:
        best_off = best_len = 0
        if pos + 2 < n:
            cand = head3[_hash3(data, pos)]
            tried = 0
            while cand >= 0 and tried < max_candidates:
                off = pos - cand
                length = _match_length(data, cand, pos)
                minimum = 3 if off > MAX_OFFSET_FOR_LEN2 else 2
                if length >= minimum and length > best_len:
                    best_off, best_len = off, length
                    if best_len == MAX_MATCH_LEN:
                        break
                cand = chain3[cand]
                tried += 1
        if best_len < 2 and pos + 1 < n:
            cand = head2[_hash2(data, pos)]
            if cand >= 0 and pos - cand <= MAX_OFFSET_FOR_LEN2:
                best_off, best_len = pos - cand, 2
        if best_len >= 2:
            ops.append((best_off, best_len))
            advance = best_len
        else:
            ops.append(data[pos])
            advance = 1
        end = pos + advance
        while pos < end:
            if pos + 1 < n:
                k = _hash2(data, pos); chain2[pos] = head2[k]; head2[k] = pos
            if pos + 2 < n:
                k = _hash3(data, pos); chain3[pos] = head3[k]; head3[k] = pos
            pos += 1
    return ops


def _gamma_bits(value):
    assert value >= 2
    highest = value.bit_length() - 1
    bits = []
    for i in range(highest - 1, -1, -1):
        bits.append((value >> i) & 1)
        bits.append(1 if i == 0 else 0)
    return bits


def _length_bits(length_read):
    if length_read == 1:
        return [0, 1]
    if length_read == 2:
        return [1, 0]
    if length_read == 3:
        return [1, 1]
    assert length_read > 3
    return [0, 0] + _gamma_bits(length_read - 2)


def pack(data: bytes, max_candidates: int) -> bytes:
    """Deterministic aPLib-variant stream, bit-identical to her encoder.
    Memoised on the input's sha256 (out/cache/pack): the same bytes pack to
    the same stream, and the greedy parse is pure Python."""
    key = f"{hashlib.sha256(data).hexdigest()}-{max_candidates}"
    hit = _cache_read("pack", key)
    if hit is not None and hit[:32] == hashlib.sha256(hit[32:]).digest():
        return hit[32:]
    out = _pack(data, max_candidates)
    _cache_write("pack", key, hashlib.sha256(out).digest() + out)
    return out


def _pack(data: bytes, max_candidates: int) -> bytes:
    tag_bits: list[int] = []
    emissions: list[tuple[int, int]] = []
    last_offset = None
    for op in _greedy_parse(data, max_candidates):
        if isinstance(op, int):
            tag_bits.append(1)
            emissions.append((len(tag_bits) - 1, op))
            continue
        offset, length = op
        tag_bits.append(0)
        if last_offset == offset:
            tag_bits.extend(_gamma_bits(2))
        else:
            raw = offset - 1
            tag_bits.extend(_gamma_bits((raw + 0x300) // 0x100))
            emissions.append((len(tag_bits) - 1, (raw + 0x300) % 0x100))
        tag_bits.extend(_length_bits(length - (2 if offset > MAX_OFFSET_FOR_LEN2 else 1)))
        last_offset = offset
    tag_bits.append(0)
    tag_bits.extend(_gamma_bits(0x01000002))
    emissions.append((len(tag_bits) - 1, 0xFF))
    while len(tag_bits) % 8:
        tag_bits.append(0)
    out = bytearray()
    ei = 0
    for g in range(0, len(tag_bits), 8):
        tag = 0
        for i in range(8):
            tag |= tag_bits[g + i] << (7 - i)
        out.append(tag)
        while ei < len(emissions) and emissions[ei][0] < g + 8:
            out.append(emissions[ei][1])
            ei += 1
    assert ei == len(emissions)
    return bytes(out)


# ---- the recipe ----------------------------------------------------------

def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _verify(label: str, data: bytes, ident: dict) -> None:
    got = {"size": len(data), "sha256": _sha(data)}
    want = {"size": ident["size"], "sha256": ident["sha256"]}
    if got != want:
        sys.exit(f"runtime build: {label} differs from the recipe --\n"
                 f"  got  {got['size']} B {got['sha256']}\n"
                 f"  want {want['size']} B {want['sha256']}")


def extract_stock(stock: bytes, op: dict, load: int, runtime_load: int) -> bytes:
    """One of Elektron's own routines, copied or relocated into the runtime."""
    start, length = op["source_offset"], op["source_length"]
    src = stock[start:start + length]
    if op["kind"] == "stock-copy":
        out = src
    elif op["kind"] == "m68k-relocate":
        lengths = op["instruction_lengths"]
        policy = op["policy"]
        if sum(lengths) != length or any(n <= 0 or n % 2 for n in lengths):
            sys.exit("runtime build: invalid instruction relocation in recipe")
        buf = bytearray()
        cur = 0
        for n in lengths:
            ins = src[cur:cur + n]
            opcode = int.from_bytes(ins[:2], "big")
            if policy == "preserve-absolute-control-flow" and n == 4 and opcode in (0x4EBA, 0x4EFA):
                absolute = load + start + cur + 2 + int.from_bytes(ins[2:], "big", signed=True)
                disp = absolute - (runtime_load + op["target_offset"] + len(buf) + 2)
                if -32768 <= disp <= 32767:
                    buf += ins[:2] + disp.to_bytes(2, "big", signed=True)
                else:
                    buf += (0x4EB9 if opcode == 0x4EBA else 0x4EF9).to_bytes(2, "big")
                    buf += absolute.to_bytes(4, "big")
            else:
                buf += ins
            cur += n
        out = bytes(buf)
    else:
        sys.exit(f"runtime build: unsupported stock operation {op['kind']!r}")
    if len(out) != op["target_length"]:
        sys.exit("runtime build: stock extraction length differs from the recipe")
    return out


def writes(spec: dict, stock: bytes, skip=()) -> list[tuple[int, bytes, bytes, str]]:
    """(vaddr, expect, write, name): every sparse write, with its guard's
    sha256 checked against STOCK and expect taken from stock -- the same
    assert-before-write discipline as a CavePatch poke. `skip` names
    patches the build computes itself (the arena geometry a module's
    ArenaReserve declares); their guards are still checked."""
    base = spec["format"]["os_load_address"]
    out = []
    prev_end = 0
    for p in sorted(spec["patches"], key=lambda p: p["offset"]):
        s, e = p["offset"], p["offset"] + p["length"]
        if s < prev_end or e <= s or e > len(stock):
            sys.exit(f"runtime build: guard {p['name']} overlaps or exceeds the image")
        if _sha(stock[s:e]) != p["sha256"]:
            sys.exit(f"runtime build: guard {p['name']} at 0x{base + s:08x} is not stock")
        prev_end = e
        if p["name"] in skip:
            continue
        wend = s
        for w in p["writes"]:
            data = bytes.fromhex(w["data"])
            pos = w["offset"]
            if not data or pos < wend or pos + len(data) > e:
                sys.exit(f"runtime build: write in {p['name']} exceeds its guard")
            expect = stock[pos:pos + len(data)]
            if any(a == b for a, b in zip(expect, data)):
                sys.exit(f"runtime build: write in {p['name']} keeps an unchanged stock byte")
            out.append((base + pos, expect, data, p["name"]))
            wend = pos + len(data)
    return out


def _run(args, cwd):
    r = subprocess.run([str(a) for a in args], cwd=cwd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"runtime build: {args[0]} failed on {args[-1]}\n{r.stderr[-3000:]}")
    return r.stdout


def build(rt, stock: bytes, work: pathlib.Path, skip=()) -> tuple[list, bytes, dict]:
    """Returns (writes, append, info). `info` carries the identities and
    the gcc version actually used, for the build report."""
    missing = [t for t in TOOLS if not shutil.which(t)]
    if missing:
        sys.exit(f"runtime build: missing {', '.join(missing)} -- run `make setup` "
                 f"(Homebrew: brew install m68k-elf-gcc)")
    recipe = ROOT / rt.recipe
    srcdir = ROOT / rt.sources
    spec = json.loads(recipe.read_text())
    if spec.get("interface_version") != 1:
        sys.exit(f"runtime build: {recipe} interface_version "
                 f"{spec.get('interface_version')!r}, this builder speaks 1")
    _verify("stock OS", stock, spec["source"]["os"])
    load = spec["format"]["os_load_address"]
    runtime_spec = spec["append"]["runtime"]
    runtime_load = runtime_spec["load_address"]

    work = work.resolve()          # every tool runs with cwd=work
    work.mkdir(parents=True, exist_ok=True)
    (work / "stock").mkdir(exist_ok=True)
    for i, op in enumerate(runtime_spec["stock_operations"]):
        (work / "stock" / f"{i:04d}.bin").write_bytes(extract_stock(stock, op, load, runtime_load))

    gcc_version = _run(["m68k-elf-gcc", "-dumpfullversion"], work).strip()

    # The memo key: the recipe, every file under her sources, the stock
    # image, the compiler and the skipped guards. A hit hands back the three
    # artifacts and the symbol table, each re-verified against the recipe's
    # own identities (raw, packed, append) -- the same checks a cold build
    # passes -- and writes the work files the DRAM boot gate reads.
    h = hashlib.sha256()
    h.update(recipe.read_bytes())
    for f in sorted(x for x in srcdir.rglob("*") if x.is_file() and ".git" not in x.parts):
        h.update(str(f.relative_to(srcdir)).encode()); h.update(b"\0"); h.update(f.read_bytes())
    h.update(_sha(stock).encode()); h.update(gcc_version.encode()); h.update(repr(sorted(skip)).encode())
    cache_key = h.hexdigest()
    hit = _cache_read("runtime", cache_key)
    if hit is not None:
        try:
            c = json.loads(hit)
            runtime, packed, append = (bytes.fromhex(c[k]) for k in ("runtime", "packed", "append"))
            symbols = c["symbols"]
        except (ValueError, KeyError, TypeError):
            hit = None
    if hit is not None:
        _verify(f"cached runtime (m68k-elf-gcc {gcc_version})", runtime, runtime_spec["raw"])
        _verify("cached packed runtime", packed, runtime_spec["packed"])
        _verify("cached append", append, {"size": spec["append"]["length"], "sha256": spec["append"]["sha256"]})
        (work / "runtime.bin").write_bytes(runtime)
        (work / "packed.bin").write_bytes(packed)
        (work / "append.bin").write_bytes(append)
        return _result(spec, stock, skip, gcc_version, runtime, packed, append, symbols, runtime_load)

    def compile_one(src, obj):
        if src.suffix == ".c":
            _run(["m68k-elf-gcc", *spec["compiler"]["cflags"], "-c", "-o", obj, src], work)
        else:
            _run(["m68k-elf-as", "-march=cfv4e", "-I", srcdir, "-I", src.parent, "-o", obj, src], work)

    objects = []
    for name in spec["sources"]:
        src = srcdir / name
        if pathlib.Path(name).name != name or src.suffix not in (".S", ".c") or not src.exists():
            sys.exit(f"runtime build: bad source {name!r} in {recipe}")
        obj = work / (src.stem + ".o")
        compile_one(src, obj)
        objects.append(obj)
    ldscript = srcdir / "link.ld"
    ld = ["m68k-elf-ld", "-T", ldscript]
    elf, raw = work / "runtime.elf", work / "runtime.bin"
    _run([*ld, "--defsym", "GK_PACKED_RUNTIME_HASH=0", "-o", elf, *objects], work)
    _run(["m68k-elf-objcopy", "-O", "binary", "-j", ".runtime", elf, raw], work)
    runtime = raw.read_bytes()
    _verify(f"rebuilt runtime (m68k-elf-gcc {gcc_version}, recipe pins "
                f"{spec['compiler']['gcc_version']})", runtime, runtime_spec["raw"])
    for op in runtime_spec["stock_operations"]:
        s = op["target_offset"]
        if runtime[s:s + op["target_length"]] != extract_stock(stock, op, load, runtime_load):
            sys.exit("runtime build: a stock routine inside the runtime differs from its slice")

    packed = PACKED_MAGIC + len(runtime).to_bytes(4, "big") + pack(runtime, spec["build"]["max_candidates"])
    _verify("packed runtime", packed, runtime_spec["packed"])
    packed_path = work / "packed.bin"
    packed_path.write_bytes(packed)
    packed_obj = work / "packed.o"
    _run(["m68k-elf-objcopy", "-I", "binary", "-O", "elf32-m68k", "-B", "m68k",
          "--rename-section", ".data=.stage.packed,alloc,load,readonly,data,contents",
          packed_path, packed_obj], work)
    rolling = 0
    for b in packed:
        rolling = (rolling * 33 + b) & 0xFFFFFFFF
    _run([*ld, "--defsym", f"GK_PACKED_RUNTIME_HASH={rolling}", "-o", elf, *objects, packed_obj], work)
    append_path = work / "append.bin"
    _run(["m68k-elf-objcopy", "-O", "binary", "-j", ".early", "-j", ".stage", elf, append_path], work)
    append = append_path.read_bytes()
    _verify("append (loader + stage + packed runtime)", append,
            {"size": spec["append"]["length"], "sha256": spec["append"]["sha256"]})
    if spec["append"]["offset"] != len(stock):
        sys.exit("runtime build: the recipe appends somewhere other than the end of the image")

    symbols = {}
    for line in _run(["m68k-elf-nm", "--defined-only", elf], work).splitlines():
        f = line.split()
        if len(f) == 3 and not f[2].startswith(".L"):
            symbols[f[2]] = int(f[0], 16)
    _cache_write("runtime", cache_key, json.dumps(dict(
        runtime=runtime.hex(), packed=packed.hex(), append=append.hex(), symbols=symbols)).encode())
    return _result(spec, stock, skip, gcc_version, runtime, packed, append, symbols, runtime_load)


def _result(spec, stock, skip, gcc_version, runtime, packed, append, symbols, runtime_load):
    """(writes, append, info) from the built or cached artifacts."""
    ws = writes(spec, stock, skip)
    def _roll(b):
        h = 0
        for x in b:
            h = (h * 33 + x) & 0xFFFFFFFF
        return h
    info = dict(gcc=gcc_version, gcc_pinned=spec["compiler"]["gcc_version"],
                runtime_size=len(runtime), packed_size=len(packed), append_size=len(append),
                runtime_load=runtime_load, memory=spec.get("memory"), symbols=symbols,
                output_os=spec["output"]["os"], id=spec["id"], version=spec["build"]["version"],
                # what octabam's loader needs to carry this runtime as a PAYLOAD:
                # her stage (signature + GKA3 stream, exactly her .stage section,
                # where her post-clear relocation re-depacks from), her window,
                # her backup, and the x33 hashes her OS-resident helpers gate on
                payload=dict(name=spec["id"],
                             blob=append[len(append) - len(packed) - 4:],
                             stage=symbols["__gk_stage_uncached_start"],
                             dst=symbols["__gk_runtime_uncached_start"],
                             rawlen=len(runtime), rhash=_roll(runtime),
                             backup=symbols["__gk_runtime_backup_uncached_start"],
                             symbols=symbols))
    return ws, append, info
