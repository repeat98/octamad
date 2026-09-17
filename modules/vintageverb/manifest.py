"""Vintage Verb -- a Freeverb-lineage reverb replacing stock DARK REV.

A per-track insert on DARK REV's id 0x16 (FX2-only on stock, so none of the
FX1-buffer-size hazard in MenuEntry.replaces applies). Inspired by
stancsz/fnd-reverb-vst3 (github.com/stancsz/fnd-reverb-vst3), whose own
"reverb core" is JUCE's stock `dsp::Reverb` -- itself Jezar's Freeverb: eight
parallel damped comb filters per channel summed into four series allpass
filters -- wrapped in a pre-delay and a chorus ("WARP") stage ahead of the
tank. This module is not a port of that C++ (JUCE's float DSP classes don't
exist here), but the same lineage, sized down and reimplemented in this
project's own fixed-point idioms:

  * SIX comb filters per channel (not eight -- CPU budget; Jezar's own first
    six tunings, 1116/1188/1277/1356/1422/1491 samples, the right channel
    offset +23 each for stereo spread, exactly as Freeverb does), each with
    a one-pole damping filter INSIDE the feedback loop (the classic
    Freeverb topology: read the old tap, low-pass it, scale by DECAY, add
    the input, write back) -- the same one-pole idiom this repo's own
    BusVerb and the previous GloamVerb used, just simpler addressing (one
    pointer per line, no separate read/write offsets, since a comb filter
    reads and writes the SAME cell each sample).
  * THREE series allpass filters per channel (not four), Schroeder's
    classic form (fixed feedback g=0.5): output = bufout - g*input;
    buffer[p] = input + g*output.
  * A pre-delay line (2048 words, PRE 0..~46 ms) and a WARP stage -- one
    small modulated (integer, non-interpolated) delay per channel, a shared
    triangle LFO (nimbus's `mpy phase,mult` + `abs` idiom, ~1.3 Hz, fixed
    rate) with a half-period phase offset between L/R for width -- ahead of
    the tank, for the chorused "vintage" movement the reference's own WARP
    knob is named for.
  * Comb write pointers wrap via compare + `tge` (Jezar's tunings are NOT
    powers of two, so AND-masking -- this repo's usual idiom -- cannot wrap
    them; `move #>LEN,x0 / cmp x0,a / move #>0,x0 / tge x0,a` is the exact
    pattern `modules/modulation/modulation.asm` already uses for a clamp,
    reused here for a wrap. Verified against CLAUDE.md's Tcc-sharing trap:
    the plain `move #>0,x0` between `cmp` and `tge` does not disturb the
    condition codes, so this is the SAME single-compare pattern, not a
    shared one).

One Vintage Verb per core: the buffer is the fixed core-private
FX2-instance region Y:0x4000-0x9851 (22,610 of the 32,768 words available),
the same ground BusVerb's tank, Nimbus's line and the previous GloamVerb
used. MIX=0 is an exact passthrough (during warm-up the effect outputs pure
dry).
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
    # The comb/allpass banks, warp lines and pre-delay are hardcoded into
    # Y:0x4000-0x9851, inside the per-core region BusVerb's tank and
    # Nimbus's line also use.
    claims=Claims(owns_fx2_buffers=True),
    harness=Harness(layout_char="Q", is_server=False),
)
