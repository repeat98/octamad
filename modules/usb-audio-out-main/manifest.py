"""USB AUDIO OUT MAIN -- MAIN L/R alone to the host, two channels.

The DAC feed's MAIN pair at high speed every 250 us (96-byte packets) and at
full speed every 1 ms (360-byte packets), 24-bit in 4-byte subslots, a front
left / front right cluster. USB AUDIO OUT TRACKS MAIN CUE's source
(markandrus/octemu, MIT) assembled with USB_LAYOUT = 4: the producer reads
MAIN_CUE_BASE's MAIN pair (not ping-ponged) and writes one 8-byte slot per
frame that both speeds send, the USB AUDIO OUT MASTER shape at the 250 us
cadence, so USB AUDIO IN can take this stream as its implicit-feedback
source: with USB AUDIO IN AB the unit is a two-in, two-out interface. It
takes the same hook sites as the other out layouts, so a remix carries one
of the five. README.md.
"""
import dataclasses
import importlib.util
import pathlib

from remix import schema
from remix.schema import Category, Proof, Linked, Module

_spec = importlib.util.spec_from_file_location(
    "usbaudio_manifest", pathlib.Path(schema.__file__).resolve().parents[2] / "modules/usb-audio-out-tracks-main-cue/manifest.py")
usbaudio = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(usbaudio)

_PRODUCER = 0x4000d9a0

MODULE = Module(
    name="usb-audio-out-main", key="USB AUDIO OUT MAIN", kind=usbaudio.MODULE.kind,
    category=Category.MIDI_USB, author="markandrus/octemu", author_url="https://github.com/markandrus/octemu",
    proof=Proof.PORT, proof_note="`verify_usb` under the port (28 Sep 2026); not on a unit",
    doc="MAIN L/R over USB (UAC2, 2 channels, 24-bit) every 250 us; the stereo pairing for USB AUDIO IN (markandrus/octemu's source, the MAIN layout ours).",
    linked=(Linked("usbaudio", usbaudio.SOURCE, cpu="5475", dram=True, include=usbaudio.layout_inc(4)),),
    detours=tuple(
        dataclasses.replace(d, **({"note": "frame_isr's last instruction: the per-block producer (MAIN L/R) and the packet builder"}
                                  if d.site == _PRODUCER else {}))
        for d in usbaudio.DETOURS),
    overrides=usbaudio.MODULE.overrides,
    pokes=usbaudio.MODULE.pokes,
)
