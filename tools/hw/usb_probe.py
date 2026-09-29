#!/usr/bin/env python3
"""A hardware probe for USB AUDIO IN (the host's channels into inputs A/B, C/D or A-D)
and the USB AUDIO stream it rides on, for anyone with an Octatrack on
`usb-io` to run against their own unit. Bryan T, 27 Sep 2026 (PR #492), for
a report from an MKI (nordseele, USB_AUDIO_PR468_REVIEW.md): macOS
CoreAudio restarting the stream's IO context hundreds of times, output-only
playback taking about twice its nominal length, and EP3 IN losing frames --
none of which showed on the MKII the module was built on. The USB
controller code has no MKI/MKII branch, so the probe gathers comparable
numbers from more units and hosts.

Two modes:

  sustained (default): one continuous tone for --duration seconds, output
    only. Does a plain session run at nominal speed?

      tools/hw/usb_probe.py --mode sustained --duration 10

  churn: opens and closes the output stream repeatedly (a short tone burst,
    a pause, repeat), the pattern that triggered the reported failure:
    CoreAudio's host apps started and stopped the OT's IO context hundreds
    of times, not once.

      tools/hw/usb_probe.py --mode churn --churn-cycles 100 --churn-on 0.3 --churn-off 0.1

Both modes poll USB AUDIO's counters (vendor 0xc0/0x55, the EP3 IN ring:
produced/consumed/overruns/bankdup/...) and USB AUDIO IN's (0xc0/0x56, the
EP3 OUT ring: produced/underruns/overruns/bad/...) throughout, the requests
tools/hw/usb_counters.py uses; a device-recipient control request needs no
interface claim, so it runs beside the CoreAudio client.

The verdict is read from the counters taken WHILE THE STREAM WAS OPEN: the
host stops polling EP3 IN before it sends alt 0, so the device counts EP3 IN
overruns at every stream close (Bryan T, 27 Sep 2026: +2..+4 per close,
none while running). The close-time delta is reported separately.

EP3 IN's drain rate (`consumed` per second) is the discriminating number
for the half-speed report: the device produces 44,100 frames/s into that
ring whatever the host does; `consumed` is what the endpoint actually sent.

  tools/hw/usb_probe.py --list-devices     # find the CoreAudio name
  tools/hw/usb_probe.py --unit mkii --json out/probe_mkii.json

Needs: `brew install portaudio`, then
`python3 -m pip install --user --break-system-packages sounddevice numpy pyusb`
(libusb is found as tools/hw/usb_counters.py finds it; its docstring has
the Intel/arm64 note for this Mac).

`0x56` STALLs (reported, not fatal) on an image with no USB AUDIO IN; the
EP3 OUT section of the report is then empty. `0x55` STALLs on an image with
no USB AUDIO at all.

Attach the --json report to the issue or PR thread with the unit
(MKI/MKII), the macOS version and the host app.
"""
import argparse
import glob
import json
import platform
import struct
import subprocess
import sys
import threading
import time

import numpy as np

# USB AUDIO IN's counters (0x56), the EP3 OUT ring: usbaudio_in.s in_counters
IN_RING_NAMES = ("produced", "consumed", "pkts", "lastn", "lastfill", "underruns", "overruns",
                 "reprimes", "bad", "frames", "seconds", "minfill", "maxfill", "err", "partial")
# USB AUDIO's counters (0x55), the EP3 IN ring: usbaudio.s
AUDIO_NAMES = ("consumed", "acc", "overruns", "underruns", "lastn", "lastfill", "lastbank",
               "bankdup", "lastsamp", "srcjump", "reprimes", "minfill", "maxfill", "anchor", "produced")
# the host -> unit stream's channel count is read from the CoreAudio device
# (2 with USB AUDIO IN AB or IN CD, 4 with IN ABCD)

EXPECTED_RATE = 44100.0


def find_device():
    import usb.core
    import usb.backend.libusb1
    libs = (glob.glob("/usr/local/opt/libusb/lib/libusb-1.0.dylib") + glob.glob("/opt/homebrew/opt/libusb/lib/libusb-1.0.dylib")
            + glob.glob("/usr/local/lib/libusb-1.0*.dylib") + glob.glob("/usr/local/Cellar/libusb/*/lib/libusb-1.0*.dylib")
            + glob.glob("/opt/homebrew/lib/libusb-1.0*.dylib") + glob.glob("/opt/homebrew/Cellar/libusb/*/lib/libusb-1.0*.dylib"))
    backend = usb.backend.libusb1.get_backend(find_library=lambda _: libs[0]) if libs else None
    dev = usb.core.find(idVendor=0x1935, idProduct=0x0002, backend=backend)
    if dev is None:
        sys.exit("no Octatrack on USB (1935:0002) -- is it connected and enumerated?")
    return dev


def read_counters(dev, ep3out):
    """ep3out: USB AUDIO IN's ring (0x56); else USB AUDIO's EP3 IN ring (0x55)."""
    req, names = (0x56, IN_RING_NAMES) if ep3out else (0x55, AUDIO_NAMES)
    n = 4 * len(names)
    raw = bytes(dev.ctrl_transfer(0xc0, req, 0, 0, n, timeout=1000))
    if len(raw) != n:
        raise RuntimeError(f"{len(raw)} bytes back for {'EP3 OUT' if ep3out else 'EP3 IN'} counters, expected {n}")
    return dict(zip(names, struct.unpack(f">{len(names)}I" if ep3out else f">{len(names)}i", raw)))


class Poller(threading.Thread):
    """Polls both counter sets on a fixed interval until told to stop.
    Each STALL (an image missing that vendor request) is recorded once and
    then that ring is skipped for the rest of the run, so a probe on an
    older image still reports what it can."""

    def __init__(self, dev, interval):
        super().__init__(daemon=True)
        self.dev, self.interval = dev, interval
        self.samples = []   # (t, EP3 IN counters or None, EP3 OUT counters or None)
        self.errors = []
        self._stop = threading.Event()
        self._have_in = self._have_out = True
        self.t0 = time.monotonic()

    def run(self):
        self.t0 = time.monotonic()
        while not self._stop.is_set():
            t = time.monotonic() - self.t0
            ci = co = None
            if self._have_in:
                try:
                    ci = read_counters(self.dev, ep3out=False)
                except Exception as e:  # noqa: BLE001
                    self.errors.append((t, "in", str(e)))
                    self._have_in = False
            if self._have_out:
                try:
                    co = read_counters(self.dev, ep3out=True)
                except Exception as e:  # noqa: BLE001
                    self.errors.append((t, "out", str(e)))
                    self._have_out = False
            self.samples.append((t, ci, co))
            self._stop.wait(self.interval)

    def stop(self):
        self._stop.set()


def list_devices():
    import sounddevice as sd
    for i, d in enumerate(sd.query_devices()):
        print(f"{i}: {d['name']!r}  in={d['max_input_channels']} out={d['max_output_channels']}"
              f" default_sr={d['default_samplerate']}")


def find_output_device(name_substr):
    """(device index, its output channel count)."""
    import sounddevice as sd
    devs = sd.query_devices()
    matches = [i for i, d in enumerate(devs) if name_substr.lower() in d["name"].lower() and d["max_output_channels"] > 0]
    if not matches:
        sys.exit(f"no CoreAudio output device matching {name_substr!r}; run --list-devices")
    if len(matches) > 1:
        sys.exit(f"{len(matches)} devices match {name_substr!r}: {[devs[i]['name'] for i in matches]}; be more specific")
    return matches[0], devs[matches[0]]["max_output_channels"]


def make_tone(duration, freq, level_dbfs, channel, n_channels, fs):
    amp = 10 ** (level_dbfs / 20)
    n = int(duration * fs)
    t = np.arange(n) / fs
    tone = (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)
    buf = np.zeros((n, n_channels), dtype=np.float32)
    buf[:, channel - 1] = tone
    return buf


def run_sustained(device, duration, freq, level_dbfs, channel, n_channels, fs=44100):
    import sounddevice as sd
    buf = make_tone(duration, freq, level_dbfs, channel, n_channels, fs)
    wall0 = time.monotonic()
    sd.play(buf, samplerate=fs, device=device, blocking=True)
    return {"wall_s": time.monotonic() - wall0, "cycles": 1, "requested_s": duration,
            "t_end": time.monotonic()}


def run_churn(device, cycles, on_s, off_s, freq, level_dbfs, channel, n_channels, fs=44100):
    import sounddevice as sd
    buf = make_tone(on_s, freq, level_dbfs, channel, n_channels, fs)
    wall0 = time.monotonic()
    for _ in range(cycles):
        sd.play(buf, samplerate=fs, device=device, blocking=True)   # each call opens and closes the stream
        if off_s:
            time.sleep(off_s)
    return {"wall_s": time.monotonic() - wall0, "cycles": cycles, "requested_s": cycles * (on_s + off_s),
            "t_end": time.monotonic()}


def host_fingerprint():
    info = {"platform": platform.platform(), "python": sys.version.split()[0]}
    try:
        import sounddevice as sd
        info["sounddevice"] = sd.__version__
        info["portaudio"] = sd.get_portaudio_version()[1]
    except Exception:  # noqa: BLE001
        pass
    try:
        info["macos_version"] = subprocess.run(["sw_vers", "-productVersion"], capture_output=True, text=True, timeout=2).stdout.strip()
    except Exception:  # noqa: BLE001
        pass
    return info


def summarize(samples, errors, t_open_end):
    """Deltas over the polls taken while the stream was open (t <= t_open_end),
    plus what the close added (the last poll against the last open one)."""
    while_open = [smp for smp in samples if smp[0] <= t_open_end]
    ep3in = [(t, c) for t, c, _ in while_open if c is not None]
    ep3out = [(t, c) for t, _, c in while_open if c is not None]
    summary = {"ep3_in": None, "ep3_out": None, "at_close": None, "poll_errors": len(errors)}
    if len(ep3in) >= 2:
        (t0, c0), (t1, c1) = ep3in[0], ep3in[-1]
        dt = t1 - t0
        d_produced = c1["produced"] - c0["produced"]
        d_consumed = c1["consumed"] - c0["consumed"]
        summary["ep3_in"] = {
            "poll_span_s": dt,
            "produced_delta": d_produced,
            "consumed_delta": d_consumed,
            "produced_rate_hz": d_produced / dt if dt > 0 else None,
            "consumed_rate_hz": d_consumed / dt if dt > 0 else None,
            "drain_ratio": (d_consumed / dt / EXPECTED_RATE) if dt > 0 else None,
            "overruns_delta": c1["overruns"] - c0["overruns"],
            "underruns_delta": c1["underruns"] - c0["underruns"],
            "bankdup_delta": c1["bankdup"] - c0["bankdup"],
            "reprimes_delta": c1["reprimes"] - c0["reprimes"],
        }
    if len(ep3out) >= 2:
        (t0, c0), (t1, c1) = ep3out[0], ep3out[-1]
        summary["ep3_out"] = {
            "produced_delta": c1["produced"] - c0["produced"],
            "underruns_delta": c1["underruns"] - c0["underruns"],
            "overruns_delta": c1["overruns"] - c0["overruns"],
            "bad_delta": c1["bad"] - c0["bad"],
            "minfill_final": c1["minfill"],
            "maxfill_final": c1["maxfill"],
        }
    last_in = [c for _, c, _ in samples if c is not None]
    if ep3in and last_in:
        summary["at_close"] = {"ep3_in_overruns": last_in[-1]["overruns"] - ep3in[-1][1]["overruns"],
                               "ep3_in_reprimes": last_in[-1]["reprimes"] - ep3in[-1][1]["reprimes"]}
    return summary


def verdict(play_result, summary):
    """The wall/requested ratio means device pacing in sustained mode only:
    in churn mode each cycle opens a fresh CoreAudio stream, and that
    per-cycle cost is the host's (100 cycles add 10-20 s), so the EP3
    counters carry the verdict there and the ratio is informational."""
    ratio = play_result["wall_s"] / play_result["requested_s"] if play_result["requested_s"] else None
    reasons = []
    if play_result["cycles"] == 1 and ratio is not None and not (0.9 <= ratio <= 1.1):
        reasons.append(f"wall/requested ratio {ratio:.3f} is outside 0.9-1.1 (the reported failure was 0.48-0.63)")
    ir = summary.get("ep3_in")
    if ir:
        dr = ir.get("drain_ratio")
        if dr is not None and dr < 0.9:
            reasons.append(f"EP3 IN drained {dr:.2f}x the expected 44,100 frames/s while the stream was open")
        if ir["overruns_delta"] > 0 or ir["bankdup_delta"] > 0:
            reasons.append(f"EP3 IN overruns +{ir['overruns_delta']}, bankdup +{ir['bankdup_delta']} while the stream was open"
                            " (the reported failure's signature)")
    orr = summary.get("ep3_out")
    if orr and orr["bad_delta"] > 0:
        reasons.append(f"EP3 OUT bad packets +{orr['bad_delta']}")
    if reasons:
        return "MATCHES_REPORTED_FAILURE", reasons
    if ratio is None or ir is None:
        return "AMBIGUOUS", ["not enough counter data to judge (STALLs or too few polls -- see poll_errors)"]
    return "CLEAN", ["ratio near 1.0, EP3 IN drained at rate, no overrun/bankdup/bad growth on either ring"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", choices=("sustained", "churn"), default="sustained")
    ap.add_argument("--duration", type=float, default=10.0, help="sustained mode: requested playback length, seconds")
    ap.add_argument("--churn-cycles", type=int, default=100, help="churn mode: number of open/close cycles")
    ap.add_argument("--churn-on", type=float, default=0.3, help="churn mode: seconds of tone per cycle")
    ap.add_argument("--churn-off", type=float, default=0.1, help="churn mode: silent pause between cycles")
    ap.add_argument("--freq", type=float, default=440.0, help="tone frequency, Hz")
    ap.add_argument("--level", type=float, default=-20.0, help="tone level, dBFS")
    ap.add_argument("--channel", type=int, default=1, help="host output channel, 1..n (the unit's input in the IN module's order); the others silent")
    ap.add_argument("--poll-interval", type=float, default=0.1, help="seconds between counter polls")
    ap.add_argument("--device", default="Octatrack", help="substring matching the CoreAudio device name")
    ap.add_argument("--unit", choices=("mki", "mkii", "unknown"), default="unknown",
                     help="which hardware this is -- can't be read over USB, please set it")
    ap.add_argument("--build-note", default="", help="free text: image/build number, remix name, etc.")
    ap.add_argument("--json", type=str, default=None, help="write a structured report here")
    ap.add_argument("--list-devices", action="store_true", help="list CoreAudio devices and exit")
    args = ap.parse_args()

    if args.list_devices:
        list_devices()
        return 0

    dev = find_device()
    device, n_channels = find_output_device(args.device)
    if not 1 <= args.channel <= n_channels:
        sys.exit(f"--channel {args.channel}: the device has {n_channels} output channel(s)")

    poller = Poller(dev, args.poll_interval)
    poller.start()
    if args.mode == "sustained":
        print(f"[sustained] {args.freq} Hz at {args.level} dBFS on channel {args.channel}, "
              f"requesting {args.duration:.1f} s, polling every {args.poll_interval*1000:.0f} ms ...")
        play_result = run_sustained(device, args.duration, args.freq, args.level, args.channel, n_channels)
    else:
        print(f"[churn] {args.churn_cycles} cycles of {args.churn_on}s on / {args.churn_off}s off, "
              f"{args.freq} Hz at {args.level} dBFS on channel {args.channel} ...")
        play_result = run_churn(device, args.churn_cycles, args.churn_on, args.churn_off, args.freq, args.level, args.channel, n_channels)
    time.sleep(0.3)   # a couple more polls after the close, for at_close
    poller.stop()
    poller.join(timeout=2)

    # the poller's clock is its own start; play_result's t_end is monotonic
    t_open_end = play_result["t_end"] - poller.t0 - args.poll_interval
    summary = summarize(poller.samples, poller.errors, t_open_end)
    verdict_str, reasons = verdict(play_result, summary)

    ratio = play_result["wall_s"] / play_result["requested_s"] if play_result["requested_s"] else float("nan")
    note = "" if play_result["cycles"] == 1 else "  (informational only in churn mode -- per-cycle stream-open overhead inflates this; see EP3 counters)"
    print(f"\nwall clock: {play_result['wall_s']:.2f} s over {play_result['cycles']} cycle(s), "
          f"requested {play_result['requested_s']:.2f} s (ratio {ratio:.3f}){note}")
    if summary["ep3_in"]:
        ir = summary["ep3_in"]
        print(f"EP3 IN (to the host):  produced +{ir['produced_delta']} consumed +{ir['consumed_delta']} over "
              f"{ir['poll_span_s']:.2f}s open (drained {ir['consumed_rate_hz']:.0f}/s, ratio {ir['drain_ratio']:.3f}); "
              f"overruns +{ir['overruns_delta']} underruns +{ir['underruns_delta']} "
              f"bankdup +{ir['bankdup_delta']} reprimes +{ir['reprimes_delta']}")
    else:
        print("EP3 IN (to the host):  no data (STALLed: the image has no USB AUDIO?)")
    if summary["ep3_out"]:
        orr = summary["ep3_out"]
        print(f"EP3 OUT (from the host): produced +{orr['produced_delta']}, underruns +{orr['underruns_delta']} "
              f"overruns +{orr['overruns_delta']} bad +{orr['bad_delta']}, "
              f"minfill/maxfill {orr['minfill_final']}/{orr['maxfill_final']}")
    else:
        print("EP3 OUT (from the host): no data (STALLed: the image has no USB AUDIO IN?)")
    if summary["at_close"]:
        ac = summary["at_close"]
        print(f"at stream close: EP3 IN overruns +{ac['ep3_in_overruns']} reprimes +{ac['ep3_in_reprimes']} "
              f"(the host stops polling before alt 0; not part of the verdict)")
    if poller.errors:
        print(f"{len(poller.errors)} poll error(s) during the run (see JSON for detail)")

    print(f"\nVERDICT: {verdict_str}")
    for r in reasons:
        print(f"  - {r}")

    if args.json:
        report = {
            "mode": args.mode,
            "params": vars(args),
            "host": host_fingerprint(),
            "unit": args.unit,
            "build_note": args.build_note,
            "play_result": play_result,
            "summary": summary,
            "poll_errors": poller.errors,
            "verdict": verdict_str,
            "verdict_reasons": reasons,
        }
        with open(args.json, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
