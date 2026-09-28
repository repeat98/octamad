"""Stock Octatrack DSP upload records, extracted from the existing image walker."""
import sys
BASE = 0x40000400
UNCACHED = 0x08000000
PAYLOAD_A = (0x400e2324, 79563)
PAYLOAD_B = (0x400f59ef, 77061)
B_POINTER = 0x40001ed4

def die(message):
    sys.exit(f"ab-records: {message}")

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

def ot_record(space, addr, words):
    b = bytearray()
    for v in (space, addr, len(words), *words):
        b += bytes((v & 0xff, (v >> 8) & 0xff, (v >> 16) & 0xff))
    return bytes(b)
