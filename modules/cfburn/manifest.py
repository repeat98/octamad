"""CF BURN -- a ColdFire cycle-burn knob, the CPU twin of the DSP rig burn.

An FX2 effect with no sound of its own (the DSP side is a passthrough; the
stock delay routine treats the id as "no delay", as it does every id but 8).
Its ColdFire hook sits at the end of the stock eight-track delay routine,
0x40003826, which runs at IPL 5 inside the ColdFire->DSP transfer interrupt
(docs/firmware/OPTIMIZATION_LEVERS.md 1): the same budget as the frame ISR
and every ColdFire effect. It spins a register-only loop whose length is
set by this effect's two page-1 knobs, summed over every track that carries
it:

    iterations = sum over CF BURN tracks of (BURN * 64 + FINE)
    one iteration = 10 instructions (8 register adds, subq, bne)

So BURN is 640 instructions per step and FINE 10. Sweep BURN on the unit
until the audio breaks, back off one step, then sweep FINE: the setting is
the spare level-5 CPU in that project, in a register-only loop whose
cycles per instruction is near 1 on the V4e (inferred, not measured).
verify_cfburn.py proves the hook inert (every SRAM word, ring, audio buffer
and returned register identical to stock) and the step exact under the
ColdFire port. No hardware sweep has been run yet.
"""

from remix.schema import (BusRole, Detour, DspSection, Formatter, Harness, Kind,
                          Linked, MenuEntry, Module, Param, YBase)

ID = 0x1f            # burn.s carries the same value (CFBURN_ID); the gate checks both
STEP = 64            # iterations per BURN step (burn.s: lsl #6)
BODY = 10            # instructions per iteration (burn.s: .rept 8 add + subq + bne)

MODULE = Module(
    name="cfburn",
    key="CF BURN",
    kind=Kind.HYBRID,
    doc="ColdFire cycle-burn knob in the stock delay routine: measures spare level-5 CPU.",
    menu=MenuEntry(
        fx2_id=ID,
        donor_desc=0x400d58b8,        # DARK REV, as HELLO WORLD
        abbr=b"CPUB",
        fullname=b"CF BURN",
        build_tag=False,
    ),
    params=(
        Param(b"BURN", 0, 128, active=True, formatter=Formatter.PLAIN,
              doc="coarse: 64 loop iterations (640 instructions) per step, summed over tracks"),
        Param(b"FINE", 0, 128, active=True, formatter=Formatter.PLAIN,
              doc="fine: one loop iteration (10 instructions) per step"),
        Param(), Param(), Param(), Param(),
        Param(), Param(), Param(), Param(), Param(), Param(),
    ),
    dsp=DspSection(
        asm="modules/cfburn/passthrough.asm",
        priority=17,
        bus_role=BusRole.NONE,
        ybase=YBase.NEVER,
        r7_latch_slot=None,
        gate_label=None,
    ),
    linked=(Linked("cfburn", "modules/cfburn/burn.s", cpu="5475"),),
    detours=(Detour(0x40003826, bytes.fromhex("45ef00747203"),
                    "cfburn", "cfburn_hook",
                    "CF BURN: knob-set spin at the end of the stock delay routine (IPL 5)"),),
    harness=Harness(layout_char=None, is_server=False),
)
