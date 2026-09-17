#!/usr/bin/env python3
"""Build, exercise and audition the Tape Echo Spring-Reverb replacement.

The gates are intentionally structural rather than a claim that the desktop
reference's detailed transport behaviour was reproduced:

* MIX=0 is bit-exact dry;
* an impulse reaches head 1 at FREE TIME=0's 2048-sample delay;
* the 1+2 mask produces both the first and the 1.96875x head; and
* detail-page DRIVE softens overload and AGE reduces repeat bandwidth;
* FREE and BEAT time changes take the shared fractional motor step; and
* BEAT at 120 BPM reaches the 11,000-sample three-head safety ceiling.

It also writes a self-contained technical audition: four short, decaying
three-note strikes through all heads, feedback and wow.  No external stem is
required, so the result is reproducible on a fresh checkout.

    python3 tools/verify/verify_tapeecho.py
    python3 tools/verify/verify_tapeecho.py --wav out/tapeecho-technical-audition.wav
"""

from __future__ import annotations

import argparse
import math
import os
import pathlib
import struct
import subprocess
import sys
import tempfile
import wave

# OCTAMAD_ROOT lets the same checked-out verifier run from a Windows-mounted
# source path against a WSL checkout that contains the DSP toolchain.
ROOT = pathlib.Path(os.environ.get(
    "OCTAMAD_ROOT", pathlib.Path(__file__).resolve().parents[2])).resolve()
sys.path.insert(0, str(ROOT / "tools")); import toolpath  # noqa: E402,F401
import send_probe  # noqa: E402
from remix import registry  # noqa: E402

HOST = ROOT / "vendor/dsp56300/build/source/dsp_host/dsp_host"
IMAGE = ROOT / "out/mainos_bus.bin"
MEM = ROOT / "out/dsp/_tapeecho_A.mem"
MOD = registry.by_name("tapeecho")
SEND = registry.by_name("send")
K = MOD.knob_map()

SR, FRAMES, WARM_BLOCKS = 44100, 15, 300
WARM = FRAMES * WARM_BLOCKS
QMAX = 8388607
DEFAULTS = [(p.default or 0) for p in MOD.params]


def q(x: float) -> int:
    return max(-QMAX - 1, min(QMAX, round(x * QMAX)))


def build() -> tuple[int, int]:
    """Build this remix and resolve its real dispatch entries."""
    env = {**os.environ, "REMIX": "tapeecho"}
    r = subprocess.run([sys.executable, "tools/build/build_bus.py"], cwd=ROOT,
                       env=env, capture_output=True, text=True)
    if r.returncode:
        sys.exit("Tape Echo build failed:\n" + (r.stdout + r.stderr)[-3000:])
    send_probe.dump_mem(IMAGE, MEM, "A")
    init, proc = send_probe.entry_points(MEM, MOD.menu.fx2_id)
    send_ep = send_probe.entry_points(MEM, SEND.menu.fx2_id)
    if (init, proc) == send_ep:
        sys.exit("Tape Echo resolves to the fallback SEND entry -- refusing to test dry audio")
    return init, proc


def render(init: int, proc: int, samples: list[int], *, tempo: int | None = None,
           **over: int) -> tuple[list[int], list[int], str]:
    """Run one FX2 Tape Echo instance through the host's recovered ABI."""
    values = list(DEFAULTS)
    for name, value in over.items():
        values[K[name]] = value
    if len(samples) % FRAMES:
        samples = samples + [0] * (FRAMES - len(samples) % FRAMES)
    with tempfile.TemporaryDirectory(prefix="tapeecho_") as td:
        td = pathlib.Path(td)
        src, out = td / "in.raw", td / "out.raw"
        src.write_bytes(struct.pack(f"<{len(samples)}i", *samples))
        cmd = [str(HOST), "-mem", str(MEM), "-init", f"{init:x}",
               "-proc", f"{proc:x}", "-inst", "1", "-r7", "2", "-alloc", "1",
               "-inmask", "1", "-frames", str(FRAMES),
               "-blocks", str(len(samples) // FRAMES), "-in", str(src),
               "-out", str(out), "-params", ",".join(map(str, values))]
        if tempo is not None:
            cmd += ["-tempo", str(tempo)]
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        if r.returncode:
            sys.exit(f"dsp_host failed for {over}:\n{r.stdout[-2500:]}{r.stderr[-1500:]}")
        raw = out.read_bytes()
        words = struct.unpack(f"<{len(raw) // 4}i", raw)
        return list(words[0::2])[:len(samples)], list(words[1::2])[:len(samples)], r.stdout


def first_motor_step(init: int, proc: int, *, time: int, sync: int,
                     tempo: int | None = None) -> tuple[int, int]:
    """Exercise a live parameter change and return (actual, target) delay.

    Two harness instances intentionally share one r7 block only for this
    state test.  The first call holds FREE TIME=0; the second call changes to
    the requested target.  As soon as warm-up finishes, tracking the Q15.8
    r7+$21 position captures the real DSP's first audio-rate motor ramp.
    """
    low = list(DEFAULTS)
    high = list(DEFAULTS)
    for values in (low, high):
        values[K["FDBK"]] = 0
        values[K["WOW"]] = 0
        values[K["HEADS"]] = 0
        values[K["MIX"]] = 0
    low[K["TIME"]], low[K["SYNC"]] = 0, 0
    high[K["TIME"]], high[K["SYNC"]] = time, sync
    with tempfile.TemporaryDirectory(prefix="tapeecho_motor_") as td:
        track = pathlib.Path(td) / "motor.txt"
        cmd = [str(HOST), "-mem", str(MEM), "-init", f"{init:x}",
               "-proc", f"{proc:x}", "-inst", "2", "-alloc", "1,3",
               "-r7", "2,2", "-frames", str(FRAMES), "-blocks", "130",
               "-in", "-,-", "-params", ",".join(map(str, low)),
               "-params", ",".join(map(str, high)),
               "-track", "21,33,34", "-trackinst", "1",
               "-trackout", str(track)]
        if tempo is not None:
            cmd += ["-tempo", str(tempo)]
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        if r.returncode:
            sys.exit("motor trace failed:\n" + r.stdout[-2000:] + r.stderr[-1000:])
        rows = [tuple(map(int, line.split())) for line in track.read_text().splitlines()]
        live = next((row for row in rows if row[3] == 1), None)
        if live is None:
            sys.exit("motor trace never left tape warm-up")
        _block, actual, target, _ready = live
        return actual, target


def first_signal(samples: list[int], start: int, end: int, threshold: int = 2048) -> int | None:
    for i in range(max(0, start), min(len(samples), end)):
        if abs(samples[i]) > threshold:
            return i
    return None


def plucks(seconds: float = 1.5, tail: float = 3.0) -> list[int]:
    """Four small decaying chord strikes, preceded by the required warm-up."""
    n = WARM + round((seconds + tail) * SR)
    out = [0] * n
    starts = (WARM, WARM + round(0.36 * SR), WARM + round(0.72 * SR),
              WARM + round(1.08 * SR))
    for at in starts:
        for i in range(at, min(n, at + round(0.52 * SR))):
            t = (i - at) / SR
            # A tiny 220/277/330-Hz strike stays well inside the limiting
            # write path but gives the tape heads something musical to repeat.
            out[i] += q(0.24 * math.exp(-7.5 * t) * (
                0.62 * math.sin(2 * math.pi * 220.0 * t)
                + 0.26 * math.sin(2 * math.pi * 277.18 * t)
                + 0.12 * math.sin(2 * math.pi * 329.63 * t)))
    return [max(-QMAX - 1, min(QMAX, x)) for x in out]


def write_wav(path: pathlib.Path, left: list[int], right: list[int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = bytearray()
    for l, r in zip(left[WARM:], right[WARM:]):
        body += struct.pack("<hh", max(-32768, min(32767, l >> 8)),
                            max(-32768, min(32767, r >> 8)))
    with wave.open(str(path), "wb") as f:
        f.setnchannels(2); f.setsampwidth(2); f.setframerate(SR)
        f.writeframes(body)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wav", type=pathlib.Path,
                    default=ROOT / "out/tapeecho-technical-audition.wav")
    a = ap.parse_args()
    if not HOST.exists():
        sys.exit(f"missing {HOST.relative_to(ROOT)} -- run make setup")
    init, proc = build()
    print(f"entries: init=P:0x{init:04x}, proc=P:0x{proc:04x}, id=0x{MOD.menu.fx2_id:02x}")

    fails = 0
    def check(name: str, ok: bool, detail: str = "") -> None:
        nonlocal fails
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}{'  ' + detail if detail else ''}")
        fails += not ok

    # MIX=0 must not alter either sign or channel, including while the tape
    # warm-up declines to process its first 256 blocks.
    ramp = [((i * 1_103_515 + 12_345) & 0xffffff) - 0x800000
            for i in range(WARM + 900)]
    l, r, _ = render(init, proc, ramp, MIX=0, FDBK=127, WOW=127, HEADS=6, SYNC=0)
    check("MIX=0 is bit-exact dry", l[:len(ramp)] == ramp and r[:len(ramp)] == ramp)

    # One head, no feedback/modulation: the earliest wet sample is the line
    # delay itself.  AGE at its default starts at 1/4 of the impulse, so 2K is a
    # comfortably low threshold without mistaking numerical residue for sound.
    impulse = [0] * (WARM + 5000); impulse[WARM] = q(0.5)
    l, _r, _ = render(init, proc, impulse, TIME=0, FDBK=0, WOW=0,
                      MIX=127, HEADS=0, SYNC=0)
    first = first_signal(l, WARM + 2000, WARM + 2100)
    check("head 1 is a 2048-sample FREE repeat", first == WARM + 2048,
          f"first wet sample {None if first is None else first - WARM}")

    l, _r, _ = render(init, proc, impulse, TIME=0, FDBK=0, WOW=0,
                      MIX=127, HEADS=3, SYNC=0)
    h1 = first_signal(l, WARM + 2000, WARM + 2100)
    h2 = first_signal(l, WARM + 4000, WARM + 4100)
    check("1+2 mask emits 1.00x and 1.96875x heads",
          h1 == WARM + 2048 and h2 == WARM + 4032,
          f"heads {None if h1 is None else h1 - WARM}, {None if h2 is None else h2 - WARM}")

    # Detail-page character controls must reach their packed DSP fields.
    # DRIVE changes only the record curve; AGE changes the playback one-pole.
    clean, _r, _ = render(init, proc, impulse, TIME=0, FDBK=0, WOW=0,
                          MIX=127, HEADS=0, SYNC=0, DRIVE=0, AGE=64)
    driven, _r, _ = render(init, proc, impulse, TIME=0, FDBK=0, WOW=0,
                           MIX=127, HEADS=0, SYNC=0, DRIVE=127, AGE=64)
    at = WARM + 2048
    clean_peak, driven_peak = abs(clean[at]), abs(driven[at])
    check("detail DRIVE increases soft compression", driven_peak < clean_peak,
          f"first hit {clean_peak} -> {driven_peak}")

    fresh, _r, _ = render(init, proc, impulse, TIME=0, FDBK=0, WOW=0,
                          MIX=127, HEADS=0, SYNC=0, DRIVE=0, AGE=0)
    worn, _r, _ = render(init, proc, impulse, TIME=0, FDBK=0, WOW=0,
                         MIX=127, HEADS=0, SYNC=0, DRIVE=0, AGE=127)
    fresh_peak, worn_peak = abs(fresh[at]), abs(worn[at])
    check("detail AGE reduces repeat bandwidth", fresh_peak > 2 * worn_peak,
          f"first hit {fresh_peak} -> {worn_peak}")

    synced = [0] * (WARM + 12500); synced[WARM] = q(0.5)
    l, _r, _ = render(init, proc, synced, tempo=120, TIME=112, FDBK=0,
                      WOW=0, MIX=127, HEADS=0, SYNC=1)
    beat = first_signal(l, WARM + 10950, WARM + 11050)
    check("BEAT 1/8 at 120 BPM reaches the 11,000-sample safety cap",
          beat == WARM + 11000,
          f"first wet sample {None if beat is None else beat - WARM}")

    # The first call seeds 2048 samples in Q15.8. The second call computes a
    # per-sample velocity of error/65536 and applies it to all 15 frames.
    actual, target = first_motor_step(init, proc, time=127, sync=0)
    expected = (2048 << 8) + ((((10176 - 2048) << 8) >> 16) * FRAMES)
    check("FREE TIME changes slew through the tape motor",
          (actual, target) == (expected, 10176),
          f"first step {actual / 256:.3f} samples, target {target}")
    actual, target = first_motor_step(init, proc, time=112, sync=1, tempo=120)
    expected = (2048 << 8) + ((((11000 - 2048) << 8) >> 16) * FRAMES)
    check("BEAT TIME changes slew through the same tape motor",
          (actual, target) == (expected, 11000),
          f"first step {actual / 256:.3f} samples, target {target}")

    src = plucks()
    l, r, meter = render(init, proc, src, TIME=64, FDBK=96, WOW=56,
                          MIX=110, HEADS=6, SYNC=0)
    write_wav(a.wav, l, r)
    peak = max(max(map(abs, l[WARM:])), max(map(abs, r[WARM:]))) / QMAX
    print(f"  [WAV] {a.wav}  {len(l) - WARM} frames, peak {20 * math.log10(max(peak, 1e-12)):.1f} dBFS")
    meter_line = next((line.strip() for line in meter.splitlines()
                        if "instructions/sample" in line), "meter unavailable")
    print(f"  [METER] {meter_line}")

    print(f"\n{fails} gate(s) failed" if fails else "\nOK")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
