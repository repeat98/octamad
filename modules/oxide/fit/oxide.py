"""Oxide Tape Recorder (UADx VST3) characterisation via pedalboard.

Each point: a steady sine, plugin reset, tail analysed by least squares on
the fundamental and harmonics 2..9; the remainder is reported separately so
a non-harmonic residual is not hidden (AGENTS.md: a THD sum over 2f..9f
cannot see intermodulation/aliasing).
"""
import contextlib, io, json, sys, time
import numpy as np
from pedalboard import load_plugin

SR = 44100
PATH = "/Library/Audio/Plug-Ins/VST3/uaudio_oxide_tape.vst3"
_p = None


def plugin():
    global _p
    if _p is None:
        with contextlib.redirect_stdout(io.StringIO()):
            _p = load_plugin(PATH)
    return _p


def setp(**kw):
    p = plugin()
    for k, v in kw.items():
        setattr(p, k, v)


def run(x):
    p = plugin()
    y = p.process(np.asarray(x, np.float32)[None, :].repeat(2, 0), SR, reset=True)
    return y[0].astype(np.float64)


def db(v):
    return 20 * np.log10(max(abs(v), 1e-12))


def tone(f, level_db, dur=None, settle=None):
    """(fund_gain_db, {n: dBc}, resid_dBc_vs_fund, dc) at f Hz, level_db dBFS peak."""
    dur = dur or max(2.0, 12.0 / f)          # >=12 cycles even at 20 Hz
    settle = settle or dur * 0.5
    n = int(dur * SR)
    t = np.arange(n) / SR
    a = 10 ** (level_db / 20)
    y = run(a * np.sin(2 * np.pi * f * t))
    s0 = int(settle * SR)
    ty = y[s0:]
    tt = t[s0:]
    H = [k for k in range(1, 10) if k * f < SR / 2 * 0.98]
    cols = [np.ones_like(tt)]
    for k in H:
        cols += [np.sin(2 * np.pi * k * f * tt), np.cos(2 * np.pi * k * f * tt)]
    A = np.stack(cols, 1)
    c, *_ = np.linalg.lstsq(A, ty, rcond=None)
    amp = {k: np.hypot(c[1 + 2 * i], c[2 + 2 * i]) for i, k in enumerate(H)}
    fit = A @ c
    rem = ty - fit
    fund = amp[1]
    harm = {k: db(amp[k] / fund) for k in H if k > 1}
    resid = db(np.sqrt(np.mean(rem ** 2)) * np.sqrt(2) / fund)
    return db(fund / a), harm, resid, c[0]


def sweep_level(f=1000, levels=range(-60, 7, 3)):
    out = []
    for L in levels:
        g, h, r, dc = tone(f, L)
        out.append(dict(level=L, gain=g, h2=h.get(2), h3=h.get(3), h4=h.get(4),
                        h5=h.get(5), resid=r, dc=dc))
    return out


def sweep_freq(level, freqs=None):
    freqs = freqs if freqs is not None else np.geomspace(20, 20000, 40)
    out = []
    for f in freqs:
        g, h, r, dc = tone(float(f), level)
        out.append(dict(f=float(f), gain=g, h2=h.get(2), h3=h.get(3), resid=r))
    return out


if __name__ == "__main__":
    t0 = time.time()
    g = tone(1000, -20)
    print("one point", g[0], "in", round(time.time() - t0, 2), "s")


def tone_c(f, level_db, dur=None, settle=None, nh=5):
    """Complex response: {k: (a_k + j b_k)} for harmonics 1..nh, divided by the
    input amplitude. Convention: output = |H| sin(k w t + arg H), so arg H > 0
    is a lead, the same convention as scipy.signal.freqz."""
    dur = dur or max(2.0, 16.0 / f)
    settle = settle or dur * 0.5
    n = int(dur * SR)
    t = np.arange(n) / SR
    a = 10 ** (level_db / 20)
    y = run(a * np.sin(2 * np.pi * f * t))
    s0 = int(settle * SR)
    ty, tt = y[s0:], t[s0:]
    H = [k for k in range(1, nh + 1) if k * f < SR / 2 * 0.98]
    cols = [np.ones_like(tt)]
    for k in H:
        cols += [np.sin(2 * np.pi * k * f * tt), np.cos(2 * np.pi * k * f * tt)]
    c, *_ = np.linalg.lstsq(np.stack(cols, 1), ty, rcond=None)
    return {k: complex(c[1 + 2 * i], c[2 + 2 * i]) / a for i, k in enumerate(H)}
