#!/usr/bin/env python3
"""Reproducible stock/candidate/stock software comparison; never flashes.

Run make bus REMIX=stock-analysis-fast and verify_stock_analysis.py first.
Use --project to stage a COPY as an eight-track FLEX fixture, or --card to
reuse a previously generated card image (specify its set/project names).
A fresh --out is required so another run's evidence cannot be silently
overwritten.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import wave

from profile_stock import ROOT, digest


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    source = ap.add_mutually_exclusive_group(required=True)
    source.add_argument("--project", type=Path)
    source.add_argument("--card", type=Path)
    ap.add_argument("--card-set", default="OCTABAM")
    ap.add_argument("--card-project", default="POLYBENCH")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--frames", type=int, default=5600)
    args = ap.parse_args()
    if args.frames<2: ap.error("at least two frames are required")
    out = args.out.resolve()
    if not out.is_relative_to(ROOT/"out"):
        ap.error("--out must be a new directory inside the repo's ignored out/")
    out.mkdir(parents=True, exist_ok=False)
    if args.project:
        from benchmark_polyphony import fixture, stage_fixture
        tone = out/"tone.wav"
        fixture.make_loop(tone)
        card = stage_fixture(args.project.resolve(), out, "mono", 1, tone)
    else:
        card = args.card.resolve()
    stock = ROOT/"out/raw/section_3_MAIN_OS.bin"
    candidate = ROOT/"out/stock-profile/candidate-raw.bin"
    placement = ROOT/"out/stock-profile/candidate-map.json"
    emu = ROOT/"out/emu/ot_emu"
    metadata = dict(units="emulator instructions, not hardware cycles", hardware_measured=False,
                    frames=args.frames, card_set=args.card_set, card_project=args.card_project,
                    card_sha256=digest(card), emulator_sha256=digest(emu),
                    git_head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
                    source_sha256={str(p.relative_to(ROOT)):digest(p) for p in sorted(
                        [*ROOT.glob("tools/emu/ot_emu/*.*"), *ROOT.glob("modules/stock-analysis-fast/*.*"),
                         ROOT/"tools/harness/profile_stock.py", Path(__file__).resolve()]) if p.is_file()},
                    runs=[])
    for label,image in (("stock-a",stock),("candidate",candidate),("stock-b",stock)):
        prefix=out/label
        command=[str(emu),"--image",str(image),"--card",str(card),"--set",args.card_set,
                 "--project",args.card_project,"--sequencer","--internal-clock","--frames",str(args.frames),
                 "--load-ms","20000","--dsp","--main-level","64","--work-profile",str(prefix),
                 "--audio-out",str(prefix)]
        print(f"Running {label} ({args.frames} frames)...",flush=True)
        with prefix.with_suffix(".log").open("w") as log:
            result=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        log_text=prefix.with_suffix(".log").read_text()
        if result.returncode or "run ended REACHED" not in log_text:
            raise RuntimeError(f"Incomplete run; inspect {prefix}.log")
        summary=prefix.with_suffix(".json")
        parse=[sys.executable,str(ROOT/"tools/harness/profile_stock.py"),"--prefix",str(prefix),
               "--frames",str(args.frames),"--image",str(image),"--card",str(card),"--json",str(summary)]
        if label=="candidate": parse += ["--candidate-map",str(placement)]
        subprocess.run(parse,cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
        wav=Path(str(prefix)+"_core0.wav")
        with wave.open(str(wav),"rb") as audio:
            if not any(audio.readframes(audio.getnframes())):
                raise RuntimeError("Silent capture is not an audio-equivalence test")
        data=json.loads(summary.read_text())
        metadata["runs"].append(dict(label=label,command=command,image_sha256=digest(image),
                                     audio_sha256=digest(wav),profile_sha256=digest(str(prefix)+".cpu.tsv"),
                                     total=data["total"],per_frame=data["per_frame"],
                                     cpu_frames=data["complete_frames"]["cpu"]))
        (out/"result.json").write_text(json.dumps(metadata,indent=2)+"\n")
    a,b,c=metadata["runs"]
    metadata["audio_identical"] = a["audio_sha256"]==b["audio_sha256"]==c["audio_sha256"]
    metadata["stock_repeat_identical"] = a["profile_sha256"]==c["profile_sha256"]
    metadata["fewer_instructions_percent"] = 100*(a["total"]-b["total"])/a["total"]
    (out/"result.json").write_text(json.dumps(metadata,indent=2)+"\n")
    if not metadata["audio_identical"] or not metadata["stock_repeat_identical"]:
        raise RuntimeError("Audio or repeatability check failed; do not claim equivalence")
    print(f"PASS: identical audio and repeatable stock; {metadata['fewer_instructions_percent']:.3f}% fewer CPU instructions")
    print("Hardware savings remain unmeasured.")


if __name__=="__main__":
    main()
