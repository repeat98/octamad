"""The USB configuration descriptors the responder serves, per remix.

markandrus/octemu's `custom/usb-midi.py` and `custom/usb-audio.py`
(`config_descriptor`, MIT), as the text of USB MIDI's descriptor unit:
the build calls `remix_inc(modules)` and writes it beside `cfg.s` as
`remix.inc` (schema.Linked.include). Every configuration keeps the stock
MSC interface byte for byte at the front:

  MSC only (stock)      one interface, 32 bytes
  + USB MIDI            + AudioControl [2] + MIDIStreaming with EP2 bulk
                        in/out: three interfaces, 124 bytes
  + USB AUDIO           the MIDI function under an interface association,
                        then a second: a UAC2 AudioControl (clock source,
                        input terminal, USB streaming output terminal) +
                        AudioStreaming (alt 0 idle, alt 1 with the iso IN
                        EP3): five interfaces, 250 bytes. Sixteen channels
                        at high speed, the stereo sum at full speed.

`cfg_len` is exported as an absolute symbol: the responder's two clamp
shims (usbmidi.s) compare wLength against it, since the stock `moveq #32`
cannot hold either grown length above 127.
"""
import struct

HS_CHANNELS, HS_MAXPKT, HS_BINTERVAL = 16, 23 * 32, 3     # 23 frames x 32 B every 500 us
FS_CHANNELS, FS_MAXPKT, FS_BINTERVAL = 2, 45 * 4, 1       # 45 stereo frames every 1 ms
UAC2_AC_IFACE, UAC2_AS_IFACE = 3, 4                        # usbaudio.s .set: the same numbers
UAC2_CLOCK_ID, UAC2_IT_ID, UAC2_OT_ID = 0x10, 0x11, 0x12


def _ep(addr, pkt):
    return bytes([7, 5, addr, 2]) + struct.pack("<H", pkt) + bytes([0])


def _ep_midi(addr, pkt):
    return bytes([9, 5, addr, 2]) + struct.pack("<H", pkt) + bytes(3)


_MS_CLASS = (bytes([7, 0x24, 1, 0, 1, 37, 0]) +           # MS header
             bytes([6, 0x24, 2, 1, 1, 0]) +               # IN jack, embedded 1
             bytes([6, 0x24, 2, 2, 2, 0]) +               # IN jack, external 2
             bytes([9, 0x24, 3, 1, 3, 1, 2, 1, 0]) +      # OUT jack, embedded 3
             bytes([9, 0x24, 3, 2, 4, 1, 1, 1, 0]))       # OUT jack, external 4


def midi_config(hs, other_speed=False):
    """MSC + AudioControl + MIDIStreaming, 124 bytes (usb-midi.py)."""
    bulk = 512 if hs else 64
    body = (bytes([9, 4, 0, 0, 2, 8, 6, 0x50, 0]) +
            _ep(0x81, bulk) + _ep(0x01, bulk) +
            bytes([9, 4, 1, 0, 0, 1, 1, 0, 0]) +
            bytes([9, 0x24, 1, 0, 1, 9, 0, 1, 2]) +
            bytes([9, 4, 2, 0, 2, 1, 3, 0, 0]) +
            _MS_CLASS +
            _ep_midi(0x02, bulk) + bytes([5, 0x25, 1, 1, 1]) +
            _ep_midi(0x82, bulk) + bytes([5, 0x25, 1, 1, 3]))
    total = 9 + len(body)
    hdr = bytes([9, 7 if other_speed else 2]) + struct.pack("<H", total) + bytes([3, 1, 0, 0xC0, 3])
    return hdr + body


def audio_config(hs, other_speed=False):
    """The MIDI composite plus a UAC2 audio function, 250 bytes (usb-audio.py).

    Two SEPARATE functions under interface associations, the shape of a
    device macOS accepts (his measurement against an Elektron Digitone):
    one AudioControl collecting the MIDIStreaming interface, another
    collecting the AudioStreaming one. The clock source is read-only
    (bmControls 0b01): a host-programmable clock would need a control OUT
    with a data stage, which the stock EP0 stack does not have.
    """
    bulk = 512 if hs else 64
    nch = HS_CHANNELS if hs else FS_CHANNELS
    maxpkt = HS_MAXPKT if hs else FS_MAXPKT
    clk, it, ot = UAC2_CLOCK_ID, UAC2_IT_ID, UAC2_OT_ID
    clock = bytes([8, 0x24, 0x0A, clk, 0x01, 0x05, 0, 0])
    in_term = (bytes([17, 0x24, 0x02, it]) + struct.pack("<H", 0x0603) +
               bytes([0, clk, nch]) + struct.pack("<I", 0) +
               bytes([0]) + struct.pack("<H", 0) + bytes([0]))
    out_term = (bytes([12, 0x24, 0x03, ot]) + struct.pack("<H", 0x0101) +
                bytes([0, it, clk]) + struct.pack("<H", 0) + bytes([0]))
    ac_audio_total = 9 + len(clock) + len(in_term) + len(out_term)
    ac_audio = (bytes([9, 0x24, 1]) + struct.pack("<H", 0x0200) + bytes([0x0A]) +
                struct.pack("<H", ac_audio_total) + bytes([0]) + clock + in_term + out_term)
    ac, as_ = UAC2_AC_IFACE, UAC2_AS_IFACE
    as_iface = (
        bytes([9, 4, as_, 0, 0, 1, 2, 0x20, 0]) +
        bytes([9, 4, as_, 1, 1, 1, 2, 0x20, 0]) +
        bytes([16, 0x24, 1, ot, 0, 1]) + struct.pack("<I", 1) +
        bytes([nch]) + struct.pack("<I", 0) + bytes([0]) +
        bytes([6, 0x24, 2, 1, 2, 16]) +
        bytes([7, 5, 0x83, 0x05]) + struct.pack("<H", maxpkt) +
        bytes([HS_BINTERVAL if hs else FS_BINTERVAL]) +
        bytes([8, 0x25, 1, 0, 0, 0]) + struct.pack("<H", 0))
    ac_midi = bytes([9, 0x24, 1, 0, 1]) + struct.pack("<H", 9) + bytes([1, 2])
    iad_midi = bytes([8, 0x0B, 1, 2, 0x01, 0x00, 0x00, 0])
    iad_audio = bytes([8, 0x0B, ac, 2, 0x01, 0x00, 0x20, 0])
    body = (bytes([9, 4, 0, 0, 2, 8, 6, 0x50, 0]) +
            _ep(0x81, bulk) + _ep(0x01, bulk) +
            iad_midi +
            bytes([9, 4, 1, 0, 0, 1, 1, 0, 0]) + ac_midi +
            bytes([9, 4, 2, 0, 2, 1, 3, 0, 0]) +
            _MS_CLASS +
            _ep_midi(0x02, bulk) + bytes([5, 0x25, 1, 1, 1]) +
            _ep_midi(0x82, bulk) + bytes([5, 0x25, 1, 1, 3]) +
            iad_audio +
            bytes([9, 4, ac, 0, 0, 1, 1, 0x20, 0]) + ac_audio +
            as_iface)
    total = 9 + len(body)
    hdr = bytes([9, 7 if other_speed else 2]) + struct.pack("<H", total) + bytes([5, 1, 0, 0xC0, 3])
    return hdr + body


def configs(with_audio):
    f = audio_config if with_audio else midi_config
    out = {"cfg_fs": f(False), "cfg_hs": f(True), "cfg_os_fs": f(False, True), "cfg_os_hs": f(True, True)}
    lengths = {len(v) for v in out.values()}
    assert len(lengths) == 1, "the four configurations must share one length (one clamp)"
    return out, lengths.pop()


def remix_inc(modules):
    tables, length = configs("USB AUDIO" in modules)
    lines = [f"| remix.inc -- the configuration descriptors for this remix ({'USB MIDI + USB AUDIO' if 'USB AUDIO' in modules else 'USB MIDI'}),",
             "| generated by modules/usbmidi/descriptors.py; the build rewrites it.",
             f"    .global cfg_len", f"    .set cfg_len, {length}", "",
             "    .text", "    .global cfg_fs, cfg_hs, cfg_os_fs, cfg_os_hs", ""]
    for name, blob in tables.items():
        lines.append("    .balign 4")
        lines.append(f"{name}:")
        for i in range(0, len(blob), 16):
            lines.append("    .byte " + ", ".join(f"0x{b:02x}" for b in blob[i:i + 16]))
        lines.append("")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    import sys
    print(remix_inc({"USB MIDI", "USB AUDIO"} if "--audio" in sys.argv else {"USB MIDI"}))
