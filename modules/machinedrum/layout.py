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
        {"name": "voice_x", "space": "X", "start": 0x8C00, "words": 0x400},
        {"name": "voice_y_records", "space": "Y", "start": 0x8C00, "words": 0x400},

        # The driver's own Y (loop words, the 16 x 32 output blocks, the MD's
        # kept words, the stock low-memory stash).
        {"name": "stash", "space": "Y", "start": 0xB9C0, "words": 0x240},
        {"name": "outbuf", "space": "Y", "start": 0xBC00, "words": 0x200},
        {"name": "loop_words", "space": "Y", "start": 0xBE00, "words": 0x20},
        {"name": "mdsave", "space": "Y", "start": 0xBE20, "words": 0x24},

        # Table ground: what md_flip.py --plan packs the tables and the P-I
        # buffers into (best fit, each keeping its old alignment).
        {"name": "x_tables_a", "space": "X", "start": 0x2840, "words": 0x3F00 - 0x2840},
        {"name": "x_tables_b", "space": "X", "start": 0x5840, "words": 0x6000 - 0x5840},
        {"name": "x_tables_c", "space": "X", "start": 0x7A92, "words": 0x8040 - 0x7A92},
        {"name": "x_tables_d", "space": "X", "start": 0x8858, "words": 0x8C00 - 0x8858},
        {"name": "y_tables_a", "space": "Y", "start": 0x07A5, "words": 0x8C00 - 0x07A5},
        {"name": "y_tables_b", "space": "Y", "start": 0x9000, "words": 0xB9C0 - 0x9000},

        # The shared window (P/X/Y alias there): the code that does not fit
        # private P, and the tables private X and Y cannot take (no flip is
        # needed there).
        {"name": "window_code", "space": "shared", "start": 0x34000, "words": 0x2400},
        {"name": "window_tables", "space": "shared", "start": 0x36400, "words": 0x1C00},
        {"name": "sine", "space": "shared", "start": 0x38000, "words": 0x8000},
    ],
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
        {"owner": "T8 FX2 slot storage (T8's FX2 limited to memoryless effects)", "space": "shared",
         "start": 0x34000, "end": 0x38000},
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
                      ("loopvars", "loop_words"), ("code", "driver_code")):
        if d[key] != allocation(name)["start"]:
            errors.append(f"driver {key} {d[key]:#x} is not {name}'s start")
    lw = allocation("loop_words")
    for key in ("LV140", "LV141", "LV142", "HALF", "TMP"):
        if not lw["start"] <= d[key] < _end(lw):
            errors.append(f"driver {key} is outside loop_words")
    if not lw["start"] <= d["ENG"] and d["ENG"] + 16 <= _end(lw):
        errors.append("driver ENG (16 words) is outside loop_words")
    return errors


if __name__ == "__main__":
    problems = check()
    if problems:
        for problem in problems:
            print(f"FAIL: {problem}")
        raise SystemExit(1)
    print(f"PASS: {len(LAYOUT['allocations'])} core-1 allocations, no overlap, all on free ground")
    print(f"REVIEW: {len(LAYOUT['stock_costs'])} stock costs listed for the user's sign-off")
