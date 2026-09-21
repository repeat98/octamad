"""EUCLID -- a swung, track-clocked filter/amp sequencer."""
import math

from remix.schema import (BusRole, Detour, DspSection, Formatter, Harness,
                          Kind, Linked, MenuEntry, ModeView, Module, Param, YBase)

P, S, W, B = (Formatter.PLAIN, Formatter.STEPPED,
              Formatter.WIDE_STEPPED, Formatter.BIPOLAR)
# Spectrum's TPT SVF coefficient convention: g/2, logarithmic 30 Hz..15 kHz.
G2 = tuple(round(math.tan(math.pi * 30 * 500 ** (i / 32) / 44100) * (1 << 22))
           for i in range(33))
MODULE = Module(
    name="euclid", key="EUCLID", kind=Kind.HYBRID,
    doc="Euclidean LP/BP/HP/amp sequencer: swing, envelope, gate, random and loop.",
    menu=MenuEntry(fx2_id=0x1d, donor_desc=0x400d58b8,
                   abbr=b"EUCL", fullname=b"Euclid"),
    params=(
        Param(b"FREQ", 48, 128, True, P, doc="Base filter cutoff or AMP level; cutoff is 30 Hz..15 kHz logarithmic"),
        Param(b"RES", 48, 128, True, P, doc="Filter resonance; inert for AMP"),
        Param(b"DEPTH", 100, 128, True, B, doc="Cutoff or gain modulation: negative/down, zero/static, positive/up"),
        Param(b"DECAY", 48, 128, True, P, doc="Envelope decay up to eight steps / gate length; inert for random"),
        Param(b"STEPS", 15, 64, True, W, labels=tuple(str(i) for i in range(1, 65)),
              doc="Euclidean cycle length 1..64 (stored as length minus one)"),
        Param(b"PULSE", 5, 65, True, W, labels=tuple(str(i) for i in range(65)),
              doc="Pulse count; values above STEPS are clamped to STEPS"),
        Param(b"ROT", 0, 64, True, W, labels=tuple(str(i) for i in range(64)),
              doc="Shift rhythm and captured values right, modulo STEPS"),
        Param(b"RATE", 1, 5, True, S, labels=("1/32", "1/16", "1/8", "1/4", "1/2"),
              doc="Division relative to the track speed; 1/16 = one track step"),
        Param(b"TYPE", 0, 4, True, S, labels=("LP", "BP", "HP", "AMP"),
              doc="Two-pole filter response, or amplitude modulation"),
        Param(b"ATTACK", 0, 128, True, P, doc="Attack / gate edge / random slew, 0..one step"),
        Param(b"OUTPUT", 0, 4, True, S, labels=("ENV", "GATE", "RAND", "LOOP"),
              doc="Pulse envelope, timed gate, random sample-and-hold, captured random"),
        Param(b"MIX", 127, 128, True, P, doc="Dry/wet; zero is exact passthrough"),
    ),
    mode_slot=10,
    mode_views=(
        ModeView(0, names={3: b"DEC", 9: b"ATK"}),
        ModeView(1, names={3: b"LEN", 9: b"EDGE"}),
        ModeView(2, names={3: b"--", 9: b"SLEW"}),
        ModeView(3, names={3: b"--", 9: b"SLEW"}),
    ),
    dsp=DspSection(asm="modules/euclid/filter.asm", priority=16,
                   bus_role=BusRole.NONE, ybase=YBase.NEVER, ptable=G2),
    linked=(Linked("euclid", "modules/euclid/control.s", cpu="5475", dram=True),),
    detours=(
        Detour(0x4000d562, bytes.fromhex("43f9800000f0"), "euclid", "eu_frame_hook",
               "Publish Euclid's cutoff after the final scene and LFO writes"),
        Detour(0x4009c3d4, bytes.fromhex("23c0800065b8"), "euclid", "eu_start_hook",
               "Reset Euclidean phase at the stock PLAY anchor"),
        Detour(0x4009c4d4, bytes.fromhex("23c0800065b8"), "euclid", "eu_resume_hook",
               "Reset Euclidean phase on the second PLAY path"),
    ),
    harness=Harness(layout_char="Q", is_server=False),
)
