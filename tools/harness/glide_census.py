"""Click census of a TIME move under dsp_host: BusDelay in MODE (0 CLEAN, 1
GRAIN, 2 REVERSE) fed a tone through a SEND, TIME 20 -> 90 at block 3000,
second-difference spikes > 0.02 FS in T1's print (the wet). 20 Sep 2026:
5,228 / 2,676 / 4,483 spikes per mode with the glide stepping per block,
0 / 73 / 896 with the ramp (tools/harness/port_click_census.py is the same
census on a port run).

    python3 tools/harness/glide_census.py [mode]      # needs the SPEC dumps of verify_onebus
"""
import pathlib, struct, subprocess, sys, math
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa
import send_probe, verify_onebus as vo  # noqa
from remix import registry  # noqa
A, B = vo.SCRATCH / "spec_A.mem", vo.SCRATCH / "spec_B.mem"; mems = {0: A, 1: B}
kw = dict(MODE=int(sys.argv[1]) if len(sys.argv) > 1 else 0, TIME=20, FDBK=60, TONE=100, PING=0, WET=127)
D = vo.Inst("DELAY SERVER", 1, 0, **kw); S2 = vo.Inst("SEND", 1, 1, fed=True, DEL=100); S6 = vo.Inst("SEND", 0, 1, DEL=0)
km = registry.by_key("DELAY SERVER").knob_map_all()
vo.BLOCKS = 8000; vo.tone_file(vo.SCRATCH / "tone.raw", 8000, amp=0.3)
_orig = subprocess.run
def run_with(sched, tag):
    def patched(cmd, **k):
        if cmd and str(cmd[0]).endswith("dsp_host") and sched: cmd = list(cmd) + ["-sched", sched]
        return _orig(cmd, **k)
    subprocess.run = patched
    try: return vo.run(mems, [D, S2, S6], tag=tag)[0][0]
    finally: subprocess.run = _orig
x = run_with(f"3000:0:{km['TIME']}=90", "gl")
F = vo.FRAMES; t0 = (3000 - 300) * F      # the move, in output samples (PAD stripped)
t = int(0.02 * 8388607)
sd = [abs(x[i + 1] - 2 * x[i] + x[i - 1]) for i in range(1, len(x) - 1)]
idx = [i + 1 for i, v in enumerate(sd) if v > t]
print("spikes (2nd diff > 0.02 FS): total", len(idx), "; first 30 positions relative to the move:", [i - t0 for i in idx[:30]])
if idx:
    i = idx[0]
    print("samples around the first spike (FS):")
    print([round(x[j] / 8388607, 4) for j in range(i - 6, i + 8)])
    i = idx[len(idx)//2]
    print("around a mid-glide spike, at", i - t0, "samples after the move:")
    print([round(x[j] / 8388607, 4) for j in range(i - 6, i + 8)])
# how long do they last
last = idx[-1] - t0 if idx else None
print("last spike at", last, "samples after the move (", (last or 0) / 15, "blocks )")
