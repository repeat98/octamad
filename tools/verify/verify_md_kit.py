#!/usr/bin/env python3
"""The Machinedrum's kit and record producer under the ColdFire port (WP-C4).

    python3 tools/verify/verify_md_kit.py [--project DIR] [--cases base|all]
    OT_PROJECT=DIR [MD_EMU=path/to/ot_emu] make verify-md-kit

The oracle is the MD itself: md_handler_cases.py's capture of all 50
engines (out/machinedrum/c2_maps). map.txt holds the trig packet the MD
sent for a baseline and after eight detents of each encoder; cases.txt the
record before a handler call in each scenario (some handlers keep state in
it). A case's own parameter snapshot is not the trig's: it can catch an
update between trigs, with a parameter still easing toward its new value
(TRX-CP B: 0x23eb on its way to 0x2400), and TRX-CP computes nothing
unless triggered. So the kit gets the snapshot rounded to the nearest
step and the expected words are map.txt's. Per run the gate:

  1. pokes a 16-part kit into md_kit (engine, VOL 100 + part, PAN, the
     case's parameters >> 7), seeds each part's record with the MD's own
     record before that call (some handlers keep state in it: TRX-CP), sets
     md_kit_active and marks every part's trig and gains pending, before
     the frame engine starts;
  2. boots REMIX=machinedrum under the port, MACHINEDRUM in T1's FX2 slot
     (the glue runs on every frame), and samples core 1 at glue label
     gnotrg, after the frame's packets are written and before the driver
     renders: the sixteen Y voice records and both gain tables.

Checks, per part: its record's word 0 became non-zero exactly once (one
trig, no refresh re-triggers; the driver clears it when it renders the
slot's half, so a trig may be sampled twice); then words 0..count-1 are
the MD's trig record (word 0 = engine id + 1); and after the run the gain
words equal md_gain(VOL, PAN) (the MD's VOL^2 law, constant-power PAN).
TRX-S2 is the MD's own special case: MD OS 1.63 leaves it on the empty
handler, so its trig record is two words, the trig and a word it does not
write (the record's previous word 1). E12 is refused on the OT (its
samples are not on the DSP, WP-R1): an E12 part plays as GND---, whose
empty handler sends [1, the previous word 1].

--cases base runs each engine's baseline (four runs); all adds every
encoder detent (29 runs, about 15 minutes). SKIPs without a project, the
port, the MD payload or the capture. It sees the words the DSP receives,
not the audio: that the same words render the same blocks is WP-C1's gate
(verify_md_transport.py) and verify_md_image.py's.
"""
import argparse
import json
import math
import os
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
import runpy  # noqa: E402

OUT = ROOT / "out/mdverify/kit"
EMU = pathlib.Path(os.environ.get("MD_EMU") or ROOT / "out/emu/ot_emu")
MDB = ROOT / "out/machinedrum/build"
MAPS = ROOT / "out/machinedrum/c2_maps"
LAYOUT = runpy.run_path(str(ROOT / "modules/machinedrum/layout.py"))["LAYOUT"]
VOICE_Y = next(r["start"] for r in LAYOUT["allocations"] if r["name"] == "voice_y_records")
TRX_S2 = 0x1d


def pan_q15(p):
    return round(32768 * math.sqrt(2) * math.cos(p / 127 * math.pi / 2))


def md_gain(vol, pan, right):
    return vol * vol * pan_q15(127 - pan if right else pan) // 252


def load_cases():
    """{(id, encoder): (params[8], after[21], before bytes)}, {id: count}."""
    cases = {}
    for line in (MAPS / "cases.txt").read_text().splitlines():
        f = line.split()
        key = (int(f[0], 16), int(f[1]))
        p, before, after = bytes.fromhex(f[4]), bytes.fromhex(f[5]), bytes.fromhex(f[6])
        cases[key] = ([int.from_bytes(p[2 * i:2 * i + 2], "big") for i in range(8)],
                      [int.from_bytes(after[4 * i:4 * i + 4], "big") for i in range(21)],
                      before)
    counts, packets = {}, {}
    for line in (MAPS / "map.txt").read_text().splitlines():
        f = line.split()
        if len(f) > 2 and f[1] == "base":
            i = int(f[0], 16)
            counts[i] = int(f[2], 16) + 1
            packets[(i, -1)] = [int(x, 16) for x in f[3:3 + counts[i]]]
    # The trig packet after each encoder's +8: the base packet with the
    # changes map.txt lists (wK is packet word K; word 0 of a packet is the
    # count, so wK is record word K - 1).
    for line in (MAPS / "map.txt").read_text().splitlines():
        f = line.split()
        if len(f) > 1 and f[1].startswith("enc"):
            i, e = int(f[0], 16), ord(f[1][3]) - ord("A")
            if (i, -1) not in packets:
                continue
            rec = list(packets[(i, -1)])
            for ch in f[2:]:
                if ch == "-":
                    continue
                k, change = ch[1:].split(":")
                if 1 <= int(k) <= len(rec):
                    rec[int(k) - 1] = int(change.split(">")[1], 16)
            packets[(i, e)] = rec
    # md_profile's map hook keeps packets of more than four words only, so
    # the two-word trig records (GND-NS: its handler's moveq #2, and TRX-S2
    # on the empty handler) have no map line; their count is 2.
    for i in {k[0] for k in cases} - set(counts):
        counts[i] = 2
    counts[TRX_S2] = 2
    return cases, counts, packets


def stage(project, frames_note):
    """Build the image and a card with MACHINEDRUM in T1's FX2 slot."""
    import ot_project as otp
    OUT.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, REMIX="machinedrum", XBUS="1", SPEC="1")
    env.setdefault("BUILD", "0")
    r = subprocess.run([sys.executable, str(ROOT / "tools/build/build_bus.py")], env=env,
                       capture_output=True, text=True, cwd=ROOT)
    if r.returncode:
        sys.exit(f"verify_md_kit: building machinedrum failed:\n{(r.stdout + r.stderr)[-1500:]}")
    image = OUT / "image.bin"
    shutil.copy2(ROOT / "out/mainos_bus.bin", image)
    proj = OUT / "project"
    if proj.exists():
        shutil.rmtree(proj)
    shutil.copytree(pathlib.Path(project).expanduser(), proj)
    otp.set_fx(proj, "fx2", 1, "MACHINEDRUM", page=[100, 0, 0, 0, 0, 0], guard=False)
    card = OUT / "card.img"
    r = subprocess.run([sys.executable, str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(proj),
                        "OCTABAM", "RIG", "--tree", str(OUT / "tree"), "--out", str(card)],
                       capture_output=True, text=True, cwd=ROOT)
    if r.returncode:
        sys.exit(f"verify_md_kit: staging the card failed:\n{r.stdout[-800:]}{r.stderr[-800:]}")
    return image, card


def symbols():
    nm = subprocess.check_output(["m68k-elf-nm", str(ROOT / "out/platform/runtime/runtime.elf")],
                                 text=True)
    cf = {f[2]: int(f[0], 16) for f in (l.split() for l in nm.splitlines()) if len(f) == 3}
    glue = {l.split()[0]: int(l.split()[1], 16)
            for l in (MDB / "glue.sym").read_text().splitlines() if l.strip()}
    return cf, glue


# md_ctl.h MdRun, as md_ctl.c's static assertions pin it.
RUN_SHADOW, RUN_TRIG, RUN_GAINS, RUN_STARTED, RUN_KIT_READY = 1344, 1556, 1560, 1563, 1565


def run(tag, kit, image, card, cf, glue, frames, records):
    """kit: 16 (id, vol, pan, syn[8]); records: 16 x 84 bytes, each part's
    record before its handler call. Returns the sampled rows.

    The runtime is seeded as if each part had the MD's own history: some
    handlers keep state in the record they rewrite (TRX-CP writes words
    1, 2, 5 and 7 only on a condition, so a detent case's output depends on
    the calls before it), so each part's record starts as the MD's record
    before the captured call, the kit counts as applied (started), and the
    trigs and gains are pending. This is the same-history comparison the
    WP-C2 handler gate makes, here through the producer and the transport."""
    blob = bytearray()
    for eng, vol, pan, syn in kit:
        blob += bytes((eng, vol, pan, 0, *syn))
    run_head = bytearray(b"".join(records))
    run_head += blob                                   # shadow = the kit
    run_head += bytes(RUN_TRIG - len(run_head))
    run_head += (0xffff).to_bytes(2, "big") + bytes(2) + (0xffff).to_bytes(2, "big")
    run_head += bytes(RUN_STARTED - len(run_head)) + b"\x01\xff\x01"   # started, no MD track, kit ready
    pokes = [(cf["md_kit"], bytes(blob)),
             (cf["md_run"], bytes(run_head)),
             (cf["md_kit_active"], (1).to_bytes(4, "big"))]
    poke = ";".join(f"{addr + i:#x}={b:#x}" for addr, data in pokes for i, b in enumerate(data))
    g = LAYOUT["glue"]
    samples, log = OUT / f"{tag}.samples.txt", OUT / f"{tag}.port.txt"
    spans = f"Y:{VOICE_Y:x},1024;X:{g['GAIN']:x},16;X:{g['GAINR']:x},16;X:{g['BAD']:x},1"
    cmd = [str(EMU), "--image", str(image), "--card", str(card), "--set", "OCTABAM",
           "--project", "RIG", "--sequencer", "--internal-clock", "--frames", str(frames),
           "--load-ms", "20000", "--dsp",
           "--dsp-sample", f"1:{glue['gnotrg']:x}:{samples}:1000000={spans}",
           "--poke-early", poke]
    with open(log, "w") as f:
        f.write(" ".join(cmd) + "\n"); f.flush()
        r = subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
    if r.returncode:
        sys.exit(f"verify_md_kit: ot_emu exit {r.returncode} -- {log}")
    ran = re.search(r"frames run : (\d+) since transport start \(target (\d+)\), run ended (\w+)",
                    log.read_text())
    if not ran or ran.group(3) != "REACHED":
        sys.exit(f"verify_md_kit: the port did not reach {frames} frames -- {log}")
    rows = []
    for line in samples.read_text().splitlines():
        p = line.split("|")
        rows.append([[int(x, 16) for x in s.split()] for s in p[1:]])
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--project", default=os.environ.get("OT_PROJECT", ""))
    ap.add_argument("--cases", choices=("base", "all"), default="base")
    ap.add_argument("--frames", type=int, default=40)
    a = ap.parse_args()
    if not a.project:
        print("  [SKIP] verify_md_kit: no project (OT_PROJECT=<dir> or --project)")
        return 0
    for need, what in ((EMU, "the ColdFire port (make emu-cf)"),
                       (MDB / "payload_B.mem", "the MD payload (tools/build/md_payload.py)"),
                       (MAPS / "cases.txt", "the handler cases (md_handler_cases.py)")):
        if not need.exists():
            print(f"  [SKIP] verify_md_kit: no {what}")
            return 0
    cases, counts, packets = load_cases()
    ids = sorted({k[0] for k in cases})
    keys = [(i, e) for e in ((-1,) if a.cases == "base" else range(-1, 8)) for i in ids]
    image, card = stage(a.project, a.frames)
    cf, glue = symbols()
    fails = 0

    def check(label, ok, detail=""):
        nonlocal fails
        fails += 0 if ok else 1
        print(f"  [{'ok' if ok else 'FAIL'}] {label}{'  ' + detail if detail else ''}")

    total = 0
    for n in range(0, len(keys), 16):
        batch = keys[n:n + 16]
        kit, records = [], []
        for p in range(16):
            if p < len(batch):
                eng, enc = batch[p]
                _, _, before = cases[batch[p]]
                # The scenario's values: the case's own snapshot, rounded to
                # the nearest step. A snapshot can catch a parameter easing
                # toward its new value (TRX-CP B: 0x23eb on its way to
                # 0x2400); the rig's eight detents are not always + 8
                # (GND-SN A: 73 -> 69), so the snapshot, not the detent
                # count, says where the value went.
                syn = [min(127, (w + 64) >> 7) for w in cases[batch[p]][0]]
            else:
                eng, syn, before = 0, [0] * 8, bytes(84)
            kit.append((eng, 100 + (p % 16) + (p // 16), (8 * p) % 128, syn))
            records.append(before)
        rows = run(f"run{n // 16:02d}", kit, image, card, cf, glue, a.frames, records)
        bad = []
        for p, key in enumerate(batch):
            eng = key[0]
            _, after, before = cases[key]
            count = counts[eng]
            # The oracle: the trig packet the MD sent (map.txt), or for the
            # two-word engines without one, the captured record.
            want = packets.get(key) or [eng + 1] + [w & 0xffffff for w in after[1:count]]
            stale = int.from_bytes(before[4:8], "big") & 0xffffff
            if eng == TRX_S2:
                want = [eng + 1, stale]       # the empty handler writes nothing
            if 0x30 <= eng <= 0x3f:
                # E12 is refused (no samples on the OT DSP): it plays as
                # GND---, the empty handler's two words, routine index 1.
                count, want = 2, [1, stale]
            recs = [r[0][0x40 * p:0x40 * p + 0x40] for r in rows]
            # A trig's word 0 stays set until the driver renders the slot's
            # half, so one trig can be sampled on two calls: count arrivals.
            hits = [rec for k, rec in enumerate(recs) if rec[0] and (k == 0 or not recs[k - 1][0])]
            if len(hits) != 1 or hits[0][:count] != want:
                got = [f"{w:06x}" for w in hits[0][:count]] if hits else []
                bad.append(f"{eng:#04x}/{key[1]}: {len(hits)} trig(s) {got} want "
                           f"{[f'{w:06x}' for w in want]}")
        last = rows[-1]
        gains_ok = all(last[1][p] == md_gain(kit[p][1], kit[p][2], 0)
                       and last[2][p] == md_gain(kit[p][1], kit[p][2], 1) for p in range(16))
        total += len(batch)
        check(f"run {n // 16}: {len(batch)} trig records equal the MD's, one trig each",
              not bad, "; ".join(bad[:3]))
        check(f"run {n // 16}: gain words are md_gain(VOL, PAN)", gains_ok and last[3][0] == 0,
              f"bad packets {last[3][0]}")
    print(f"  verify_md_kit: {total} cases, {'PASS' if not fails else f'{fails} FAILED'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
