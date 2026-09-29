#!/usr/bin/env python3
"""MASTER STRIP's pages: under the port, the MIXER window pages the strip.

    python3 tools/verify/verify_mixerpages.py [REMIX]            # default: every remix carrying MASTER STRIP
    OT_PROJECT=<dir> python3 tools/verify/verify_mixerpages.py   # the port runs need a project

modules/strip/strip_ui.s makes LEFT / RIGHT walk the strips (MIXER, MASTER),
UP / DOWN the slots (INS 1, INS 2), A-F turn the shown slot's page-1 knobs
in strip_model and LEVEL turn MAIN on MASTER. Built from the remix, with a
reference image that has the three detour sites' stock bytes put back (the
unit is linked but never reached), on one staged card. Each case is a panel
script (`ot_emu --live-script`: keys and encoders at emulated times) forked
from one load (`--scenario`); the screen is composited from the window
planes as tools/emu/lcd_view.py does.

  mixer     MIXER on the built image is the reference's stock MIXER page but
            for the arrow at the title band's right end: every pixel that
            differs is inside that box, and some do
  back      MIXER, RIGHT, LEFT is the MIXER page again, pixel for pixel: the
            title's frame rows and the arrows go back as a new window has them
  reopen    MIXER, RIGHT, MIXER, MIXER opens on the MIXER page, pixel for pixel
  layers    on MIXER our key layer is registered after the stock one and the
            knobs' layer is not; on MASTER both, in that order, last
  close     from MASTER, each of the stock ways out (MIXER, NO, FUNC + UP):
            the window handle is 0, and neither the unit's layers nor the
            window's own are left in the list (every close is the window's
            close routine 0x4007d274, which the manager also holds as its
            callback; the one LPOP of the window's layer is in it)
  master    MIXER, RIGHT: below the boxes (the MUTE band) the screen is the
            stock page's; there is an arrow at the band's left end and none
            at its right (MASTER is the last strip); both boxes' outlines are
            lit; the stock boxes' edges inside box 2 are gone; the four cells
            the slot's effect does not draw (OXIDE: IN, OUT) are empty
  ins2      DOWN: the six cells are empty, and only the slot's digit on the
            side label differs from INS 1's page
  mute      a trig on MASTER toggles its mute (the MUTE band changes) and
            the page above the band stays MASTER's, pixel for pixel
  knobs     on MASTER, A +10 then +40, B -5 then -20 and LEVEL +10 then +40
            move IN, OUT and MAIN by exactly what A +10 then +40 moves MAIN
            and LEVEL -5 then -20 moves MIX on the reference's stock page: the
            knobs take a stock MIXER knob's step. The screen differs from the
            untouched MASTER page only inside the three value cells, and in
            each of them; slot 2's bytes stay 0
  slots     DOWN then A +10 changes nothing (INS 2 is empty); UP then A +10
            moves INS 1's IN
  dsp       with the DSP (`--dsp`): MASTER, A +10, then OXIDE onto INS 2 in
            its SETUP: core 0's slot 1 record (X:0x7c20) holds the new IN,
            v << 16, and OUT unchanged; slot 2 runs OXIDE (X:0x7c12, the
            same proc as slot 1's) on the defaults its SETUP wrote (X:0x7c30):
            the page's knob and the SETUP's choice reach the DSP
            (verify_strip's record fixture shows a model edit reaching
            MAIN's samples)
  dsp_none  with the DSP: NONE onto INS 1 in its SETUP, and slot 1 is dry
            (X:0x7c10, id and proc 0)

The slot's SETUP (YES on MASTER), against the reference's stock EFFECT 2
SETUP (FUNC + FX2) with DELAY on every track's FX2 (ot_project.set_fx on the
staged copy, every part of every bank):
  su        the list is the unit's (NONE, then the ids core 0 runs, as
            verify_strip reads tail.asm's), the slot's effect's row inverted
            and the other not; the SETUP's key layer is registered last,
            after the MIXER pages' two; the MIXER window stays open under it
  grid      slot 1 poked to DELAY (0x08): A-F to their minimum, then small
            steps, then their maximum, each left to settle, and a turn left
            lifted: every pixel that differs from stock's SETUP after the
            same turns is in the title band or the list, and some in the
            title (the frame, the rule, the six knobs, their names, their
            lift and their value text are stock's); the model holds each
            knob's range end
  choose    UP, YES: NONE onto INS 1, its row inverted, the model's slot 1 id
            and values 0; NO: the SETUP closed (its layer gone), the MIXER
            window open on the empty INS 1 page, which differs from INS 2's
            only in the side label's digit
  choose2   DOWN, YES, DOWN, YES: OXIDE onto INS 2 with its descriptor's
            defaults (IN 48, OUT 80, the rest 0), the screen INS 1's SETUP
            but for the title band; NO: the MASTER page for INS 2 differs
            from INS 1's only in the digit
  su_close  NO then NO, MIXER, FUNC + UP from the SETUP: the MIXER window and
            the SETUP's are closed and no layer of the unit is left; YES,
            NO, YES is the SETUP again, pixel for pixel; YES, NO then A +10
            and +40 steps IN as the MIXER page did before the SETUP opened

MIXERPAGES_KEEP=<dir> keeps the runs there, each case's screen as a PNG.

What it cannot see: a list longer than the window (the strip runs one
insert; the scroll arrows and paging are stock's code paths, not exercised);
the unit's LCD (the port composites the firmware's
window planes; a window the firmware draws another way would not show);
the MKII keymap (the port boots the MKI's; the arrow keys, MIXER and the
trigs are the same codes); a real encoder's acceleration (the port delivers
a delta per event, the same to both images); anything about the audio
beyond the record (verify_strip).
"""
import argparse, contextlib, os, pathlib, re, shutil, struct, subprocess, sys, tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
from remix import registry  # noqa: E402
import verify_dspsite as vds  # noqa: E402
import verify_strip as vst  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/emu"))
import lcd_view  # noqa: E402

KEY = "MASTER STRIP"
CF_BASE = 0x40000400
PLANES = ((0x46c7e0ea, 0x400), (0x46c7d34c, 280), (0x460d1f7b, 0x2800))   # lcd_view's file
CFG = 0x80000000                      # MIX at +0x32, MAIN at +0x35
WINH, LAYERS, STOCK_LAYER = 0x460e7424, 0x460d165c, 0x400d0384
ROM_BASE, ROM_LEN = 0x400b0000, 0x28000
KEYS = dict(NO=0x32, YES=0x31, MIXER=0x30, FUNC=0x2d, UP=0x33, DOWN=0x20, LEFT=0x34, RIGHT=0x21,
            TRIG1=0x00, FX2=0x26)
IN_KNOB, OUT_KNOB, MAIN0 = 48, 80, 64
# Screen boxes (x0, y0, x1, y1), inclusive, screen coordinates (y down): the
# window is at x 10, its surface y up (screen y = 63 - surface y).
RIGHT_ARROW = (108, 0, 117, 8)
LEFT_ARROW = (10, 0, 19, 8)
ABOVE_BAND = (0, 0, 127, 43)          # the title and the boxes; the MUTE band below
VALUES = {"IN": (46, 18, 64, 24), "OUT": (69, 18, 87, 24), "MAIN": (13, 18, 33, 24)}
BOX1, BOX2 = (13, 10, 33, 42), (35, 10, 113, 42)
STOCK_EDGES = (63, 65)                # the stock OUT box's right edge, the AB/CD box's left
RULE_Y = 26                           # box 2's horizontal dotted rule
CELLS = [(44, 11, 66, 25), (68, 11, 89, 25), (91, 11, 112, 25),
         (44, 27, 66, 41), (68, 27, 89, 41), (91, 27, 112, 41)]
DIGIT = (37, 32, 42, 38)              # the side label's last character
# The SETUP window (x 0, stock's): screen x = surface x + 7, y = 63 - surface y.
SU_TITLE = (0, 0, 127, 8)             # the title band
SU_LIST = (10, 9, 58, 61)             # the list, left of the rule at surface x 0x34
SU_ROW = lambda r: (10, 11 + 7 * r, 58, 17 + 7 * r)   # list row r: surface y 46..52 - 7 r
SU_GRID = (60, 9, 127, 61)            # the knobs' grid, right of the rule
DELAY_ID = 0x08
MINS6 = [f"enc {k} -127" for k in range(6)]

fails = 0


def check(label, ok, detail=""):
    global fails
    print(f"  [{'ok' if ok else 'FAIL'}] {label}" + (f"  {detail}" if detail else ""))
    fails += 0 if ok else 1
    return ok


def script(path, steps, tail=800):
    """A panel script: the boot's date prompt answered, then `steps`, then
    `tail` ms."""
    t, out = [1500.0], []

    def at(line, pause):
        out.append(f"{t[0]:.0f} {line}")
        t[0] += pause

    def key(k, pause=250):
        at(f"key {KEYS[k]:#x} down", 20)
        at(f"key {KEYS[k]:#x} up", pause)
    key("NO", 400)
    for s in steps:
        if s.startswith("enc"):
            at(s, 300)
        elif s.startswith("wait "):
            t[0] += int(s[5:])
        elif s.startswith("poke "):             # ot_emu's live-script poke: ADDR=BYTE[;...]
            at(s, 50)
        elif s.startswith("FUNC+"):             # held across the other key's press
            at(f"key {KEYS['FUNC']:#x} down", 100)
            key(s[5:], 100)
            at(f"key {KEYS['FUNC']:#x} up", 250)
        else:
            key(s)
    t[0] += tail
    out.append(f"{t[0]:.0f} quit")
    path.write_text("\n".join(out) + "\n")


def diff(a, b, box=None):
    """Pixels where screens a and b differ (inside box, when given)."""
    x0, y0, x1, y1 = box or (0, 0, 127, 63)
    return [(x, y) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1) if a[y][x] != b[y][x]]


def inside(p, box):
    return box[0] <= p[0] <= box[2] and box[1] <= p[1] <= box[3]


def lit(s, box):
    return sum(s[y][x] for y in range(box[1], box[3] + 1) for x in range(box[0], box[2] + 1))


CASES = {
    # (image, steps)
    "ref_mixer": ("ref", ["MIXER"]),
    "ref_knobs": ("ref", ["MIXER", "enc 0 10", "enc 0 40", "enc 6 -5", "enc 6 -20"]),
    "mixer": ("built", ["MIXER"]),
    "back": ("built", ["MIXER", "RIGHT", "LEFT"]),
    "reopen": ("built", ["MIXER", "RIGHT", "MIXER", "MIXER"]),
    "close": ("built", ["MIXER", "RIGHT", "MIXER"]),
    "close_no": ("built", ["MIXER", "RIGHT", "NO"]),
    "close_fu": ("built", ["MIXER", "RIGHT", "FUNC+UP"]),
    "master": ("built", ["MIXER", "RIGHT"]),
    "ins2": ("built", ["MIXER", "RIGHT", "DOWN"]),
    "mute": ("built", ["MIXER", "RIGHT", "TRIG1"]),
    "knobs": ("built", ["MIXER", "RIGHT", "enc 0 10", "enc 0 40", "enc 1 -5", "enc 1 -20",
                        "enc 6 10", "enc 6 40"]),
    "slots": ("built", ["MIXER", "RIGHT", "DOWN", "enc 0 10", "UP", "enc 0 10"]),
    # the SETUP
    "su1": ("built", ["MIXER", "RIGHT", "YES"]),
    "su_none": ("built", ["MIXER", "RIGHT", "YES", "UP", "YES"]),
    "su_none_no": ("built", ["MIXER", "RIGHT", "YES", "UP", "YES", "NO"]),
    "su2": ("built", ["MIXER", "RIGHT", "DOWN", "YES", "DOWN", "YES"]),
    "su2_no": ("built", ["MIXER", "RIGHT", "DOWN", "YES", "DOWN", "YES", "NO"]),
    "su_nono": ("built", ["MIXER", "RIGHT", "YES", "NO", "NO"]),
    "su_mixer": ("built", ["MIXER", "RIGHT", "YES", "MIXER"]),
    "su_fu": ("built", ["MIXER", "RIGHT", "YES", "FUNC+UP"]),
    "su_again": ("built", ["MIXER", "RIGHT", "YES", "NO", "YES"]),
    "su_knobs": ("built", ["MIXER", "RIGHT", "YES", "NO", "enc 0 10", "enc 0 40"]),
}
# The SETUP's grid against stock's: (steps after the SETUP opens, tail ms).
# Built: slot 1 poked to DELAY, MIXER RIGHT YES; reference: FUNC + FX2.
GRID = {
    "g_min": (MINS6 + ["wait 3000"], 800),
    "g_mid": (MINS6 + ["enc 0 3", "enc 1 4", "enc 2 2", "enc 3 1", "enc 4 5", "enc 5 1", "wait 3000"], 800),
    "g_max": ([f"enc {k} 127" for k in range(6)] + ["wait 3000"], 800),
    "g_lift": (MINS6 + ["wait 3000", "enc 4 5"], 200),     # LOCK turned, still lifted
}
for g, (steps, tail) in GRID.items():
    CASES[g] = ("built", ["MIXER", "RIGHT", "YES"] + steps, tail, "delay")
    CASES["ref_" + g] = ("ref", ["FUNC+FX2"] + steps, tail)


def port(name, built, project, sym):
    import verify_set as vs
    import ot_project as otp
    if not vds.EMU.exists() or not vds.PY.exists():
        print("  [SKIP] port: the ColdFire port (make emu-cf) or the .venv is missing")
        return
    stock = vds.STOCK.read_bytes()
    ref = bytearray(built)
    for d in registry.by_key(KEY).detours:
        o = d.site - CF_BASE
        n = d.pad_to or 6
        ref[o:o + n] = stock[o:o + n]
    lo, hi = sym["strip_xport"], sym["_end"]          # the runtime: the two units and their data
    model = sym["strip_model"]
    keep = os.environ.get("MIXERPAGES_KEEP")
    with (contextlib.nullcontext(keep) if keep else tempfile.TemporaryDirectory(prefix="mixerpages_")) as work:
        work = pathlib.Path(work)
        work.mkdir(parents=True, exist_ok=True)
        (work / "built.bin").write_bytes(bytes(built))
        (work / "ref.bin").write_bytes(bytes(ref))
        proj = work / "src"
        shutil.copytree(pathlib.Path(project).expanduser(), proj,
                        ignore=shutil.ignore_patterns("*.wav", "*.WAV", "*.ot"))
        with contextlib.redirect_stdout(open(os.devnull, "w")):
            for t in range(1, 9):                         # stock's SETUP shows DELAY's page 2
                otp.set_fx(proj, "fx2", t, DELAY_ID, guard=False)
        raw = (proj / "project.work").read_bytes()
        bank = int(re.search(rb"\r\nBANK=(\d+)\r\n", raw).group(1)) + 1
        pat_part, _ = otp.bank_info(proj, bank)
        part = vs.part_of(proj, bank, pat_part[0] + 1)
        card = work / "card.img"
        vs.stage(proj, part, "OCTABAM", "RIG", work / "tree", 64, bank, card)

        def dumps(c):
            d = work / c
            spec = ";".join(f"{a:#x},{n:#x}={d}.{i}" for i, (a, n) in enumerate(PLANES))
            return (spec + f";{CFG:#x},0x100={d}.cfg;{model:#x},32={d}.model;{WINH:#x},4={d}.win;"
                    f"{sym['su_win']:#x},4={d}.suwin;"
                    f"{LAYERS:#x},4={d}.head;{ROM_BASE:#x},{ROM_LEN:#x}={d}.rom;{lo:#x},{hi - lo:#x}={d}.unit")
        runs = []
        for tag in ("built", "ref"):
            args = []
            for c, (img, steps, *more) in CASES.items():
                if img != tag:
                    continue
                script(work / f"{c}.txt", steps, *more[:1])
                poke = f" --poke {model:#x}={DELAY_ID:#x}" if more[1:] == ["delay"] else ""
                args += ["--scenario", f"{work / c}.log --live-script {work / c}.txt --mem-dump {dumps(c)}{poke}"]
            shutil.copy2(card, work / f"card_{tag}.img")
            cmd = [str(vds.EMU), "--image", str(work / f"{tag}.bin"), "--card", str(work / f"card_{tag}.img"),
                   "--set", "OCTABAM", "--project", "RIG", "--load-ms", "90000", "--scenario-jobs", "4"] + args
            runs.append(subprocess.Popen(cmd, cwd=ROOT, stdout=open(work / f"{tag}.txt", "w"),
                                         stderr=subprocess.STDOUT))
        # the DSP cases, each on its own load: --dsp is the parent's
        for c, steps in (("dsp", ["MIXER", "RIGHT", "enc 0 10", "DOWN", "YES", "DOWN", "YES", "NO"]),
                         ("dsp_none", ["MIXER", "RIGHT", "YES", "UP", "YES", "NO"])):
            script(work / f"{c}.txt", steps)
            shutil.copy2(card, work / f"card_{c}.img")
            cmd = [str(vds.EMU), "--image", str(work / "built.bin"), "--card", str(work / f"card_{c}.img"),
                   "--set", "OCTABAM", "--project", "RIG", "--load-ms", "90000", "--dsp",
                   "--live-script", str(work / f"{c}.txt"), "--dsp-peek", "0:X:7c10,4;0:X:7c20,2;0:X:7c30,2",
                   "--mem-dump", f"{model:#x},32={work / c}.model"]
            runs.append(subprocess.Popen(cmd, cwd=ROOT, stdout=open(work / f"{c}.log", "w"),
                                         stderr=subprocess.STDOUT))
        codes = [p.wait() for p in runs]
        check("port: every load ran", all(c == 0 for c in codes), f"exit codes {codes}")

        R = {}
        for c in list(CASES) + ["dsp", "dsp_none"]:
            log = (work / f"{c}.log").read_text() if (work / f"{c}.log").exists() else ""
            if not check(f"port: {c}: the panel script ended on quit", "ended on quit" in log,
                         (re.search(r"live script: .*", log) or re.search(r".*$", log)).group(0)[:120]):
                continue
            r = {"log": log}
            if not c.startswith("dsp"):
                r["screen"] = lcd_view.screen(b"".join((work / f"{c}.{i}").read_bytes() for i in range(len(PLANES))))
                if keep:
                    lcd_view.png(r["screen"], str(work / f"{c}.png"))
                r["cfg"] = (work / f"{c}.cfg").read_bytes()
                r["win"] = struct.unpack(">I", (work / f"{c}.win").read_bytes())[0]
                r["suwin"] = struct.unpack(">I", (work / f"{c}.suwin").read_bytes())[0]
                r["head"] = struct.unpack(">I", (work / f"{c}.head").read_bytes())[0]
                r["rom"], r["unit"] = (work / f"{c}.rom").read_bytes(), (work / f"{c}.unit").read_bytes()
            r["model"] = list((work / f"{c}.model").read_bytes())
            R[c] = r
        checks(R, sym, lo, hi)


def layers(r, lo, hi):
    """The registered input layers, in order (the list at 0x460d165c)."""
    def u32(a):
        if ROM_BASE <= a < ROM_BASE + ROM_LEN:
            return struct.unpack(">I", r["rom"][a - ROM_BASE:a - ROM_BASE + 4])[0]
        if lo <= a < hi:
            return struct.unpack(">I", r["unit"][a - lo:a - lo + 4])[0]
        return None
    out, node = [], r["head"]
    while node and len(out) < 32:
        out.append(node)
        node = u32(node)
        if node is None:
            out.append("?")
            break
    return out


def checks(R, sym, lo, hi):
    need = lambda *cs: all(c in R for c in cs)
    keyl, encl = sym.get("MX_KEYL"), sym.get("MX_ENCL")
    if need("mixer", "ref_mixer"):
        d = diff(R["mixer"]["screen"], R["ref_mixer"]["screen"])
        check("mixer: the stock MIXER page but for the arrow at the title's right end",
              d and all(inside(p, RIGHT_ARROW) for p in d),
              f"{len(d)} pixel(s) differ, {sum(1 for p in d if not inside(p, RIGHT_ARROW))} outside the arrow")
        ls = layers(R["mixer"], lo, hi)
        check("layers: on MIXER ours follows the stock layer, the knobs' is off",
              STOCK_LAYER in ls and keyl in ls and ls.index(keyl) > ls.index(STOCK_LAYER) and encl not in ls,
              " ".join(f"{n:#x}" if isinstance(n, int) else n for n in ls))
    for c in ("back", "reopen"):
        if need(c, "mixer"):
            d = diff(R[c]["screen"], R["mixer"]["screen"])
            check(f"{c}: the MIXER page again, pixel for pixel", not d, f"{len(d)} pixel(s) differ")
    for c, how in (("close", "MIXER"), ("close_no", "NO"), ("close_fu", "FUNC+UP")):
        if need(c):
            ls = layers(R[c], lo, hi)
            check(f"{c}: {how} on MASTER closes the window and leaves no layer of the unit or the "
                  "window's registered", R[c]["win"] == 0 and "?" not in ls
                  and not any(lo <= n < hi for n in ls if isinstance(n, int)) and STOCK_LAYER not in ls,
                  f"handle {R[c]['win']:#x}, layers " + " ".join(f"{n:#x}" if isinstance(n, int) else n for n in ls))
    if need("master"):
        ls = layers(R["master"], lo, hi)
        check("layers: on MASTER ours and then the knobs' follow the stock layer",
              STOCK_LAYER in ls and ls[-2:] == [keyl, encl] and ls.index(keyl) > ls.index(STOCK_LAYER),
              " ".join(f"{n:#x}" if isinstance(n, int) else n for n in ls))
    if need("master", "ref_mixer"):
        m, s = R["master"]["screen"], R["ref_mixer"]["screen"]
        band = diff(m, s, (0, 44, 127, 63))
        check("master: the MUTE band and the frame below the boxes are the stock page's", not band,
              f"{len(band)} pixel(s) differ")
        check("master: an arrow at the title's left end, none at its right",
              diff(m, s, LEFT_ARROW) and not diff(m, s, RIGHT_ARROW),
              f"left {len(diff(m, s, LEFT_ARROW))} px changed, right {len(diff(m, s, RIGHT_ARROW))}")
        edges = [(x, y) for (x0, y0, x1, y1) in (BOX1, BOX2) for x in range(x0, x1 + 1) for y in (y0, y1)]
        edges += [(x, y) for (x0, y0, x1, y1) in (BOX1, BOX2) for y in range(y0, y1 + 1) for x in (x0, x1)]
        dark = [p for p in edges if not m[p[1]][p[0]]]
        check("master: both boxes' outlines are lit", not dark, f"{len(dark)} dark edge pixel(s)")
        stray = [(x, y) for x in STOCK_EDGES for y in range(11, 42) if m[y][x] and y != RULE_Y]
        were = sum(s[y][x] for x in STOCK_EDGES for y in range(11, 42))
        check("master: the stock boxes' edges inside box 2 are gone", were and not stray,
              f"{len(stray)} lit (stock {were})")
        empty = [lit(m, c) for c in CELLS[2:]]
        check("master: the cells OXIDE does not draw are empty", not any(empty), f"lit {empty}")
        full = [lit(m, c) for c in CELLS[:2]]
        check("master: IN's and OUT's cells are drawn", all(full), f"lit {full}")
    if need("ins2", "master"):
        m = R["ins2"]["screen"]
        empty = [lit(m, c) for c in CELLS]
        check("ins2: INS 2 (empty) shows six empty cells", not any(empty), f"lit {empty}")
        d = diff(m, R["master"]["screen"])
        check("ins2: beyond the cells only the side label's digit differs from INS 1's page",
              any(inside(p, DIGIT) for p in d)
              and all(inside(p, DIGIT) or any(inside(p, c) for c in CELLS) for p in d),
              f"{len(d)} pixel(s) differ")
    if need("mute", "master"):
        d = diff(R["mute"]["screen"], R["master"]["screen"])
        check("mute: the trig toggled a mute and MASTER stays drawn above the band",
              d and not any(inside(p, ABOVE_BAND) for p in d),
              f"{len(d)} pixel(s) differ, {sum(1 for p in d if inside(p, ABOVE_BAND))} above the band")
    if need("knobs", "ref_knobs", "master"):
        k, rk = R["knobs"], R["ref_knobs"]
        d_main_stock = rk["cfg"][0x35] - MAIN0
        d_mix_stock = rk["cfg"][0x32] - MAIN0
        got = (k["model"][4] - IN_KNOB, k["model"][5] - OUT_KNOB, k["cfg"][0x35] - MAIN0)
        want = (d_main_stock, d_mix_stock, d_main_stock)
        check("knobs: A, B and LEVEL on MASTER step IN, OUT and MAIN as A and LEVEL step MAIN and MIX "
              "on the stock page", got == want and d_main_stock > 0 and d_mix_stock < 0,
              f"IN {got[0]:+}, OUT {got[1]:+}, MAIN {got[2]:+}; stock MAIN {d_main_stock:+}, MIX {d_mix_stock:+}")
        d = diff(k["screen"], R["master"]["screen"])
        check("knobs: the screen changed only inside the three value cells, and in each",
              all(any(inside(p, b) for b in VALUES.values()) for p in d)
              and all(any(inside(p, b) for p in d) for b in VALUES.values()),
              f"{len(d)} pixel(s) differ")
        check("knobs: slot 2 untouched", k["model"][16:] == [0] * 16, f"{k['model'][16:]}")
    if need("slots"):
        mdl = R["slots"]["model"]
        check("slots: A on the empty INS 2 changes nothing, on INS 1 again moves IN",
              mdl[16:] == [0] * 16 and mdl[4] > IN_KNOB and mdl[5] == OUT_KNOB, f"{mdl}")
    if need("dsp"):
        mdl, x = R["dsp"]["model"], peek(R["dsp"]["log"])
        words = x.get(0x7c20)
        check("dsp: core 0's slot 1 record holds the page's IN and OUT, v << 16",
              words == [mdl[4] << 16, mdl[5] << 16] and mdl[4] != IN_KNOB,
              f"X:0x7c20 {hexs(words)}, model IN {mdl[4]} OUT {mdl[5]}")
        sl = x.get(0x7c10)
        check(f"dsp: OXIDE chosen in INS 2's SETUP runs on core 0's slot 2 (id 0x{vst.INSERT_ID:02x}, "
              "slot 1's proc)", sl is not None and sl[0] == sl[2] == vst.INSERT_ID and sl[1] and sl[3] == sl[1]
              and mdl[16] == vst.INSERT_ID, f"X:0x7c10 {hexs(sl)}, model slot 2 id {mdl[16]:#x}")
        check("dsp: slot 2's record is the defaults the SETUP wrote, IN 48 and OUT 80",
              x.get(0x7c30) == [IN_KNOB << 16, OUT_KNOB << 16] and mdl[20:22] == [IN_KNOB, OUT_KNOB],
              f"X:0x7c30 {hexs(x.get(0x7c30))}, model {mdl[20:22]}")
    if need("dsp_none"):
        mdl, x = R["dsp_none"]["model"], peek(R["dsp_none"]["log"])
        sl = x.get(0x7c10)
        check("dsp_none: NONE chosen in INS 1's SETUP leaves core 0's slot 1 dry (id and proc 0)",
              sl is not None and sl[:2] == [0, 0] and mdl[0] == 0 and x.get(0x7c20) == [0, 0],
              f"X:0x7c10 {hexs(sl)}, X:0x7c20 {hexs(x.get(0x7c20))}, model slot 1 id {mdl[0]:#x}")
    setup_checks(R, sym, lo, hi, need)


def peek(log):
    """--dsp-peek's lines: {address: [words]}."""
    return {int(a, 16): [int(w, 16) for w in ws.split()]
            for a, ws in re.findall(r"core 0 X:0x([0-9a-f]+): ((?:[0-9a-f]{6} ?)+)", log)}


def hexs(ws):
    return ws and [f"{w:06x}" for w in ws]


def setup_checks(R, sym, lo, hi, need):
    keyl, encl, sukl = sym.get("MX_KEYL"), sym.get("MX_ENCL"), sym.get("SU_KEYL")
    fmt = lambda ls: " ".join(f"{n:#x}" if isinstance(n, int) else n for n in ls)
    row = lambda s, r: lit(s, SU_ROW(r))
    band = (SU_ROW(0)[2] - SU_ROW(0)[0] + 1) * 7
    if need("su1"):
        r = R["su1"]
        ids_at, n = sym.get("SU_IDS"), sym.get("SU_N")
        ids = list(r["unit"][ids_at - lo:ids_at - lo + n]) if ids_at and n else None
        check("su: the list is NONE and the ids core 0 runs (tail.asm's, as verify_strip reads it)",
              ids == [0, vst.INSERT_ID], f"SU_IDS {ids}")
        s = r["screen"]
        check("su: YES on MASTER opens INS 1's SETUP over the MIXER window, OXIDE's row inverted",
              r["suwin"] and r["win"] and row(s, 1) > band // 2 > row(s, 0) and not lit(s, SU_ROW(2)),
              f"SETUP {r['suwin']:#x}, MIXER {r['win']:#x}, lit rows {row(s, 0)} {row(s, 1)} {row(s, 2)} of {band}")
        ls = layers(r, lo, hi)
        check("su: the SETUP's key layer is last, after the MIXER pages' two",
              ls[-3:] == [keyl, encl, sukl] and ls.index(keyl) > ls.index(STOCK_LAYER), fmt(ls))
        grid = lit(s, SU_GRID)
        if need("su_none"):
            check("su: OXIDE has no page 2: the grid is NONE's", not diff(s, R["su_none"]["screen"], SU_GRID),
                  f"{len(diff(s, R['su_none']['screen'], SU_GRID))} px differ, {grid} lit")
    empty = lit(R["su_none"]["screen"], SU_GRID) if need("su_none") else 0     # the rules alone
    for g in GRID:
        if need(g, "ref_" + g):
            d = diff(R[g]["screen"], R["ref_" + g]["screen"])
            out = [p for p in d if not inside(p, SU_TITLE) and not inside(p, SU_LIST)]
            n = lit(R[g]["screen"], SU_GRID)
            check(f"grid: {g}: DELAY's page 2 is drawn as stock's SETUP draws it after the same turns",
                  not out and any(inside(p, SU_TITLE) for p in d) and n > empty + 200,
                  f"{len(d)} px differ, {len(out)} outside the title band and the list; "
                  f"{n} lit in the grid, {empty} with no page 2")
    if need(*GRID):
        moved = [len(diff(R[a]["screen"], R[b]["screen"], SU_GRID))
                 for a, b in (("g_min", "g_mid"), ("g_mid", "g_max"), ("g_min", "g_max"), ("g_min", "g_lift"))]
        check("grid: the turns moved the knobs (min, mid, max and a lifted knob draw apart)", all(moved),
              f"px differ min/mid {moved[0]}, mid/max {moved[1]}, min/max {moved[2]}, min/lift {moved[3]}")
    if need("g_min", "g_max"):
        lo_, hi_ = R["g_min"]["model"][10:16], R["g_max"]["model"][10:16]
        check("grid: A-F move the model to DELAY's page-2 range ends",
              R["g_max"]["model"][0] == DELAY_ID and lo_ == [0] * 6 and hi_ == [1, 1, 127, 1, 1, 1],
              f"min {lo_}, max {hi_}")
    if need("su_none"):
        r = R["su_none"]
        s = r["screen"]
        check("choose: UP, YES puts NONE on INS 1: its row inverted, the model's slot 1 zero",
              row(s, 0) > band // 2 > row(s, 1) and r["model"][:16] == [0] * 16 and r["suwin"],
              f"lit rows {row(s, 0)} {row(s, 1)}, slot 1 {r['model'][:16]}")
    if need("su_none_no", "ins2"):
        r = R["su_none_no"]
        ls = layers(r, lo, hi)
        d = diff(r["screen"], R["ins2"]["screen"])
        check("choose: NO closes the SETUP (its layer gone) onto the MIXER window's INS 1 page, now empty",
              r["win"] and not r["suwin"] and sukl not in ls and ls[-2:] == [keyl, encl]
              and d and all(inside(p, DIGIT) for p in d),
              f"MIXER {r['win']:#x}, SETUP {r['suwin']:#x}, {len(d)} px differ from INS 2's page, "
              f"{sum(1 for p in d if not inside(p, DIGIT))} outside the digit; layers {fmt(ls)}")
    if need("su2", "su1"):
        r = R["su2"]
        d = diff(r["screen"], R["su1"]["screen"])
        check("choose2: DOWN, YES puts OXIDE on INS 2 with its defaults; the screen is INS 1's SETUP "
              "but for the title", r["model"][16:32] == r["model"][:16] == R["su1"]["model"][:16]
              and r["model"][16] == vst.INSERT_ID and d and all(inside(p, SU_TITLE) for p in d),
              f"slot 2 {r['model'][16:32]}, {len(d)} px differ, "
              f"{sum(1 for p in d if not inside(p, SU_TITLE))} outside the title band")
    if need("su2_no", "master"):
        d = diff(R["su2_no"]["screen"], R["master"]["screen"])
        check("choose2: NO: INS 2's MASTER page differs from INS 1's only in the digit",
              d and all(inside(p, DIGIT) for p in d), f"{len(d)} px differ")
    for c, how in (("su_nono", "NO, NO"), ("su_mixer", "MIXER"), ("su_fu", "FUNC+UP")):
        if need(c):
            r = R[c]
            ls = layers(r, lo, hi)
            check(f"su_close: {how} from the SETUP closes both windows and leaves no layer of the unit",
                  r["win"] == 0 and r["suwin"] == 0 and "?" not in ls
                  and not any(lo <= n < hi for n in ls if isinstance(n, int)) and STOCK_LAYER not in ls,
                  f"MIXER {r['win']:#x}, SETUP {r['suwin']:#x}, layers {fmt(ls)}")
    if need("su_again", "su1"):
        d = diff(R["su_again"]["screen"], R["su1"]["screen"])
        check("su_close: YES, NO, YES is the SETUP again, pixel for pixel", not d, f"{len(d)} px differ")
    if need("su_knobs", "knobs"):
        got, want = R["su_knobs"]["model"][4] - IN_KNOB, R["knobs"]["model"][4] - IN_KNOB
        check("su_close: after the SETUP, A steps IN on MASTER as it did before", got == want and got > 0,
              f"IN {got:+}, before {want:+}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("remix", nargs="*")
    ap.add_argument("--project", default=os.environ.get("OT_PROJECT", ""))
    a = ap.parse_args()
    if not vds.STOCK.exists():
        print("  [SKIP] verify_mixerpages: no stock image (make os)")
        return 0
    names = a.remix or [n for n in sorted(registry.remix_names()) if KEY in registry.remix(n).modules]
    names = [n for n in names if KEY in registry.remix(n).modules]
    if not names:
        print(f"  [--] verify_mixerpages: no remix selected carries {KEY}")
        return 0
    for name in names:
        built, report = vds.build(name)
        print(f"{name}: {len(built):,} bytes built")
        sym = vst.symbols()
        for d in registry.by_key(KEY).detours:
            o = d.site - CF_BASE
            want = sym.get(d.symbol)
            got = int.from_bytes(built[o + 2:o + 6], "big")
            check(f"{name}: 0x{d.site:08x} reaches {d.symbol}", want is not None and got == want,
                  f"0x{got:08x}")
        if a.project:
            port(name, built, a.project, sym)
        else:
            print(f"  [SKIP] {name}: the port runs -- no project (OT_PROJECT=<dir> or --project)")
    print(f"verify_mixerpages: {fails} failure(s)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
