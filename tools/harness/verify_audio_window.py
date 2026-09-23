#!/usr/bin/env python3
"""Compare an explicit post-transport PCM window in stock/candidate/stock WAVs.

This is a separate oracle from benchmark_stock_analysis.py's strict whole-WAV
gate. It never relabels a failed whole-capture comparison as a pass.
"""

import argparse
import hashlib
from pathlib import Path
import re
import wave

NAMES = ("stock-a", "candidate", "stock-b")
START_RE = re.compile(r"audio out\s*:.*transport start at frame (\d+)")


def transport_start(log: Path) -> int:
    matches = START_RE.findall(log.read_text())
    if len(matches) != 1:
        raise ValueError(f"expected one transport-start record in {log}")
    return int(matches[0])


def compare(run: Path, frames: int) -> dict:
    if frames < 1:
        raise ValueError("frames must be positive")
    starts = [transport_start(run / f"{name}.log") for name in NAMES]
    if len(set(starts)) != 1:
        raise ValueError(f"transport starts differ: {starts}")
    start = starts[0]
    # An Octatrack frame contains 16 audio sample frames.
    sample_count = frames * 16
    chunks = []
    lengths = []
    formats = []
    for name in NAMES:
        with wave.open(str(run / f"{name}_core0.wav"), "rb") as wav:
            fmt = (wav.getnchannels(), wav.getsampwidth(), wav.getframerate())
            formats.append(fmt)
            lengths.append(wav.getnframes())
            if wav.getnframes() < start + sample_count:
                raise ValueError(f"{name} ends before requested window: "
                                 f"{wav.getnframes()} < {start + sample_count}")
            wav.setpos(start)
            chunks.append(wav.readframes(sample_count))
    if len(set(formats)) != 1 or formats[0] != (8, 3, 44100):
        raise ValueError(f"unexpected or unequal WAV formats: {formats}")
    expected_bytes = sample_count * formats[0][0] * formats[0][1]
    if any(len(chunk) != expected_bytes for chunk in chunks):
        raise ValueError("short PCM read")
    hashes = [hashlib.sha256(chunk).hexdigest() for chunk in chunks]
    return {
        "window_equal": chunks[0] == chunks[1] == chunks[2],
        "window_non_silent": any(chunks[0]),
        "transport_start_sample": start,
        "window_cpu_frames": frames,
        "window_audio_samples": sample_count,
        "window_sha256": dict(zip(NAMES, hashes)),
        "full_capture_samples": dict(zip(NAMES, lengths)),
        "full_capture_lengths_equal": len(set(lengths)) == 1,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--frames", type=int, required=True,
                    help="number of complete 16-sample post-transport frames")
    args = ap.parse_args()
    result = compare(args.run, args.frames)
    for key, value in result.items():
        print(f"{key}: {value}")
    if not result["window_equal"] or not result["window_non_silent"]:
        raise SystemExit(1)
    if not result["full_capture_lengths_equal"]:
        print("NOTE: whole-capture lengths differ; strict benchmark gate remains failed")


if __name__ == "__main__":
    main()
