"""The Octatrack bank file's pattern records: trigs and parameter locks.

Measured 16 Sep 2026 on OCTABAM90 (five saves from the unit, one change
each, byte-diffed): a bank file is a FORM/BANK header, 16 PTRN records
(stride 0x8eec), each carrying 8 TRAC audio-track records (stride 0x922)
and 8 MTRA MIDI-track records (stride 0x8b9), then the 8 PART records
ot_project.py writes. A TRAC record's data starts 9 bytes after its tag
(ot_project.trac_off, settled against RAM): eight 8-byte step masks
first, BIG-endian -- step s (1-based) is byte 7 - (s-1)//8, bit (s-1)%8;
mask 0 is the trigs, mask 2 the trigless lock trigs (exactly the locked
steps without a trig, four patterns checked); data+0x40..0x47 read 0xaa
on every track of every pattern (a 2-bit-per-step field at its default,
not decoded); data+0x50 / +0x51 are the track's own LENGTH (16/32/48/64
seen) and SCALE index (ot_project.SCALE_NAMES; CLEAR PATTERN resets them
to 16 / 1X) -- the PTRN chunk's tail carries the pattern-level pair
(ot_project.set_pattern_scale); then, at data+0x59 (tag+0x62), 64 step
records of 32 bytes, one byte per lockable parameter, 0xff = no lock, and
0xc0 bytes after them (64 x 3, sparse in real patterns) not decoded.
Lock slots = the live lane's first 32 bytes (port, 18 Sep 2026: a lock in
every slot landed in the lane byte of the same index): 0-5 PLAYBACK page
1, 6-11 LFO page 1 (SPD1-3 DEP1-3), 12-17 AMP (ATK HOLD REL VOL BAL XVOL),
18-23 FX1 page 1, 24-29 FX2 page 1 (knob A..F), 30-31 unseen. A bipolar
knob stores its panel value + 64.

    python3 tools/hw/ot_bank.py report PROJECT_DIR [--bank N]       # FX lock counts per pattern/track
    python3 tools/hw/ot_bank.py strip PROJECT_DIR [--bank N] [--pages fx1,fx2,amp]
                                                                    # those pages' locks -> 0xff, every pattern
The writer fixes the checksum and reads every byte back (.work and .strd).
"""
import pathlib, sys

PTRN_BASE, PTRN_STRIDE, NPATTERNS = 0x16, 0x8eec, 16
TRAC_OFF, TRAC_STRIDE, NTRACKS = 0x08, 0x922, 8        # TRAC records inside a PTRN
DATA, MASK_LEN, NMASKS = 9, 8, 8                        # tag + length + pad, then the masks
LOCKS, NSTEPS, LOCK_LEN = 0x62, 64, 32                  # from the tag
PAGES = {"playback": range(0, 6), "lfo": range(6, 12), "amp": range(12, 18), "fx1": range(18, 24), "fx2": range(24, 30)}
LOCK_TRIGS = 2                                          # step mask 2
TRK_LENGTH, TRK_SCALE = 0x50, 0x51                      # from DATA
NOLOCK = 0xff


def trac(pattern, track):
    """Offset of the TRAC record for pattern (0-15), track (0-7)."""
    return PTRN_BASE + pattern * PTRN_STRIDE + TRAC_OFF + track * TRAC_STRIDE


def check_tags(data):
    for p in range(NPATTERNS):
        if data[PTRN_BASE + p * PTRN_STRIDE:PTRN_BASE + p * PTRN_STRIDE + 4] != b"PTRN":
            sys.exit(f"no PTRN tag for pattern {p + 1}: not a bank file this tool knows")
        for t in range(NTRACKS):
            a = trac(p, t)
            if data[a:a + 4] != b"TRAC":
                sys.exit(f"no TRAC tag for pattern {p + 1} track {t + 1}")


def mask(data, pattern, track, which=0):
    """One of the eight 64-step masks as an int, bit s = step s (0-based)."""
    a = trac(pattern, track) + DATA + which * MASK_LEN
    return int.from_bytes(data[a:a + MASK_LEN], "big")


def set_mask(data, pattern, track, value, which=0):
    a = trac(pattern, track) + DATA + which * MASK_LEN
    data[a:a + MASK_LEN] = int(value).to_bytes(MASK_LEN, "big")


def trigs(data, pattern, track):
    m = mask(data, pattern, track, 0)
    return [s for s in range(NSTEPS) if m >> s & 1]


def locks(data, pattern, track):
    """-> {step: {slot: value}} for every locked byte."""
    base = trac(pattern, track) + LOCKS
    out = {}
    for s in range(NSTEPS):
        rec = data[base + s * LOCK_LEN:base + (s + 1) * LOCK_LEN]
        got = {i: v for i, v in enumerate(rec) if v != NOLOCK}
        if got:
            out[s] = got
    return out


def report(pdir, bank=None):
    pdir = pathlib.Path(pdir)
    banks = [pdir / f"bank{bank:02d}.work"] if bank else sorted(pdir.glob("bank*.work"))
    for b in banks:
        data = b.read_bytes()
        check_tags(data)
        rows = []
        for p in range(NPATTERNS):
            for t in range(NTRACKS):
                lk = locks(data, p, t)
                per = {pg: sum(1 for st in lk.values() for i in st if i in rg) for pg, rg in PAGES.items()}
                other = sum(1 for st in lk.values() for i in st if not any(i in rg for rg in PAGES.values()))
                if lk or trigs(data, p, t):
                    rows.append(f"  P{p + 1:02d} T{t + 1}: {len(trigs(data, p, t)):2d} trigs, locks amp {per['amp']:3d} fx1 {per['fx1']:3d} fx2 {per['fx2']:3d} other {other:3d}")
        print(f"{b.name}: {len(rows)} track(s) with content")
        for r in rows:
            print(r)


def strip(pdir, bank=None, pages=("fx1", "fx2")):
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import ot_project as op
    pdir = pathlib.Path(pdir)
    slots = [i for pg in pages for i in PAGES[pg]]
    nums = [bank] if bank else [int(b.name[4:6]) for b in sorted(pdir.glob("bank*.work"))]
    total = 0
    for num in nums:
        cleared = []

        def mut(data):
            check_tags(data)
            for p in range(NPATTERNS):
                for t in range(NTRACKS):
                    base = trac(p, t) + LOCKS
                    for s in range(NSTEPS):
                        for i in slots:
                            a = base + s * LOCK_LEN + i
                            if data[a] != NOLOCK:
                                data[a] = NOLOCK
                                cleared.append(a)

        op._bank_write(pdir, num, mut, guard=False)
        for path in (pdir / f"bank{num:02d}.work", pdir / f"bank{num:02d}.strd"):
            if not path.is_file():
                continue
            data = path.read_bytes()
            if int.from_bytes(data[-2:], "big") != (sum(data[0x10:-2]) & 0xFFFF):
                sys.exit(f"{path.name}: checksum did not take -- do NOT use this")
            for p in range(NPATTERNS):
                for t in range(NTRACKS):
                    base = trac(p, t) + LOCKS
                    if any(data[base + s * LOCK_LEN + i] != NOLOCK for s in range(NSTEPS) for i in slots):
                        sys.exit(f"{path.name} pattern {p + 1} track {t + 1}: a lock survived")
        n = len(cleared) // 2 if (pdir / f"bank{num:02d}.strd").is_file() else len(cleared)
        total += n
        print(f"bank{num:02d}: {n} {'/'.join(pages)} lock byte(s) cleared")
    print(f"{total} lock byte(s) cleared in {pdir.name}; every pattern read back")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    cmd, pdir, args = sys.argv[1], sys.argv[2], sys.argv[3:]
    bank = int(args[args.index("--bank") + 1]) if "--bank" in args else None
    pages = tuple(args[args.index("--pages") + 1].split(",")) if "--pages" in args else ("fx1", "fx2")
    if cmd == "report":
        report(pdir, bank)
    elif cmd == "strip":
        strip(pdir, bank, pages)
    else:
        sys.exit(__doc__)
