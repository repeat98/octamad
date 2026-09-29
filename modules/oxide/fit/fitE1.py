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
def run(spec, p0, seeds=12, wph=1.0):
    lo, hi = bounds(spec); lo = np.r_[lo[:-2], -np.pi, -np.pi]; hi = np.r_[hi[:-2], np.pi, np.pi]
    def res(p):
        S = sections(spec, p[:-2]); c3, c5 = p[-2:]
        mag = 20*np.log10(abs(resp(S, fS))) - E1d
        ph = lambda x: np.angle(resp(S, x))
        r3 = np.angle(np.exp(1j*(D3 - (3*ph(f) - ph(3*f)) - c3)))
        r5 = np.angle(np.exp(1j*(D5 - (5*ph(f[m5]) - ph(5*f[m5])) - c5)))
        return np.r_[mag, np.degrees(r3)/10*wph, np.degrees(r5)/10*wph]
    best = None
    for s in range(seeds):
        rng = np.random.default_rng(s)
        q = np.array(list(p0) + [0.0, 0.0], float)
        if s: q[:-2] *= np.exp(rng.normal(0, .25, len(p0))); q[-2:] = rng.uniform(-3, 3, 2)
        q = np.clip(q, lo+1e-6, hi-1e-6)
        r = optimize.least_squares(res, q, bounds=(lo, hi), x_scale="jac", max_nfev=8000)
        if best is None or r.cost < best.cost: best = r
    p = best.x; r = res(p); nm = len(fS)
    return p, np.sqrt(np.mean(r[:nm]**2)), np.sqrt(np.mean((r[nm:nm+len(f)]*10)**2)), np.max(abs(r[nm:]*10)), np.sqrt(np.mean((r[nm+len(f):]*10)**2))
cands = {
 "hpf+ls+peak4+apHF":  (["hpf", "ls"] + ["peak"]*4 + ["ap1"], [1.9, .4, 9.5, .55, 19, 15.5, .38, 5.8, 5400, .5, -1.6, 20000, .11, 4.8, 400, .24, .18, 5750]),
 "hpf+ls+peak4":       (["hpf", "ls"] + ["peak"]*4,          [1.9, .4, 9.5, .55, 19, 15.5, .38, 5.8, 5400, .5, -1.6, 20000, .11, 4.8, 400, .24, .18]),
 "ls+peak4+apHF":      (["ls"] + ["peak"]*4 + ["ap1"],       [9.5, .55, 17.6, 15.5, .38, 5.8, 5400, .5, -1.6, 20000, .11, 4.8, 400, .24, .18, 5750]),
 "hpf+ls+peak4+apHF+apLF": (["hpf", "ls"] + ["peak"]*4 + ["ap1", "ap1"], [1.9, .4, 9.5, .55, 19, 15.5, .38, 5.8, 5400, .5, -1.6, 20000, .11, 4.8, 400, .24, .18, 5750, 50]),
}
out = {}
for name, (spec, p0) in cands.items():
    p, mr, r3, mx, r5 = run(spec, p0)
    print(f"{name:24s} E1 mag rms {mr:.3f} dB | H3 phase rms {r3:5.2f} | H5 rms {r5:5.2f} | worst {mx:6.2f} deg")
    print("    ", np.round(p[:-2], 3).tolist())
    out[name] = dict(spec=spec, p=p[:-2].tolist())
json.dump(out, open("fitE1.json", "w"), indent=1)
