"""Click census of a track's chain output from a verify_set port run: second-
difference spikes per 1,000-sample window against the MIDI script's frame
marks (tools/harness/midi/delay_knob_moves.midi, Sam's 20 Sep 2026 recipe):

    OT_PROJECT=<dir> python3 tools/verify/verify_set.py bamsep26 --frames 32000 --midi-file tools/harness/midi/delay_knob_moves.midi
    python3 tools/harness/port_click_census.py [out/setverify/port.dump] [track] [thresh]
"""
import pathlib, sys, math
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa
import blockdump as bd, recloop as rl  # noqa
dump = sys.argv[1] if len(sys.argv) > 1 else "out/setverify/port.dump"
track = int(sys.argv[2]) if len(sys.argv) > 2 else 1
thr = float(sys.argv[3]) if len(sys.argv) > 3 else 0.02
c = bd.classes(bd.read(dump))
x = rl.readback_audio(c, track)
n = len(x); print(f"T{track} chain output: {n} samples = {n/16:.0f} frames")
t = int(thr * 8388607)
def spikes(seg):
    return sum(1 for i in range(1, len(seg) - 1) if abs(seg[i + 1] - 2 * seg[i] + seg[i - 1]) > t)
W = 1000
rows = []
for w0 in range(0, n - W, W):
    seg = x[w0:w0 + W + 2]
    r = math.sqrt(sum((v / 8388607) ** 2 for v in seg) / len(seg))
    rows.append((w0 // 16, spikes(seg), 20 * math.log10(max(1e-9, r))))
print("frame   spikes  rms(dBFS)   (every 8th window; frames of 16 samples)")
for i in range(0, len(rows), 8):
    f, sp, r = rows[i]
    print(f"{f:6d}  {sp:6d}  {r:7.1f}")
marks = [(400, "MODE->REVERSE"), (3400, "PTCH 0"), (5400, "PTCH 127"), (7400, "PTCH 64"), (9400, "TIME 90"),
         (12400, "TIME 20"), (15400, "FDBK 120"), (18400, "FDBK 60"), (24400, "TONE 90"), (26400, "TONE 100")]
print("\nspikes per window, averaged between marks:")
for (f0, name), (f1, _) in zip(marks, marks[1:] + [(n // 16, "end")]):
    sel = [sp for f, sp, _ in rows if f0 <= f < f1]
    rm = [r for f, _, r in rows if f0 <= f < f1]
    if sel:
        print(f"  {name:14s} frames {f0:5d}-{f1:5d}: spikes/window {sum(sel)/len(sel):6.1f}  max {max(sel):4d}  rms {sum(rm)/len(rm):6.1f}")
