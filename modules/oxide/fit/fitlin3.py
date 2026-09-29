import json, numpy as np
from scipy import optimize
from lin import *
M = np.load("Hmeas.npy"); f = M[:, 0]; H = M[:, 1] + 1j*M[:, 2]
st = json.load(open("stage1.json")); spec1, p1 = st["spec1"], np.array(st["p1"])
H1 = resp(sections(spec1, p1), f)
def phase_fit(specA, p0, sign, fmax=18000):
    m = f <= fmax
    lo, hi = bounds(specA); lo, hi = lo[:-1], hi[:-1]        # keep delay, drop gain
    def res(p):
        ha = sign * resp(sections(specA, p[:-1]), f[m], p[-1])
        return np.degrees(np.angle(H[m] / (H1[m] * ha)))
    r = optimize.least_squares(res, np.r_[p0, 1.0], bounds=(lo, hi), x_scale="jac")
    return r.x, np.sqrt(np.mean(r.fun**2)), np.max(abs(r.fun))
for name, specA, p0, sign in (("-ap1", ["ap1"], [50], -1), ("+ap1", ["ap1"], [50], +1),
                              ("-ap1 ap2", ["ap1", "ap2"], [50, 8000, .5], -1),
                              ("-ap1 ap1", ["ap1", "ap1"], [50, 12000], -1)):
    p, rms, mx = phase_fit(specA, p0, sign)
    print(f"{name:10s} phase rms {rms:6.2f} max {mx:6.2f} deg   params {np.round(p, 3).tolist()}")
    if name == "-ap1": print(f"           -> fa = {p[0]:.2f} Hz  (NAB 3180 us = {1/(2*np.pi*3180e-6):.2f} Hz)")
