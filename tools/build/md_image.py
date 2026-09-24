#!/usr/bin/env python3
"""The Machinedrum's core-1 integration into an OT image (WP-B2 image side,
WP-B3 dispatcher hook, WP-B4 fixed trigger).

build_bus.py calls integrate() last, when the remix carries MACHINEDRUM,
after every DSP pass has written both payloads. It

  1. assembles modules/machinedrum/md_glue.asm into the window at
     layout.glue (placeholders from layout.py, the payload's reloc.txt and
     the driver's symbols) and disassembles it (dsp_asm has mis-encoded
     forms before, CLAUDE.md);
  2. patches payload A in the image: its boot clear skips 0x34000-0x37fff
     (a jsr to gaclr), its per-frame read of X:0x38000-0x3800f reads the
     glue's zero words, and T8's FX2 slot takes T7's base;
  3. patches payload B in the image: its boot clear becomes a jsr to gboot,
     and every dispatch id runs the null stub except MACHINEDRUM's, which
     runs gfxinit/gfxproc (T1-T4's stock effect code is the MD's now);
  4. builds the core-1 upload: payload B's own records, then the MD's
     records from out/machinedrum/build/payload_B.mem (all but the sine,
     which gboot builds at 0x38000 where payload B's entry still lives
     during the upload), then the glue, then B's own terminator;
  5. returns it as a PRE-BOOT payload of octabam's loader, depacked before
     the boot-continue call, and the poke that points the boot's payload-B
     upload at it (through the uncached alias, so no cache line the boot's
     own copies left behind can be read instead).

The payload artifact comes from the user's pinned MD update
(tools/build/md_payload.py); nothing here is committed and nothing derived
from it enters Git.
"""

from __future__ import annotations

import array
import pathlib
import re
import runpy
import struct
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
BUILD = ROOT / "out/machinedrum/build"
MEM = BUILD / "payload_B.mem"
SOURCE = BUILD / "source"
GLUE_SRC = ROOT / "modules/machinedrum/md_glue.asm"
ASM = ROOT / "vendor/dsp56300/build/source/dsp_host/dsp_asm"
DIS = ROOT / "out/md_reference/md_dis"
LAYOUT = runpy.run_path(str(ROOT / "modules/machinedrum/layout.py"))["LAYOUT"]

BASE = 0x40000400
PAYLOAD_A = (0x400e2324, 79563)
PAYLOAD_B = (0x400f59ef, 77061)
B_POINTER = 0x40001ED4          # the literal of `pea 0x400f59ef` in the DSP boot 0x40001e50
UNCACHED = 0x08000000
# Pre-boot scratch in the audio page arena, above the boot's cold-path copy
# of the four DSP blobs (0x40a955e0 + 157 KB) and dead once the DSPs run:
# the arena is cleared at cold init, after the boot-continue call.
PRE_DST = 0x40B00000
PRE_STAGE = 0x40B80000
NULL_B = (0x588, 0x589)         # payload B's null stub: init rts, process passthrough
MD_INIT = 0x100057              # the MD's boot init (sine, P-I buffers, voice word 0)

# c10's first slot-0 trigger packet (block 2272 of md_profile cap4/c10): TRX-BD,
# routine index 0x11. The host words only, mapped values; the user's MD update
# is where they came from, so they are read at build time, never written here.
FIXED_CAPTURE = ROOT / "out/md_profile/cap4/c10/log.txt"


def die(msg):
    sys.exit(f"md-image: {msg}")


# ---- payloads in the OS image ---------------------------------------------

def records(img, va, ln):
    """[(space, addr, count, byte offset in img)] and the terminator offset."""
    o = va - BASE
    end = o + ln
    w = lambda k: img[k] | img[k + 1] << 8 | img[k + 2] << 16
    p = o
    if img[p] == 3:
        p += 6
    if img[p] == 4:
        p += 6
    out = []
    while p < end:
        sp = w(p)
        if sp > 2:
            return out, p
        a, c = w(p + 3), w(p + 6)
        out.append((sp, a, c, p + 9))
        p += 9 + 3 * c
    die(f"payload at 0x{va:08x} has no terminator")


def word_at(recs, space, addr):
    hits = [off + 3 * (addr - a) for sp, a, c, off in recs if sp == space and a <= addr < a + c]
    if len(hits) != 1:
        die(f"{'PXY'[space]}:{addr:05x} is in {len(hits)} load records, not one")
    return hits[0]


def rd(img, off):
    return img[off] | img[off + 1] << 8 | img[off + 2] << 16


def wr(img, off, v):
    img[off:off + 3] = bytes((v & 0xff, (v >> 8) & 0xff, (v >> 16) & 0xff))


def patch(img, recs, space, addr, expect, write, what, log):
    for i, (e, v) in enumerate(zip(expect, write)):
        off = word_at(recs, space, addr + i)
        got = rd(img, off)
        if got != e:
            die(f"{what}: {'PXY'[space]}:{addr + i:05x} holds {got:06x}, not stock {e:06x}")
        wr(img, off, v)
    log.append(f"    {'PXY'[space]}:{addr:05x} {' '.join(f'{x:06x}' for x in expect)} -> "
               f"{' '.join(f'{x:06x}' for x in write)}  {what}")


# ---- the MD payload artifact ------------------------------------------------

def md_records():
    if not MEM.exists():
        die(f"{MEM.relative_to(ROOT)} is missing: run `python3 tools/build/md_payload.py` "
            f"(it needs the user's pinned MD OS 1.63 update and the twelve captures)")
    import importlib.util
    spec = importlib.util.spec_from_file_location("md_payload", ROOT / "tools/build/md_payload.py")
    mp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mp)
    try:
        mp.verify()
    except SystemExit as e:
        die(f"the payload artifact does not verify ({e}); rebuild it")
    return mp.read_mem(MEM)


def reloc_place():
    moves = []
    for line in (SOURCE / "reloc.txt").read_text().splitlines():
        f = line.split()
        if f and f[0] == "M":
            moves.append((int(f[1], 16), int(f[2], 16), int(f[3], 16)))
        elif f and f[0] == "T":
            moves.append((int(f[2], 16), int(f[3], 16), int(f[4], 16)))

    def place(a):
        for s, e, n in reversed(moves):
            if s <= a < e:
                return n + a - s
        die(f"MD address {a:06x} has no relocation")
    return place


def fixed_record():
    """Slot 0's first TRX-BD trigger packet in the c10 capture's host stream."""
    if not FIXED_CAPTURE.exists():
        die(f"{FIXED_CAPTURE.relative_to(ROOT)} is missing (md_profile capture of kit 0x10)")
    last_w, cur, expect_count = None, None, False
    with open(FIXED_CAPTURE) as fh:
        for line in fh:
            if not line or line[0] not in "CW":
                continue
            v = int(line.split()[1], 16)
            if line[0] == "C":
                cur = {"dest": last_w, "n": None, "w": []} if v == 0x12 else None
                expect_count = v == 0x12
            elif expect_count:
                cur["n"], expect_count = v + 1, False
            elif cur is not None and len(cur["w"]) < cur["n"]:
                cur["w"].append(v)
                if len(cur["w"]) == cur["n"] and cur["dest"] == 0x800 and cur["w"][0] == 0x11:
                    if cur["n"] != 14:
                        die(f"c10's TRX-BD trigger has {cur['n']} words, not 14")
                    return cur["w"]
            else:
                last_w = v
    die("c10 has no slot-0 TRX-BD trigger packet")


# ---- the glue -----------------------------------------------------------------

def assemble_glue(place):
    g, d = LAYOUT["glue"], LAYOUT["driver"]
    syms = dict(l.split() for l in (SOURCE / "driver.sym").read_text().splitlines() if l.strip())
    vals = {k: g[k] for k in ("OWNER", "GOUT", "ONCE", "SAVER6", "SAVEN7", "TRIGS", "SINE16",
                              "FIXED", "GAIN", "MIX", "LSEQ", "NAPPLY", "NWORDS", "SLIPS", "GAPS", "BAD")}
    alloc = {r["name"]: r for r in LAYOUT["allocations"]}
    voice = alloc["voice_y_records"]["start"]
    vals.update(MIX2=g["MIX"] + 0x20, HALF=d["HALF"], OUTBUF=d["OUTBUF"],
                MBOXA=alloc["mbox_a"]["start"], MBOXB=alloc["mbox_b"]["start"],
                MBOXOFF=alloc["mbox_a"]["start"] - 0x2000, MBOXLEN=alloc["mbox_a"]["words"],
                VOICEOFF=voice - 0x800,
                VOICE=voice,
                SINE=next(r["start"] for r in LAYOUT["allocations"] if r["name"] == "sine"),
                ENTER=int(syms["md_enter"], 16), MDINIT=place(MD_INIT))
    if vals["MDINIT"] != place(MD_INIT) or place(0x10008d) != vals["MDINIT"] + 0x10008d - MD_INIT:
        die("the MD's boot init does not move as one piece")
    src = GLUE_SRC.read_text()
    for k, v in vals.items():
        src = src.replace(f"@{k}@", f"${v:x}")
    left = re.findall(r"@[A-Z0-9]+@", src)
    if left:
        die(f"unfilled placeholders: {sorted(set(left))}")
    labels = re.findall(r"^([A-Za-z_][A-Za-z0-9_]*):", src, re.M)
    clash = [(a, b) for a in labels for b in labels if a != b and b.startswith(a)]
    if clash:
        die(f"label is a prefix of another (dsp_asm resolves by prefix): {clash}")
    org = g["code"]
    with tempfile.TemporaryDirectory(prefix="md-glue-") as tmp:
        tmp = pathlib.Path(tmp)
        (tmp / "g.asm").write_text(src)
        r = subprocess.run([str(ASM), "-in", str(tmp / "g.asm"), "-org", f"{org:x}",
                            "-out", str(tmp / "g.bin"), "-sym", str(tmp / "g.sym")],
                           capture_output=True, text=True)
        if r.returncode or not (tmp / "g.bin").exists():
            die("dsp_asm failed on md_glue.asm:\n" + r.stdout + r.stderr)
        blob = (tmp / "g.bin").read_bytes()
        words = [blob[i] | blob[i + 1] << 8 | blob[i + 2] << 16 for i in range(0, len(blob), 3)]
        gsyms = {}
        for l in (tmp / "g.sym").read_text().splitlines():
            if l.strip():
                k, v = l.split()
                gsyms[k] = int(v, 16)
        if len(words) > g["code_words"]:
            die(f"the glue is {len(words)} words; layout gives it {g['code_words']}")
        # Disassemble what was assembled.
        p = array.array("I", [0]) * 0x150000
        for i, w in enumerate(words):
            p[org + i] = w
        (tmp / "snap.bin").write_bytes(p.tobytes())
        out = subprocess.run([str(DIS), str(tmp / "snap.bin"), f"{org:x}-{org + len(words):x}"],
                             capture_output=True, text=True).stdout
    lines = {int(l.split()[0], 16): l.split(None, 4) for l in out.splitlines() if l.strip()}
    listing, bad, a = [], [], org
    while a < org + len(words):
        f = lines[a]
        text = f[4] if len(f) > 4 else ""
        op = text.split()[0] if text else ""
        listing.append(f"  {a:05x}  {f[2]} {f[3] if f[1] == '2' else '      '}  {text}")
        if op in ("max", "maxm", "dc", "illegal") or re.match(r"(mpy|mac)(su|uu|us)", op):
            bad.append(f"{a:05x} {text}")
        a += max(int(f[1]), 1)
    if bad:
        die("md_glue.asm mis-encoded: " + "; ".join(bad))
    for need in ("gfxinit", "gfxproc", "gboot", "gaclr"):
        if need not in gsyms:
            die(f"md_glue.asm has no {need}")
    return words, gsyms, vals, listing


def ot_record(space, addr, words):
    b = bytearray()
    for v in (space, addr, len(words), *words):
        b += bytes((v & 0xff, (v >> 8) & 0xff, (v >> 16) & 0xff))
    return bytes(b)


# ---- the integration -----------------------------------------------------------

def integrate(img, md_id):
    """Patch both payloads in `img` (bytearray) and return
    (pre-boot payload dict, (poke va, expect, write, note), report lines)."""
    from remix import runtime_build, platform_build
    log = []
    place = reloc_place()
    mdrecs = md_records()
    words, gsyms, vals, listing = assemble_glue(place)
    g = LAYOUT["glue"]
    fixed = fixed_record()

    # ---- payload A ----
    ra, _ = records(img, *PAYLOAD_A)
    patch(img, ra, 0, 0x46, (0x06CF00, 0x000049, 0x5E5C00, 0x5E5D00),
          (0x0BF080, gsyms["gaclr"], 0x000000, 0x000000),
          "A boot clear -> jsr gaclr (keeps 0x34000-0x37fff: the MD's window code)", log)
    patch(img, ra, 0, 0x9B, (0x60F400, 0x038000), (0x60F400, g["ZERO"]),
          "A per-frame read of X:0x38000-f -> the glue's zero words (the sine lives there)", log)
    patch(img, ra, 1, 0x25C, (0x034000,), (0x030000,),
          "A slot table: T8's FX2 takes T7's base (0x34000 is the MD's)", log)

    # ---- payload B ----
    rb, bterm = records(img, *PAYLOAD_B)
    patch(img, rb, 0, 0x47, (0x06CF00, 0x00004A, 0x5E5C00, 0x5E5D00),
          (0x0BF080, gsyms["gboot"], 0x000000, 0x000000),
          "B boot clear -> jsr gboot (the MD's init; its Y and the sine are not cleared)", log)
    if rd(img, word_at(rb, 0, NULL_B[0])) != 0x00000C or rd(img, word_at(rb, 0, NULL_B[1])) != 0x221100:
        die("payload B's null stub is not at P:0x588/0x589")
    for i in range(32):
        init, proc = (gsyms["gfxinit"], gsyms["gfxproc"]) if i == md_id else NULL_B
        wr(img, word_at(rb, 1, 0x215 + i), init)
        wr(img, word_at(rb, 1, 0x235 + i), proc)
    log.append(f"    X:00215/00235 core 1 dispatch: id 0x{md_id:02x} -> "
               f"{gsyms['gfxinit']:05x}/{gsyms['gfxproc']:05x}, the other 31 ids -> the null "
               f"stub 00588/00589 (T1-T4's effect code is the MD's)")

    # ---- the combined core-1 upload ----
    b0 = PAYLOAD_B[0] - BASE
    sine = next(r for r in LAYOUT["allocations"] if r["name"] == "sine")
    out = bytearray(img[b0:bterm])
    dropped = 0
    for space, start, ws in mdrecs:
        if space == "P" and start == sine["start"] and len(ws) == sine["words"]:
            dropped += 1
            continue
        if space == "P" and start < sine["start"] + sine["words"] and start + len(ws) > sine["start"]:
            die(f"MD record P:{start:05x} overlaps the sine but is not it")
        out += ot_record("PXY".index(space), start, ws)
    if dropped != 1:
        die("the MD payload has no single sine record to drop")
    data = [0] * (g["end"] - g["code"])
    data[:len(words)] = words
    data[g["OWNER"] - g["code"]] = 0xFFFFFF
    for i, w in enumerate(fixed):
        data[g["FIXED"] - g["code"] + i] = w
    for i in range(16):
        data[g["GAIN"] - g["code"] + i] = 0x200000       # 1/4 per slot (D1 open)
    out += ot_record(0, g["code"], data)
    out += bytes(img[bterm:PAYLOAD_B[0] - BASE + PAYLOAD_B[1]])
    raw = bytes(out)
    packed = runtime_build.PACKED_MAGIC + len(raw).to_bytes(4, "big") + \
        runtime_build.pack(raw, platform_build.MAX_CANDIDATES)
    if PRE_STAGE + 4 + len(packed) > 0x41000000 or PRE_DST + len(raw) > PRE_STAGE:
        die(f"the core-1 upload ({len(raw):,} B, packed {len(packed):,}) outgrows its pre-boot scratch")
    pre = dict(name="machinedrum core-1 upload", blob=platform_build.SIGNATURE + packed,
               stage=PRE_STAGE + UNCACHED, dst=PRE_DST + UNCACHED, rawlen=len(raw),
               rhash=platform_build.roll(raw))
    poke = (B_POINTER, PAYLOAD_B[0].to_bytes(4, "big"), (PRE_DST + UNCACHED).to_bytes(4, "big"),
            "DSP boot: payload B's upload reads the combined core-1 blob")
    log.insert(0, f"  machinedrum: core-1 upload {len(raw):,} B (stock B {bterm - b0 + 6:,} + MD "
                  f"{len(mdrecs) - 1} records + glue {g['end'] - g['code']} words), packed "
                  f"{len(packed):,} B; the sine record is dropped (gboot builds it); glue "
                  f"{len(words)} words at P:{g['code']:05x} (gboot {gsyms['gboot']:05x}, gaclr "
                  f"{gsyms['gaclr']:05x}); fixed trigger: c10 TRX-BD, {len(fixed)} words")
    (BUILD / "glue.lst").write_text("\n".join(listing) + "\n")
    (BUILD / "glue.sym").write_text("".join(f"{k} {v:06x}\n" for k, v in sorted(
        gsyms.items(), key=lambda kv: kv[1])))
    (BUILD / "core1_upload.bin").write_bytes(raw)
    return pre, poke, log
