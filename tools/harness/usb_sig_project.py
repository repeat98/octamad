#!/usr/bin/env python3
"""A project where every track plays its own steady tone: the USB AUDIO
channel-mapping and click fixture (the shape of octemu's `sig8` set).

  python3 tools/harness/usb_sig_project.py --source <a local project> [--out out/usb-sig-project]

Eight FLEX tracks, sample slot N on track N, one trig on step 1 of A01 with
the sample looping, so each track sounds continuously once PLAY is
pressed: track N's left channel at 200 + 100·N Hz, its right at +50 Hz
(T1 300/350 … T8 1000/1050), −12 dBFS, two-second loops. FX1 and FX2 sit
at their manifest defaults (the stations are bit-exact passthroughs there,
SEND at 0), so what the USB stream carries is the tone itself: a steady
sine has a tiny 99th-percentile sample step, and a click stands out from
it by orders of magnitude (`tools/harness/click_scan.py`). Channel 2N-1
must carry 200 + 100·N Hz and channel 2N that plus 50, which is what
`verify_usb_sig` (below) measures under the port.

The template stays local (Elektron bytes); `out/` holds the result. The
generated `AUDIO/USBSIG/T<n>.wav` files go in the SET's AUDIO folder on
the card (the [SAMPLE] paths are `../AUDIO/USBSIG/T<n>.wav`, which the
unit and the port both resolve to the set's AUDIO; `docs/firmware/STORAGE.md`
4), the `.work`/`.strd` files in `PRESETS/<project>/`.
"""
import argparse
import math
import pathlib
import re
import shutil
import struct
import sys
import wave

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import toolpath  # noqa: E402,F401
from hw import ot_bank as bank  # noqa: E402
from hw import ot_project as otp  # noqa: E402
from remix import registry  # noqa: E402

FRAMES = 88200
FX1 = ("MODULATION", "SPECTRUM", "MODULATION", "SPECTRUM", "CHARACTER", "CHARACTER", "CHARACTER", "CHARACTER")
FX2 = ("DELAY SERVER", "SEND", "SEND", "SEND", "REVERB SERVER", "SEND", "SEND", "SEND")


def tone(track):
    return 200 + 100 * (track + 1), 250 + 100 * (track + 1)


def make_sample(path, track):
    fl, fr = tone(track)
    amp = 0.25 * 32767
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(44100)
        out = bytearray()
        for n in range(FRAMES):
            out += struct.pack("<hh", int(amp * math.sin(2 * math.pi * fl * n / 44100)),
                               int(amp * math.sin(2 * math.pi * fr * n / 44100)))
        w.writeframes(out)


def set_project_text(dest):
    blocks = b"".join(("[SAMPLE]\r\nTYPE=FLEX\r\nSLOT=%03d\r\nPATH=../AUDIO/USBSIG/T%d.wav"
                       "\r\nTRIM_BARSx100=100\r\nLOOP_BARSx100=100\r\nBPMx24=2880"
                       "\r\nTSMODE=0\r\nLOOPMODE=1\r\nGAIN=48"
                       "\r\nTRIGQUANTIZATION=-1\r\n[/SAMPLE]\r\n\r\n" % (t + 1, t + 1)).encode()
                      for t in range(8))
    for path in (dest / "project.work", dest / "project.strd"):
        if not path.exists():
            continue
        raw = path.read_bytes()
        for t in range(8):
            raw = re.sub(rb"\[SAMPLE\]\r?\nTYPE=FLEX\r?\nSLOT=%03d\r?\n.*?\[/SAMPLE\]\r?\n\r?\n" % (t + 1),
                         b"", raw, flags=re.S)
        at = raw.find(b"[SAMPLE]")
        if at < 0:
            raise ValueError(f"{path}: no sample section")
        raw = raw[:at] + blocks + raw[at:]
        for key, val in ((b"BANK", b"0"), (b"PATTERN", b"0"), (b"TRACK", b"0")):
            raw, count = re.subn(rb"(\r?\n)" + key + rb"=\d+", lambda m: m.group(1) + key + b"=" + val, raw, count=1)
            if count != 1:
                raise ValueError(f"{path}: no {key.decode()} key")
        raw = raw.replace(b"MASTER_TRACK=1", b"MASTER_TRACK=0")
        path.write_bytes(raw)
    otp.set_tempo(dest, 120)


def set_markers(dest):
    for path in (dest / "markers.work", dest / "markers.strd"):
        if not path.exists():
            continue
        data = bytearray(path.read_bytes())
        for t in range(8):
            offset = 0x16 + t * 784          # FLEX slot t+1, 784-byte marker record
            data[offset:offset + 784] = struct.pack(">III", 0, FRAMES, 0) + bytes(772)
        data[-2:] = (sum(data[0x10:-2]) & 0xFFFF).to_bytes(2, "big")
        path.write_bytes(data)


def mutate_bank(data, bank_number, mods):
    bank.check_tags(data)
    for part in range(otp.NPARTS_ALL):
        base = otp.PART_BASE + part * otp.PART_STRIDE
        for track in range(8):
            fx1 = otp.module_defaults(mods[FX1[track]])
            fx2 = otp.module_defaults(mods[FX2[track]], {"SEND": 0})
            data[base + otp.FX1_OFF + track] = mods[FX1[track]].menu.fx2_id
            data[base + otp.FX2_OFF + track] = mods[FX2[track]].menu.fx2_id
            p1 = base + otp.P1_OFF + track * otp.TRACK_STRIDE
            p2 = base + otp.P2_OFF + track * otp.P2_STRIDE
            data[p1:p1 + 12] = fx1[:6] + fx2[:6]
            data[p2:p2 + 12] = fx1[6:] + fx2[6:]
            data[base + otp.MTYPE_OFF + track] = 1          # FLEX
            data[base + 0x2d3 + track * 5 + 1] = track       # slot N on track N (0-based index)
            data[base + 0x01b + track * 2] = 100             # AMP VOL: the tones are -12 dBFS already
            setup = base + 0x1e3 + track * 30 + 6
            values = base + 0x033 + track * 30 + 6
            data[setup] = 1          # LOOP on
            data[setup + 4] = 0      # TSTR off
            data[values] = 64        # PTCH neutral
            data[values + 3] = 127   # RATE forward
    for pat in range(16):
        tail = bank.PTRN_BASE + pat * bank.PTRN_STRIDE + bank.PTRN_STRIDE - 5
        data[tail] = 0
        for track in range(8):
            off = otp.trac_off(pat, track)
            data[off:off + 64] = bytes(64)
            data[off + 0x59:off + 0x59 + 64 * 32] = bytes([0xff]) * (64 * 32)
            if bank_number == 1 and pat == 0:
                data[off + 7] |= 1               # one trig on step 1: the loop carries on


def verify(dest, mods):
    for num in range(1, 17):
        for suffix in ("work", "strd"):
            path = dest / f"bank{num:02d}.{suffix}"
            if not path.exists():
                continue
            data = path.read_bytes()
            bank.check_tags(data)
            assert int.from_bytes(data[-2:], "big") == sum(data[0x10:-2]) & 0xffff, path
            for part in range(otp.NPARTS_ALL):
                base = otp.PART_BASE + part * otp.PART_STRIDE
                for track in range(8):
                    assert data[base + otp.FX1_OFF + track] == mods[FX1[track]].menu.fx2_id
                    assert data[base + otp.FX2_OFF + track] == mods[FX2[track]].menu.fx2_id
                    assert data[base + 0x2d3 + track * 5 + 1] == track
            if suffix != "work":
                continue
            for pat in range(16):
                for track in range(8):
                    trigs = bank.trigs(data, pat, track)
                    assert len(trigs) == (1 if num == 1 and pat == 0 else 0), (path, pat, track, trigs)
                    assert not bank.locks(data, pat, track)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", type=pathlib.Path, required=True, help="a locally saved Octatrack project (the template)")
    ap.add_argument("--out", type=pathlib.Path, default=ROOT / "out/usb-sig-project")
    ap.add_argument("--remix", default="usb-audio")
    args = ap.parse_args()
    source, dest = args.source.resolve(), args.out.resolve()
    if dest.exists():
        ap.error(f"{dest} exists; choose a new --out directory")
    if not (source / "project.work").is_file() or not (source / "bank01.work").is_file():
        ap.error("source needs project.work and bank01.work")
    remix = registry.remix(args.remix)
    mods = registry.modules()
    if not all(k in remix.modules for k in set(FX1 + FX2)):
        ap.error(f"{args.remix} no longer contains the required modules")
    dest.mkdir(parents=True)
    for src in source.iterdir():
        if src.is_file() and src.suffix in (".work", ".strd"):
            shutil.copy2(src, dest / src.name)
    set_project_text(dest)
    set_markers(dest)
    for num in range(1, 17):
        otp._bank_write(dest, num, lambda data, n=num: mutate_bank(data, n, mods), guard=False)
    otp.write_stored(dest)
    verify(dest, mods)
    for t in range(8):
        make_sample(dest / "AUDIO" / "USBSIG" / f"T{t + 1}.wav", t)
    lines = [f"T{t + 1}: L {tone(t)[0]} Hz  R {tone(t)[1]} Hz  -> USB channels {2 * t + 1}/{2 * t + 2}" for t in range(8)]
    (dest / "USBSIG_README.txt").write_text("USB AUDIO signal project: one steady stereo tone per track, A01 step 1, looping.\n"
                                            + "\n".join(lines) + "\n"
                                            "Card: AUDIO/USBSIG/T*.wav into the SET's AUDIO folder; the .work/.strd files into PRESETS/<name>/.\n")
    print("\n".join(lines))
    print(dest)


if __name__ == "__main__":
    main()
