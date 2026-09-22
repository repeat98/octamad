"""CHARACTER -- the station that dirties or tightens.

A per-track insert on stock LO-FI's id 0x1c (FX1 only; an FX2 instance runs
as a dry pass, decided from the allocator base at init). Chain order:
fold -> saturate -> tilt -> compress -> width.

  * FOLD -- WarpFold's wavefolder at a held level;
  * TXTR -- Airwindows Pockey (Chris Johnson, MIT): mu-law encode, a
    continuous quantiser in that domain, decode, an interpolated
    sample-and-hold and a slew smoother; one knob moves its two sliders;
  * SAT -- three JClones (MIT) characters: TAPE = TapeHead (a state-variable
    split at TONE, the low and band parts through a cubic smoothstep, the
    top clean), TUBE = DaTube (u - u^P, the negative half driven twice as
    hard, level-compensated), INFL = OInflator (a signed cubic; DRV is its
    Effect). DRV 0 skips the stage, bit-exact;
  * TONE -- a tilt after the saturator, drawn -64..+63; 0 flat, bit-exact;
  * COMP -- JClones AC1's console channel law: GLUE (slow) on the master
    by position, COMP (fast) elsewhere; the detector's key is the station's
    own input;
  * WDTH -- mid/side width, drawn -64..+63: -64 mono, +63 2x side.

Page 1: DRV FOLD TXTR COMP TONE MIX; page 2: SAT WDTH (20 Sep 2026: TONE
back on page 1 in the return's slot; the return left the station, each
engine prints its wet on its own host)."""

from remix.schema import (BusRole, Claims, DspSection, Formatter, Harness,
                          Kind, MenuEntry, ModeView, Module, Param, YBase)

_PLAIN = Formatter.PLAIN
_STEP = Formatter.STEPPED
_BIPOL = Formatter.BIPOLAR   # drawn -64..+63 around 64

_BLANK = Param(b"", 0)

import math as _m
_P = _m.log(10.0) + 1.0
def _q(v): return min(0x7FFFFF, max(0, round(v * (1 << 23))))

# DaTube's curve: u^P over u in [0, 1], stored as u^P / 2 in 17 pairs (value,
# slope to the next), interpolated in chtube over u/2 in 1/32 steps. T(u) =
# u - u^P applied to u = 1 - |x|; past |x| = 1 the JSFX goes linear, which is
# the same formula with u^P dropped -- the lookup clamps u at 0. TUBE's post
# gain is a per-block division in the source.
def _tube_up(n=16):
    t = [0.5 * (i / n) ** _P for i in range(n + 1)]
    out = []
    for i in range(n + 1):
        out.append(_q(t[i]))
        out.append(_q(t[i + 1] - t[i]) if i < n else 0)
    return tuple(out)


TUBE_UP = _tube_up()
# Pockey's mu-law codec as two 257-point tables over [0, 1] (index = the top
# 8 bits of the magnitude, linear between points; the encode chord error is
# 0.011 at worst, in the first interval), placed after TAPE_D8: ENC at
# TUBE_UP + 51, DEC at + 308 (modules/character/pockey_ref.py).
_math = __import__("math")
POCKEY_ENC = tuple(round(8388607 * min(1.0, _math.log(1 + 255 * i / 256) / _math.log(255))) for i in range(257))
POCKEY_DEC = tuple(round(8388607 * (256 ** (i / 256) - 1) / 255) for i in range(257))
# TapeHead's drive: d/8 with d = 0.8 * 10^(i/16) (0.8x .. 8x over DRV/128),
# 17 words, interpolated (idx = knob >> 19, frac = the 19 bits under it),
# placed after TUBE_UP's 34 in the P table:
TAPE_D8 = (0x0ccccd, 0x0ec7fd, 0x1111af, 0x13b608, 0x16c311, 0x1a48fe, 0x1e5a84, 0x230d41, 0x287a27, 0x2ebe07, 0x35fa27, 0x3e54f4, 0x47facd, 0x531ef0, 0x5ffc89, 0x6ed7eb, 0x7fffff)


MODULE = Module(
    name="character",
    key="CHARACTER",
    kind=Kind.DSP_EFFECT,
    doc="BamSep26 station: crush, fold/ring, saturation, compressor, width.",
    menu=MenuEntry(
        fx2_id=0x1c,
        replaces="LO-FI",
        donor_desc=0x400d58b8,        # DARK REV: 12 active slots, selects 7/9/11
        abbr=b"CHAR",
        fullname=b"Character",
        build_tag=True,
    ),
    params=(
        # ---- page 1: the performance surface, scene/CC-reachable -----------
        Param(b"DRV", 0, active=True, formatter=_PLAIN,
              doc="saturation drive; 0 skips the stage (bit-exact); TAPE 0.8x..8x"),
        Param(b"FOLD", 0, active=True, formatter=_PLAIN,
              doc="wavefolder drive, 1x..48x into the fold at a held level; 0 = no folding"),
        Param(b"TXTR", 0, active=True, formatter=_PLAIN,
              doc="Airwindows Pockey (MIT): the 12-bit sampler texture, both sliders at once; 0 = off"),
        Param(b"COMP", 0, active=True, formatter=_PLAIN,
              doc="compression amount; 0 = no gain reduction at any level"),
        # TONE on page 1 again (20 Sep 2026, the return's slot): a tilt after
        # the saturator, drawn -64..+63.
        Param(b"TONE", 64, 128, active=True, formatter=_BIPOL,
              doc="a tilt after the saturator in every mode: 64 flat, 127 bright, 0 dark"),
        # MIX on page 1 since 16 Sep 2026 (Sam's knob pass); TONE back beside it 20 Sep.
        Param(b"MIX", 127, active=True, formatter=_PLAIN,
              doc="dry/wet across the whole chain; 0 = exact passthrough"),
        # ---- page 2, filled from the top left: SAT (the mode, slot 6 as on
        # every effect), WDTH ------------------------------------------------
        Param(b"SAT", 0, 3, active=True, formatter=_STEP,
              labels=("TAPE", "TUBE", "INFL"),
              doc="character: TAPE (TapeHead), TUBE (DaTube, asymmetric), INFL (OInflator). JClones, MIT"),
        Param(b"WDTH", 64, 128, active=True, formatter=_BIPOL,
              doc="mid/side width, drawn -64..+63: 0 = untouched, -64 = mono, +63 = double the sides"),
        _BLANK, _BLANK, _BLANK, _BLANK,
    ),
    # SAT names itself by its value (tools/build/mode_names.with_selfname).
    # No knob changes meaning by mode.
    mode_slot=6,                      # SAT names itself (TAPE / TUBE / INFL)
    dsp=DspSection(
        asm="modules/character/character.asm",
        ptable=TUBE_UP + TAPE_D8 + POCKEY_ENC + POCKEY_DEC,
        priority=13,                  # after the Spectrum station
        bus_role=BusRole.NONE,        # an insert; never on the bus
        ybase=YBase.NEVER,            # an FX1 module may own no buffers; the
                                      # master's payload test reads the
                                      # dispatch table instead
        r7_latch_slot=None,           # never reads the rotation
        gate_label=None,              # no housekeeping: a station never elects
    ),
    # FX1 only: the rig's cycle envelope closes only with the stations on
    # FX1 (four Characters on both slots priced a core at 4,830 against
    # 3,120). The FX2 chooser hides the row; verify_character proves the
    # dry pass.
    claims=Claims(fx1_only=True),
    harness=Harness(layout_char="2", is_server=False, bus_client=False),
)
