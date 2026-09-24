#!/usr/bin/env python3
"""Generate a relocated MD handler unit from the user's pinned OS at build time.

Only assembly directives are generated. Code and table bytes remain in the
user's extracted image and are read by GNU as. Absolute table operands become
linker expressions; every other code byte is copied unchanged.
"""

from collections import defaultdict
from pathlib import Path
import argparse
import hashlib
import sys

import extraction

ROOT = Path(__file__).resolve().parents[2]
SOURCE = extraction.OUT / "section_0_MAIN_OS.bin"
CODE = (0x201128, 0x204330)  # GND--- through the last P-I-HH RTS
SRAM_WORD = 0x0100150c  # E12 pitch divisor in the MD internal SRAM
TABLES = ((0x2462e8, 0x246ae8), (0x24bb90, 0x24e000))
TARGETS = frozenset((0x2462e8, 0x2464e8, 0x2466e8, 0x2468e8,
                     0x24bb90, 0x24bd94, 0x24bf94, 0x24c048,
                     0x24c19c, 0x24c794, 0x24cc44, 0x24d794,
                     0x24da14, SRAM_WORD))
# LEA abs.l, MOVE.L abs.l, and ADDA.L #imm are the only forms used here.
OPERANDS = frozenset((0x41f9, 0x43f9, 0x47f9, 0x2839,
                      0x2239, 0x2439, 0x2639, 0xd1fc))
EXPECTED_RELOCS = 148
FAMILIES = frozenset(("GND", "TRX", "EFM", "E12", "P-I"))


def image() -> bytes:
    syx = extraction.find_syx(None)
    if extraction.sha(syx) != extraction.SYX_SHA256:
        raise ValueError("user MD OS update differs from pinned OS 1.63")
    if not SOURCE.exists():
        extraction.unpack(syx)
    if extraction.sha(SOURCE) != extraction.SECTIONS[SOURCE.name]:
        raise ValueError("extracted MD MAIN OS differs from pinned OS 1.63")
    return SOURCE.read_bytes()


def relocations(img: bytes) -> dict[int, int]:
    out = {}
    for addr in range(CODE[0] + 2, CODE[1] - 3, 2):
        off = addr - extraction.OS_BASE
        val = int.from_bytes(img[off:off + 4], "big")
        if val not in TARGETS:
            continue
        op = int.from_bytes(img[off - 2:off], "big")
        if op not in OPERANDS:
            raise ValueError(f"unexpected MD table operand at {addr:#x}: {op:#x}")
        out[addr] = val
    if len(out) != EXPECTED_RELOCS:
        raise ValueError(f"MD handler relocation count {len(out)}, expected {EXPECTED_RELOCS}")
    return out


# The MD's live handler for machine id i is the first long of the
# descriptor that 0x252092[i] points at (0x206b1a, machine assignment).
# It equals the descriptor table's handler for every playable id except
# TRX-S2, which MD OS 1.63 runs on the empty handler (two words: the trig
# and a stale word; measured in capture c1d_16).
LIVE_TABLE = 0x252092
ENGINE_IDS = 0x49
FAMILY_CODE = {"GND": 1, "TRX": 2, "EFM": 3, "E12": 4, "P-I": 5}
# The OT image renders every family but E12, whose samples are not on the
# OT DSP (WP-R1); an E12 id in a kit plays as GND--- (silent).
PLAYABLE = frozenset(("GND", "TRX", "EFM", "P-I"))


def engine_table(img: bytes, engines) -> list[str]:
    """md_engines (md_ctl.h MdEngine, 48 bytes a row, ids 0x00..0x48):
    live handler, eight defaults, eight 4-character names, flags, family."""
    def long_at(addr):
        off = addr - extraction.OS_BASE
        return int.from_bytes(img[off:off + 4], "big")
    label = {CODE[0]: "md_handler_empty"}
    for e in engines:
        label.setdefault(e["handler"], f"md_handler_{e['id']:02x}")
    by_id = {e["id"]: e for e in extraction.engines()}
    out = ["        .balign 4", "        .global md_engines", "md_engines:"]
    for i in range(ENGINE_IDS):
        e = by_id.get(i)
        if e is None or (i and e["family"] not in FAMILY_CODE):
            out.append(f"        .zero 48                | {i:#04x}: no machine")
            continue
        live = long_at(long_at(LIVE_TABLE + 4 * i))
        if live not in label:
            raise ValueError(f"{e['name']} live handler {live:#x} is not a linked entry")
        names = b"".join(n.encode("ascii").ljust(4, b"\0")[:4] for n in e["params"])
        flags = 1 if (i == 0 or e["family"] in PLAYABLE) else 0
        family = FAMILY_CODE.get(e["family"], 0)
        out += [f"        .long {label[live]}          | {i:#04x} {e['name']}",
                "        .byte " + ",".join(str(v) for v in e["defaults"]),
                "        .byte " + ",".join(str(b) for b in names),
                f"        .byte {flags},{family},0,0"]
    return out


def build(dest: Path) -> None:
    img = image()
    engines = [e for e in extraction.engines()
               if e["family"] in FAMILIES and e["name"] != "GND---"]
    if len(engines) != 50 or len({e["handler"] for e in engines}) != 44:
        raise ValueError("MD descriptor handler inventory changed")
    labels = defaultdict(list)
    labels[CODE[0]].append("md_handler_empty")
    for e in engines:
        if not CODE[0] <= e["handler"] < CODE[1]:
            raise ValueError(f"{e['name']} handler outside pinned code slice")
        labels[e["handler"]].append(f"md_handler_{e['id']:02x}")
    refs = relocations(img)
    points = sorted({*labels, *refs})
    lines = ["| Generated by modules/machinedrum/handler_build.py.",
             "| Code and tables come from the user's pinned MD OS at build time.",
             "        .text", "        .balign 4"]
    cursor = CODE[0]
    for p in points:
        if p < cursor:
            raise ValueError(f"overlapping MD relocation or label at {p:#x}")
        if p > cursor:
            lines.append(f'        .incbin "{SOURCE}", {cursor - extraction.OS_BASE}, {p - cursor}')
        for name in labels[p]:
            lines += [f"        .global {name}", f"{name}:"]
        if p in refs:
            target = refs[p]
            if target == SRAM_WORD:
                lines.append("        .long md_handler_sram_word")
            else:
                base = TABLES[0][0] if target < TABLES[1][0] else TABLES[1][0]
                name = "md_table_low" if base == TABLES[0][0] else "md_table_high"
                lines.append(f"        .long {name}+{target - base}")
            cursor = p + 4
        else:
            cursor = p
    if cursor < CODE[1]:
        lines.append(f'        .incbin "{SOURCE}", {cursor - extraction.OS_BASE}, {CODE[1] - cursor}')
    for (lo, hi), name in zip(TABLES, ("md_table_low", "md_table_high")):
        lines += ["        .balign 4", f"{name}:",
                  f'        .incbin "{SOURCE}", {lo - extraction.OS_BASE}, {hi - lo}']
    lines += engine_table(img, engines)
    # WP-C4's producer supplies the source SRAM value before each E12 call.
    # It is a writable long in the DRAM unit, shared by the E12 handlers.
    lines += ["        .balign 4", "        .global md_handler_sram_word",
              "md_handler_sram_word:", "        .long 0"]
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(lines) + "\n")
    print(f"MD handlers: {len(engines)} engines, 44 code entries, "
          f"{len(refs)} relocated table operands, source sha256 "
          f"{hashlib.sha256(img).hexdigest()[:16]}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=ROOT / "out/machinedrum/handlers.s")
    args = ap.parse_args()
    try:
        build(args.out)
    except ValueError as exc:
        sys.exit(str(exc))
