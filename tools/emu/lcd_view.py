#!/usr/bin/env python3
"""Show the Octatrack's screen from the port's plane file.

    ./out/emu/ot_emu ... --lcd out/lcd.bin        # the port, in one terminal
    .venv/bin/python3 tools/emu/lcd_view.py out/lcd.bin          # a window
    .venv/bin/python3 tools/emu/lcd_view.py out/lcd.bin --term   # in the terminal
    .venv/bin/python3 tools/emu/lcd_view.py out/lcd.bin --png shot.png
    .venv/bin/python3 tools/emu/lcd_view.py out/lcd.bin --panel out/panel.fifo   # + keys and encoders

--panel writes the port's --live FIFO: a key sends "key <code> down" on
press and "... up" on release (so FUNC + key works), an encoder sends
"enc <n> <delta>" (buttons, or the mouse wheel over its label), the pot
"pot <0..255>". Keyboard: arrows, Return = YES, Escape = NO, space =
PLAY, 1..8 / q..i = trigs 1..16, F1..F5 = the page keys.

The file starts with the firmware's own 1-bpp plane at 0x46c7e0ea (1,024
bytes): 64 columns x 128 rows, 8 bytes per row, MSB left. Screen pixel
(x, y) is column 63-y of row x -- the panel is stored rotated a quarter
turn. Measured 17 Sep 2026 by rendering a dump under each candidate
layout; the PLAYBACK page reads upright under this one and under no other.

Since 25 Sep 2026 the port appends the popup windows (the menu, TEMPO,
prompts), which the firmware keeps out of that plane: the window table at
0x46c7d34c (five 56-byte entries: x and y from the top left at +8/+12,
bit 0x20 of +32 set while the window shows, w and h at +36/+40) and the
planes at 0x460d1f7b (slot i's ink at +i*0x400, its opacity mask 0x1400
above; w columns of ceil(h/32)*4 bytes, row y of the window at bit h-1-y
from the column's MSB). Every visible window is composited over the page:
the mask picks the window's ink, the page shows elsewhere. Read from the
port's RAM against the stock TEMPO, CONTROL INPUT, MIDI SYNC and date
prompt, 25 Sep 2026.
"""
import struct as _struct
import argparse
import os
import struct
import sys
import time
import zlib

W, H = 128, 64
ON, OFF = (0xE8, 0xF0, 0x60), (0x18, 0x20, 0x10)


def pixels(plane):
    """Rows of 0/1, screen orientation."""
    def bit(col, row):
        return (plane[row * 8 + col // 8] >> (7 - col % 8)) & 1
    return [[bit(63 - y, x) for x in range(W)] for y in range(H)]


def png(rows, path, scale=4):
    out = []
    for y in range(H * scale):
        line = bytearray([0])
        for x in range(W * scale):
            line += bytes(ON if rows[y // scale][x // scale] else OFF)
        out.append(bytes(line))
    raw = b"".join(out)

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", W * scale, H * scale, 8, 2, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def term(rows):
    """Two pixel rows per text row, half blocks."""
    glyph = {(0, 0): " ", (1, 0): "▀", (0, 1): "▄", (1, 1): "█"}
    return "\n".join("".join(glyph[(rows[y][x], rows[y + 1][x])] for x in range(W)) for y in range(0, H, 2))


WIN_TABLE, WIN_ENTRY, WIN_SLOTS = 1024, 56, 5
WIN_PLANES = WIN_TABLE + WIN_SLOTS * WIN_ENTRY
WIN_MASK = 0x1400


def read_plane(path):
    """The file as the port wrote it: the page plane, and the windows when
    it carries them."""
    with open(path, "rb") as f:
        data = f.read()
    if len(data) != 1024 and len(data) != WIN_PLANES + 0x2800:
        raise ValueError(f"{path}: {len(data)} bytes, want 1024 or {WIN_PLANES + 0x2800}")
    return data


def composite(rows, data):
    """Every visible window over the page rows, in table order."""
    if len(data) == 1024:
        return rows
    for i in range(WIN_SLOTS):
        e = WIN_TABLE + i * WIN_ENTRY
        x0, y0 = _struct.unpack(">ii", data[e + 8:e + 16])
        flags, w, h = _struct.unpack(">Iii", data[e + 32:e + 44])
        if not flags & 0x20 or not (0 < w <= W and 0 < h <= H):
            continue
        col = (h + 31) // 32 * 4
        ink = WIN_PLANES + i * 0x400
        for x in range(w):
            sx = x0 + x
            if not 0 <= sx < W:
                continue
            a = int.from_bytes(data[ink + x * col:ink + x * col + col], "big")
            m = int.from_bytes(data[ink + WIN_MASK + x * col:ink + WIN_MASK + x * col + col], "big")
            for y in range(h):
                sy = y0 + y
                shift = col * 8 - 1 - (h - 1 - y)
                if 0 <= sy < H and (m >> shift) & 1:
                    rows[sy][sx] = (a >> shift) & 1
    return rows


def screen(data):
    """Screen rows (0/1) of a file's contents: page plus windows."""
    return composite(pixels(data[:1024]), data)


def watch(path, on_frame, period=0.05):
    last = None
    while True:
        try:
            st = os.stat(path)
            key = (st.st_mtime_ns, st.st_size)
            if key != last:
                last = key
                on_frame(screen(read_plane(path)))
        except (FileNotFoundError, ValueError):
            pass
        yield
        time.sleep(period)


# Key codes are the panel controller's: the keymap the firmware installs
# ([0x46c901dc]) is the identity, so code = row*8 + bit. Names from
# docs/firmware/PANEL.md (octalab's list, the 18 Sep 2026 probe under the
# port) and the 25 Sep 2026 survey under the port (TEMPO, SCENE A/B, PAGE,
# PART, ARR, MIX); a trailing "?" marks a name inferred, not measured.
KEYS = {
    **{i: f"{i + 1}" for i in range(16)},          # trig keys
    **{0x10 + i: f"T{i + 1}" for i in range(8)},   # track keys
    0x18: "TEMPO", 0x19: "SCENE A", 0x1A: "SCENE B", 0x1B: "PAGE", 0x1C: "MENU", 0x1D: "PART", 0x1F: "ARR",
    0x20: "DOWN", 0x21: "RIGHT", 0x22: "SRC", 0x23: "AMP", 0x24: "LFO", 0x25: "FX1", 0x26: "FX2",
    0x27: "CUE?", 0x28: "PLAY", 0x29: "REC", 0x2A: "STOP", 0x2B: "REC1?", 0x2C: "REC2?",
    0x2D: "FUNC", 0x2E: "PATTERN", 0x2F: "BANK", 0x30: "MIX", 0x31: "YES", 0x32: "NO", 0x33: "UP", 0x34: "LEFT",
    0x35: "MIDI", 0x36: "REC3?",
    **{0x38 + i: f"push {'ABCDEF'[i]}" for i in range(6)}, 0x3E: "push LEV",
}
ENCODERS = ["A", "B", "C", "D", "E", "F", "LEVEL"]
# Codes the survey has not named; drawn in their own group by number.
UNNAMED = (0x1E, 0x37, 0x3F)


class Panel:
    """Writes panel events to the port's --live FIFO."""

    def __init__(self, path):
        self.path = path
        self.fd = -1

    def send(self, line):
        # Opened on first use, non-blocking: a FIFO with no reader yet
        # (the port still loading) refuses the open and the event is
        # dropped rather than the window freezing.
        try:
            if self.fd < 0:
                self.fd = os.open(self.path, os.O_WRONLY | os.O_NONBLOCK)
            os.write(self.fd, (line + "\n").encode())
        except OSError:
            if self.fd >= 0:
                try:
                    os.close(self.fd)
                except OSError:
                    pass
            self.fd = -1

    def key(self, code, down):
        self.send(f"key 0x{code:02x} {'down' if down else 'up'}")

    def enc(self, n, delta):
        self.send(f"enc {n} {delta}")

    def pot(self, v):
        self.send(f"pot {int(v)}")


# The MKII's front, placed from Elektron's product photo (1930 x 1110 px):
# every coordinate below is the photo's, and the canvas draws them scaled by
# F from an origin at the panel's top left. The screen is the LCD at 2x,
# which is the photo's own screen size at this scale.
F, PX0, PY0 = 0.862, 60, 100
LCD_SCALE = 2
LCD_CENTRE = (913, 413)
# code, label, under, x, y, w, h (photo px)
KEYS_MK2 = [
    (0x35, "MIDI", "MIDI Sync", 148, 408, 60, 58),
    (0x2B, "REC1", "Setup 1\nPickup +", 315, 378, 62, 58),
    (0x2C, "REC2", "Setup 2\nPickup \u25b7/\u25a1", 398, 378, 62, 58),
    (0x36, "REC3", "Rec Edit\nErase", 482, 378, 62, 58),
    (0x1C, "PROJ", "Save Proj", 148, 513, 62, 58),
    (0x1D, "PART", "Part Edit", 231, 513, 62, 58),
    (0x1E, "AED", "Slice Grid", 315, 513, 62, 58),
    (0x30, "MIX", "Click", 399, 513, 62, 58),
    (0x1F, "ARR", "Arr Mode", 483, 513, 62, 58),
    (0x2D, "FUNC", "", 165, 648, 90, 56),
    (0x2A, "CUE", "Reload Part", 315, 648, 90, 56),     # 0x25.2 (KEYMAP.md; the key table gives 0x2a a press and a release handler, 0x4004e978/0x4004e968)
    (0x2E, "PTN", "Pattern Settings", 165, 773, 90, 56),
    (0x2F, "BANK", "Track Trig Edit", 315, 773, 90, 56),
    (0x31, "YES", "Arm", 447, 690, 58, 58),
    (0x32, "NO", "Disarm", 447, 773, 58, 58),
    (0x33, "\u2227", "Trig Mode", 615, 690, 58, 58),
    (0x34, "<", "\u00b5Time -", 530, 773, 58, 58),
    (0x20, "\u2228", "Trig Mode", 615, 773, 58, 58),
    (0x21, ">", "\u00b5Time +", 698, 773, 58, 58),
    (0x22, "SRC", "Note", 742, 625, 58, 58),
    (0x23, "AMP", "Arp", 826, 625, 58, 58),
    (0x24, "LFO", "LFO", 910, 625, 58, 58),
    (0x25, "FX1", "Ctrl 1", 994, 625, 58, 58),
    (0x26, "FX2", "Ctrl 2", 1078, 625, 58, 58),
    (0x29, "\u25cb", "Copy", 860, 773, 90, 58),
    (0x28, "\u25b7", "Clear", 958, 773, 90, 58),
    (0x27, "\u25a1", "Paste", 1058, 773, 90, 58),     # STOP = 0x24.7 (KEYMAP.md, E2 `stop`); same handler 0x4004aca4 in both keymaps
    (0x18, "TEMPO", "Tap Tempo\nPickup Sync", 1344, 490, 62, 62),
    (0x19, "A", "Mute", 1252, 733, 92, 92),
    (0x1A, "B", "Mute", 1755, 733, 92, 92),
    (0x1B, "PAGE", "Scale", 1755, 910, 92, 64),
] + [(0x10 + i, f"T{i + 1}", "Cue / Mute", 644 if i < 4 else 1176, 292 + 83.7 * (i % 4), 56, 56) for i in range(8)] \
  + [(i, str(i + 1), f"T{i % 8 + 1}", 165 + 99.4 * i, 907, 88, 88) for i in range(16)]
KNOBS_MK2 = [   # encoder index, label, under, x, y (photo px)
    (6, "Level", "Cursor Pos", 1342, 345),
    (0, "A", "Start Pos", 1483, 345), (1, "B", "Loop Pos", 1625, 345), (2, "C", "End Pos", 1767, 345),
    (3, "D", "Zoom \u2195", 1483, 490), (4, "E", "Scroll \u2194", 1625, 490), (5, "F", "Zoom \u2194", 1767, 490),
]
SPARE_MK2 = [(0x37, 1680, 1015), (0x3F, 1740, 1015)]    # codes not yet placed


def build_panel(tk, root, panel):
    """The MKII's front as one canvas: every key sends press and release,
    a knob turns when dragged up or down, with the wheel or with a
    trackpad's two-finger scroll (Shift: x4), and pushes on a click,
    the headphones knob drives the port's MAIN pot. Returns the canvas and where the
    screen goes on it."""
    BG, KEY, TXT, SUB, EDGE = "#1d1d1f", "#2b2b2e", "#d4d4d4", "#8e8e8e", "#38383c"
    X = lambda px: (px - PX0) * F
    Y = lambda py: (py - PY0) * F
    Wd, Hd = X(1860), Y(1075)
    cv = tk.Canvas(root, width=int(Wd), height=int(Hd), bg="#0e0e10", highlightthickness=0)
    cv.pack()
    cv.create_rectangle(X(75), Y(115), X(1845), Y(1035), fill=BG, outline="#2e2e32", width=2)
    for sx, sy in ((120, 145), (1795, 145), (120, 1010), (918, 1010), (1795, 1010)):
        cv.create_oval(X(sx) - 7, Y(sy) - 7, X(sx) + 7, Y(sy) + 7, fill="#2a2a2d", outline="#3a3a3e")
    for text, px in (("Main Out", 257), ("Cue Out", 349), ("Input A B", 451), ("Input C D", 543),
                     ("MIDI In", 655), ("MIDI Out", 760), ("MIDI Thru", 865), ("Compact Flash", 1117),
                     ("USB", 1329), ("DC In", 1540), ("Power", 1691)):
        cv.create_text(X(px), Y(143), text=text, fill="#9a9a9a", font=("Helvetica", 9))
    cv.create_oval(X(1197) - 5, Y(186) - 5, X(1197) + 5, Y(186) + 5, fill="#c8b640", outline="")
    cv.create_text(X(1197), Y(207), text="Card Status", fill="#9a9a9a", font=("Helvetica", 9))

    def rrect(x0, y0, x1, y1, r, **kw):
        pts = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1, x1 - r, y1,
               x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]
        return cv.create_polygon(pts, smooth=True, **kw)

    def key(code, label, under, px, py, pw, ph):
        tag = f"key{code}"
        x, y, w, h = X(px), Y(py), pw * F, ph * F
        fill, ink = (("#b9b9bd", "#1a1a1a") if code == 0x2D else (KEY, TXT))
        outline = "#3f8f5a" if code in (0, 4, 8, 12) else EDGE
        rrect(x - w / 2, y - h / 2, x + w / 2, y + h / 2, 9, fill=fill, outline=outline, width=2,
              tags=(tag, tag + "b"))
        size = 15 if code < 16 else 11
        cv.create_text(x, y, text=label, fill=ink, font=("Helvetica", size, "bold"), tags=tag)
        if under:
            cv.create_text(x, y + h / 2 + 7, text=under, fill=SUB, font=("Helvetica", 9), anchor="n",
                           justify="center")

        def down(e):
            cv.itemconfigure(tag + "b", fill="#5a5a60")
            panel.key(code, True)

        def up(e):
            cv.itemconfigure(tag + "b", fill=fill)
            panel.key(code, False)
        cv.tag_bind(tag, "<ButtonPress-1>", down)
        cv.tag_bind(tag, "<ButtonRelease-1>", up)

    wheel = {}                      # canvas tag -> (event, +-1): the wheel is the canvas's
    drag = {"tag": None}            # a knob being dragged: its tag, the y it started at, whether it moved

    def grab(e, tag, push):
        drag.update(tag=tag, y=e.y, moved=False, push=push)

    def motion(e):
        if drag["tag"] is None:
            return
        steps = int((drag["y"] - e.y) / 6)          # up turns up, one step per 6 px
        if steps:
            drag["moved"] = True
            drag["y"] -= steps * 6
            wheel[drag["tag"]](e, steps)

    def letgo(e):
        if drag["tag"] is not None and not drag["moved"] and drag["push"] is not None:
            panel.key(drag["push"], True)            # a click without a drag pushes
            panel.key(drag["push"], False)
        drag["tag"] = None
    cv.bind("<B1-Motion>", motion, add="+")
    cv.bind("<ButtonRelease-1>", letgo, add="+")

    def knob(n, label, under, px, py, r=38):
        tag = f"knob{n}"
        x, y, r = X(px), Y(py), r * F
        cv.create_oval(x - r - 3, y - r - 3, x + r + 3, y + r + 3, fill="#141416", outline="", tags=tag)
        cv.create_oval(x - r, y - r, x + r, y + r, fill="#3a3a3f", outline="#505056", width=1, tags=tag)
        cv.create_oval(x - r * 0.72, y - r * 0.72, x + r * 0.72, y + r * 0.72, fill="#2f2f33", outline="", tags=tag)
        cv.create_text(x, y + r + 12, text=label, fill=TXT, font=("Helvetica", 11, "bold"))
        cv.create_text(x, y + r + 26, text=under, fill=SUB, font=("Helvetica", 9))
        push = 0x38 + n if n < 6 else 0x3E
        wheel[tag] = lambda e, d: panel.enc(n, d * (4 if e.state & 1 else 1))
        cv.tag_bind(tag, "<ButtonPress-1>", lambda e: grab(e, tag, push))

    # the screen's bezel and legends
    lw, lh = W * LCD_SCALE, H * LCD_SCALE
    lx, ly = X(LCD_CENTRE[0]) - lw / 2, Y(LCD_CENTRE[1]) - lh / 2
    cv.create_rectangle(X(718), Y(270), X(1105), Y(560), fill="#0a0a0b", outline="#222")
    cv.create_text(X(750), Y(310), anchor="w", text="8 Track Dynamic Performance Sampler", fill="#d0d0d0",
                   font=("Helvetica", 10, "bold"))
    cv.create_text(X(750), Y(533), anchor="w", text="Octatrack", fill="#e4e4e4", font=("Helvetica", 18, "bold"))
    cv.create_text(X(750) + 108, Y(533), anchor="w", text="MKII", fill="#bdbdbd", font=("Helvetica", 18))

    for k in KEYS_MK2:
        key(*k)
    for k in KNOBS_MK2:
        knob(*k)
    for code, px, py in SPARE_MK2:
        key(code, f"{code:02x}", "", px, py, 50, 30)

    # page keys' "Setup" bracket, the trigs' brackets
    cv.create_line(X(745), Y(700), X(1080), Y(700), fill="#555")
    cv.create_rectangle(X(910) - 20, Y(700) - 7, X(910) + 20, Y(700) + 7, fill=BG, outline="")
    cv.create_text(X(910), Y(700), text="Setup", fill=SUB, font=("Helvetica", 9))
    for a, b, t in ((120, 905, "Track Trigs"), (915, 1700, "Sample / MIDI Trigs")):
        cv.create_line(X(a), Y(985), X(a), Y(995), X(b), Y(995), X(b), Y(985), fill="#555")
        tw = 4 * len(t) + 8
        cv.create_rectangle(X((a + b) / 2) - tw, Y(995) - 7, X((a + b) / 2) + tw, Y(995) + 7, fill=BG, outline="")
        cv.create_text(X((a + b) / 2), Y(995), text=t, fill=SUB, font=("Helvetica", 9))

    # LEDs: the inputs, the scale page
    for text, xs in (("A \u2014 B", (295, 337)), ("C \u2014 D", (380, 421)), ("- Int -", (463, 505))):
        cv.create_text(X(sum(xs) / 2), Y(296), text=text, fill=SUB, font=("Helvetica", 9))
        for xx in xs:
            cv.create_oval(X(xx) - 6, Y(316) - 6, X(xx) + 6, Y(316) + 6, fill="#8a8a8a", outline="")
    for i, t in enumerate(("1:4", "2:4", "3:4", "4:4")):
        xx = 1710 + 29 * i
        cv.create_text(X(xx), Y(828), text=t, fill=SUB, font=("Helvetica", 8))
        cv.create_oval(X(xx) - 6, Y(848) - 6, X(xx) + 6, Y(848) + 6,
                       fill="#e0a030" if i == 0 else "#8a8a8a", outline="")

    # the headphones knob is the port's MAIN pot: wheel it
    level = {"v": 200}
    px, py, r = X(183), Y(290), 36 * F
    cv.create_oval(px - r, py - r, px + r, py + r, fill="#2c2c30", outline="#4a4a50", width=2, tags="pot")
    potv = cv.create_text(px, py, text="200", fill=TXT, font=("Helvetica", 10), tags="pot")
    cv.create_text(px, py + r + 12, text="Headphones Vol", fill=TXT, font=("Helvetica", 10, "bold"))

    def pot(d):
        level["v"] = max(0, min(255, level["v"] + d))
        cv.itemconfigure(potv, text=str(level["v"]))
        panel.pot(level["v"])
    wheel["pot"] = lambda e, d: pot(8 * d)
    cv.tag_bind("pot", "<ButtonPress-1>", lambda e: grab(e, "pot", None))

    # the crossfader: drawn, not modelled by the port
    fy = Y(728)
    for i in range(10):
        xx = X(1390 + 25 * i)
        cv.create_line(xx, fy - 42 * F, xx, fy - 20 * F, fill="#555")
        cv.create_line(xx, fy + 20 * F, xx, fy + 42 * F, fill="#555")
    cv.create_line(X(1360), fy, X(1645), fy, fill="#46464a", width=8)
    cv.create_rectangle(X(1490), fy - 32 * F, X(1522), fy + 32 * F, fill="#d8d8d8", outline="#999")
    cv.create_text(X(1503), fy + 58 * F, text="crossfader: not modelled", fill=SUB, font=("Helvetica", 8))

    def on_wheel(e, d):
        for it in cv.find_withtag("current"):
            for t in cv.gettags(it):
                if t in wheel:
                    wheel[t](e, d)
                    return
    cv.bind("<MouseWheel>", lambda e: on_wheel(e, 1 if e.delta > 0 else -1))
    cv.bind("<Button-4>", lambda e: on_wheel(e, 1))
    cv.bind("<Button-5>", lambda e: on_wheel(e, -1))
    # Tk 9 delivers a trackpad's two-finger scroll as <TouchpadScroll>, not
    # <MouseWheel>: %D packs deltaX in the high 16 bits and deltaY in the low.
    pad = {"acc": 0}

    def on_pad(e):
        dy = e.delta & 0xFFFF
        dy = dy - 0x10000 if dy & 0x8000 else dy
        pad["acc"] -= dy
        steps = int(pad["acc"] / 8)
        if steps:
            pad["acc"] -= steps * 8
            on_wheel(e, steps)
    try:
        cv.bind("<TouchpadScroll>", on_pad)
    except tk.TclError:              # Tk 8.6 has no such event; its trackpad sends <MouseWheel>
        pass
    cv.create_text(X(960), Y(1057), text="knobs: drag up/down, or scroll over one (Shift x4); a click pushes it.   "
                   "keyboard: arrows, Return = YES, Esc = NO, space = PLAY, F1-F5 = pages, 1-8 q-i = trigs",
                   fill="#6e6e6e", font=("Helvetica", 9))

    # keyboard
    kb = {"Left": 0x34, "Right": 0x21, "Up": 0x33, "Down": 0x20, "Return": 0x31, "Escape": 0x32, "space": 0x28,
          "F1": 0x22, "F2": 0x23, "F3": 0x24, "F4": 0x25, "F5": 0x26}
    for i, ch in enumerate("12345678qwertyui"):
        kb[ch] = i
    held = set()

    def press(e):
        code = kb.get(e.keysym)
        if code is not None and code not in held:
            held.add(code)
            panel.key(code, True)

    def release(e):
        code = kb.get(e.keysym)
        if code is not None and code in held:
            held.discard(code)
            panel.key(code, False)
    root.bind("<KeyPress>", press)
    root.bind("<KeyRelease>", release)
    return cv, lx, ly, LCD_SCALE


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("plane", help="the file --lcd writes")
    ap.add_argument("--png", help="write one PNG of the current frame and exit")
    ap.add_argument("--term", action="store_true", help="draw in the terminal instead of a window")
    ap.add_argument("--panel", help="the port's --live FIFO: draw keys and encoders under the screen and write events to it")
    ap.add_argument("--scale", type=int, default=4)
    a = ap.parse_args()

    if a.png:
        png(screen(read_plane(a.plane)), a.png, a.scale)
        print(a.png)
        return

    if a.term:
        def draw(rows):
            sys.stdout.write("\x1b[H\x1b[2J" + term(rows) + "\n")
            sys.stdout.flush()
        try:
            for _ in watch(a.plane, draw):
                pass
        except KeyboardInterrupt:
            pass
        return

    import tkinter as tk
    root = tk.Tk()
    root.title(os.path.basename(a.plane))
    root.resizable(False, False)
    root.title(os.path.basename(a.plane) + (" + panel" if a.panel else ""))
    if a.panel:
        canvas, ox, oy, scale = build_panel(tk, root, Panel(a.panel))
    else:
        canvas = tk.Canvas(root, width=W * a.scale, height=H * a.scale, bg="#%02x%02x%02x" % OFF,
                           highlightthickness=0)
        canvas.pack()
        ox, oy, scale = 0, 0, a.scale
    on = "#%02x%02x%02x" % ON
    state = {"img": None}

    def draw(rows):
        img = tk.PhotoImage(width=W, height=H)
        data = " ".join("{" + " ".join(on if v else "#%02x%02x%02x" % OFF for v in row) + "}" for row in rows)
        img.put(data, to=(0, 0))
        img = img.zoom(scale, scale)
        canvas.delete("lcd")
        canvas.create_image(ox, oy, anchor="nw", image=img, tags="lcd")
        state["img"] = img

    gen = watch(a.plane, draw, period=0)

    def tick():
        next(gen)
        root.after(50, tick)
    tick()
    root.mainloop()


if __name__ == "__main__":
    main()
