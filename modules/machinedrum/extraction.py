#!/usr/bin/env python3
"""Phase 0 of the Machinedrum machine: unpack and inventory MD OS 1.63.

Everything here is derived at run time from the user's own update file
(`Elektron_SPS1-1UW_OS1.63.syx`); nothing Elektron-derived is committed.
Outputs go to `out/machinedrum/os163/` (gitignored).

Layers, outermost first (docs/proposals/MACHINEDRUM_MACHINE.md, "Phase 0
findings"):

  .syx      14,684 data messages; 2+7+7 packing, 64 decoded bytes each,
            counted from flash offset 0x4000; a 7F trailer carries the
            total, 939,744 bytes. Decoded and checksummed by the vendored
            elektron-firmware-tool (its "pre-ELE" container).
  sections  [u32 compressed size][u32 byte sum] + an aPLib-variant
            stream, five of them: MAIN OS, two DSP load images, two
            512 KiB factory data banks.
  DSP       little-endian 24-bit words: a 4-word header, then
            (space, address, count, words...) load records, space
            0/1/2 = P/X/Y, ending in the 2-word (3, 0x24) trailer.
  engines   an 86-byte descriptor per machine in the MAIN OS image:
            [handler:24][id:8][family:3][name:2][8 x 4-char param
            names][8 defaults][8 flag bytes].

Usage:
  python3 modules/machinedrum/extraction.py [--syx PATH] [--wav] [--disasm]

--disasm writes dsp_1.asm / dsp_2.asm: every P run of each image except the
sample block, through the vendored dsp56kDisassemble.
"""
import argparse
import hashlib
import json
import struct
import subprocess
import sys
import wave
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out/machinedrum/os163"
EFT = ROOT / "vendor/elektron-firmware-tool/elektron-firmware-tool"
SYX_NAME = "Elektron_SPS1-1UW_OS1.63/Elektron_SPS1-1UW_OS1.63.syx"

# The only input this recipe is proven against. A different file is refused.
SYX_SHA256 = "a58cd61f2efacfb07add0c643162fb4365c30e73831f2021c17b4aa3b42cabd5"
SECTIONS = {  # extracted name -> sha256
    "section_0_MAIN_OS.bin": "95d74ace951af86777d1deeb2b6c993213344d7d8ae64a985c5df36f3b499e12",
    "section_1_DSP.bin":     "e1d845a772f87b04e1681130f3e3eab2db20dc4d047489375a3be93870c591bc",
    "section_2_DSP.bin":     "0fd8b64a4cef976c07f246ab543294c263b08f543ebff8f8415811d29e434c06",
    "section_3_data.bin":    "f43a388e292bd7284e92cc74eab71c2c48b5c9109af45d02ea65afe806604538",
    "section_4_data.bin":    "1d5bc1d89dedf6c06c7346393790b51eefd677e40ffe0451ce304a4ae40dfbc9",
}

# The reference emulator this plan compares against (vendor/, not built by
# scripts/setup.sh). Its loader accepts only a full 8 MiB flash dump.
REFERENCE = ("https://github.com/joelanders/gearmulator-md-mm",
             "8cea0524a75435122c20b669ca114c9ac6509ba2")

OS_BASE = 0x200000          # MAIN OS link address (its startup code)
DESC_SIZE = 86
DESC_FIRST = 0x4EF55        # GND-EM, the first descriptor, image offset
FAMILIES = {0x0: "GND", 0x1: "TRX", 0x2: "EFM", 0x3: "E12", 0x4: "P-I",
            0x5: "INP", 0x6: "MID", 0x7: "CTR"}
# Section 1, P space, 12-bit pairs: the E12 samples, 21 of them back to back,
# each followed by 0x88 words. The code runs to 0x103c7x below; between them,
# at 0x103d7b, the 21 descriptors [start word, length in samples, 0].
SAMPLE_BLOCK = (0x103DBA, 0x135206)
E12_DESCRIPTORS = (0x103D7B, 21)
DIS = ROOT / "vendor/dsp56300/build/source/disassemble/dsp56kDisassemble"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def find_syx(arg):
    if arg:
        return Path(arg)
    for base in (ROOT, Path(subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "--path-format=absolute",
             "--git-common-dir"], capture_output=True, text=True).stdout.strip()).parent):
        p = base / "base_firmware" / SYX_NAME
        if p.exists():
            return p
    sys.exit(f"no MD OS 1.63 update: put yours at base_firmware/{SYX_NAME} or pass --syx")


def unpack(syx):
    if sha(syx) != SYX_SHA256:
        sys.exit(f"{syx}: sha256 {sha(syx)} is not the MD OS 1.63 update this recipe knows")
    if not EFT.exists():
        sys.exit(f"{EFT} missing: run scripts/setup.sh")
    OUT.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([str(EFT), "-i", str(syx), "-o", str(OUT)],
                       capture_output=True, text=True)
    if r.returncode:
        sys.exit(r.stdout + r.stderr)
    for name, want in SECTIONS.items():
        if sha(OUT / name) != want:
            sys.exit(f"{name}: sha256 differs from the pinned extraction")


def dsp_records(path):
    """(space, address, words) records of one DSP load image."""
    b = (OUT / path).read_bytes()
    w = [int.from_bytes(b[i:i + 3], "little") for i in range(0, len(b), 3)]
    i, recs = 4, []
    while i + 3 <= len(w):
        sp, ad, n = w[i:i + 3]
        if sp > 2 or n == 0 or i + 3 + n > len(w):
            break
        recs.append((sp, ad, w[i + 3:i + 3 + n]))
        i += 3 + n
    if w[i:] != [3, 0x24] or w[:4] != [3, 0x24, 4, 0]:
        sys.exit(f"{path}: load records do not end in the known trailer")
    return recs


def dsp_map(recs):
    runs = []
    for sp, ad, words in recs:
        if runs and runs[-1][0] == sp and runs[-1][1] + runs[-1][2] == ad:
            runs[-1][2] += len(words)
        else:
            runs.append([sp, ad, len(words)])
    return [{"space": "PXY"[sp], "start": ad, "end": ad + n - 1, "words": n}
            for sp, ad, n in runs]


def engines():
    img = (OUT / "section_0_MAIN_OS.bin").read_bytes()
    out, o = [], DESC_FIRST
    while True:
        r = img[o:o + DESC_SIZE]
        fam = r[4:7]
        if len(r) < DESC_SIZE or not fam.replace(b"-", b"").isalnum():
            break
        mid = r[3]
        out.append({
            "id": mid,
            "name": f"{fam.decode()}-{r[7:9].decode()}",
            "family": FAMILIES.get(mid >> 4, "ROM/RAM"),
            "handler": int.from_bytes(r[0:3], "big"),
            "params": [r[9 + 4 * k:13 + 4 * k].rstrip(b"\0").decode("latin1")
                       for k in range(8)],
            "defaults": list(r[41:49]),
            "flags": r[49:57].hex(),
        })
        o += DESC_SIZE
    if out[0]["name"] != "GND---" or len(out) != 135:
        sys.exit(f"descriptor walk found {len(out)} records; expected 135 from GND-EM")
    for e in out:
        if not OS_BASE <= e["handler"] < OS_BASE + len(img):
            sys.exit(f"{e['name']}: handler {e['handler']:#x} outside the OS image")
    return out


def disasm(name, recs, tag):
    """One .asm per image, P runs in address order, the sample block skipped."""
    if not DIS.exists():
        sys.exit(f"{DIS} missing: run scripts/setup.sh")
    runs = []
    for sp, ad, words in recs:
        if sp != 0:
            continue
        if runs and runs[-1][0] + len(runs[-1][1]) == ad:
            runs[-1][1].extend(words)
        else:
            runs.append([ad, list(words)])
    out = OUT / f"dsp_{tag}.asm"
    with out.open("w") as fh:
        for ad, words in sorted(runs):
            if ad <= SAMPLE_BLOCK[0] < ad + len(words):
                words = words[:SAMPLE_BLOCK[0] - ad]
            if not words:
                continue
            blob = OUT / f"dsp_{tag}_P{ad:06x}.bin"
            blob.write_bytes(b"".join(w.to_bytes(3, "little") for w in words))
            r = subprocess.run([str(DIS), "-in", str(blob), "-pc", f"{ad:x}", "-le"],
                               capture_output=True, text=True)
            fh.write(f"; ---- P:{ad:06x}, {len(words)} words\n{r.stdout}")
            blob.unlink()
    return out


def sample_wav(recs):
    p = {}
    for sp, ad, words in recs:
        if sp == 0:
            for k, v in enumerate(words):
                p[ad + k] = v
    frames = bytearray()
    for a in range(*SAMPLE_BLOCK):
        for v in (p[a] >> 12, p[a] & 0xFFF):
            frames += struct.pack("<h", (v - 4096 if v & 0x800 else v) << 4)
    with wave.open(str(OUT / "e12_candidate_region.wav"), "wb") as o:
        o.setnchannels(1)
        o.setsampwidth(2)
        o.setframerate(44100)
        o.writeframes(frames)
    return len(frames) // 2


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--syx")
    ap.add_argument("--wav", action="store_true",
                    help="also write the section-1 sample block as a WAV")
    ap.add_argument("--disasm", action="store_true",
                    help="also disassemble both DSP images")
    a = ap.parse_args()
    syx = find_syx(a.syx)
    unpack(syx)
    print(f"input    {syx.name}  sha256 {SYX_SHA256[:16]}  ok")
    report = {"syx_sha256": SYX_SHA256, "sections": SECTIONS,
              "reference": {"url": REFERENCE[0], "commit": REFERENCE[1]}}
    for name in ("section_1_DSP.bin", "section_2_DSP.bin"):
        recs = dsp_records(name)
        m = dsp_map(recs)
        tot = Counter()
        for run in m:
            tot[run["space"]] += run["words"]
        report[name] = m
        print(f"{name}: {len(recs)} load records, "
              + ", ".join(f"{k} {v}" for k, v in sorted(tot.items())) + " words")
        for run in m:
            print(f"    {run['space']}:{run['start']:06x}..{run['end']:06x} {run['words']:7d}")
        if a.disasm:
            print(f"    {disasm(name, recs, name[8]).relative_to(ROOT)}")
        if name == "section_1_DSP.bin" and a.wav:
            n = sample_wav(recs)
            print(f"    e12_candidate_region.wav: {n} samples, {n / 44100:.2f} s")
    eng = engines()
    report["engines"] = eng
    fam = Counter(e["family"] for e in eng)
    core = [e for e in eng if e["family"] in ("TRX", "EFM", "E12", "P-I", "GND")
            and e["id"] != 0]
    print(f"engines  {len(eng)} descriptors: "
          + ", ".join(f"{k} {v}" for k, v in fam.items()))
    print(f"         core synthesis catalog (TRX/EFM/E12/P-I/GND, EMPTY excluded): {len(core)}")
    (OUT / "inventory.json").write_text(json.dumps(report, indent=1))
    print(f"wrote    {(OUT / 'inventory.json').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
