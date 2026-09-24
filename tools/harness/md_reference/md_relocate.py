#!/usr/bin/env python3
"""Relocate the Machinedrum voice DSP to the core-1 layout, for md_replay --reloc.

    python3 tools/harness/md_reference/md_relocate.py [--hot <capture dirs,...>]
        [--hot-plan <reloc.txt>] [--plan <plan.json>] [--keep <ids>|all|sine] <capture dir>

The layout is modules/machinedrum/layout.py (core 1); where each table goes,
and which instructions change, is md_flip.py's placement plan (--plan,
default out/machinedrum/plan.json; WP-A7). Everything moves through one
address map:

  * code is found by recursive descent (md_dis decodes every address of the
    snapshot): from the voice loop head (P:64), the boot init (P:100057) and
    every entry of the three routine tables (init 0x145af5, trigger 0x145bb6,
    render 0x145c77, 193 each). Branches and calls continue at both target
    and fall-through; rts/rti/jmp/bra end a path. Long immediates that point
    into a code region are extra entry points (the indirect jsr (rN) targets).
    An instruction that starts inside one of the plan's data regions is data
    the descent walked into, and is dropped;
  * code moves in units: a unit is joined across a fall-through, across a
    hardware loop's whole body, and across
    every one-word PC-relative branch (its short displacement is not
    patched). The hottest units (--hot: fetch.txt of those captures,
    md_replay MD_REPLAY_FETCH=2; --hot-plan: the H lines of an earlier
    reloc.txt) go to hot_code in private P, the rest to window_code, each in
    source order;
  * the plan's split instructions become two words where they were one, so
    every later address of their unit moves by one more; the map counts
    that, and a loop whose last instruction is split ends one word later;
  * the tables and the P-I buffers go to their private X or Y homes, the
    sine to the window;
  * in every code instruction of two words, word B is re-pointed when it
    holds a moved address: a jump/loop target, an absolute or displacement
    operand, or a #> immediate. Two-word PC-relative branches get their
    displacement recomputed. The routine tables are re-pointed entry by
    entry, in their new home;
  * the plan's flips (one space bit) and splits (two words) are written at
    the instruction's new place;
  * the snapshot's live state: every word of the MD's internal X and Y
    (below LIVE_TOP) holding an address that moves (per-voice pointers set by init code that ran before
    the snapshot; on the OT, init runs after relocation instead), written
    where the word itself ends up (the voice records move). A value test
    cannot tell a pointer from data that happens to fall in the range, so a
    live patch is a guess the replay has to confirm.

It refuses what the map cannot express: a one-word relative branch across a
split, or a one-word absolute target that moves.

Writes <capture dir>/reloc.txt, which md_replay --reloc applies in order:
  Q <X|Y> <old start> <old end> <new start>   move the voice records
  T <X|Y> <old start> <old end> <new start>   move a table from the MD's
                                              external RAM into private X or Y
  M <old start> <old end> <new start>         move code (or the sine) in P
  H <old start> <old end>                     a hot unit (for --hot-plan)
  W <new addr> <value>                        a patched P word at its new place
  X|Y <addr> <value>                          a patched X or Y word
  V <old> <new>                               move a loop word in Y
"""
import bisect
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DIS = ROOT / "out/md_reference/md_dis"
PLAN = ROOT / "out/machinedrum/plan.json"

# Keep the replay harness and the proposed OT image on one address book.  The
# layout is deliberately plain data, so importing it does not pull in build
# machinery or any firmware bytes.
sys.path.insert(0, str(ROOT / "modules/machinedrum"))
from layout import LAYOUT, allocation  # noqa: E402

# The MD code lives in two external spans and one called low-P init routine
# (old start, old end exclusive; the third field is for existing callers).
REGIONS = [
    (0x000143, 0x00015A, None),  # low-P engine init reached from P:10009d/1000a1
    (0x100000, 0x103DBA, None),   # engine code, tables, the E12 descriptors (0x103d7b)
    (0x140000, 0x148000, None),   # engine code and tables
]
LOOP = (0x64, 0xE8)
TABLES = [(0x145AF5, 193), (0x145BB6, 193), (0x145C77, 193)]
# The MD calls this straight-line boot sequence before it enters the voice
# loop.  It is not reachable from the render tables, so it must be an
# explicit descent root for its #> operands to be relocated.
INIT_ENTRY = 0x100057
LIVE_TOP = 0x1000     # the live-pointer scan covers internal X and Y below this

CC = "(cc|hs|ge|ne|pl|nn|ec|lc|gt|cs|lo|lt|eq|mi|nr|es|ls|le)"
END = re.compile(r"^(rts|rti|jmp|bra|illegal|stop|debug)$")
BRANCH = re.compile(rf"^(b{CC}|j{CC}|bs{CC}|js{CC}|bsr|jsr|brclr|brset|bsclr|bsset|jclr|jset|jsclr|jsset|bra|jmp)$")


def in_code_region(a):
    return any(s <= a < e for s, e, _ in REGIONS) or LOOP[0] <= a < LOOP[1]


def decode(snapshot):
    ranges = [f"{LOOP[0]:x}-{LOOP[1]:x}"] + [f"{s:x}-{e:x}" for s, e, _ in REGIONS]
    out = subprocess.run([str(DIS), str(snapshot)] + ranges, capture_output=True, text=True, check=True).stdout
    table = {}
    for line in out.splitlines():
        a, ln, wa, wb, text = line.split(" ", 4)
        table[int(a, 16)] = (int(ln), int(wa, 16), int(wb, 16), text.strip())
    return table


def targets(text):
    return [int(m, 16) for m in re.findall(r"(?:func|int|label|loc)_([0-9a-f]{6})", text)] + \
           [int(m, 16) for m in re.findall(r"(?<![xyl]:)>\$([0-9a-f]{5,6})\b", text)
            if re.match(r"^(j|b|do|dor)", text)]


def relative(op):
    return (op.startswith("b") and BRANCH.match(op) is not None) or op == "dor"


def descend(table, P):
    entries = {LOOP[0], INIT_ENTRY}
    for base, n in TABLES:
        for i in range(n):
            if in_code_region(P[base + i]):
                entries.add(P[base + i])
    code, work = {}, list(entries)
    while work:
        a = work.pop()
        while a in table and a not in code:
            ln, wa, wb, text = table[a]
            code[a] = table[a]
            op = text.split()[0] if text else ""
            for t in targets(text):
                if in_code_region(t) and t not in code:
                    work.append(t)
            for m in re.findall(r"#>\$([0-9a-f]{6})", text):
                v = int(m, 16)
                if in_code_region(v) and v not in code and v not in entries:
                    entries.add(v)
                    work.append(v)
            if END.match(op):
                break
            a += ln
    return code, entries


def units_of(code):
    """Units that must move as one (see the module docstring)."""
    parent = {a: a for a in code}

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for a, (ln, wa, wb, text) in code.items():
        op = text.split()[0] if text else ""
        if not END.match(op) and a + ln in code:
            parent[find(a)] = find(a + ln)
        if ln == 1 and relative(op):
            for t in targets(text):
                if t in parent:
                    parent[find(a)] = find(t)
    # A hardware loop runs by address from the do to its last word, so its
    # body stays in one piece even across a bra or rts inside it.
    starts = sorted(code)
    for a, (ln, wa, wb, text) in code.items():
        if not text.startswith("do") or ln != 2:
            continue
        la = a + (wb - 0x1000000 if wb & 0x800000 else wb) if text.split()[0] == "dor" else wb
        for x in starts[bisect.bisect_left(starts, a):bisect.bisect_right(starts, la)]:
            parent[find(x)] = find(a)
    units = {}
    for a in code:
        units.setdefault(find(a), []).append(a)
    return [sorted(v) for v in units.values()]


def hot_choice(units, sizes, fetch_dirs, budget):
    """The units that carry the most fetches into `budget` words. Greedy:
    each step takes the unit that most lowers the sum of squared remaining
    fetches per word it costs, which works on whichever kit is worst."""
    unit_of = {a: i for i, u in enumerate(units) for a in u}
    per = []
    for d in fetch_dirs:
        f = {}
        for line in (Path(d) / "fetch.txt").read_text().splitlines():
            pc, _, w = line.split()
            pc = int(pc, 16)
            if pc in unit_of:
                f[unit_of[pc]] = f.get(unit_of[pc], 0) + int(w)
        per.append(f)
    rem = [sum(f.values()) for f in per]
    start = list(rem)
    candidates = {i for f in per for i in f}
    chosen, used = set(), 0
    while True:
        best, best_score = None, 0.0
        for i in candidates:
            if used + sizes[i] > budget:
                continue
            gain = sum(rem[k] ** 2 - (rem[k] - f.get(i, 0)) ** 2 for k, f in enumerate(per))
            if gain / sizes[i] > best_score:
                best, best_score = i, gain / sizes[i]
        if best is None:
            break
        chosen.add(best)
        candidates.discard(best)
        used += sizes[best]
        rem = [rem[k] - f.get(best, 0) for k, f in enumerate(per)]
    print(f"hot: chose {len(chosen)} of {len(units)} units, {used} words; fetches left per capture: "
          + ", ".join(f"{100 * r / max(s, 1):.0f}%" for r, s in zip(rem, start)))
    return chosen


class AddressMap:
    """Old MD address -> new address, for code, data regions and the sine."""

    def __init__(self):
        self.spans = []     # (old start, old end, new start, sorted split points)

    def add(self, lo, hi, new, splits=()):
        self.spans.append((lo, hi, new, sorted(splits)))

    def freeze(self):
        self.spans.sort()
        self.starts = [s[0] for s in self.spans]
        for (a, b, *_r), (c, *_s) in zip(self.spans, self.spans[1:]):
            if b > c:
                sys.exit(f"address map: {a:06x}..{b:06x} overlaps {c:06x}")

    def __call__(self, a):
        i = bisect.bisect_right(self.starts, a) - 1
        if i < 0:
            return None
        lo, hi, new, splits = self.spans[i]
        if not lo <= a < hi:
            return None
        # Each split before a adds one word; a split instruction itself
        # starts where its first half goes.
        return new + (a - lo) + bisect.bisect_left(splits, a)


def main():
    args = sys.argv[1:]
    hot_dirs, hot_plan, plan_path, keep, no_live = [], None, PLAN, set(), False
    while args and args[0].startswith("--"):
        flag = args.pop(0)
        if flag == "--hot":
            hot_dirs = args.pop(0).split(",")
        elif flag == "--hot-plan":
            hot_plan = args.pop(0)
        elif flag == "--plan":
            plan_path = Path(args.pop(0))
        elif flag == "--keep":
            keep = set(args.pop(0).split(","))
        elif flag == "--no-live":
            no_live = True
        else:
            sys.exit(f"unknown flag {flag}")
    if hot_plan and hot_dirs:
        sys.exit("use either --hot or --hot-plan, not both")
    if not args:
        sys.exit(__doc__)
    cap = Path(args[0])
    snap = cap / "snapshot.bin"
    P = memoryview(snap.read_bytes()).cast("I")
    plan = json.loads(Path(plan_path).read_text())
    # --keep id,...|all|sine: leave those regions where they are (a bisection
    # aid: the replay's external RAM aliases P, X and Y, so an unmoved table
    # is still reached through either space).
    all_regions = list(plan["regions"])
    if keep:
        plan["regions"] = [r for r in plan["regions"] if "all" not in keep and r["id"] not in keep]
        if "sine" in keep:
            plan["sine"] = None
    table = decode(snap)
    code, entries = descend(table, P)

    # Data the descent walked into: an instruction starting in a data region
    # (every region of the plan, moved or kept).
    data = [(r["lo"], r["hi"]) for r in all_regions]
    data_starts = [lo for lo, _hi in sorted(data)]
    data_sorted = sorted(data)

    def in_data(a):
        i = bisect.bisect_right(data_starts, a) - 1
        return i >= 0 and data_sorted[i][0] <= a < data_sorted[i][1]

    dropped = [a for a in code if in_data(a)]
    for a in dropped:
        del code[a]
    splits = {s["pc"]: s for s in plan["splits"]}
    flips = {f["pc"]: f["word"] for f in plan["flips"]}
    # The P-I render setup uses the buffer pointer as a number in its
    # phase recurrence. Keep the physical pointer in the voice record,
    # then restore the MD numerical value in x1 at this one use. B is
    # dead here and the next mpy overwrites it.
    pi_region = next((r for r in plan["regions"] if r["id"] == "pi"), None)
    expansions = {}
    if pi_region:
        pc = 0x102FAE
        if pc not in code or code[pc][0] != 1 or code[pc][1] != 0x459500:
            sys.exit("P-I phase correction: unexpected instruction at 102fae")
        delta = (pi_region["lo"] - pi_region["new"]) & 0xFFFFFF
        if delta:
            # A driver-owned per-slot flag is set at startup and on each
            # trigger. Consume it on the first P-I phase setup; subsequent
            # phase values can equal aligned buffer addresses by chance.
            flags = allocation("phase_flags")["start"]
            slot = LAYOUT["driver"]["LV142"]
            expansions[pc] = [0x459500, 0x6CF000, slot, 0x0B74CF, flags,
                              0x20000B, 0x0D104A, 0x000011, 0x20001B,
                              0x0B748F, flags, 0x20AF00, 0x0140CD,
                              pi_region["new"], 0x0D1049, 0x000009,
                              0x0140CD, pi_region["new"] + pi_region["hi"] - pi_region["lo"],
                              0x0D1041, 0x000005, 0x0140C8, delta, 0x21A500]
    extra = {a: 1 for a in splits}
    for a, words in expansions.items():
        if a in extra or a in flips:
            sys.exit(f"P-I phase correction conflicts with plan at {a:06x}")
        extra[a] = len(words) - code[a][0]
    missing = sorted(a for a in list(splits) + list(flips) if a not in code and not LOOP[0] <= a < LOOP[1])
    if missing:
        sys.exit("plan names instructions the descent did not find: " + " ".join(f"{a:06x}" for a in missing))
    for a in splits:
        if code[a][0] != 1:
            sys.exit(f"split {a:06x}: not a one-word instruction")

    # Units, sized with their splits, and where each goes.
    moving = {a: v for a, v in code.items() if not LOOP[0] <= a < LOOP[1]}
    units = units_of(moving)
    sizes = [max(a + moving[a][0] for a in u) - u[0] + sum(extra.get(a, 0) for a in u) for u in units]
    hot_alloc, win_alloc = allocation("hot_code"), allocation("window_code")
    if hot_plan:
        pinned = set()
        for line in Path(hot_plan).read_text().splitlines():
            if line.startswith("H "):
                pinned.add(int(line.split()[1], 16))
        hot = {i for i, u in enumerate(units) if u[0] in pinned}
        print(f"hot: pinned {len(hot)} of {len(pinned)} units from {hot_plan}")
    elif hot_dirs:
        hot = hot_choice(units, sizes, hot_dirs, hot_alloc["words"])
    else:
        hot = set()
    amap = AddressMap()
    at = {"hot": hot_alloc["start"], "win": win_alloc["start"]}
    placed = []
    for i in sorted(range(len(units)), key=lambda i: units[i][0]):
        u = units[i]
        where = "hot" if i in hot else "win"
        lo, hi = u[0], max(a + moving[a][0] for a in u)
        amap.add(lo, hi, at[where], [a for a in u for _ in range(extra.get(a, 0))])
        placed.append((lo, hi, at[where], where))
        at[where] += sizes[i]
    for where, alloc in (("hot", hot_alloc), ("win", win_alloc)):
        if at[where] > alloc["start"] + alloc["words"]:
            sys.exit(f"{alloc['name']}: {at[where] - alloc['start']} words do not fit {alloc['words']}")
    homes = {(r["lo"], r["hi"]): "P" for r in all_regions}
    for r in plan["regions"]:
        amap.add(r["lo"], r["hi"], r["new"])
        homes[(r["lo"], r["hi"])] = r["home"]
    sine = plan["sine"]
    if sine:
        amap.add(sine["lo"], sine["hi"], sine["new"])
    amap.freeze()

    def home_of(a):
        i = bisect.bisect_right(data_starts, a) - 1
        if i >= 0 and data_sorted[i][0] <= a < data_sorted[i][1]:
            return homes[data_sorted[i]]
        return "P"

    def loop_end(la):
        # A loop ends at its last word; a split last instruction ends one later.
        return amap(la) + extra.get(la, 0)

    # The refusals: one-word targets the map would have to change.
    for a, (ln, wa, wb, text) in moving.items():
        op = text.split()[0] if text else ""
        if ln != 1:
            continue
        for t in targets(text):
            if amap(t) is None:
                continue
            if relative(op):
                if amap(t) - amap(a) != t - a:
                    sys.exit(f"{a:06x} {text}: a one-word relative branch across a split")
            elif amap(t) != t:
                sys.exit(f"{a:06x} {text}: a one-word absolute target that moves")

    patches, kinds = {}, {}
    tail = next((r for r in plan["regions"] if r["id"] == "e12_tail"), None)

    def count(kind):
        kinds[kind] = kinds.get(kind, 0) + 1

    for a, (ln, wa, wb, text) in moving.items():
        if ln != 2:
            continue
        op = text.split()[0] if text else ""
        if relative(op):
            disp = wb - 0x1000000 if wb & 0x800000 else wb
            t = a + disp if op == "dor" else (targets(text) or [None])[0]
            if t is None or t - a != disp:
                sys.exit(f"{a:06x} {text}: relative target does not decode as own address + word B")
            nt = loop_end(t) if op == "dor" else (amap(t) if amap(t) is not None else t)
            na = amap(a)
            if nt - na != disp:
                patches[a + 1] = (nt - na) & 0xFFFFFF
                count("rel")
            continue
        m = amap(wb)
        if m is None and tail and wb == tail["hi"]:
            # Exclusive end of the four 128-word E12 tail buffers.
            m = tail["new"] + tail["hi"] - tail["lo"]
        if m is None:
            continue
        if text.startswith("do"):
            patches[a + 1] = loop_end(wb)
            count("loop")
            continue
        count("target" if BRANCH.match(op) else "imm" if "#>$" in text else
              "disp" if re.search(r"\(r\d[+-]\$", text) else "abs")
        patches[a + 1] = m

    # The boot init's voice-record base is internal, not in the map.
    voice_x, voice_y = allocation("voice_x"), allocation("voice_y_records")
    if INIT_ENTRY in code and code[INIT_ENTRY][0] == 2 and code[INIT_ENTRY][2] == 0x800:
        patches[INIT_ENTRY + 1] = voice_y["start"]
        count("init")

    # The routine tables' entries, in the tables' new home.
    xy_patches = []
    for base, n in TABLES:
        for i in range(n):
            m = amap(P[base + i])
            if m is not None:
                where = amap(base + i)
                space = home_of(base + i)
                xy_patches.append(("P" if space == "W" else space, base + i if where is None else where, m))
                count("table")

    # Seed the MD low image that the driver swaps in on the first call.
    # Preserve the relocated pointers there as in the live X/Y image.
    mdsave = allocation("mdsave_full")
    assert mdsave["words"] == 0x240
    for offset, base, n in ((0, 0x150000, 0x100),
                            (0x100, 0x170000, 0x140)):
        for i in range(n):
            value = P[base + i]
            mapped = amap(value)
            xy_patches.append(("Y", mdsave["start"] + offset + i,
                               value if mapped is None else mapped))

    # Each slot gets one chance to translate an initial physical P-I
    # pointer to the MD numerical phase. The driver re-arms it on a trigger.
    phase_flags = allocation("phase_flags")
    for i in range(16):
        xy_patches.append(("Y", phase_flags["start"] + i, 1))

    # The loop's Y words (the render buffer y:$140, the record base y:$141,
    # the slot y:$142, and each slot's engine at y:$153+slot) move to the
    # layout's loop words; the engines reach y:$140 and y:$142 through long
    # absolute operands only.
    loopvars = LAYOUT["driver"]["loopvars"]
    ymove = {0x140: loopvars, 0x141: loopvars + 1, 0x142: loopvars + 2}
    ymove.update({0x153 + i: loopvars + 0x10 + i for i in range(16)})
    for a, (ln, wa, wb, text) in moving.items():
        if ln != 2:
            continue
        for m in re.findall(r"y:>\$([0-9a-f]+)\b", text):
            v = int(m, 16)
            if v in ymove and wb == v:
                patches[a + 1] = ymove[v]
                count("loopvar")

    # Live state: internal X and Y words that hold a moving address, written
    # where the word lives after the voice records move.
    def voice_moved(space, a):
        if 0x800 <= a < 0xC00:
            return (voice_x if space == "X" else voice_y)["start"] + a - 0x800
        return a

    # Only the MD's own internal RAM (it uses X and Y below 0xc00): the
    # snapshot's words above it are leftovers the MD never reads, and the
    # tables now live there.
    live = []
    for space, base in () if no_live else (("X", 0x150000), ("Y", 0x170000)):
        for i in range(LIVE_TOP):
            m = amap(P[base + i])
            if m is not None:
                live.append((space, voice_moved(space, i), m))
    kinds["live"] = len(live)

    # Calls out of the moved code into the MD's low P, other than the loop:
    # on the OT that P is payload B's own.
    low = sorted({t for a, (ln, wa, wb, text) in moving.items() for t in targets(text)
                  if t < 0x100000 and not LOOP[0] <= t < LOOP[1]})

    words = sum(ln for ln, *_r in moving.values())
    print(f"code: {len(code)} instructions, {words} words outside the loop, from {len(entries)} entries;"
          f" {len(dropped)} starts in data regions dropped")
    print(f"placed: hot {at['hot'] - hot_alloc['start']} of {hot_alloc['words']} words at "
          f"{hot_alloc['start']:04x}, window {at['win'] - win_alloc['start']} of {win_alloc['words']} at "
          f"{win_alloc['start']:05x}; {len(plan['regions'])} data regions, "
          f"{len(flips)} flips, {len(splits)} splits, {len(expansions)} phase expansions")
    print("patches: " + ", ".join(f"{k} {v}" for k, v in sorted(kinds.items())))
    if low:
        print("targets in the MD's low P outside the loop: " + " ".join(f"{t:04x}" for t in low))

    with (cap / "reloc.txt").open("w") as f:
        for space, voice in (("X", voice_x), ("Y", voice_y)):
            f.write(f"Q {space} 000800 000c00 {voice['start']:06x}\n")
        for r in plan["regions"]:
            if r["home"] == "W":
                f.write(f"M {r['lo']:06x} {r['hi']:06x} {r['new']:06x}\n")
            else:
                f.write(f"T {r['home']} {r['lo']:06x} {r['hi']:06x} {r['new']:06x}\n")
        if sine:
            f.write(f"M {sine['lo']:06x} {sine['hi']:06x} {sine['new']:06x}\n")
        for lo, hi, new, where in placed:
            # The unit's words, in segments around its split points.
            cut = [a for a in sorted(set(splits) | set(expansions)) if lo <= a < hi]
            seg = lo
            for a in cut + [hi]:
                if a > seg:
                    f.write(f"M {seg:06x} {a:06x} {amap(seg):06x}\n")
                seg = a + moving[a][0] if a < hi else a
            if where == "hot":
                f.write(f"H {lo:06x} {hi:06x}\n")
        for a, v in sorted(patches.items()):
            f.write(f"W {amap(a) if amap(a) is not None else a:06x} {v:06x}\n")
        for a, w in sorted(flips.items()):
            f.write(f"W {amap(a) if amap(a) is not None else a:06x} {w:06x}\n")
        for a, s in sorted(splits.items()):
            f.write(f"W {amap(a):06x} {s['words'][0]:06x}\n")
            f.write(f"W {amap(a) + 1:06x} {s['words'][1]:06x}\n")
        for a, words in sorted(expansions.items()):
            for i, word in enumerate(words):
                f.write(f"W {amap(a) + i:06x} {word:06x}\n")
        for space, a, v in xy_patches:
            f.write(f"{space if space in 'XY' else 'W'} {a:06x} {v:06x}\n")
        for space, a, v in live:
            f.write(f"{space} {a:06x} {v:06x}\n")
        for old, new in sorted(ymove.items()):
            f.write(f"V {old:06x} {new:06x}\n")
    print(f"wrote {cap / 'reloc.txt'}")


if __name__ == "__main__":
    main()
