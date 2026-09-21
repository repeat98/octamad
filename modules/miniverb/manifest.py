"""Full-rate, modulated four-branch diffused FDN insert with allocator-owned memory."""
from remix.schema import (BusRole, Claims, DspSection, Formatter, Harness,
                          Kind, MenuEntry, Module, Param, YBase)

MODULE = Module(
    name="miniverb", key="MINIVERB", kind=Kind.DSP_EFFECT,
    doc="Modulated diffused FDN reverb; independent FX2 buffers, smoothed controls.",
    menu=MenuEntry(fx2_id=0x16, replaces="DARK REV", donor_desc=0x400d58b8,
                   abbr=b"MINI", fullname=b"Mini Verb", build_tag=False),
    params=(
        Param(b"DECAY", 104, active=True, formatter=Formatter.PLAIN,
              doc="feedback 0.65..0.97; fixed room size"),
        Param(b"DAMP", 70, active=True, formatter=Formatter.PLAIN,
              doc="higher values darken the tail"),
        Param(b"MIX", 40, active=True, formatter=Formatter.PLAIN,
              doc="dry/wet, smoothed; 0 dry, 127 wet"),
        Param(b"MOD", 80, active=True, formatter=Formatter.PLAIN,
              doc="two in-loop allpasses; smoothed 0..64 sample depth"),
        Param(b"RATE", 2, count=8, active=True, formatter=Formatter.STEPPED,
              labels=("0.34", "0.67", "1.01", "1.35", "1.68", "2.02", "2.36", "2.69"),
              doc="LFO speed: (value+1)*0.33646 Hz, continuous phase"),
        *(Param() for _ in range(7)),
    ),
    dsp=DspSection(asm="modules/miniverb/miniverb.asm", priority=15,
                   bus_role=BusRole.NONE, ybase=YBase.NEVER,
                   r7_latch_slot=None, gate_label=None),
    claims=Claims(stock_instance_buffer=True, buffer_words=16384),
    harness=Harness(layout_char="7", is_server=False),
)
