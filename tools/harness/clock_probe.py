#!/usr/bin/env python3
"""The DSP core clock from a probe-55 recording.

    python3 tools/harness/clock_probe.py capture.wav [--lr 2,3]

Probe 55 (branch probe55, 22 Sep 2026) prints on the delay host a square
wave toggled per block: L at amplitude (timer-0 advance per frame) << 7,
R at 32768 << 7. Timer 0 counts the core clock / 2, so

    cycles per sample = advance / 8 = 32768 * rms(L) / rms(R) / 8

independent of every gain between the DSP and the file. The two channels
are read from the capture's channel indices given by --lr (the MicroBook's
3/4 are indices 2,3); a mono-per-channel file works with --lr 0,1.
"""
import sys, wave, math
import numpy as np


def load(path):
    w = wave.open(path); n, ch, sw, sr = w.getnframes(), w.getnchannels(), w.getsampwidth(), w.getframerate()
    raw = w.readframes(n); w.close()
    if sw == 2:
        x = np.frombuffer(raw, np.int16).astype(float) / 32768
    elif sw == 3:
        b = np.frombuffer(raw, np.uint8).reshape(-1, 3).astype(np.int32)
        x = b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)
        x = np.where(x >= 1 << 23, x - (1 << 24), x) / float(1 << 23)
    else:
        x = np.frombuffer(raw, np.int32).astype(float) / 2 ** 31
    return x.reshape(-1, ch), sr


def main():
    path = sys.argv[1]
    lr = (2, 3)
    if "--lr" in sys.argv:
        lr = tuple(int(v) for v in sys.argv[sys.argv.index("--lr") + 1].split(","))
    x, sr = load(path)
    L, R = x[:, lr[0]], x[:, lr[1]]
    # the middle 60 % of the file, away from the start/stop edges
    a, b = len(L) * 2 // 10, len(L) * 8 // 10
    L, R = L[a:b], R[a:b]
    rl, rr = math.sqrt(np.mean(L * L)), math.sqrt(np.mean(R * R))
    ratio = rl / rr
    adv = 32768 * ratio
    cps = adv / 8
    print(f"file {path}: {sr} Hz, channels {lr}, {b - a} samples analysed")
    print(f"rms L {20*math.log10(rl+1e-12):.2f} dBFS, R {20*math.log10(rr+1e-12):.2f} dBFS, L/R {ratio:.5f}")
    print(f"timer advance per frame {adv:.1f} (CLK/2), core cycles per sample {cps:.1f}, "
          f"core clock {cps * sr / 1e6:.3f} MHz at fs = {sr}")
    print(f"  4160/sample = 183.456 MHz (EXTAL 22.5792 x 195/24); 4535 = 200 MHz")
    print(f"  if the timer counts CLK (not CLK/2) halve the result: {cps/2:.1f}")


if __name__ == "__main__":
    main()
