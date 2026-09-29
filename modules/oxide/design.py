"""OXIDE's design: the fitted tape model, and every number the DSP code uses.

The model is a Wiener-Hammerstein fit to UADx Oxide Tape Recorder (15 IPS,
NAB, Repro, input/output at 0 dB, noise reduction on, so silence renders
exact zeros), measured 28-29 Sep 2026 by hosting the VST3 headlessly
(`modules/oxide/fit/`). Linear, then a static curve, then linear:

    pre   E1  first-order high-pass 5.32 Hz, first-order low shelf +20.3 dB
              (corner 5.32 Hz, zero at 55 Hz): the bass is driven hardest
    curve     odd, linear to ~0.5 FS, flat at 0.909 above |u| ~ 1.75
    post  E2  low shelf 13.3 Hz Q 0.72 -21.3 dB (a TPT state-variable
              filter: a direct-form biquad cannot place poles this close
              to DC in 24 bits), first-order high shelf +2.1 dB (10.4 kHz),
              first-order all-pass 52.9 Hz with a sign flip, +0.107 dB

Which side of the curve each part sits on was measured, not assumed: the
3rd/5th-harmonic phases of the plugin fit the pre filter to 0.5/0.3 deg RMS
only with the high-pass and the shelf before the curve and the all-pass
after it. The 52.9 Hz all-pass is there under CCIR as well (it is not the
NAB 3180 us term).

Against the plugin (float model, the 33-point curve below): band levels
within 0.24 dB and peaks within 0.7 dB on drums and pink noise at -24..+6
dBFS; sine gain within 0.5 dB up to 0 dBFS (4 kHz at +6 dBFS: -0.9 dB);
two-tone intermodulation within 0.2 dB. Not modelled: the plugin's 5.6 kHz
all-pass and its ~2 samples of latency (phase only), 7.5 IPS, CCIR,
hiss, wow and flutter.
"""

import math

SR = 44100.0

# ---- the fit (full precision: these ARE the model) ------------------------
E1_HPF_HZ = 5.320168876925031
E1_SHELF_HZ = 5.320151470321708
E1_SHELF_DB = 20.31949441373395
E2_LS_HZ = 13.313646245960554
E2_LS_Q = 0.7160053321105934
E2_LS_DB = -21.319463355074543
E2_HS_HZ = 10391.474083299481
E2_HS_DB = 2.144384799544809
E2_AP_HZ = 52.8713923292435
E2_GAIN_DB = 0.10697400408247087
E2_SIGN = -1
# V(u) at u = 0, 0.125, ... 2.0; odd; held beyond |u| = 2
CURVE_POS = (0.0, 0.126926, 0.253367, 0.373604, 0.483964, 0.581019,
             0.66318, 0.731695, 0.786708, 0.828929, 0.858923, 0.880312,
             0.89466, 0.901424, 0.905421, 0.908448, 0.908726)
CURVE = tuple(-v for v in CURVE_POS[:0:-1]) + CURVE_POS      # u = -2 .. 2, 33 points

# ---- the knobs ------------------------------------------------------------
# 0.3 dB a step; IN 48 and OUT 80 are exactly 0 dB (table points).
DB_STEP = 0.3
IN_ZERO, OUT_ZERO = 48, 80


def in_db(v): return DB_STEP * (v - IN_ZERO)
def out_db(v): return DB_STEP * (v - OUT_ZERO)


def _law(db_of, v):
    """The gain the DSP applies: exact dB at knob 0, 8 .. 128 (its table
    points), linear in amplitude between (at most 0.08 dB off the dB law)."""
    i, f = divmod(v, 8)
    lo, hi = 10 ** (db_of(8 * i) / 20), 10 ** (db_of(8 * i + 8) / 20)
    return lo + (hi - lo) * f / 8


def in_gain(v): return _law(in_db, v)
def out_gain(v): return _law(out_db, v)


# ---- fixed-point scalings (see oxide.asm's header) -------------------------
#   hh = h/2 (the high-pass), s = u/16 (E1's output), t = u*gin/2 (the curve's
#   argument, clamped), v = V/4 (the curve's output), z = E2's shelf pair / 2.
#   out = q * c_out * 64, c_out = sign * gain * gout / 8.
def q23(v):
    r = round(v * (1 << 23))
    if not -(1 << 23) <= r < (1 << 23):
        raise ValueError(f"{v} does not fit Q23")
    return r


def _tan(f): return math.tan(math.pi * f / SR)


def coefficients():
    """name -> float value; the asm carries each as an immediate `; COEF name`."""
    c = {}
    w = _tan(E1_HPF_HZ)
    c["C1H"] = 0.5 / (1 + w)                   # hpf1, halved: c/2
    c["P1"] = (1 - w) / (1 + w)
    w = _tan(E1_SHELF_HZ); G = 10 ** (E1_SHELF_DB / 20)
    c["B0S"] = (1 + G * w) / (1 + w) / 8       # sh1 on hh = h/2 into s = u/16
    c["B1S"] = (G * w - 1) / (1 + w) / 8
    c["P2"] = (1 - w) / (1 + w)
    # the RBJ low shelf as a TPT SVF at g = tan(pi f0/fs)/sqrt(A) (the same
    # bilinear map: identical response). Its outputs satisfy hp + k bp + lp = x
    # exactly, so y = hp + A k bp + A^2 lp = x + k(A-1) bp + (A^2-1) lp, and hp
    # is never formed: v1 = g D (x - s2 - (k+g) s1).
    A = 10 ** (E2_LS_DB / 40); k = 1 / E2_LS_Q
    g = _tan(E2_LS_HZ) / math.sqrt(A)
    c["KG2"] = (k + g) / 2
    c["GD"] = g / (1 + g * (g + k))
    c["GG"] = g
    c["M1"] = k * (A - 1)
    c["M2"] = A * A - 1
    w = _tan(E2_HS_HZ); G = 10 ** (E2_HS_DB / 20)
    c["HB0"] = (G + w) / (1 + w) / 2           # hs1, halved
    c["HB1"] = (w - G) / (1 + w) / 2
    c["HP"] = (1 - w) / (1 + w)
    t = _tan(E2_AP_HZ)
    c["KAP"] = (t - 1) / (t + 1)
    return c


def coefficients_q23():
    return {k: q23(v) for k, v in coefficients().items()}


def gain_tables():
    """IN: gin/16; OUT: sign * gain * gout / 8; at knob 0, 8, ... 128."""
    g0 = 10 ** (E2_GAIN_DB / 20)
    gi = tuple(q23(10 ** (in_db(8 * i) / 20) / 16) for i in range(17))
    go = tuple(q23(E2_SIGN * g0 * 10 ** (out_db(8 * i) / 20) / 8) for i in range(17))
    return gi, go


def curve_tables():
    """V/4 at the left of each of the 32 segments of t in [-1, 1), and the slope to the next."""
    vt = tuple(q23(CURVE[k] / 4) for k in range(32))
    st = tuple(q23((CURVE[k + 1] - CURVE[k]) / 4) for k in range(32))
    return vt, st


# The coefficient ring: the sixteen numbers a channel multiplies by, in the
# order oxd_ch uses them (r3 walks it modulo 16). GIN and COUT are the knobs,
# written every block; the rest are copied from the P table's tail once.
RING = ("C1H", "P1", "B0S", "B1S", "P2", "GIN", "KG2", "GD",
        "GG", "M2", "M1", "HB0", "HB1", "HP", "KAP", "COUT")


def ptable():
    """The P table, in the order oxide.asm reads it: VT(32) ST(32) IN(17)
    OUT(17), then the ring (16, the knobs' places zero)."""
    vt, st = curve_tables(); gi, go = gain_tables(); c = coefficients_q23()
    ring = tuple(c.get(n, 0) for n in RING)
    return tuple(w & 0xFFFFFF for w in vt + st + gi + go + ring)


# ---- the float reference (the fitted model, what the DSP approximates) ----
def reference(x, in_knob=IN_ZERO, out_knob=OUT_ZERO):
    """x: float samples in (-1, 1). Returns the model's output, float."""
    import numpy as np
    from scipy import signal
    x = np.asarray(x, np.float64)
    c = coefficients()
    gin = in_gain(in_knob); gout = out_gain(out_knob)
    h = signal.lfilter([2 * c["C1H"], -2 * c["C1H"]], [1, -c["P1"]], x)
    u = signal.lfilter([8 * c["B0S"], 8 * c["B1S"]], [1, -c["P2"]], h)
    uu = np.clip(u * gin, -2, 2)
    v = np.interp(uu, np.linspace(-2, 2, 33), CURVE)
    y = _svf_lowshelf(v, c)
    z = signal.lfilter([2 * c["HB0"], 2 * c["HB1"]], [1, -c["HP"]], y)
    q = signal.lfilter([c["KAP"], 1], [1, c["KAP"]], z)
    return E2_SIGN * 10 ** (E2_GAIN_DB / 20) * gout * q


def _svf_lowshelf(x, c):
    import numpy as np
    k_g = 2 * c["KG2"]; gd = c["GD"]; g = c["GG"]
    s1 = s2 = 0.0
    y = np.empty_like(x)
    for n, xn in enumerate(x):
        v1 = gd * (xn - s2 - k_g * s1); bp = v1 + s1; s1 = bp + v1
        v2 = g * bp; lp = v2 + s2; s2 = lp + v2
        y[n] = xn + c["M1"] * bp + c["M2"] * lp
    return y


# ---- the bit-level model of oxide.asm (the render gate's expectation) -----
# Accumulators are Python ints in units of 2^-47 (A2:A1:A0); registers and
# memory words are signed 24-bit ints in units of 2^-23. Every operation is
# the instruction the asm uses, in the asm's order.
_M24 = 1 << 24


def _s24(w):
    w &= 0xFFFFFF
    return w - _M24 if w & 0x800000 else w


def _lim(a):
    """move a,D: A1 with the limiter (saturate when A2:A1 is out of range)."""
    if a >= (1 << 47): return 0x7FFFFF
    if a < -(1 << 47): return -0x800000
    return a >> 24


def _mpy(x, y): return 2 * x * y


def _rnd(a):
    """convergent rounding of the accumulator at A1's LSB (mpyr / macr)."""
    r, rem = a >> 24, a & 0xFFFFFF
    if rem > 0x800000 or (rem == 0x800000 and r & 1):
        r += 1
    return r << 24


STATE = ("X1", "H1", "S1", "C1", "C2", "Y1", "Z1", "Q1")


def fixed(xs, in_knob=IN_ZERO, out_knob=OUT_ZERO, state=None):
    """xs: one channel of signed 24-bit ints. Returns the DSP's output ints.

    `state`: a dict of the channel's filter states (STATE), read at the start
    and written back at the end, so a run can go on where another stopped
    (the master strip's gate changes the knobs between frames); None starts
    from zero, as init leaves the instance block."""
    C = coefficients_q23(); vt, st = curve_tables(); gi, go = gain_tables()
    gin = _knob(gi, in_knob); cout = _knob(go, out_knob)
    # (the ring's order changes no arithmetic: every product is exact)
    X1, H1, S1, C1, C2, Y1, Z1, Q1 = (state.get(k, 0) for k in STATE) if state is not None else (0,) * 8
    out = []
    for x in xs:
        # E1a: hh = (c/2) x - (c/2) x1 + p1 hh1
        a = _mpy(x, C["C1H"]) - _mpy(C["C1H"], X1) + _mpy(H1, C["P1"])
        X1 = x
        hh1_old = H1
        hh = _lim(_rnd(a)); H1 = hh                    # macr
        # E1b: s = b0/8 hh + b1/8 hh1 + p2 s1
        a = _mpy(hh, C["B0S"]) + _mpy(hh1_old, C["B1S"]) + _mpy(S1, C["P2"])
        s = _lim(_rnd(a)); S1 = s                      # macr
        # drive and clamp
        t = _lim(_mpy(s, gin) << 7)
        # the curve
        kk = t >> 19                                   # asr #19 (k - 16)
        frac = ((t & 0x7FFFF) << 4)                    # and, asl #4, b1
        a = _mpy(frac, st[kk + 16]) + (vt[kk + 16] << 24)
        # E2a: the SVF
        v = _lim(a)                                    # move a,y0: kept for the mix
        a = a - (C2 << 24) - _mpy(C1, C["KG2"]) - _mpy(C1, C["KG2"])
        hpd = _lim(_rnd(a))                            # macr
        v1 = _rnd(_mpy(C["GD"], hpd))                  # mpyr
        b = (C1 << 24) + v1                            # bp
        C1 = _lim(v1 + b)
        bp = _lim(b)
        v2 = _rnd(_mpy(C["GG"], bp))
        b = (C2 << 24) + v2                            # lp
        C2 = _lim(v2 + b)
        lp = _lim(b)
        b = _mpy(lp, C["M2"]) + (v << 24) + _mpy(C["M1"], bp)
        y = _lim(_rnd(b))                              # macr
        # E2b: z = hb0 y + hb1 y1 + hp z1
        a = _mpy(y, C["HB0"]) + _mpy(Y1, C["HB1"]) + _mpy(Z1, C["HP"])
        Y1 = y
        z1_old = Z1
        z = _lim(_rnd(a)); Z1 = z                      # macr
        # E2c: q = K z + z1 - K q1
        a = _mpy(z, C["KAP"]) + (z1_old << 24) - _mpy(C["KAP"], Q1)
        q = _lim(_rnd(a)); Q1 = q                      # macr
        # out
        out.append(_lim(_mpy(q, cout) << 6))
    if state is not None:
        state.update(zip(STATE, (X1, H1, S1, C1, C2, Y1, Z1, Q1)))
    return out


def _knob(table, v):
    """The per-block interpolation, as the asm does it (idx = v >> 3)."""
    w = v << 16
    idx = w >> 19
    frac = (w & 0x7FFFF) << 4
    lo, hi = table[idx], table[idx + 1]
    return _lim(_mpy(frac, hi - lo) + (lo << 24))


if __name__ == "__main__":
    import numpy as np
    from scipy import signal
    # the SVF realises the RBJ low shelf exactly
    A = 10 ** (E2_LS_DB / 40); w0 = 2 * math.pi * E2_LS_HZ / SR
    al = math.sin(w0) / (2 * E2_LS_Q); cw = math.cos(w0); sA = 2 * math.sqrt(A) * al
    b = [A * ((A + 1) - (A - 1) * cw + sA), 2 * A * ((A - 1) - (A + 1) * cw), A * ((A + 1) - (A - 1) * cw - sA)]
    a = [(A + 1) + (A - 1) * cw + sA, -2 * ((A - 1) + (A + 1) * cw), (A + 1) + (A - 1) * cw - sA]
    imp = np.zeros(4096); imp[0] = 1
    d = np.max(abs(signal.lfilter(b, a, imp) - _svf_lowshelf(imp, coefficients())))
    print(f"SVF vs RBJ low shelf, max impulse-response difference: {d:.2e}")
    for k, v in coefficients_q23().items():
        print(f"  {k:4s} = ${v & 0xFFFFFF:06x}  ({coefficients()[k]:+.9f})")
    print("P table:", len(ptable()), "words (the ring:", ", ".join(RING) + ")")
