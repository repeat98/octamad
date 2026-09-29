#!/usr/bin/env python3
"""Prove CC FEEDBACK's sweep (modules/cc-feedback/cc_feedback.s) against the
stock emitter in the emulator.

The unit is assembled and linked at a test address and its sweep called
directly (the keyrepeat-loop detour is the build's; `verify_set` runs it
under the port). Stock's emitter 0x40033e3c runs as the image carries it.

1. Eight sweeps over eight tracks on channels 0..7 with every mapped lane
   byte non-zero: the emitter is entered once per (track, CC) of the map,
   336 times, with the lane's value; its per-channel cache holds the lane;
   its dirty bitmap has exactly the 42 mapped CCs per channel; the channel
   mask reads 0xff; INTFRCH bit 2 (source 34, the drainer) is forced.
2. Eight more sweeps: nothing is emitted (the cache is the diff).
3. One mapped byte changes: exactly one message, that CC, that value.
4. An unmapped lane byte changes (PLAYBACK page 2, AMP page 2): nothing.
5. AUDIO CC OUT bit 1 clear: nothing; set again: the change is sent.
6. A track whose trig channel is off: nothing; on again: sent.
7. A MIDI track on the same channel: the emitter is entered and refuses
   (cache unchanged); cleared: sent.
8. The engine task running a command (its queue's waiting-TCB slot 0):
   nothing is swept and the track index holds; idle again: sent.
"""
import os
import pathlib
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
try:
    import emu_bringup as emu
    from unicorn import UC_HOOK_CODE
    from unicorn.m68k_const import UC_M68K_REG_A7
except ImportError:
    print("  [SKIP] verify_ccfeedback: no unicorn (the .venv: make emu-setup)")
    sys.exit(0)
from remix import registry  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / "modules/cc-feedback/cc_feedback.s"
UNIT_AT = 0x40300000            # a fresh RWX page, away from the OS image
EMIT = 0x40033e3c
EMIT_FORCE = 0x40033ece           # its `orl %d0,0xfc048010`: INTFRCH bit 2 = source 34, the soft-timer dispatcher
CCOUT, TRIGCH, LIVEB = 0x8000004a, 0x8000003f, 0x80000810
CACHE, BITMAP, CHMASK, TXBUSY = 0x46c7bf2c, 0x46c7d7d8, 0x46c7e0de, 0x46c7ca34
MIDITRK, MIDITRK_STRIDE = 0x46c76de0, 68     # the eight MIDI tracks' channel bytes (0 = off, else ch+1)
ENGQ_WAITER, ENGINE_TCB = 0x460d17ce + 0xc, 0x460ddde4   # the engine blocked on its queue: its TCB parked by the event wait
# The unit's map, as cc_feedback.s: (lane offset, CC)
MAP = [(i, 16 + i) for i in range(30)] + [(0x32 + i, 68 + i) for i in range(6)] + [(0x38 + i, 62 + i) for i in range(6)]
UNMAPPED = [0x20, 0x25, 0x2c, 0x31, 0x3e, 0x47]
# Any image without the DRAM platform boots under unicorn; the CC MAP fixture
# is the one verify_ccmap builds, so the build memo serves it warm.
FIXTURE_REMIX = registry.fixture("CC MAP", "REVERB SERVER", "DELAY SERVER", "CHARACTER", without_runtime=True)


def _build(remix):
    env = dict(os.environ, REMIX=remix, XBUS="1", SPEC="1")
    r = subprocess.run([sys.executable, str(ROOT / "tools/build/build_bus.py")],
                       env=env, capture_output=True, text=True, cwd=ROOT)
    if r.returncode:
        sys.exit(f"verify_ccfeedback: building {remix} failed:\n{(r.stdout + r.stderr)[-1500:]}")
    return ROOT / "out/mainos_bus.bin"


def _link(at):
    """The unit linked at `at`: (bytes, {symbol: address})."""
    with tempfile.TemporaryDirectory() as d:
        o, e, b = (pathlib.Path(d) / n for n in ("cf.o", "cf.elf", "cf.bin"))
        subprocess.run(["m68k-elf-as", "-mcpu=54455", "-o", str(o), str(SRC)], check=True)
        subprocess.run(["m68k-elf-ld", f"-Ttext=0x{at:x}", "-e", "cf_tick", "-o", str(e), str(o)], check=True)
        subprocess.run(["m68k-elf-objcopy", "-O", "binary", "-j", ".text", str(e), str(b)], check=True)
        nm = subprocess.run(["m68k-elf-nm", str(e)], check=True, capture_output=True, text=True).stdout
        syms = {m.group(2): int(m.group(1), 16) for m in re.finditer(r"^([0-9a-f]+) [TtDdBb] (\w+)$", nm, re.M)}
        return b.read_bytes(), syms


def lane_value(t, off):
    return (t * 13 + off * 7) % 127 + 1


def main():
    import shutil
    if not all(shutil.which(x) for x in ("m68k-elf-as", "m68k-elf-ld", "m68k-elf-objcopy", "m68k-elf-nm")):
        print("  [SKIP] verify_ccfeedback: no m68k-elf toolchain")
        return 0
    blob, syms = _link(UNIT_AT)
    sweep, track_var = syms["cf_sweep"], syms["cf_track"]
    print(f"  unit: {len(blob)} bytes; cf_sweep +0x{sweep - UNIT_AT:x}, cf_track +0x{track_var - UNIT_AT:x}")

    r = emu.boot(str(_build(FIXTURE_REMIX)))
    uc = r.uc
    assert r.clean, f"{FIXTURE_REMIX} did not boot to the RTOS handoff: {r.stopped}"
    uc.mem_write(UNIT_AT, blob)

    calls = []
    def on_emit(u, a, s, x):
        sp = u.reg_read(UC_M68K_REG_A7)
        args = [int.from_bytes(u.mem_read(sp + 4 + 4 * i, 4), "big") for i in range(3)]
        calls.append((args[0], args[1], args[2] & 0xff))
    uc.hook_add(UC_HOOK_CODE, on_emit, begin=EMIT, end=EMIT + 2)
    # the emitter's `orl #4,INTFRCH` (0x40033ece): the drainer forced. The
    # MMIO page reads back all-ones under unicorn, so count the instruction.
    forced = [0]
    uc.hook_add(UC_HOOK_CODE, lambda u, a, s, x: forced.__setitem__(0, forced[0] + 1), begin=EMIT_FORCE, end=EMIT_FORCE + 2)

    def reset_stock():
        uc.mem_write(CCOUT, b"\x02")                       # EXT
        uc.mem_write(ENGQ_WAITER, ENGINE_TCB.to_bytes(4, "big"))   # the engine idle
        for t in range(8):
            uc.mem_write(TRIGCH + t, bytes([t]))
            uc.mem_write(MIDITRK + t * MIDITRK_STRIDE, b"\x00")
        uc.mem_write(CACHE, bytes(16 * 128))
        uc.mem_write(BITMAP, bytes(16 * 16))
        uc.mem_write(CHMASK, bytes(4))
        uc.mem_write(TXBUSY, bytes(4))
        forced[0] = 0
        uc.mem_write(track_var, b"\x00")
        for t in range(8):
            lane = bytearray(72)
            for off in range(72):
                lane[off] = 0x55
            for off, _ in MAP:
                lane[off] = lane_value(t, off)
            uc.mem_write(LIVEB + t * 72, bytes(lane))

    def sweeps(n=8):
        del calls[:]
        for _ in range(n):
            emu._call(uc, sweep, (), count=2_000_000)
        return list(calls)

    def cache(t, cc):
        return uc.mem_read(CACHE + t * 128 + cc, 1)[0]

    def bits(ch):
        words = [int.from_bytes(uc.mem_read(BITMAP + ch * 16 + 4 * k, 4), "big") for k in range(4)]
        return {cc for cc in range(128) if words[cc // 32] >> (cc % 32) & 1}

    fails = 0
    def check(label, ok, detail=""):
        nonlocal fails
        fails += 0 if ok else 1
        print(f"  [{'ok' if ok else 'FAIL'}] {label}{'  ' + detail if detail else ''}")

    # 1. the full dump
    reset_stock()
    got = sweeps()
    want = [(t, cc, lane_value(t, off)) for t in range(8) for off, cc in MAP]
    check("dump: 8 sweeps enter the emitter once per mapped (track, CC) with the lane's value",
          got == want, f"{len(got)} calls (want {len(want)})" + ("" if got == want else f"; first diff {next((g, w) for g, w in zip(got, want) if g != w) if len(got) == len(want) else '(length)'}"))
    check("dump: the emitter's cache holds every mapped lane byte",
          all(cache(t, cc) == lane_value(t, off) for t in range(8) for off, cc in MAP))
    check("dump: each channel's dirty bitmap is exactly the 42 mapped CCs",
          all(bits(ch) == {cc for _, cc in MAP} for ch in range(8)), f"ch0 {sorted(bits(0))}")
    check("dump: the channel mask reads 0xff", uc.mem_read(CHMASK, 4) == b"\x00\x00\x00\xff",
          uc.mem_read(CHMASK, 4).hex())
    check("dump: the emitter forced INTFRCH bit 2 (source 34, the drainer) on every call",
          forced[0] == len(want), f"{forced[0]} forces")
    check("dump: cf_track wrapped to 0 after eight sweeps", uc.mem_read(track_var, 1) == b"\x00")

    # 2. idempotent
    got = sweeps()
    check("diff: eight more sweeps emit nothing", got == [], f"{len(got)} calls")

    # 3. one mapped byte
    uc.mem_write(LIVEB + 3 * 72 + 0x38, b"\x05")
    got = sweeps()
    check("diff: one FX2 page-2 byte on T4 -> one message, CC 62 = 5", got == [(3, 62, 5)], f"{got}")
    check("diff: the cache follows", cache(3, 62) == 5)

    # 4. unmapped bytes
    for off in UNMAPPED:
        uc.mem_write(LIVEB + 3 * 72 + off, b"\x09")
    got = sweeps()
    check("map: unmapped lane bytes (PLAYBACK/AMP page 2, past the FX2 lane) emit nothing", got == [], f"{got}")

    # 5. EXT off
    uc.mem_write(CCOUT, b"\x01")                            # INT only
    uc.mem_write(LIVEB + 1 * 72 + 0x0c, b"\x07")            # LFO slot 0 on T2
    got = sweeps()
    check("gate: AUDIO CC OUT without EXT emits nothing", got == [], f"{got}")
    uc.mem_write(CCOUT, b"\x02")
    got = sweeps()
    check("gate: EXT on again -> the pending change is sent (T2 CC 28 = 7)", got == [(1, 28, 7)], f"{got}")

    # 6. channel off
    uc.mem_write(TRIGCH + 5, b"\xff")
    uc.mem_write(LIVEB + 5 * 72 + 0x18, b"\x11")            # FX2 slot 0 on T6
    got = sweeps()
    check("gate: a track with its trig channel off is skipped", got == [], f"{got}")
    uc.mem_write(TRIGCH + 5, b"\x05")
    got = sweeps()
    check("gate: channel back on -> sent (T6 CC 40 = 17)", got == [(5, 40, 17)], f"{got}")

    # 8. the engine running a command (a load): the sweep waits, then catches up
    uc.mem_write(ENGQ_WAITER, bytes(4))
    uc.mem_write(LIVEB + 7 * 72 + 0x06, b"\x2a")            # AMP slot 0 on T8
    got = sweeps()
    check("gate: while the engine runs a command nothing is swept", got == [] and uc.mem_read(track_var, 1) == b"\x00", f"{got}")
    uc.mem_write(ENGQ_WAITER, ENGINE_TCB.to_bytes(4, "big"))
    got = sweeps()
    check("gate: the engine idle again -> sent (T8 CC 22 = 42)", got == [(7, 22, 0x2a)], f"{got}")

    # 7. a MIDI track on the same channel: the emitter refuses
    uc.mem_write(MIDITRK + 2 * MIDITRK_STRIDE, bytes([6 + 1]))
    uc.mem_write(LIVEB + 6 * 72 + 0x00, b"\x21")            # PLAYBACK slot 0 on T7
    got = sweeps()
    check("gate: a MIDI track on T7's channel -> the emitter is entered and refuses (cache unchanged)",
          got == [(6, 16, 0x21)] and cache(6, 16) != 0x21, f"{got} cache {cache(6, 16)}")
    uc.mem_write(MIDITRK + 2 * MIDITRK_STRIDE, b"\x00")
    got = sweeps()
    check("gate: MIDI track off -> sent", got == [(6, 16, 0x21)] and cache(6, 16) == 0x21, f"{got}")

    print(f"verify_ccfeedback: {'PASS' if not fails else f'{fails} FAIL'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
