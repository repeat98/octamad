#!/usr/bin/env python3
"""WP-E1: the Machinedrum's kits and patterns load from and save to the card.

Under the ColdFire port (MD_EMU), on OT_PROJECT with T1 signed MD in bank 1:

  1. load: machinedrum.work written here (a known kit in Part 1's kit and a
     known lane and lock in pattern A01) is read at the project load into
     md_kits[0] and md_patterns[0], every other kit empty, every lock of
     every other pattern free; the SRAM block mirrors bank 1;
  2. damaged: the same file with one body byte flipped is refused (the sum),
     the loaded banks are empty and the MD's default kit is on the track;
  3. save (a card octemu wrote, --card): SYNC TO CARD runs stock's bank
     save and the detour after it writes machinedrum.work. The port cannot
     write files from --call (stock's own bank save runs away in its copy
     there, as does the MD writer), and its panel walk did not reach the
     PROJECT menu, so the write is measured in octemu and checked here:
     header, sizes, sum, and the kit and lanes it carries.

Run: MD_EMU=... OT_PROJECT=... python3 tools/verify/verify_md_persist.py
     python3 tools/verify/verify_md_persist.py --card CARD.img "SET/PROJECT"
"""
import os
import pathlib
import struct
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/verify"))
import verify_md_ui as ui

OUT = ROOT / "out/mdverify/persist_gate"
KIT_BYTES, KITS, PATTERN_BYTES, PATTERNS = 192, 64, 384, 256
SRAM = 0x100fa000


def fnv(data, h=2166136261):
    for b in data:
        h = ((h ^ b) * 16777619) & 0xffffffff
    return h


def empty_pattern():
    return bytes(128) + b"".join(bytes((0, 0xff, 0, 0)) for _ in range(64))


def known():
    """Kit 0: part 1 TRX-RS (0x14) VOL 99 PAN 30, SYN 11..18; part 2 TRX-SD.
    Pattern 0: part 1 on steps 1, 5, 9; one lock (step 5, part 1, SYN 3 = 7)."""
    kit = bytearray(KIT_BYTES)
    kit[0:12] = bytes((0x14, 99, 30, 0, *range(11, 19)))
    kit[12:24] = bytes((0x11, 100, 64, 0, *([64] * 8)))
    kits = bytes(kit) + bytes(KIT_BYTES * (KITS - 1))
    pat = bytearray(empty_pattern())
    pat[0:4] = (0x111).to_bytes(4, "big")        # part 1, trig[0][0]: steps 1, 5, 9
    pat[4:8] = (0).to_bytes(4, "big")            # part 1, trig[0][1]: steps 33..64
    pat[128:132] = bytes((4, 0, 2, 7))
    patterns = bytes(pat) + empty_pattern() * (PATTERNS - 1)
    return kits, patterns


def md_file(kits, patterns):
    head = struct.pack(">8I", 0x4d44524d, 1, KIT_BYTES, KITS, PATTERN_BYTES, PATTERNS, 0, 0)
    body = kits + patterns
    return head + body + struct.pack(">I", fnv(body))


def stage_with(source, name, blob):
    fixture, _ = ui.stage(source, name, True)
    (fixture / "machinedrum.work").write_bytes(blob)
    card = ui.OUT / (name + ".img")
    subprocess.run([sys.executable, str(ROOT / "tools/emu/ot_emu/stage_card.py"),
                    str(fixture), "OCTABAM", "RIG", "--tree", str(ui.OUT / (name + "_tree")),
                    "--out", str(card)], check=True, cwd=ROOT, capture_output=True)
    return card


def spans(sym):
    return {"kits": (sym["md_kits"], KIT_BYTES * 4), "pats": (sym["md_patterns"], PATTERN_BYTES * 2),
            "persist": (sym["md_persist"], 32), "sram": (SRAM, 16 + KIT_BYTES)}


def check_card(image, project_dir):
    """Validate machinedrum.work on a FAT card image (the OT's: FAT32 at 1 MiB)."""
    back = OUT / "card_machinedrum.work"
    OUT.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["mcopy", "-n", "-o", "-i", f"{image}@@1M",
                        f"::/{project_dir}/machinedrum.work", str(back)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    got = back.read_bytes()
    body = got[32:-4]
    assert struct.unpack(">6I", got[:24]) == (0x4d44524d, 1, KIT_BYTES, KITS, PATTERN_BYTES, PATTERNS)
    assert len(got) == 32 + KIT_BYTES * KITS + PATTERN_BYTES * PATTERNS + 4, len(got)
    assert fnv(body) == int.from_bytes(got[-4:], "big"), "sum"
    kits = [k for k in range(KITS) if any(body[k * KIT_BYTES:(k + 1) * KIT_BYTES])]
    print(f"card: machinedrum.work {len(got)} bytes, sum sound; non-empty kits {kits}")
    for k in kits[:4]:
        kit = body[k * KIT_BYTES:(k + 1) * KIT_BYTES]
        parts = [f"{kit[12 * p]:02x}/v{kit[12 * p + 1]}/p{kit[12 * p + 2]}" for p in range(16) if kit[12 * p] or kit[12 * p + 1]]
        print(f"  kit {k} (bank {k // 4 + 1} part {k % 4 + 1}): " + " ".join(parts))
    pats = body[KIT_BYTES * KITS:]
    for q in range(PATTERNS):
        pat = pats[q * PATTERN_BYTES:(q + 1) * PATTERN_BYTES]
        lanes = [(p, int.from_bytes(pat[8 * p:8 * p + 4], "big")          # steps 1..32
                  | int.from_bytes(pat[8 * p + 4:8 * p + 8], "big") << 32)  # steps 33..64
                 for p in range(16)]
        lanes = [(p, [s + 1 for s in range(64) if m >> s & 1]) for p, m in lanes if m]
        used = sum(1 for i in range(64) if pat[128 + 4 * i + 1] != 0xff)
        if lanes or used:
            print(f"  pattern {q} (bank {q // 16 + 1} {q % 16 + 1:02d}): lanes {lanes} locks {used}")
    print("verify_md_persist --card: PASS")


def main():
    if len(sys.argv) == 4 and sys.argv[1] == "--card":
        return check_card(sys.argv[2], sys.argv[3])
    project, emu = os.environ.get("OT_PROJECT"), os.environ.get("MD_EMU")
    if not project or not emu:
        raise SystemExit("MD_EMU and OT_PROJECT are required")
    ui.OUT = OUT
    OUT.mkdir(parents=True, exist_ok=True)
    source = pathlib.Path(project)
    if not source.is_absolute():
        source = ROOT / source
    image = ROOT / "out/mainos_bus.bin"
    sym = ui.symbols()
    kits, patterns = known()
    blob = md_file(kits, patterns)

    card = stage_with(source, "good", blob)
    st = ui.run("load", card, emu, image, spans(sym), [(2.0, "quit")])
    ready, bank, pos, project_hash, writes, reads, errors, bad = struct.unpack(">8I", st["persist"])
    assert ready == 1 and reads == 1 and bad == 0, (ready, reads, bad)
    assert st["kits"][:KIT_BYTES] == kits[:KIT_BYTES], st["kits"][:24].hex()
    assert st["kits"][KIT_BYTES:] == bytes(KIT_BYTES * 3)
    assert st["pats"][:PATTERN_BYTES] == patterns[:PATTERN_BYTES], st["pats"][:12].hex()
    assert st["pats"][PATTERN_BYTES:] == empty_pattern()
    magic, sbank, sproj = struct.unpack(">3I", st["sram"][:12])
    assert magic == 0x4d445331 and sbank == 0 and sproj == project_hash, (hex(magic), sbank)
    assert st["sram"][16:] == kits[:KIT_BYTES]
    print("load: machinedrum.work -> kit 0 (TRX-RS, VOL 99, PAN 30), pattern A01 (steps 1/5/9, a lock); SRAM mirrors bank 1")

    damaged = bytearray(blob)
    damaged[32 + 5] ^= 0x40
    card_bad = stage_with(source, "damaged", bytes(damaged))
    st = ui.run("damaged", card_bad, emu, image, spans(sym), [(2.0, "quit")])
    ready, _, _, _, _, reads, _, bad = struct.unpack(">8I", st["persist"])
    assert ready == 1 and reads == 0 and bad == 1, (ready, reads, bad)
    assert st["kits"][0] == 0x10, f"default kit expected, part 1 engine {st['kits'][0]:#x}"
    assert st["pats"][:PATTERN_BYTES] == empty_pattern()
    print("damaged: the sum refuses it; the banks load empty and the MD gets its default kit")

    print("verify_md_persist: PASS")


if __name__ == "__main__":
    main()
