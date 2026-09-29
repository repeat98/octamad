#!/usr/bin/env python3
"""Part-resident Analog BD DSP engines.

SPRING's P region holds a resident source dispatcher, bounded packet loader,
shared desk and an initially empty engine pool. Its stock PLATE/DARK helper
is preserved at the end. Both boot uploads carry only the common tables and
zeroed voice/loader state. A third preboot payload puts our relocatable engine
catalogue in reserved ColdFire SDRAM, declared and range-checked by the platform.
The ColdFire source builder streams the active Part's packages through the
normal per-track control records; the DSP admits them only after COMMIT.
"""
from __future__ import annotations

import hashlib
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "modules/analog-bassdrum"))
sys.path.insert(0, str(ROOT / "tools/build"))
import dynamic
import dsp909  # noqa: E402
import ab_records  # noqa: E402  (stock DSP upload record helpers)

BASE = ab_records.BASE
UNCACHED = ab_records.UNCACHED
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
TABLES = 0x2840                 # X: the tables, then the voice blocks
X_TOP = 0x3940                  # the lower of the two ledgers' free tops
# Pre-boot destination and staging buffers for each DSP upload.
PRE = {"A": (0x40B00000, 0x40B80000), "B": (0x40B40000, 0x40BC0000)}


def die(msg):
    sys.exit(f"ab-image: {msg}")


def integrate(img, stock_img):
    """Patch both payloads in `img` (bytearray); return ([pre-boot dicts], [pokes], log).
    `stock_img` is the pristine image: SPRING's words are checked against it."""
    from remix import runtime_build, platform_build
    assert dynamic.META+8 <= X_TOP
    xwords = [0] * (dynamic.META+8-TABLES)
    common = dsp909.tables()[0]
    for name, addr in dynamic.common_layout().items():
        for i, value in enumerate(common[name]): xwords[addr-TABLES+i] = dsp909.q24(value)
    kernels=[]
    pres, pokes, log = [], [], []
    for tag, c in PAY.items():
        recs, term = ab_records.records(img, *c["payload"])
        srecs, _ = ab_records.records(stock_img, *c["payload"])
        OUT.mkdir(parents=True,exist_ok=True)
        pend=c['spring']+SPRING_WORDS-SHARED_WORDS
        resident,syms,pbase=dynamic.kernel(c['spring'],c['cont'],pend,OUT/f'kernel_{tag}.bin')
        kernels.append(dict(base=pbase,end=pend,symbols=syms))
        words=resident+[0]*(pend-pbase)
        assert len(resident)<SPRING_WORDS-SHARED_WORDS
        log.append(f"  dynamic {tag}: resident {len(resident)} P words, engine pool {pend-pbase}, P:{pbase:05x}..{pend-1:05x}")
        helper_old = c["spring"] + SHARED_OFFSET
        helper_new = c["spring"] + SPRING_WORDS - SHARED_WORDS
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
        # 1. the code over SPRING's words, which must still be stock
        for i, w in enumerate(words):
            off = ab_records.word_at(recs, 0, c["spring"] + i)
            soff = ab_records.word_at(srecs, 0, c["spring"] + i)
            if ab_records.rd(img, off) != ab_records.rd(stock_img, soff):
                die(f"payload {tag}: P:{c['spring'] + i:05x} is no longer SPRING REV's stock word; "
                    f"something else was placed in its region")
            ab_records.wr(img, off, w)
        # 2. SPRING's dispatch -> the null stub
        for table, stub in ((0x215, c["null"][0]), (0x235, c["null"][1])):
            off = ab_records.word_at(recs, 1, table + SPRING_ID)
            got = ab_records.rd(img, off)
            if not (c["spring"] <= got < c["spring"] + SPRING_WORDS or got == stub):
                die(f"payload {tag}: X:{table + SPRING_ID:05x} holds {got:06x}, not SPRING's entry")
            ab_records.wr(img, off, stub)
        # 3. the seam
        ab_records.patch(img, recs, 0, c["seam"], (0x567000, 0x00020E), (0x0BF080, syms["zd01"]),
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
        log.append(f"  analog bd {tag}: resident + empty engine pool {len(words)} words at P:{c['spring']:05x} "
                   f"(SPRING REV's region, {SPRING_WORDS}); id 0x{SPRING_ID:02x} -> null stub "
                   f"{c['null'][0]:05x}/{c['null'][1]:05x}; X:{TABLES:05x}..{TABLES + len(xwords) - 1:05x} "
                   f"common tables + empty allocations (voice 0 at {dynamic.VOICE_BASE:05x}); upload {len(raw):,} B, packed {len(packed):,}")
        (OUT / f"upload_{tag}.bin").write_bytes(raw)
        (OUT / f"ab_{tag}.sym").write_text("".join(f"{k} {v:06x}\n" for k, v in sorted(syms.items(), key=lambda kv: kv[1])))
    raw,packages=dynamic.library(kernels,OUT)
    (OUT/'library.bin').write_bytes(raw)
    import json
    (OUT/'dynamic.json').write_text(json.dumps(dict(kernels=kernels,packages=packages),indent=2))
    packed=runtime_build.PACKED_MAGIC+len(raw).to_bytes(4,'big')+runtime_build.pack(raw,platform_build.MAX_CANDIDATES)
    assert len(packed)+4<=dynamic.LIBRARY_LIMIT
    pres.append(dict(name='Analog BD engine library',blob=platform_build.SIGNATURE+packed,
                     stage=dynamic.LIBRARY_STAGE+UNCACHED,dst=dynamic.LIBRARY+UNCACHED,
                     rawlen=len(raw),rhash=platform_build.roll(raw)))
    log.append(f"  dynamic library: {len(raw):,} B in SDRAM, {len(packages)} engines; no engine code resident at boot")
    return pres, pokes, log
