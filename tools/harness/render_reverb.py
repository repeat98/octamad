#!/usr/bin/env python3
"""
Render real audio through BusVerb in the emulator, so voicing can be judged by
ear without a flash.

    python3 tools/harness/render_reverb.py loop.wav
    python3 tools/harness/render_reverb.py loop.wav -p TIME=100 -p SIZE=127 -p WET=80
    python3 tools/harness/render_reverb.py loop.wav --sweep SIZE=0,64,127 --wet
    python3 tools/harness/render_reverb.py loop.wav --mode all       # all three characters
    python3 tools/harness/render_reverb.py loop.wav --build          # rebuild first

tools/harness/dsp_host runs the assembled instruction stream with the
DSP56300 arithmetic emulated exactly, about 6x faster than real time.

What it cannot tell you, and still needs a flash:
  * whether the layout fits the cycle budget -- the harness renders code
    that cannot run on the chip
  * anything ColdFire-side: menu, descriptors, knob labels, parameter
    ranges. -params pokes r6 directly and bypasses all of it
  * the ColdFire's timing between the two cores (dsp_host boots both since
   , lock-step; tools/harness/rig_render.py renders the whole rig)
  * multi-instance behaviour under a nonzero split, where there is a known
    unexplained one-vs-two-instance divergence

Voice here; spend flashes on the cycle budget and the UI surface.
"""
import argparse, array, hashlib, math, os, pathlib, re, shutil, struct, subprocess, sys, wave

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path)
from remix import registry  # noqa: E402
HOST = ROOT / "vendor/dsp56300/build/source/dsp_host/dsp_host"
IMAGE = ROOT / "out/mainos_bus.bin"
MEM = ROOT / "out/dsp/mem_reverb_server_A.mem"
CACHE = ROOT / "out/render"          # engine-keyed render artifacts, see engine()


# ---- provenance ----------------------------------------------------------

# Every env var build_bus.py branches on -- grep 'environ' tools/build/build_bus.py.
# A var missing from this list is a way to change the build without changing
# the fingerprint, which is the exact bug this guards against.
BUILD_ENV = ("RVSRC", "MODE", "WIDTH", "NOSHIM", "XBUS", "SPEC", "DEV", "BURN",
             "PROBE", "XPROBE", "XBUS_BASE", "DELAYPROBE",
             "DLSRC", "MARKER", "DMODE", "DINT", "TPROBE",
             "REMIX", "NOTEMPO", "TEMPOCAVE", "HKB", "DNOTE")


def fingerprint(extra=()):
    """sha256 over every input that can change the assembled instruction stream:
    all DSP and module sources, the build engine, and the env vars it
    branches on."""
    h = hashlib.sha256()
    srcs = (list(ROOT.glob("dsp/*.asm")) + list(ROOT.glob("dsp/*.inc"))
            + list(ROOT.glob("modules/*/*.asm")) + list(ROOT.glob("modules/*/*.s"))
            + list(ROOT.glob("modules/*/manifest.py")) + list(ROOT.glob("remixes/*.py"))
            + list(ROOT.glob("tools/remix/*.py")))
    for p in sorted(srcs, key=lambda p: str(p.relative_to(ROOT))):
        h.update(str(p.relative_to(ROOT)).encode()); h.update(p.read_bytes())
    for p in ("tools/build/build_bus.py", "tools/build/dsp_modmap.py"):
        h.update((ROOT / p).read_bytes())
    for k in BUILD_ENV:
        h.update(f"{k}={os.environ.get(k, '')}\n".encode())
    for k, v in extra:
        h.update(f"{k}={v}\n".encode())
    return h.hexdigest()


def sha(path, n=12):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()[:n]


def prov_ok(img, fp):
    """True when `img` was built from fingerprint `fp` and still exists."""
    tag = img.with_suffix(img.suffix + ".prov")
    return img.exists() and tag.exists() and tag.read_text().strip() == fp


def prov_stamp(img, fp):
    img.with_suffix(img.suffix + ".prov").write_text(fp + "\n")

SR = 44100
FRAMES = 16              # the firmware's frame (the harness's own cap is 15: the & 0xf
WARMUP_BLOCKS = 260      # the engine stays dry for 256 CALLS; pad past it and trim

PARAMS = [("SEND", 64), ("TIME", 64), ("SIZE", 127), ("SHMR", 0), ("SHFT", 0),
          ("WET", 127), ("_C", 0), ("TONE", 64), ("DIFF", 64), ("_9", 0),
          ("GATE", 0), ("_11", 0)]   # the 16 Sep 2026 layout: TIME-SIZE, SHMR-SHFT linked; TONE on page 2
NAMES = {n: i for i, (n, _) in enumerate(PARAMS)}
# _C (index 6) is MODE's slot; --mode owns it, so no knob.
KNOBS = ", ".join(n for n, _ in PARAMS if n != "_C")


def die(msg):
    sys.exit(f"render_reverb: {msg}")


# ---- WAV in --------------------------------------------------------------
def read_wav(path):
    """-> (mono float list in -1..1, samplerate). Stereo is summed to mono:
    the harness feeds one mono stream and the engine sums L+R itself."""
    chans, sr = read_wav_channels(path)
    if len(chans) == 1:
        return chans[0], sr
    return [sum(c[i] for c in chans) / len(chans) for i in range(len(chans[0]))], sr


def read_wav_channels(path):
    """-> ([channel float lists in -1..1], samplerate), channels kept apart
    (rig_render's mixer model applies AMP BAL per side)."""
    with wave.open(str(path), "rb") as w:
        ch, sw, sr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    if sw == 1:
        vals = [(b - 128) / 128.0 for b in raw]
    elif sw == 2:
        a = array.array("h"); a.frombytes(raw); vals = [v / 32768.0 for v in a]
    elif sw == 3:
        vals = []
        for i in range(0, len(raw), 3):
            v = raw[i] | (raw[i + 1] << 8) | (raw[i + 2] << 16)
            vals.append(((v - 0x1000000) if v & 0x800000 else v) / 8388608.0)
    elif sw == 4:
        a = array.array("i"); a.frombytes(raw); vals = [v / 2147483648.0 for v in a]
    else:
        die(f"unsupported sample width {sw*8}-bit in {path}")
    return [vals[c::ch] for c in range(ch)], sr


def resample(x, src, dst):
    """Naive linear resample. Good enough to audition a reverb; not a
    mastering-grade converter, so prefer 44.1 kHz sources."""
    if src == dst:
        return x
    ratio = dst / src
    out = []
    for i in range(int(len(x) * ratio)):
        p = i / ratio
        j = int(p)
        f = p - j
        a = x[j] if j < len(x) else 0.0
        b = x[j + 1] if j + 1 < len(x) else a
        out.append(a + (b - a) * f)
    return out


def write_wav(path, left, right):
    b = bytearray()
    for l, r in zip(left, right):
        for s in (l, r):
            s = max(-8388608, min(8388607, int(s)))
            b += (s & 0xFFFFFF).to_bytes(3, "little")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2); w.setsampwidth(3); w.setframerate(SR)
        w.writeframes(bytes(b))


# ---- the emulator --------------------------------------------------------
def engine():
    """(source path, cache stem) for the reverb engine being rendered.

    THE RENDER CACHE IS KEYED BY ENGINE, NOT JUST BY MODE AND MTIME. It has
    to be. build_bus.py writes every MODE build to the one path
    out/mainos_bus_mode{N}.bin whatever RVSRC says, so under mode+mtime
    keying alone an A/B between two engines silently replays whichever build
    landed there first: render `RVSRC=dsp/some_alt_engine.asm` and then the
    default, and the default reuses the 8-line image whenever its own source
    is older than that build -- the normal case for a file that has been
    sitting in the tree.

    The failure is invisible. The render succeeds, the report prints, the
    numbers are simply the other engine's. It cost a round of concluding the
    eight-line tank sounded exactly like the four-line one, because it WAS
    the four-line one. Every artifact below therefore carries the engine's
    stem, and build_bus.py's fixed output path is treated as scratch that is
    moved into the keyed cache immediately after each build."""
    rv = os.environ.get("RVSRC") or registry.asm("busverb")
    if not (ROOT / rv).exists():
        die(f"RVSRC={rv} does not exist")
    return rv, re.sub(r"[^A-Za-z0-9]+", "-", pathlib.Path(rv).stem)


def claim(built, dest):
    """Move build_bus.py's fixed-path output into the engine-keyed cache.

    A move, not a copy: leaving one engine's build behind at the shared path
    is exactly the aliasing this cache exists to prevent, because a later run
    for a different engine would find a file with a fresh mtime and reuse
    it."""
    if not built.exists():
        die(f"build did not produce {built.relative_to(ROOT)}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(built), str(dest))
    return dest


def ensure_mem(build):
    rvsrc, stem = engine()
    # The default engine renders out/mainos_bus.bin in place -- that is the
    # shipping artifact and `make render`'s documented subject. An alternate
    # RVSRC must never be left sitting at that path pretending to be it.
    alt = bool(os.environ.get("RVSRC"))
    # DEV=1 annexes CHORUS's module as a fourth donor, which is 329 free words
    # on payload A where the shipping build has almost none (FREE 32,
    #). That is the room to
    # develop an engine change in before paying for it -- a DEV build is never
    # flashed, so it proves the SOUND without also having to have solved the
    # space problem. `make check` still gates what ships.
    dev = os.environ.get("DEV") == "1"
    if dev:
        img = ROOT / "out/mainos_bus_dev.bin"
        mem = ROOT / "out/dsp/mem_dev_A.mem"
    else:
        img = CACHE / f"{stem}.bin" if alt else IMAGE
        mem = CACHE / f"{stem}_A.mem" if alt else MEM
    fp = fingerprint([("XBUS", "1"), ("SPEC", "1"), ("RVSRC", rvsrc if alt else "")])
    if build or not prov_ok(img, fp) or not mem.exists():
        print(f"building {img.relative_to(ROOT)} ...")
        env = dict(os.environ, XBUS="1", SPEC="1")
        if alt:
            env["RVSRC"] = rvsrc
        r = subprocess.run([sys.executable, "tools/build/build_bus.py"], cwd=ROOT,
                           env=env, capture_output=True, text=True)
        if r.returncode != 0:
            die(f"build_bus.py failed:\n{r.stdout[-2000:]}{r.stderr[-2000:]}")
        if alt and not dev:
            claim(IMAGE, img)
        if not HOST.exists():
            die(f"missing {HOST.relative_to(ROOT)} -- run 'make setup'")
        if not dev:                         # the DEV build dumps its own .mem
            sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path)
            import dsp_modmap
            mem.parent.mkdir(parents=True, exist_ok=True)
            dsp_modmap.dumpmem(img.read_bytes(), ["A", str(mem)])
        prov_stamp(img, fp)                 # stamp LAST: a crash mid-build must
    else:                                   # not leave a valid-looking artifact
        print(f"reusing {img.relative_to(ROOT)} (fingerprint {fp[:12]} unchanged)")
    return mem


MODES = ["ROOM", "PLATE", "BIG"]     # modules/busverb/reverb_server.asm's md_* order


def ensure_mode_mem(mode, build):
    """Payload-A dump of a build with MODE assembled in, one image per mode.

    build_bus.py's MODE= override substitutes the value for the page-2 read,
    which is the only way to hear a character here -- the slot itself is a
    companion field and dsp_host cannot write those. Those images are
    diagnostic (the real MODE slot is ignored), so they get their own paths
    and are never the flashable out/mainos_bus.bin."""
    rvsrc, stem = engine()
    img = CACHE / f"{stem}_mode{mode}.bin"
    mem = CACHE / f"{stem}_mode{mode}_A.mem"
    # Rebuild whenever ANY build input changed -- a stale mode render silently
    # voices the previous constants, and mtime keying missed exactly that.
    dev = os.environ.get("DEV") == "1"
    fp = fingerprint([("MODE", str(mode)), ("XBUS", "1"), ("SPEC", "1"),
                      ("RVSRC", rvsrc)])
    if build or not prov_ok(img, fp) or not mem.exists():
        print(f"building {img.name} (MODE={mode} {MODES[mode]}) ...")
        # RVSRC= passthrough so alternate engines can be rendered without
        # copying files: RVSRC=dsp/some_alt_engine.asm make reverb ...
        env = dict(os.environ, MODE=str(mode), XBUS="1", SPEC="1", RVSRC=rvsrc)
        r = subprocess.run([sys.executable, "tools/build/build_bus.py"], cwd=ROOT,
                           env=env, capture_output=True, text=True)
        if r.returncode != 0:
            die(f"build_bus.py MODE={mode} failed:\n{r.stdout[-2000:]}{r.stderr[-2000:]}")
        # DEV=1 writes the dev-named image and dumps its own .mem; a plain
        # build writes the per-mode path and needs the dump doing here. The
        # MODE override costs 2 words the shipping region does not have, so
        # --mode in practice always needs --dev.
        built = ROOT / ("out/mainos_bus_dev.bin" if dev
                        else f"out/mainos_bus_mode{mode}.bin")
        claim(built, img)
        if not HOST.exists():
            die(f"missing {HOST.relative_to(ROOT)} -- run 'make setup'")
        sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path)
        import dsp_modmap
        mem.parent.mkdir(parents=True, exist_ok=True)
        dsp_modmap.dumpmem(img.read_bytes(), ["A", str(mem)])
        prov_stamp(img, fp)
    else:
        print(f"reusing {img.name} (fingerprint {fp[:12]} unchanged)")
    return mem


REVERB_ID = 0x07                 # NEW_IDS["REVERB SERVER"] in build_bus.py
INIT_TAB, PROC_TAB = 0x215, 0x235    # X memory, the dispatcher's two tables


def _guarded(mem):
    """Does the SELECTED REMIX compile the HOSTGUARD into the reverb?

    Read from the remix rather than from the dump: a .mem carries no marker
    that survives assembly cleanly, and every other tool here already keys
    off REMIX. A remix that hides the reverb guards it (build_bus.py), and a
    guarded engine only runs on the bank's FIRST FX2 slot.
    """
    try:
        sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401  (every tools/ dir on sys.path)
        from remix import registry
        r = registry.remix(os.environ.get("REMIX") or registry.DEFAULT_REMIX)
        return "REVERB SERVER" in r.hidden
    except Exception:
        return False


def entry_points(mem_path):
    """Read the reverb's init/proc addresses out of the dump being rendered.

    Hardcoded as 1252/1253 until v98 repacked the servers to give CHORUS's
    module back to stock. A hardcoded entry point does not fail loudly when
    the code moves -- it jumps into the middle of whatever now lives there --
    so it is read from X:0x215/0x235, the same tables the hardware dispatches
    through. Reading the .mem rather than the image also keeps --mem honest:
    two builds being A/B'd need not put the engine at the same address.
    """
    blob = mem_path.read_bytes()
    want = {INIT_TAB + REVERB_ID, PROC_TAB + REVERB_ID}
    found, pos = {}, 0
    while pos + 9 <= len(blob):
        sp, addr, cnt = struct.unpack_from("<BII", blob, pos)
        pos += 9
        if sp == 0xff:
            break
        if sp == 1:                                  # X space
            for a in want:
                if addr <= a < addr + cnt:
                    found[a] = struct.unpack_from("<I", blob, pos + (a - addr) * 4)[0]
        pos += cnt * 4
    init, proc = found.get(INIT_TAB + REVERB_ID), found.get(PROC_TAB + REVERB_ID)
    if init is None or proc is None:
        die(f"no dispatch table in {mem_path.name} -- cannot locate the engine")
    if not 0 < init < 0x20000 or proc != init + 1:
        die(f"implausible reverb entry points in {mem_path.name}: "
            f"init 0x{init:05x} proc 0x{proc:05x}")
    return init, proc


def run(mem, src, values, tail_s, verbose, entry=None, frames=FRAMES):
    """src: mono floats at SR. -> (L, R) as 24-bit ints, warm-up trimmed."""
    pad = WARMUP_BLOCKS * frames
    total = pad + len(src) + int(tail_s * SR)
    blocks = -(-total // frames)
    n = blocks * frames

    tmp = ROOT / f"out/dsp/_render_in_{os.getpid()}.raw"
    out = ROOT / f"out/dsp/_render_out_{os.getpid()}.raw"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    with open(tmp, "wb") as f:
        for i in range(n):
            v = src[i - pad] if pad <= i < pad + len(src) else 0.0
            f.write(struct.pack("<i", max(-8388608, min(8388607, int(v * 8388607)))))

    init, proc = entry or entry_points(mem)
    # ⚠️ THE STATE BLOCK IS NOT FREE TO CHOOSE ANY MORE. A remix that HIDES
    # the reverb compiles in build_bus.py's HOSTGUARD, which runs the engine
    # on the bank's FIRST FX2 slot (r7 = 0x6200, `-r7 2`) and passes dry on
    # every other -- so the historical `-r7 4`, the SECOND slot, renders
    # silence and every comparison built on it goes blind. verify_burn caught
    # exactly that on the first guarded remix: it reported its own harness
    # insensitive rather than reporting a result, which is the gate working.
    # RVR7 overrides; the default follows the image on disk.
    r7 = os.environ.get("RVR7") or ("2" if _guarded(mem) else "4")
    cmd = [str(HOST), "-mem", str(mem), "-init", f"{init:x}", "-proc", f"{proc:x}",
           "-inst", "1", "-r7", r7, "-alloc", "3", "-blocks", str(blocks),
           "-frames", str(frames), "-in", str(tmp), "-out", str(out),
           "-params", ",".join(str(v) for v in values)]
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        die(f"dsp_host failed:\n{r.stdout[-2000:]}{r.stderr[-2000:]}")
    if verbose:
        print(r.stdout.strip().splitlines()[-1])

    a = array.array("i")
    a.frombytes(out.read_bytes())
    return list(a[0::2])[pad:], list(a[1::2])[pad:]


# ---- reporting -----------------------------------------------------------
# ⚠️ "tail to -60 dB" CANNOT TELL DECAY FROM RUNAWAY. It scores the last
# window above -60 dB RELATIVE TO THE TAIL'S OWN PEAK, so a tail that GROWS
# scores as a magnificent one -- it reported 7.90 s for an engine that was
# diverging, and that number was written down as proof the eight-line tank
# worked (docs/history/VOICING.md, "a single scalar cannot tell decay from runaway").
# Read the per-second envelope before believing it.
def report(label, L, R, src_len, normalized=False):
    peak = max((abs(v) for v in L + R), default=0)
    clip = sum(1 for v in L + R if abs(v) >= 8388607)
    tail = L[src_len:] or L
    w = SR // 10
    env = [math.sqrt(sum(s * s for s in tail[i:i + w]) / w)
           for i in range(0, max(len(tail) - w, 1), w)]
    rt = 0.0
    if env and max(env) > 0:
        pk = max(env)
        above = [i for i, e in enumerate(env) if 20 * math.log10(max(e, 1e-9) / pk) > -60]
        if above:
            rt = (above[-1] + 1) * w / SR
    rms = math.sqrt(sum(v * v for v in L) / max(len(L), 1)) / 8388607
    print(f"  {label:28s} peak {peak/8388607:5.2f} FS  rms {20*math.log10(max(rms,1e-9)):6.1f} dBFS"
          f"  tail to -60 dB {rt:5.2f} s"
          + ("  [normalised]" if normalized else "")
          + (f"   *** {clip} CLIPPED SAMPLES ***" if clip else ""))


def main():
    ap = argparse.ArgumentParser(description="Render audio through BusVerb in the emulator.")
    ap.add_argument("input", help="source .wav (mono or stereo; 44.1 kHz preferred)")
    ap.add_argument("-o", "--out", help="output .wav (default: alongside the source)")
    ap.add_argument("-p", "--param", action="append", default=[], metavar="NAME=VAL",
                    help="knob, 0..127: " + KNOBS)
    ap.add_argument("--sweep", metavar="NAME=a,b,c", help="one render per value")
    ap.add_argument("--wet", action="store_true",
                    help="wet only (out minus the dry path, exact -- not a MIX trick)")
    ap.add_argument("--tail", type=float, default=8.0, help="seconds of ring-out (default 8)")
    ap.add_argument("--gain", type=float, default=1.0, help="input gain, linear (default 1.0)")
    ap.add_argument("--normalize", action="store_true",
                    help="peak-normalise the OUTPUT to -1 dBFS. Does not change what the "
                         "hardware would do -- it just makes quiet renders (impulses, "
                         "--wet tails) auditionable without riding the volume knob.")
    ap.add_argument("--mode", metavar="N|all",
                    help="audition MODE characters: 0 ROOM, 1 PLATE, 2 BIG, "
                         "or 'all'. Assembles the value in (the slot is "
                         "a companion field dsp_host cannot drive)")
    ap.add_argument("--build", action="store_true", help="run build_bus.py first")
    ap.add_argument("--dev", action="store_true",
                    help="build with DEV=1: annexes CHORUS's module for 329 extra "
                         "program words on payload A, where the shipping build has "
                         "almost none (FREE 32). Never flashable -- for proving a change SOUNDS right "
                         "before paying for its space")
    ap.add_argument("--mem", metavar="FILE",
                    help="render through a different payload dump instead of the "
                         "current build -- how you A/B two engine versions on the "
                         "same source (keep the old .mem when you change the engine)")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--frames", type=int, default=FRAMES,
                    help="samples per block: 16 = the firmware's frame (default); 15 = the old harness")
    a = ap.parse_args()
    if a.dev:
        os.environ["DEV"] = "1"     # before any fingerprint() call -- DEV is in
                                    # BUILD_ENV, so it keys the cache correctly

    values = [d for _, d in PARAMS]
    for spec in a.param:
        if "=" not in spec:
            die(f"bad -p {spec!r}, want NAME=VALUE")
        k, v = (s.strip() for s in spec.split("=", 1))
        if k.upper() not in NAMES or k.upper() == "_C":
            die(f"unknown knob {k!r}; known: {KNOBS}")
        values[NAMES[k.upper()]] = max(0, min(127, int(v)))

    sweep = []
    if a.sweep:
        k, vs = a.sweep.split("=", 1)
        if k.upper() not in NAMES or k.upper() == "_C":
            die(f"unknown knob {k!r}; known: {KNOBS}")
        sweep = [(k.upper(), int(v)) for v in vs.split(",")]

    src_path = pathlib.Path(a.input)
    if not src_path.exists():
        die(f"no such file: {src_path}")
    src, sr = read_wav(src_path)
    if sr != SR:
        print(f"note: {sr} Hz source, linearly resampled to {SR} -- prefer 44.1 kHz sources")
        src = resample(src, sr, SR)
    if a.gain != 1.0:
        src = [v * a.gain for v in src]

    if a.mode is not None:
        if a.mem:
            die("--mode builds its own images; --mem renders a prebuilt dump. Pick one.")
        if a.mode.lower() == "all":
            modes = list(range(len(MODES)))
        elif a.mode.isdigit() and int(a.mode) < len(MODES):
            modes = [int(a.mode)]
        else:
            die(f"bad --mode {a.mode!r}; want 0..{len(MODES)-1} or 'all'")
        renders = [(ensure_mode_mem(m, a.build), MODES[m]) for m in modes]
    else:
        mem = pathlib.Path(a.mem) if a.mem else ensure_mem(a.build)
        if a.mem and not mem.exists():
            die(f"no such payload dump: {mem}")
        if a.mem:
            # --mem is for A/B'ing a KEPT dump against a new build. It does not
            # assemble anything, so edits made since that dump was written are
            # not in it. That is the flag's purpose, but it has also been the
            # way an edit went unheard, so it announces itself.
            print(f"  --mem: NO BUILD RUN. Rendering the prebuilt dump {mem} "
                  f"as-is;\n         source edits since it was written are NOT in it.")
        renders = [(mem, None)]
    out_base = pathlib.Path(a.out) if a.out else src_path.with_suffix("")
    print(f"{src_path.name}: {len(src)/SR:.1f} s + {a.tail:.0f} s tail"
          + (f"   [{'wet only' if a.wet else 'wet+dry'}]"))

    jobs = [(dict(zip(NAMES, values)), out_base, None)] if not sweep else []
    for k, v in sweep:
        vals = dict(zip(NAMES, values)); vals[k] = v
        jobs.append((vals, pathlib.Path(f"{out_base}_{k}{v}"), k))

    seen = {}                       # audio sha -> first filename that produced it
    for mem, mode_name in renders:
        # The dump actually handed to dsp_host. Printed every time: this line
        # is the answer to "am I hearing the code I just edited?"
        print(f"  engine {mem.name}  [payload {sha(mem)}]")
        for vals, dest, swept in jobs:
            vlist = [vals[n] for n, _ in PARAMS]
            L, R = run(mem, src, vlist, a.tail, a.verbose, frames=a.frames)
            if a.wet:
                # output = dry + wet, and the dry path is the mono input duplicated,
                # so subtracting it recovers the wet exactly.
                # ⚠️ TRUE AGAIN SINCE v5.
                # It was FALSE for the v4 window (17-23 Aug 2026): the return
                # printed the wet ALONE, so --wet subtracted a phantom dry and
                # produced wet-minus-dry -- any --wet render from that window
                # is suspect. Without --wet, v4 renders were already wet-only
                # (correct), and v5 renders are dry+wet as labelled.
                dry = [int(v * 8388607) for v in src] + [0] * (len(L) - len(src))
                L = [l - d for l, d in zip(L, dry)]
                R = [r - d for r, d in zip(R, dry)]
            # name the knobs that differ from the defaults, and always the swept one
            # (a sweep can legitimately pass through a knob's own default value)
            label = " ".join(f"{n}={vals[n]}" for n, _ in PARAMS
                             if n != "_C" and (n == swept or vals[n] != dict(PARAMS)[n])) \
                    or "defaults"
            if mode_name:
                label = f"{mode_name:<6s} {label}"
            report(label, L, R, len(src), a.normalize)   # BEFORE normalising --
            # rescaling first would move the rail out from under the clip counter
            # and report a saturated render as clean
            if a.normalize:
                pk = max((abs(v) for v in L + R), default=0)
                if pk:
                    g = (8388607 * 0.891) / pk          # -1 dBFS
                    L = [v * g for v in L]; R = [v * g for v in R]
            # NOT with_suffix: an output name containing a dot ("trim_0.25") has
            # everything from that dot replaced, silently colliding two renders
            d = dest if not mode_name else dest.with_name(f"{dest.name}_{mode_name}")
            d = d if d.suffix.lower() == ".wav" else d.with_name(d.name + ".wav")
            if d.resolve() == src_path.resolve():
                die(f"output would overwrite input: {d}\n"
                    f"  use -o to pick a different output, or --mode to add a suffix")
            # An A/B is only evidence if the two sides actually differ. Compare
            # against what was at this path before, and against every other
            # render this invocation produced, and SAY SO when they match --
            # a silent no-op render is what made five shimmer iterations
            # indistinguishable from each other on 8 Aug (see fingerprint()).
            before = sha(d) if d.exists() else None
            write_wav(d, L, R)
            now = sha(d)
            note = ""
            if before == now:
                note = "   *** IDENTICAL to the file already at this path ***"
            elif now in seen:
                note = f"   *** IDENTICAL to {seen[now]} ***"
            seen.setdefault(now, d.name)
            print(f"  -> {d}  [audio {now}]{note}")


if __name__ == "__main__":
    main()
