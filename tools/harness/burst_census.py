"""Census of one-off full-scale events in a MicroBook take, both channels.

Events: second-difference > 0.35 FS with no comparable event one pattern
period either side (a repeating hit is the music, a one-off is a burst).
For each event on either channel, the OTHER channel is aligned against
its own copy 1-2 trig spacings earlier (the audio repeats every trig) and
the difference over the event block is printed: a block-constant offset
below the 0.35 threshold is invisible to the event detector but is the
same fault (24 Sep 2026: every R burst had a sign-flipped T1 block).

usage: burst_census.py take.wav [T1_IDX T5_IDX]   (default channels 2, 3)
"""
import wave, numpy as np, sys

path = sys.argv[1]
c1, c5 = (int(sys.argv[2]), int(sys.argv[3])) if len(sys.argv) > 3 else (2, 3)
w = wave.open(path); n, ch, sr = w.getnframes(), w.getnchannels(), w.getframerate()
a = np.frombuffer(w.readframes(n), dtype=np.int32).reshape(-1, ch).astype(np.float64) / 2**31
T1, T5 = a[:, c1], a[:, c5]
chans = (("T1/L", T1, T5), ("T5/R", T5, T1))
for name, x, _ in chans:
    rms = np.sqrt(np.mean(x**2)); print(f"{name}: peak {np.max(np.abs(x)):.3f} rms {20*np.log10(rms+1e-12):.1f} dBFS")
env = np.abs(T1); env = np.convolve(env, np.ones(441)/441, mode="same")[::10]
lags = np.arange(int(1.5*sr/10), int(4.2*sr/10)); e = env - env.mean()
ac = [np.dot(e[:-l], e[l:]) for l in lags]; P = int(lags[int(np.argmax(ac))] * 10)
print("pattern period", P, "samples =", P/sr, "s")

def oneoffs(x):
    d2 = np.abs(np.diff(x, 2)); out = []
    for i in np.where(d2 > 0.35)[0]:
        if out and i - out[-1][0] < 2000:
            out[-1][1] = max(out[-1][1], d2[i]); out[-1][2] = i; continue
        lo, hi = max(0, i-80), i+80
        b = d2[max(0,lo-P):max(0,hi-P)].max() if i-P > 80 else 0
        f = d2[lo+P:hi+P].max() if hi+P < len(d2) else 0
        if max(b, f) < 0.5 * d2[i]: out.append([i, d2[i], i])
    return out

def aligned_copy(x, s):
    """Best earlier copy of x[s-60:s-4] at k * (P / d) back, within +-250 samples."""
    w = x[s-60:s-4]; best = (0, 0)
    for d in (1, 2, 3, 4, 6, 8):
        for k in (1, 2):
            c = s - k * P // d
            if c < 400: continue
            for off in range(-250, 251):
                v = x[c+off-60:c+off-4]
                r = np.dot(w, v) / (np.linalg.norm(w) * np.linalg.norm(v) + 1e-12)
                if r > best[0]: best = (r, c + off)
    return best

for name, x, other in chans:
    ev = oneoffs(x)
    oname = "T5/R" if name == "T1/L" else "T1/L"
    print(f"{name}: one-off events: {len(ev)}  times:", " ".join(f"{s/sr:.3f}" for s, m, e in ev), " spans:", [int(e-s+1) for s, m, e in ev])
    for s, m, e in ev:
        print(f"  t={s/sr:.3f}s {name}:", " ".join(f"{v:+.2f}" for v in x[s-12:s+28]))
        r, c = aligned_copy(other, s)
        if r < 0.95:
            print(f"      {oname}: no aligned copy (best corr {r:.2f})"); continue
        d = other[s-8:s+40] - other[c-8:c+40]
        sd0 = np.std(d[:6]) + 1e-4
        idx = np.where(np.abs(d) > max(0.02, 4*sd0))[0]
        if len(idx) == 0:
            print(f"      {oname}: no deviation from its copy (corr {r:.2f})"); continue
        on = idx[0]; blk = d[on:on+16]
        print(f"      {oname}: deviates from its copy (corr {r:.2f}) at {on-8:+d} samples: mean {blk.mean():+.3f} sd {np.std(blk):.3f}; "
              f"value there {other[s-8+on:s+on+8].mean():+.3f} vs copy {other[c-8+on:c+on+8].mean():+.3f}")
