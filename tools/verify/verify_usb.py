#!/usr/bin/env python3
"""Enumerate the image just built as a USB device under the ColdFire port.

Boots out/mainos_bus.bin with the device-controller model and its bench
(tools/emu/ot_emu/usb.h), then acts as the host: bus reset, GET_DESCRIPTOR,
SET_ADDRESS, SET_CONFIGURATION, a mass-storage INQUIRY and TEST UNIT READY
over EP1. The firmware's own USB stack answers every step, so this checks:

  * the stock control path is intact in the built image (a module that
    moves a descriptor table, hooks the ISR or grows a configuration shows
    up here as a wrong VID/PID, a short config or a hang);
  * the model's queue-head and transfer-descriptor walk agrees with what
    the firmware builds (the INQUIRY data + CSW chain, both directions);
  * no primed queue head was left uninitialised (the defect that crashed a
    unit under octemu's USB-audio payload).

SKIPs when the port is not built (`make emu-cf`). What this cannot see:
timing (the port serialises the host's polls against the frame interrupt)
and anything a real host does beyond these requests.
"""
import os
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
import usb_host  # noqa: E402  (tools/harness)

from remix import registry  # noqa: E402

EMU = ROOT / "out/emu/ot_emu"
IMAGE = ROOT / "out/mainos_bus.bin"
MIDI_FIFO_HEAD = 0x46100b80         # midi_rx_fifo_head: +1 per byte midi_rx_enqueue (0x40092bbc) takes


def main():
    if not EMU.is_file():
        print("  [SKIP] verify_usb: the port is not built (make emu-cf)")
        return 0
    if not IMAGE.is_file():
        print("  [FAIL] verify_usb: no out/mainos_bus.bin (make bus)")
        return 1
    remix = registry.remix(os.environ.get("REMIX") or registry.DEFAULT_REMIX)
    midi = "USB MIDI" in remix.modules
    audio = "USB AUDIO" in remix.modules
    sock = f"/tmp/ot-usb-{os.getpid()}.sock"     # sun_path is 104 bytes on macOS; the scratch dirs are longer
    log = ROOT / "out/verify_usb.log"
    with open(log, "w") as lf:
        # --frame: the audio producer runs from the frame interrupt, which
        # the port leaves off unless asked (no card, no transport: the
        # tracks are silent, the stream is not).
        emu = subprocess.Popen([str(EMU), "--image", str(IMAGE), "--usb-host", sock, "--usb-hold-ms", "120000",
                                "--watch-mem", f"{MIDI_FIFO_HEAD:#x},4"] + (["--frame"] if audio else []),
                               cwd=ROOT, stdout=lf, stderr=subprocess.STDOUT)
    fails = []

    def check(what, ok, detail=""):
        print(f"  [{'PASS' if ok else 'FAIL'}] {what}{'  ' + detail if detail else ''}")
        if not ok:
            fails.append(what)

    try:
        b = usb_host.Bench(sock, timeout=60.0)
        dev, cfg = usb_host.enumerate_device(b, hs=True)
        vid, pid = dev[8] | dev[9] << 8, dev[10] | dev[11] << 8
        check("device descriptor: Elektron 1935:0002, USB 2.00", (vid, pid, dev[2], dev[3]) == (0x1935, 0x0002, 0x00, 0x02),
              f"got {vid:04x}:{pid:04x} bcdUSB {dev[3]:x}.{dev[2]:02x}")
        ifaces = [d for t, d in usb_host.descriptors(cfg) if t == 4]
        eps = [d for t, d in usb_host.descriptors(cfg) if t == 5]
        msc = [d for d in ifaces if d[5:8] == bytes([8, 6, 0x50])]
        check("a mass-storage SCSI/BOT interface is in the configuration", len(msc) == 1,
              f"{len(ifaces)} interface(s), {len(cfg)} bytes")
        bulk = sorted((d[2], d[3] & 3, d[4] | d[5] << 8) for d in eps if d[2] in (0x81, 0x01))
        check("EP 0x81/0x01 bulk, 512 bytes at high speed", bulk == [(0x01, 2, 512), (0x81, 2, 512)], str(bulk))
        ok = usb_host.msc_test(b)
        check("INQUIRY answers 36 bytes with a good CSW", ok)
        if midi:
            ms = [d for d in ifaces if d[5:7] == bytes([1, 3])]
            ac = [d for d in ifaces if d[5:8] == bytes([1, 1, 0])]     # the MIDI function's (the audio one is protocol 0x20)
            check("USB MIDI: an AudioControl and a MIDIStreaming interface follow the MSC one",
                  len(ac) == 1 and len(ms) == 1 and cfg[4] == (5 if audio else 3), f"bNumInterfaces {cfg[4]}")
            ep2 = sorted((d[2], d[3] & 3, d[4] | d[5] << 8) for d in eps if d[2] in (0x82, 0x02))
            check("USB MIDI: EP 0x82/0x02 bulk, 512 bytes", ep2 == [(0x02, 2, 512), (0x82, 2, 512)], str(ep2))
            # receive: two channel messages in -> six bytes through midi_rx_enqueue (the log's watch)
            usb_host.midi_send(b, bytes.fromhex("903c64b03c40"))
            # transmit: the firmware's own midi_send on a message in its staging buffer -> one event packet out
            raw = bytes([0x90, 0x3c, 0x64])
            b.poke(0x400d807c, raw)
            b.call(0x40010bc8, len(raw), 0x400d807c)
            pk = usb_host.midi_recv(b, 2.0)
            check("USB MIDI: midi_send reaches EP2 IN as one event packet", bytes([0x09]) + raw in pk, str([p.hex() for p in pk]))
        else:
            check("stock: one interface only", cfg[4] == 1, f"bNumInterfaces {cfg[4]}")
        if audio:
            check("USB AUDIO: the device descriptor is the interface-association composite", dev[4:7] == bytes([0xef, 2, 1]), dev[4:7].hex())
            as_ = [d for d in ifaces if d[5:7] == bytes([1, 2])]
            check("USB AUDIO: a UAC2 AudioStreaming interface 4 with alt 0 and alt 1",
                  sorted((d[2], d[3]) for d in as_) == [(4, 0), (4, 1)], str([(d[2], d[3]) for d in as_]))
            iso = [d for d in eps if d[2] == 0x83]
            check("USB AUDIO: EP 0x83 isochronous, 736 bytes, bInterval 3",
                  len(iso) == 1 and (iso[0][3] & 3, iso[0][4] | iso[0][5] << 8, iso[0][6]) == (1, 736, 3),
                  str([(d[3], d[4] | d[5] << 8, d[6]) for d in iso]))
            # the clock source answers its sample rate; SET_INTERFACE alt 1 brings EP3 up
            cur = b.ctrl_in(0xa1, 1, 0x0100, 0x1000 | 3, 4)
            check("USB AUDIO: CS_SAM_FREQ_CONTROL CUR = 44100", cur == (44100).to_bytes(4, "little"), cur.hex())
            b.ctrl_nodata(0x01, 0x0b, 1, 4)
            alt = b.ctrl_in(0x81, 0x0a, 0, 4, 1)
            check("USB AUDIO: GET_INTERFACE reports alt 1", alt == b"\x01", alt.hex())
            got = [b.ep_in(3, 1024) for _ in range(400)]        # 200 ms of device time at the 500 us poll
            sizes = sorted({len(g) for g in got[10:]})           # the first polls may land before the first prime
            check("USB AUDIO: 400 polls on EP3 carry 22/23-frame packets and none empty after the first ten",
                  bool(sizes) and all(s in (704, 736) for s in sizes), f"sizes {sizes}")
            c = usb_host.counters(b)
            print("  counters: " + " ".join(f"{k}={v}" for k, v in c.items()))
            check("USB AUDIO: the vendor request reads the counters back: frames produced and consumed, no overrun",
                  c["produced"] > c["consumed"] > 0 and c["overruns"] == 0,
                  f"produced {c['produced']} consumed {c['consumed']} overruns {c['overruns']} underruns {c['underruns']} bankdup {c['bankdup']}")
            b.ctrl_nodata(0x01, 0x0b, 0, 4)
            after = [len(b.ep_in(3, 1024)) for _ in range(8)]
            check("USB AUDIO: alt 0 stops the stream (empty polls)", all(a == 0 for a in after[2:]), str(after))
    except Exception as e:  # noqa: BLE001 -- a hang or a stall is the finding
        check(f"the host script completed ({type(e).__name__}: {e})", False)
    finally:
        try:
            b.sock.close()          # the hangup ends the port's hold
        except NameError:
            emu.kill()
    try:
        rc = emu.wait(timeout=120)
    except subprocess.TimeoutExpired:
        emu.kill()
        rc = -1
    check("the port exited cleanly after the client hung up", rc == 0, f"exit {rc}")
    text = log.read_text(errors="replace")
    summary = [l for l in text.splitlines() if l.startswith("usb        : USBCMD")]
    if midi:
        writes = [l for l in text.splitlines() if f"[{MIDI_FIFO_HEAD:#x}]" in l]
        check("USB MIDI: six bytes enqueued into the firmware's MIDI receive FIFO", len(writes) == 6, f"{len(writes)} write(s)")
    check("the port printed its USB summary", bool(summary))
    if summary:
        s = summary[-1]
        print("  " + s)
        check("no uninitialised queue head was primed", "UNINITIALIZED" not in s)
        check("no EP0 stall during enumeration", " 0 stall(s)" in s)
    print(f"verify_usb: {'OK' if not fails else str(len(fails)) + ' FAILED'} ({log})")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
