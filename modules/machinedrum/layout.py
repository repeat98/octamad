"""WP-A2's proposed core-0 address book.

This is deliberately a plain data dictionary.  The ranges are capacities for
the later layout-driven relocator; this file does not copy any firmware or
generated words.  ``python3 modules/machinedrum/layout.py`` checks the MD
allocations against one another.  ``stock_conflicts`` is kept separate because
those are the user-owned layout trade-offs that must be signed off before the
proposal can become a shipping remix.
"""


LAYOUT = {
    "status": "superseded: the MD moves to core 1, tracks 1-4 (24 Sep 2026); redo WP-A2",
    "core": 0,
    "track_range": (5, 8),
    "voice_home": "A_fx1_slot_0x3400",
    "max_pi_voices": 6,
    "source_budget_words": {
        "engine_code": 15621,
        "hot_code": 2724,
        "tables_max": 28061,
        "sine": 32768,
        "pi_buffer_per_voice": 1536,
        "driver_code_measured": 192,
    },
    "allocations": [
        # Core-0 private P: the PLATE/SPRING/DARK donor span, inclusive in
        # the source notes as 0x1000..0x1aa3.
        {"name": "hot_code", "space": "P", "start": 0x1000, "words": 0xAA4},

        # The MD voice record/state is 1K in both X and Y.  X is in the
        # measured free span; Y is deliberately the forfeited FX1 slot.
        {"name": "voice_x", "space": "X", "start": 0x3400, "words": 0x400},
        {"name": "voice_y_records", "space": "Y", "start": 0x3400, "words": 0x400},

        # Driver state in the measured-clean internal Y scratch above 0x0bff.
        {"name": "loop_words", "space": "Y", "start": 0x0C00, "words": 0x20},
        {"name": "outbuf", "space": "Y", "start": 0x0D00, "words": 0x200},
        {"name": "mdsave", "space": "Y", "start": 0x0F20, "words": 0x24},
        {"name": "stash", "space": "Y", "start": 0x1800, "words": 0x240},

        # One shared physical window, visible as P/X/Y.  The sine keeps a
        # full 32K contiguous span.  The remaining spans are capacity
        # budgets: private Y carries the rest of the Y-only tables.
        {"name": "sine", "space": "shared", "start": 0x30000, "words": 0x8000},
        {"name": "window_code_tables", "space": "shared", "start": 0x38000, "words": 0x5A00},
        {"name": "pi_buffers", "space": "shared", "start": 0x3DA00, "words": 0x2400},
        {"name": "driver_code", "space": "shared", "start": 0x3FE00, "words": 0x200},

        # At the maximum table estimate, this is the Y-only complement that
        # makes the shared-window budget close.  It also occupies the two
        # private FX2 slots, which is an explicit review cost below.
        {"name": "y_only_tables", "space": "Y", "start": 0x4000, "words": 0x4600},
    ],
    "driver": {
        "loopvars": 0x0C00,
        "LV140": 0x0C00,
        "LV141": 0x0C01,
        "LV142": 0x0C02,
        "HALF": 0x0C03,
        "TMP": 0x0C04,
        "ENG": 0x0C10,
        "OUTBUF": 0x0D00,
        "MDSAVE": 0x0F20,
        "STASH": 0x1800,
        "code": 0x3FE00,
    },
    "stock_conflicts": [
        {
            "owner": "payload-A frame state",
            "space": "shared",
            "start": 0x30000,
            "end": 0x30048,
            "cost": "must be relocated or saved/restored; it is not free",
        },
        {
            "owner": "core-0 T7/T8 FX2 storage",
            "space": "shared",
            "start": 0x30048,
            "end": 0x38000,
            "cost": "the selected FX2 slots must be memoryless or surrendered",
        },
        {
            "owner": "payload-B entry/read state",
            "space": "shared",
            "start": 0x38000,
            "end": 0x38013,
            "cost": "core-1 stock entry/table words cannot be overwritten",
        },
        {
            "owner": "core-1 loaded/effect window",
            "space": "shared",
            "start": 0x38013,
            "end": 0x40000,
            "cost": "core-1 stock must be relocated or this proposal cannot ship",
        },
        {
            "owner": "core-0 FX1 slot at 0x3400",
            "space": "Y",
            "start": 0x3400,
            "end": 0x4000,
            "cost": "forfeited by the selected voice-Y home",
        },
        {
            "owner": "core-0 private FX2 slots T5/T6",
            "space": "Y",
            "start": 0x4000,
            "end": 0xC000,
            "cost": "forfeited where y_only_tables are placed",
        },
        {
            "owner": "payload-A donor effects PLATE/SPRING/DARK",
            "space": "P",
            "start": 0x1000,
            "end": 0x1AA4,
            "cost": "their core-0 code is harvested for hot MD units",
        },
        {
            "owner": "core-0 X curve/table bank",
            "space": "X",
            "start": 0x800,
            "end": 0xC00,
            "cost": "not used by the selected 0x3400 voice home; relevant to alternatives",
        },
    ],
}


OPTIONS = {
    "A_move_base_fx1": {
        "voice_base": 0x3400,
        "cost": "forfeit the 3,072-word FX1 slot 0x3400..0x3fff; no per-batch copy",
        "status": "signed off by the user, 24 Sep 2026",
    },
    "B_swap_pi_x_words": {
        "voice_y_base": 0x800,
        "voice_x_base": 0x2840,
        "cost": "preserve FX1, but move/copy about 17 X words per P-I voice per batch; runtime cost is unmeasured",
        "status": "not chosen (24 Sep 2026)",
    },
    "C_batch_overwrite_curve_table": {
        "voice_base": 0x800,
        "cost": "save/restore the overlapping X curve bank around the MD batch; stock-table timing and cycle cost are unmeasured",
        "status": "not chosen (24 Sep 2026); unsafe until a scheduler proof",
    },
}


def _end(region):
    return region["start"] + region["words"]


def check_internal_overlaps():
    """Return the non-overlap and capacity errors for MD-owned ranges."""
    errors = []
    by_space = {}
    for region in LAYOUT["allocations"]:
        if region["words"] <= 0:
            errors.append(f"{region['name']}: non-positive size")
        by_space.setdefault(region["space"], []).append(region)

    for space, regions in by_space.items():
        ordered = sorted(regions, key=lambda r: r["start"])
        for left, right in zip(ordered, ordered[1:]):
            if _end(left) > right["start"]:
                errors.append(
                    f"{space}: {left['name']} [{left['start']:#x}, {_end(left):#x}) "
                    f"overlaps {right['name']} [{right['start']:#x}, {_end(right):#x})"
                )

    budget = LAYOUT["source_budget_words"]
    max_pi = LAYOUT["max_pi_voices"]
    if max_pi * budget["pi_buffer_per_voice"] > 0x2400:
        errors.append("pi_buffers: max P-I voice budget exceeds its shared range")
    code_tables = budget["engine_code"] - budget["hot_code"] + budget["tables_max"]
    if code_tables > 0x5A00 + 0x4600:
        errors.append("code/tables: shared plus private-Y capacity is too small")
    if budget["driver_code_measured"] > 0x200:
        errors.append("driver_code: measured assembly exceeds its capacity")
    return errors


if __name__ == "__main__":
    problems = check_internal_overlaps()
    if problems:
        for problem in problems:
            print(f"FAIL: {problem}")
        raise SystemExit(1)
    print("PASS: 12 MD allocations are internally non-overlapping")
    print("PASS: source budgets fit with max_pi_voices=6")
    print("REVIEW: 8 stock conflicts remain explicitly listed")
