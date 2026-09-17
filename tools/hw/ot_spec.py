"""Write a project's parts and patterns from one JSON spec; read one back.

    python3 tools/hw/ot_spec.py report PROJECT_DIR [--bank N] > spec.json
    python3 tools/hw/ot_spec.py apply  PROJECT_DIR spec.json
    python3 tools/hw/ot_spec.py diff   PROJECT_A PROJECT_B [--bank N]

The spec (every key optional; "all" or a list of 1-based numbers; banks
also as letters, "A" or "A-C"):

  {"banks": "all",
   "parts": {"all": {"name": "RIG",
                      "tracks": {"5": {"fx1": "SPECTRUM", "fx2": "REVERB SERVER",
                                       "fx1_knobs": {"FREQ": 100, "MODE": 4},
                                       "fx2_knobs": {"SEND": 0, "WET": 127}},
                                 "all": {"fx2_knobs": {"SEND": 0}}}}},
   "patterns": {"all": {"tracks": {"all": {"locks": {"fx1": "clear", "fx2": "clear"}},
                                   "5":   {"trigs": [1, 5],
                                           "locks": {"fx2": {"1": {"SEND": 77}},
                                                     "amp": {"1": {"VOL": 77}}}}}}}}

fx1 / fx2: a module key ("SPECTRUM"), a module name ("spectrum"), "NONE",
"SEND", or an id ("0x14" for a stock effect). Setting an id writes that
module's manifest defaults into its twelve knob bytes first; *_knobs then
overrides by the module's own names (or "P0".."P11"). A part is written
with its saved copy (parts 5-8 mirror 1-4, as the unit keeps them). Knob
and lock values are the stored byte, 0-127; a bipolar knob stores panel
value + 64. Lock steps are 1-based; a lock on a step without a trig is a
trigless lock, so "trigs" decides whether it fires. "trigs": "clear" empties
the trig mask; "locks": {"fx1": "clear"} clears that page's locks on every
step; "locks": {"all": "clear"} clears every lock slot, PLAYBACK and LFO
included. Everything else in the file is left as it is.

Layout: tools/hw/ot_project.py (parts), tools/hw/ot_bank.py (patterns).
Every bank written is checksummed and read back, .work and .strd, and the
values re-read must be the values asked for.
"""
import json, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
import ot_project as op  # noqa: E402
import ot_bank as ob  # noqa: E402
from remix import registry  # noqa: E402

AMP = ("ATK", "HOLD", "REL", "VOL", "BAL", "XVOL")       # lock slots 12-17
LOCK_PAGES = {"amp": 12, "fx1": 18, "fx2": 24}
LOCK_SPAN = {"amp": 6, "fx1": 6, "fx2": 6, "all": 32}   # "all": every slot 0-31, "clear" only
SEND_ID, NONE_ID = 0x09, 0x00


# ---- names -----------------------------------------------------------------
def _mods():
    """fx id -> module; a module of ours outranks the stock effect whose id
    it replaces (SPECTRUM over FILTER on 0x04)."""
    out = {}
    for m in registry.modules().values():
        if m.menu is None:
            continue
        cur = out.get(m.menu.fx2_id)
        if cur is None or (getattr(cur, "is_stock", False) and not getattr(m, "is_stock", False)):
            out[m.menu.fx2_id] = m
    return out


def id_name(fid):
    if fid == NONE_ID:
        return "NONE"
    m = _mods().get(fid)
    return m.key if m is not None else f"0x{fid:02x}"


def name_id(name):
    if isinstance(name, int):
        return name
    n = str(name).strip()
    if n.upper() == "NONE":
        return NONE_ID
    if n.upper() == "SEND":
        return SEND_ID
    try:
        return int(n, 0)
    except ValueError:
        pass
    for m in registry.modules().values():
        if m.menu is not None and n.upper() in (m.key.upper(), m.name.upper()):
            return m.menu.fx2_id
    sys.exit(f"no module or id {name!r}")


def knob_names(fid):
    """slot -> name for an effect id: the module's own names, else P0..P11."""
    m = _mods().get(fid)
    out = {}
    for i in range(12):
        nm = m.params[i].name.decode("latin1") if m is not None and i < len(m.params) and m.params[i].name else ""
        out[i] = nm or f"P{i}"
    return out


def knob_slot(fid, name):
    names = knob_names(fid)
    up = str(name).upper()
    for i, nm in names.items():
        if nm.upper() == up:
            return i
    if up.startswith("P") and up[1:].isdigit() and int(up[1:]) < 12:
        return int(up[1:])
    sys.exit(f"{id_name(fid)} has no knob {name!r}; it has {' '.join(v for v in names.values() if v)}")


def lock_slot(page, name, fid=None):
    base = LOCK_PAGES[page]
    up = str(name).upper()
    if up.startswith("S") and up[1:].isdigit():
        return int(up[1:])
    if page == "amp":
        if up not in AMP:
            sys.exit(f"AMP has no knob {name!r}; it has {' '.join(AMP)}")
        return base + AMP.index(up)
    s = knob_slot(fid if fid is not None else NONE_ID, name)
    if s > 5:
        sys.exit(f"lock {name!r} is a page-2 knob; only page 1 (knob A-F) is lockable")
    return base + s


def lock_name(slot, fid1, fid2):
    if 12 <= slot < 18:
        return "amp", AMP[slot - 12]
    if 18 <= slot < 24:
        return "fx1", knob_names(fid1)[slot - 18]
    if 24 <= slot < 30:
        return "fx2", knob_names(fid2)[slot - 24]
    return "other", f"S{slot}"


# ---- selectors -------------------------------------------------------------
def sel(spec, n, letters=False):
    """'all' | [1,3] | 'A-C' | '2' -> sorted 1-based list within 1..n."""
    if spec is None or spec == "all":
        return list(range(1, n + 1))
    if isinstance(spec, int):
        return [spec]
    if isinstance(spec, str):
        s = spec.strip().upper()
        if letters and s.replace("-", "").isalpha():
            a, _, b = s.partition("-")
            lo, hi = ord(a) - 64, ord(b or a) - 64
            return list(range(lo, hi + 1))
        if "-" in s:
            a, b = s.split("-")
            return list(range(int(a), int(b) + 1))
        return [int(s)]
    return sorted(int(x) for x in spec)


def _merge(old, new):
    """A numbered entry over an 'all' entry: dicts merge key by key; a
    'clear' under a dict of specific values means clear the page first,
    then write those (kept as the '_clear' flag)."""
    if isinstance(old, dict) and isinstance(new, dict):
        out = dict(old)
        for k, v in new.items():
            out[k] = _merge(old.get(k), v)
        return out
    if old == "clear" and isinstance(new, dict):
        return {"_clear": True, **new}
    return new


def keyed(d, n, letters=False):
    """{'all': {...}, '5': {...}} -> [(index, merged spec)] for 1..n; 'all'
    applies first, a numbered entry on top."""
    out = []
    for i in range(1, n + 1):
        merged = {}
        for k, v in (d or {}).items():
            if k == "all" or i in sel(k, n, letters):
                for kk, vv in v.items():
                    merged[kk] = _merge(merged.get(kk), vv)
        if merged:
            out.append((i, merged))
    return out


# ---- the part record -------------------------------------------------------
def part_read(data, p, t):
    off = op.PART_BASE + p * op.PART_STRIDE
    a = off + op.P1_OFF + t * op.TRACK_STRIDE
    b = off + op.P2_OFF + t * op.P2_STRIDE
    fid1, fid2 = data[off + op.FX1_OFF + t], data[off + op.FX2_OFF + t]
    return fid1, fid2, bytes(data[a:a + 6]) + bytes(data[b:b + 6]), bytes(data[a + 6:a + 12]) + bytes(data[b + 6:b + 12])


def part_write(data, p, t, fid1, fid2, k1, k2):
    off = op.PART_BASE + p * op.PART_STRIDE
    a = off + op.P1_OFF + t * op.TRACK_STRIDE
    b = off + op.P2_OFF + t * op.P2_STRIDE
    data[off + op.FX1_OFF + t] = fid1
    data[off + op.FX2_OFF + t] = fid2
    data[a:a + 6], data[b:b + 6] = k1[:6], k1[6:]
    data[a + 6:a + 12], data[b + 6:b + 12] = k2[:6], k2[6:]


def part_name(data, p):
    off = len(data) - 2 - 4 * 7 + p * 7
    return bytes(data[off:off + 7]).split(b"\0")[0].decode("latin1")


def defaults_for(fid):
    m = _mods().get(fid)
    if m is None:
        return bytes(12)
    return op.module_defaults(m)


# ---- report ----------------------------------------------------------------
def report(pdir, bank=None):
    pdir = pathlib.Path(pdir)
    banks = sel(bank, 16) if bank else [int(b.name[4:6]) for b in sorted(pdir.glob("bank*.work"))]
    out = {"project": pdir.name, "banks": {}}
    for num in banks:
        path = pdir / f"bank{num:02d}.work"
        if not path.is_file():
            continue
        data = path.read_bytes()
        ob.check_tags(data)
        bank_out = {"parts": {}, "patterns": {}}
        for p in range(op.NPARTS):
            tracks = {}
            for t in range(8):
                fid1, fid2, k1, k2 = part_read(data, p, t)
                n1, n2 = knob_names(fid1), knob_names(fid2)
                tracks[str(t + 1)] = {
                    "fx1": id_name(fid1), "fx2": id_name(fid2),
                    "fx1_knobs": {n1[i]: k1[i] for i in range(12) if n1[i] and not n1[i].startswith("P")} if fid1 else {},
                    "fx2_knobs": {n2[i]: k2[i] for i in range(12) if n2[i] and not n2[i].startswith("P")} if fid2 else {},
                    "fx1_bytes": k1.hex(), "fx2_bytes": k2.hex()}
            bank_out["parts"][str(p + 1)] = {"name": part_name(data, p), "tracks": tracks}
        for pt in range(ob.NPATTERNS):
            tracks = {}
            for t in range(8):
                tr = ob.trigs(data, pt, t)
                lk = ob.locks(data, pt, t)
                if not tr and not lk:
                    continue
                fid1, fid2, _, _ = part_read(data, 0, t)      # names from part 1's effects
                locks = {}
                for step, slots in lk.items():
                    for s, v in slots.items():
                        page, nm = lock_name(s, fid1, fid2)
                        locks.setdefault(page, {}).setdefault(str(step + 1), {})[nm] = v
                tracks[str(t + 1)] = {"trigs": [s + 1 for s in tr], "locks": locks}
            if tracks:
                bank_out["patterns"][str(pt + 1)] = {"tracks": tracks}
        out["banks"][str(num)] = bank_out
    return out


# ---- apply -----------------------------------------------------------------
def apply(pdir, spec):
    pdir = pathlib.Path(pdir)
    have = [int(b.name[4:6]) for b in sorted(pdir.glob("bank*.work"))]
    banks = [b for b in sel(spec.get("banks"), 16, letters=True) if b in have]
    want_parts, want_pat = [], []          # (bank, ...) expectations for the read-back
    for num in banks:
        def mut(data, num=num):
            ob.check_tags(data)
            for p, ps in keyed(spec.get("parts"), op.NPARTS):
                if "name" in ps:
                    off = len(data) - 2 - 4 * 7 + (p - 1) * 7
                    data[off:off + 7] = ps["name"].upper()[:6].encode("latin1").ljust(7, b"\0")
                for t, ts in keyed(ps.get("tracks"), 8):
                    for pp in (p - 1, p - 1 + op.NPARTS):        # the part and its saved copy
                        fid1, fid2, k1, k2 = part_read(data, pp, t - 1)
                        k1, k2 = bytearray(k1), bytearray(k2)
                        if "fx1" in ts:
                            fid1 = name_id(ts["fx1"]); k1 = bytearray(defaults_for(fid1))
                        if "fx2" in ts:
                            fid2 = name_id(ts["fx2"])
                            if fid2 == NONE_ID:
                                fid2 = SEND_ID                     # id 0 gets no page: see ot_project
                            k2 = bytearray(defaults_for(fid2))
                        for nm, v in (ts.get("fx1_knobs") or {}).items():
                            k1[knob_slot(fid1, nm)] = int(v) & 0x7f
                        if fid2 == NONE_ID and ts.get("fx2_knobs"):
                            fid2 = SEND_ID                         # an empty FX2 runs SEND: name its knob
                        for nm, v in (ts.get("fx2_knobs") or {}).items():
                            k2[knob_slot(fid2, nm)] = int(v) & 0x7f
                        part_write(data, pp, t - 1, fid1, fid2, bytes(k1), bytes(k2))
                        want_parts.append((num, pp, t - 1, fid1, fid2, bytes(k1), bytes(k2)))
            for pt, pts in keyed(spec.get("patterns"), ob.NPATTERNS):
                for t, ts in keyed(pts.get("tracks"), 8):
                    fid1, fid2, _, _ = part_read(data, 0, t - 1)
                    if "trigs" in ts:
                        m = 0 if ts["trigs"] == "clear" else sum(1 << (s - 1) for s in ts["trigs"])
                        ob.set_mask(data, pt - 1, t - 1, m, 0)
                    base = ob.trac(pt - 1, t - 1) + ob.LOCKS
                    for page, lk in (ts.get("locks") or {}).items():
                        lo, span = LOCK_PAGES.get(page, 0), LOCK_SPAN[page]
                        if page == "all" and lk != "clear":
                            sys.exit('locks "all" takes "clear" only (slots 0-11 have no names yet)')
                        if lk == "clear" or (isinstance(lk, dict) and lk.get("_clear")):
                            for s in range(ob.NSTEPS):
                                for i in range(lo, lo + span):
                                    data[base + s * ob.LOCK_LEN + i] = ob.NOLOCK
                        if lk == "clear":
                            continue
                        for step, knobs in lk.items():
                            if step == "_clear":
                                continue
                            for nm, v in knobs.items():
                                i = lock_slot(page, nm, fid1 if page == "fx1" else fid2)
                                data[base + (int(step) - 1) * ob.LOCK_LEN + i] = ob.NOLOCK if v is None else int(v) & 0x7f
                    want_pat.append((num, pt - 1, t - 1, ts))
        op._bank_write(pdir, num, mut, guard=False)
    # read back: every file, every write
    for num in banks:
        for path in (pdir / f"bank{num:02d}.work", pdir / f"bank{num:02d}.strd"):
            if not path.is_file():
                continue
            data = path.read_bytes()
            if int.from_bytes(data[-2:], "big") != (sum(data[0x10:-2]) & 0xFFFF):
                sys.exit(f"{path.name}: checksum did not take -- do NOT use this")
            for b, pp, t, fid1, fid2, k1, k2 in want_parts:
                if b == num and part_read(data, pp, t) != (fid1, fid2, k1, k2):
                    sys.exit(f"{path.name} part {pp + 1} T{t + 1}: read-back disagrees")
            for b, pt, t, ts in want_pat:
                if b != num:
                    continue
                if "trigs" in ts:
                    want = [] if ts["trigs"] == "clear" else sorted(s - 1 for s in ts["trigs"])
                    if ob.trigs(data, pt, t) != want:
                        sys.exit(f"{path.name} pattern {pt + 1} T{t + 1}: trigs read back {ob.trigs(data, pt, t)}")
                lk = ob.locks(data, pt, t)
                for page, spec_l in (ts.get("locks") or {}).items():
                    lo, span = LOCK_PAGES.get(page, 0), LOCK_SPAN[page]
                    if spec_l == "clear":
                        if any(i in range(lo, lo + span) for st in lk.values() for i in st):
                            sys.exit(f"{path.name} pattern {pt + 1} T{t + 1}: a {page} lock survived")
                    elif isinstance(spec_l, dict):
                        fid1, fid2, _, _ = part_read(data, 0, t)
                        asked = set()
                        for step, knobs in spec_l.items():
                            if step == "_clear":
                                continue
                            for nm, v in knobs.items():
                                i = lock_slot(page, nm, fid1 if page == "fx1" else fid2)
                                asked.add((int(step) - 1, i))
                                got = lk.get(int(step) - 1, {}).get(i)
                                want = None if v is None else int(v) & 0x7f
                                if got != want:
                                    sys.exit(f"{path.name} pattern {pt + 1} T{t + 1} step {step} {nm}: read back {got}, want {want}")
                        if spec_l.get("_clear"):
                            for st, slots in lk.items():
                                for i in slots:
                                    if lo <= i < lo + 6 and (st, i) not in asked:
                                        sys.exit(f"{path.name} pattern {pt + 1} T{t + 1}: a {page} lock survived the clear at step {st + 1}")
    print(f"{pdir.name}: banks {banks} written, {len(want_parts)} part-track(s) and "
          f"{len(want_pat)} pattern-track(s), every byte read back (.work and .strd)")


# ---- diff ------------------------------------------------------------------
def diff(a, b, bank=None):
    ra, rb = report(a, bank), report(b, bank)
    n = 0

    def walk(x, y, path):
        nonlocal n
        if isinstance(x, dict) and isinstance(y, dict):
            for k in sorted(set(x) | set(y)):
                walk(x.get(k), y.get(k), path + [k])
        elif x != y:
            n += 1
            print(f"  {'/'.join(path)}: {x!r} -> {y!r}")
    walk(ra["banks"], rb["banks"], [])
    print(f"{n} difference(s)")
    return n


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    cmd, args = sys.argv[1], sys.argv[2:]
    bank = args[args.index("--bank") + 1] if "--bank" in args else None
    if cmd == "report":
        print(json.dumps(report(args[0], bank), indent=1))
    elif cmd == "apply":
        apply(args[0], json.loads(pathlib.Path(args[1]).read_text()))
    elif cmd == "diff":
        sys.exit(1 if diff(args[0], args[1], bank) else 0)
    else:
        sys.exit(__doc__)
