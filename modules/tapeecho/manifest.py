"""Tape Echo -- a lean three-head tape delay replacing stock SPRING REV.

This is a DSP56300 reimplementation of the useful core of the custom
Space-Echo-inspired implementation in DJ-Mixer's ``fx-dsp`` project.  It
keeps the parts that define the instrument on the Octatrack:

* one mono tape loop, read by three unevenly-spaced playback heads;
* a low-pass filtered, saturating feedback write path;
* a slow tape-speed wow LFO shared by the heads; and
* optional tempo-quantised repeat time, using the stock tempo24 word already
  present in each FX2 track record, with shared motor inertia in both modes.

The desktop source's full transport model, separate flutter oscillators,
pre/de-emphasis biquads, head-bump filters, hiss and dropouts are intentionally
not copied.  They would turn a compact insert into an
unsafe four-times-per-core DSP load.  The fixed feedback low-pass is the
remaining tape voicing, so there is deliberately no separate TONE control.

The three original head ratios (1.0, 1.97, 2.96) require the whole fixed
FX2 line.  At the slow end, the first head is bounded to 11,000 samples so
the third head and ±8-sample wow always remain inside Y:0x4000..0xBFFF.
"""

from remix.schema import (BusRole, Claims, DspSection, Formatter, Harness,
                          Kind, MenuEntry, Module, Param, YBase)

_PLAIN = Formatter.PLAIN
_STEP = Formatter.STEPPED

MODULE = Module(
    name="tapeecho",
    key="TAPE ECHO",
    kind=Kind.DSP_EFFECT,
    doc="Three-head tape echo: filtered feedback, wow and optional beat sync.",
    menu=MenuEntry(
        fx2_id=0x15,
        replaces="SPRING REV",
        donor_desc=0x400d5726,        # SPRING REV: all twelve descriptor slots
        abbr=b"TAPE",
        fullname=b"Tape Echo",
        build_tag=False,
    ),
    params=(
        # ---- page 1: live performance surface ---------------------------
        Param(b"TIME", 64, active=True, formatter=_PLAIN,
              doc="free: 46..231 ms; SYNC: 1/64..1/8 divisions, bounded by the tape"),
        Param(b"FDBK", 64, active=True, formatter=_PLAIN,
              doc="repeat intensity; tape softening plus a final limiter keep the loop bounded"),
        Param(b"WOW", 25, active=True, formatter=_PLAIN,
              doc="slow shared tape-speed wobble; 0 is a static repeat"),
        Param(b"HEADS", 4, 7, active=True, formatter=_STEP,
              labels=("1", "2", "3", "1+2", "2+3", "1+3", "1+2+3"),
              doc="active playback heads; the selected heads are level-normalised"),
        Param(b"SYNC", 0, 2, active=True, formatter=_STEP,
              labels=("FREE", "BEAT"),
              doc="FREE uses milliseconds; BEAT quantises TIME from stock tempo"),
        Param(b"MIX", 90, active=True, formatter=_PLAIN,
              doc="dry/wet crossfade; 0 is exact passthrough"),
        # ---- detail/setup page (stock effect page 2) ---------------------
        Param(b"DRIVE", 64, 128, active=True, formatter=_PLAIN,
              doc="record-curve strength; 0 is clean, 127 gives the softest overload"),
        Param(b"AGE", 64, 128, active=True, formatter=_PLAIN,
              doc="repeat bandwidth; 0 is fresh and bright, 127 is worn and dark"),
        Param(), Param(), Param(), Param(),
    ),
    dsp=DspSection(
        asm="modules/tapeecho/tape_echo.asm",
        priority=14,
        bus_role=BusRole.NONE,
        ybase=YBase.NEVER,
        r7_latch_slot=None,
        gate_label=None,
    ),
    # One instance owns the sole core-private FX2 delay line.  It cannot
    # coexist on a core with BusVerb, BusDelay, Nimbus or a buffer-writing
    # stock FX2 effect.
    claims=Claims(owns_fx2_buffers=True),
    harness=Harness(layout_char="X", is_server=False),
)
