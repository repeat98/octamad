#!/usr/bin/env python3
"""Copy the generated stress project into a CF BURN measurement fixture."""
import argparse
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import toolpath  # noqa: E402,F401
from hw import ot_project as otp  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", type=pathlib.Path, default=ROOT / "out/stress-project")
    ap.add_argument("--out", type=pathlib.Path, required=True)
    ap.add_argument("--burn", type=int, default=0)
    ap.add_argument("--fine", type=int, default=0)
    args = ap.parse_args()
    if not all(0 <= v <= 127 for v in (args.burn, args.fine)):
        ap.error("BURN and FINE must be 0..127")
    if args.out.exists():
        ap.error(f"{args.out} exists; choose a new destination")
    if not (args.source / "bank01.work").is_file():
        ap.error("source must be a generated stress project")
    shutil.copytree(args.source, args.out)

    def detach_controls(data, bank_number):
        # Keep three T8 LFOs active, but move the third off FX2 BURN.
        for part in range(otp.NPARTS_ALL):
            base = otp.PART_BASE + part * otp.PART_STRIDE
            target = base + otp.LFO_PM_OFF + 7 * 30 + 2
            if data[target] != 24:
                raise ValueError(f"bank{bank_number:02d} part {part + 1}: unexpected T8 LFO target")
            data[target] = 20
        if bank_number == 1:
            for pat, count in enumerate((16, 32, 64, 64)):
                track = otp.trac_off(pat, 7)
                for step in range(count):
                    data[track + 0x59 + step * 32 + 24] = 0xff

    for number in range(1, 17):
        otp._bank_write(args.out, number,
                        lambda data, n=number: detach_controls(data, n), guard=False)
    otp.set_fx(args.out, "fx2", 8, "CF BURN",
               page=[args.burn, args.fine, 0, 0, 0, 0], guard=False)
    print(f"CF BURN measurement project: {args.out}")


if __name__ == "__main__":
    main()
