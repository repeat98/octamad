#!/usr/bin/env python3
"""Character's KEY = T1, on both cores: the compressor keyed from the
BusDelay host's level of T1 (y:$990/$991 in the bus scratch).

Every case renders the SPEC image with both payloads booted, the delay host
on T1 (core 1, position 0) and Characters on FX1 at COMP 127. dsp_host has
one input stream, so every fed instance hears the same signal: a quiet tone
(0.05) with a burst at 0.25 in the middle, the level where the AC1 law's dip
is deepest (Lv = K x level = 1). Gain reduction is the station's out/in gain
in the quiet part minus the same in the burst.

  T1 keys T3     host fed, T3 (core 1) KEY = T1: ducks in the burst
  T1 keys T6     host fed, T6 (core 0) KEY = T1: ducks in the burst; both
                 under four skews
  key is T1's    host NOT fed, T3 fed at KEY = T1: no gain reduction (the
                 level came from T1, not from the station's own input)
  no host        no delay host in the render: KEY = T1 reads a counter that
                 never moves and holds no gain reduction
  SELF           T3 at KEY = SELF is bit-identical with the host fed or not
  master         T8 (core 0 position 3) at KEY = T1 is bit-identical with
                 KEY = SELF: the master receives T1 itself
  T1's print     the host's own output is bit-identical with and without
                 Characters reading it

What this cannot show: the chip's timing (lock-step, or a guessed -skew),
and anything the ColdFire does (knobs are poked into r6).

    python3 tools/verify/verify_charkey.py      # ~1 min
"""
import math
import pathlib
import shutil
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
import send_probe  # noqa: E402
import verify_onebus as ob  # noqa: E402

ob.SCRATCH = ob.OUT / "_charkey"
FRAMES, PAD, BLOCKS = ob.FRAMES, ob.PAD, ob.BLOCKS
QUIET, BURST = 0.05, 0.25
B0, B1 = 300 * FRAMES, 600 * FRAMES          # the burst, samples after PAD
GR_MIN = 6.0                                 # dB: a live key (SELF ducks 8.7 on the same burst)
GR_MAX_IDLE = 0.5                            # dB: no key


def burst_file(path):
    w = 2 * math.pi * ob.TONE_HZ / ob.SR
    with open(path, "wb") as f:
        for i in range(BLOCKS * FRAMES):
            t = i - PAD
            amp = 0.0 if t < 0 else (BURST if B0 <= t < B1 else QUIET)
            f.write(struct.pack("<i", int(amp * math.sin(w * t) * 8388607)))


def gr_db(stream):
    """gain in the quiet stretch before the burst minus gain in the burst,
    the attack's first block and the release's tail left out"""
    L = stream[0]
    q = L[B0 - 200 * FRAMES:B0 - 10 * FRAMES]
    b = L[B0 + 20 * FRAMES:B1 - 10 * FRAMES]
    return (ob.rms_db(q) - 20 * math.log10(QUIET / math.sqrt(2))) - \
           (ob.rms_db(b) - 20 * math.log10(BURST / math.sqrt(2)))


def main():
    ob.SCRATCH.mkdir(parents=True, exist_ok=True)
    snap = ob.SCRATCH / "mainos_bus.snapshot.bin"
    had = ob.IMAGE.is_file()
    if had:
        shutil.copy2(ob.IMAGE, snap)
    try:
        ob.build({"XBUS": "1", "SPEC": "1"}, ob.SCRATCH / "build_spec.log")
        A = send_probe.dump_mem(ob.IMAGE, ob.SCRATCH / "spec_A.mem", "A")
        B = send_probe.dump_mem(ob.IMAGE, ob.SCRATCH / "spec_B.mem", "B")
    finally:
        if had:
            shutil.copy2(snap, ob.IMAGE)
    mems = {0: A, 1: B}
    burst_file(ob.SCRATCH / "burst.raw")
    run = lambda insts, **k: ob.run(mems, insts, tone="burst.raw", **k)   # noqa: E731

    D = lambda fed=True: ob.Inst("DELAY SERVER", 1, 0, fed=fed, WET=0)     # noqa: E731
    C = lambda core, pos, **k: ob.Inst("CHARACTER", core, pos, fx=1, fed=True,  # noqa: E731
                                       **{"COMP": 127, "KLVL": 64, **k})
    bad = []

    def check(ok, what):
        print(f"  [{'PASS' if ok else 'FAIL'}] {what}")
        if not ok:
            bad.append(what)

    print("== T1 keys T3 (core 1) and T6 (core 0) ==")
    for skew in (None,) + ob.SKEWS:
        st = run([D(), C(1, 2, KEY=1), C(0, 1, KEY=1)], skew=skew, tag=f"live{skew}")
        g3, g6 = gr_db(st[1]), gr_db(st[2])
        check(g3 >= GR_MIN and g6 >= GR_MIN,
              f"skew {skew}: T3 ducks {g3:.1f} dB, T6 ducks {g6:.1f} dB (>= {GR_MIN})")

    print("== the key is T1's, not the station's own input ==")
    st = run([D(fed=False), C(1, 2, KEY=1)], tag="hostquiet")
    g = gr_db(st[1])
    check(abs(g) <= GR_MAX_IDLE, f"host silent, T3 KEY = T1: {g:.2f} dB (|x| <= {GR_MAX_IDLE})")
    st = run([C(1, 2, KEY=1), C(0, 1, KEY=1)], tag="nohost")
    g3, g6 = gr_db(st[0]), gr_db(st[1])
    check(abs(g3) <= GR_MAX_IDLE and abs(g6) <= GR_MAX_IDLE,
          f"no host: T3 {g3:.2f} dB, T6 {g6:.2f} dB (|x| <= {GR_MAX_IDLE})")

    print("== SELF and the master ignore T1 ==")
    a = run([D(), C(1, 2, KEY=0)], tag="self_fed")[1]
    b = run([D(fed=False), C(1, 2, KEY=0)], tag="self_quiet")[1]
    check(a == b, "T3 at KEY = SELF: bit-identical with the host fed or silent")
    print(f"      (SELF ducks {gr_db(a):.1f} dB on its own burst)")
    a = run([D(), C(0, 3, KEY=1)], tag="master_t1")[1]
    b = run([D(), C(0, 3, KEY=0)], tag="master_self")[1]
    check(a == b, "T8 at KEY = T1: bit-identical with KEY = SELF")

    print("== T1's print ==")
    a = run([D()], tag="host_alone")[0]
    b = run([D(), C(1, 2, KEY=1), C(0, 1, KEY=1)], tag="host_read")[0]
    check(a == b, "the host's output: bit-identical with and without Characters reading it")

    print(f"\n{'PASS' if not bad else 'FAIL'}: {len(bad)} failing")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
