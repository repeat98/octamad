"""Gloam -- a small four-line FDN insert, replacing stock DARK REV.

A per-track insert on DARK REV's id 0x16 (FX2-only on stock -- the three
reverbs are never on the FX1 chooser, so none of the FX1-buffer-size hazard
in MenuEntry.replaces applies here). Structurally closer to Airwindows'
VerbTiny (a small Hadamard-butterflied delay network, no per-line
modulation) than to this repo's own BusVerb: no LFO, no interpolation, no
input diffuser, no shimmer, four fixed-tap 4096-word lines instead of eight
modulated ones -- deliberately smaller and cheaper, since it is standing in
for a per-track stock effect that four tracks on a core can select at once,
not a once-per-bank server.

  * Four lines, 4096 words each (93 ms), fixed taps (no size knob, no
    modulation -- the taps are compile-time constants chosen to be mutually
    non-simple-ratio so the un-modulated tank does not ring on one pitch).
  * Each line: read the old tap, one-pole damp it (DAMP), scale by DECAY,
    feed all four through a 4x4 Hadamard butterfly (two sum/difference
    stages, normalised by one right shift), inject the pre-delayed mono
    input with alternating sign, write back.
  * Two of the four post-Hadamard rows feed WET L/R directly (two
    orthogonal rows of the same transform -- decorrelated for free, no
    separate wet-sum stage).
  * A short pre-delay line (2048 words) ahead of the tank; PRE picks the
    read-back offset, 0..~46 ms.
  * WIDTH blends wet L/R toward their mono sum; MIX crossfades dry/wet.

One Gloam per core: the buffer is the fixed core-private FX2-instance
region Y:0x4000-0x87FF (18,432 of the 32,768 words available), the same
region BusVerb's tank and Nimbus's line use -- the three cannot share a
core. MIX=0 is an exact passthrough (during warm-up the effect outputs
pure dry).
"""

from remix.schema import (BusRole, Claims, DspSection, Formatter, Harness,
                          Kind, MenuEntry, Module, Param, YBase)

_PLAIN = Formatter.PLAIN

MODULE = Module(
    name="gloamverb",
    key="GLOAMVERB",
    kind=Kind.DSP_EFFECT,
    doc="Small four-line Hadamard FDN insert, replacing stock DARK REV.",
    menu=MenuEntry(
        fx2_id=0x16,
        replaces="DARK REV",
        donor_desc=0x400d58b8,        # DARK REV: cloning itself, 12 active slots
        abbr=b"GLOM",
        fullname=b"Gloam Verb",
        build_tag=True,
    ),
    params=(
        # ---- page 1 ---------------------------------------------------------
        Param(b"DECAY", 90, active=True, formatter=_PLAIN,
              doc="feedback per pass through the tank; 0 = one slap, 127 = near-infinite tail"),
        Param(b"DAMP", 40, active=True, formatter=_PLAIN,
              doc="one-pole damping in the feedback path; 0 = darkest, 127 = brightest"),
        Param(b"PRE", 0, active=True, formatter=_PLAIN,
              doc="pre-delay before the tank, 0..~46 ms"),
        Param(b"MIX", 48, active=True, formatter=_PLAIN,
              doc="dry/wet across the tank; 0 = exact passthrough"),
        Param(), Param(),
        # ---- page 2 -----------------------------------------------------------
        Param(b"WIDTH", 100, active=True, formatter=_PLAIN,
              doc="stereo width of the wet signal; 0 = mono fold, 127 = full width"),
        Param(), Param(), Param(), Param(), Param(),
    ),
    dsp=DspSection(
        asm="modules/gloamverb/gloamverb.asm",
        priority=15,                  # after modulation
        bus_role=BusRole.NONE,
        ybase=YBase.NEVER,            # the buffer is core-private Y, no $30000
        r7_latch_slot=None,
        gate_label=None,
    ),
    # The four lines + pre-delay are hardcoded into Y:0x4000-0x87FF, inside
    # the per-core region BusVerb's tank and Nimbus's line also use.
    claims=Claims(owns_fx2_buffers=True),
    harness=Harness(layout_char="Q", is_server=False),
)
