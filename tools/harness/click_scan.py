#!/usr/bin/env python3
"""Find clicks in a multichannel recording: per channel, the sample steps
that stand out from the channel's own material.

  python3 tools/harness/click_scan.py out/usb_take1.wav [--ratio 8] [--top 20]

A step is |x[n] - x[n-1]|. A click is a step above `ratio` times the
channel's 99th-percentile step (the material's own transients set that
percentile, so a drum loop's hits do not count). Prints each channel's
percentile, its count above the threshold, and the largest events with
their time, so they can be lined up against a counter watch
(tools/hw/usb_counters.py) or an eye on the transport. Reads any WAV
soundfile/wave can read (16/24/32-bit PCM); 16-channel USB takes and stereo
main captures alike.
"""
import argparse
import sys
import wave

import numpy as np


def load(path):
    try:
        import soundfile as sf
        data, rate = sf.read(path, dtype="float64", always_2d=True)
        return data, rate
    except ImportError:
        w = wave.open(path)
        n, ch, sw, rate = w.getnframes(), w.getnchannels(), w.getsampwidth(), w.getframerate()
        raw = w.readframes(n)
        if sw == 2:
            d = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768
        elif sw == 3:
            b = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3).astype(np.int32)
            v = b[:, 0] | b[:, 1] << 8 | b[:, 2] << 16
            d = np.where(v >= 1 << 23, v - (1 << 24), v).astype(np.float64) / (1 << 23)
        else:
            d = np.frombuffer(raw, dtype="<i4").astype(np.float64) / (1 << 31)
        return d.reshape(-1, ch), rate


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("wav")
    ap.add_argument("--ratio", type=float, default=8.0, help="threshold = ratio x the channel's p99 step")
    ap.add_argument("--top", type=int, default=20, help="events to list per channel")
    a = ap.parse_args()
    data, rate = load(a.wav)
    n, ch = data.shape
    print(f"{a.wav}: {ch} channel(s), {n / rate:.1f} s at {rate} Hz")
    total = 0
    for c in range(ch):
        x = data[:, c]
        if not np.any(x):
            print(f"  ch {c + 1:2d}: silent")
            continue
        step = np.abs(np.diff(x))
        p99 = float(np.percentile(step, 99))
        thr = a.ratio * p99
        idx = np.flatnonzero(step > thr)
        total += len(idx)
        rms = 20 * np.log10(max(np.sqrt(np.mean(x * x)), 1e-9))
        print(f"  ch {c + 1:2d}: rms {rms:6.1f} dBFS  p99 step {p99:.5f}  {len(idx)} step(s) above {thr:.4f}")
        for i in idx[np.argsort(step[idx])[::-1][:a.top]]:
            print(f"      {i / rate:9.4f} s  step {step[i]:.4f}  ({x[i]:+.4f} -> {x[i + 1]:+.4f})")
    print(f"{total} event(s) in all")
    return 0


if __name__ == "__main__":
    sys.exit(main())
