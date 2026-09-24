#!/usr/bin/env python3
"""The flip audit: which of the Machinedrum's external data can leave the window.

    python3 tools/harness/md_reference/md_flip.py <access.txt> [...] [--init <access.txt>]
    python3 tools/harness/md_reference/md_flip.py --static

The core-1 direction (MACHINEDRUM_MACHINE.md section 12, "Core 1's memory and
the MD's full footprint") moves the tables and P-I buffers into core 1's
private memory "by flipping those reads from X to Y in the relocated code,
where the instruction form allows it". This decides where the form allows it.

The MD's external RAM is one memory seen through P, X and Y; the OT's shared
window is too, but the OT's private X and Y are separate memories. So a block
of data can leave the window only if, after the flips, every instruction that
touches it does so through one space. Each access.txt comes from md_replay's
MD_REPLAY_ACCESS (md_reads.sh runs it on a capture): every data read and
write by the PC that made it, and the executed PCs. --init adds the boot
init's accesses (MD_REPLAY_INIT_ONLY), which the replay never runs.

Instruction forms come from the emulator's own decode tables (md_forms prints
the OpcodeInfo pattern, the names are read back from opcodeinfo.h):

  twin   the other space's form has the same fields, one fixed bit apart
         (Movex_ea/Movey_ea, the short-absolute and both displaced moves, and
         every form whose S bit names the ea's space). Same length and cycle
         class; the flipped word is decoded again to confirm the twin.
  split  X:R or R:Y: the other space's form moves a different register pair.
  dual   Movexy: the other half of the move is fixed in the other space.
  long   Movel: X and Y at one address.
  split, dual and long have no one-bit twin. Splitting one into two
  single-space moves is a rewrite: one more instruction per execution.

The model. A node is a data region: a maximal run of external words that are
accessed as data or are loaded non-code table words (md_reads.py's tables), or
one of the fixed blocks (the P-I buffers, the E12 block), plus internal X and
internal Y, which stay in their own space. A site is one instruction's
accesses in one space. An instruction links every region it touches: it has
one space. For a group of linked regions and a target space T, a site can
take T when it already uses T, or when it is a twin that touches no internal
memory (flipping it would move the internal access too). Every region a site
touches that cannot take T goes to the window; the rest go to private T. The
sine is in the window by decision (a 32K modulo buffer, read through X and Y)
and links nothing. A pointer that runs past its table (stray words: see
STRAY_WORDS) links nothing either. Each group gets four options (X or Y,
with or without rewriting its split/dual sites into single-space moves, which
costs one instruction per execution); groups are placed largest first, taking
the option with the fewest window words, then the lowest rewrite rate, then
the fewest flips, whose regions pack best fit into core 1's free spans
(layout.table_spans), each at its old alignment.

A verdict is only as good as the captures: an instruction no capture ran says
nothing about its targets. The static census at the end counts the reachable
X-space instructions that never ran, by class.
"""

from __future__ import annotations

import collections
import pathlib
import re
import runpy
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools" / "build"))
sys.path.insert(0, str(ROOT / "tools" / "verify"))
import md_payload as payload  # noqa: E402
from verify_md_layout import reachable_code  # noqa: E402

FORMS = ROOT / "out/md_reference/md_forms"
DIS = ROOT / "out/md_reference/md_dis"
OPCODEINFO = [ROOT / "vendor/gearmulator-md-mm/source/dsp56300/source/dsp56kEmu/opcodeinfo.h",
              ROOT / "vendor/dsp56300/source/dsp56kEmu/opcodeinfo.h"]
STOCK = [ROOT / "out/dsp/payload_A.asm", ROOT / "out/dsp/payload_B.asm"]

SPANS = ((0x100000, 0x103DBA), (0x140000, 0x148000))
EXT = (0x100000, 0x150000)
SINE = (0x148000, 0x150000)
PI = (0x135600, 0x13B600)
E12 = (0x103DBA, 0x135206)
E12_TAIL = (0x135206, 0x135406)  # four writable 128-word E12 buffers
SAMPLE_META = (0x147E00, 0x148000)  # descriptor table and writable metadata
INTERNAL = 0x10000

TWIN_XY = {"Movex_ea": "Movey_ea", "Movex_aa": "Movey_aa",
           "Movex_Rnxxxx": "Movey_Rnxxxx", "Movex_Rnxxx": "Movey_Rnxxx"}
TWIN_XY.update({v: k for k, v in list(TWIN_XY.items())})
S_SPACE = re.compile(r"^(Bclr|Bset|Bchg|Btst|Jclr|Jset|Jsclr|Jsset|Brclr|Brset|Bsclr|Bsset)_(ea|aa)$"
                     r"|^(Do|Dor|Rep)_(ea|aa)$|^Movec_(ea|aa)$|^Movep_(ppea|Xqqea|Yqqea|eaqq)$")
SPLIT = {"Movexr_ea", "Moveyr_ea", "Movexr_A", "Moveyr_A"}
DUAL = {"Movexy"}
LONG = {"Movel_ea", "Movel_aa"}
REP_NO_OPERAND = {"Rep_xxx", "Rep_S"}
STRAY_WORDS, STRAY_RATIO = 64, 8
# Core 1's table ground comes from the layout (modules/machinedrum/layout.py):
# the voice records and the driver's storage are allocations of their own, so
# the spans here are what is left for tables. A table is addressed as base
# plus index, so it needs one contiguous span; it keeps its old alignment
# (see align_of) in case it is also a modulo buffer.
sys.path.insert(0, str(ROOT / "modules" / "machinedrum"))
import layout as md_layout  # noqa: E402
# 0x200: the P-I buffers' measured modulo (m2 = $1ff); the sine's 32K is
# placed by the layout, not packed.
ALIGN_MAX_BITS = 9
MERGE_GAP = 0x200
ASM = ROOT / "vendor/dsp56300/build/source/dsp_host/dsp_asm"

NAMES = {}
PATTERN = {}


def die(message):
    raise SystemExit(f"md-flip: {message}")


def load_names():
    for path in OPCODEINFO:
        if path.exists():
            text = path.read_text(errors="replace")
            for m in re.finditer(r'OpcodeInfo\((\w+),\s*"([01a-zA-Z?]{24})"', text):
                NAMES.setdefault(m.group(2), m.group(1))
            PATTERN.update({v: k for k, v in NAMES.items()})
            return
    die("no opcodeinfo.h (vendor/gearmulator-md-mm or vendor/dsp56300)")


def field(pat, word, ch):
    value = n = 0
    for i, c in enumerate(pat):
        if c == ch:
            value = value << 1 | (word >> (23 - i) & 1)
            n += 1
    return value if n else None


def forms(words):
    """{key: (name, pattern)} for {key: word}, via md_forms."""
    if not FORMS.exists():
        die(f"missing {FORMS}; build the md_forms target (md_profile.cmake)")
    lines = "".join(f"{k:x} {w:06x}\n" for k, w in words.items())
    out = subprocess.run([str(FORMS)], input=lines, capture_output=True, text=True, check=True).stdout
    res = {}
    for line in out.splitlines():
        k, _w, np_, mv, _alu = line.split()
        pat = np_ if np_ != "-" else mv
        res[int(k, 16)] = (NAMES.get(pat, "?"), pat)
    return res


def classify(name):
    if name in TWIN_XY or S_SPACE.match(name):
        return "twin"
    if name in SPLIT:
        return "split"
    if name in DUAL:
        return "dual"
    if name in LONG:
        return "long"
    return None


def flipped(name, pat, word):
    """The word with its X/Y space bit flipped (twins only)."""
    if name in TWIN_XY:
        other = PATTERN[TWIN_XY[name]]
        mask = 0
        for i, (c, d) in enumerate(zip(pat, other)):
            if c != d:
                if c not in "01" or d not in "01":
                    die(f"{name}/{TWIN_XY[name]}: fields differ at bit {23 - i}")
                mask |= 1 << (23 - i)
        return word ^ mask
    return word ^ (1 << (23 - pat.index("S")))


def form_key(name, pat, word):
    """Form, direction and ea space: the unit of stock precedent."""
    key = name
    w = field(pat, word, "W")
    if w is not None:
        key += ".r" if w else ".w"
    if S_SPACE.match(name):
        key += ".Y" if field(pat, word, "S") else ".X"
    return key


def stock_forms():
    words = {}
    for path in STOCK:
        if not path.exists():
            die(f"missing {path}; run tools/build/dsp_disasm_all.py")
        for line in path.read_text().splitlines():
            m = re.match(r"^([0-9a-f]{6}): (\S+).*; ([0-9a-f]{6})(?: [0-9a-f]{6})?\s*$", line)
            if m and m.group(2) != "dc":
                words[len(words)] = int(m.group(3), 16)   # the payloads overlap in address
    count = collections.Counter()
    for k, (name, pat) in forms(words).items():
        count[form_key(name, pat, words[k])] += 1
    return count


def runs(addresses):
    out = []
    for a in sorted(addresses):
        if out and out[-1][1] == a:
            out[-1][1] = a + 1
        else:
            out.append([a, a + 1])
    return out


def align_of(address):
    """The alignment a moved region keeps: the largest power of two dividing
    its old start, up to 2^ALIGN_MAX_BITS (a modulo buffer needs its base
    aligned to the power of two above its size)."""
    if address == 0:
        return 1 << ALIGN_MAX_BITS
    return 1 << min((address & -address).bit_length() - 1, ALIGN_MAX_BITS)


def assemble(lines):
    """dsp_asm the lines at P:0, one word each; returns the words."""
    with tempfile.TemporaryDirectory(prefix="md-flip-asm-") as d:
        src, out = pathlib.Path(d) / "s.asm", pathlib.Path(d) / "s.bin"
        src.write_text("".join(line + "\n" for line in lines))
        r = subprocess.run([str(ASM), "-in", str(src), "-org", "0", "-out", str(out)],
                           capture_output=True, text=True)
        if r.returncode or not out.exists():
            die("dsp_asm failed: " + r.stdout + r.stderr)
        blob = out.read_bytes()
    words = [blob[i] | blob[i + 1] << 8 | blob[i + 2] << 16 for i in range(0, len(blob), 3)]
    if len(words) != len(lines):
        die(f"dsp_asm gave {len(words)} words for {len(lines)} one-word moves")
    return words


REGS = {"a": {"a"}, "a0": {"a"}, "a1": {"a"}, "a2": {"a"}, "b": {"b"}, "b0": {"b"}, "b1": {"b"},
        "b2": {"b"}, "x": {"x0", "x1"}, "y": {"y0", "y1"}, "x0": {"x0"}, "x1": {"x1"},
        "y0": {"y0"}, "y1": {"y1"}}


def regs(text):
    """The data-ALU registers named in an operand list (address registers
    of an ea are not data)."""
    out = set()
    for tok in re.split(r"[,\s]+", re.sub(r"[xyl]:\([^)]*\)[+-]?(n\d)?", "", text)):
        out |= REGS.get(tok.strip("-"), set())
    return out


def split_dual(word, text, target):
    """A parallel move of two halves (XY dual, or X:R/R:Y) as two
    instructions, each memory half in the space its data now lives in
    (target: {"X": space, "Y": space}). In the original every read sees the
    old registers; so the half that goes first may write nothing the second
    instruction reads, and the half that goes second may read nothing the
    first one wrote. The ALU op rides with one half. Returns the two moves
    (as "move" operand text, the ALU op re-attached by the caller), which
    half carries the ALU, and dies when no order keeps the semantics."""
    ops = text.split()
    alu = None if ops[0] == "move" else ops[:2]
    moves = ops[1:] if alu is None else ops[2:]
    if len(moves) != 2:
        die(f"not a two-half parallel move: {text}")
    halves = []
    for m in moves:
        src, dst = m.split(",", 1)
        if ":" in m:
            space = "X" if m.lower().startswith("x:") or ",x:" in m else "Y"
            m = m.replace(space.lower() + ":", target[space].lower() + ":")
        halves.append({"text": m, "reads": regs(src) if ":" not in src else set(),
                       "writes": regs(dst) if ":" not in dst else set()})
    alu_reads = regs(alu[1]) if alu else set()
    alu_writes = regs(alu[1].split(",")[-1]) if alu else set()
    for alone in (0, 1):
        other = halves[1 - alone]
        with_alu = {"reads": alu_reads | other["reads"], "writes": alu_writes | other["writes"]}
        # alone first, then ALU + other
        if not halves[alone]["writes"] & with_alu["reads"]:
            return [halves[alone]["text"], other["text"]], 1
        # ALU + other first, then alone
        if not halves[alone]["reads"] & with_alu["writes"]:
            return [other["text"], halves[alone]["text"]], 0
    die(f"no order of the two halves keeps the semantics: {text}")


def disassemble(snapshot, pcs):
    out = {}
    ranges = [f"{s:x}-{e:x}" for s, e in runs(pcs)]
    for i in range(0, len(ranges), 200):
        text = subprocess.run([str(DIS), str(snapshot)] + ranges[i:i + 200],
                              capture_output=True, text=True, check=True).stdout
        for line in text.splitlines():
            a, ln, wa, _wb, t = line.split(" ", 4)
            out[int(a, 16)] = (int(ln), int(wa, 16), t.strip())
    return out


def widen(words, code, dis, executed, code_words):
    """The table words, widened where the evidence says a table goes on.

    The static descent reads some table words as code, so a table can come
    out as fragments with never-executed "code" between them, and an engine
    can address a table from a base that sits in such words (add #>$145224,a
    with the reads from 0x145324 on). Moved apart, fragments and bases lose
    their offsets. So: merge two runs when every word between them is
    never executed (at most MERGE_GAP), and take in a base that code which
    runs names in word B (an immediate, a displacement, an absolute address)
    when every word between it and the table is never executed (the same
    limit). Nothing that ran is ever taken in. What a widening swallows that
    the descent called an instruction start and some code branches to is
    listed: a path the kits did not take would be data here."""
    words = set(words)
    table_spans = [(lo, hi) for lo, hi in SPANS]

    def spans_of(a):
        return next(((lo, hi) for lo, hi in table_spans if lo <= a < hi), None)

    def quiet(lo, hi):
        return hi - lo <= MERGE_GAP and not any(a in code_words for a in range(lo, hi))

    added = set()
    rs = runs(words)
    for (a, b), (c, d) in zip(rs, rs[1:]):
        if spans_of(a) and spans_of(a) == spans_of(c) and quiet(b, c):
            added.update(range(b, c))
    words |= added
    bases = set()
    for pc in executed:
        if pc not in code or code[pc][0] != 2:
            continue
        text, wb = code[pc][3], code[pc][2]
        op = text.split()[0] if text else ""
        if text.startswith("do") or re.match(r"^(j|b)", op) or wb in words or not spans_of(wb):
            continue
        bases.add(wb)
    for v in sorted(bases):
        rs = runs(words)
        above = next(((lo, hi) for lo, hi in rs if lo > v and spans_of(lo) == spans_of(v)), None)
        below = next(((lo, hi) for lo, hi in reversed(rs) if hi <= v and spans_of(lo) == spans_of(v)), None)
        if above and quiet(v, above[0]):
            words.update(range(v, above[0]))
            added.update(range(v, above[0]))
        elif below and quiet(below[1], v + 1):
            words.update(range(below[1], v + 1))
            added.update(range(below[1], v + 1))
    swallowed = sorted(a for a in added if a in code)
    branched = {t for a, (ln, wa, wb, text) in code.items() for t in
                [int(m, 16) for m in re.findall(r"(?:func|int|label|loc)_([0-9a-f]{6})", text)]}
    print(f"table widening: {len(added):,} never-executed words taken in "
          f"({len(swallowed):,} instruction starts of the static descent)")
    hit = [a for a in swallowed if a in branched]
    if hit:
        print("  WARNING: branch targets taken in as data: " + " ".join(f"{a:06x}" for a in hit[:16]))
    return sorted(words)


def disassemble_words(snapshot_like, words):
    """The disassembler's text for loose words (placed at P:0 of a scratch
    snapshot)."""
    import array
    with tempfile.TemporaryDirectory(prefix="md-flip-dis-") as d:
        snap = pathlib.Path(d) / "s.bin"
        mem = [0] * 0x150000
        mem[:len(words)] = words
        snap.write_bytes(array.array("I", mem).tobytes())
        out = disassemble(snap, set(range(len(words))))
    return [out[i][2] for i in range(len(words))]


class Captures:
    """The union of the access files, per site."""

    def __init__(self, paths, init_path):
        self.blocks = {}                  # capture -> blocks replayed
        self.executed = set()
        self.keys = collections.defaultdict(lambda: {"spans": [], "count": collections.Counter()})
        self.snapshot = None
        for path in paths + ([init_path] if init_path else []):
            path = pathlib.Path(path)
            cap = "init" if path == pathlib.Path(init_path or "") else path.parent.name
            if self.snapshot is None and (path.parent / "snapshot.bin").exists():
                self.snapshot = path.parent / "snapshot.bin"
            for line in path.read_text().splitlines():
                if line.startswith("# blocks"):
                    self.blocks[cap] = int(line.split()[2])
                    continue
                if line.startswith("#"):
                    continue
                if line.startswith("E "):
                    _e, lo, hi = line.split()
                    self.executed.update(range(int(lo, 16), int(hi, 16)))
                    continue
                pc, space, rw, lo, hi, count = line.split()
                k = self.keys[(int(pc, 16), space, rw)]
                k["spans"].append((int(lo, 16), int(hi, 16)))
                k["count"][cap] = int(count)
        if self.snapshot is None:
            die("no capture snapshot next to any access file")


def main() -> int:
    args = sys.argv[1:]
    init_path = None
    if "--init" in args:
        i = args.index("--init")
        init_path = args[i + 1]
        del args[i:i + 2]
    plan_path = None
    if "--plan" in args:
        i = args.index("--plan")
        plan_path = args[i + 1]
        del args[i:i + 2]
    static_only = "--static" in args
    paths = [a for a in args if not a.startswith("--")]
    if not paths and not static_only:
        print(__doc__)
        return 2
    load_names()

    _ns, _update, records = payload.unpack_update(None)
    raw, source = payload.source_maps(records)
    relocator = runpy.run_path(str(ROOT / "tools/harness/md_reference/md_relocate.py"))
    with tempfile.TemporaryDirectory(prefix="md-flip-") as temporary:
        snapshot = pathlib.Path(temporary) / "snapshot.bin"
        payload.write_snapshot(source, snapshot)
        code = reachable_code(snapshot, relocator)
    static = forms({a: wa for a, (ln, wa, wb, t) in code.items()})
    stock = stock_forms()

    ran = set()
    if paths:
        caps = Captures(paths, init_path)
        ran = audit(caps, raw, code, stock, plan_path)
    census(code, static, stock, ran, bool(paths))
    return 0


def audit(caps, raw, code, stock, plan_path=None):
    P = memoryview(caps.snapshot.read_bytes()).cast("I")
    pcs = {pc for pc, _s, _rw in caps.keys} | caps.executed
    dis = disassemble(caps.snapshot, pcs)
    form = forms({pc: P[pc] for pc in pcs})

    # A rep'd instruction runs inside the rep's own exec: charge its accesses
    # to the instruction after the rep.
    keys = collections.defaultdict(lambda: {"spans": [], "count": collections.Counter()})
    for (pc, space, rw), k in caps.keys.items():
        if form[pc][0] in REP_NO_OPERAND:
            pc += dis[pc][0]
            if pc not in form:
                form.update(forms({pc: P[pc]}))
                dis.update(disassemble(caps.snapshot, {pc}))
        keys[(pc, space, rw)]["spans"] += k["spans"]
        keys[(pc, space, rw)]["count"].update(k["count"])

    code_words = set()
    for pc in caps.executed:
        code_words.update(range(pc, pc + max(1, dis[pc][0])))

    # Sites: (pc, space) -> words touched, executions per capture.
    site_words = collections.defaultdict(set)
    site_count = collections.defaultdict(collections.Counter)
    site_rw = collections.defaultdict(set)
    for (pc, space, rw), k in keys.items():
        for lo, hi in k["spans"]:
            site_words[(pc, space)].update(range(lo, hi))
        for cap, n in k["count"].items():
            site_count[(pc, space)][cap] = max(site_count[(pc, space)][cap], n)
        site_rw[(pc, space)].add(rw)

    # Regions.
    data = set()
    for words in site_words.values():
        data.update(a for a in words if EXT[0] <= a < EXT[1])
    loaded = {a for values in raw.values() for a in values}
    static_code = set()
    for a, (ln, *_r) in code.items():
        static_code.update(range(a, a + ln))
    for lo, hi in SPANS:
        data.update(a for a in loaded if lo <= a < hi and a not in static_code)
    code_as_data = data & code_words
    region_of = {}
    regions = {}                      # id -> (lo, hi, kind)
    for name, (lo, hi) in (("sine", SINE), ("pi", PI), ("e12", E12)):
        regions[name] = (lo, hi, name)
    for a in data:
        for name, (lo, hi) in (("sine", SINE), ("pi", PI), ("e12", E12)):
            if lo <= a < hi:
                region_of[a] = name
    rest = sorted(a for a in data if a not in region_of and a not in code_as_data)
    rest = widen(rest, code, dis, caps.executed, code_words)
    for lo, hi in runs(rest):
        rid = f"{lo:06x}"
        regions[rid] = (lo, hi, "table" if any(s <= lo < e for s, e in SPANS) else "other")
        for a in range(lo, hi):
            region_of[a] = rid
    for a in code_as_data:
        region_of[a] = "code"
    regions["code"] = (0, 0, "code")

    def node_words(site):
        pc, space = site
        out = collections.Counter()
        for a in site_words[site]:
            if a < INTERNAL:
                out["int" + space] += 1
            elif a in region_of:
                out[region_of[a]] += 1
        return out

    # A stray access: a pointer that ran off its table (the sample reads at
    # 143521/143e84 walk down through every region below theirs). A site's
    # words in a region other than its home (the region it touched most) are
    # stray when they are at most STRAY_WORDS and under 1/STRAY_RATIO of its
    # home words; they link nothing, and are reported.
    site_nodes, strays = {}, {}
    for s in site_words:
        counts = node_words(s)
        home_words = max(counts.values(), default=0)
        keep = {n for n, c in counts.items()
                if c == home_words or c > STRAY_WORDS or c * STRAY_RATIO >= home_words}
        site_nodes[s] = keep
        stray = {n: c for n, c in counts.items() if n not in keep}
        if stray:
            strays[s] = stray
    samples = {cap: 2 * b for cap, b in caps.blocks.items() if b}

    def rate(site):
        return max((n / samples[c] for c, n in site_count[site].items() if c in samples), default=0.0)

    def cls(site):
        return classify(form[site[0]][0])

    def can(site, target, rewrite):
        pc, space = site
        if space == target:
            return True
        if space == "P":
            return False
        c = cls(site)
        movable = c == "twin" or (rewrite and c in ("split", "dual"))
        return movable and not any(n.startswith("int") for n in site_nodes[site])

    # Groups: regions linked by a site (the sine and the code words link nothing).
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for site, ns in site_nodes.items():
        linked = sorted(n for n in ns if n not in ("sine", "code"))
        for n in linked:
            find(n)
        for a, b in zip(linked, linked[1:]):
            parent[find(a)] = find(b)
    groups = collections.defaultdict(set)
    for n in list(parent):
        groups[find(n)].add(n)

    def size(rid):
        lo, hi, kind = regions[rid]
        return hi - lo

    def group_key(g):
        # Largest first; ties by the lowest region address, so runs repeat.
        ext = [n for n in g if not n.startswith("int")]
        return (-sum(size(n) for n in ext if n != "e12"), min((regions[n][0] for n in ext), default=0))

    def option(g, target, rewrite):
        """Target space T for group g: which regions go to the window, the
        words that go to private T, the flips and the rewrites."""
        ext = {n for n in g if not n.startswith("int")}
        sites = [s for s, ns in site_nodes.items() if ns & g]
        window = set()
        for s in sites:
            if not can(s, target, rewrite):
                window |= site_nodes[s] & ext
        kept = ext - window
        flips, rewrites = set(), set()
        for s in sites:
            if s[1] != target and s[1] != "P" and site_nodes[s] & kept:
                (flips if cls(s) == "twin" else rewrites).add(s)
        return {"target": target, "rewrite": rewrite, "window": window, "kept": kept,
                "words": sum(size(n) for n in kept if n != "e12"),
                "window_words": sum(size(n) for n in window if n != "e12"),
                "flips": flips, "rewrites": rewrites,
                "rate": sum(rate(s) for s in rewrites)}

    def place(free, items):
        """Best fit, largest first, each item at its old alignment. free is a
        list of [start, end) spans; items are (region, old start, words).
        Returns (the spans left, {region: new start}), or None."""
        free = [list(f) for f in free]
        at = {}
        for rid, lo, n in sorted(items, key=lambda it: (-it[2], it[1])):
            a = align_of(lo)
            best = None
            for i, (s, e) in enumerate(free):
                start = s + ((lo - s) % a)
                if start + n <= e and (best is None or e - s - n < best[0]):
                    best = (e - s - n, i, start)
            if best is None:
                return None
            _w, i, start = best
            s, e = free.pop(i)
            free += [f for f in ([s, start], [start + n, e]) if f[1] > f[0]]
            at[rid] = start
        return sorted(free), at

    def choose(free):
        """Greedy, largest group first: fewest window words, then the lowest
        rewrite rate, then the fewest flips, placed into the free spans."""
        chosen, at = [], {}

        ordered = sorted((g for g in groups.values() if any(not n.startswith("int") for n in g)),
                         key=group_key)
        for g in ordered:
            options = [option(g, t, r) for r in (False, True) for t in ("X", "Y")]
            options.sort(key=lambda o: (o["window_words"], o["rate"], len(o["flips"]) > 0, o["target"] == "X",
                                        len(o["flips"])))
            pick = None
            for o in options:
                if o["window_words"]:
                    continue    # it would leave a region out; the window is tried next
                got = place(free[o["target"]], [(n, regions[n][0], size(n)) for n in o["kept"] if n != "e12"])
                if got is not None:
                    pick = o
                    free[o["target"]], placed = got
                    at.update(placed)
                    break
            if pick is None:
                # The window's table area: P, X and Y alias there, so the
                # group needs no flip and no rewrite.
                ext = {n for n in g if not n.startswith("int")}
                got = place(free["W"], [(n, regions[n][0], size(n)) for n in ext if n != "e12"])
                if got is not None:
                    free["W"], placed = got
                    at.update(placed)
                    pick = {"target": "W", "rewrite": False, "window": set(), "kept": ext,
                            "words": sum(size(n) for n in ext if n != "e12"), "window_words": 0,
                            "flips": set(), "rewrites": set(), "rate": 0.0}
            if pick is None:
                ext = {n for n in g if not n.startswith("int")}
                pick = {"target": "window", "rewrite": False, "window": ext, "kept": set(), "words": 0,
                        "window_words": sum(size(n) for n in ext if n != "e12"),
                        "flips": set(), "rewrites": set(), "rate": 0.0}
            chosen.append((g, pick))
        return chosen, free, at

    print(f"captures: {len(samples)} ({sum(samples.values()) // 32 * 32:,} samples)"
          + (", plus the boot init" if "init" in caps.blocks or any("init" in k["count"] for k in keys.values()) else ""))
    print(f"instructions with a data access: {len({s[0] for s in site_words}):,}; executed: {len(caps.executed):,}")

    print()
    print("external data by region: words touched through each space (sites)")
    for rid in sorted(regions, key=lambda r: regions[r][0]):
        lo, hi, kind = regions[rid]
        if rid == "code":
            continue
        by = collections.defaultdict(set)
        sites_by = collections.defaultdict(set)
        for s, words in site_words.items():
            for a in words:
                if region_of.get(a) == rid:
                    for rw in site_rw[s]:
                        by[s[1] + rw].add(a)
                        sites_by[s[1] + rw].add(s[0])
        if not by and kind == "table":
            continue
        parts = ", ".join(f"{k} {len(v):,} ({len(sites_by[k])})" for k, v in sorted(by.items()))
        print(f"  {rid:6s} {lo:06x}..{hi - 1:06x} {hi - lo:7,} {kind:5s} {parts or 'unread'}")
    cad = sorted(code_as_data)
    cad_sites = {s[0] for s, w in site_words.items() if w & code_as_data}
    print(f"  stray accesses (a pointer past its table; they link nothing): {len(strays)} sites")
    for s, stray in sorted(strays.items(), key=lambda kv: (-sum(kv[1].values()), kv[0])):
        home_node = max(node_words(s).items(), key=lambda kv: kv[1])
        print(f"    {s[0]:06x} {s[1]} home {home_node[0]} ({home_node[1]:,} words); stray "
              + ", ".join(f"{n} {c}" for n, c in sorted(stray.items(), key=lambda kv: -kv[1])[:6])
              + (" ..." if len(stray) > 6 else ""))
    print(f"  code words read as data: {len(cad):,} words by {len(cad_sites)} instructions"
          f" ({', '.join(f'{p:06x}' for p in sorted(cad_sites)[:8])}{' ...' if len(cad_sites) > 8 else ''})")

    # The MD's own internal footprint also lives in core 1's private memory.
    internal = {"X": set(), "Y": set()}
    for s, words in site_words.items():
        if s[1] in internal and "int" + s[1] in site_nodes[s]:
            internal[s[1]].update(a for a in words if a < INTERNAL)
    print()
    print(f"the MD's internal data touched: X {len(internal['X']):,} words, Y {len(internal['Y']):,} words"
          " (the voice records, state and buffers; they keep their space)")

    print()
    print("groups (regions one instruction links), and each option: words to private T / to the window,"
          " flips, rewrites (executions per sample, summed over sites' worst kits)")
    for g in sorted(groups.values(), key=group_key):
        ext = sorted((n for n in g if not n.startswith("int")), key=lambda n: regions[n][0])
        if not ext:
            continue
        pins = sorted(n for n in g if n.startswith("int"))
        print(f"  {', '.join(ext[:6])}{' ...' if len(ext) > 6 else ''}"
              f" ({sum(size(n) for n in ext if n != 'e12'):,} words{', links ' + '+'.join(pins) if pins else ''})")
        for r in (False, True):
            parts = []
            for tgt in ("X", "Y"):
                o = option(g, tgt, r)
                parts.append(f"{tgt}: {o['words']:,}/{o['window_words']:,} w, {len(o['flips'])} flips"
                             + (f", {len(o['rewrites'])} rewrites {o['rate']:.1f}/smp" if r else ""))
            print(f"    {'rewrite' if r else 'flips  '}  " + " | ".join(parts))

    spans = {s: md_layout.table_spans(s) for s in ("X", "Y", "W")}
    chosen, free, at = choose({s: list(v) for s, v in spans.items()})
    home = {}
    for g, o in chosen:
        for n in o["kept"]:
            home[n] = o["target"]
        for n in o["window"]:
            home[n] = "window"
    print()
    print("plan within core 1's private memory (layout.table_spans): "
          + "; ".join(f"{s} " + ", ".join(f"{a:04x}..{b - 1:04x} ({b - a:,})" for a, b in v)
                      for s, v in spans.items()))
    print("  left free: " + "; ".join(f"{s} " + ", ".join(f"{b - a:,}" for a, b in sorted(v, key=lambda f: f[0] - f[1]))
                                      for s, v in free.items()))
    total = collections.Counter()
    for n, h in home.items():
        if n != "e12":
            total[h] += size(n)
    print("  words by home (E12 is a stream buffer and is left out; the sine's 32,768 are in the window): "
          + ", ".join(f"{h} {v:,}" for h, v in sorted(total.items())))
    for rid in sorted(home, key=lambda r: regions[r][0]):
        lo, hi, kind = regions[rid]
        if kind in ("pi", "e12") or size(rid) >= 256:
            print(f"    {rid:6s} {lo:06x}..{hi - 1:06x} {hi - lo:7,} -> {home[rid]}"
                  + (f" {at[rid]:04x}" if rid in at else ""))
    small = collections.Counter()
    for rid, h in home.items():
        if regions[rid][2] not in ("pi", "e12") and size(rid) < 256:
            small[h] += size(rid)
    if small:
        print("    smaller regions: " + ", ".join(f"{h} {n:,}" for h, n in sorted(small.items())))
    rewrites = set().union(*(o["rewrites"] for _g, o in chosen))
    flips = set().union(*(o["flips"] for _g, o in chosen))
    cost = collections.Counter()
    for s in rewrites:
        for c, n in site_count[s].items():
            if c in samples:
                cost[c] += n / samples[c]
    worst = max(cost.items(), key=lambda kv: kv[1]) if cost else ("-", 0.0)
    print(f"  rewrites: {len(rewrites)} instructions split into two single-space moves;"
          f" one more instruction per execution, worst kit {worst[0]}: {worst[1]:.1f} per sample")
    for s in sorted(rewrites, key=lambda s: (-rate(s), s)):
        print(f"    {s[0]:06x} {s[1]} {cls(s):5s} {dis[s[0]][2]:55s} {rate(s):5.2f}/smp")
    need = collections.Counter()
    bad = []
    for s in flips:
        name, pat = form[s[0]]
        w = flipped(name, pat, P[s[0]])
        got = forms({s[0]: w})[s[0]][0]
        if got != TWIN_XY.get(name, name):
            bad.append((s[0], name, got))
        need[form_key(got, PATTERN.get(got, pat), w)] += 1
    print(f"  flips: {len(flips)} instructions, each one bit; their forms after the flip:")
    for k, v in sorted(need.items(), key=lambda kv: -kv[1]):
        print(f"    {k:24s} {v:4d}; stock A+B {stock[k]:5d}" + ("" if stock[k] else "  <-- no stock precedent"))
    for pc, name, got in bad:
        print(f"    FAIL {pc:06x}: {name} flipped decodes as {got}")

    # Instructions no capture ran but whose operand names a moved region
    # outright (a displacement or an absolute address in word B): flip them
    # too, or say they cannot be.
    moved_space = {}
    for rid, h in home.items():
        if h in ("X", "Y") and rid != "e12":
            lo, hi, _k = regions[rid]
            for a in range(lo, hi):
                moved_space[a] = h
    ran_pcs = {s[0] for s in site_words}
    static_flips, unresolved = [], []
    for a, (ln, wa, wb, text) in sorted(code.items()):
        if a in ran_pcs or ln != 2 or wb not in moved_space:
            continue
        name, pat = forms({a: wa})[a]
        c = classify(name)
        if c is None:
            continue
        if name in TWIN_XY:
            space = "X" if name.startswith("Movex") else "Y"
        elif S_SPACE.match(name):
            space = "Y" if field(pat, wa, "S") else "X"
        else:
            space = None
        if space == moved_space[wb]:
            continue
        if c == "twin":
            static_flips.append((a, flipped(name, pat, wa)))
        else:
            unresolved.append((a, text))
    print(f"  flips of instructions no capture ran (operand names a moved region): {len(static_flips)}")
    for a, text in unresolved:
        print(f"    UNRESOLVED {a:06x} {text}: names a moved region, no one-bit twin")

    # The splits, assembled (dsp_asm) with the original ALU byte, and decoded.
    splits = []
    for s in sorted(rewrites):
        pc = s[0]
        target = {}
        for side in ("X", "Y"):
            nodes_ = site_nodes.get((pc, side), set())
            homes = {home[n] for n in nodes_ if n in home and home[n] in ("X", "Y")}
            target[side] = homes.pop() if len(homes) == 1 else side
        texts, alu_half = split_dual(P[pc], dis[pc][2], target)
        words = assemble(["move " + m for m in texts])
        words[alu_half] = (words[alu_half] & 0xFFFF00) | (P[pc] & 0xFF)
        got = forms({i: w for i, w in enumerate(words)})
        for i, w in enumerate(words):
            name = got[i][0]
            if name not in ("Movex_ea", "Movey_ea", "Mover"):
                die(f"split {pc:06x}: half {i} decodes as {name}")
            if (w & 0xFF) != (P[pc] & 0xFF if i == alu_half else 0):
                die(f"split {pc:06x}: half {i} carries the wrong ALU byte")
        shown = disassemble_words(caps.snapshot, words)
        splits.append({"pc": pc, "words": words, "text": shown, "was": dis[pc][2]})
        print(f"    split {pc:06x} {dis[pc][2]:52s} -> {shown[0]} | {shown[1]}")

    if plan_path:
        if any(h == "window" for h in home.values()):
            die("--plan: the plan leaves regions in the window; only the sine may be there")
        plan = {
            "note": "md_flip.py placement plan (WP-A7 / WP-A2, core 1); generated, not an Elektron byte",
            "regions": [{"id": rid, "lo": regions[rid][0], "hi": regions[rid][1], "home": home[rid],
                         "new": at[rid]} for rid in sorted(home, key=lambda r: regions[r][0])
                        if rid != "e12"] +
                       [{"id": "e12_tail", "lo": E12_TAIL[0], "hi": E12_TAIL[1],
                         "home": "W", "new": md_layout.allocation("e12_tail")["start"]},
                         {"id": "sample_meta", "lo": SAMPLE_META[0], "hi": SAMPLE_META[1],
                          "home": "W", "new": md_layout.allocation("sample_meta")["start"]}],
            "note_homes": "X/Y: private, via T lines; W: shared window, via M lines",
            "sine": {"lo": SINE[0], "hi": SINE[1], "new": md_layout.allocation("sine")["start"]},
            "flips": [{"pc": s[0], "word": flipped(*form[s[0]], P[s[0]])} for s in sorted(flips)]
                     + [{"pc": a, "word": w, "static": True} for a, w in static_flips],
            "splits": splits,
            "unresolved": [{"pc": a, "text": t_} for a, t_ in unresolved],
        }
        import json
        pathlib.Path(plan_path).write_text(json.dumps(plan, indent=1))
        print(f"  wrote {plan_path}")

    # Every non-twin site that touches external data, for the record.
    print()
    print("non-twin sites touching external data (other than the sine):")
    rows = []
    for s, ns in site_nodes.items():
        ext = {n for n in ns if not n.startswith("int") and n not in ("sine",)}
        if ext and cls(s) != "twin" and s[1] != "P":
            rows.append((s, ext))
    for s, ext in sorted(rows, key=lambda r: (-rate(r[0]), r[0])):
        pc = s[0]
        others = sorted(site_nodes.get((pc, "Y" if s[1] == "X" else "X"), set()))
        print(f"  {pc:06x} {s[1]} {cls(s) or 'other':5s} {dis[pc][2]:52s} {rate(s):6.2f}/smp"
              f" -> {','.join(sorted(ext))[:40]}" + (f"  [{s[1] == 'X' and 'Y' or 'X'}: {','.join(others)[:24]}]" if others else ""))
    return {s[0] for s in site_words}


def census(code, static, stock, ran, have_runs):
    print()
    print("static census: reachable instructions with an X-space data operand, by class")
    by = collections.defaultdict(lambda: [0, 0])
    for a, (ln, wa, wb, t) in code.items():
        name, pat = static[a]
        c = classify(name)
        if c is None:
            continue
        operands = t.split(None, 1)[-1] if " " in t else ""
        if "x:" not in operands and "l:" not in operands:
            continue
        if S_SPACE.match(name) and field(pat, wa, "S"):
            continue
        by[c][0 if a in ran else 1] += 1
    for c in ("twin", "split", "dual", "long"):
        done, never = by[c]
        print(f"  {c:5s} {done + never:5d}" + (f"   ran with a data access {done:5d}, never ran {never:5d}" if have_runs else ""))

    print()
    print("forms in the MD's reachable code that neither stock payload uses (the hardware-probe list):")
    md = collections.Counter()
    for a, (ln, wa, wb, t) in code.items():
        name, pat = static[a]
        if name in ("Nop", "?"):
            continue
        md[form_key(name, pat, wa)] += 1
    for k, v in sorted(md.items(), key=lambda kv: -kv[1]):
        if not stock[k]:
            print(f"  {k:24s} {v:5d}")


if __name__ == "__main__":
    raise SystemExit(main())
