"""USB AUDIO OUT TRACKS MAIN CUE -- the unit as a UAC2 audio input, 20 channels at 44.1 kHz 24-bit.

High speed: the eight tracks' L/R (post-FX, pre-fader) on channels 1-16,
MAIN on 17-18, CUE on 19-20. Full speed: the tracks' stereo sum.
markandrus (octemu, MIT); MAIN/CUE Bryan T. A DRAM unit with build-time
detours. Needs USB MIDI: the audio function joins its composite, and the
ISR shim chains to USB MIDI's. README.md has the design and what was
measured. USB AUDIO OUT TRACKS (modules/usb-audio-out-tracks, the sixteen track
channels) and USB AUDIO OUT MASTER (modules/usb-audio-out-master, track 8's two)
assemble the same source with another USB_LAYOUT.
"""
from remix.schema import Category, Gate, Proof, Detour, Kind, Linked, Module, Override, Poke

H = bytes.fromhex


SOURCE = "modules/usb-audio-out-tracks-main-cue/usbaudio.s"


def layout_inc(layout):
    """The `remix.inc` usbaudio.s includes: USB_LAYOUT 0 (these twenty
    channels), 1 (USB AUDIO OUT TRACKS), 2 (USB AUDIO OUT MASTER), 3 (USB AUDIO OUT MAIN
    CUE) or 4 (USB AUDIO OUT MAIN);
    USB_IN 1 when a USB AUDIO IN module is in the remix (usbaudio.s then answers
    GET_INTERFACE(5) from that unit's in_alt)."""
    def inc(modules):
        usb_in = int(any(k in modules for k in ("USB AUDIO IN AB", "USB AUDIO IN CD", "USB AUDIO IN ABCD")))
        return (f"| remix.inc -- usbaudio.s's layout\n    .set USB_LAYOUT, {layout}\n"
                f"    .set USB_IN, {usb_in}\n")
    return inc


DETOURS = (
    Detour(0x4001dd04, H("2039fc0b01c4"), "usbaudio", "audio_setiface_shim",
           "SET_INTERFACE: interface 4 alt 1 brings the stream up, alt 0 down; others stock"),
    Detour(0x4001d824, H("4879400e20a1"), "usbaudio", "audio_getiface_shim",
           "GET_INTERFACE: interface 4 reports the alt setting the host asked for"),
    Detour(0x4001de64, H("2039fc0b01c0"), "usbaudio", "audio_ctrl_shim",
           "class requests to the clock source (sample rate CUR/RANGE, validity); the rest STALL as stock"),
    Detour(0x4001d4b2, H("23d04ec95028"), "usbaudio", "audio_ep0page_shim",
           "usb_ep0_send fills the dTD's buffer page 1 too: a configuration straddling a 4 KB page transmitted truncated"),
    Detour(0x4000d9a0, H("42b946104d4e"), "usbaudio", "audio_frame_shim",
           "frame_isr's last instruction: the per-block producer (20 channels: tracks, MAIN, CUE; + the sum into the rings) and the packet builder"),
    Detour(0x4001e606, H("2039fc0b01ac"), "usbaudio", "audio_isr_shim",
           "usb_isr UI path: retire EP3 IN completions, then USB MIDI's shim"),
)

MODULE = Module(
    name="usb-audio-out-tracks-main-cue", key="USB AUDIO OUT TRACKS MAIN CUE", kind=Kind.CF_PATCH,
    category=Category.MIDI_USB, author="markandrus/octemu", author_url="https://github.com/markandrus/octemu",
    proof=Proof.HARDWARE, proof_note="Sam's MKII (image 64, 25 Sep 2026); Tim's MKI (OCTATRICK9, 26 Sep 2026)",
    doc="Twenty 24-bit channels over USB (UAC2): the tracks post-FX pre-fader, MAIN, CUE; the stereo sum at full speed (markandrus/octemu).",
    linked=(Linked("usbaudio", SOURCE, cpu="5475", dram=True, include=layout_inc(0)),),
    detours=DETOURS,
    # The ISR site is USB MIDI's; this shim does its EP3 work and jumps to
    # USB MIDI's shim by symbol (the units link together).
    overrides=(Override(0x4001e606, "USB MIDI"),),
    pokes=(Poke(0x400e2004, H("000000"), H("ef0201"),
                "device descriptor: class/subclass/protocol = interface-association composite"),),
    # MAIN/CUE aligned with the tracks (skips without a source project)
    gates=(Gate("tools/verify/verify_usb_align.py", remix_arg=False, venv=True, stage="image"),),
)
