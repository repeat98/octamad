#!/usr/bin/env python3
"""Relocate the Machinedrum voice DSP's code and tables, for md_replay --reloc.

    python3 tools/harness/md_reference/md_relocate.py <capture dir> [profile dirs...]

The engine code lives in two external regions of the MD's unified external
RAM. This moves each region by its own offset (REGIONS below) and patches every
address that points into a moved region:

  * code is found by recursive descent (md_dis decodes every address of the
    snapshot): from the voice loop head (P:64) and every entry of the three
    routine tables (init 0x145af5, trigger 0x145bb6, render 0x145c77, 193
    each). Branches and calls continue at both target and fall-through;
    rts/rti/jmp/bra end a path. Long immediates that point into a code
    region are taken as extra entry points (the indirect jsr (rN) targets);
  * in every code instruction of two words, word B is patched when it holds a
    moved address: a jump/loop target, an absolute or displacement operand,
    or a #> immediate;
  * the routine tables are patched entry by entry.

  * the snapshot's live state: every word of internal X and Y holding an
    address in a moved region (per-voice pointers set by init code that ran
    before the snapshot; on the OT, init runs after relocation instead).
    A value test cannot tell a pointer from data that happens to fall in the
    range, so a live patch is a guess the replay has to confirm.

    python3 tools/harness/md_reference/md_relocate.py --hot <capture dirs,...>
        [--hot-base 0x1000] [--hot-size 2724] [--loopvars 0xc00]
        <capture dir> [profile dirs...]

--hot also moves the hottest code units (by the fetch.txt counts of those
captures, md_replay MD_REPLAY_FETCH=2) into private P at --hot-base, as the
OT's core-0 donor region would hold them (see hot_units).

Writes <capture dir>/reloc.txt, which md_replay --reloc applies:
  M <old start> <old end> <new start>     move a region or a hot unit (end exclusive)
  Z <start> <end>                         wipe a region copy of a hot unit
  V <old> <new>                           move a loop word in Y (--loopvars)
  W <new addr> <value>                    a patched P word at its new place
                                          (or in place, below the regions)
  Q <X|Y> <old start> <old end> <new start>  move the voice records
  I <new start> <new end>                 relocated P-I init span
  X|Y <addr> <value>                      a patched live-state word
With profile dirs, it also checks that every word those runs executed was
found as code (a hole means the descent missed a path).
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DIS = ROOT / "out/md_reference/md_dis"

# Keep the replay harness and the proposed OT image on one address book.  The
# layout is deliberately plain data, so importing it does not pull in build
# machinery or any firmware bytes.
sys.path.insert(0, str(ROOT / "modules/machinedrum"))
from layout import LAYOUT


def allocation(name):
    for region in LAYOUT["allocations"]:
        if region["name"] == name:
            return region
    raise KeyError(f"layout allocation not found: {name}")


HOT_LAYOUT = allocation("hot_code")
WINDOW_LAYOUT = allocation("window_code_tables")
SINE_LAYOUT = allocation("sine")
PI_LAYOUT = allocation("pi_buffers")
VOICE_X_LAYOUT = allocation("voice_x")
VOICE_Y_LAYOUT = allocation("voice_y_records")

# old start, old end (exclusive), new start. The new places sit in the
# emulator's bridged external RAM at 0x30000.., where P, X and Y alias, as
# they do in the OT's shared window.
REGIONS = [
    (0x100000, 0x103DBA, WINDOW_LAYOUT["start"]),  # engine code and E12 descriptors (0x103d7b)
    (0x140000, 0x148000, SINE_LAYOUT["start"]),    # the 32K sine/table source span
]
LOOP = (0x64, 0xE8)
TABLES = [(0x145AF5, 193), (0x145BB6, 193), (0x145C77, 193)]
# The MD calls this straight-line boot sequence before it enters the voice
# loop.  It is not reachable from the render tables, so it must be an
# explicit descent root for its #> operands to be relocated.
INIT_ENTRY = 0x100057

CC = "(cc|hs|ge|ne|pl|nn|ec|lc|gt|cs|lo|lt|eq|mi|nr|es|ls|le)"
END = re.compile(r"^(rts|rti|jmp|bra|illegal|stop|debug)$")
BRANCH = re.compile(rf"^(b{CC}|j{CC}|bs{CC}|js{CC}|bsr|jsr|brclr|brset|bsclr|bsset|jclr|jset|jsclr|jsset|bra|jmp)$")


# With --hot: old word address -> new address in private P for the hot
# units (see hot_units), which move separately from their region.
HOT = {}


def moved(a):
    if a in HOT:
        return HOT[a]
    # These are layout-relative data bases used by the boot init, not code
    # regions.  in_code_region() below deliberately does not treat them as
    # descent roots.
    if a == 0x135600:
        return PI_LAYOUT["start"]
    if a == 0x148000:
        return SINE_LAYOUT["start"]
    for s, e, n in REGIONS:
        if s <= a < e:
            return n + (a - s)
    return None


def in_code_region(a):
    return (any(s <= a < e for s, e, _ in REGIONS) or a in HOT or
            LOOP[0] <= a < LOOP[1])


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


def hot_units(code, fetch_dirs, base, size):
    """Split the code into units that can move on their own, and pick the
    ones that carry the most fetches into `size` words at `base`.

    A unit is joined across a fall-through (unless the instruction before
    ends the path) and across every one-word PC-relative branch (b..., dor),
    whose short displacement cannot be patched. Absolute operands (j..., do, #>, tables)
    are patched through moved(), so they may cross units freely. Fetch counts
    come from md_replay MD_REPLAY_FETCH=2 (fetch.txt, per capture); each
    capture counts as its share of its own fetches."""
    parent = {a: a for a in code}

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def join(a, b):
        if a in parent and b in parent:
            parent[find(a)] = find(b)

    for a, (ln, wa, wb, text) in code.items():
        op = text.split()[0] if text else ""
        if not END.match(op) and a + ln in code:
            join(a, a + ln)
        # A one-word relative branch has a short displacement that cannot
        # be patched; a two-word one is re-pointed in main().
        if ln == 1 and relative(op):
            for t in targets(text):
                join(a, t)
    units = {}
    for a in code:
        units.setdefault(find(a), []).append(a)

    # Fetches per capture and unit (the captures run equally long, so the
    # totals compare). Greedy: each step takes the unit that most lowers the
    # sum of squared remaining fetches per word it costs, which works on
    # whichever kit is worst at that point.
    per = []
    for d in fetch_dirs:
        f = {}
        for l in (Path(d) / "fetch.txt").read_text().splitlines():
            pc, _, w = l.split()
            pc = int(pc, 16)
            if pc in parent:
                r = find(pc)
                f[r] = f.get(r, 0) + int(w)
        per.append(f)
    sizes = {r: max(a + code[a][0] for a in m) - min(m) for r, m in units.items()}
    rem = [sum(f.values()) for f in per]
    start_rem = list(rem)
    candidates = {r for f in per for r in f}
    chosen, used = [], 0
    while True:
        best, best_score = None, 0.0
        for r in candidates:
            if used + sizes[r] > size:
                continue
            gain = sum(rem[i] ** 2 - (rem[i] - f.get(r, 0)) ** 2 for i, f in enumerate(per))
            score = gain / sizes[r]
            if score > best_score:
                best, best_score = r, score
        if best is None:
            break
        chosen.append(best)
        candidates.discard(best)
        used += sizes[best]
        rem = [rem[i] - f.get(best, 0) for i, f in enumerate(per)]
    moves = []
    at = base
    for r in sorted(chosen, key=lambda r: min(units[r])):
        start = min(units[r])
        end = max(a + code[a][0] for a in units[r])
        for a in range(start, end):
            HOT[a] = at + (a - start)
        moves.append((start, end, at))
        at += end - start
    big = sorted(sizes.values(), reverse=True)[:5]
    print(f"hot: {len(units)} units (largest {big} words); chose {len(chosen)}, {at - base} words at "
          f"{base:04x}; fetches left per capture: "
          + ", ".join(f"{100 * r / max(s0, 1):.0f}%" for r, s0 in zip(rem, start_rem)))
    return moves


def main():
    args = sys.argv[1:]
    hot_dirs = []
    hot_base = HOT_LAYOUT["start"]
    hot_size = HOT_LAYOUT["words"]
    # --loopvars remains as a compatibility override for old experiments;
    # normal runs consume the proposed layout without needing the flag.
    loopvars = LAYOUT["driver"]["loopvars"]
    while args and args[0].startswith("--"):
        flag = args.pop(0)
        if flag == "--hot":
            hot_dirs = args.pop(0).split(",")
        elif flag == "--hot-base":
            hot_base = int(args.pop(0), 0)
        elif flag == "--hot-size":
            hot_size = int(args.pop(0), 0)
        elif flag == "--loopvars":
            loopvars = int(args.pop(0), 0)
    sys.argv = [sys.argv[0]] + args
    cap = Path(sys.argv[1])
    snap = cap / "snapshot.bin"
    P = memoryview(snap.read_bytes()).cast("I")
    table = decode(snap)

    entries = {LOOP[0], INIT_ENTRY}
    for base, n in TABLES:
        for i in range(n):
            v = P[base + i]
            if in_code_region(v):
                entries.add(v)
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
            if END.match(op) and "(r" not in text.split(None, 1)[-1]:
                break
            if END.match(op):
                break
            a += ln

    hot_moves = hot_units(code, hot_dirs, hot_base, hot_size) if hot_dirs else []

    patches = {}
    kinds = {}
    for a, (ln, wa, wb, text) in code.items():
        if ln != 2:
            continue
        m = moved(wb)
        if m is None:
            continue
        kind = ("target" if BRANCH.match(text.split()[0]) else
                "loop" if text.startswith(("do", "dor")) else
                "imm" if "#>$" in text else
                "disp" if re.search(r"\(r\d[+-]\$", text) else "abs")
        kinds[kind] = kinds.get(kind, 0) + 1
        patches[a + 1] = m
    # Two-word relative branches (target = own address + word B) whose source
    # and target now move by different offsets.
    for a, (ln, wa, wb, text) in code.items():
        op = text.split()[0] if text else ""
        if ln != 2 or not relative(op):
            continue
        disp = wb - 0x1000000 if wb & 0x800000 else wb
        if op == "dor":
            # Word B is LA - PC (LA the loop's last word); the disassembler
            # prints LA + 1, as it does for do.
            t = [a + disp]
        else:
            t = targets(text)
        if not t or t[0] - a != disp:
            sys.exit(f"{a:06x} {text}: relative target does not decode as own address + word B")
        na, nt = moved(a), moved(t[0])
        na = a if na is None else na
        nt = t[0] if nt is None else nt
        if nt - na != disp:
            patches[a + 1] = (nt - na) & 0xFFFFFF
            kinds["rel"] = kinds.get("rel", 0) + 1
    for base, n in TABLES:
        for i in range(n):
            m = moved(P[base + i])
            if m is not None:
                patches[base + i] = m
                kinds["table"] = kinds.get("table", 0) + 1

    # The layout's loopvars: the loop's own Y words (the render buffer y:$140, the
    # record base y:$141, the slot y:$142, and each slot's engine at
    # y:$153+slot) move to base..base+2 and base+$10..; the engines reach
    # y:$140 and y:$142 through long absolute operands only (checked: 3 and
    # 10 sites; y:$141 and y:$153+ only from the loop, which the driver
    # replaces).
    ymove = {}
    if loopvars is not None:
        ymove = {0x140: loopvars, 0x141: loopvars + 1, 0x142: loopvars + 2}
        ymove.update({0x153 + i: loopvars + 0x10 + i for i in range(16)})
        for a, (ln, wa, wb, text) in code.items():
            if ln != 2 or LOOP[0] <= a < LOOP[1]:
                continue
            for m in re.findall(r"y:>\$([0-9a-f]+)\b", text):
                v = int(m, 16)
                if v in ymove and wb == v:
                    patches[a + 1] = ymove[v]
                    kinds["loopvar"] = kinds.get("loopvar", 0) + 1

    # The boot sequence is called after the relocation on the OT.  Keep the
    # original arithmetic and loop structure, but rebase its absolute
    # destinations to the proposed voice/sine/P-I allocations.  The P-I
    # count is the proposed six-voice cap (6 * 0x600), so this is a capacity
    # relocation, not a second hand-written init implementation.
    init_patches = {
        INIT_ENTRY: VOICE_Y_LAYOUT["start"],
        0x10005F: PI_LAYOUT["start"],
        0x100063: PI_LAYOUT["words"],
        0x100069: SINE_LAYOUT["start"],
    }
    for a, value in init_patches.items():
        if a in code and code[a][0] == 2:
            patches[a + 1] = value
            kinds["init"] = kinds.get("init", 0) + 1

    live = []
    X = P[0x150000:0x170000]
    Y = P[0x170000:0x190000]
    for area, mem in (("X", X), ("Y", Y)):
        for i, v in enumerate(mem):
            m = moved(v)
            if m is not None:
                live.append((area, i, m))
    # Not the working RAM above the moved regions (0x148000..): a scan there
    # "found" 60 pointers in c10 that were two curve tables (step ~0x63c)
    # crossing the code ranges, and patching them broke single samples.
    kinds["live"] = len(live)

    words = set()
    for a, (ln, *_rest) in code.items():
        words.update(range(a, a + ln))
    print(f"code: {len(code)} instructions, {len(words)} words, from {len(entries)} entry points")
    print("patches: " + ", ".join(f"{k} {v}" for k, v in sorted(kinds.items())))

    if len(sys.argv) > 2:
        sys.path.insert(0, str(Path(__file__).parent))
        import md_analyze as A
        asm = A.load_asm("dsp_1.asm")
        executed = set()
        for d in sys.argv[2:]:
            for f in Path(d).glob("*.producer.txt"):
                _, b = A.load(f)
                executed |= {w for w in A.words(b, asm) if in_code_region(w)}
        holes = sorted(executed - words)
        print(f"executed words in the code regions: {len(executed)}, not found as code: {len(holes)}"
              + (" e.g. " + " ".join(f"{h:06x}" for h in holes[:12]) if holes else ""))

    with (cap / "reloc.txt").open("w") as f:
        for s, e, n in REGIONS:
            f.write(f"M {s:06x} {e:06x} {n:06x}\n")
        for s, e, n in hot_moves:
            f.write(f"M {s:06x} {e:06x} {n:06x}\n")
        f.write(f"Q X 000800 000c00 {VOICE_X_LAYOUT['start']:06x}\n")
        f.write(f"Q Y 000800 000c00 {VOICE_Y_LAYOUT['start']:06x}\n")
        f.write(f"I {PI_LAYOUT['start']:06x} {PI_LAYOUT['start'] + PI_LAYOUT['words']:06x}\n")
        # The region copies of the hot units are dead: wipe them, so a
        # reference that still reaches them shows.
        for s, e, n in hot_moves:
            for rs, re_, rn in REGIONS:
                if rs <= s < re_:
                    f.write(f"Z {rn + s - rs:06x} {rn + e - rs:06x}\n")
        for a, v in sorted(patches.items()):
            f.write(f"W {moved(a) if moved(a) is not None else a:06x} {v:06x}\n")
        for area, a, v in live:
            f.write(f"{area} {a:06x} {v:06x}\n")
        for old_, new_ in sorted(ymove.items()):
            f.write(f"V {old_:06x} {new_:06x}\n")
    print(f"wrote {cap / 'reloc.txt'}")


if __name__ == "__main__":
    main()
