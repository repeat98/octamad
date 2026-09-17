#!/usr/bin/env python3
"""Show the Octatrack's screen from the port's plane file.

    ./out/emu/ot_emu ... --lcd out/lcd.bin        # the port, in one terminal
    .venv/bin/python3 tools/emu/lcd_view.py out/lcd.bin          # a window
    .venv/bin/python3 tools/emu/lcd_view.py out/lcd.bin --term   # in the terminal
    .venv/bin/python3 tools/emu/lcd_view.py out/lcd.bin --png shot.png

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


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("plane", help="the file --lcd writes")
    ap.add_argument("--png", help="write one PNG of the current frame and exit")
    ap.add_argument("--term", action="store_true", help="draw in the terminal instead of a window")
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
    canvas = tk.Canvas(root, width=W * a.scale, height=H * a.scale, bg="#%02x%02x%02x" % OFF, highlightthickness=0)
    canvas.pack()
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
