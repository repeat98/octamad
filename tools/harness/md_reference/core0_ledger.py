#!/usr/bin/env python3
"""Classify every word of core 0's X, Y and the shared window from a port
word map (WP-A1).

The word map comes from the ColdFire port built with `core0_wordmap.patch`
(an isolated build; see `core0_wordmap.sh`), run with `--dsp-wordmap FILE`.
For every word of X, Y and P below 0x40000 on each core it holds:
  flags  bit 0 written before the first frame vector (load or init)
         bit 1 written after it (runtime)
         bit 2 a runtime write was non-zero
         bit 3 read before the first frame vector
         bit 4 read at runtime
  W      frame epochs in which the word was written
  R      frame epochs in which it was read
  RB     frame epochs in which it was read BEFORE any write in that epoch
An epoch is the span between two frame vectors: 0x18 on core 0, 0x12 on core 1.

Classes (per word):
  state    written at runtime and read before written in some epoch: it
           carries a value from one frame to the next
  scratch  written at runtime, and every runtime read follows a write in
           the same epoch
  table    read at runtime, never written at runtime
  loaded   written at load/init, never touched at runtime
  garbage  read at runtime but never written at all (reads what boot left)
  free     never touched after the first frame vector, never loaded

    core0_ledger.py WORDMAP [WORDMAP ...] [--payload A]

With several word maps (one per project configuration) each word gets the
most-used class any run gave it (state > scratch > garbage > table >
loaded > free), so "free" means free in every run.
"""
import argparse, pathlib, struct, sys

import numpy as np

N = 0x40000
ROOT = pathlib.Path(__file__).resolve().parents[3]


def load(path):
    raw = pathlib.Path(path).read_bytes()
    magic, ncores, e0, e1 = struct.unpack_from("<4I", raw, 0)
    if magic != 0x41314d50:
        sys.exit(f"{path}: not a word map")
    off = 16
    cores = []
    for c in range(ncores):
        areas = []
        for a in range(3):
            fl = np.frombuffer(raw, np.uint8, N, off); off += N
            w = np.frombuffer(raw, np.uint16, N, off); off += 2 * N
            r = np.frombuffer(raw, np.uint16, N, off); off += 2 * N
            rb = np.frombuffer(raw, np.uint16, N, off); off += 2 * N
            areas.append((fl, w, r, rb))
        cores.append(areas)
    return cores, (e0, e1)


CLASSES = ("state", "scratch", "table", "loaded", "garbage", "free")


def classify(fl, w, r, rb, loaded):
    rtw = (fl & 2) != 0
    rtr = (fl & 16) != 0
    initw = ((fl & 1) != 0) | loaded
    cls = np.full(N, 5, np.uint8)                       # free
    cls[initw & ~rtw & ~rtr] = 3                         # loaded
    cls[~rtw & rtr & initw] = 2                          # table
    cls[~rtw & rtr & ~initw] = 4                         # garbage
    cls[rtw & (rb == 0)] = 1                             # scratch
    cls[rtw & (rb > 0)] = 0                              # state
    return cls


def runs(cls, lo, hi):
    out = []
    a = lo
    while a < hi:
        b = a
        while b < hi and cls[b] == cls[a]:
            b += 1
        out.append((a, b, int(cls[a])))
        a = b
    return out


def payload_loaded(tag):
    sys.path.insert(0, str(ROOT / "tools")); import toolpath  # noqa: F401
    from dsp_modmap import IMG, PAYLOADS, modules
    img = IMG.read_bytes()
    va, ln = [(v, l) for t, v, l in PAYLOADS if t == tag][0]
    mods, _ = modules(img, va, ln)
    m = {1: np.zeros(N, bool), 2: np.zeros(N, bool), 0: np.zeros(N, bool)}
    for sp, addr, cnt, _data in mods:
        if sp in m:
            m[sp][addr:min(N, addr + cnt)] = True
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("wordmap", nargs="+")
    ap.add_argument("--payload", default="A")
    ap.add_argument("--core", type=int, default=0)
    a = ap.parse_args()
    maps = [load(f) for f in a.wordmap]
    ld = payload_loaded(a.payload)
    for f, (_c, ep) in zip(a.wordmap, maps):
        print(f"# {f}: epochs core 0 {ep[0]}, core 1 {ep[1]}")
    print(f"# core {a.core}, payload {a.payload}")
    RANK = np.array([5, 4, 2, 1, 3, 0])                 # state scratch table loaded garbage free -> usage rank

    def merged(pick, loaded):
        best = None
        acc = None
        for cores, _ep in maps:
            fl, w, r, rb = pick(cores)
            cls = classify(fl, w, r, rb, loaded)
            if best is None:
                best, acc = cls.copy(), [w.copy(), r.copy(), rb.copy()]
            else:
                take = RANK[cls] > RANK[best]
                best[take] = cls[take]
                acc = [np.maximum(acc[0], w), np.maximum(acc[1], r), np.maximum(acc[2], rb)]
        return best, acc

    def show(name, cls, w, r, rb, lo, hi):
        tot = {c: int((cls[lo:hi] == i).sum()) for i, c in enumerate(CLASSES)}
        print(f"\n## {name}:{lo:#07x}-{hi - 1:#07x}  " + "  ".join(f"{c} {n}" for c, n in tot.items() if n))
        for s, e, c in runs(cls, lo, hi):
            n = e - s
            extra = ""
            if CLASSES[c] in ("state", "scratch"):
                extra = f"  (written in up to {int(w[s:e].max())} epochs, read-before-write in up to {int(rb[s:e].max())})"
            elif CLASSES[c] == "table":
                extra = f"  (read in up to {int(r[s:e].max())} epochs)"
            print(f"{name}:{s:#07x}-{e - 1:#07x}  {n:6d}  {CLASSES[c]}{extra}")

    for name, ai, sp, hi in (("X", 0, 1, 0x9000), ("Y", 1, 2, 0xc000)):
        cls, (w, r, rb) = merged(lambda cores, ai=ai: cores[a.core][ai], ld[sp])
        show(name, cls, w, r, rb, 0, hi)
    # The window is ONE memory that P, X and Y all address, shared by both
    # cores: judge it per core on the union of its three views.
    wl = np.zeros(N, bool)
    for sp in (0, 1, 2):
        wl |= ld[sp]

    def union(cores, core):
        fl = np.zeros(N, np.uint8); w = np.zeros(N, np.uint16); r = np.zeros(N, np.uint16); rb = np.zeros(N, np.uint16)
        for ai in range(3):
            f2, w2, r2, rb2 = cores[core][ai]
            fl |= f2; w = np.maximum(w, w2); r = np.maximum(r, r2); rb = np.maximum(rb, rb2)
        return fl, w, r, rb
    for core in range(len(maps[0][0])):
        cls, (w, r, rb) = merged(lambda cores, core=core: union(cores, core), wl)
        show(f"window core {core}", cls, w, r, rb, 0x30000, 0x40000)

if __name__ == "__main__":
    main()
