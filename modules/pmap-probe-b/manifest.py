"""PMAP PROBE B -- the 16K program map probe on core 1 (payload B).

The same source as PMAP PROBE (modules/pmap-probe/probe.asm): the boot's map
switch and test, and `report` at the frame's end (P:0x333), which copies the
verdict to the top of core 1's shared half every frame for core 0's tone.
"""

import runpy
from pathlib import Path

from remix.schema import Category, DspHook, DspSection, Kind, Module, Proof

BOOT = runpy.run_path(str(Path(__file__).parent.parent / "pmap-probe/manifest.py"))["BOOT"]

MODULE = Module(
    name="pmap-probe-b", key="PMAP PROBE B", kind=Kind.DSP_EFFECT,
    category=Category.REFERENCE, author="repeat98", author_url="https://github.com/repeat98",
    proof=Proof.CHECK, proof_note="see PMAP PROBE",
    doc="Hardware probe, core 1: the 16K program map switch and test, the verdict reported to core 0.",
    dsp=DspSection(
        asm="modules/pmap-probe/probe.asm", priority=0, payloads=frozenset({"B"}),
        hooks=(BOOT, DspHook(0x333, (0x56f000, 0x000415), "report",
                             "the frame's end: the verdict to the shared window for core 0")),
    ),
    requires=("PMAP PROBE",),
)
