"""USB MIDI -- the firmware's dormant USB-MIDI half, completed.

OS 1.40C ships a USB-MIDI transmit encoder and the EP2 primitives that
nothing reaches, and no receive decoder. markandrus (octemu, MIT) wired it
in: grown configuration descriptors (MSC + AudioControl + MIDIStreaming,
EP2 bulk both ways), EP2 brought up at SET_CONFIGURATION, EP2 completions
dispatched from the USB ISR into a new receive decoder that feeds the same
byte path DIN MIDI uses, and both transmit senders (channel messages and
the realtime bytes) mirrored into the dormant encoder. The port sits on
the DRAM platform instead of his in-image free zone; README.md has what
differs and what was measured.
"""
import importlib.util
import pathlib

from remix import schema
from remix.schema import Detour, Kind, Linked, Module, SymbolRef

# Manifests are executed from source, not imported as a package; the
# descriptor generator beside this file is loaded by path.
_spec = importlib.util.spec_from_file_location(
    "usbmidi_descriptors", pathlib.Path(schema.__file__).resolve().parents[2] / "modules/usbmidi/descriptors.py")
descriptors = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(descriptors)

H = bytes.fromhex

MODULE = Module(
    name="usbmidi", key="USB MIDI", kind=Kind.CF_PATCH,
    doc="Class-compliant USB-MIDI in and out on the OT's own USB port, mirroring the DIN ports (markandrus/octemu).",
    linked=(
        # his unit, verbatim: the build re-links it at his zone address and
        # compares with his usb-midi.py's blob (1,124 B, from our stock bytes)
        Linked("usbmidi", "modules/usbmidi/usbmidi.s", cpu="54455", dram=True,
               reference=(0x400d24f0, "6291d91e923145be62719eee56c2ca823d36c2d71ae538550e70b5533d404e60")),
        Linked("usbmidi_clamp", "modules/usbmidi/clamp.s", cpu="54455", dram=True),
        # the four configurations for THIS remix (124 B, or 250 B with USB
        # AUDIO's function added) and the absolute `cfg_len` the clamps read
        Linked("usbmidi_cfg", "modules/usbmidi/cfg.s", cpu="5475", dram=True,
               include=descriptors.remix_inc),
    ),
    detours=(
        Detour(0x4001d9ca, H("4879400b9868"), "usbmidi", "usbmidi_setcfg_shim",
               "SET_CONFIGURATION body: bring EP2 up, 512-byte packets at high speed"),
        Detour(0x4001e606, H("2039fc0b01ac"), "usbmidi", "usbmidi_isr_shim",
               "usb_isr UI path: EP2 completions -> decode / re-prime / kick"),
        Detour(0x40010bc8, H("4fefffec48d7043c"), "usbmidi", "usbmidi_send_shim",
               "midi_send entry: queue the message for the USB encoder", pad_to=8),
        Detour(0x400108b0, H("2f02122f000b"), "usbmidi", "usbmidi_prio_shim",
               "priority (realtime) byte sender: queue the byte for the USB encoder"),
        Detour(0x4001daec, H("303946c8ce0c"), "usbmidi", "usbmidi_clrfeat_shim",
               "CLEAR_FEATURE(ENDPOINT_HALT): answer for EP2 instead of stalling"),
        # GET_DESCRIPTOR(CONFIG / OTHER_SPEED): the responder's two hardcoded
        # clamps (moveq #32,d0 / cmpl d2,d0 / bcs +4) become min(wLength, cfg_len)
        Detour(0x4001d858, H("7020b0826504"), "usbmidi_clamp", "usbmidi_clamp1_shim",
               "config responder: clamp the reply to the grown configuration's length"),
        Detour(0x4001d896, H("7020b0826504"), "usbmidi_clamp", "usbmidi_clamp2_shim",
               "other-speed responder: the same clamp"),
    ),
    # GET_DESCRIPTOR(CONFIG): the responder's four `pea <table>` operands.
    symbol_refs=(
        SymbolRef(0x4001d882, 0x400e201c, "usbmidi_cfg", "cfg_fs", "full-speed configuration"),
        SymbolRef(0x4001d88a, 0x400e203c, "usbmidi_cfg", "cfg_hs", "high-speed configuration"),
        SymbolRef(0x4001d8c0, 0x400e207c, "usbmidi_cfg", "cfg_os_hs", "other-speed (type 7), 512-byte EPs"),
        SymbolRef(0x4001d8c8, 0x400e205c, "usbmidi_cfg", "cfg_os_fs", "other-speed (type 7), 64-byte EPs"),
    ),
)
