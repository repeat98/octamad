"""Parametric digital sections (RBJ cookbook), complex response, and a complex fit."""
import numpy as np
from scipy import optimize
SR = 44100

def hpf(f0, Q):
    w = 2*np.pi*f0/SR; al = np.sin(w)/(2*Q); c = np.cos(w)
    b = np.array([(1+c)/2, -(1+c), (1+c)/2]); a = np.array([1+al, -2*c, 1-al]); return b/a[0], a/a[0]
def lpf(f0, Q):
    w = 2*np.pi*f0/SR; al = np.sin(w)/(2*Q); c = np.cos(w)
    b = np.array([(1-c)/2, 1-c, (1-c)/2]); a = np.array([1+al, -2*c, 1-al]); return b/a[0], a/a[0]
def peak(f0, Q, g):
    A = 10**(g/40); w = 2*np.pi*f0/SR; al = np.sin(w)/(2*Q); c = np.cos(w)
    b = np.array([1+al*A, -2*c, 1-al*A]); a = np.array([1+al/A, -2*c, 1-al/A]); return b/a[0], a/a[0]
def ap1(fc):
    t = np.tan(np.pi*fc/SR); k = (t-1)/(t+1)          # first-order allpass, -90 deg at fc
    return np.array([k, 1.0, 0.0]), np.array([1.0, k, 0.0])
def ap2(f0, Q):
    w = 2*np.pi*f0/SR; al = np.sin(w)/(2*Q); c = np.cos(w)
    b = np.array([1-al, -2*c, 1+al]); a = np.array([1+al, -2*c, 1-al]); return b/a[0], a/a[0]

KINDS = {"hpf": (hpf, 2), "lpf": (lpf, 2), "peak": (peak, 3), "ap1": (ap1, 1), "ap2": (ap2, 2)}

def sections(spec, p):
    out = []; i = 0
    for kind in spec:
        fn, n = KINDS[kind]; out.append(fn(*p[i:i+n])); i += n
    return out

def resp(secs, f, delay=0.0):
    z1 = np.exp(-2j*np.pi*f/SR)
    h = np.exp(-2j*np.pi*f/SR*delay).astype(complex)
    for b, a in secs:
        h *= (b[0] + b[1]*z1 + b[2]*z1**2) / (a[0] + a[1]*z1 + a[2]*z1**2)
    return h

def sos(secs):
    return np.array([np.r_[b, a] for b, a in secs])

def bounds(spec):
    lo, hi = [], []
    for k in spec:
        if k in ("hpf", "lpf"): lo += [0.5, 0.3]; hi += [21000, 8]
        elif k == "peak": lo += [2, 0.1, -30]; hi += [21000, 12, 30]
        elif k == "ap1": lo += [1]; hi += [20000]
        elif k == "ap2": lo += [1, 0.1]; hi += [20000, 8]
    return lo + [-2.0, -3.0], hi + [6.0, 3.0]            # + delay (samples), gain (dB)

def fit(spec, f, H, p0, wphase=1.0, fmax=None):
    m = f <= (fmax or f.max())
    lo, hi = bounds(spec)
    def res(p):
        hm = resp(sections(spec, p[:-2]), f[m], p[-2]) * 10**(p[-1]/20)
        r = np.log(hm / H[m])                           # complex log: real = ln mag (Np), imag = phase (rad)
        return np.r_[r.real*8.686, np.angle(hm/H[m])*np.degrees(1)/10*wphase]   # dB and deg/10
    p0 = np.clip(p0, np.array(lo)+1e-9, np.array(hi)-1e-9)
    r = optimize.least_squares(res, p0, bounds=(lo, hi), x_scale="jac", max_nfev=20000)
    return r.x, r


def lshelf(f0, Q, g):
    A = 10**(g/40); w = 2*np.pi*f0/SR; al = np.sin(w)/(2*Q); c = np.cos(w); s = 2*np.sqrt(A)*al
    b = np.array([A*((A+1)-(A-1)*c+s), 2*A*((A-1)-(A+1)*c), A*((A+1)-(A-1)*c-s)])
    a = np.array([(A+1)+(A-1)*c+s, -2*((A-1)+(A+1)*c), (A+1)+(A-1)*c-s]); return b/a[0], a/a[0]
def hshelf(f0, Q, g):
    A = 10**(g/40); w = 2*np.pi*f0/SR; al = np.sin(w)/(2*Q); c = np.cos(w); s = 2*np.sqrt(A)*al
    b = np.array([A*((A+1)+(A-1)*c+s), -2*A*((A-1)+(A+1)*c), A*((A+1)+(A-1)*c-s)])
    a = np.array([(A+1)-(A-1)*c+s, 2*((A-1)-(A+1)*c), (A+1)-(A-1)*c-s]); return b/a[0], a/a[0]
def shelf1(f0, g):
    """first-order low shelf: gain g dB at DC, 0 dB at HF, transition around f0 (bilinear, prewarped)"""
    G = 10**(g/20); wc = np.tan(np.pi*f0/SR)          # H(s) = (s + G*wc)/(s + wc)
    b = np.array([1 + G*wc, G*wc - 1, 0.0]); a = np.array([1 + wc, wc - 1, 0.0]); return b/a[0], a/a[0]
KINDS.update({"ls": (lshelf, 3), "hs": (hshelf, 3), "sh1": (shelf1, 2)})
_b = bounds
def bounds(spec):
    lo, hi = [], []
    for k in spec:
        if k in ("ls", "hs"): lo += [1, 0.2, -30]; hi += [21000, 4, 30]
        elif k == "sh1": lo += [0.5, -40]; hi += [20000, 40]
        else:
            l, h = _b([k]); lo += l[:-2]; hi += h[:-2]
    return lo + [-2.0, -3.0], hi + [6.0, 3.0]


def hpf1(fc):
    w = np.tan(np.pi*fc/SR)
    return np.array([1.0, -1.0, 0.0])/(1+w), np.array([1.0, (w-1)/(1+w), 0.0])
KINDS["hpf1"] = (hpf1, 1)
_b2 = bounds
def bounds(spec):
    lo, hi = [], []
    for k in spec:
        if k == "hpf1": lo += [0.3]; hi += [2000]
        else:
            l, h = _b2([k]); lo += l[:-2]; hi += h[:-2]
    return lo + [-2.0, -3.0], hi + [6.0, 3.0]


def hs1(f0, g):
    """first-order high shelf: 0 dB at DC, g dB at HF. H(s) = (G s + wc)/(s + wc)"""
    G = 10**(g/20); wc = np.tan(np.pi*f0/SR)
    b = np.array([G + wc, wc - G, 0.0]); a = np.array([1 + wc, wc - 1, 0.0]); return b/a[0], a/a[0]
KINDS["hs1"] = (hs1, 2)
_b3 = bounds
def bounds(spec):
    lo, hi = [], []
    for k in spec:
        if k == "hs1": lo += [200, -12]; hi += [20000, 12]
        else:
            l, h = _b3([k]); lo += l[:-2]; hi += h[:-2]
    return lo + [-2.0, -3.0], hi + [6.0, 3.0]
