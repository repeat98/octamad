#!/usr/bin/env python3
"""Analog BD DSP 808/909 engines in an OT image (modules/analog-bassdrum/DSP909.md).

build_bus.py calls integrate() last, when the remix carries ANALOG BD, after
every DSP pass has written both payloads. For each payload it

  1. assembles ab_glue.asm with both bass-drum engines behind it at the harvested SPRING
     REV's P address (the remix does not list SPRING REV, so its code is on
     neither chooser: stock.harvested) and checks the bytes by disassembly
     (dsp909.assemble); the code is written over SPRING's own P words, in
     place, after checking they are still stock. A shared stock reverb helper
     is copied to the reserved end of the region and its external callers
     are retargeted before replacing the donor;
  2. points SPRING's dispatch (id 0x15, X:0x22a/0x24a) at the null stub, so a
     Part that still names SPRING REV runs a passthrough, not our code;
  3. patches the source seam, `move a,x:>$20e` (A P:0x39c, B P:0x1a2), into
     a jsr to the glue;
  4. builds the payload's upload with one more X record: the 909's tables at
     X:0x2840 and four voice blocks after them, in private X that both
     cores' measured memory ledgers mark free. Not the shared window: stock PLATE and DARK write
     14,335 and 15,778 words into a 16K FX2 slot there, and the window runs
     code at one wait state.

The two uploads go in as PRE-BOOT payloads of octabam's loader, with the
pokes that point the DSP boot's two uploads at them.
"""
from __future__ import annotations

import hashlib
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "modules/analog-bassdrum"))
sys.path.insert(0, str(ROOT / "tools/build"))
import dsp808
import dsp909  # noqa: E402
import ab_records  # noqa: E402  (stock DSP upload record helpers)

BASE = ab_records.BASE
UNCACHED = ab_records.UNCACHED
GLUE = ROOT / "modules/analog-bassdrum/ab_glue.asm"
OUT = ROOT / "out/analog-bassdrum/image"

SPRING_ID = 0x15
PAY = {
    #    payload (va, len), upload pointer, SPRING's P, null stub, seam, continue
    "A": dict(payload=ab_records.PAYLOAD_A, pointer=0x40001E8E, spring=0x01252,
              null=(0x7C8, 0x7C9), seam=0x39C, cont=0x426),
    "B": dict(payload=ab_records.PAYLOAD_B, pointer=ab_records.B_POINTER, spring=0x01012,
              null=(0x588, 0x589), seam=0x1A2, cont=0x221),
}
SPRING_WORDS = 1063
# This 35-word routine is shared by PLATE/DARK despite lying inside SPRING.
# Copy from the user's stock image; only its absolute DO end needs relocation.
SHARED_WORDS = 35
SHARED_OFFSET = 0x334
SHARED_SHA256 = "c411c03ac315959374f7f16b8cc3558f65dbcd60dcdaa912ff0a39dcea53752a"
SHARED_CALLS = {"A": (0x17b3, 0x1998, 0x19c2), "B": (0x1573, 0x1758, 0x1782)}
# With the DSP dynamic loader's stock variant every stock effect is loaded on
# demand, the whole effect block is harvested, and the build reserves this much
# at its top for Analog BD (build_bus.AB_TOP): the same ceiling SPRING's region
# gave it. The loader's X reply words must stay outside the private X below.
RESERVE = SPRING_WORDS - SHARED_WORDS
LOADER_X = (0x2360, 0x2368), (0x4360, 0x4368)
TABLES = 0x2840                 # X: the tables, then the voice blocks
VOICE_STRIDE = 0x40             # 2 * x:$418 (0/$20/$40/$60)
KNOBS = 0x30                    # the knob block inside a voice block
TABLES808 = 0x3200
VOICES808 = 0x3600
X_TOP = 0x3940                  # the lower of the two ledgers' free tops
# Pre-boot destination and staging buffers for each DSP upload.
PRE = {"A": (0x40B00000, 0x40B80000), "B": (0x40B40000, 0x40BC0000)}


def die(msg):
    sys.exit(f"ab-image: {msg}")


def layout():
    lay = dsp909.default_layout(TABLES)
    end = max(a + n for a, n in ((lay[k], len(v)) for k, v in
                                  list(dsp909.tables()[0].items()) + list(dsp909.tables()[2].items())))
    vbase = (end + 0x3F) & ~0x3F
    if dsp909.SWORDS > KNOBS or KNOBS + 13 > VOICE_STRIDE:
        die(f"a voice block holds {dsp909.SWORDS} state words and 13 knob words: "
            f"stride {VOICE_STRIDE:#x} is too small")
    if vbase + 4 * VOICE_STRIDE > X_TOP:
        die(f"tables and voices end at X:{vbase + 4 * VOICE_STRIDE:05x}, past the free top {X_TOP:05x}")
    return lay, vbase


def x_image(lay, vbase):
    """The X record: tables, then four voice blocks as zq02 leaves them."""
    words = [0] * (VOICES808 + 4 * VOICE_STRIDE - TABLES)
    assert vbase + 4 * VOICE_STRIDE <= TABLES808
    assert VOICES808 + 4 * VOICE_STRIDE <= X_TOP
    for name, vals in dsp808.tables().items():
        start = dsp808.layout(TABLES808)[name]
        assert start + len(vals) <= VOICES808
        for i, v in enumerate(vals):
            words[start - TABLES + i] = dsp909.q24(v)
    tab, _, lists, _ = dsp909.tables()
    for name, vals in list(tab.items()) + list(lists.items()):
        for i, v in enumerate(vals):
            words[lay[name] - TABLES + i] = dsp909.q24(v)
    for k in range(4):
        b = vbase - TABLES + k * VOICE_STRIDE
        words[b + dsp909.OFF["C"]] = 0x7FFFFF
        words[b + dsp909.OFF["KLPF"]] = 0x7FFFFF
        words[b + dsp909.OFF["LCG"]] = dsp909.SEED
    for k in range(4):
        words[VOICES808 - TABLES + k * VOICE_STRIDE + 0x16] = 0x7fffff
    return words


def assemble(org, cont, lay, vbase, tag):
    glue = GLUE.read_text().replace("@VBASE@", f"${vbase:x}").replace("@CONT@", f"${cont:x}")
    glue = glue.replace("@V808@", f"${VOICES808:x}")
    src = glue + "\n" + dsp909.source(lay) + "\n" + dsp808.source(dsp808.layout(TABLES808), lay)
    OUT.mkdir(parents=True, exist_ok=True)
    binf = OUT / f"ab_{tag}.bin"
    syms, _ = dsp909.assemble(org, lay, binf, src)
    blob = binf.read_bytes()
    words = [blob[i] | blob[i + 1] << 8 | blob[i + 2] << 16 for i in range(0, len(blob), 3)]
    if len(words) > SPRING_WORDS - SHARED_WORDS:
        die(f"payload {tag}: glue + engine are {len(words)} words; SPRING's usable region is {SPRING_WORDS - SHARED_WORDS}")
    return words, syms


def integrate(img, stock_img, org=None):
    """Patch both payloads in `img` (bytearray); return ([pre-boot dicts], [pokes], log).
    `stock_img` is the pristine image: SPRING's words are checked against it.
    `org` ({payload: P address}) places the engines there instead, for the
    dynamic stock build: no stock reverb stays resident, so the shared reverb
    helper is neither copied nor retargeted (the loader keeps its own copy),
    and the reserved words must still be stock (nothing else placed there)."""
    from remix import runtime_build, platform_build
    lay, vbase = layout()
    xwords = x_image(lay, vbase)
    pres, pokes, log = [], [], []
    for tag, c in PAY.items():
        recs, term = ab_records.records(img, *c["payload"])
        srecs, _ = ab_records.records(stock_img, *c["payload"])
        at = org[tag] if org else c["spring"]
        words, syms = assemble(at, c["cont"], lay, vbase, tag)
        if org:
            if len(words) > RESERVE:
                die(f"payload {tag}: glue + engine are {len(words)} words; the reserve is {RESERVE}")
            for lo, hi in LOADER_X:
                if lo < X_TOP and TABLES < hi:
                    die(f"payload {tag}: the loader's X words {lo:05x}..{hi:05x} overlap the private X")
        helper_old = c["spring"] + SHARED_OFFSET
        helper_new = c["spring"] + SPRING_WORDS - SHARED_WORDS
        if org:
            log.append(f"  analog bd {tag}: no stock reverb is resident; the shared "
                       f"reverb routine is the dynamic loader's copy")
        else:
            helper = [ab_records.rd(stock_img, ab_records.word_at(srecs, 0, helper_old + i))
                      for i in range(SHARED_WORDS)]
            normalized = helper.copy()
            normalized[6] -= helper_old
            digest = hashlib.sha256(b"".join(w.to_bytes(3, "big") for w in normalized)).hexdigest()
            if digest != SHARED_SHA256:
                die(f"payload {tag}: shared stock reverb routine drifted")
            helper[6] += helper_new - helper_old
            for i, word in enumerate(helper):
                addr = helper_new + i
                off = ab_records.word_at(recs, 0, addr)
                if ab_records.rd(img, off) != ab_records.rd(stock_img, ab_records.word_at(srecs, 0, addr)):
                    die(f"payload {tag}: shared reverb destination P:{addr:05x} is not stock")
                ab_records.wr(img, off, word)
            for call in SHARED_CALLS[tag]:
                ab_records.patch(img, recs, 0, call, (0x0bf080, helper_old),
                               (0x0bf080, helper_new), f"{tag} preserve shared reverb call", log)
            log.append(f"  analog bd {tag}: shared reverb {SHARED_WORDS} words "
                       f"P:{helper_old:05x} -> P:{helper_new:05x}; 3 stock calls retargeted")
        # 1. the code over its donor words, which must still be stock
        for i, w in enumerate(words):
            off = ab_records.word_at(recs, 0, at + i)
            soff = ab_records.word_at(srecs, 0, at + i)
            if ab_records.rd(img, off) != ab_records.rd(stock_img, soff):
                die(f"payload {tag}: P:{at + i:05x} is no longer a stock word; "
                    f"something else was placed in Analog BD's region")
            ab_records.wr(img, off, w)
        # 2. SPRING's dispatch -> the null stub (the dynamic build stubbed it already)
        for table, stub in ((0x215, c["null"][0]), (0x235, c["null"][1])):
            off = ab_records.word_at(recs, 1, table + SPRING_ID)
            got = ab_records.rd(img, off)
            if not (c["spring"] <= got < c["spring"] + SPRING_WORDS or got == stub):
                die(f"payload {tag}: X:{table + SPRING_ID:05x} holds {got:06x}, not SPRING's entry")
            if org and got != stub:
                die(f"payload {tag}: dynamic build left SPRING's dispatch at {got:06x}, not the stub")
            ab_records.wr(img, off, stub)
        # 3. the seam
        ab_records.patch(img, recs, 0, c["seam"], (0x567000, 0x00020E), (0x0BF080, syms["zg01"]),
                       f"{tag} source seam -> jsr the Analog BD glue", log)
        # 4. the upload: the payload's records, the X record, its terminator
        p0 = c["payload"][0] - BASE
        raw = bytes(img[p0:term]) + ab_records.ot_record(1, TABLES, xwords) + \
            bytes(img[term:p0 + c["payload"][1]])
        packed = runtime_build.PACKED_MAGIC + len(raw).to_bytes(4, "big") + \
            runtime_build.pack(raw, platform_build.MAX_CANDIDATES)
        dst, stage = PRE[tag]
        if len(raw) > 0x40000 or 4 + len(packed) > 0x40000:
            die(f"payload {tag}'s upload ({len(raw):,} B, packed {len(packed):,}) outgrows its scratch")
        pres.append(dict(name=f"analog bd payload {tag}", blob=platform_build.SIGNATURE + packed,
                         stage=stage + UNCACHED, dst=dst + UNCACHED, rawlen=len(raw),
                         rhash=platform_build.roll(raw)))
        pokes.append((c["pointer"], c["payload"][0].to_bytes(4, "big"), (dst + UNCACHED).to_bytes(4, "big"),
                      f"DSP boot: payload {tag}'s upload reads the Analog BD's"))
        log.append(f"  analog bd {tag}: glue + 808/909 {len(words)} words at P:{at:05x} "
                   + (f"(the effect block's top, reserve {RESERVE}); " if org else
                      f"(SPRING REV's region, {SPRING_WORDS}); ")
                   + f"id 0x{SPRING_ID:02x} -> null stub "
                   f"{c['null'][0]:05x}/{c['null'][1]:05x}; X:{TABLES:05x}..{TABLES + len(xwords) - 1:05x} "
                   f"tables + voices (voice 0 at {vbase:05x}); upload {len(raw):,} B, packed {len(packed):,}")
        (OUT / f"upload_{tag}.bin").write_bytes(raw)
        (OUT / f"ab_{tag}.sym").write_text("".join(f"{k} {v:06x}\n" for k, v in sorted(syms.items(), key=lambda kv: kv[1])))
    return pres, pokes, log
