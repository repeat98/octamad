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

# The three USB audio modules (one source, modules/usb-audio-extended/usbaudio.s):
# high-speed channels, packet cap, bInterval (2 = 250 us, 4 = 1 ms), and what each channel
# carries as (source, L/R): source 0-7 = track 1-8's read-back words, 8 =
# MAIN, 9 = CUE.
LAYOUTS = {
    "USB AUDIO EXTENDED": (20, 960, 2, [(t, c) for t in range(8) for c in (0, 1)] + [(8, 0), (8, 1), (9, 0), (9, 1)]),
    "USB AUDIO FULL": (16, 768, 2, [(t, c) for t in range(8) for c in (0, 1)]),
    "USB AUDIO MASTER": (2, 360, 4, [(7, 0), (7, 1)]),
}
RB_BASE, MC_BASE = 0x80003190, 0x80005e60   # the tracks' read-back arena (2 banks) and MAIN/CUE (usbaudio.s)


def tap_word(src, lr, frame):
    """A read-back word that names its source, side and frame; the producer
    keeps the top 24 bits."""
    return ((0x10 + src) << 24) | ((0x20 + lr) << 16) | ((0x30 + frame) << 8) | 0x77


TAP_RB = b"".join(tap_word(t, c, f).to_bytes(4, "big") for _bank in range(2) for t in range(8) for f in range(16) for c in (0, 1))
TAP_MC = b"".join(tap_word(8 + k, c, f).to_bytes(4, "big") for k in (0, 1) for f in range(16) for c in (0, 1))


def main():
    if not EMU.is_file():
        print("  [SKIP] verify_usb: the port is not built (make emu-cf)")
        return 0
    if not IMAGE.is_file():
        print("  [FAIL] verify_usb: no out/mainos_bus.bin (make bus)")
        return 1
    remix = registry.remix(os.environ.get("REMIX"))
    midi = "USB MIDI" in remix.modules
    audio = next((k for k in LAYOUTS if k in remix.modules), None)
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
            nch, maxpkt, bint, taps = LAYOUTS[audio]
            frame_b = 4 * nch
            per = (10, 11, 12) if bint == 2 else (43, 44, 45, 46)     # frames per packet the servo can send
            iso = [d for d in eps if d[2] == 0x83]
            if iso:                                              # poll at the rate the descriptor asks for
                b.iso_hz(8000 // (1 << (iso[0][6] - 1)))
            check(f"{audio}: EP 0x83 isochronous, {maxpkt} bytes, bInterval {bint}",
                  len(iso) == 1 and (iso[0][3] & 3, iso[0][4] | iso[0][5] << 8, iso[0][6]) == (1, maxpkt, bint),
                  str([(d[3], d[4] | d[5] << 8, d[6]) for d in iso]))
            asg = cfg.find(bytes([16, 0x24, 1]))                 # CS AS_GENERAL: bNrChannels at +10, bmChannelConfig +11
            check(f"{audio}: AS_GENERAL declares {nch} channels",
                  asg >= 0 and cfg[asg + 10] == nch, f"bNrChannels {cfg[asg + 10] if asg >= 0 else None}")
            if nch == 2:
                cc = int.from_bytes(cfg[asg + 11:asg + 15], "little") if asg >= 0 else None
                check(f"{audio}: AS_GENERAL bmChannelConfig = front left + front right (0x3)", cc == 3, f"{cc}")
            fmt24, fmt16 = bytes([6, 0x24, 2, 1, 4, 24]), bytes([6, 0x24, 2, 1, 2, 16])   # FORMAT_TYPE_I: subslot, bits
            check("USB AUDIO: FORMAT_TYPE_I, 24-bit samples in 4-byte subslots",
                  cfg.count(fmt24) == 1 and fmt16 not in cfg)
            # the clock source answers its sample rate; SET_INTERFACE alt 1 brings EP3 up
            cur = b.ctrl_in(0xa1, 1, 0x0100, 0x1000 | 3, 4)
            check("USB AUDIO: CS_SAM_FREQ_CONTROL CUR = 44100", cur == (44100).to_bytes(4, "little"), cur.hex())
            b.ctrl_nodata(0x01, 0x0b, 1, 4)
            alt = b.ctrl_in(0x81, 0x0a, 0, 4, 1)
            check("USB AUDIO: GET_INTERFACE reports alt 1", alt == b"\x01", alt.hex())
            got = [b.ep_in(3, 1024) for _ in range(800)]        # 200 ms of device time at the 250 us poll
            sizes = sorted({len(g) for g in got[10:]})           # the first polls may land before the first prime
            check(f"{audio}: 800 polls on EP3 carry {per[0]}-{per[-1]}-frame packets of {frame_b} B and none empty after the first ten",
                  bool(sizes) and all(s in [n * frame_b for n in per] for s in sizes), f"sizes {sizes}")
            words = b"".join(got[10:])
            low = sum(1 for i in range(0, len(words), 4) if words[i])
            check("USB AUDIO: every 4-byte subslot's low byte is zero (24 bits, left-justified)",
                  bool(words) and low == 0, f"{low} of {len(words) // 4} subslots")
            c = usb_host.counters(b)
            print("  counters: " + " ".join(f"{k}={v}" for k, v in c.items()))
            check(f"{audio}: the vendor request reads the counters back: frames produced and consumed, no overrun",
                  c["produced"] > c["consumed"] > 0 and c["overruns"] == 0,
                  f"produced {c['produced']} consumed {c['consumed']} overruns {c['overruns']} underruns {c['underruns']} bankdup {c['bankdup']}")
            # (after the counters: re-poking between polls slows the bench's
            # polling, and the port counts the polls it skips as overruns)
            # Which taps stream: the read-back arena (both banks) and MAIN/CUE
            # re-poked before every poll with words naming their source, so
            # the producer reads them whichever bank the eDMA left it (the
            # eDMA rewrites the current bank each frame). Every channel must
            # carry only its own source's words, and every source it should.
            tapped = []
            for _ in range(1200):
                b.poke(RB_BASE, TAP_RB)
                b.poke(MC_BASE, TAP_MC)
                tapped.append(b.ep_in(3, 1024))
            tw = [int.from_bytes(w[i:i + 4], "little") for w in tapped[-400:] for i in range(0, len(w), 4)]
            seen, wrong = [0] * nch, []
            for i, w in enumerate(tw):
                src, lr = (w >> 24) - 0x10, ((w >> 16) & 0xff) - 0x20
                if 0 <= src < 10 and lr in (0, 1):
                    if (src, lr) == taps[i % nch]:
                        seen[i % nch] += 1
                    else:
                        wrong.append((i % nch, f"{w:08x}"))
            names = ["T%d %s" % (s + 1, "LR"[c]) if s < 8 else ("MAIN", "CUE")[s - 8] + " " + "LR"[c] for s, c in taps]
            check(f"{audio}: channels 1-{nch} carry {', '.join(names) if nch <= 4 else names[0] + ' .. ' + names[-1]}, each its own source's words only",
                  not wrong and all(n >= 100 for n in seen), f"per-channel hits {seen}; wrong {wrong[:6]}")
            b.ctrl_nodata(0x01, 0x0b, 0, 4)
            after = [len(b.ep_in(3, 1024)) for _ in range(8)]
            check("USB AUDIO: alt 0 stops the stream (empty polls)", all(a == 0 for a in after[2:]), str(after))
            # Full speed: the same device re-enumerated. The stereo sum of the
            # tracks (EXTENDED, FULL) or track 8's L/R (MASTER) in 44/45-frame
            # 1 ms packets of 8-byte frames.
            usb_host.enumerate_device(b, hs=False)
            b.iso_hz(0)                                          # bInterval 1 at full speed: 1 ms
            b.ctrl_nodata(0x01, 0x0b, 1, 4)
            fs = []
            for _ in range(300):
                if nch == 2:
                    b.poke(RB_BASE, TAP_RB)
                fs.append(b.ep_in(3, 1024))
            fsizes = sorted({len(g) for g in fs[10:]})
            check(f"{audio}: full speed: 1 ms packets of 43-46 8-byte frames, none empty after the first ten",
                  bool(fsizes) and all(s in (344, 352, 360, 368) for s in fsizes), f"sizes {fsizes}")
            if nch == 2:
                fw = [int.from_bytes(w[i:i + 4], "little") for w in fs[-150:] for i in range(0, len(w), 4)]
                fseen, fwrong = [0, 0], []
                for i, w in enumerate(fw):
                    src, lr = (w >> 24) - 0x10, ((w >> 16) & 0xff) - 0x20
                    if 0 <= src < 10 and lr in (0, 1):
                        if (src, lr) == taps[i % 2]:
                            fseen[i % 2] += 1
                        else:
                            fwrong.append((i % 2, f"{w:08x}"))
                check(f"{audio}: full speed: channels 1/2 carry T8 L/R, its own words only",
                      not fwrong and all(n >= 100 for n in fseen), f"per-channel hits {fseen}; wrong {fwrong[:6]}")
            b.ctrl_nodata(0x01, 0x0b, 0, 4)
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
