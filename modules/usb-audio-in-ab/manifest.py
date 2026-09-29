"""USB AUDIO IN AB -- a stereo pair from the host standing in for inputs A/B.

Host channel 1 = input A, 2 = input B; C and D stay on the jacks. 2 ch x
24-bit in 4-byte subslots, <= 96 B every 250 us, high speed only.

  Descriptors: USB MIDI's descriptor unit adds the host -> device path when
    one of the three IN keys is in the remix (modules/usb-midi/descriptors.py):
    USB streaming IT 0x13 -> line OT 0x14 on the one clock, and interface 5,
    in the high-speed configuration alone. It refuses a remix without a
    250 us USB AUDIO OUT layout (the feedback source): OUT MASTER polls every
    1 ms, untested beside this.
  ColdFire (DRAM unit `usbaudio_in`, modules/usb-audio-in-ab/usbaudio_in.s,
    IN_CHANNELS from remix.inc): SET_INTERFACE(5) at 0x4001dd0a, where
    usbaudio's shim sends every interface but 4; and state 7 of the frame
    transfer machine (0x40004bc0): EP3 OUT up/down, four queued dTDs retired
    into a 1,024-frame ring, and once per frame one more host-port transfer
    to core 0 at $6320 (the idle bank + $320): word 0 = 1 while the stream
    is open, then the 16 samples in host channel order. usbaudio.s answers
    GET_INTERFACE(5) from this unit's in_alt (USB_IN).
  DSP (payload A, placed by the build in the donor region): P:0x88's
    `move r2,x:>$204` becomes `jsr >inject` (schema.DspHook); the inject
    replays it and, while word 0 is set, writes the host's channels over
    this module's slots of the current RX block (slots 2/3 = inputs A/B,
    0/1 = C/D), before every stock reader of the block runs. Payload B has
    no ESAI.
  Memory: dTDs and packet buffers in the top 1 KB of on-chip SRAM
    (Claims.sram), the host-port buffer in the unit's data through the
    uncached alias.

Needs USB MIDI, USB CROSSBAR (without it the controller's 16-byte RX FIFO
loses packet tails under a busy project) and one of USB AUDIO OUT TRACKS
MAIN CUE, OUT TRACKS, OUT MAIN CUE or OUT MAIN. The three IN modules share
their detour sites, so a remix carries one. Bryan T's USB AUDIO OUT
(usbin-test, 26 Sep 2026; four channels, poked into SPATIALIZER's words) on
the placed-section path, 28 Sep 2026. modules/usb-audio-in-ab/README.md.
"""
from remix.schema import (Category, Claims, Detour, DspHook, DspSection, Gate, Kind,
                          Linked, Module, Proof)

H = bytes.fromhex
SOURCE = "modules/usb-audio-in-ab/usbaudio_in.s"
IN_CHANNELS = 2


def in_inc(modules):
    """The `remix.inc` usbaudio_in.s includes: IN_CHANNELS, 2 or 4."""
    return f"| remix.inc -- usbaudio_in.s's width\n    .set IN_CHANNELS, {IN_CHANNELS}\n"


MODULE = Module(
    name="usb-audio-in-ab", key="USB AUDIO IN AB", kind=Kind.HYBRID,
    category=Category.MIDI_USB, author="bryantysinger", author_url="https://github.com/bryantysinger",
    proof=Proof.PORT, proof_note="`verify_usb_in` under the port (28 Sep 2026); the four-channel form ran on Bryan T's MKII as usbin-test build 16 (27 Sep 2026)",
    doc="A stereo pair from the host into inputs A/B (UAC2 EP3 OUT, implicit feedback); the jacks while the stream is closed. C/D stay on the jacks.",
    linked=(Linked("usbaudio_in", SOURCE, cpu="5475", dram=True, include=in_inc),),
    detours=(
        Detour(0x4001dd0a, H("008000400040"), "usbaudio_in", "in_setiface_shim",
               "SET_INTERFACE: interface 5 alt 0/1 records the alt and ACKs, other alts STALL; the rest goes on to stock"),
        Detour(0x40004bc0, H("720113c1fc04801d"), "usbaudio_in", "in_state7_shim",
               "frame transfer state 7: EP3 OUT, the ring, and one more transfer to core 0 at $6320",
               pad_to=8),
        Detour(0x4001de6e, H("23c0fc0b01c0"), "usbaudio_in", "in_ctrl_shim",
               "EP0 stall store: vendor GET 0x56 answers the IN counters instead"),
    ),
    dsp=DspSection(
        asm="modules/usb-audio-in-ab/rx_inject_ab.asm",
        priority=20,
        payloads=frozenset({"A"}),          # core 0 receives the ESAI
        hooks=(DspHook(0x88, (0x627000, 0x000204), "inject",
                       "frame head: the RX block is written before any reader runs"),),
    ),
    claims=Claims(sram=((0x80007c00, 0x80, "EP3 OUT dTDs"),
                        (0x80007c80, 0x180, "EP3 OUT packet buffers"),
                        (0x80007f80, 0x40, "EP0 reply for vendor 0x56"))),
    requires=("USB MIDI", "USB CROSSBAR"),
    gates=(Gate("tools/verify/verify_usb_in.py", remix_arg=False, venv=True, stage="image"),),
)
