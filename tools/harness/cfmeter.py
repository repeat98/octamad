#!/usr/bin/env python3
"""Decode CF METER's readout (modules/cfmeter) from a capture of track 8.

    python3 tools/harness/cfmeter.py capture.wav [--lr 14,15]   # USB AUDIO: T8 = channels 15/16
    python3 tools/harness/cfmeter.py --dump out/setverify/port.dump   # the port's read-back blocks

The insert prints a square wave per 16-sample block: L = N x 128, R =
8192 x 128 (24-bit units), so N = 8192 x |L| / |R| per block, whatever
the gain after the slot. N steps through eight slots, 125 ms each, the
first 0 (the sync) and the second 8192. Each cycle is printed as one row:
idle %, the frame interrupt's mean and longest duration and the frame
period in microseconds (DMA timer 3 taken at 132 MHz; the period column
checks that rate: 16 / 44,100 s = 362.8 us), the idle loop's shortest
step in timer counts, and BURN in microseconds.
"""
import argparse, math, statistics, sys, wave
import numpy as np

CLK = 132e6
REF = 8192


def load_wav(path, lr):
    w = wave.open(path)
    n, ch, sw = w.getnframes(), w.getnchannels(), w.getsampwidth()
    raw = w.readframes(n); w.close()
    if sw == 2:
        x = np.frombuffer(raw, np.int16).astype(float) / 32768
    elif sw == 3:
        b = np.frombuffer(raw, np.uint8).reshape(-1, 3).astype(np.int32)
        x = b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)
        x = np.where(x >= 1 << 23, x - (1 << 24), x) / float(1 << 23)
    else:
        x = np.frombuffer(raw, np.int32).astype(float) / 2 ** 31
    x = x.reshape(-1, ch)
    return x[:, lr[0]], x[:, lr[1]]


def load_dump(path):
    """Track 8 from the port's read-back blocks (RB_BASE + bank*1024 +
    track*128 + frame*8, 32-bit L,R): the core-0 classes at 0x80003390 and
    0x80003790 hold tracks 5-8."""
    sys.path.insert(0, __file__.rsplit("/", 1)[0])
    import blockdump
    blocks = [(f, w) for d, f, ch, core, ram, w in blockdump.read(path)
              if d == "<" and ch == 1 and core == 0 and ram in (0x80003390, 0x80003790)]
    blocks.sort()
    L, R = [], []
    for _, w in blocks:
        seg = w[192:256]
        v = [(seg[2 * i] << 16 | seg[2 * i + 1]) for i in range(32)]
        v = [(x - (1 << 32) if x >= 1 << 31 else x) / 2 ** 31 for x in v]
        L += v[0::2]; R += v[1::2]
    return np.array(L), np.array(R)


def per_block(L, R, n=16):
    m = len(L) // n
    l = np.sqrt(np.mean(L[:m * n].reshape(m, n) ** 2, axis=1))
    r = np.sqrt(np.mean(R[:m * n].reshape(m, n) ** 2, axis=1))
    return np.where(r > 1e-6, REF * l / np.maximum(r, 1e-9), np.nan)


def cycles(nb):
    """Each cycle starts where N steps from the sync (~0) to the reference
    (8192); its eight slots are one eighth of the distance to the next such
    edge each, read as the median of each slot's middle half."""
    ok = ~np.isnan(nb)
    ref = ok & (np.abs(nb - REF) < 0.01 * REF)
    sync = ok & (np.abs(nb) < 20)
    edges = [i for i in range(1, len(nb)) if ref[i] and sync[i - 1]]
    rows = []
    for e0, e1 in zip(edges, edges[1:]):
        seg = (e1 - e0) / 8
        row = []
        for k in range(8):
            a = e0 + int((k - 1 + 0.25) * seg) if k else e0 - int(0.75 * seg)
            b = e0 + int((k - 1 + 0.75) * seg) if k else e0 - int(0.25 * seg)
            row.append(float(np.nanmedian(nb[max(a, 0):b])))
        rows.append(row)
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("wav", nargs="?")
    ap.add_argument("--lr", default="14,15", help="0-based channel indices of T8 L,R in the file")
    ap.add_argument("--dump", help="a ot_emu --block-dump file instead of a capture")
    a = ap.parse_args()
    if a.dump:
        L, R = load_dump(a.dump)
    else:
        L, R = load_wav(a.wav, tuple(int(v) for v in a.lr.split(",")))
    nb = per_block(L, R)
    rows = cycles(nb)
    if not rows:
        sys.exit("cfmeter: no sync -> reference edge pair found")
    us = lambda q: q * 4 / CLK * 1e6
    print(f"{len(rows)} cycle(s) of 1 s; values are the medians of each 125 ms slot")
    print(f"{'idle %':>7} {'isr mean us':>11} {'isr max us':>10} {'period us':>9} {'isr %':>6} {'step cnt':>8} {'burn us':>7}")
    for r in rows:
        idle = r[2] / 16384 * 100
        per = us(r[5])
        print(f"{idle:7.2f} {us(r[3]):11.1f} {us(r[4]):10.1f} {per:9.1f} "
              f"{(us(r[3]) / per * 100 if per else float('nan')):6.1f} {r[6]:8.0f} {us(r[7]):7.1f}")
    med = lambda j: statistics.median(r[j] for r in rows)
    print(f"median: idle {med(2) / 16384 * 100:.2f} %, isr mean {us(med(3)):.1f} us, "
          f"isr max {us(med(4)):.1f} us, period {us(med(5)):.1f} us (16/44100 s = 362.8 us)")


if __name__ == "__main__":
    main()
