import json, numpy as np
import oxide as o, solve3
from model2 import Model
from sigs import pink, drums, bandlevels, imd
o.setp(input_level=0.0, output_level=0.0, path_select="Repro", ips="15 IPS", emphasis_eq="NAB", noise_reduct=True, power=True, master_bypass=False)
real = o.run; SR = o.SR
cfg = json.load(open("fo.json"))["ls+hs1+AP"]
M = Model(cfg); r = M.solve(real); fine, G, ev = solve3.coef_to_fn(M.sol)
grid = np.linspace(0, 2.0, 17); vals = np.array([np.interp(g, solve3.NODES, G) for g in grid])
curve = np.r_[-vals[:0:-1], vals]                       # u = -2 .. 2, 33 points, odd
M.fn = lambda u: np.interp(np.clip(u, -2, 2), np.linspace(-2, 2, 33), curve)
final = dict(cfg, curve_u=np.linspace(-2, 2, 33).tolist(), curve=curve.tolist())
json.dump(final, open("final.json", "w"), indent=1)
print("solve residual", round(r, 3), "| curve (u>=0):", np.round(vals, 4).tolist())
src = {"pink": pink(SR*6, 3)/3.0, "drums": drums(SR*6)}
for (k, L) in [(k, L) for k in src for L in (-24, -12, 0, 6)]:
    x = src[k]*10**(L/20); y = real(x); m = M(x); s = slice(SR//2, None)
    d = np.array(bandlevels(m[s])) - np.array(bandlevels(y[s]))
    print(f"  {k:6s} {L:+3d}: peak {20*np.log10(np.max(abs(m[s]))/np.max(abs(y[s]))):+5.2f} dB | rms {20*np.log10(np.std(m[s])/np.std(y[s])):+5.2f} | bands max |d| {np.max(abs(d)):.2f} dB")
fs = (40, 100, 1000, 4000, 10000); print("  sines gain/H3 diff:", "".join(f"{f:>13}" for f in fs))
for L in (-12, 0, 6):
    row = []
    for f in fs:
        o.run = real; g, h, *_ = o.tone(f, L); o.run = lambda x: M(np.asarray(x, np.float64)); gm, hm, *_ = o.tone(f, L); o.run = real
        row.append(f"{gm-g:+5.2f}/{(hm.get(3, np.nan)-h.get(3, np.nan)):+5.1f}")
    print(f"   {L:+4d}                  " + "  ".join(row))
for L in (-12, 0):
    g, s = imd(real, L); gm, sm = imd(lambda x: M(np.asarray(x, np.float64)), L)
    print(f"  two-tone LF {L:3d}: HF gain {g:6.2f} vs {gm:6.2f} | HF±2LF {s[1]:6.1f} vs {sm[1]:6.1f} dBc")
