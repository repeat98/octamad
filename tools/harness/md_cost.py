#!/usr/bin/env python3
"""WP-A6: what the Machinedrum costs core 1 under the firmware's own dispatch.

    MD_EMU=... OT_PROJECT=... python3 tools/harness/md_cost.py [--frames 1400] [--kits all]

Stages OT_PROJECT with T1 MACHINEDRUM in every Part of bank 1 (as
verify_md_seq does), pokes a 16-part kit into md_kit and a pattern with
every lane on every step into md_patterns[0] after the load, runs the
sequencer at 300 BPM and times the MD's driver call in the glue (the jsr
at P:0x360fb and gdone after it) with the port's stopwatch
(docs/history/COLDFIRE_PORT.md O13): half of the sixteen slots a call, one
call a frame. The glue around it adds the mix, 32 x (2 + 16 x 4 + 3) =
2,208 instructions every second frame (69 a sample), and the record
packets. Windows that end at the dispatcher's P:0x303 are not usable: MD
code passes through that address too (pairs of 23 instructions, 25 Sep
2026).

The unit is executed DSP instructions (the port models no stall). The same
unit read BusVerb at 1,109 per sample where the hardware burn sweep
measured about 1,650 cycles (CHIP.md section 2), so cycles are inferred as
instructions / 0.68, and the budget is the burn-sweep ceiling, about 3,120
cycles per sample for all of core 1's effect work.
"""
import argparse
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/verify"))
sys.path.insert(0, str(ROOT / "tools/hw"))
import verify_md_kit as kit  # noqa: E402

OUT = ROOT / "out/mdverify/a6"
BPM = 300
KITS = {
    "default8": [0x10, 0x11, 0x16, 0x17, 0x13, 0x14, 0x15, 0x18] + [0] * 8,
    "trx16": [0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17, 0x18, 0x19, 0x1a, 0x1b, 0x1c, 0x1d, 0x10, 0x11],
    "efm16": [0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27] * 2,
    "pi16": [0x40, 0x41, 0x42, 0x43, 0x44, 0x45, 0x46, 0x47, 0x48, 0x40, 0x41, 0x42, 0x43, 0x44, 0x45, 0x46],
    "efmcb16": [0x25] * 16,
    "mixed16": [0x10, 0x11, 0x16, 0x17, 0x13, 0x14, 0x15, 0x18, 0x20, 0x21, 0x26, 0x27, 0x40, 0x41, 0x48, 0x19],
}


def engine_defaults():
    lines = (ROOT / "out/machinedrum/handlers.s").read_text().splitlines()
    i = next(k for k, l in enumerate(lines) if l.startswith("md_engines:"))
    out, k = {}, i + 1
    while k < len(lines) and len(out) < 0x49 and not lines[k].startswith("        .global"):
        m = re.match(r"\s+\.long (\S+)\s+\| (0x[0-9a-f]+) (\S+)", lines[k])
        if m:
            out[int(m.group(2), 16)] = [int(x) for x in lines[k + 1].split(".byte")[1].split(",")]
            k += 5
        else:
            k += 1
    return out


def kit_blob(engines, defaults):
    blob = bytearray()
    for e in engines:
        syn = defaults.get(e, [0] * 8) if e else [0] * 8
        blob += bytes((e, 100 if e else 0, 64, 0, *syn))
    return bytes(blob)


def pattern_blob(engines):
    blob = bytearray()
    for p in range(16):
        bits = 0xffff if engines[p] else 0          # every step of a 16-step pattern
        blob += bits.to_bytes(4, "big") + (0).to_bytes(4, "big")
    return bytes(blob) + bytes((0, 0xff, 0, 0)) * 64


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--frames", type=int, default=1400)
    ap.add_argument("--kits", default="all")
    ap.add_argument("--project", default=os.environ.get("OT_PROJECT", ""))
    ap.add_argument("--watch", default="1:360fb:360fc")
    a = ap.parse_args()
    import ot_project as otp
    OUT.mkdir(parents=True, exist_ok=True)
    image = OUT / "image.bin"
    shutil.copy2(ROOT / "out/mainos_bus.bin", image)
    proj = OUT / "project"
    if proj.exists():
        shutil.rmtree(proj)
    shutil.copytree(pathlib.Path(a.project).expanduser(), proj)
    for part in range(1, 5):
        otp.set_md_machine(proj, 1, part, 1, guard=False)
    otp.set_pattern_scale(proj, 1, 0, 16, 2, guard=False)
    otp.set_tempo(proj, BPM)
    card = OUT / "card.img"
    subprocess.run([sys.executable, str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(proj),
                    "OCTABAM", "RIG", "--tree", str(OUT / "tree"), "--out", str(card)],
                   check=True, capture_output=True, cwd=ROOT)
    cf, _ = kit.symbols()
    defaults = engine_defaults()
    names = list(KITS) if a.kits == "all" else a.kits.split(",")
    results = {}
    for name in names:
        engines = KITS[name]
        pokes = [(cf["md_kit"], kit_blob(engines, defaults)), (cf["md_patterns"], pattern_blob(engines))]
        poke = ";".join(f"{addr + i:#x}={b:#x}" for addr, data in pokes for i, b in enumerate(data))
        log = OUT / f"{name}.txt"
        cmd = [str(kit.EMU), "--image", str(image), "--card", str(card), "--set", "OCTABAM",
               "--project", "RIG", "--sequencer", "--internal-clock", "--frames", str(a.frames),
               "--load-ms", "20000", "--dsp", "--dsp-stopwatch", a.watch, "--poke", poke]
        with open(log, "w") as f:
            f.write(" ".join(cmd) + "\n"); f.flush()
            subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
        text = log.read_text()
        m = re.search(r"dsp stopwatch: \S+ -- (\d+) pair\(s\), instructions per pair mean (\d+) min (\d+) max (\d+)", text)
        last = re.search(r"last 24:([ \d]+)", text)
        if not m:
            print(f"{name}: no stopwatch line -- {log}")
            continue
        pairs, mean, lo, hi = map(int, m.groups())
        recent = [int(x) for x in last.group(1).split()] if last else []
        per_frame = mean * pairs / a.frames      # calls per frame vary (a trig splits a frame)
        results[name] = {"pairs": pairs, "mean": mean, "min": lo, "max": hi, "recent": recent,
                         "per_frame_mean": per_frame, "per_sample_mean": per_frame / 16,
                         "per_sample_max_call": hi / 16, "cycles_max_inferred": hi / 16 / 0.68}
        print(f"{name:9} {pairs:5} calls, mean {mean:6}/call, {per_frame:7.0f}/frame -> {per_frame / 16:5.0f} instr/sample; "
              f"worst call {hi:6} -> {hi / 16:5.0f} instr/sample, ~{hi / 16 / 0.68:5.0f} cycles (inferred); min {lo}")
        print(f"          last calls: {recent}")
    (OUT / "results.json").write_text(json.dumps(results, indent=1))


if __name__ == "__main__":
    main()
