"""USB AUDIO OUT MASTER -- USB AUDIO as a two-channel stream of track 8.

Channels 1/2: track 8's L/R, post-FX, pre-fader (the master track: with
MASTER TRACK on, the mix through T8's effects, before T8 LEVEL and MAIN
volume), at both USB speeds. USB AUDIO OUT TRACKS MAIN CUE's source (markandrus/octemu, MIT)
assembled with USB_LAYOUT = 2: the producer reads T8's read-back words alone and
writes one 8-byte slot per frame, and USB MIDI's descriptor unit declares a
front-left/front-right stereo input. The variant is Sam Banks's. It takes
the same hook sites as USB AUDIO OUT TRACKS MAIN CUE and USB AUDIO OUT TRACKS, so a remix
carries one of the three. README.md.
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
    name="usb-audio-out-master", key="USB AUDIO OUT MASTER", kind=usbaudio.MODULE.kind,
    category=Category.MIDI_USB, author="markandrus/octemu", author_url="https://github.com/markandrus/octemu",
    proof=Proof.PORT, proof_note="`verify_usb` under the port (27 Sep 2026); not on hardware",
    doc="Track 8's L/R over USB (UAC2, 2 channels, 24-bit): the master track, post-FX pre-fader; USB AUDIO OUT TRACKS MAIN CUE's source, the T8 variant Sam Banks's.",
    linked=(Linked("usbaudio", usbaudio.SOURCE, cpu="5475", dram=True, include=usbaudio.layout_inc(2)),),
    detours=tuple(
        dataclasses.replace(d, **({"note": "frame_isr's last instruction: the per-block producer (track 8's L/R) and the packet builder"}
                                  if d.site == _PRODUCER else {}))
        for d in usbaudio.DETOURS),
    overrides=usbaudio.MODULE.overrides,
    pokes=usbaudio.MODULE.pokes,
)
