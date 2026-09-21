"""Vintage Verb -- a Dattorro plate reverb, running at half the audio rate,
replacing stock DARK REV. modules/vintageverb/vintageverb.asm's own header
has the full ground (signal path, the tank's per-line offset table, why
half rate); this module has gone through two earlier structures (v1 was a
Freeverb of six comb filters + three allpasses, scrapped for being 1.6x
stock DARK REV's instruction count with too small a room -- see the
README) -- v3, current, is the Dattorro figure-8 tank.

A per-track insert on DARK REV's id 0x16 (FX2-only on stock, so none of the
FX1-buffer-size hazard in MenuEntry.replaces applies).

Up to FOUR independent instances per core: init reads this FX2 slot's own
16,384-word base from the stock allocator (X:$213, the same mechanism
modules/tapeecho/tape_echo.asm uses), rather than hardcoding the fixed
core-private address a single shared instance used before. Two of the
allocator's four per-core bases ($4000, $8000) are the low core-private
region; the other two are in the cross-core shared window
(docs/firmware/DSP.md section 10) -- Claims.stock_instance_buffer makes the
ledger refuse this module beside BusVerb, BusDelay or Nimbus, which
hardcode those same four addresses. MIX=0 is an exact passthrough (during
warm-up the effect outputs pure dry).
"""

from remix.schema import (BusRole, Claims, DspSection, Formatter, Harness,
                          Kind, MenuEntry, Module, Param, YBase)

_PLAIN = Formatter.PLAIN

MODULE = Module(
    name="vintageverb",
    key="VINTAGEVERB",
    kind=Kind.DSP_EFFECT,
    doc="Dattorro plate insert (diffusers + modulated figure-8 allpass tank), replacing stock DARK REV.",
    menu=MenuEntry(
        fx2_id=0x16,
        replaces="DARK REV",
        donor_desc=0x400d58b8,        # DARK REV: cloning itself, 12 active slots
        abbr=b"VINT",
        fullname=b"Vintage Verb",
        build_tag=False,
    ),
    params=(
        # ---- page 1 ---------------------------------------------------------
        Param(b"DECAY", 100, active=True, formatter=_PLAIN,
              doc="tail length: RT60 ~0.9 s at 40, ~1.5 s at 80, ~2.4 s at 100, ~5.4 s at 127"),
        Param(b"DAMP", 85, active=True, formatter=_PLAIN,
              doc="one-pole HF damping inside the tank loop; 0 = darkest, 127 = brightest"),
        Param(b"WARP", 40, active=True, formatter=_PLAIN,
              doc="tank modulation depth, interpolated, fixed ~1.3 Hz; 0 = static, 127 = ~1 ms"),
        Param(b"PRE", 0, active=True, formatter=_PLAIN,
              doc="pre-delay before the tank, 0..~46 ms"),
        Param(b"MIX", 90, active=True, formatter=_PLAIN,
              doc="dry/wet across the tank; 0 = exact passthrough"),
        Param(),
        # ---- page 2 -----------------------------------------------------------
        Param(b"WIDTH", 100, active=True, formatter=_PLAIN,
              doc="stereo width of the wet signal; 0 = mono fold, 127 = full width"),
        Param(), Param(), Param(), Param(), Param(),
    ),
    dsp=DspSection(
        asm="modules/vintageverb/vintageverb.asm",
        priority=15,                  # after modulation
        bus_role=BusRole.NONE,
        ybase=YBase.NEVER,            # the buffer is core-private Y, no $30000
        r7_latch_slot=None,
        gate_label=None,
    ),
    # An allocator reader: init takes this FX2 slot's own 16,384-word base
    # from X:$213 (vintageverb.asm), so it does not hardcode BusVerb's tank
    # or Nimbus's line's addresses -- but the ledger still refuses it beside
    # them, since they hardcode the same four per-core addresses.
    claims=Claims(stock_instance_buffer=True, buffer_words=16384),
    harness=Harness(layout_char="5", is_server=False),
)
