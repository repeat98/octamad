"""OXIDE -- tape: UADx Oxide's headroom, saturation and head bump, modelled.

A stereo insert (no bus, no buffers) that reproduces the Oxide Tape
Recorder plugin at 15 IPS / NAB / Repro closely enough to stand in for it
on a mix: the bass driven into the curve first, a ceiling at ~0.91 of full
scale, the +4.7 dB head bump at 30 Hz, the gentle top lift, and the
plugin's low-frequency phase, which is what sets the peaks of a kick.
Built to go on the master once there is a post-mix insert point; until
then it runs on any track.

The model, its fit and its accuracy are in design.py; the measurement
tooling (it needs the plugin installed) in fit/. The DSP code is held to
design.fixed() at 0 LSB by tools/verify/verify_oxide.py.
"""

import importlib.util as _iu
import pathlib as _pl

from remix.schema import (BusRole, DspSection, Formatter, Harness, Kind,
                          MenuEntry, Module, Param, YBase)

_spec = _iu.spec_from_file_location("oxide_design", _pl.Path(__file__).with_name("design.py"))
design = _iu.module_from_spec(_spec)
_spec.loader.exec_module(design)

MODULE = Module(
    name="oxide",
    key="OXIDE",
    kind=Kind.DSP_EFFECT,
    doc="Tape: UADx Oxide's headroom, saturation and head bump, modelled (15 IPS NAB).",
    menu=MenuEntry(
        # 0x1e is claimed on the machinedrum and analog-bassdrum branches.
        fx2_id=0x1f,
        donor_desc=0x400d58b8,        # DARK REV
        abbr=b"OXID",                 # <=4 chars: the 5-byte field keeps its NUL
        fullname=b"Oxide Tape",       # 10 of 13 bytes
        build_tag=False,
    ),
    params=(
        # ---- page 1 ---------------------------------------------------------
        Param(b"IN", design.IN_ZERO, 128, active=True, formatter=Formatter.PLAIN,
              doc="drive into the tape, 0.3 dB a step: 48 = 0 dB (the plugin's), 0 = -14.4, 127 = +23.7"),
        Param(b"OUT", design.OUT_ZERO, 128, active=True, formatter=Formatter.PLAIN,
              doc="output level, 0.3 dB a step: 80 = 0 dB, 0 = -24, 127 = +14.1"),
        Param(), Param(), Param(), Param(),
        # ---- page 2: none -----------------------------------------------------
        Param(), Param(), Param(), Param(), Param(), Param(),
    ),
    dsp=DspSection(
        asm="modules/oxide/oxide.asm",
        # the curve (VT, ST: 32 segments each), then the IN and OUT tables
        ptable=design.ptable(),
        priority=41,                  # byte-load-bearing
        bus_role=BusRole.NONE,
        ybase=YBase.NEVER,            # no absolute Y anywhere in the source
        r7_latch_slot=None,
        gate_label=None,
    ),
    harness=Harness(layout_char="8", is_server=False, bus_client=False),
)
