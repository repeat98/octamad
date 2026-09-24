#!/usr/bin/env python3
"""A USB host for the port's device-controller bench (tools/emu/ot_emu/usb.h).

  out/emu/ot_emu --image out/mainos_bus.bin --usb-host /tmp/ot-usb.sock --ms 20000 &
  tools/harness/usb_host.py /tmp/ot-usb.sock enum          # reset + enumerate
  tools/harness/usb_host.py /tmp/ot-usb.sock msc           # + INQUIRY, TEST UNIT READY
  tools/harness/usb_host.py /tmp/ot-usb.sock midi-recv 5   # drain EP2 IN for 5 s
  tools/harness/usb_host.py /tmp/ot-usb.sock midi-send 903c64
  tools/harness/usb_host.py /tmp/ot-usb.sock audio 3 2.0 out.pcm   # drain an iso IN endpoint, then the counters
  tools/harness/usb_host.py /tmp/ot-usb.sock counters       # USB AUDIO's twelve counters (vendor request)

The line protocol is octemu's (markandrus, MIT), so its tests/usb-host.py
drives this port too. Every transfer runs under a deadline: a hang IS the
failure, reported with the op that stalled. Exit 0 only when the scenario
passed. Replies come when the guest completes the transfer, so the emulator
must be running, not stopped at a gate.
"""
import socket
import struct
import sys
import time


class Stall(Exception):
    pass


class Bench:
    def __init__(self, path, timeout=30.0):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        deadline = time.time() + timeout
        while True:
            try:
                self.sock.connect(path)
                break
            except (FileNotFoundError, ConnectionRefusedError):
                if time.time() > deadline:
                    raise
                time.sleep(0.2)
        self.timeout = timeout
        self.buf = b""

    def cmd(self, line, expect=None, timeout=None):
        self.sock.sendall(line.encode() + b"\n")
        return self.wait(expect or line.split()[0], timeout)

    def wait(self, prefix, timeout=None):
        deadline = time.time() + (timeout or self.timeout)
        while True:
            i = self.buf.find(b"\n")
            if i >= 0:
                line = self.buf[:i].decode()
                self.buf = self.buf[i + 1:]
                if line.startswith("err"):
                    raise RuntimeError(f"bench: {line}")
                if line.startswith(prefix) or line == "ok":
                    return line
                continue
            left = deadline - time.time()
            if left <= 0:
                raise TimeoutError(f"no reply to '{prefix}' in time: the guest never completed the transfer")
            self.sock.settimeout(left)
            try:
                chunk = self.sock.recv(65536)
            except socket.timeout:
                continue
            if not chunk:
                raise RuntimeError("bench closed the socket")
            self.buf += chunk

    def reset(self):
        self.cmd("reset", "ok")

    def speed(self, hs):
        self.cmd(f"speed {'hs' if hs else 'fs'}", "ok")

    def setup(self, bm, breq, wval, widx, wlen):
        self.cmd("setup " + struct.pack("<BBHHH", bm, breq, wval, widx, wlen).hex(), "ok")

    def ep_in(self, ep, maxlen, timeout=None):
        parts = self.cmd(f"in {ep} {maxlen}", f"in {ep}", timeout).split()
        if len(parts) > 2 and parts[2] == "stall":
            raise Stall(f"EP{ep} IN stalled")
        return bytes.fromhex(parts[2]) if len(parts) > 2 else b""

    def ep_out(self, ep, data=b"", timeout=None):
        parts = self.cmd(f"out {ep} {data.hex()}".rstrip(), f"out {ep}", timeout).split()
        if len(parts) > 2 and parts[2] == "stall":
            raise Stall(f"EP{ep} OUT stalled")
        return int(parts[2])

    def poke(self, addr, data):
        self.cmd(f"poke {addr:#x} {data.hex()}", "poke")

    def call(self, addr, *args, timeout=None):
        r = self.cmd("call " + " ".join(f"{v:#x}" for v in (addr, *args)), "call", timeout)
        parts = r.split()
        if len(parts) > 1 and parts[1] == "err":
            raise RuntimeError(r)
        return int(parts[1], 0)

    def ctrl_in(self, bm, breq, wval, widx, wlen):
        self.setup(bm, breq, wval, widx, wlen)
        data = self.ep_in(0, wlen)
        self.ep_out(0)
        return data

    def ctrl_nodata(self, bm, breq, wval, widx):
        self.setup(bm, breq, wval, widx, 0)
        self.ep_in(0, 64)


def descriptors(cfg):
    i = 0
    while i + 2 <= len(cfg):
        ln, ty = cfg[i], cfg[i + 1]
        if ln < 2:
            break
        yield ty, cfg[i:i + ln]
        i += ln


def enumerate_device(b, hs=True):
    b.speed(hs)
    b.reset()
    time.sleep(0.3)
    dev = b.ctrl_in(0x80, 6, 0x0100, 0, 18)
    assert len(dev) == 18, f"device descriptor: {len(dev)} bytes"
    vid, pid = struct.unpack("<HH", dev[8:12])
    b.ctrl_nodata(0x00, 5, 1, 0)
    cfg9 = b.ctrl_in(0x80, 6, 0x0200, 0, 9)
    assert len(cfg9) == 9, f"config header: {len(cfg9)} bytes"
    total = struct.unpack("<H", cfg9[2:4])[0]
    cfg = b.ctrl_in(0x80, 6, 0x0200, 0, total)
    assert len(cfg) == total, f"full config: {len(cfg)}/{total} bytes"
    b.ctrl_nodata(0x00, 9, 1, 0)
    ifaces = [d for t, d in descriptors(cfg) if t == 4]
    eps = [d for t, d in descriptors(cfg) if t == 5]
    print(f"enumerated: VID {vid:04x} PID {pid:04x}, bcdUSB {dev[3]:x}.{dev[2]:02x}, config {total} bytes, "
          f"bNumInterfaces {cfg[4]}, {len(ifaces)} interface descriptor(s)")
    for d in ifaces:
        print(f"  interface {d[2]} alt {d[3]}: class {d[5]:02x}/{d[6]:02x}/{d[7]:02x}, {d[4]} EP(s)")
    for d in eps:
        print(f"  EP {d[2]:02x} type {d[3] & 3} maxpkt {struct.unpack('<H', d[4:6])[0]} interval {d[6]}")
    return dev, cfg


def msc_cbw(tag, datalen, in_dir, cb):
    return struct.pack("<4sIIBBB", b"USBC", tag, datalen, 0x80 if in_dir else 0, 0, len(cb)) + cb + bytes(16 - len(cb))


def msc_test(b):
    cbw = msc_cbw(1, 36, True, bytes([0x12, 0, 0, 0, 36, 0]))
    assert b.ep_out(1, cbw) == 31
    data = b.ep_in(1, 36)
    csw = b.ep_in(1, 13)
    assert csw[:4] == b"USBS", f"bad CSW: {csw.hex()}"
    print(f"MSC INQUIRY: {len(data)} bytes {data[8:36].decode('ascii', 'replace')!r}, CSW status {csw[12]}")
    ok = len(data) == 36 and csw[12] == 0
    cbw = msc_cbw(2, 0, False, bytes([0x00, 0, 0, 0, 0, 0]))
    assert b.ep_out(1, cbw) == 31
    csw = b.ep_in(1, 13)
    assert csw[:4] == b"USBS", f"bad CSW: {csw.hex()}"
    print(f"MSC TEST UNIT READY: CSW status {csw[12]} (nonzero = no medium outside DISK MODE)")
    return ok


def midi_recv(b, seconds):
    end = time.time() + seconds
    packets = []
    while time.time() < end:
        try:
            data = b.ep_in(2, 64, timeout=max(0.1, end - time.time()))
        except TimeoutError:
            break
        for i in range(0, len(data) - 3, 4):
            packets.append(data[i:i + 4])
    for p in packets:
        print(f"  USB-MIDI packet {p.hex()}")
    print(f"midi-recv: {len(packets)} packet(s)")
    return packets


def midi_send(b, raw):
    # one event packet per channel message, cable 0, CIN = status >> 4
    pkt = b""
    i = 0
    while i < len(raw):
        st = raw[i]
        n = 2 if st & 0xf0 in (0xc0, 0xd0) else 3
        msg = raw[i:i + n]
        pkt += bytes([st >> 4]) + msg + bytes(3 - len(msg))
        i += n
    print(f"midi-send: {b.ep_out(2, pkt)} byte(s) accepted")


COUNTERS = ("consumed", "acc", "overruns", "underruns", "lastn", "lastfill", "lastbank",
            "bankdup", "lastsamp", "srcjump", "reprimes", "produced")


def counters(b):
    """USB AUDIO's twelve counters over the vendor request 0xc0/0x55 (48 big-endian bytes)."""
    raw = b.ctrl_in(0xc0, 0x55, 0, 0, 48)
    vals = struct.unpack(">12i", raw) if len(raw) == 48 else None
    if vals is None:
        raise RuntimeError(f"counters: {len(raw)} bytes")
    return dict(zip(COUNTERS, vals))


def audio(b, ep, seconds, path):
    """Drain an isochronous IN endpoint at the host's poll rate and keep the bytes."""
    n = int(seconds * 2000)
    empty = 0
    with open(path, "wb") as f:
        for _ in range(n):
            data = b.ep_in(ep, 1024)
            if not data:
                empty += 1
            f.write(data)
    print(f"audio: {n} poll(s), {empty} empty, {path}")
    return empty


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    b = Bench(argv[1])
    what = argv[2]
    if what == "enum":
        enumerate_device(b, hs="--fs" not in argv)
        return 0
    if what == "msc":
        enumerate_device(b, hs="--fs" not in argv)
        return 0 if msc_test(b) else 1
    if what == "midi-recv":
        enumerate_device(b)
        midi_recv(b, float(argv[3]) if len(argv) > 3 else 3.0)
        return 0
    if what == "midi-send":
        enumerate_device(b)
        midi_send(b, bytes.fromhex(argv[3]))
        return 0
    if what == "midi-tx":
        # the firmware's own midi_send (0x40010bc8) on a message poked into
        # its outbound staging buffer (0x400d807c), then drain EP2 IN
        enumerate_device(b)
        raw = bytes.fromhex(argv[3]) if len(argv) > 3 else bytes([0x90, 0x3c, 0x64])
        b.poke(0x400d807c, raw)
        b.call(0x40010bc8, len(raw), 0x400d807c)
        pk = midi_recv(b, 2.0)
        want = bytes([raw[0] >> 4]) + raw + bytes(3 - len(raw))
        print(f"midi-tx: {'PASS' if want in pk else 'FAIL'} expected packet {want.hex()}")
        return 0 if want in pk else 1
    if what == "counters":
        enumerate_device(b)
        for k, v in counters(b).items():
            print(f"  {k:10s} {v}")
        return 0
    if what == "audio":
        enumerate_device(b)
        ep, seconds, path = int(argv[3]), float(argv[4]), argv[5]
        b.ctrl_nodata(0x01, 0x0b, 1, int(argv[6]) if len(argv) > 6 else 4)   # SET_INTERFACE alt 1
        audio(b, ep, seconds, path)
        c = counters(b)
        print("counters: " + " ".join(f"{k}={v}" for k, v in c.items() if k in ("underruns", "overruns", "bankdup", "reprimes", "produced", "consumed")))
        return 0
    print(f"unknown scenario {what}")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
