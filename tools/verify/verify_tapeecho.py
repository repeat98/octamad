#!/usr/bin/env python3
"""Entry point for CPU Tape Echo verification (delegates to verify_tapeecho_cpu).

The functions below retain the previous DSP regression suite as reference;
they are not run against the CPU passthrough. Historical DSP coverage:

The gates are intentionally structural rather than a claim that the desktop
reference's detailed transport behaviour was reproduced:

* MIX=0 is bit-exact dry;
* two instances use different allocator-provided tape lines;
* an impulse reaches head 1 at FREE TIME=0's 2048-sample delay;
* the 1+2 mask produces both the first and the 1.96875x head; and
* detail-page DRIVE softens overload and AGE reduces repeat bandwidth;
* maximum feedback grows tape noise into limiter-bounded self-oscillation;
* fast-time maximum-feedback stress does not cut out or overflow;
* FREE time sweeps remain monotonic and cannot overshoot;
* every TIME value selects its BEAT division across slow/normal/fast tempos;
* BEAT heads mute-switch between divisions and rapid queued edits stay smooth;
* WOW produces smooth modulation on each head rather than sample jumps.

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
import re
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
MEMS = {p: ROOT / f"out/dsp/_tapeecho_{p}.mem" for p in "AB"}
MEM = MEMS["A"]
MOD = registry.by_name("tapeecho")
SEND = registry.by_name("send")
K = MOD.knob_map()

SR, FRAMES, WARM_BLOCKS = 44100, 16, 300
WARM = FRAMES * WARM_BLOCKS
QMAX = 8388607
DEFAULTS = [(p.default or 0) for p in MOD.params]


def q(x: float) -> int:
    return max(-QMAX - 1, min(QMAX, round(x * QMAX)))


def build() -> tuple[int, int]:
    """Build this remix and resolve its real dispatch entries."""
    env = {**os.environ, "REMIX": "repitch-tapeecho", "XBUS": "1", "SPEC": "1"}
    r = subprocess.run([sys.executable, "tools/build/build_bus.py"], cwd=ROOT,
                       env=env, capture_output=True, text=True)
    if r.returncode:
        sys.exit("Tape Echo build failed:\n" + (r.stdout + r.stderr)[-3000:])
    for payload, mem in MEMS.items():
        send_probe.dump_mem(IMAGE, mem, payload)
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
    """Automate one live instance and return its first changed block."""
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
        td = pathlib.Path(td)
        track, automation = td / "motor.txt", td / "params.csv"
        automation.write_text("129," + ",".join(map(str, high)) + "\n")
        cmd = [str(HOST), "-mem", str(MEM), "-init", f"{init:x}",
               "-proc", f"{proc:x}", "-inst", "1", "-alloc", "1",
               "-r7", "2", "-frames", str(FRAMES), "-blocks", "147",
               "-in", "-", "-params", ",".join(map(str, low)),
               "-paramfile", str(automation), "-track", "21,33,34",
               "-trackout", str(track)]
        if tempo is not None:
            cmd += ["-tempo", str(tempo)]
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        if r.returncode:
            sys.exit("motor trace failed:\n" + r.stdout[-2000:] + r.stderr[-1000:])
        rows = [tuple(map(int, line.split())) for line in track.read_text().splitlines()]
        observe = 145 if sync else 129
        changed = next((row for row in rows if row[0] == observe), None)
        if changed is None:
            sys.exit("motor trace did not reach automated change observation")
        _block, actual, target, _ready = changed
        return actual, target


def sweep_trace(init: int, proc: int, initial: dict[str, int],
                events: list[tuple[int, dict[str, int]]], blocks: int,
                tempo: int = 120, split: int = 0, frames: int = FRAMES) -> list[list[int]]:
    """Run one continuously stateful instance with block-timed knob edits."""
    values = list(DEFAULTS)
    for name, value in initial.items():
        values[K[name]] = value
    with tempfile.TemporaryDirectory(prefix="tapeecho_sweep_") as td:
        td = pathlib.Path(td)
        automation, trace = td / "params.csv", td / "trace.txt"
        rows = []
        current = list(values)
        for block, changes in events:
            for name, value in changes.items():
                current[K[name]] = value
            rows.append(f"{block}," + ",".join(map(str, current)))
        automation.write_text("\n".join(rows) + "\n")
        cmd = [str(HOST), "-mem", str(MEM), "-init", f"{init:x}",
               "-proc", f"{proc:x}", "-inst", "1", "-alloc", "1", "-r7", "2",
               "-frames", str(frames), "-split", str(split),
               "-blocks", str(blocks), "-in", "-",
               "-tempo", str(tempo), "-params", ",".join(map(str, values)),
               "-paramfile", str(automation),
               "-track", "21,22,23,38,39,3a,35,36,37,3c",
               "-trackout", str(trace)]
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        if r.returncode:
            sys.exit("automated Tape Echo sweep failed:\n" + r.stdout[-2500:] + r.stderr[-1000:])
        return [list(map(int, line.split())) for line in trace.read_text().splitlines()]


def sweep_audio(init: int, proc: int, initial: dict[str, int],
                events: list[tuple[int, dict[str, int]]], blocks: int,
                hz: float = 997, tempo: int = 120, split: int = 0,
                frames: int = FRAMES) -> list[int]:
    """Render a continuous tone through block-timed knob edits."""
    values = list(DEFAULTS)
    for name, value in initial.items():
        values[K[name]] = value
    samples = [q(0.3 * math.sin(2 * math.pi * hz * n / SR))
               for n in range(blocks * frames)]
    with tempfile.TemporaryDirectory(prefix="tapeecho_audio_sweep_") as td:
        td = pathlib.Path(td)
        automation, src, out = td / "params.csv", td / "in.raw", td / "out.raw"
        current, rows = list(values), []
        for block, changes in events:
            for name, value in changes.items():
                current[K[name]] = value
            rows.append(f"{block}," + ",".join(map(str, current)))
        automation.write_text("\n".join(rows) + "\n")
        src.write_bytes(struct.pack(f"<{len(samples)}i", *samples))
        cmd = [str(HOST), "-mem", str(MEM), "-init", f"{init:x}",
               "-proc", f"{proc:x}", "-inst", "1", "-alloc", "1", "-r7", "2",
               "-frames", str(frames), "-split", str(split),
               "-blocks", str(blocks), "-in", str(src),
               "-out", str(out), "-tempo", str(tempo),
               "-params", ",".join(map(str, values)), "-paramfile", str(automation)]
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        if r.returncode:
            sys.exit("automated Tape Echo audio sweep failed:\n" +
                     r.stdout[-2500:] + r.stderr[-1000:])
        raw = out.read_bytes()
        words = struct.unpack(f"<{len(raw) // 4}i", raw)
        return list(words[0::2])


def second_instance_output(init: int, proc: int, first_input: list[int]) -> bytes:
    """Render two tracks and return track 2's stereo output bytes.

    Track 1 gets ``first_input`` and track 2 gets silence. Repeating this with
    and without a track-1 impulse must leave track 2 bit-identical; that is the
    regression for the old fixed 32K line leaking one channel into another.
    """
    if len(first_input) % FRAMES:
        first_input += [0] * (FRAMES - len(first_input) % FRAMES)
    values = list(DEFAULTS)
    values[K["TIME"]] = 0
    values[K["FDBK"]] = 0
    values[K["WOW"]] = 0
    values[K["HEADS"]] = 0
    values[K["MIX"]] = 127
    with tempfile.TemporaryDirectory(prefix="tapeecho_pair_") as td:
        td = pathlib.Path(td)
        src, out = td / "first.raw", td / "pair.raw"
        src.write_bytes(struct.pack(f"<{len(first_input)}i", *first_input))
        cmd = [str(HOST), "-mem", str(MEM), "-init", f"{init:x}",
               "-proc", f"{proc:x}", "-inst", "2", "-alloc", "1,3",
               "-r7", "2,5", "-audioidx", "0,1", "-frames", str(FRAMES),
               "-blocks", str(len(first_input) // FRAMES),
               "-in", f"{src},-", "-out", str(out), "-guard", "16384",
               "-params", ",".join(map(str, values)),
               "-params", ",".join(map(str, values))]
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        violations = re.findall(r"(\d+) stray write regions, (\d+) CLOBBERING", r.stdout)
        if r.returncode or len(violations) != 2 or any(
                int(stray) or int(clobber) for stray, clobber in violations):
            sys.exit("two-instance render failed:\n" +
                     r.stdout[-3000:] + r.stderr[-1000:])
        return pathlib.Path(str(out) + ".i1").read_bytes()


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
    global MEM
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
    # warm-up declines to process its first 128 blocks.
    ramp = [((i * 1_103_515 + 12_345) & 0xffffff) - 0x800000
            for i in range(WARM + 900)]
    l, r, _ = render(init, proc, ramp, MIX=0, FDBK=127, WOW=127, HEADS=6, SYNC=0)
    check("MIX=0 is bit-exact dry", l[:len(ramp)] == ramp and r[:len(ramp)] == ramp)

    pair_n = WARM + 5000
    first_hot = [0] * pair_n
    first_hot[WARM] = q(0.8)
    track2_hot = second_instance_output(init, proc, first_hot)
    track2_silent = second_instance_output(init, proc, [0] * pair_n)
    check("two Tape Echo instances have isolated tape lines",
          track2_hot == track2_silent,
          f"track-2 bytes {'identical' if track2_hot == track2_silent else 'differ'}")

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

    # Maximum feedback is deliberately above unity. A small impulse and the
    # internal noise floor must grow, while the pre/post-curve limiting stores
    # keep the loop below full scale.
    ringing = [0] * (WARM + 10 * SR); ringing[WARM] = q(0.01)
    osc, _r, _ = render(init, proc, ringing, TIME=0, FDBK=127, WOW=0,
                         MIX=127, HEADS=0, SYNC=0, DRIVE=64, AGE=0)
    early = max(map(abs, osc[WARM + SR:WARM + 2 * SR]))
    late = max(map(abs, osc[WARM + 9 * SR:WARM + 10 * SR]))
    check("FDBK=127 grows into controlled self-oscillation",
          late > 2 * early and late <= QMAX,
          f"peak {20 * math.log10(max(early / QMAX, 1e-12)):.1f} -> "
          f"{20 * math.log10(max(late / QMAX, 1e-12)):.1f} dBFS")

    # Exercise short TIME, maximum feedback and a hot strike. This is a
    # numerical stress test, not a reproduction of the hardware dropout.
    stress = [0] * (WARM + 4 * SR)
    for i in range(WARM, WARM + SR // 4):
        stress[i] = q(0.85 * math.sin(2 * math.pi * 97 * (i - WARM) / SR))
    hot, _r, _ = render(init, proc, stress, TIME=0, FDBK=127, WOW=0,
                         MIX=127, HEADS=6, SYNC=0, DRIVE=0, AGE=0)
    tail = hot[WARM + 3 * SR:WARM + 4 * SR]
    check("fast-time self-oscillation stays live and bounded",
          max(map(abs, hot[WARM:])) <= QMAX and
          sum(abs(x) > 32 for x in tail) > len(tail) // 8,
          f"tail active {sum(abs(x) > 32 for x in tail)}/{len(tail)} samples")

    # Test INSIDE bands too: asr leaves a fractional A0, so comparing the
    # full accumulator against integers used to accept ONLY multiples of 16.
    # Both payloads and slow tempos matter: the previous tick representation
    # also saturated below ~54 BPM. Expected delays come from clock timing,
    # independent of the assembly's fixed-point representation (<=1 sample).
    for payload, mem in MEMS.items():
        MEM = mem
        pi, pp = send_probe.entry_points(mem, MOD.menu.fx2_id)
        for tempo in (30, 45, 120, 240):
            events = [(129 + time, {"TIME": time}) for time in range(128)]
            trace = sweep_trace(pi, pp,
                                dict(TIME=0, SYNC=1, FDBK=0, WOW=0,
                                     HEADS=0, MIX=0), events, 257, tempo)
            by_block = {row[0]: row for row in trace}
            bad = []
            for time in range(128):
                row = by_block[129 + time]
                clocks = (1.5, 2, 3, 4, 6, 8, 9, 12)[time // 16]
                want = min(11000, SR * 60 * clocks / (tempo * 24))
                if abs(row[4] / 256 - want) > 1:
                    bad.append((time, row[1] / 256, row[4] / 256,
                                round(want, 2)))
            check(f"{payload}: live sweep quantises all 128 BEAT TIME values at {tempo} BPM",
                  not bad, f"{len(bad)} mismatches" + (f": {bad[:4]}" if bad else ""))

            spaced_events = [(129 + 40 * band, {"TIME": 16 * band})
                             for band in range(8)]
            spaced = sweep_trace(pi, pp,
                                 dict(TIME=0, SYNC=1, FDBK=0, WOW=0,
                                      HEADS=0, MIX=0),
                                 spaced_events, 430, tempo)
            spaced_by_block = {row[0]: row for row in spaced}
            missed = [band for band in range(8)
                      if spaced_by_block[145 + 40 * band][1:4] !=
                      spaced_by_block[145 + 40 * band][4:7]]
            check(f"{payload}: BEAT heads snap at the mute point at {tempo} BPM",
                  not missed, f"missed bands {missed}")
            switch_gains = [row[10] for prev, row in zip(spaced, spaced[1:])
                            if row[1:4] != prev[1:4] and row[0] > 128]
            check(f"{payload}: BEAT tap switches occur near digital zero at {tempo} BPM",
                  bool(switch_gains) and max(switch_gains) <= 0x80000,
                  f"largest post-block gain {max(switch_gains, default=-1):#x}")

        free = sweep_trace(pi, pp,
                           dict(TIME=0, SYNC=0, FDBK=0, WOW=0,
                                HEADS=0, MIX=0),
                           [(129, {"TIME": 16}), (800, {"TIME": 0})],
                           1500)
        up = [row for row in free if 129 <= row[0] < 800]
        down = [row for row in free if row[0] >= 800]
        no_over = all(
            all(a[h] <= b[h] <= b[h + 3] for a, b in zip(up, up[1:])) and
            all(a[h] >= b[h] >= b[h + 3] for a, b in zip(down, down[1:]))
            for h in (1, 2, 3))
        check(f"{payload}: FREE motor sweep is monotonic and never overshoots",
              no_over, "up and down across all three heads")
        geometry_error = max(
            max(abs(row[2] - (2 * row[1] - (row[1] >> 5))),
                abs(row[3] - (row[2] + row[1] - (row[1] >> 7))))
            for row in free[128:])
        check(f"{payload}: FREE sweep uses one coherent transport ramp",
              geometry_error <= 1,
              f"largest fixed-point geometry error {geometry_error}/256 sample")

        # A pure sine obeys y[n] - 2*cos(w)*y[n-1] + y[n-2] = 0.
        # Smooth slow wow barely perturbs it; integer read jumps create large
        # impulses in this residual, even though ordinary harmonic THD misses
        # the clicks. Pin both effectiveness (nonzero change) and smoothness.
        hz = 997
        tone = [0] * WARM + [q(0.3 * math.sin(2 * math.pi * hz * n / SR))
                             for n in range(2 * SR)]
        c = 2 * math.cos(2 * math.pi * hz / SR)
        for head in range(3):
            common = dict(tempo=120, TIME=65, SYNC=1, FDBK=0, MIX=127,
                          HEADS=head, DRIVE=0, AGE=0)
            still, _, _ = render(pi, pp, tone, WOW=0, **common)
            wow, _, _ = render(pi, pp, tone, WOW=127, **common)
            start = WARM + 20000
            segment = wow[start:]
            residual = max(abs(segment[n] - c * segment[n - 1] + segment[n - 2])
                           for n in range(2, len(segment))) / QMAX
            change = math.sqrt(sum((a - b) ** 2 for a, b in
                                   zip(still[start:], wow[start:])) / len(segment)) / QMAX
            check(f"{payload}: WOW modulates head {head + 1} without read jumps",
                  change > 0.005 and residual < 0.0005,
                  f"change RMS {change:.5f} FS, click residual {residual:.6f} FS")

        # A quick panel sweep crosses a 16-value band roughly every four
        # 16-sample blocks after the stock parameter slew. Deliberately queue
        # several targets before the mute-switch envelope can finish.
        change_blocks = [350 + 4 * i for i in range(7)]
        swept = sweep_audio(pi, pp,
                            dict(TIME=1, SYNC=1, FDBK=0, WOW=0,
                                 HEADS=0, MIX=127, DRIVE=0, AGE=0),
                            [(block, {"TIME": 17 + 16 * i})
                             for i, block in enumerate(change_blocks)],
                            460, tempo=120)
        c = 2 * math.cos(2 * math.pi * 997 / SR)
        click_residual, click_at = max(
            (abs(swept[n] - c * swept[n - 1] + swept[n - 2]) / QMAX, n)
            for n in range(change_blocks[0] * FRAMES + 2, 420 * FRAMES))
        check(f"{payload}: rapid BEAT mute-switch sweep has no sharp discontinuity",
              click_residual < 0.002,
              f"peak sine-recurrence residual {click_residual:.6f} FS "
              f"at sample {click_at}")

        # Reproduce the panel report: go back to FREE part-way through BEAT's
        # down/up fade. A hard unity reset produced a 0.20 FS impulse here.
        # Cover both fade directions, a settled switch, the default 2+3 mask,
        # single/all heads, every trig split, and non-divisor callback sizes.
        worst = (0.0, None)
        gain_bad = []
        events = [(1400, {"SYNC": 1}), (1401, {"SYNC": 0}),
                  (1500, {"SYNC": 1}), (1508, {"SYNC": 0}),
                  (1600, {"SYNC": 1}), (1616, {"SYNC": 0}),
                  (1700, {"SYNC": 1}), (1724, {"SYNC": 0}),
                  (1800, {"SYNC": 1}), (1840, {"SYNC": 0})]
        for frames, split in [(16, s) for s in range(16)] + [(15, 0), (7, 0), (1, 0)]:
            # Short callbacks need enough samples to fill the longest tap.
            # Parameter events are specified in physical 16-sample blocks.
            scale = lambda b: b * FRAMES // frames
            ev = [(scale(b), changes) for b, changes in events]
            for heads in (0, 2, 4, 6):
                initial = dict(TIME=65, SYNC=0, FDBK=0, WOW=0,
                               HEADS=heads, MIX=127, DRIVE=0, AGE=0)
                audio = sweep_audio(pi, pp, initial, ev, scale(1950),
                                    frames=frames, split=split)
                peak = max(abs(audio[n] - c * audio[n - 1] + audio[n - 2]) / QMAX
                           for n in range(scale(1400) * frames, len(audio)))
                if peak > worst[0]:
                    worst = (peak, (frames, split, heads))
                if heads == 4:
                    state = sweep_trace(pi, pp, initial, ev, scale(1950),
                                        frames=frames, split=split)
                    if (any(not 0 <= row[10] <= QMAX for row in state)
                            or state[-1][10] != QMAX):
                        gain_bad.append((frames, split))
        check(f"{payload}: FREE/BEAT toggles remain continuous at every trig split",
              worst[0] < 0.006,
              f"peak recurrence residual {worst[0]:.6f} FS; frames/split/heads {worst[1]}")
        check(f"{payload}: interrupted fades stay within 0..1 and recover to unity",
              not gain_bad, f"bad callback configurations {gain_bad}")

        # Independent timing oracle from fx-dsp's first-playing-head rule.
        # This port retains its original physical head ratios; only the sync
        # anchor changes. Measure audio on every mask, not just state targets.
        masks = ((0,), (1,), (2,), (0, 1), (1, 2), (0, 2), (0, 1, 2))
        ratios = (1.0, 63 / 32, 379 / 128)
        misses = []
        for tempo, time in ((120, 17), (174, 65), (240, 113)):
            note = SR * 60 * (1.5, 2, 3, 4, 6, 8, 9, 12)[time // 16] / (tempo * 24)
            signal = [0] * (WARM + 16384)
            signal[WARM] = q(0.5)
            for heads, active in enumerate(masks):
                out, _, _ = render(pi, pp, signal, tempo=tempo, TIME=time,
                                  SYNC=1, HEADS=heads, FDBK=0, WOW=0,
                                  MIX=127, DRIVE=0, AGE=0)
                first = first_signal(out, WARM + 100, len(out))
                if first is None or abs(first - WARM - note) > 3:
                    misses.append((tempo, time, heads, first))
                for head in active[1:]:
                    expected = note * ratios[head] / ratios[active[0]]
                    arrival = first_signal(out, WARM + round(expected) - 4,
                                           WARM + round(expected) + 5)
                    if arrival is None or abs(arrival - WARM - expected) > 4:
                        misses.append((tempo, time, heads, head, arrival))
        check(f"{payload}: every head mask syncs its first playing head to the note",
              not misses, f"timing mismatches {misses[:8]}")

        # The generic dirty-state gate ends before this module's 128-call
        # warm-up finishes. Run past it with BEAT selected and compare audio
        # against a clean instance, so stale motor positions/velocity matter.
        signal = [0] * (WARM + 12000)
        signal[WARM] = q(0.5)
        clean, _, meter = render(pi, pp, signal, TIME=65, SYNC=1,
                                 HEADS=4, FDBK=0, WOW=0, MIX=127)
        state_at = int(re.search(r"r7 = X:0x([0-9a-f]+)", meter)[1], 16)
        dirty_ok = True
        with tempfile.TemporaryDirectory(prefix="tapeecho_dirty_") as td:
            blob = mem.read_bytes()
            assert blob[-9] == 0xff
            for fill in (0x7fffff, 0x800000, 0x5a5a5a):
                dirty = pathlib.Path(td) / f"{fill:x}.mem"
                dirty.write_bytes(blob[:-9] + struct.pack("<BII", 1, state_at, 0x100)
                                  + struct.pack("<I", fill) * 0x100 + blob[-9:])
                MEM = dirty
                out, _, _ = render(pi, pp, signal, TIME=65, SYNC=1,
                                   HEADS=4, FDBK=0, WOW=0, MIX=127)
                dirty_ok &= out == clean
            MEM = mem
        check(f"{payload}: saved BEAT selection is identical from dirty instance memory",
              dirty_ok)
    MEM = MEMS["A"]

    # Confirm the sync result reaches the AUDIO, not only the motor target.
    # Use interior knob values that failed on the old binary.
    for time, expected_delay in ((17, 1837), (65, 5512), (127, 11000)):
        signal = [0] * (WARM + 12000)
        signal[WARM] = q(0.5)
        wet, _, _ = render(init, proc, signal, tempo=120, TIME=time, SYNC=1,
                            HEADS=0, WOW=0, FDBK=0, MIX=127)
        at = first_signal(wet, WARM + 100, len(wet))
        check(f"BEAT TIME={time}: impulse arrives at the selected division",
              at == WARM + expected_delay,
              f"delay {None if at is None else at - WARM} samples")

    # One real instance changes after warm-up. FREE moves monotonically;
    # BEAT changes are exact on the first changed block.
    actual, target = first_motor_step(init, proc, time=127, sync=0)
    expected = (2048 << 8) + 32 * FRAMES
    check("FREE TIME changes slew through the tape motor",
          (actual, target) == (expected, 10176),
          f"first step {actual / 256:.3f} samples, target {target}")
    actual, target = first_motor_step(init, proc, time=112, sync=1, tempo=120)
    expected = 11000 << 8
    check("BEAT TIME snaps to its musical division at the mute point",
          (actual, target) == (expected, 11000),
          f"position {actual / 256:.3f} samples, target {target}")

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
    # Keep the DSP regression source as the previous implementation's record;
    # the shipping module now renders in the ColdFire delay stage.
    from verify_tapeecho_cpu import main as cpu_main
    raise SystemExit(cpu_main())
