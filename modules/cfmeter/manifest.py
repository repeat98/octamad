"""CF METER -- a probe: the frame interrupt's duration (and, with CF METER
IDLE, the ColdFire's idle time) on the unit, read out as audio from track 8.

The ColdFire unit (`meter.s`, DRAM) wraps the frame interrupt (vector 0x41:
main's install names `m_isr` instead of the stock handler) with an entry
stamp on DMA timer 3 and a BURN of 2 us per step, and replaces the
handler's epilogue with an exit stamp and the publisher. Every 125 ms the
publisher writes one of eight values into track 8's FX2 page-2 lane,
beside a fixed reference; the DSP insert (`meter_out.asm`) on T8's FX2
prints both as a square wave. `tools/harness/cfmeter.py` decodes a
capture. README.md has the procedure.
"""

from remix.schema import (BusRole, Category, Detour, DspSection, Formatter, Harness, Kind,
                          Linked, MenuEntry, Module, Param, Proof, YBase)

_BLANK = Param(b"", None, active=False)

MODULE = Module(
    name="cfmeter",
    key="CF METER",
    kind=Kind.HYBRID,
    category=Category.REFERENCE, author="sambanks", author_url="https://github.com/sambanks",
    proof=Proof.PORT, proof_note="the readout chain and the interrupt timing under the port; the numbers need the unit",
    doc="Probe: frame-interrupt duration and (with CF METER IDLE) idle time, printed as audio on T8's FX2.",
    menu=MenuEntry(
        fx2_id=0x0e,
        donor_desc=0x400d4772,        # FILTER
        abbr=b"CFMT",
        fullname=b"CF Meter",
        build_tag=False,
    ),
    params=(
        Param(b"BURN", 0, active=True, formatter=Formatter.PLAIN,
              doc="read on track 8 only: 2 us of busy-wait per step at the start of every frame interrupt"),
        _BLANK, _BLANK, _BLANK, _BLANK, _BLANK,
        _BLANK, _BLANK, _BLANK, _BLANK, _BLANK, _BLANK,
    ),
    dsp=DspSection(
        asm="modules/cfmeter/meter_out.asm",
        priority=15,
        bus_role=BusRole.NONE,
        ybase=YBase.NEVER,
        r7_latch_slot=None,
        gate_label=None,
    ),
    linked=(Linked("cfmeter", "modules/cfmeter/meter.s", dram=True),),
    detours=(
        Detour(0x4001fbf8, bytes.fromhex("48794000aad0"), "cfmeter", "m_isr",
               "main's install of vector 0x41 (the frame interrupt): pea m_isr", kind="lea"),
        Detour(0x4000d9a6, bytes.fromhex("4cd77fff4fef00fc4e73"), "cfmeter", "m_tail",
               "the frame interrupt's epilogue, every exit path: the exit stamp", pad_to=10),
    ),
    harness=Harness(layout_char=None, is_server=False),
)
