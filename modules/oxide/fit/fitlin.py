import json, numpy as np
from lin import *
d = np.load("ir1.npz"); i0 = int(d["i0"]); h = d["0.01"]
f = np.geomspace(1, 18000, 500); n = np.arange(len(h)) - i0
H = np.array([np.sum(h*np.exp(-2j*np.pi*ff*n/SR)) for ff in f])
np.save("Hmeas.npy", np.c_[f, H.real, H.imag])
variants = {
 "minphase: hpf2+peak5":       (["hpf","hpf"]+["peak"]*5,           [4,.7,4,.7, 30,1,5, 100,1,-1, 400,1,.3, 8000,1,1.5, 15000,1,1]),
 "hpf3+peak5":                 (["hpf","hpf","hpf"]+["peak"]*5,     [4,.7,4,.7,25,1.2, 30,1,3, 100,1,-1, 400,1,.3, 8000,1,1.5, 15000,1,1]),
 "hpf2+peak5+ap1":             (["hpf","hpf"]+["peak"]*5+["ap1"],   [4,.7,4,.7, 30,1,5, 100,1,-1, 400,1,.3, 8000,1,1.5, 15000,1,1, 45]),
 "hpf3+peak5+ap1":             (["hpf","hpf","hpf"]+["peak"]*5+["ap1"], [4,.7,4,.7,25,1.2, 30,1,3, 100,1,-1, 400,1,.3, 8000,1,1.5, 15000,1,1, 45]),
 "hpf2+peak5+ap2":             (["hpf","hpf"]+["peak"]*5+["ap2"],   [4,.7,4,.7, 30,1,5, 100,1,-1, 400,1,.3, 8000,1,1.5, 15000,1,1, 60,.5]),
}
res = {}
for name, (spec, p0) in variants.items():
    best = None
    for seed in range(6):
        rng = np.random.default_rng(seed)
        q = np.array(p0 + [1.0, 0.0], float) * (1 if seed == 0 else np.exp(rng.normal(0, .25, len(p0)+2)))
        q[-2:] = [1.0, 0.0] if seed == 0 else q[-2:]
        p, r = fit(spec, f, H, q)
        if best is None or r.cost < best[1].cost: best = (p, r)
    p, r = best
    hm = resp(sections(spec, p[:-2]), f, p[-2]) * 10**(p[-1]/20)
    dm = 20*np.log10(abs(hm/H)); dp = np.degrees(np.angle(hm/H))
    lf = f < 200
    print(f"{name:26s} mag rms {np.sqrt(np.mean(dm**2)):.3f} max {np.max(abs(dm)):.2f} dB | phase rms {np.sqrt(np.mean(dp**2)):5.2f} max {np.max(abs(dp)):6.2f} deg | <200 Hz phase max {np.max(abs(dp[lf])):6.2f} | delay {p[-2]:.2f}")
    res[name] = dict(spec=spec, p=p.tolist())
json.dump(res, open("fitlin.json", "w"), indent=1)
