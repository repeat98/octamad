"""Compact Oxide model: E1 (sos) -> table f(u) -> E2 (sos, sign, gain), plugin output = model delayed by D."""
import json, sys, numpy as np
from scipy import signal
from lin import *
import solve3                                    # NODES, design(), coef_to_fn()
def sos_of(spec, p, sign=1, gain_db=0.0):
    s = sos(sections(spec, p)).copy(); s[0, :3] *= sign * 10**(gain_db/20); return s
class Model:
    def __init__(self, cfg):
        self.s1 = sos_of(cfg["spec1"], cfg["p1"]); self.s2 = sos_of(cfg["spec2"], cfg["p2"], cfg["sign"], cfg["gain"]); self.D = cfg["D"]
        self.fn = None
    def E1(self, x): return signal.sosfilt(self.s1, x, axis=0)
    def E2(self, v): return signal.sosfilt(self.s2, v, axis=0)
    def solve(self, run, lam=1e-3):
        cols, ys = [], []
        for f in (60, 150, 300, 600, 1000):
            for L in np.arange(-42, 24.1, 1.5):
                t = np.arange(int(0.5*SR))/SR; x = 10**(L/20)*np.sin(2*np.pi*f*t)
                y = run(x); y = np.r_[y[self.D:], np.zeros(self.D)]; sk = int(0.2*SR)
                B = self.E2(solve3.design(self.E1(x)))[sk:]
                w = 1/np.sqrt(np.mean(y[sk:]**2)); cols.append(B*w); ys.append(y[sk:]*w)
        A = np.vstack(cols); Y = np.concatenate(ys); nG = len(solve3.NODES) - 1
        Dm = np.zeros((nG-2, A.shape[1]))
        for i in range(nG-2): Dm[i, i:i+3] = [1, -2, 1]
        self.sol, *_ = np.linalg.lstsq(np.vstack([A, lam*Dm*np.sqrt(len(Y)/nG)]), np.r_[Y, np.zeros(len(Dm))], rcond=None)
        self.fn = solve3.coef_to_fn(self.sol)[0]
        return np.sqrt(np.mean((A@self.sol - Y)**2))/np.sqrt(np.mean(Y**2))
    def __call__(self, x):
        y = self.E2(self.fn(self.E1(np.asarray(x, np.float64))))
        return np.r_[np.zeros(self.D), y[:len(y)-self.D]]            # same timing as the plugin
