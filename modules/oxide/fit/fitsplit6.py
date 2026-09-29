import json, numpy as np
from scipy import optimize
from lin import *
rows = np.array(json.load(open("split6.json"))); fS, E1d = rows[:, 0], rows[:, 2]
st = json.load(open("stage1.json")); spec1, p1 = st["spec1"], np.array(st["p1"])
def magfit(spec, p0, f, tgt, seeds=16):
    lo, hi = bounds(spec); lo, hi = np.array(lo[:-2]), np.array(hi[:-2]); best = None
    for s in range(seeds):
        rng = np.random.default_rng(s)
        q = np.clip(np.array(p0, float)*(1 if s == 0 else np.exp(rng.normal(0, .3, len(p0)))), lo+1e-6, hi-1e-6)
        r = optimize.least_squares(lambda p: 20*np.log10(abs(resp(sections(spec, p), f))) - tgt, q, bounds=(lo, hi), x_scale="jac", max_nfev=6000)
        if best is None or r.cost < best.cost: best = r
    e = best.fun; return best.x, np.sqrt(np.mean(e**2)), np.max(abs(e))
out = {}
for name, spec, p0 in (("sh1+peak4", ["sh1"] + ["peak"]*4, [15, 18, 150, .7, .3, 4000, .7, -1.2, 15000, .7, 3, 800, 1, .1]),
                       ("ls+peak4",  ["ls"] + ["peak"]*4,  [12, .6, 18, 150, .7, .3, 4000, .7, -1.2, 15000, .7, 3, 800, 1, .1]),
                       ("sh1+ls+peak4", ["sh1", "ls"] + ["peak"]*4, [15, 18, 40, .7, 1, 150, .7, .3, 4000, .7, -1.2, 15000, .7, 3, 800, 1, .1])):
    p, rms, mx = magfit(spec, p0, fS, E1d)
    print(f"E1 {name:14s} rms {rms:.3f} max {mx:.3f} dB  {np.round(p, 2).tolist()}")
    out[name] = dict(spec=spec, p=p.tolist(), rms=rms)
best = min(out, key=lambda k: out[k]["rms"]); e1 = out[best]; print("E1 ->", best)
f2 = np.geomspace(1, 20000, 400)
tot = 20*np.log10(abs(resp(sections(spec1, p1), f2)))
tgt2 = tot - 20*np.log10(abs(resp(sections(e1["spec"], e1["p"]), f2)))
out2 = {}
for name, spec, p0 in (("hpf2+sh1+peak4", ["hpf", "hpf", "sh1"] + ["peak"]*4, [p1[0], p1[1], p1[2], p1[3], 15, -18, 150, .7, -.3, 4000, .7, 1.2, 15000, .7, -3, 800, 1, -.1]),
                       ("hpf2+ls+peak4",  ["hpf", "hpf", "ls"] + ["peak"]*4,  [p1[0], p1[1], p1[2], p1[3], 12, .6, -18, 150, .7, -.3, 4000, .7, 1.2, 15000, .7, -3, 800, 1, -.1])):
    p, rms, mx = magfit(spec, p0, f2, tgt2)
    print(f"E2 {name:16s} rms {rms:.3f} max {mx:.3f} dB  {np.round(p, 2).tolist()}")
    out2[name] = dict(spec=spec, p=p.tolist(), rms=rms)
best2 = min(out2, key=lambda k: out2[k]["rms"]); print("E2 ->", best2)
json.dump(dict(E1=e1, E2=out2[best2]), open("e1e2.json", "w"), indent=1)
