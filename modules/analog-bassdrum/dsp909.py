#!/usr/bin/env python3
"""The 909 voice on the DSP: tables, the assembled engine and its reference.

fit909.json holds the numbers fitted to the user's Drumazon 2 (DSP909.md
says how and with which scripts). From them this builds:

  tables()        the 128-entry knob tables and fixed coefficients, 24-bit
  source(layout)  bd909.asm with every placeholder filled
  assemble()      dsp_asm, then its listing checked for su/uu multiplies and
                  the max/rnd encodings AGENTS.md warns about
  Voice           a float reference with the engine's exact structure (the
                  tolerance gate compares the DSP against it)

No plugin state, recording or Elektron byte is used or written.
"""
from __future__ import annotations

import json
import math
import pathlib
import re
import subprocess
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FIT = json.loads((HERE / 'fit909.json').read_text())
RATE = 44100
OUT = 0.4                     # output scale: Drumazon's init peak 0.98 -> 0.39
VBS = 1.62                    # T_VB = vb/VBS <= 1 at ACCNT 127
VAS = 1.92                    # T_VA = va/VAS
SHIFT = 16                    # the attack path's final x16 (four asl)
NODES = FIT['nodes']
B = FIT['body']
PU = FIT['pulse']
NZ = FIT['noise']
MK = FIT['mackie']

# State block: X words at r5+k. The 48-bit states are hi/lo pairs (LMH/LML the
# VCA, THH/THL the thump, HPH/HPL the desk's coupling): X only, no Y.
STATE = ['EP', 'U', 'O', 'C', 'PULSE', 'R8', 'UPPREV', 'HP', 'BX1', 'BX2',
         'BY1', 'BY2', 'LPU', 'LCG', 'NPREV', 'NH', 'N1', 'N2', 'E2', 'E3',
         'YL', 'ACC', 'PT', 'SEG', 'INCB', 'INCA', 'DKP', 'DKD', 'GBODY',
         'GDC', 'GP', 'GN', 'KLPF', 'LMH', 'LML', 'THH', 'THL',
         'TIN', 'PAD', 'GB', 'OB', 'GH', 'OH', 'LB', 'M2', 'KHP', 'HPH', 'HPL']
OFF = {name: k for k, name in enumerate(STATE)}
SWORDS = len(STATE)


def u_of(i):
    """OT knob 0..127 -> Drumazon's 0..1 (64 is its 50 %)."""
    return i / 128 if i <= 64 else .5 + (i - 64) / 126


def _pchip(xs, ys):
    """Monotone cubic (Fritsch-Carlson), so no scipy is needed at build time."""
    n = len(xs)
    h = [xs[k + 1] - xs[k] for k in range(n - 1)]
    d = [(ys[k + 1] - ys[k]) / h[k] for k in range(n - 1)]
    m = [d[0]] + [0.0] * (n - 2) + [d[-1]]
    for k in range(1, n - 1):
        if d[k - 1] * d[k] > 0:
            w1, w2 = 2 * h[k] + h[k - 1], h[k] + 2 * h[k - 1]
            m[k] = (w1 + w2) / (w1 / d[k - 1] + w2 / d[k])

    def f(x):
        k = min(max(0, next((j for j in range(n - 1) if x <= xs[j + 1]), n - 2)), n - 2)
        t = (x - xs[k]) / h[k]
        h00, h10 = 2*t**3 - 3*t**2 + 1, t**3 - 2*t**2 + t
        h01, h11 = -2*t**3 + 3*t**2, t**3 - t**2
        return h00*ys[k] + h10*h[k]*m[k] + h01*ys[k+1] + h11*h[k]*m[k+1]
    return f


_LOG = lambda vals: [math.log(v) for v in vals]
FB = _pchip(NODES, _LOG(FIT['pitch']['fb_hz']))
AP = _pchip(NODES, _LOG(FIT['pitch']['A_hz']))
A_REF = FIT['pitch']['A_hz'][NODES.index(.5)]
GT = _pchip(NODES, _LOG([a / A_REF for a in FIT['tune']['A_hz']]))
TAUP = _pchip(NODES, _LOG(FIT['tune']['tau_s']))
_GD = _pchip(NODES, _LOG([a / A_REF for a in FIT['depth']['A_hz']]))
TAUD = _pchip(NODES, _LOG(FIT['decay']['tau_s']))
VA = _pchip(FIT['velocity']['attack_v'], FIT['velocity']['attack_gain'])


def GD(u):
    """TUNE DEPTH: the fitted nodes from 0.125, the power law below (A -> 0)."""
    if u >= .125:
        return math.exp(_GD(u))
    return math.exp(_GD(.125)) * (max(u, 1e-9) / .125) ** FIT['depth']['below_0.125_exponent']


def thump(A):
    t = FIT['thump_vs_A']
    s = lambda a: t['a'] + t['b'] * (1 - math.exp(-a / t['A0_hz']))
    return s(A) / s(t['A_ref_hz'])


def k_exp(tau):
    return math.exp(-1 / (tau * RATE))


def k_pole(fc):
    return math.exp(-2 * math.pi * fc / RATE)


def biquad_lp(f0, q):
    w = 2 * math.pi * f0 / RATE
    al = math.sin(w) / (2 * q)
    a0 = 1 + al
    b0 = (1 - math.cos(w)) / 2 / a0
    return b0, 2 * b0, b0, -2 * math.cos(w) / a0, (1 - al) / a0


# The 909 service notes' output network (R473/474 + R530/532, C511/512 into
# R531/533): the existing LPF knob. 0 = off, 64 = the drawn network.
_NOMINAL = 1 / (2 * math.pi * (3200 * 10000 / (3200 + 10000)) * 10e-9)
LPF_HZ = [0] + [500 * (_NOMINAL / 500) ** ((i - 1) / 63) if i <= 64 else
                _NOMINAL * (18000 / _NOMINAL) ** ((i - 64) / 63) for i in range(1, 128)]

LCG_M = 1664525                       # = 2K + 1, 1 mod 4: full period with an odd c
LCG_K = (LCG_M - 1) // 2
LCG_C = 1013904223 & 0xffffff
SEED = 0x5a5a5b
assert LCG_C & 1 and LCG_M % 4 == 1 and LCG_K < 1 << 23


def _white_rms_through_filters():
    """RMS of the LCG through the noise HP and two LPs (normalises NOISE g)."""
    s = SEED
    anh, kl1, kl2 = k_pole(NZ['f_hp']), 1 - k_pole(NZ['f_lp1']), 1 - k_pole(NZ['f_lp2'])
    nh = prev = n1 = n2 = acc = 0.0
    n = 0
    for i in range(300000):
        s = (s * LCG_M + LCG_C) & 0xffffff
        w = (s - (1 << 24) if s & 0x800000 else s) / 8388608
        nh = anh * nh + (1 + anh) / 2 * (w - prev); prev = w
        n1 += kl1 * (nh - n1); n2 += kl2 * (n1 - n2)
        if i > 10000:
            acc += n2 * n2; n += 1
    return math.sqrt(acc / n)


NOISE_RMS = _white_rms_through_filters()


PADMAX = 1 / (1 - MK['k_sat'])   # the curve tops out at 1 - k_sat: never a hard clip
_RISE = _pchip(MK['rise_knots'], MK['rise_db'])


def mk_drive(i):
    """SAT i: the stage's gain, 0 dB .. top_db over 1/PADMAX (so SAT 0 is transparent)."""
    return 10 ** (i / 127 * MK['top_db'] / 20) / PADMAX


def mk_pad(i):
    """SAT i: the make-up; the init patch's level rises target_rise_db over the knob."""
    return PADMAX * 10 ** (-max(0.0, _RISE(i) - MK['target_rise_db'] * i / 127) / 20)


def mk_sat(v):
    """The Mackie curve: clip at 1, then v - k_sat v^5."""
    v = max(-1.0, min(1 - 2 ** -23, v))
    return v - MK['k_sat'] * v ** 5


def tables():
    """Every table and constant, as floats. q24() quantises for the DSP."""
    ap = [math.exp(AP(u_of(i))) for i in range(128)]
    gt = [math.exp(GT(u_of(i))) for i in range(128)]
    gd = [GD(u_of(i)) for i in range(128)]
    # a hair above each maximum: a 24-bit fraction cannot hold 1.0
    ap_max, gt_max, gd_max = (max(v) * (1 + 2 ** -20) for v in (ap, gt, gd))
    a_max = ap_max * gt_max * gd_max
    k_inc = 2 * a_max / RATE
    assert k_inc < 1
    t = dict(
        T_INCB=[2 * math.exp(FB(u_of(i))) / RATE for i in range(128)],
        T_AP=[a / ap_max for a in ap],
        T_GT=[g / gt_max for g in gt],
        T_GD=[g / gd_max for g in gd],
        T_DKP=[1 - k_exp(math.exp(TAUP(u_of(i)))) for i in range(128)],
        T_DKD=[1 - k_exp(math.exp(TAUD(u_of(i)))) for i in range(128)],
        # thump level by sweep size: index = floor(q*128), A = mid-bin
        T_THS=[OUT * B['k_dc'] * thump((i + .5) / 128 * a_max) * VBS for i in range(128)],
        T_VB=[(max(i, 1) / 100) ** 2 / VBS for i in range(128)],
        T_VA=[VA(max(i, 1)) / VAS for i in range(128)],
        T_ATP=[OUT * (B['k0'] + u_of(i)) * VAS for i in range(128)],
        # the noise chain runs at half scale: its HP swings (w - prev), up to 2
        T_ATN=[2 * OUT * u_of(i) * NZ['g'] / NOISE_RMS * VAS / SHIFT for i in range(128)],
        T_LPF=[1 - 2 ** -23] + [1 - k_pole(f) for f in LPF_HZ[1:]],
        # SAT: drive / stage / 32 (five asl) and the make-up / 2 (one asl)
        T_TIN=[mk_drive(i) / MK['stage'] / 32 for i in range(128)],
        T_PAD=[mk_pad(i) / 2 for i in range(128)],
        T_KHP=[MK['k_hp'] * min(1.0, i / MK['hp_full']) for i in range(128)],
        # LOW / HIGH: the band's drive / 4 (two asl; u = 1 clamps a hair
        # under 4) and its output, stage / 16 folded in
        T_GB=[min(u_of(i) ** 2, 1 - 2 ** -23) for i in range(128)],
        T_OB=[math.sqrt(2 * u_of(i)) * MK['stage'] / 16 for i in range(128)],
    )
    b0, b1, b2, a1, a2 = biquad_lp(PU['f0'], PU['q'])
    ahp, anh = k_pole(PU['f_hp']), k_pole(NZ['f_hp'])
    c = dict(
        KA_INC=k_inc, K_BODY=4 * OUT * B['G'] * VBS,
        NREL=math.ceil(B['t_r'] * RATE), FRAC=1 - (math.ceil(B['t_r'] * RATE) - B['t_r'] * RATE),
        U0=-0.5 + B['x_r'] / 2, THETA=FIT['theta'], NHOLD=round(B['t_h'] * RATE),
        KA=1 - k_exp(B['tau_a']), DKDROOP=1 - k_exp(B['tau_droop']), KTH=1 - k_exp(B['tau_dc']),
        KR=1 - k_exp(PU['tau_r2']), KR8=8 * (1 - k_exp(PU['tau_r2'])),
        AHP=ahp, BHP=(1 + ahp) / 2, KU=1 - k_pole(PU['f_u']),
        KW16=PU['k_w'] / 128, KU16=PU['k_u'] / 128,
        ANH=anh, BNH=(1 + anh) / 4, KL1=1 - k_pole(NZ['f_lp1']), KL2=1 - k_pole(NZ['f_lp2']),
        K2=k_exp(NZ['t2']), K3=k_exp(NZ['t2']) * k_exp(NZ['t1']),
        LCGK=LCG_K, LCGC=LCG_C, SEED=SEED,
        KSAT=MK['k_sat'], KB=MK['kb'], KM=MK['km'], KMS=2 * MK['stage'] / 16,
    )
    # S/16 in Horner order: the degree-11 partial sums reach 2.8 at S/4; the
    # engine's two asl bring the result back to S/4
    cpoly = [x / 16 for x in list(B['c'])[::-1]] + [B['c0'] / 16]
    assert horner_ok(cpoly) < 1, 'Horner partial sum overflows'
    cbiq = [b0, b1, b2, -a1 / 2, -a2]
    for name, v in list(t.items()) + [('CPOLY', cpoly), ('CBIQ', cbiq)]:
        assert all(-1 <= x < 1 for x in v), name
    return t, c, dict(CPOLY=cpoly, CBIQ=cbiq), dict(a_max=a_max, k_inc=k_inc)


def q24(x):
    """A fraction as a 24-bit word (clamped, rounded)."""
    v = max(-1 << 23, min((1 << 23) - 1, round(x * (1 << 23))))
    return v & 0xffffff


def horner_ok(cpoly):
    """Every Horner partial sum stays inside the 24-bit register it moves to."""
    worst = 0.0
    for k in range(-1000, 1001):
        x = k / 1000
        h = cpoly[0]
        for cf in cpoly[1:]:
            h = cf + h * x
            worst = max(worst, abs(h))
    return worst


def source(layout):
    """bd909.asm with its placeholders filled. layout: table and list bases."""
    tab, con, lists, _ = tables()
    text = (HERE / 'bd909.asm').read_text()
    subs = {name: f'${k:x}' for name, k in OFF.items()}
    subs['SWORDS'] = f'${SWORDS:x}'
    for name in list(tab) + list(lists):
        subs[name] = f"${layout[name]:x}"
    for name, v in con.items():
        if name in ('NREL', 'NHOLD'):
            subs[name] = f'${int(v):x}'
        elif name in ('LCGK', 'LCGC', 'SEED'):
            subs[name] = f'${int(v) & 0xffffff:06x}'
        else:
            subs[name] = f'${q24(v):06x}'
    out = re.sub(r'@([A-Z0-9_]+)@', lambda m: subs[m.group(1)], text)
    left = re.findall(r'@[A-Z0-9_]+@', out)
    assert not left, left
    labels = re.findall(r'^(\w+):', out, re.M)
    for a in labels:
        for b in labels:
            assert a == b or not b.startswith(a), f'label {a} prefixes {b}'
    return out


def desk_source(layout):
    """The desk stage alone, for the stage gate: zt01 decodes SAT/LOW/HIGH
    from r6 like zq01, then runs step 12 on each input sample at x:(r0),
    writing it back as L,R. The text is bd909.asm's own, between markers."""
    full = source(layout)
    cut = lambda tag: full[full.index(f';<{tag}>'):full.index(f';</{tag}>')]
    return ('zt01:\n        move    #>$ffffff,m0\n        move    #>$ffffff,m1\n'
            '        move    #>$ffffff,m4\n' + cut('desk-decode') +
            '        do      n7,zt02\n        move    x:(r0),a\n' +
            cut('desk') + 'zt02:\n        rts\n')


def data_lines(layout):
    """Tables and coefficient lists as X data for bd909_host: 'X addr w w ...'."""
    tab, _, lists, _ = tables()
    lines = []
    for name, vals in list(tab.items()) + list(lists.items()):
        lines.append('X %x ' % layout[name] + ' '.join('%06x' % q24(v) for v in vals))
    return '\n'.join(lines) + '\n'


def default_layout(base=0x1000):
    tab, _, lists, _ = tables()
    lay, a = {}, base
    for name, vals in list(tab.items()) + list(lists.items()):
        lay[name] = a
        a += len(vals)
    return lay


DSP_ASM = ROOT / 'vendor/dsp56300/build/source/dsp_host/dsp_asm'
DISASM = ROOT / 'vendor/dsp56300/build/source/disassemble/dsp56kDisassemble'
BAD = re.compile(r'\b(mpysu|macsu|mpyuu|macuu|max|maxm|rnd)\b')
LINE = re.compile(r'^([0-9a-f]{6}): (\S+)(?:\s+(.*?))?\s*; [0-9a-f]{6}(?: [0-9a-f]{6})?$')


def _decoded(text):
    return {int(m.group(1), 16): (m.group(2), (m.group(3) or '').strip())
            for m in map(LINE.match, text.splitlines()) if m}


def assemble(org, layout, out_bin, src=None):
    """Assemble at org; return ({label: address}, listing).

    Disassembles what it assembled (AGENTS.md): every address's decoded
    mnemonic AND operands must equal the typed ones, and no su/uu/max/rnd
    form may appear in the decode. A listing echoes the SOURCE text, so it
    cannot see `mac -y0,y1,b` written as `macsu -y0,y1,b` (28 Sep 2026: an
    operand order outside the multiplier's pair table, found by the gate).
    Branch and loop operands render differently in the two tools and are
    compared by mnemonic only."""
    src = src or source(layout)
    with tempfile.TemporaryDirectory() as tmp:
        asm = pathlib.Path(tmp) / 'bd909.asm'
        asm.write_text(src)
        sym = pathlib.Path(tmp) / 'bd909.sym'
        r = subprocess.run([str(DSP_ASM), '-in', str(asm), '-org', f'{org:x}', '-out', str(out_bin),
                            '-list', '-sym', str(sym)], capture_output=True, text=True)
        if r.returncode:
            raise RuntimeError(r.stdout[-3000:] + r.stderr[-2000:])
        listing = r.stdout
        symbols = {n: int(a, 16) for n, a in (l.split() for l in sym.read_text().splitlines())}
        pathlib.Path(out_bin).with_suffix('.lst').write_text(listing)
        d = subprocess.run([str(DISASM), '-in', str(out_bin), '-pc', f'{org:x}', '-le'],
                           capture_output=True, text=True)
    typed, dec = _decoded(listing), _decoded(d.stdout)
    assert typed and len(dec) >= len(typed) * 0.9, 'no decode to compare'
    norm = lambda op: re.sub(r'\s+', '', op.split(';')[0]).replace('#>', '#').replace('#<', '#').lower()
    bad = []
    for a, (m, op) in typed.items():
        dm, dop = dec.get(a, ('?', ''))
        if BAD.search(dm) or dm != m:
            bad.append((a, m, op, dm, dop))
        elif m not in ('bsr', 'bra', 'beq', 'bne', 'blt', 'bge', 'jsr', 'jmp', 'do', 'rep') \
                and norm(op) != norm(dop) and not re.search(r'#|\$', op):
            bad.append((a, m, op, dm, dop))
    if bad:
        raise RuntimeError('disassemble-what-you-assemble:\n' + '\n'.join(
            f'  P:{a:06x} typed {m} {op}  decodes {dm} {dop}' for a, m, op, dm, dop in bad))
    return symbols, listing


def rnd24(x):
    """mpyr: the product rounded to 24 bits (ties away from zero is close
    enough here: the DSP's convergent rounding differs only on exact ties)."""
    return math.floor(x * 8388608 + 0.5) / 8388608


def fl24(x):
    """An accumulator stored to 24 bits: two's-complement truncation."""
    return math.floor(x * 8388608) / 8388608


class Voice:
    """Float reference with the engine's structure, block by block. The
    phase path (control products, ep, inc) is quantised as the DSP does it:
    its drift is otherwise the largest DSP-vs-reference difference."""

    def __init__(self, quantized=True):
        self.t, self.c, self.lists, self.meta = tables()
        if quantized:   # the words the DSP receives, back as fractions
            f = lambda v: ((q24(v) ^ 0x800000) - 0x800000) / 8388608
            self.t = {k: [f(v) for v in vals] for k, vals in self.t.items()}
            self.lists = {k: [f(v) for v in vals] for k, vals in self.lists.items()}
            self.c = {k: (v if k in ('NREL', 'NHOLD', 'LCGK', 'LCGC', 'SEED') else f(v))
                      for k, v in self.c.items()}
        self.ep = self.u = self.o = self.m = self.th = 0.0
        self.cnt = (1 << 23) - 1
        self.pulse = 0.0
        self.r = self.upp = self.hp = self.lpu = 0.0
        self.bx1 = self.bx2 = self.by1 = self.by2 = 0.0
        self.lcg = SEED
        self.nprev = self.nh = self.n1 = self.n2 = 0.0
        self.e2 = self.e3 = 0.0
        self.yl = 0.0
        self.lb = self.m2 = self.hps = 0.0

    def block(self, k, trig=None, frames=16):
        t, c = self.t, self.c
        inc_b = t['T_INCB'][k[0]]
        q = rnd24(rnd24(t['T_AP'][k[0]] * t['T_GT'][k[2]]) * t['T_GD'][k[4]])
        inc_a = rnd24(q * c['KA_INC'])
        dkp, dkd = t['T_DKP'][k[2]], t['T_DKD'][k[1]]
        vb = t['T_VB'][k[7]]
        gdc = vb * t['T_THS'][min(127, int(q * 128))]
        gbody = vb * c['K_BODY']
        va = t['T_VA'][k[7]]
        gp = va * t['T_ATP'][k[3]]
        gn = va * t['T_ATN'][k[3]]
        klpf = t['T_LPF'][k[8]]
        self.desk_knobs(k)
        b0, b1, b2, na1h, na2 = self.lists['CBIQ']
        cp = self.lists['CPOLY']
        out = []
        for i in range(frames):
            if trig is not None and i == trig:
                self.ep = self.pulse = self.e2 = self.e3 = 1 - 2 ** -23
                self.cnt = 0
                self.r = 0.0
                self.m = 1.0
                self.u = fl24(c['U0'] - c['FRAC'] * (inc_b + inc_a))
            inc = fl24(inc_b + inc_a * self.ep)
            self.ep = fl24(self.ep - self.ep * dkp)
            if self.cnt >= c['NREL']:
                self.u += inc
                if self.u >= 1:
                    self.u -= 2
            x = 1 - 2 * abs(self.u)
            if x >= c['THETA']:
                self.pulse = 0.0
            x = min(x, 1 - 2 ** -23)
            h = cp[0]
            for cf in cp[1:]:
                h = cf + h * x
            s4 = 4 * h
            self.o += c['KA'] * (1 - self.o)
            self.m -= self.m * (c['DKDROOP'] if self.cnt < c['NHOLD'] else dkd)
            g = self.o * self.m
            body = gbody * g * s4
            self.th += c['KTH'] * (g - self.th)
            body -= gdc * self.th
            self.r += c['KR'] * (1 - self.r)
            up8 = -8 * self.r * self.pulse
            self.lpu += c['KU'] * (up8 - self.lpu)
            self.hp = c['AHP'] * self.hp + c['BHP'] * (up8 - self.upp)
            self.upp = up8
            w8 = b0 * self.hp + b1 * self.bx1 + b2 * self.bx2 + 2 * na1h * self.by1 + na2 * self.by2
            self.bx2, self.bx1, self.by2, self.by1 = self.bx1, self.hp, self.by1, w8
            pt = gp * (c['KW16'] * w8 + c['KU16'] * self.lpu)
            self.lcg = (self.lcg * LCG_M + LCG_C) & 0xffffff
            wn = (self.lcg - (1 << 24) if self.lcg & 0x800000 else self.lcg) / 8388608
            self.nh = c['ANH'] * self.nh + c['BNH'] * (wn - self.nprev)
            self.nprev = wn
            self.n1 += c['KL1'] * (self.nh - self.n1)
            self.n2 += c['KL2'] * (self.n1 - self.n2)
            self.e2 *= c['K2']; self.e3 *= c['K3']
            nt = gn * (self.e2 - self.e3) * self.n2
            y = body + SHIFT * (pt + nt)
            y = max(-1.0, min(1 - 2 ** -23, y))
            self.yl += klpf * (y - self.yl)
            out.append(self.desk(self.yl))
            self.cnt = min(self.cnt + 1, (1 << 23) - 1)
        return out

    def desk_knobs(self, k):
        t = self.t
        self.dk = (t['T_TIN'][k[5]], t['T_PAD'][k[5]], t['T_KHP'][k[5]],
                   t['T_GB'][k[9]], t['T_OB'][k[9]], t['T_GB'][k[10]], t['T_OB'][k[10]])

    def desk(self, y):
        """The Mackie stage, one sample; the scalings are bd909.asm step 12's."""
        c = self.c
        tin, pad, khp, gb, ob, gh, oh = self.dk
        clip = lambda v: max(-1.0, min(1 - 2 ** -23, v))
        sat = lambda v: clip(v) - c['KSAT'] * clip(v) ** 5
        self.hps += khp * (y - self.hps)
        x = sat(32 * tin * (y - self.hps))
        self.lb += c['KB'] * (x - self.lb)
        rest2 = (x - self.lb) / 2
        self.m2 += c['KM'] * (rest2 - self.m2)
        high2 = rest2 - self.m2
        acc = ob * sat(4 * gb * self.lb) + oh * sat(8 * gh * high2) + c['KMS'] * self.m2
        return clip(2 * pad * sat(16 * acc))


if __name__ == '__main__':
    t, c, lists, meta = tables()
    print(f"A max {meta['a_max']:.1f} Hz, K_A {meta['k_inc']:.4f}, noise rms {NOISE_RMS:.4f}, "
          f"Horner worst |h| {horner_ok(lists['CPOLY']):.3f}")
    for k in ('K_BODY', 'NREL', 'FRAC', 'U0', 'NHOLD', 'KW16', 'KU16'):
        print(k, c[k])
