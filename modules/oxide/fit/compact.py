import json, numpy as np
from scipy import optimize
from lin import *
rows = np.array(json.load(open("split6.json"))); fS, E1d = rows[:, 0], rows[:, 2]
b6 = json.load(open("batch6.json"))["harm"]["0"]
d = np.load("ir1.npz"); i0 = int(d["i0"]); h = d["0.01"]; n = np.arange(len(h)) - i0
HT = lambda f: np.array([np.sum(h*np.exp(-2j*np.pi*ff*n/SR)) for ff in np.atleast_1d(f)])
f = np.array([r[0] for r in b6], float)
H3 = np.array([complex(*r[2]) for r in b6]); H5 = np.array([complex(*r[3]) if r[3] else np.nan for r in b6])
D3 = np.angle(H3/HT(3*f)); m5 = ~np.isnan(H5) & (5*f < 18000); D5 = np.angle(H5[m5]/HT(5*f[m5]))
M = np.load("Hmeas.npy"); fm = M[:, 0]; Hm = M[:, 1] + 1j*M[:, 2]
def fit(res, lo, hi, p0, seeds=10):
    best = None
    for s in range(seeds):
        rng = np.random.default_rng(s); q = np.array(p0, float) * (1 if s == 0 else np.exp(rng.normal(0, .3, len(p0))))
        r = optimize.least_squares(res, np.clip(q, lo+1e-6, hi-1e-6), bounds=(lo, hi), x_scale="jac", max_nfev=6000)
        if best is None or r.cost < best.cost: best = r
    return best.x
def fitE1(spec, p0, fmax_mag=3000, fmax_ph=1000):
    lo, hi = bounds(spec); lo = np.r_[lo[:-2], -4, -4]; hi = np.r_[hi[:-2], 4, 4]
    mm = fS <= fmax_mag; m3 = f <= fmax_ph; m5b = m5 & (f <= fmax_ph)
    def res(p):
        S = sections(spec, p[:-2]); ph = lambda x: np.angle(resp(S, x))
        r3 = np.angle(np.exp(1j*(D3[m3] - (3*ph(f[m3]) - ph(3*f[m3])) - p[-2])))
        r5 = np.angle(np.exp(1j*(D5[m5b[m5]] - (5*ph(f[m5b]) - ph(5*f[m5b])) - p[-1])))
        return np.r_[20*np.log10(abs(resp(S, fS[mm]))) - E1d[mm], np.degrees(r3)/10, np.degrees(r5)/10]
    p = fit(res, lo, hi, list(p0) + [0, 0]); r = res(p); k = mm.sum()
    return p[:-2], np.sqrt(np.mean(r[:k]**2)), np.sqrt(np.mean((r[k:]*10)**2))
def fitE2(S1, spec, p0, sign, fmin=10, fmax=17000):
    T = Hm / resp(S1, fm); m = (fm >= fmin) & (fm <= fmax)
    lo, hi = bounds(spec); lo, hi = np.array(lo[:-2] + [-3.0]), np.array(hi[:-2] + [3.0])
    for D in (0, 1, 2, 3):                      # integer delay only: free on the DSP
        def res(p):
            hm = sign * resp(sections(spec, p[:-1]), fm[m], D) * 10**(p[-1]/20)
            w = np.where(fm[m] < 20, 0.3, 1.0)
            return np.r_[20*np.log10(abs(hm/T[m]))*w, np.degrees(np.angle(hm/T[m]))/10*w]
        p = fit(res, lo, hi, list(p0) + [0.0], seeds=6); r = res(p); k = m.sum()
        mag = np.sqrt(np.mean(r[:k]**2)); ph = np.sqrt(np.mean((r[k:]*10)**2))
        yield D, p, mag, ph, np.max(abs(r[:k])), np.max(abs(r[k:]*10))
E1c = {
 "A hpf1+sh1":        (["hpf1", "sh1"], [4, 10, 18]),
 "B hpf+sh1":         (["hpf", "sh1"], [4, .9, 10, 18]),
 "C hpf1+ls":         (["hpf1", "ls"], [4, 18, .45, 18]),
 "D hpf1+sh1+ap1HF":  (["hpf1", "sh1", "ap1"], [4, 10, 18, 5600]),
}
out = {}
for name, (spec, p0) in E1c.items():
    p, mr, pr = fitE1(spec, p0, fmax_ph=(6000 if "ap1" in spec else 1000))
    print(f"E1 {name:18s} mag rms (5 Hz-3 kHz) {mr:.3f} dB | H3/H5 phase rms {pr:5.2f} deg | {np.round(p, 2).tolist()}")
    out[name] = dict(spec=spec, p=p.tolist())
json.dump(out, open("compactE1.json", "w"), indent=1)
