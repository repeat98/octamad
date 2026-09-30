#!/usr/bin/env python3
"""Run the 909 DSP engine in bd909_host and hold it against its reference.

  python3 tools/harness/bd909.py [--wav]      render the gate patches, compare,
                                              print instructions per sample

The host (tools/harness/bd909_host) is built into out/bd909 from the shared
vendor/dsp56300 build with dsp_host's own flags. Every render is also compared
with modules/analog-bassdrum/dsp909.Voice, the float model with the engine's
structure; a mismatch is a DSP bug, a mismatch with Drumazon is a model limit.
"""
from __future__ import annotations

import argparse
import array
import math
import pathlib
import subprocess
import sys
import wave

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'modules/analog-bassdrum'))
import dsp909  # noqa: E402

OUT = ROOT / 'out/bd909'
HOST = OUT / 'bd909_host'
V = ROOT / 'vendor/dsp56300'
ORG = 0x2000
FRAMES = 16
# PITCH DECAY TUNE ATK TDEP SAT MODEL ACCNT LPF LOW HIGH -; Drumazon Init = 64 32 64 32 64,
# velocity 100; SAT 0 and LOW / HIGH 64 leave the desk stage flat
INIT = [64, 32, 64, 32, 64, 0, 1, 100, 0, 64, 64, 0]


def patch(**kw):
    slots = dict(pitch=0, decay=1, tune=2, atk=3, tdep=4, sat=5, accnt=7, lpf=8, low=9, high=10)
    k = list(INIT)
    for name, v in kw.items():
        k[slots[name]] = v
    return k


def build_host():
    src = ROOT / 'tools/harness/bd909_host/bd909_host.cpp'
    if HOST.exists() and HOST.stat().st_mtime > src.stat().st_mtime:
        return
    OUT.mkdir(parents=True, exist_ok=True)
    subprocess.run(['c++', '-O3', '-DNDEBUG', '-std=gnu++17', '-DASMJIT_STATIC', '-DDSP56300_DEBUGGER=0',
                    f'-I{V}/source', f'-I{V}/source/asmjit/src', str(src),
                    f'{V}/build/source/dsp56kEmu/libdsp56kEmu.a', f'{V}/build/source/dsp56kBase/libdsp56kBase.a',
                    f'{V}/build/source/asmjit/libasmjit.a', '-lpthread', '-o', str(HOST)],
                   check=True, capture_output=True)


def build(*, output_gain=True):
    build_host()
    layout = dsp909.default_layout(0x1000)
    labels, _ = dsp909.assemble(ORG, layout, OUT / 'bd909.bin',
                              dsp909.source(layout, output_gain=output_gain))
    (OUT / 'bd909.data').write_text(dsp909.data_lines(layout))
    desk, _ = dsp909.assemble(ORG, layout, OUT / 'desk.bin', dsp909.desk_source(layout))
    labels['zt01'] = desk['zt01']
    return labels


def render(labels, blocks, tag):
    """blocks: list of (knobs[12], trig offset or None). Returns (samples L, meter)."""
    script = OUT / f'{tag}.script'
    script.write_text(''.join(' '.join(map(str, k)) + f' {-1 if t is None else t}\n' for k, t in blocks))
    raw, meter = OUT / f'{tag}.raw', OUT / f'{tag}.meter'
    r = subprocess.run([str(HOST), '-code', str(OUT / 'bd909.bin'), '-org', f'{ORG:x}',
                        '-entry', f"{labels['zq01']:x}", '-init', f"{labels['zq02']:x}",
                        '-data', str(OUT / 'bd909.data'), '-script', str(script),
                        '-out', str(raw), '-meter', str(meter)], capture_output=True, text=True, check=True)
    a = array.array('i'); a.frombytes(raw.read_bytes())
    counts = [int(x) for x in meter.read_text().split()]
    # Measured code-growth guard, NOT a hardware timing budget (CPU.md).
    assert max(counts) <= 5232, ('909 instruction cost grew; re-benchmark full chains', max(counts))
    return [a[i] / 8388608 for i in range(0, len(a), 2)], counts, r.stdout.strip()


def render_desk(labels, blocks, x, tag):
    """The desk stage alone (dsp909.desk_source) on the 24-bit input x."""
    script, raw, inp = OUT / f'{tag}.script', OUT / f'{tag}.raw', OUT / f'{tag}.in'
    script.write_text(''.join(' '.join(map(str, k)) + ' -1\n' for k, _ in blocks))
    inp.write_bytes(array.array('i', x).tobytes())
    subprocess.run([str(HOST), '-code', str(OUT / 'desk.bin'), '-org', f'{ORG:x}',
                    '-entry', f"{labels['zt01']:x}",
                    '-data', str(OUT / 'bd909.data'), '-script', str(script), '-input', str(inp),
                    '-out', str(raw)], capture_output=True, text=True, check=True)
    a = array.array('i'); a.frombytes(raw.read_bytes())
    return [a[i] / 8388608 for i in range(0, len(a), 2)]


def desk_input(blocks):
    """The voice's signal into the desk (the reference's), as 24-bit words."""
    v = dsp909.Voice(); seen = []
    v.desk = lambda y: seen.append(y) or 0.0
    for k, t in blocks:
        v.block(k, t, FRAMES)
    return [max(-8388608, min(8388607, math.floor(y * 8388608))) for y in seen]


def reference_desk(blocks, x):
    v = dsp909.Voice(); out = []
    for b, (k, _) in enumerate(blocks):
        v.desk_knobs(k)
        out += [v.desk(w / 8388608) for w in x[b * FRAMES:(b + 1) * FRAMES]]
    return out


def reference(blocks):
    v = dsp909.Voice(); out = []
    for k, t in blocks:
        out += v.block(k, t, FRAMES)
    return out


def hits(knobs, seconds=3.0, at=(4410,), changes=None):
    n = int(seconds * 44100) // FRAMES
    trig = {h // FRAMES: h % FRAMES for h in at}
    kn = list(knobs); blocks = []
    for b in range(n):
        if changes and b in changes:
            for slot, val in changes[b].items():
                kn[slot] = val
        blocks.append((list(kn), trig.get(b)))
    return blocks


def err_db(x, ref):
    num = math.sqrt(sum((a - b) ** 2 for a, b in zip(x, ref)))
    den = math.sqrt(sum(b * b for b in ref)) or 1e-12
    return 20 * math.log10(max(num, 1e-12) / den)


def wav(path, x):
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(1); w.setsampwidth(3); w.setframerate(44100)
        w.writeframes(b''.join((max(-8388608, min(8388607, round(s * 8388608))) & 0xffffff).to_bytes(3, 'little') for s in x))


CASES = {
    'init': hits(INIT),
    'attack-max': hits(patch(atk=127)),
    'decay-max': hits(patch(decay=127)),
    'pitch-min-depth0': hits(patch(pitch=0, tdep=0)),
    'tune0-depthmax': hits(patch(pitch=127, decay=60, tune=0, atk=127, tdep=127, accnt=127)),
    'lpf-orig': hits(patch(atk=64, lpf=64)),
    'retrig-roll': hits(patch(decay=50, atk=64), at=(4410, 5733, 7056, 8379, 9261, 13230, 13350)),
    'sat-64': hits(patch(sat=64)),
    'sat-max-low-max': hits(patch(sat=127, low=127, atk=100)),
    'low-cut-high-max': hits(patch(sat=40, low=0, high=127, atk=127)),
    'moving-knobs': hits(INIT, at=(4410, 30000, 60000),
                         changes={b: {0: (b * 3) % 128, 1: (b * 5) % 128, 2: (b * 7) % 128, 3: (b * 11) % 128,
                                      4: (b * 13) % 128, 5: (b * 23) % 128, 7: (b * 17) % 128,
                                      8: (b * 19) % 128, 9: (b * 29) % 128, 10: (b * 31) % 128}
                                  for b in range(0, 8268, 37)}),
}


# The desk stage alone, fed the same 24-bit signal on both sides: heavy SAT
# turns the voice's own -77 dB residue into far more at every clip edge, so
# the whole-voice cases above cannot hold the stage to a tight tolerance.
DESK_CASES = {
    'desk-sat64': (patch(sat=64), patch()),
    'desk-sat-max-low-max': (patch(sat=127, low=127), patch(atk=100)),
    'desk-low0-high-max': (patch(sat=40, low=0, high=127), patch(atk=127)),
    'desk-high-max-sat-max': (patch(sat=127, high=127), patch(atk=127, decay=90)),
}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--wav', action='store_true', help='write out/bd909/<case>.wav')
    ap.add_argument('--tolerance', type=float, default=-60.0, help='worst DSP-vs-reference error, dB')
    args = ap.parse_args()
    labels = build()
    worst_err, worst_instr = -999.0, 0
    for name, blocks in CASES.items():
        dsp, meter, _ = render(labels, blocks, name)
        ref = reference(blocks)
        e = err_db(dsp, ref)
        peak = max(abs(s) for s in dsp)
        mx = max(meter)
        worst_err, worst_instr = max(worst_err, e), max(worst_instr, mx)
        print(f'{name:18s} DSP vs reference {e:7.1f} dB   peak {peak:.3f}   max {mx} instr/block '
              f'({mx / FRAMES:.1f}/sample)   mean {sum(meter) / len(meter) / FRAMES:.1f}/sample')
        if args.wav:
            wav(OUT / f'{name}.wav', dsp)
    for name, (desk, voice) in DESK_CASES.items():
        blocks = hits(voice)
        x = desk_input(blocks)
        dblocks = [(list(desk), None) for _ in blocks]
        # the knobs move through the whole range in the second half
        for b in range(len(dblocks) // 2, len(dblocks)):
            dblocks[b][0][5], dblocks[b][0][9], dblocks[b][0][10] = (b * 7) % 128, (b * 11) % 128, (b * 13) % 128
        dsp = render_desk(labels, dblocks, x, name)
        ref = reference_desk(dblocks, x)
        e = err_db(dsp, ref)
        worst_err = max(worst_err, e)
        print(f'{name:22s} desk alone vs reference {e:7.1f} dB   peak {max(abs(s) for s in dsp):.3f}')
    print(f'worst DSP-vs-reference {worst_err:.1f} dB (gate {args.tolerance}), '
          f'worst block {worst_instr} instructions = {worst_instr / FRAMES:.1f} per sample')
    if worst_err > args.tolerance:
        sys.exit('DSP output differs from the reference')


if __name__ == '__main__':
    main()
