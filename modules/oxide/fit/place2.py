import json, itertools, numpy as np
from lin import *
e = json.load(open("e1e2.json")); S1 = sections(e["E1"]["spec"], e["E1"]["p"])
AL = lambda f: -resp([ap1(52.617)], f); AH = lambda f: resp([ap1(5751.248)], f)
b6 = json.load(open("batch6.json"))["harm"]
d = np.load("ir1.npz"); i0 = int(d["i0"]); h = d["0.01"]; n = np.arange(len(h)) - i0
HT = lambda f: np.array([np.sum(h*np.exp(-2j*np.pi*ff*n/SR)) for ff in np.atleast_1d(f)])
for L in ("-6", "0", "6"):
    rows = b6[L]; print(L, "H3 dBc at 30 Hz / 1 kHz:", [round(20*np.log10(abs(complex(*r[2]))/abs(complex(*r[1]))), 1) for r in rows if r[0] in (30, 1000)])
rows = b6["0"]; f = np.array([r[0] for r in rows], float)
H1 = np.array([complex(*r[1]) for r in rows]); H3 = np.array([complex(*r[2]) for r in rows])
H5 = np.array([complex(*r[3]) if r[3] else np.nan for r in rows])
D3 = np.angle(H3 / HT(3*f)); D5 = np.angle(H5 / HT(5*f))      # = k*phi1(f) - phi1(k f) + c_k
ok5 = ~np.isnan(H5) & (5*f < 18000)
def score(phi1):
    out = []
    for D, k, m in ((D3, 3, np.ones_like(f, bool)), (D5, 5, ok5)):
        r = D[m] - (k*phi1(f[m]) - phi1(k*f[m])); c = np.angle(np.mean(np.exp(1j*r)))
        err = np.degrees(np.angle(np.exp(1j*(r - c)))); out.append((np.sqrt(np.mean(err**2)), np.max(abs(err)), err))
    return out
print("\npre-saturator filter candidates, scored on H3 and H5 phases (measured total removed):")
for lf, hf in itertools.product((False, True), repeat=2):
    phi1 = lambda x, lf=lf, hf=hf: np.angle(resp(S1, x) * (AL(x) if lf else 1) * (AH(x) if hf else 1))
    (r3, m3, e3), (r5, m5, e5) = score(phi1)
    print(f"  E1 min-phase {'+ LF allpass' if lf else '             '} {'+ HF allpass' if hf else '             '}: H3 rms {r3:6.2f} max {m3:6.2f} | H5 rms {r5:6.2f} max {m5:6.2f} deg")
    if lf == False and hf == False: base_err = e3
print("\nresidual per frequency (E1 min-phase only), H3:")
print("  ", [(int(ff), round(x, 1)) for ff, x in zip(f, base_err)])
