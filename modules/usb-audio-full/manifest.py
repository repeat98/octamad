"""USB AUDIO FULL -- USB AUDIO with the sixteen track channels only.

High speed: the eight tracks' L/R (post-FX, pre-fader) on channels 1-16,
MAIN and CUE left out; full speed: the tracks' stereo sum. USB AUDIO
EXTENDED's source (markandrus/octemu, MIT) assembled with USB_LAYOUT = 1:
the producer skips MAIN/CUE and writes a 64-byte slot per frame. The
layout is his before MAIN/CUE were added (image 69 ran sixteen channels
at 24 bits on hardware, from the source as it was then); this build is
ours. It takes the same hook sites as USB AUDIO EXTENDED and USB AUDIO
MASTER, so a remix carries one of the three. README.md.
"""
import dataclasses
import importlib.util
import pathlib

from remix import schema
from remix.schema import Category, Proof, Linked, Module

_spec = importlib.util.spec_from_file_location(
    "usbaudio_manifest", pathlib.Path(schema.__file__).resolve().parents[2] / "modules/usb-audio-extended/manifest.py")
usbaudio = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(usbaudio)

_PRODUCER = 0x4000d9a0

MODULE = Module(
    name="usb-audio-full", key="USB AUDIO FULL", kind=usbaudio.MODULE.kind,
    category=Category.MIDI_USB, author="markandrus/octemu", author_url="https://github.com/markandrus/octemu",
    proof=Proof.PORT, proof_note="`verify_usb` under the port (27 Sep 2026); this build not on hardware (image 69 ran the 16-channel layout from earlier source)",
    doc="Sixteen 24-bit channels over USB (UAC2): the tracks post-FX pre-fader, no MAIN/CUE; the stereo sum at full speed (markandrus/octemu).",
    linked=(Linked("usbaudio", usbaudio.SOURCE, cpu="5475", dram=True, include=usbaudio.layout_inc(1)),),
    detours=tuple(
        dataclasses.replace(d, **({"note": "frame_isr's last instruction: the per-block producer (16 channels: the tracks; + the sum into the rings) and the packet builder"}
                                  if d.site == _PRODUCER else {}))
        for d in usbaudio.DETOURS),
    overrides=usbaudio.MODULE.overrides,
    pokes=usbaudio.MODULE.pokes,
)
