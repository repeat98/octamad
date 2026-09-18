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

The file is the firmware's own 1-bpp plane at 0x46c7e0ea (1,024 bytes):
64 columns x 128 rows, 8 bytes per row, MSB left. Screen pixel (x, y) is
column 63-y of row x -- the panel is stored rotated a quarter turn.
Measured 17 Sep 2026 by rendering a dump under each candidate layout; the
PLAYBACK page reads upright under this one and under no other.
"""
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


def read_plane(path):
    with open(path, "rb") as f:
        data = f.read()
    if len(data) != 1024:
        raise ValueError(f"{path}: {len(data)} bytes, want 1024")
    return data


def watch(path, on_frame, period=0.05):
    last = None
    while True:
        try:
            st = os.stat(path)
            key = (st.st_mtime_ns, st.st_size)
            if key != last:
                last = key
                on_frame(pixels(read_plane(path)))
        except (FileNotFoundError, ValueError):
            pass
        yield
        time.sleep(period)


# Key codes are the panel controller's: the keymap the firmware installs
# ([0x46c901dc]) is the identity, so code = row*8 + bit. Names from
# docs/firmware/EXTERNAL.md (octamax) and the 18 Sep 2026 probe under the
# port (PLAY/STOP/REC/MIDI...); an unlisted code is drawn by its number.
KEYS = {
    **{i: f"{i + 1}" for i in range(16)},          # trig keys
    **{0x10 + i: f"T{i + 1}" for i in range(8)},   # track keys
    0x1C: "MENU", 0x20: "DOWN", 0x21: "RIGHT", 0x22: "SRC", 0x23: "AMP", 0x24: "LFO", 0x25: "FX1", 0x26: "FX2",
    0x28: "PLAY", 0x29: "REC", 0x2A: "STOP",
    0x2D: "FUNC", 0x2E: "PTN", 0x2F: "BANK", 0x31: "YES", 0x32: "NO", 0x33: "UP", 0x34: "LEFT",
    0x35: "MIDI",
    **{0x38 + i: f"push {'ABCDEF'[i]}" for i in range(6)}, 0x3E: "push LEV",
}
ENCODERS = ["A", "B", "C", "D", "E", "F", "LEV"]


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


def build_panel(tk, root, panel):
    frame = tk.Frame(root)
    frame.pack(fill="x", padx=4, pady=4)

    def keybtn(parent, code, width=5):
        b = tk.Button(parent, text=KEYS.get(code, f"{code:02x}"), width=width)
        b.bind("<ButtonPress-1>", lambda e, c=code: panel.key(c, True))
        b.bind("<ButtonRelease-1>", lambda e, c=code: panel.key(c, False))
        return b

    # encoders: label (wheel), -4 -1 +1 +4, push
    enc = tk.Frame(frame)
    enc.pack(fill="x")
    for n, name in enumerate(ENCODERS):
        col = tk.Frame(enc)
        col.pack(side="left", padx=2)
        lab = tk.Label(col, text=name, width=4, relief="ridge")
        lab.pack()
        lab.bind("<MouseWheel>", lambda e, i=n: panel.enc(i, 1 if e.delta > 0 else -1))
        lab.bind("<Button-4>", lambda e, i=n: panel.enc(i, 1))
        lab.bind("<Button-5>", lambda e, i=n: panel.enc(i, -1))
        row = tk.Frame(col)
        row.pack()
        for d in (-4, -1, 1, 4):
            tk.Button(row, text=f"{d:+d}", width=2, command=lambda i=n, dd=d: panel.enc(i, dd)).pack(side="left")
        keybtn(col, 0x38 + n, width=8).pack()
    pot = tk.Scale(enc, from_=255, to=0, orient="vertical", label="MAIN", length=80, command=panel.pot)
    pot.set(200)
    pot.pack(side="left", padx=6)

    # navigation + page keys + transport
    nav = tk.Frame(frame)
    nav.pack(fill="x", pady=2)
    for code in (0x22, 0x23, 0x24, 0x25, 0x26):
        keybtn(nav, code).pack(side="left")
    tk.Label(nav, text=" ").pack(side="left")
    for code in (0x34, 0x33, 0x20, 0x21, 0x31, 0x32):
        keybtn(nav, code).pack(side="left")
    tk.Label(nav, text=" ").pack(side="left")
    for code in (0x28, 0x2A, 0x29):
        keybtn(nav, code).pack(side="left")

    # mode keys: everything not placed above, by code
    placed = set(range(16)) | set(range(0x10, 0x18)) | {0x22, 0x23, 0x24, 0x25, 0x26, 0x34, 0x33, 0x20, 0x21, 0x31, 0x32, 0x28, 0x2A, 0x29} | set(range(0x38, 0x3F))
    modes = tk.Frame(frame)
    modes.pack(fill="x", pady=2)
    for code in range(0x40):
        if code not in placed:
            keybtn(modes, code, width=4).pack(side="left")

    tracks = tk.Frame(frame)
    tracks.pack(fill="x", pady=2)
    for code in range(0x10, 0x18):
        keybtn(tracks, code, width=3).pack(side="left")
    trigs = tk.Frame(frame)
    trigs.pack(fill="x", pady=2)
    for code in range(16):
        keybtn(trigs, code, width=3).pack(side="left")

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


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("plane", help="the file --lcd writes")
    ap.add_argument("--png", help="write one PNG of the current frame and exit")
    ap.add_argument("--term", action="store_true", help="draw in the terminal instead of a window")
    ap.add_argument("--panel", help="the port's --live FIFO: draw keys and encoders under the screen and write events to it")
    ap.add_argument("--scale", type=int, default=4)
    a = ap.parse_args()

    if a.png:
        png(pixels(read_plane(a.plane)), a.png, a.scale)
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
    canvas = tk.Canvas(root, width=W * a.scale, height=H * a.scale, bg="#%02x%02x%02x" % OFF, highlightthickness=0)
    canvas.pack()
    if a.panel:
        build_panel(tk, root, Panel(a.panel))
    on = "#%02x%02x%02x" % ON
    state = {"img": None}

    def draw(rows):
        img = tk.PhotoImage(width=W, height=H)
        data = " ".join("{" + " ".join(on if v else "#%02x%02x%02x" % OFF for v in row) + "}" for row in rows)
        img.put(data, to=(0, 0))
        img = img.zoom(a.scale, a.scale)
        canvas.delete("all")
        canvas.create_image(0, 0, anchor="nw", image=img)
        state["img"] = img

    gen = watch(a.plane, draw, period=0)

    def tick():
        next(gen)
        root.after(50, tick)
    tick()
    root.mainloop()


if __name__ == "__main__":
    main()
