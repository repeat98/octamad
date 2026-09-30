"""PMAP PROBE -- does the DSP56720 run the 16K program map on the unit?

A hardware probe, one flash (docs/firmware/CHIP.md section 3; the question
behind dynamic DSP loading's memory plan). Each core's boot (P:0x40, before
anything touches Y) sets OMR MS with MSW1:MSW0 = 11 (16K P, 36K X, 40K Y),
writes and reads back all 8K new program words (0x2000..0x3FFF) with two
patterns, copies a routine to P:0x3F00 and calls it, and keeps a verdict;
the boot's Y zeroing is shortened to stop at 0x9FFF, the new Y ceiling. The
verdicts are heard on MAIN: left core 0, right core 1; 882 Hz pass, 110 Hz
fail, no tone no report (and no audio at all: the switch wedged the core).

Core 0 here (payload A: boot and the tone at P:0x2d5); PMAP PROBE B is core 1
(boot and the report at P:0x333, the frame's end). The ColdFire port's DSP
emulator does not model the memory switch (the vendored dsp.cpp has OMR MS
handling commented out), so under the port both cores pass by construction:
the port proves the probe's plumbing, never its answer.
"""

from remix.schema import Category, DspHook, DspSection, Gate, Kind, Module, Proof

BOOT = DspHook(0x40, (0x57f400, 0x008000), "boot",
               "the first instruction after the upload: the map switch and the test, before Y is touched")

MODULE = Module(
    name="pmap-probe", key="PMAP PROBE", kind=Kind.DSP_EFFECT,
    category=Category.REFERENCE, author="repeat98", author_url="https://github.com/repeat98",
    proof=Proof.CHECK,
    proof_note="a hardware probe: under the port it passes by construction (the emulator ignores OMR MS); "
               "the unit is the measurement",
    doc="Hardware probe, core 0: switch to the 16K program map at boot, test the new program memory, "
        "play both cores' verdicts on MAIN (L core 0, R core 1; 882 Hz pass, 110 Hz fail).",
    dsp=DspSection(
        asm="modules/pmap-probe/probe.asm", priority=0, payloads=frozenset({"A"}),
        hooks=(BOOT, DspHook(0x2d5, (0x60f000, 0x000206), "tone",
                             "after both mixdown paths: the verdicts added to MAIN")),
    ),
    requires=("PMAP PROBE B",),
    gates=(Gate("tools/verify/verify_pmap_probe.py", remix_arg=False, stage="image"),),
)
