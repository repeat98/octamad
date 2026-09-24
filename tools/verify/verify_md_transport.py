#!/usr/bin/env python3
"""The Machinedrum's record transport under the ColdFire port (WP-C1).

    python3 tools/verify/verify_md_transport.py [--project DIR] [--capture DIR] [--frames N]
    OT_PROJECT=DIR [MD_EMU=path/to/ot_emu] make verify-md-transport

A captured kit's host stream goes through the image's own path, ColdFire to
core 1, and core 1's voice blocks are compared with the replay's:

  1. the reference: md_replay --reloc --driver --boot --interpreter on
     the payload's own memory image (out/machinedrum/build/source) with the capture's log, so
     the replay starts where core 1 starts (the relocated boot init) and
     takes the same writes (MD_REPLAY_OUT, every block);
  2. the stream: the capture's host writes, cut into one chunk per OT frame.
     The driver renders slots 0-7 on one frame and 8-15 on the next, and a
     write reaches the slot at its next render in the Machinedrum; so a
     write to slot t sent before slot s rendered in period p belongs to
     period p (t >= s) or p + 1 (t < s), and goes in that period's chunk for
     t's half. Consecutive words make a packet. Even chunks carry the sync
     mark (the glue's driver half starts there);
  3. the run: REMIX=machinedrum, MACHINEDRUM in T1's FX2 slot, the stream
     loaded into the platform reserve (--load-file) and md_feed pointed at it
     before the frame engine starts (a pre-roll, so the stream arrives before
     any OT trig could fire the fixed trigger); core 1 sampled right after
     every driver call (glue label gdone).

Checks: md_xport sent one block per chunk and dropped none; the glue took
every block (no sequence gap, no refused packet, one sync slip at most);
and every slot's block in every period core 1 rendered equals the
reference's, bit for bit. It also prints how many of the reference's blocks
equal the Machinedrum's own output (the capture's "O" lines), which differ
with a different startup state and the capture emulator's JIT loop defect
(see machinedrum_reports/WP-C1.md). Captured audio is not this gate's oracle.

THE EMULATOR PIN MATTERS, as for verify_md_image.py: MD_EMU names a port
built from the repo's dsp56300 pin. SKIPs without a project, the port, the
MD payload, md_replay or the capture. It cannot see the unit's timing: the
added burst's cost on the FlexBus is unmeasured on hardware.
"""
import argparse
import os
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
import runpy  # noqa: E402

OUT = ROOT / "out/mdverify/xport"
EMU = pathlib.Path(os.environ.get("MD_EMU") or ROOT / "out/emu/ot_emu")
REPLAY = ROOT / "out/md_reference/md_replay"
MDB = ROOT / "out/machinedrum/build"
CAPTURE = ROOT / "out/md_profile/cap4/c01_16"
LAYOUT = runpy.run_path(str(ROOT / "modules/machinedrum/layout.py"))["LAYOUT"]
MBOX_HW = next(r["words"] for r in LAYOUT["allocations"] if r["name"] == "mbox_a")
# Empty chunks ahead of the stream. The first block after the frame engine
# starts does not reach the glue (measured: seq 1 of a run never taken, gap
# 1, every later block taken); an even count keeps the sync marks on the
# stream's even chunks.
PAD = 4


def host_writes(log):
    """[(slot the MD rendered next, [(Y address, word)...])] per rendered block."""
    groups, pend, last_w, dest, count, done, open_, expect = [], [], 0, 0, 0, 0, False, False
    for line in log.read_text().splitlines():
        if not line:
            continue
        k = line[0]
        if k in "CW":
            v = int(line.split()[1], 16)
            if k == "C":
                open_ = expect = v == 0x12
                dest, count, done = last_w, 0, 0
            elif expect:
                count, expect = v + 1, False
            elif open_ and done < count:
                pend.append((dest + done, v))
                done += 1
            else:
                last_w = v
        elif k == "R":
            groups.append((int(line.split()[1]), pend))
            pend = []
    return groups


def stream(groups):
    """The chunks, one per OT frame: {chunk: [(address, word)...]} in order."""
    chunks, period = {}, -1
    for slot, writes in groups:
        if slot == 0:
            period += 1
        for a, v in writes:
            t = (a - 0x800) >> 6
            if not 0 <= t < 16:
                sys.exit(f"verify_md_transport: host write outside the voice records: Y:{a:x}")
            e = period if t >= slot else period + 1
            chunks.setdefault(2 * e + (t >= 8), []).append((a, v))
    return chunks, period + 1


def encode(chunks, n):
    """Big-endian halfwords: per chunk flags, npkt, nhw, packets; 0xffff ends.
    PAD empty chunks go first."""
    out = bytearray()

    def hw(v):
        out.extend((v & 0xffff).to_bytes(2, "big"))
    for _ in range(PAD):
        hw(0), hw(0), hw(0)
    worst = 0
    for c in range(n):
        packets = []
        for a, v in chunks.get(c, []):
            if packets and packets[-1][0] + len(packets[-1][1]) == a and len(packets[-1][1]) < 64:
                packets[-1][1].append(v)
            else:
                packets.append((a, [v]))
        body = []
        for a, words in packets:
            body += [a, len(words)]
            for v in words:
                body += [v >> 16, v & 0xffff]
        if len(packets) > 64:
            sys.exit(f"verify_md_transport: chunk {c} has {len(packets)} packets (the glue takes 64)")
        worst = max(worst, 3 + len(body))
        hw(1 if c % 2 == 0 else 0)
        hw(len(packets))
        hw(len(body))
        for x in body:
            hw(x)
    hw(0), hw(0xffff), hw(0)
    return bytes(out), worst


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--project", default=os.environ.get("OT_PROJECT", ""))
    ap.add_argument("--capture", default=str(CAPTURE))
    ap.add_argument("--frames", type=int, default=0, help="default: the whole stream")
    ap.add_argument("--pre-roll", type=int, default=16)
    ap.add_argument("--load-ms", type=int, default=20000)
    a = ap.parse_args()
    cap = pathlib.Path(a.capture)
    if not a.project:
        print("  [SKIP] verify_md_transport: no project (OT_PROJECT=<dir> or --project)")
        return 0
    for need, what in ((EMU, "the ColdFire port (make emu-cf)"),
                       (REPLAY, "md_replay (tools/harness/md_reference/md_profile.cmake)"),
                       (MDB / "source/snapshot.bin", "the MD payload (tools/build/md_payload.py)"),
                       (cap / "log.txt", f"the capture {cap}")):
        if not need.exists():
            print(f"  [SKIP] verify_md_transport: no {what}")
            return 0
    import verify_set as vs  # noqa: F401  (toolpath)
    import ot_project as otp

    OUT.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, REMIX="machinedrum", XBUS="1", SPEC="1")
    env.setdefault("BUILD", "0")
    r = subprocess.run([sys.executable, str(ROOT / "tools/build/build_bus.py")], env=env,
                       capture_output=True, text=True, cwd=ROOT)
    if r.returncode:
        sys.exit(f"verify_md_transport: building machinedrum failed:\n{(r.stdout + r.stderr)[-1500:]}")
    image = OUT / "image.bin"
    shutil.copy2(ROOT / "out/mainos_bus.bin", image)

    # 1. the reference
    ref_dir = OUT / "ref"
    if ref_dir.exists():
        shutil.rmtree(ref_dir)
    ref_dir.mkdir()
    for f in (MDB / "source").iterdir():
        shutil.copy2(f, ref_dir / f.name)
    for name in ("log.txt", "regs.txt"):
        shutil.copy2(cap / name, ref_dir / name)
    # Ambient diagnostic overrides (partial runs, poisoned memory, idle
    # prefixes) must not silently change the comparison oracle.
    ref_env = {k: v for k, v in os.environ.items() if not k.startswith("MD_REPLAY_")}
    ref_env["MD_REPLAY_OUT"] = str(ref_dir / "blocks.txt")
    r = subprocess.run([str(REPLAY), str(ref_dir), "--reloc", "--driver", "--boot", "--interpreter"],
                       env=ref_env,
                       capture_output=True, text=True, cwd=ROOT)
    summary = next((l for l in r.stdout.splitlines() if l.startswith("blocks:")), "")
    if (r.returncode not in (0, 3) or "execution: interpreter" not in r.stdout
            or not summary or not (ref_dir / "blocks.txt").exists()):
        sys.exit(f"verify_md_transport: md_replay --boot failed:\n{(r.stdout + r.stderr)[-1500:]}")
    ref, period = {}, -1
    for line in (ref_dir / "blocks.txt").read_text().splitlines():
        f = line.split()
        slot = int(f[1])
        if slot == 0:
            period += 1
        ref[(period, slot)] = [int(x, 16) for x in f[2:]]

    # 2. the stream
    chunks, periods = stream(host_writes(cap / "log.txt"))
    blob, worst = encode(chunks, 2 * periods)
    if worst > MBOX_HW:
        sys.exit(f"verify_md_transport: a chunk needs {worst} halfwords; the mailbox holds {MBOX_HW}")
    (OUT / "stream.bin").write_bytes(blob)
    frames = a.frames or 2 * periods + PAD + 8

    # 3. the run
    lay = __import__("json").loads((ROOT / "out/platform/layout.json").read_text())
    at = (lay["stage_end"] + 0x10000) & ~0xffff
    if at + len(blob) > lay["ceiling"]:
        sys.exit("verify_md_transport: the stream does not fit the platform reserve")
    nm = subprocess.run(["m68k-elf-nm", str(ROOT / "out/platform/runtime/runtime.elf")],
                        capture_output=True, text=True).stdout
    cf = {f[2]: int(f[0], 16) for f in (l.split() for l in nm.splitlines()) if len(f) == 3}
    feed = cf["md_feed"]
    poke = ";".join(f"{feed + i:#x}={(at >> (24 - 8 * i)) & 0xff:#x}" for i in range(4))

    src = pathlib.Path(a.project).expanduser()
    proj = OUT / "project"
    if proj.exists():
        shutil.rmtree(proj)
    shutil.copytree(src, proj)
    otp.set_fx(proj, "fx2", 1, "MACHINEDRUM", page=[100, 0, 0, 0, 0, 0], guard=False)
    card = OUT / "card.img"
    r = subprocess.run([sys.executable, str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(proj), "OCTABAM",
                        "RIG", "--tree", str(OUT / "tree"), "--out", str(card)],
                       capture_output=True, text=True, cwd=ROOT)
    if r.returncode:
        sys.exit(f"verify_md_transport: staging the card failed:\n{r.stdout[-800:]}{r.stderr[-800:]}")

    g, d = LAYOUT["glue"], LAYOUT["driver"]
    sym = {l.split()[0]: int(l.split()[1], 16)
           for l in (MDB / "glue.sym").read_text().splitlines() if l.strip()}
    samples, log, cfmem = OUT / "glue.txt", OUT / "port.txt", OUT / "cf.bin"
    spans = f"X:{g['LSEQ']:x},6;Y:{d['HALF']:x},1;Y:{d['OUTBUF']:x},512;X:{g['OWNER']:x},1"
    cmd = [str(EMU), "--image", str(image), "--card", str(card), "--set", "OCTABAM", "--project", "RIG",
           "--sequencer", "--internal-clock", "--frames", str(frames), "--load-ms", str(a.load_ms),
           "--pre-roll", str(a.pre_roll), "--dsp",
           "--load-file", f"{at:#x}={OUT / 'stream.bin'}", "--poke-early", poke,
           "--mem-dump", f"{feed:#x},20={cfmem}",
           "--dsp-sample", f"1:{sym['gdone']:x}:{samples}:1000000={spans}"]
    with open(log, "w") as f:
        f.write(" ".join(cmd) + "\n"); f.flush()
        r = subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
    if r.returncode:
        sys.exit(f"verify_md_transport: ot_emu exit {r.returncode} -- {log}")
    text = log.read_text()

    fails = 0

    def check(label, ok, detail=""):
        nonlocal fails
        fails += 0 if ok else 1
        print(f"  [{'ok' if ok else 'FAIL'}] {label}{'  ' + detail if detail else ''}")

    ran = re.search(r"frames run : (\d+) since transport start \(target (\d+)\), run ended (\w+)", text)
    check("load: the project loaded and the frames ran", ran is not None and ran.group(3) == "REACHED",
          f"frames {ran.group(1)}/{ran.group(2)}" if ran else "no frames line")
    mem = cfmem.read_bytes() if cfmem.exists() else b""
    words = [int.from_bytes(mem[i:i + 4], "big") for i in range(0, 16, 4)] if len(mem) >= 16 else None
    rows = []
    for line in samples.read_text().splitlines() if samples.exists() else []:
        p = line.split("|")
        rows.append([[int(x, 16) for x in s.split()] for s in p[1:]])
    if not rows or words is None:
        check("run: core 1 sampled and md_xport's words read", False)
        return 1
    fed, _seq, blocks, over = words
    n = 2 * periods
    whole = frames >= n + PAD
    check("xport: every chunk sent, none dropped",
          over == 0 and (blocks == n + PAD and fed == 0 if whole else blocks >= frames),
          f"{blocks} of {n + PAD} blocks sent ({PAD} empty first), {over} dropped, "
          f"feed {'ended' if fed == 0 else f'at {fed:#x}'}")
    lseq, napply, nwords, slips, gaps, bad = rows[-1][0]
    # the calls that took a stream block: seq - 1 - PAD is the chunk
    taken = [(r_[0][0] - 1 - PAD, r_) for r_ in rows if r_[0][0] >= PAD + 1]
    # Once the feed ends, rendering continues with the last LSEQ. Only
    # the first n samples belong to the n stream chunks; the tail is audio
    # decay, not repeated application of the last packet.
    if whole:
        taken = taken[:n]
    seqs = [c for c, _ in taken]
    total = sum(len(v) for c, v in chunks.items() if not seqs or c <= seqs[-1])
    check("glue: every stream block taken once, in order, every word written",
          bool(seqs) and seqs == list(range(len(seqs))) and gaps <= PAD and bad == 0 and slips <= 1
          and nwords == total and napply == lseq - gaps
          and (len(seqs) == n or not whole),
          f"chunks 0..{seqs[-1] if seqs else -1} of {n}, {nwords}/{total} words, "
          f"{gaps} gap(s) in the padding, refused {bad}, sync slips {slips}")
    check("owner: the instance is T1's", rows[-1][3][0] == 0, f"owner offset {rows[-1][3][0]:#x}")

    # core 1's blocks, by (period, slot): chunk c rendered slots 0-7 (c even)
    # or 8-15 (c odd) of period c // 2
    ours = {}
    for c, r_ in taken:
        half = 0 if r_[1][0] == 8 else 8
        if half != 8 * (c % 2):
            check("sync: the halves follow the chunks", False, f"chunk {c} rendered slots {half}-{half + 7}")
            break
        for s in range(half, half + 8):
            ours[(c // 2, s)] = r_[2][32 * s:32 * s + 32]
    common = sorted(set(ours) & set(ref))
    same = [key for key in common if ours[key] == ref[key]]
    first = next((key for key in common if ours[key] != ref[key]), None)
    live = sum(1 for key in common if any(ref[key]))
    check("voices: core 1's blocks equal the replay's", bool(common) and len(same) == len(common)
          and (not whole or set(ref) <= set(ours)),
          f"{len(same)} of {len(common)} blocks bit-identical ({live} non-silent), "
          f"{len({p for p, _ in common})} of {periods} periods"
          + (f"; first difference period {first[0]} slot {first[1]}" if first else ""))
    print(f"  reference vs the Machinedrum's own output ({cap.name}): {summary.split('blocks: ')[1]}")
    print(f"  verify_md_transport: {'PASS' if not fails else f'{fails} FAILED'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
