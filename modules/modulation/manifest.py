"""MODULATION -- a modulation pedal, five modes, on stock CHORUS's id 0x12.

A per-track insert (FX1 only). Each mode transcribes a published,
permissively licensed source (survey and licences: docs/effects/PORTS.md;
the float reference the DSP is proven against: modulation_ref.py):

    JUNO  the Juno-60 chorus (jpcima HeraChorus.dsp, ISC + the Juno-60
          measurements): two BBD lines on one triangle LFO, R inverted;
          I 0.513 Hz / II 0.863 Hz over 1.5..5.4 ms
    DIM   the Roland Dimension D (SDD-320): antiphase lines, cross-mixed
          through a highpass, a bass lift on the dry; 0.25 / 0.5 Hz, 5..12
          ms. The amounts are unpublished: ours
    FLNG  Dattorro's flanger (JAES 1997, Table 6): through-zero, the dry
          read from the sweep's centre, feedforward and feedback -0.7071
    COMB  Rings' string loop (Mutable Instruments, MIT): Hermite-read,
          FIR damping, the per-pass gain from a decay TIME so every pitch
          rings for the same time; FDBK's sign = the polarity (ours)
    PHSR  ChowPhaser (BSD-3), the Schulte Compact Phasing A: a feedback
          section of two RC allpasses, then 2/4/6/8 allpasses on the LDR's
          law. Last in the select so dropping it moves no stored byte

FX1 only, enforced by the module: it needs a per-track delay line, and
beside the servers the only free per-track buffer is the FX1 slot. It reads
its base from the host's bump allocator at init (docs/firmware/DSP.md
section 10); if that base is an FX2 slot (>= 0x4000) it runs as a dry pass
and writes nothing. `Claims(fx1_only=True)` declares that and the render
gate proves it. Two lines of 1,024 words out of the 3,072 an FX1 slot
gives; the read offset is masked, not the address.

Not a bus client: does not housekeep, does not write the bus."""

from remix.schema import (BusRole, Claims, DspSection, Formatter, Harness,
                          Kind, MenuEntry, ModeView, Module, Param, YBase)

_PLAIN = Formatter.PLAIN
_STEP = Formatter.STEPPED
_BIPOL = Formatter.BIPOLAR   # drawn -64..+63 around 64

_BLANK = Param(b"", 0)

# The P tables (modulation_ref.py generates them; 33 words each, read at
# idx = u >> 18 and interpolated on the 18 bits under it):
#   PHSR_MOD  ChowPhaser's mod-stage allpass coefficient b0 = (RCK-1)/(RCK+1)
#             over lfo = -1..1, R = 100k (light/0.1)^-0.75, light = 20.1 -
#             20 lfo, C = 25 nF, K = 2 fs
#   PHSR_FB   the same for the feedback stages, C = 15 nF
#   PERIOD    COMB's period in Q11.12 samples: 1,000 .. 8, exponential
#   POW2      T(u) = 2^(-8u): COMB's decay (rt60 and the per-pass gain)
PHSR_MOD = (
    0x360688, 0x3744bd, 0x3889f1, 0x39d676, 0x3b2aa0, 0x3c86cc,
    0x3deb5e, 0x3f58c2, 0x40cf6e, 0x424fe1, 0x43daa7, 0x457059,
    0x4711a0, 0x48bf36, 0x4a79ea, 0x4c42a4, 0x4e1a68, 0x50025e,
    0x51fbd5, 0x540850, 0x562990, 0x5861a6, 0x5ab307, 0x5d20ad,
    0x5fae47, 0x62607b, 0x653d5b, 0x684d26, 0x6b9ba8, 0x6f3b29,
    0x734baa, 0x78138a, 0x7ed820,
    )
PHSR_FB = (
    0x189fb0, 0x1a158e, 0x1b95c1, 0x1d20d0, 0x1eb74e, 0x2059d8,
    0x220919, 0x23c5cd, 0x2590be, 0x276acc, 0x2954eb, 0x2b5028,
    0x2d5dad, 0x2f7ec6, 0x31b4e5, 0x3401a8, 0x3666e3, 0x38e6ac,
    0x3b8364, 0x3e3fca, 0x411f11, 0x442501, 0x47561b, 0x4ab7d6,
    0x4e50f4, 0x522a00, 0x564e1b, 0x5acc56, 0x5fba2a, 0x6538a3,
    0x6b8108, 0x730f94, 0x7e145b,
    )
PERIOD = (
    0x3e8000, 0x35bf26, 0x2e3822, 0x27bf02, 0x222df7, 0x1d6481,
    0x1946ac, 0x15bc6f, 0x12b11e, 0x1012f2, 0x0dd2a2, 0x0be309,
    0x0a38d9, 0x08ca5a, 0x078f2f, 0x068027, 0x059715, 0x04cea8,
    0x04224c, 0x038e15, 0x030e9f, 0x02a103, 0x0242c1, 0x01f1b3,
    0x01abfe, 0x01700d, 0x013c81, 0x01102d, 0x00ea0f, 0x00c947,
    0x00ad17, 0x0094d9, 0x008000,
    )
# LOFI's bit mask by k >> 3: 24 bits below 64, then 16 12 10 9 8 7 6 5
LOFI_BITS = (24, 24, 24, 24, 24, 24, 24, 24, 16, 12, 10, 9, 8, 7, 6, 5)
LOFI_MASK = tuple((0xffffff << (24 - b)) & 0xffffff for b in LOFI_BITS)
POW2 = (
    0x7fffff, 0x6ba27e, 0x5a827a, 0x4c1bf8, 0x400000, 0x35d13f,
    0x2d413d, 0x260dfc, 0x200000, 0x1ae8a0, 0x16a09e, 0x1306fe,
    0x100000, 0x0d7450, 0x0b504f, 0x09837f, 0x080000, 0x06ba28,
    0x05a828, 0x04c1c0, 0x040000, 0x035d14, 0x02d414, 0x0260e0,
    0x020000, 0x01ae8a, 0x016a0a, 0x013070, 0x010000, 0x00d745,
    0x00b505, 0x009838, 0x008000,
    )

MODULE = Module(
    name="modulation",
    key="MODULATION",
    kind=Kind.DSP_EFFECT,
    doc="BamSep26 station: a modulation pedal -- Juno, Dimension, flanger, phaser, comb; FX1 only.",
    menu=MenuEntry(
        fx2_id=0x12,
        replaces="CHORUS",
        donor_desc=0x400d58b8,        # DARK REV: 12 active slots, selects 7/9/11
        abbr=b"MODU",
        fullname=b"Modulation",
        build_tag=True,
    ),
    params=(
        # ---- page 1 (16 Sep 2026): the sweep's three knobs together, RATE
        # and DPTH drawn as a linked pair; LOFI, then MIX bottom right.
        Param(b"RATE", 26, active=True, formatter=_PLAIN,
              doc="LFO speed, 0.08 .. 10 Hz on a squared taper (26 = the Juno's 0.5 Hz)"),
        Param(b"DPTH", 21, active=True, formatter=_PLAIN, link=True,
              doc="the sweep, 0 .. 480 samples either side of DLY; in PHSR the LFO's reach"),
        Param(b"DLY", 18, active=True, formatter=_PLAIN,
              doc="the sweep's centre, 0.2 .. 23 ms; COMB's pitch; PHSR's stage count (2/4/6/8 by quarters)"),
        Param(b"FDBK", 64, 128, active=True, formatter=_BIPOL,
              doc="bipolar, 64 = none: feedback from the swept tap; PHSR regen; COMB decay time and polarity"),
        Param(b"LOFI", 0, active=True, formatter=_PLAIN,
              doc="the line clocked coarse and quantised: hold 1 + 64 (k/128)^2 samples, 24 bits then 16..5"),
        # MIX bottom right, as on every effect (Sam, image 29)
        Param(b"MIX", 0, active=True, formatter=_PLAIN,
              doc="dry/wet; 0 = exact passthrough, 127 = the wet alone"),
        # ---- page 2, filled from the top left: MODE (slot 6 as on every
        # effect), TONE, WDTH ----------------------------------------------
        Param(b"MODE", 0, 5, active=True, formatter=_STEP,
              labels=("JUNO", "DIM", "FLNG", "COMB", "PHSR"),
              doc="which pedal"),
        Param(b"TONE", 80, 128, active=True, formatter=_PLAIN,
              doc="the BBD filters in and out of the line: 0 dark (2 kHz), 127 open; COMB brightness; no PHSR"),
        Param(b"WDTH", 127, 128, active=True, formatter=_PLAIN,
              doc="the right channel LFO lag: 0 mono, 64 quadrature, 127 antiphase (Juno, DIM); not COMB"),
        _BLANK, _BLANK, _BLANK,
    ),
    # ---- what each MODE renames and re-defaults ---------------------------
    # The defaults are each source's own numbers: the Juno's I (0.513 Hz,
    # +-1.8 ms about 3.35 ms, antiphase, dry 0.83 + wet 1.0 ~ MIX 70), the
    # Dimension's mode 1 (0.25 Hz, 5..12 ms),
    # Dattorro's flanger (0..10 ms; his 0.15 Hz slowed to 0.12 by ear), ChowPhaser's defaults (4 Hz,
    # depth 0.95 -> 121, 8 stages), Rings at a mid pitch with a 2 s ring.
    mode_slot=6,
    mode_views=(
        ModeView(mode=0,                        # JUNO
                 defaults={0: 26, 1: 21, 2: 18, 3: 64, 5: 70, 7: 80, 8: 127}),
        ModeView(mode=1,                        # DIM
                 defaults={0: 18, 1: 41, 2: 47, 3: 64, 5: 127, 7: 80, 8: 127}),
        ModeView(mode=2,                        # FLNG
                 names={2: b"MANL"},
                 defaults={0: 8, 1: 59, 2: 27, 3: 19, 5: 127, 7: 127, 8: 0}),   # RATE 8 = 0.12 Hz (Sam, 16 Sep: 14 too fast)
        ModeView(mode=3,                        # COMB: no LFO (RATE DPTH WDTH `---`)
                 names={0: b"---", 1: b"---", 3: b"DCAY", 2: b"PTCH", 7: b"BRIT", 8: b"---"},   # TONE = the FIR's brightness
                 defaults={0: 0, 1: 0, 2: 64, 3: 82, 5: 64, 7: 100, 8: 0}),   # FDBK 82: rt60 ~ 1 s
        ModeView(mode=4,                        # PHSR (last: dropping it
                 names={2: b"STGS", 7: b"---"},  # would move no other mode); no line filter: TONE `---`
                 defaults={0: 28, 1: 121, 2: 127, 3: 64, 5: 64, 7: 127, 8: 64}),
    ),
    dsp=DspSection(
        asm="modules/modulation/modulation.asm",
        ptable=PHSR_MOD + PHSR_FB + PERIOD + POW2 + LOFI_MASK,
        priority=14,                  # after the Character station
        bus_role=BusRole.NONE,        # an insert; it writes nothing to the bus
        ybase=YBase.NEVER,
        r7_latch_slot=None,           # no ROTLATCH/ROTINIT: not a bus client
        gate_label=None,              # no housekeeping: a station never elects
    ),
    # Two 1,024-word lines out of the 3,072 an FX1 slot gives. `fx1_only`
    # is the promise that an FX2 instance writes nothing; the ledger admits
    # it beside a server on that basis and verify_modulation proves it.
    claims=Claims(stock_instance_buffer=True, buffer_words=2048, fx1_only=True),
    harness=Harness(layout_char="3", is_server=False, bus_client=False),
)
