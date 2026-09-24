#!/usr/bin/env python3
"""Build a repeatable, locally generated DSP and sequencer stress project.

The source template stays local and is never committed. Output belongs in out/.
"""
import argparse
import hashlib
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

SAMPLE_REL = "AUDIO/STRESS_LOOP.wav"
FRAMES = 88200
# On payload A, four Character instances run beside BusVerb. Payload B runs
# Modulation's phaser/comb/line paths beside BusDelay.
FX1 = ("MODULATION", "SPECTRUM", "MODULATION", "SPECTRUM",
       "CHARACTER", "CHARACTER", "CHARACTER", "CHARACTER")
FX2 = ("DELAY SERVER", "SEND", "SEND", "SEND",
       "REVERB SERVER", "SEND", "SEND", "SEND")
LOCK_SLOTS = (0, 3, 6, 7, 9, 10, 15, 16, 18, 19, 20, 21, 22, 23, 24)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_sample(path):
    """Two seconds of deterministic, low-level stereo content."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(44100)
        out = bytearray()
        for n in range(FRAMES):
            # Integer triangle plus two gated pulses keeps this cheap to
            # generate while providing edges and a sustained DSP input.
            phase = n % 200
            tri = (phase if phase < 100 else 200 - phase) - 50
            pulse = 1800 if n % 11025 < 100 else 0
            left = 70 * tri + pulse
            right = 70 * (((phase + 50) % 200) if (phase + 50) % 200 < 100
                          else 200 - (phase + 50) % 200) - 3500 - pulse
            out += struct.pack("<hh", left, right)
        wav.writeframes(out)


def set_project_text(dest):
    block = ("[SAMPLE]\r\nTYPE=FLEX\r\nSLOT=001\r\nPATH=../" + SAMPLE_REL
             + "\r\nTRIM_BARSx100=100\r\nLOOP_BARSx100=100\r\nBPMx24=2880"
             + "\r\nTSMODE=0\r\nLOOPMODE=1\r\nGAIN=48"
             + "\r\nTRIGQUANTIZATION=-1\r\n[/SAMPLE]\r\n\r\n").encode()
    for path in (dest / "project.work", dest / "project.strd"):
        if not path.exists():
            continue
        raw = path.read_bytes()
        raw = re.sub(rb"\[SAMPLE\]\r?\nTYPE=FLEX\r?\nSLOT=001\r?\n.*?\[/SAMPLE\]\r?\n\r?\n",
                     b"", raw, flags=re.S)
        at = raw.find(b"[SAMPLE]")
        if at < 0:
            raise ValueError(f"{path}: no sample section")
        raw = raw[:at] + block + raw[at:]
        for key, val in ((b"BANK", b"0"), (b"PATTERN", b"0"), (b"TRACK", b"0")):
            raw, count = re.subn(rb"(\r?\n)" + key + rb"=\d+",
                                 lambda m: m.group(1) + key + b"=" + val, raw, count=1)
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
        offset = 0x16  # FLEX slot 1, 784-byte marker record
        data[offset:offset + 784] = struct.pack(">III", 0, FRAMES, 0) + bytes(772)
        data[-2:] = (sum(data[0x10:-2]) & 0xFFFF).to_bytes(2, "big")
        path.write_bytes(data)


def part_values(mods, track, part):
    key = FX1[track]
    if key == "MODULATION":
        # PHSR is the measured worst loop. The other bank parts select
        # LINE and COMB so a part change also exercises mode transitions.
        modes = (4, 0, 3, 4)
        extra = {"MIX": 95, "RATE": 72, "DPTH": 90, "FDBK": 75, "LOFI": 35}
        extra["MODE"] = modes[(part + track) % 4]
    elif key == "SPECTRUM":
        extra = {"MODE": (0, 2, 4, 1)[(part + track) % 4], "FREQ": 72, "RES": 85,
                 "LDP": 75, "SHPE": 70}
    else:
        extra = {"SAT": (0, 1, 2, 1)[(track - 4 + part) % 4], "DRV": 72,
                 "FOLD": 55, "COMP": 50, "MIX": 100}
    fx1 = otp.module_defaults(mods[key], extra)
    key2 = FX2[track]
    if track == 0:
        extra2 = {"SEND": 35, "MODE": (1, 0, 2, 1)[part % 4], "TIME": 45, "FDBK": 65,
                  "WET": 70, "DENS": 110, "SCAT": 65, "PTCH": 88}
    elif track == 4:
        extra2 = {"SEND": 35, "MODE": (2, 1, 0, 2)[part % 4], "TIME": 75, "SIZE": 95,
                  "SHMR": 28, "WET": 65, "DIFF": 95}
    else:
        extra2 = {"SEND": 35}
    fx2 = otp.module_defaults(mods[key2], extra2)
    return fx1, fx2


def mutate_bank(data, bank_number, mods):
    bank.check_tags(data)
    for part in range(otp.NPARTS_ALL):
        base = otp.PART_BASE + part * otp.PART_STRIDE
        for track in range(8):
            fx1, fx2 = part_values(mods, track, part)
            data[base + otp.FX1_OFF + track] = mods[FX1[track]].menu.fx2_id
            data[base + otp.FX2_OFF + track] = mods[FX2[track]].menu.fx2_id
            p1 = base + otp.P1_OFF + track * otp.TRACK_STRIDE
            p2 = base + otp.P2_OFF + track * otp.P2_STRIDE
            data[p1:p1 + 12] = fx1[:6] + fx2[:6]
            data[p2:p2 + 12] = fx1[6:] + fx2[6:]
            data[base + otp.MTYPE_OFF + track] = 1  # FLEX
            data[base + 0x2d3 + track * 5 + 1] = 0  # slot 1
            data[base + 0x01b + track * 2] = 55  # leave mix headroom
            setup = base + 0x1e3 + track * 30 + 6
            values = base + 0x033 + track * 30 + 6
            data[setup] = 1      # LOOP
            data[setup + 4] = 0  # TSTR off
            data[values] = 64    # PTCH neutral
            data[values + 3] = 127  # RATE forward
            lfo1 = base + otp.LFO_P1_OFF + track * 24
            lfo2 = base + otp.LFO_PM_OFF + track * 30
            data[lfo1:lfo1 + 6] = bytes((20, 36, 52, 20, 28, 18))
            # FX1 frequency/drive, FX1 mix/resonance, FX2 send.
            data[lfo2:lfo2 + 6] = bytes((18, 19, 24, 1, 1, 1))

    # Pattern A01-A04 select Parts 1-4 via the measured PTRN tail byte.
    for pat in range(16):
        tail = bank.PTRN_BASE + pat * bank.PTRN_STRIDE + bank.PTRN_STRIDE - 5
        data[tail] = pat if bank_number == 1 and pat < 4 else 0

    # Clear inherited trigs/locks in every bank. Bank A gets four active
    # patterns; the other banks remain useful for checking silent load.
    for pat in range(16):
        for track in range(8):
            off = otp.trac_off(pat, track)
            data[off:off + 64] = bytes(64)
            data[off + 0x59:off + 0x59 + 64 * 32] = bytes([0xff]) * (64 * 32)
            if bank_number != 1 or pat >= 4:
                continue
            count = (16, 32, 64, 64)[pat]
            for step in range(count):
                trig = pat != 3 or step % 4 == 0
                if trig:
                    mask = off + 7 - step // 8
                else:
                    mask = off + 16 + 7 - step // 8  # mask 2: trigless lock
                data[mask] |= 1 << (step % 8)
                rec = off + 0x59 + step * 32
                # Every step changes FX and modulation values. Keep playback
                # pitch/rate and SEND within useful, non-silent ranges.
                for slot in LOCK_SLOTS:
                    value = (step * 17 + track * 11 + pat * 23 + slot * 7) % 128
                    if slot == 0:
                        value = (52, 64, 76, 64)[(step + track) % 4]
                    elif slot == 3:
                        value = (96, 112, 127)[(step + track) % 3]
                    elif slot == 24:
                        value = 20 + value % 51
                    elif slot in (15, 16):
                        value = 48 + value % 33
                    data[rec + slot] = value


def verify(dest, mods):
    total_trigs = total_locks = 0
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
                    assert data[base + otp.MTYPE_OFF + track] == 1
                    assert data[base + otp.LFO_P1_OFF + track * 24 + 3] > 0
            if suffix != "work":
                continue
            for pat in range(16):
                tail = bank.PTRN_BASE + pat * bank.PTRN_STRIDE + bank.PTRN_STRIDE - 5
                assert data[tail] == (pat if num == 1 and pat < 4 else 0)
                for track in range(8):
                    locks = bank.locks(data, pat, track)
                    trigs = bank.trigs(data, pat, track)
                    if num == 1 and pat < 4:
                        expected = (16, 32, 64, 64)[pat]
                        assert len(locks) == expected, (path, pat, track)
                        assert len(trigs) == (expected // 4 if pat == 3 else expected)
                        assert all(set(rec) == set(LOCK_SLOTS) for rec in locks.values())
                        total_trigs += len(trigs)
                        total_locks += sum(map(len, locks.values()))
                    else:
                        assert not locks and not trigs, (path, pat, track)
    return total_trigs, total_locks


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", type=pathlib.Path,
                    default=ROOT / "template_project/Drum Template TGM")
    ap.add_argument("--out", type=pathlib.Path,
                    default=ROOT / "out/stress-project")
    args = ap.parse_args()
    source, dest = args.source.resolve(), args.out.resolve()
    if dest.exists():
        ap.error(f"{dest} exists; choose a new --out directory")
    if not (source / "project.work").is_file() or not (source / "bank01.work").is_file():
        ap.error("source needs project.work and bank01.work")
    remix = registry.remix("bamsep26")
    mods = registry.modules()
    if not all(k in remix.modules for k in set(FX1 + FX2)):
        ap.error("bamsep26 no longer contains the required modules")
    dest.mkdir(parents=True)
    for src in source.iterdir():
        if src.is_file() and src.suffix in (".work", ".strd"):
            shutil.copy2(src, dest / src.name)
    set_project_text(dest)
    set_markers(dest)
    for num in range(1, 17):
        otp._bank_write(dest, num, lambda data, n=num: mutate_bank(data, n, mods),
                        guard=False)
    otp.write_stored(dest)
    trigs, locks = verify(dest, mods)
    wav = dest / SAMPLE_REL
    make_sample(wav)
    report = (f"bamsep26 stress project\n"
              f"Bank A patterns 01-04: 16/32/64 dense steps, then 64 steps"
              f" with trigless locks\n"
              f"8 FLEX tracks; 24 LFOs per part; FX1: 4 Character, 2 Modulation,"
              f" 2 Spectrum; FX2: BusDelay T1, BusVerb T5, SEND elsewhere\n"
              f"{trigs} trigs; {locks} parameter lock bytes in bank A\n"
              f"Generated sample: {SAMPLE_REL}, sha256 {digest(wav)}\n"
              f"Start at A01, 120 BPM. Switch A01-A04 to exercise Part/mode and pattern/lock"
              f" loads. Turn down monitoring before first playback.\n"
              f"The source template and generated project are local assets;"
              f" do not commit Octatrack project files.\n")
    (dest / "STRESS_README.txt").write_text(report)
    print(report)
    print(dest)


if __name__ == "__main__":
    main()



