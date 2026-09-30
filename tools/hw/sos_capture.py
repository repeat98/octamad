#!/usr/bin/env python3
"""The sound-on-sound loop, captured sample-exact on a unit and compared with
the port running the same project on the same input.

The remix `sos-capture` (or any image with USB AUDIO IN AB and USB AUDIO OUT
TRACKS) takes the host's stereo stream on inputs A/B and sends the sixteen
track channels back, both 24-bit and digital end to end. The signal:

  L  a 997 Hz sine, -20 dBFS (not a divisor of any bar at any tempo, so a
     wrap that skips or repeats a sample shows in a two-tap predictor)
  R  a ramp of K per sample from -(K*N/2), N samples long, one value per
     input sample, so every sample T1 plays names the input sample it was
     recorded from (with the path's gain fitted out)

for SIG seconds, then silence: from the pass after the last one recorded
with signal, the loop only recirculates, and at unity feedback consecutive
passes are the same audio except where the loop is wrong.

  sos_capture.py fixture TEMPLATE OUT [--bpm 128] [--rlen 16] [--trigs 1]
      a copy of the project TEMPLATE with bank 1 pattern 1 in the primer's
      shape: T1 FLEX on R1, PLAY + REC1 (INAB) + REC3 (SRC3 = T1) on the trig
      steps, AMP VOL 127 locked there, FX1/FX2 NONE, R1 at 0 dB, LOOP off.
  sos_capture.py signal OUT.wav [--bpm 128] [--rlen 16] [--passes 2] [--seconds 40]
      the signal above (stereo, 24-bit) and OUT.json beside it.
  sos_capture.py capture SIGNAL.wav OUT.wav [--device Octatrack]
      plays SIGNAL into A/B and records the sixteen track channels for its
      length; reads USB AUDIO's and USB AUDIO IN's counters before and after
      when pyusb is there (a changed underrun/overrun count is a capture
      that dropped or repeated frames of its own).
  sos_capture.py port PROJECT SIGNAL.wav OUT.wav [--image out/mainos_bus.bin] [--delay N]
      the same project and signal under the port (out/emu/ot_emu): input
      A/B from the transport start, delayed by N samples; OUT.wav holds the
      sixteen track channels from the read-back the USB producer reads.
  sos_capture.py compare SIGNAL.wav A.wav [B.wav] [--track 1]
      per capture: the input sample at each arm; per recirculating pass, the
      largest difference from the pass before (after the best -2..+2 sample
      shift) and where it falls relative to the wrap. With B: the port
      delay that puts B's first arm on A's input sample, and, once they
      match, the samples where A and B differ.

On the unit: PLAY first, then `capture` (the signal starts at once; any
point in the pattern works, `compare` finds the arm). Then `port` with the
same project and `--delay` from the compare, then `compare` both.

Needs the .venv (numpy; sounddevice for `capture`), the port (make emu-cf)
for `port`, pyusb for the counters.
"""
import argparse
import json
import math
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import wave

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import toolpath  # noqa: E402,F401

FS = 44100
TONE_HZ = 997.0
TONE_AMP = 0.1
NTRACKS = 8
RB_CORE = {1: (0x80003190, 0x80003590), 0: (0x80003390, 0x80003790)}   # the read-back banks per core


def pass_len(bpm, rlen):
    return 60.0 / bpm / 4 * FS * rlen


# ---- WAV --------------------------------------------------------------------

def write_wav(path, x, width=3):
    """x: (frames, channels) int32 in 24-bit units."""
    x = np.asarray(x, np.int64)
    if x.ndim == 1:
        x = x[:, None]
    b = np.clip(x, -(1 << 23), (1 << 23) - 1).astype('<i4')
    raw = np.frombuffer(b.tobytes(), np.uint8).reshape(-1, 4)
    raw = raw[:, :3] if width == 3 else raw
    with wave.open(str(path), "wb") as w:
        w.setnchannels(x.shape[1]); w.setsampwidth(width); w.setframerate(FS)
        w.writeframes(raw.tobytes())


def read_wav(path):
    """-> (frames, channels) int64 in 24-bit units."""
    with wave.open(str(path)) as w:
        ch, width, n = w.getnchannels(), w.getsampwidth(), w.getnframes()
        raw = np.frombuffer(w.readframes(n), np.uint8)
    if width == 3:
        b = raw.reshape(-1, 3).astype(np.int64)
        v = b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)
        v = np.where(v >= 1 << 23, v - (1 << 24), v)
    elif width == 4:
        v = np.frombuffer(raw.tobytes(), '<i4').astype(np.int64) >> 8
    elif width == 2:
        v = np.frombuffer(raw.tobytes(), '<i2').astype(np.int64) << 8
    else:
        sys.exit(f"{path}: {width}-byte samples")
    return v.reshape(-1, ch)


# ---- fixture ----------------------------------------------------------------

def fixture(a):
    import ot_project as op
    import ot_spec
    src, out = pathlib.Path(a.template), pathlib.Path(a.out)
    if out.exists():
        sys.exit(f"{out} exists")
    shutil.copytree(src, out, ignore=shutil.ignore_patterns("._*"))
    trigs = [int(s) for s in a.trigs.split(",")]

    def clear_t1(data):
        for mask in (0x00, 0x20, 0x28, 0x30):
            base = op.trac_off(0, 0) + mask
            for k in range(8):
                data[base + k] = 0

    def r1_slot(data):                                  # T1 FLEX slot 129 = R1, part 1 and its saved copy
        for p in (0, op.NPARTS):
            data[op.PART_BASE + p * op.PART_STRIDE + 0x2d3 + op.SLOT_KIND["flex"]] = 128
    op._bank_write(out, 1, clear_t1, guard=False)
    op._bank_write(out, 1, r1_slot, guard=False)
    op.set_machine_type(out, 1, 1, 1, 1, guard=False)
    for step in trigs:
        for mask in (0x00, 0x20, 0x30):                 # PLAY, REC1, REC3
            op.set_pattern_trig(out, 1, 0, 0, step, mask, guard=False)
    op.set_recorder_setup(out, 1, 1, 0, "SRC3", 1, guard=False)       # T1
    op.set_recorder_setup(out, 1, 1, 0, "LOOP", 0, guard=False)
    op.set_recorder_setup(out, 1, 1, 0, "RLEN", a.rlen - 1, guard=False)
    op.set_pattern_scale(out, 1, 0, 16, "1X", guard=False)
    for slot in ("fx1", "fx2"):
        op.set_fx(out, slot, 1, 0, guard=False)
    op.set_tempo(out, a.bpm)
    for suffix in ("work", "strd"):                     # R1: TSMODE 0, LOOPMODE 0, GAIN 0 dB
        p = out / f"project.{suffix}"
        if not p.is_file():
            continue
        raw = p.read_bytes().decode("latin1")

        def attrs(m):
            s = re.sub(r"TSMODE=\d+", "TSMODE=0", m.group(0))
            s = re.sub(r"LOOPMODE=\d+", "LOOPMODE=0", s)
            return re.sub(r"GAIN=\d+", "GAIN=48", s)
        raw, k = re.subn(r"\[SAMPLE\][^\[]*?TYPE=FLEX[^\[]*?SLOT=129\b.*?\[/SAMPLE\]", attrs, raw, count=1, flags=re.S)
        if k != 1:
            sys.exit(f"{p}: no FLEX SLOT=129 sample block (R1) to set")
        p.write_bytes(raw.encode("latin1"))
    ot_spec.apply(out, {"banks": [1], "patterns": {"1": {"tracks": {"1": {
        "locks": {"amp": {str(s): {"VOL": 127} for s in trigs}}}}}}})
    print(f"{out}: T1 FLEX R1 (TSMODE 0, LOOP off, 0 dB), PLAY+REC1+REC3 (SRC3=T1) on step(s) {a.trigs}, "
          f"RLEN {a.rlen}, {a.bpm} BPM, AMP VOL 127 locked")


# ---- signal -----------------------------------------------------------------

def signal(a):
    P = pass_len(a.bpm, a.rlen)
    nsig = int(round(a.passes * P))
    ntot = max(nsig, int(a.seconds * FS))
    k = max(1, int((1 << 21) // nsig))                   # the ramp spans at most +-2^20 (-18 dBFS)
    n = np.arange(ntot)
    L = np.round(TONE_AMP * (1 << 23) * np.sin(2 * np.pi * TONE_HZ * n / FS)).astype(np.int64)
    fade = int(0.02 * FS)
    L[:fade] = L[:fade] * np.arange(fade) // fade
    L[nsig - fade:nsig] = L[nsig - fade:nsig] * np.arange(fade)[::-1] // fade
    R = k * n - k * nsig // 2
    L[nsig:] = 0; R[nsig:] = 0
    write_wav(a.out, np.stack([L, R], 1))
    meta = {"fs": FS, "tone_hz": TONE_HZ, "tone_amp": TONE_AMP, "ramp_k": int(k), "ramp_origin": int(-k * nsig // 2),
            "signal_samples": nsig, "total_samples": ntot, "bpm": a.bpm, "rlen": a.rlen, "pass": P}
    pathlib.Path(a.out).with_suffix(".json").write_text(json.dumps(meta, indent=1) + "\n")
    print(f"{a.out}: {ntot / FS:.1f} s, signal {nsig} samples ({a.passes} passes of {P:.3f}), ramp {k}/sample")


def load_meta(sig):
    p = pathlib.Path(sig).with_suffix(".json")
    if not p.is_file():
        sys.exit(f"{p}: missing (written by `signal` beside the WAV)")
    return json.loads(p.read_text())


# ---- capture ----------------------------------------------------------------

def _usb_dev():
    try:
        import glob
        import usb.backend.libusb1
        import usb.core
    except ImportError:
        return None
    libs = (glob.glob("/opt/homebrew/opt/libusb/lib/libusb-1.0.dylib") + glob.glob("/usr/local/opt/libusb/lib/libusb-1.0.dylib")
            + glob.glob("/usr/lib/*/libusb-1.0.so*") + glob.glob("/usr/lib/libusb-1.0.so*"))
    backend = usb.backend.libusb1.get_backend(find_library=lambda _: libs[0]) if libs else None
    return usb.core.find(idVendor=0x1935, idProduct=0x0002, backend=backend)


def _counters(dev):
    import usb_counters
    out = {}
    for host_in, tag in ((False, "out"), (True, "in")):
        try:
            out[tag] = usb_counters.read(dev, host_in)
        except Exception as e:  # noqa: BLE001 -- a STALL on an image without the module
            out[tag] = {"error": str(e)}
    return out


def capture(a):
    import sounddevice as sd
    sig = read_wav(a.signal)
    devs = sd.query_devices()
    idx = [i for i, d in enumerate(devs) if a.device.lower() in d["name"].lower()
           and d["max_input_channels"] >= 16 and d["max_output_channels"] >= 2]
    if len(idx) != 1:
        sys.exit(f"{len(idx)} devices match {a.device!r} with 16 inputs and 2 outputs: "
                 + ", ".join(f"{d['name']!r} in={d['max_input_channels']} out={d['max_output_channels']}" for d in devs))
    dev = _usb_dev()
    before = _counters(dev) if dev is not None else None
    out = sig.astype(np.float64) / (1 << 23)
    rec = sd.playrec(out.astype(np.float32), samplerate=FS, device=idx[0], channels=16, dtype="int32", blocking=True)
    after = _counters(dev) if dev is not None else None
    write_wav(a.out, np.asarray(rec, np.int64) >> 8)
    print(f"{a.out}: {len(rec)} frames x 16 channels from {devs[idx[0]]['name']!r}")
    if before is None:
        print("counters: pyusb/libusb not available -- check USB AUDIO's underruns/overruns with tools/hw/usb_counters.py")
        return
    for tag, keys in (("out", ("overruns", "underruns", "bankdup")), ("in", ("underruns", "overruns", "bad"))):
        b, f = before[tag], after[tag]
        if "error" in b or "error" in f:
            print(f"counters {tag}: {b.get('error') or f.get('error')}")
            continue
        d = {k: f[k] - b[k] for k in keys}
        print(f"counters {tag}: " + " ".join(f"{k} +{v}" for k, v in d.items())
              + ("" if not any(d.values()) else "   <- the capture itself dropped or repeated frames"))


# ---- port -------------------------------------------------------------------

def readback_tracks(dump):
    """The read-back arena under the port: every track's post-FX, pre-fader
    block (what USB AUDIO OUT TRACKS sends) -> (samples, 16) in 24-bit units."""
    import blockdump as bd
    c = bd.classes(bd.read(dump))
    out = []
    for t in range(1, NTRACKS + 1):
        core, pos = (0 if t >= 5 else 1), (t - 1) % 4
        blocks = sorted(sum((c.get(('<', 1, core, addr), []) for addr in RB_CORE[core]), []))
        ch = []
        for side in (0, 1):
            vals = []
            for _, w in blocks:
                w = np.asarray(w, np.int64)
                v = (w[0::2] << 8) | (w[1::2] >> 8)                       # hi/lo halfwords -> 24 bits
                v = np.where(v >= 1 << 23, v - (1 << 24), v)
                vals.append(v[pos * 32 + side: pos * 32 + 32: 2])
            ch.append(np.concatenate(vals) if vals else np.zeros(0, np.int64))
        out += ch
    n = min(len(x) for x in out)
    return np.stack([x[:n] for x in out], 1)


def port(a):
    meta = load_meta(a.signal)
    sig = read_wav(a.signal)
    emu = ROOT / "out/emu/ot_emu"
    if not emu.is_file():
        sys.exit(f"{emu}: build the port first (make emu-cf)")
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="sos_capture_"))
    proj = pathlib.Path(a.project)
    card = tmp / "card.img"
    subprocess.run([sys.executable, str(ROOT / "tools/emu/emu_card.py"), "--project", str(proj), "--set", "OCTABAM",
                    "--name", "SOSCAP", "--image", str(card), "--image-only"], check=True, stdout=subprocess.DEVNULL)
    n = len(sig) + a.delay
    four = np.zeros((n, 4), np.int64)                   # RX0 slots 2/3 = inputs A/B
    four[a.delay:, 2:] = sig
    inp = tmp / "in4.wav"
    write_wav(inp, four)
    frames = int(math.ceil(n / 16)) + 64
    dump = tmp / "run.bd"
    log = pathlib.Path(a.out).with_suffix(".log")
    cmd = [str(emu), "--image", str(a.image), "--card", str(card), "--set", "OCTABAM", "--project", "SOSCAP",
           "--sequencer", "--internal-clock", "--dsp", "--frames", str(frames), "--main-level", "64",
           "--load-ms", str(a.load_ms), "--pre-roll", "200", "--audio-in", str(inp), "--block-dump", str(dump)]
    with open(log, "w") as f:
        r = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT)
    text = log.read_text(errors="replace")
    if r.returncode != 0 or "saved_bank" not in text:
        sys.exit(f"the port run failed or the project did not load (exit {r.returncode}); see {log}")
    x = readback_tracks(dump)
    write_wav(a.out, x)
    shutil.rmtree(tmp)
    print(f"{a.out}: {len(x)} samples x 16 channels (input delay {a.delay}, signal {meta['signal_samples']}); log {log}")


# ---- compare ----------------------------------------------------------------

def decode_index(R, meta, lo, hi):
    """Fit R[lo:hi] = g * (k * (t + d) + origin): the input sample recorded at
    output sample t is t + d. -> (g, d, rms residual in 24-bit units)."""
    t = np.arange(lo, hi, dtype=np.float64)
    y = R[lo:hi].astype(np.float64)
    A = np.stack([t, np.ones_like(t)], 1)
    (s, c), *_ = np.linalg.lstsq(A, y, rcond=None)
    g = s / meta["ramp_k"]
    d = (c / g - meta["ramp_origin"]) / meta["ramp_k"] if g else float("nan")
    res = float(np.sqrt(np.mean((y - A @ np.array([s, c])) ** 2)))
    return g, d, res


def segments(R, meta):
    """The runs of R that hold ONE recording of the ramp, each a straight
    line at the path's gain: grown window by window while the line fitted
    so far predicts the next window to within 0.4 of one ramp step, then
    kept only at the gain of the first run (a feedback pass holds two
    recordings, whose sum is a line at about twice the gain).
    -> [(start, end, g, d)]: output sample t in [start, end) plays input t + d."""
    W, k = 512, meta["ramp_k"]
    nz = np.nonzero(R)[0]
    if not len(nz):
        return []
    runs, i, stop = [], nz[0], nz[-1]
    while i + 2 * W < stop:
        g, d, _ = decode_index(R, meta, i, i + W)
        if not np.isfinite(d) or abs(g) < 1e-3:
            i += W; continue
        tol = max(3.0, 0.4 * k * abs(g))
        j = i + W
        while j < len(R):
            t = np.arange(j, min(j + W, len(R)))
            e = np.abs(R[j:j + len(t)] - g * (k * (t + d) + meta["ramp_origin"]))
            bad = np.nonzero(e > tol)[0]
            if len(bad):
                j += int(bad[0]); break
            j += len(t)
            if j - i >= 4 * W:
                g, d, _ = decode_index(R, meta, i, j)
        if j - i >= 4 * W:
            runs.append((i, j, *decode_index(R, meta, i, j)[:2]))
        i = max(j, i + 1)
    if not runs:
        return []
    g0 = runs[0][2]
    return [r for r in runs if abs(r[2] / g0 - 1) < 0.05]


def loop_passes(L, first_wrap, P, count):
    """Consecutive recirculating passes. For pass k (from the k-th wrap
    after first_wrap) against pass k-1: per sample the smallest
    |difference| over shifts -2..+2 of the previous pass, so the loop's
    one-sample boundary walk drops out and a missing, repeated or foreign
    sample stays. -> [(k, largest as a fraction of rms, its offset in the
    pass, samples above 5 % of rms)]."""
    rows = []
    n = int(P) - 8
    for k in range(1, count):
        a0 = int(round(first_wrap + k * P)); b0 = int(round(first_wrap + (k - 1) * P))
        if a0 + n + 4 >= len(L) or b0 < 2:
            break
        cur = L[a0:a0 + n].astype(np.float64)
        rms = float(np.sqrt(np.mean(cur ** 2))) or 1.0
        e = np.min([np.abs(cur - L[b0 + s:b0 + s + n]) for s in range(-2, 3)], 0)
        m = int(np.argmax(e))
        rows.append((k, float(e[m]) / rms, m, int(np.count_nonzero(e > 0.05 * rms))))
    return rows


def analyse(name, x, meta, track):
    P = meta["pass"]
    L, R = x[:, 2 * (track - 1)], x[:, 2 * (track - 1) + 1]
    segs = segments(R, meta)
    print(f"{name}: T{track}, {len(x)} samples, {len(segs)} run(s) holding one recording of the ramp")
    for i, j, g, d in segs:
        print(f"  output {i:8d}..{j:8d}  gain {g:+.5f}  plays input sample (output {d:+.2f}); input {i + d:.1f}..{j + d:.1f}")
    if not segs:
        return None
    first_end = segs[0][1]
    rows = loop_passes(L, first_end, P, int((len(L) - first_end) / P))
    print(f"  passes after the first wrap (output {first_end}), each against the one before, L channel:")
    for k, rel, m, nbig in rows:
        print(f"  pass {k:3d}: largest {100 * rel:6.1f}% of rms at +{m} ({m if m < P / 2 else m - int(P)} from the wrap), "
              f"{nbig} sample(s) above 5%")
    return segs, rows, first_end


def compare(a):
    meta = load_meta(a.signal)
    A = read_wav(a.a)
    ra = analyse(pathlib.Path(a.a).name, A, meta, a.track)
    if not a.b:
        return
    B = read_wav(a.b)
    rb = analyse(pathlib.Path(a.b).name, B, meta, a.track)
    if not ra or not rb:
        sys.exit("no single-recording pass in one of the captures: nothing to align")
    (ia, ja, ga, da), (ib, jb, gb, db) = ra[0][0], rb[0][0]
    arm_a, arm_b = ja + da, jb + db                      # input sample at the end of the first pass, each side
    shift = int(round(arm_b - arm_a))
    print(f"input sample at the end of the first single-recording pass: A {arm_a:.2f}, B {arm_b:.2f}")
    if abs(shift) > 1:
        print(f"B's arm lands {shift:+d} input samples from A's: rerun `port` with --delay {shift} added to B's delay "
              f"(and {shift + int(round(meta['pass']))} if the pass lengths then alternate out of phase)")
        return
    off = int(round(ja - jb))                            # output alignment
    n = min(len(A) - max(off, 0), len(B) - max(-off, 0))
    a_ = A[max(off, 0):max(off, 0) + n, 2 * (a.track - 1):2 * a.track]
    b_ = B[max(-off, 0):max(-off, 0) + n, 2 * (a.track - 1):2 * a.track]
    d = np.nonzero(np.any(a_ != b_, 1))[0]
    P = meta["pass"]
    print(f"A and B aligned (output offset {off}): {len(d)} of {n} samples differ")
    if len(d):
        pos = [(int((i + max(off, 0) - ja) // P), int(round((i + max(off, 0) - ja) % P))) for i in d[:40]]
        print("  first differing samples (pass after A's first wrap, position in pass): " + " ".join(f"{p}:{q}" for p, q in pos))
        print(f"  max |A-B| {int(np.abs(a_ - b_).max())}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("fixture"); p.add_argument("template"); p.add_argument("out")
    p.add_argument("--bpm", type=float, default=128.0); p.add_argument("--rlen", type=int, default=16)
    p.add_argument("--trigs", default="1", help="comma-separated steps (1-16)")
    p = sub.add_parser("signal"); p.add_argument("out")
    p.add_argument("--bpm", type=float, default=128.0); p.add_argument("--rlen", type=int, default=16)
    p.add_argument("--passes", type=float, default=2.0, help="passes of signal before the silence")
    p.add_argument("--seconds", type=float, default=40.0, help="total length")
    p = sub.add_parser("capture"); p.add_argument("signal"); p.add_argument("out")
    p.add_argument("--device", default="Octatrack")
    p = sub.add_parser("port"); p.add_argument("project"); p.add_argument("signal"); p.add_argument("out")
    p.add_argument("--image", default=str(ROOT / "out/mainos_bus.bin"))
    p.add_argument("--delay", type=int, default=0, help="input delay after the transport start, samples")
    p.add_argument("--load-ms", type=int, default=20000)
    p = sub.add_parser("compare"); p.add_argument("signal"); p.add_argument("a"); p.add_argument("b", nargs="?")
    p.add_argument("--track", type=int, default=1)
    a = ap.parse_args()
    {"fixture": fixture, "signal": signal, "capture": capture, "port": port, "compare": compare}[a.cmd](a)


if __name__ == "__main__":
    main()
