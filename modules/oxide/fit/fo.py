import json, numpy as np
from scipy import optimize
from lin import *
import compact as C
fm, Hm = C.fm, C.Hm
def fitE2(S1, spec, p0, sign, fmin=10, fmax=17000, seeds=8):
    T = Hm / resp(S1, fm); m = (fm >= fmin) & (fm <= fmax); fr = fm[m]
    wm = np.where(fr < 20, 0.3, 1.0)
    wp = np.clip(1 - np.log10(fr/1500)/np.log10(3), 0.05, 1.0) * wm
    lo, hi = bounds(spec); lo, hi = np.array(lo[:-2] + [-3.0]), np.array(hi[:-2] + [3.0])
    def res(p):
        hm = sign * resp(sections(spec, p[:-1]), fr, 2) * 10**(p[-1]/20)
        return np.r_[20*np.log10(abs(hm/T[m]))*wm, np.degrees(np.angle(hm/T[m]))/10*wp]
    p = C.fit(res, lo, hi, list(p0) + [0.0], seeds=seeds)
    hm = sign * resp(sections(spec, p[:-1]), fr, 2) * 10**(p[-1]/20)
    dm = 20*np.log10(abs(hm/T[m])); dp = np.degrees(np.angle(hm/T[m])); au = fr >= 20; lfp = (fr >= 20) & (fr <= 1500)
    return p, np.sqrt(np.mean(dm[au]**2)), np.max(abs(dm[au])), np.sqrt(np.mean(dp[lfp]**2)), np.max(abs(dp[lfp]))
e1 = json.load(open("compactE1.json"))["A hpf1+sh1"]; S1 = sections(e1["spec"], e1["p"])
out = {}
for n2, spec, p0 in (("sh1+hpf1+hs1+AP", ["sh1", "hpf1", "hs1", "ap1"], [30, -21, 3, 7000, 1.6, 52]),
                     ("sh1+sh1+hs1+AP",  ["sh1", "sh1", "hs1", "ap1"],  [30, -12, 15, -9, 7000, 1.6, 52]),
                     ("hpf1+hpf1+hs1+AP", ["hpf1", "hpf1", "hs1", "ap1"], [15, 15, 7000, 1.6, 52]),
                     ("sh1+hpf1+hs+AP",  ["sh1", "hpf1", "hs", "ap1"],  [30, -21, 3, 7400, .75, 1.6, 52])):
    p, mr, mx, pr, px = fitE2(S1, spec, p0, -1)
    print(f"{n2:18s}: 20 Hz-17 kHz mag rms {mr:.3f} max {mx:.2f} dB | 20-1500 Hz phase rms {pr:5.2f} max {px:6.2f} | {np.round(p, 3).tolist()}")
    out[n2] = dict(spec1=e1["spec"], p1=e1["p"], spec2=spec, p2=p[:-1].tolist(), gain=float(p[-1]), sign=-1, D=2)
json.dump(out, open("fo.json", "w"), indent=1)
