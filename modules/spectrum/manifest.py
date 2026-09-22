"""SPECTRUM -- a filter pedal on stock FILTER's id.

A per-track insert on id 0x04 (FX1 only; an FX2 instance runs as a dry pass,
decided from the allocator base at init). MODE selects the filter:

  * LADR -- the linear zero-delay Moog transistor ladder (audiojs/filter
    moogLadder, MIT), 24 dB/oct, resonance to the edge of self-oscillation
    at RES 127 and bounded there;
  * LP / BP -- a driven Oberheim SEM zero-delay SVF (Zavalishin's
    trapezoidal form, audiojs/filter oberheim, MIT), the cutoff ramped per
    sample across the block;
  * ISO -- an isolator (Airwindows Capacitor2); RES is the dielectric colour;
  * VOWL -- a three-formant bank (constant-peak-gain resonators) morphed
    across A E I O U by FREQ, RES narrowing the bands.

ENV (a block-peak follower, instant attack, LSP = release) and LDP (an LFO,
LSP = speed) both move the cutoff; WDTH is mid/side width on the output.

Every mpy is `mpy x0,y1`, the audited-signed form; every clip is the store
limiter.
"""

from remix.schema import (ModeView, BusRole, Claims, DspSection, Formatter, Harness, Kind,
                          MenuEntry, Module, Param, YBase)

_PLAIN = Formatter.PLAIN
_STEP = Formatter.STEPPED
_BIPOL = Formatter.BIPOLAR   # drawn -64..+63 around 64

_BLANK = Param(b"", 0)

# The SEM core's g/2 = tan(pi*fc/fs)/2 at FREQ 0, 4, .., 128 for fc = 60 Hz *
# 250^(FREQ/128): exponential, 8 octaves to 15 kHz, an equal step per
# detent. Halved so g stays a fraction: tan at 15 kHz is 1.82.
G2_TABLE = (
    0x004608, 0x005338, 0x0062e4, 0x007584, 0x008ba6, 0x00a5f3,
    0x00c534, 0x00ea59, 0x01167d, 0x014af3, 0x01894c, 0x01d367,
    0x022b7d, 0x029435, 0x0310b7, 0x03a4cb, 0x0454f5, 0x0526a1,
    0x06205b, 0x074a11, 0x08ad72, 0x0a5676, 0x0c541f, 0x0eb998,
    0x11a007, 0x15297c, 0x198619, 0x1efd7f, 0x260151, 0x2f5508,
    0x3c6e04, 0x508579, 0x748894,
    )

# VOWL: cos(2*pi*F/fs) for five vowels x three formants, Peterson & Barney
# (1952) male means as the classic formant tables carry them --
# a 730/1090/2440, e 530/1840/2480, i 270/2290/3010, o 570/840/2410,
# u 300/870/2240 Hz; bandwidths 90/110/170 Hz are constants in the asm.
COS_TABLE = (
    0x7f4eed, 0x7e75a6, 0x7857c9, 0x7fa29f, 0x7ba06f,
    0x7817aa, 0x7fe7c2, 0x793f4f, 0x7468a6, 0x7f9401,
    0x7f159c, 0x788738, 0x7fe212, 0x7f0497, 0x798957,
)

# VOWL's per-formant constants, after the COS table: for each formant k the
# pair (e_k, R_k) with R_k = exp(-pi*bw_k/fs) for bw = 90 / 110 / 170 Hz and
# e_k = 0.9*(1 - R_k), the RES narrowing (R' = R_k + e_k*RES). Read with
# p:(r2)+ by the per-block formant loop.
VOWL_ER = (
    0x00bc7a, 0x7f2e95,
    0x00e632, 0x7f003a,
    0x0162ff, 0x7e758f,
)

MODULE = Module(
    name="spectrum",
    key="SPECTRUM",
    kind=Kind.DSP_EFFECT,
    doc="BamSep26 station: a filter pedal -- SEM LP/BP/HP, Airwindows Capacitor2, formants, the Moog ladder; ENV and LFO onto the cutoff; width.",
    menu=MenuEntry(
        fx2_id=0x04,
        replaces="FILTER",            # stock FILTER's id: both menus, every part
        donor_desc=0x400d58b8,        # DARK REV: 12 active slots, selects on 7/9/11
        abbr=b"SPEC",
        fullname=b"Spectrum",
        build_tag=True,
    ),
    params=(
        # ---- page 1: the performance surface, scene/CC-reachable -----------
        Param(b"FREQ", 127, active=True, formatter=_PLAIN,
              doc="the cutoff, 60 Hz..15 kHz exponential; in VOWL the vowel A-E-I-O-U; ENV and LFO move it"),
        Param(b"RES", 0, active=True, formatter=_PLAIN, link=True,
              doc="the flavour: resonance in LP/BP/LADR, sharpness in VOWL, the dielectric colour in ISO"),
        Param(b"ENV", 64, 128, active=True, formatter=_BIPOL,
              doc="the envelope follower onto the cutoff, drawn -64..+63; 0 = none"),
        Param(b"LDP", 0, active=True, formatter=_PLAIN,
              doc="LFO depth onto the cutoff, 0 = none (a negative depth would only flip the phase)"),
        Param(b"LSP", 64, 128, active=True, formatter=_PLAIN, link=True,
              doc="LFO speed ~0.08..9 Hz, and the envelope release (0 slow .. 127 fast)"),
        Param(b"WDTH", 64, 128, active=True, formatter=_BIPOL,
              doc="stereo width of the output, drawn -64..+63: 0 untouched, -64 mono, +63 double sides"),
        # ---- page 2: knob / select / knob / select / knob / select ----------
        # MODE top left (slot 6, the knob field), as on every effect (16 Sep 2026)
        Param(b"MODE", 0, 5, active=True, formatter=_STEP,
              labels=("LADR", "LP", "BP", "ISO", "VOWL"),
              doc="LADR the Moog (first: the best one); LP/BP the SEM; ISO an isolator (Capacitor2); VOWL"),
        _BLANK, _BLANK, _BLANK, _BLANK, _BLANK,
    ),
    # FREQ is always where, RES always the flavour; a mode labels RES for
    # what it is there. ISO's defaults land by stamp and, with MODE DEFAULTS
    # in the remix, on a panel MODE turn.
    mode_slot=6,
    mode_views=(ModeView(mode=3, names={0: b"LOW", 1: b"COLR"}, defaults={0: 127, 1: 64}),
                ModeView(mode=4, names={0: b"VOWL", 1: b"SHRP"})),   # FREQ morphs A E I O U
    dsp=DspSection(
        asm="modules/spectrum/spectrum.asm",
        # G2_TABLE is read with p:(r5)+ and interpolated linearly per block.
        ptable=G2_TABLE + COS_TABLE + VOWL_ER,
        priority=12,                  # after every existing module
        bus_role=BusRole.NONE,        # an insert that also WRITES the bus
        ybase=YBase.NEVER,
        gate_label=None,              # no housekeeping, so no XBUS gate
    ),
    # FX1 only: the rig's cycle envelope closes only with the stations on
    # FX1. The FX2 chooser hides the row; verify_spectrum proves the dry pass.
    claims=Claims(fx1_only=True),
    harness=Harness(layout_char="1", is_server=False, bus_client=False),
)
