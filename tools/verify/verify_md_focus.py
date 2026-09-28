#!/usr/bin/env python3
"""WP-D7/D8: the MD track's SRC page is the kit editor (under the port).

MD_EMU and OT_PROJECT as the other MD gates; T1 signed MD in bank 1. Two
runs from the load, each ending with a RAM dump:

  1. preview: trig 5 selects part 5 (TRX-CP, the default kit's), YES opens
     the ENGINE window, DOWN DOWN moves to TRX-CB, FUNC+YES previews it:
     the window is open, md_preview names part 5 and TRX-CB, the applied
     part (md_run's shadow) plays TRX-CB, and the kit still holds TRX-CP;
  2. take: the same, then YES takes TRX-CB and closes the window; the kit's
     part 5 is TRX-CB with its defaults, the preview is off, the MD's input
     layer is back on, and PTN + trig 3 still selects pattern A03 (stock).

The port's load leaves the date prompt up; YES first dismisses it (the
MD's layer is pushed only while the base layer is alone).
"""
import os
import pathlib
import struct
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/verify"))
import verify_md_ui as ui

OUT = ROOT / "out/mdverify/focus_gate"
MD_PARTS, MD_SYN, RECORD_LONGS = 16, 8, 21
PART_BYTES = 4 + MD_SYN
FOCUS_BYTES = 296              # MdFocus (md_ctl.h)
F_WIN, F_ON, F_CUR = 208, 216, 217
CP, CB = 0x13, 0x15
UI_PATTERN = 0x80000004


def key(code, gap=0.3):
    return [(gap, f"key {code:#x} down"), (0.15, f"key {code:#x} up")]


def with_func(code):
    return [(0.3, "key 0x2d down"), (0.2, f"key {code:#x} down"), (0.15, f"key {code:#x} up"),
            (0.2, "key 0x2d up")]


def with_ptn(code):
    return [(0.3, "key 0x2e down"), (0.2, f"key {code:#x} down"), (0.15, f"key {code:#x} up"),
            (0.2, "key 0x2e up")]


def main():
    project, emu = os.environ.get("OT_PROJECT"), os.environ.get("MD_EMU")
    if not project or not emu:
        raise SystemExit("MD_EMU and OT_PROJECT are required")
    ui.OUT = OUT
    OUT.mkdir(parents=True, exist_ok=True)
    source = pathlib.Path(project)
    if not source.is_absolute():
        source = ROOT / source
    image = ROOT / "out/mainos_bus.bin"
    sym = ui.symbols()
    _, card = ui.stage(source, "signed", True)
    shadow = sym["md_run"] + MD_PARTS * RECORD_LONGS * 4
    spans = {
        "ui": (sym["md_ui"], 4),
        "focus": (sym["md_focus"], FOCUS_BYTES),
        "preview": (sym["md_preview"], 4),
        "shadow": (shadow, MD_PARTS * PART_BYTES),
        "kit": (sym["md_kits"], MD_PARTS * PART_BYTES),
        "pattern": (UI_PATTERN, 4),
    }
    opening = key(0x31, 1.0) + key(0x04, 1.0) + key(0x31, 0.6) + key(0x20) + key(0x20)

    st = ui.run("preview", card, emu, image, spans,
                opening + with_func(0x31) + [(1.5, "quit")])
    focus = st["focus"]
    win = struct.unpack(">I", focus[F_WIN:F_WIN + 4])[0]
    preview = struct.unpack(">I", st["preview"])[0]
    assert st["ui"][0] == 4, f"part 5 not selected: sel {st['ui'][0]}"
    assert win, "the ENGINE window is not open"
    assert focus[220 + focus[F_CUR]] == CB, f"cursor on {focus[220 + focus[F_CUR]]:#x}"
    assert preview == 0x80000000 | 4 << 8 | CB, f"md_preview {preview:#x}"
    assert st["shadow"][4 * PART_BYTES] == CB, f"applied part 5 plays {st['shadow'][4 * PART_BYTES]:#x}"
    assert st["kit"][4 * PART_BYTES] == CP, f"the kit's part 5 changed to {st['kit'][4 * PART_BYTES]:#x}"
    print("preview: trig 5 -> part 5, YES opens ENGINE on TRX-CP, DOWN DOWN = TRX-CB, "
          "FUNC+YES plays TRX-CB on part 5; the kit keeps TRX-CP")

    st = ui.run("take", card, emu, image, spans,
                opening + key(0x31, 0.4) + with_ptn(0x02) + [(1.5, "quit")])
    focus = st["focus"]
    win = struct.unpack(">I", focus[F_WIN:F_WIN + 4])[0]
    preview = struct.unpack(">I", st["preview"])[0]
    part5 = st["kit"][4 * PART_BYTES:5 * PART_BYTES]
    assert part5[0] == CB, f"the kit's part 5 is {part5[0]:#x}"
    assert st["shadow"][4 * PART_BYTES] == CB
    assert not win and not preview, (win, preview)
    assert focus[F_ON] == 1, "the MD's input layer is not back on"
    assert st["ui"][0] == 4, f"sel {st['ui'][0]}"
    assert st["pattern"][0] == 2, f"PTN + trig 3 left pattern {st['pattern'][0]}"
    print(f"take: YES sets part 5 to TRX-CB (SYN {list(part5[4:])}), the window closes, "
          "the layer is back; PTN + trig 3 selects A03")
    print("verify_md_focus: PASS")


if __name__ == "__main__":
    main()
