import json, numpy as np
from scipy import optimize
from lin import *
M = np.load("Hmeas.npy"); f = M[:, 0]; H = M[:, 1] + 1j*M[:, 2]
magdb = 20*np.log10(abs(H))
def magfit(spec, p0, seeds=12):
    lo, hi = bounds(spec); lo, hi = lo[:-2], hi[:-2]
    best = None
    for s in range(seeds):
        rng = np.random.default_rng(s)
        q = np.clip(np.array(p0, float) * (1 if s == 0 else np.exp(rng.normal(0, .3, len(p0)))), np.array(lo)+1e-6, np.array(hi)-1e-6)
        r = optimize.least_squares(lambda p: 20*np.log10(abs(resp(sections(spec, p), f))) - magdb, q, bounds=(lo, hi), x_scale="jac", max_nfev=5000)
        if best is None or r.cost < best.cost: best = r
    return best.x
# stage 1: min-phase magnitude sections
spec1 = ["hpf", "hpf"] + ["peak"]*5
p1 = magfit(spec1, [2.8,.54, 2.8,1.31, 30,.8,4.5, 90,1,-1, 400,1,.3, 7000,.8,1.2, 15000,1,1])
H1 = resp(sections(spec1, p1), f)
dm = 20*np.log10(abs(H1)) - magdb
print("stage 1 magnitude: rms", round(np.sqrt(np.mean(dm**2)), 3), "max", round(np.max(abs(dm)), 3), "dB")
print("  sections:", [(k, np.round(p1[i:i+KINDS[k][1]], 3).tolist()) for k, i in zip(spec1, np.cumsum([0]+[KINDS[k][1] for k in spec1])[:-1])])
# stage 2: residual phase -> allpass + delay
rp = np.unwrap(np.angle(H / H1))
for ff in (1, 3, 10, 20, 30, 45, 70, 100, 200, 500, 1000, 4000, 12000, 18000):
    k = np.argmin(abs(f-ff)); print(f"   residual phase @{ff:6d} Hz {np.degrees(rp[k]):8.1f} deg")
json.dump(dict(spec1=spec1, p1=p1.tolist()), open("stage1.json", "w"))
np.save("resphase.npy", np.c_[f, rp])
