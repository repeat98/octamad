import wave, numpy as np, sys
path = sys.argv[1]
w = wave.open(path); n, ch, sr = w.getnframes(), w.getnchannels(), w.getframerate()
a = np.frombuffer(w.readframes(n), dtype=np.int32).reshape(-1, ch).astype(np.float64) / 2**31
R, L = a[:,2], a[:,3]
for name, x in (("L", L), ("R", R)):
    rms = np.sqrt(np.mean(x**2)); print(f"{name}: peak {np.max(np.abs(x)):.3f} rms {20*np.log10(rms+1e-12):.1f} dBFS")
env = np.abs(L); env = np.convolve(env, np.ones(441)/441, mode="same")[::10]
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
for name, x in (("L", L), ("R", R)):
    ev = oneoffs(x)
    print(f"{name}: one-off events: {len(ev)}  times:", " ".join(f"{s/sr:.3f}" for s, m, e in ev), " spans:", [int(e-s+1) for s, m, e in ev])
    for s, m, e in ev[:6]:
        lo = s - 12; hi = s + 28
        print(f"  t={s/sr:.3f}s {name}:", " ".join(f"{v:+.2f}" for v in x[lo:hi]))
