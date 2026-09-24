"""WP-A2's core-1 address book (proposed, 24 September 2026).

The MD runs on core 1 (payload B, tracks 1-4); T1-T4 give up their stock
FX, code and memory (MACHINEDRUM_MACHINE.md section 1, decisions of 24
September). WP-A7's placement plan decides where each table goes: everything
but the sine in core 1's private X or Y (D6, accepted). This is plain data,
so importing it pulls in no build machinery and no firmware bytes.
``python3 modules/machinedrum/layout.py`` checks the allocations against one
another and against the spans they are carved from.

Sources for the free ground (core 1):
  * private P: payload B's thirteen stock effects, P:0x0591-0x1d9f
    (tools/remix/stock.py), and P:0x1da0-0x1fff above payload B's top
    (docs/firmware/DSP.md section 3; P:0x2000 has run code on the unit, so
    everything below it is executable);
  * private X: the free spans of machinedrum_reports/WP-A2-ledger-core1.txt
    of at least 256 words;
  * private Y: Y:0x07a5-0x0fff (free) and Y:0x1000-0xbfff (T1-T4's FX1 and
    FX2 state, given up);
  * the shared window: core 1's half, 0x38000-0x3ffff, for the sine (the 19
    stock words at 0x38000 are already overwritten by the shipping
    BusDelay), and T8's FX2 slot, 0x34000-0x37fff, for the code that does
    not fit private P (T8's FX2 then runs only memoryless effects).
    The 512-word E12 write buffer and 512-word sample metadata block
    also occupy this shared window.
"""


LAYOUT = {
    "status": "proposed for core 1, 24 Sep 2026 (WP-A2 redo); pending the user's sign-off",
    "core": 1,
    "track_range": (1, 4),
    "max_pi_voices": 16,
    "allocations": [
        # Private P: the hot MD code and the OT-side driver.
        {"name": "hot_code", "space": "P", "start": 0x0591, "words": 0x1F00 - 0x0591},
        {"name": "driver_code", "space": "P", "start": 0x1F00, "words": 0x100},

        # The voice records: the engines reach X and Y through one base
        # register (r6), so both halves sit at one address.
        {"name": "voice_x", "space": "X", "start": 0x3940, "words": 0x400},
        {"name": "voice_y_records", "space": "Y", "start": 0x3940, "words": 0x400},

        # The driver's own Y (loop words, the 16 x 32 output blocks, the MD's
        # kept words, the stock low-memory stash).
        {"name": "stash", "space": "Y", "start": 0xB9C0, "words": 0x240},
        {"name": "outbuf", "space": "Y", "start": 0xBC00, "words": 0x200},
        {"name": "loop_words", "space": "Y", "start": 0xBE00, "words": 0x20},
        {"name": "mdsave", "space": "Y", "start": 0xBE20, "words": 0x24},
        {"name": "phase_flags", "space": "Y", "start": 0xBE44, "words": 0x10},

        # Table ground: what md_flip.py --plan packs the tables and the P-I
        # buffers into (best fit, each keeping its old alignment).
        {"name": "x_tables_a", "space": "X", "start": 0x2840, "words": 0x3940 - 0x2840},
        {"name": "x_tables_b", "space": "X", "start": 0x5840, "words": 0x5D40 - 0x5840},
        {"name": "x_tables_c", "space": "X", "start": 0x7A92, "words": 0x8040 - 0x7A92},
        {"name": "x_tables_d", "space": "X", "start": 0x8858, "words": 0x9000 - 0x8858},
        {"name": "y_tables_a", "space": "Y", "start": 0x07A5, "words": 0x3940 - 0x07A5},
        {"name": "y_tables_b", "space": "Y", "start": 0x3D40, "words": 0x5600 - 0x3D40},
        {"name": "pi_buffers", "space": "Y", "start": 0x5600, "words": 0x6000},
        {"name": "y_tables_c", "space": "Y", "start": 0xB600, "words": 0xB9C0 - 0xB600},

        # The shared window (P/X/Y alias there): the code that does not fit
        # private P, and the tables private X and Y cannot take (no flip is
        # needed there). The E12 write buffer and sample metadata have fixed homes.
        {"name": "window_code", "space": "shared", "start": 0x34000, "words": 0x2000},
        {"name": "window_tables", "space": "shared", "start": 0x36400, "words": 0x0C00},
        {"name": "e12_tail", "space": "shared", "start": 0x37000, "words": 0x200},
        {"name": "sample_meta", "space": "shared", "start": 0x37200, "words": 0x200},
        {"name": "window_tables_b", "space": "shared", "start": 0x37400, "words": 0x0C00},
        {"name": "sine", "space": "shared", "start": 0x38000, "words": 0x8000},

        # The core-1 host (modules/machinedrum/md_glue.asm, WP-B3/B4/A5): its
        # code from the start, its words from glue["data"].
        {"name": "glue", "space": "shared", "start": 0x36000, "words": 0x400},

        # WP-C1's mailbox: the ColdFire's record packets, one block per frame
        # (modules/machinedrum/md_xport.s). The host writes to X:0x7d40 and
        # payload B's host-command handler masks every destination with
        # 0x3fff or 0x5fff, alternately per frame, so one frame's block lands
        # at mbox_a and the next at mbox_b, 0x2000 apart like every stock
        # block; the glue reads the bank this frame's x:$207 names. Neither
        # was loaded by the payload (x_tables_e was empty in the placement).
        {"name": "mbox_a", "space": "X", "start": 0x3D40, "words": 0x1C0},
        {"name": "mbox_b", "space": "X", "start": 0x5D40, "words": 0x1C0},
    ],
    # md_glue.asm's words (tools/build/md_image.py fills its placeholders).
    # GAIN is 16-aligned (m1 = $f), MIX holds one 32-sample period, L/R.
    "glue": {
        "code": 0x36000,
        "code_words": 0x300,
        "OWNER": 0x36300,
        "GOUT": 0x36301,
        "ONCE": 0x36302,
        "SAVER6": 0x36303,
        "SAVEN7": 0x36304,
        "TRIGS": 0x36305,
        # WP-C1, the record transport (md_glue.asm, gxport):
        "LSEQ": 0x36306,     # the last block's sequence number taken
        "NAPPLY": 0x36307,   # blocks taken
        "NWORDS": 0x36308,   # record words written
        "SLIPS": 0x36309,    # sync marks that moved the driver's half
        "GAPS": 0x3630a,     # sequence numbers skipped (blocks lost)
        "BAD": 0x3630b,      # packets refused (bounds)
        "SINE16": 0x36310,
        "ZERO": 0x36320,
        "FIXED": 0x36330,
        "GAIN": 0x36340,
        "MIX": 0x36380,
        "end": 0x363c0,
    },
    "driver": {
        "LV140": 0xBE00,
        "LV141": 0xBE01,
        "LV142": 0xBE02,
        "HALF": 0xBE03,
        "TMP": 0xBE04,
        "ENG": 0xBE10,
        "loopvars": 0xBE00,
        "OUTBUF": 0xBC00,
        "MDSAVE": 0xBE20,
        "PHASE": 0xBE44,
        "STASH": 0xB9C0,
        "code": 0x1F00,
    },
    # What the stock OT loses, for the user's sign-off.
    "stock_costs": [
        {"owner": "T1-T4 stock FX code (all thirteen effects, core 1)", "space": "P",
         "start": 0x0591, "end": 0x1DA0},
        {"owner": "T1-T4 FX1/FX2 state (core 1)", "space": "Y", "start": 0x1000, "end": 0xC000},
        {"owner": "T3/T4 FX2 storage in core 1's window half", "space": "shared",
         "start": 0x38013, "end": 0x40000},
        {"owner": "payload B's entry/per-frame words (dead after boot: BusDelay overwrites them)",
         "space": "shared", "start": 0x38000, "end": 0x38013},
        {"owner": "T8 FX2 slot storage: payload A's slot table (X:0x25c) now gives T8's FX2 "
                  "T7's base 0x30000, so T7/T8 memory effects share one buffer (audio, not a crash)",
         "space": "shared", "start": 0x34000, "end": 0x38000},
        {"owner": "payload A's boot clear of Y:0x34000-0x37fff (narrowed to 0x30000-0x33fff; "
                  "the MD's window code is loaded there before core 0 reaches its clear)",
         "space": "shared", "start": 0x34000, "end": 0x38000},
        {"owner": "core 0's per-frame read of X:0x38000-0x3800f into Y:0x280 (stock reads zeros "
                  "there, measured; repointed to 16 zero words at glue ZERO)",
         "space": "shared", "start": 0x38000, "end": 0x38010},
    ],
}

# Free ground each allocation must lie inside (see the module docstring).
GROUND = {
    "P": [(0x0591, 0x2000)],
    "X": [(0x2840, 0x3F00), (0x5840, 0x6000), (0x7A92, 0x8040), (0x8858, 0x9000)],
    "Y": [(0x07A5, 0xC000)],
    "shared": [(0x34000, 0x40000)],
}


def allocation(name):
    for region in LAYOUT["allocations"]:
        if region["name"] == name:
            return region
    raise KeyError(f"layout allocation not found: {name}")


def table_spans(space):
    """The (start, end) spans md_flip.py packs tables into: X, Y or W (the window)."""
    prefix = {"X": "x_tables", "Y": "y_tables", "W": "window_tables"}[space]
    return [(r["start"], r["start"] + r["words"]) for r in LAYOUT["allocations"]
            if r["name"].startswith(prefix)]


def _end(region):
    return region["start"] + region["words"]


def check():
    """Return the overlap and ground errors for the MD's allocations."""
    errors = []
    by_space = {}
    for region in LAYOUT["allocations"]:
        if region["words"] <= 0:
            errors.append(f"{region['name']}: non-positive size")
        by_space.setdefault(region["space"], []).append(region)
        if not any(s <= region["start"] and _end(region) <= e for s, e in GROUND[region["space"]]):
            errors.append(f"{region['name']}: [{region['start']:#x}, {_end(region):#x}) "
                          f"is not inside free {region['space']} ground")
    for space, regions in by_space.items():
        ordered = sorted(regions, key=lambda r: r["start"])
        for left, right in zip(ordered, ordered[1:]):
            if _end(left) > right["start"]:
                errors.append(f"{space}: {left['name']} [{left['start']:#x}, {_end(left):#x}) "
                              f"overlaps {right['name']} [{right['start']:#x}, {_end(right):#x})")
    if allocation("voice_x")["start"] != allocation("voice_y_records")["start"]:
        errors.append("voice records: X and Y halves must share one address (one base register)")
    if allocation("outbuf")["start"] % 0x20:
        errors.append("outbuf: must be 32-aligned (m7 = $1f)")
    d = LAYOUT["driver"]
    for key, name in (("OUTBUF", "outbuf"), ("MDSAVE", "mdsave"), ("STASH", "stash"),
                      ("loopvars", "loop_words"), ("PHASE", "phase_flags"), ("code", "driver_code")):
        if d[key] != allocation(name)["start"]:
            errors.append(f"driver {key} {d[key]:#x} is not {name}'s start")
    lw = allocation("loop_words")
    for key in ("LV140", "LV141", "LV142", "HALF", "TMP"):
        if not lw["start"] <= d[key] < _end(lw):
            errors.append(f"driver {key} is outside loop_words")
    if not lw["start"] <= d["ENG"] and d["ENG"] + 16 <= _end(lw):
        errors.append("driver ENG (16 words) is outside loop_words")
    for name, bank in (("mbox_a", 0x2000), ("mbox_b", 0x4000)):
        if allocation(name)["start"] - bank != allocation("mbox_a")["start"] - 0x2000:
            errors.append("mbox_a and mbox_b must sit at one offset in the two host banks")
    if allocation("mbox_a")["start"] + allocation("mbox_a")["words"] > 0x3F00:
        errors.append("mbox_a runs into X:0x3f00 (payload B's own words)")
    g, glue = LAYOUT["glue"], allocation("glue")
    if g["code"] != glue["start"] or g["end"] > _end(glue):
        errors.append("glue words are outside the glue allocation")
    words = sorted((v, k) for k, v in g.items() if k not in ("code", "code_words", "end"))
    if words[0][0] < g["code"] + g["code_words"]:
        errors.append("glue data overlaps the glue code")
    if g["GAIN"] % 16 or allocation("outbuf")["start"] % 0x200:
        errors.append("glue GAIN must be 16-aligned and outbuf 512-aligned (the mix's modulo)")
    return errors


if __name__ == "__main__":
    problems = check()
    if problems:
        for problem in problems:
            print(f"FAIL: {problem}")
        raise SystemExit(1)
    print(f"PASS: {len(LAYOUT['allocations'])} core-1 allocations, no overlap, all on free ground")
    print(f"REVIEW: {len(LAYOUT['stock_costs'])} stock costs listed for the user's sign-off")
