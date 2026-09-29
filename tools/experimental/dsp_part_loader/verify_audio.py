"""Compare candidate packages with ordinary builds on both DSP payloads.

Offline placement only. No hot loading, Part switch or hardware claim.
Requires the local stock image, assembler and dsp_host. Generated stock dumps
stay under ignored out/. Does not change any shipping source or PR branch.
"""
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile

from .build_candidates import ROOT, build


def append_p(blob, base, words):
    pos = 0
    while pos + 9 <= len(blob):
        space, _, count = struct.unpack_from('<BII', blob, pos)
        if space == 255:
            break
        pos += 9 + 4 * count
    else:
        raise ValueError('memory dump has no terminator')
    return (blob[:pos] + struct.pack('<BII', 0, base, len(words))
            + struct.pack(f'<{len(words)}I', *words) + blob[pos:])


def main():
    out = ROOT / 'out/dsp-part-loader'
    out.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(ROOT / 'tools'))
    import toolpath  # noqa: F401
    from remix import registry
    import send_probe
    host = ROOT / 'vendor/dsp56300/build/source/dsp_host/dsp_host'
    image = ROOT / 'out/mainos_bus.bin'
    saved = image.read_bytes() if image.exists() else None
    blocks, frames = 256, 16
    samples = [round(0.25 * 8388607 * (math.sin(2 * math.pi * 197 * n / 44100)
                                     + 0.4 * math.sin(2 * math.pi * 3701 * n / 44100)))
               if n < 3072 else 0 for n in range(blocks * frames)]
    source = out / 'input.raw'
    source.write_bytes(struct.pack(f'<{len(samples)}i', *samples))
    results = []
    try:
        for name in ('spectrum', 'character'):
            candidate = build(name)
            mod = registry.by_name(name)
            with tempfile.NamedTemporaryFile(mode='w', prefix='_part_loader_', suffix='.py',
                                             dir=ROOT / 'remixes', delete=False) as f:
                scratch = Path(f.name)
                f.write('from remix.schema import Remix\n'
                        f'REMIX = Remix(name={scratch.stem!r}, doc="relocation oracle", '
                        f'modules=({mod.key!r}, "SEND"), fallback="SEND")\n')
            try:
                env = {**os.environ, 'REMIX': scratch.stem, 'XBUS': '1', 'SPEC': '1'}
                with (out / f'{name}-build.log').open('w') as log:
                    subprocess.run([sys.executable, 'tools/build/build_bus.py'], cwd=ROOT,
                                   env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
            finally:
                scratch.unlink()
                for cache in (ROOT / 'remixes/__pycache__').glob(scratch.stem + '.*'):
                    cache.unlink()
            for payload in ('A', 'B'):
                baseline = out / f'{name}-{payload}-oracle.mem'
                send_probe.dump_mem(image, baseline, payload)
                init, proc = send_probe.entry_points(baseline, mod.menu.fx2_id)
                if (init, proc) == send_probe.entry_points(baseline, registry.by_name('send').menu.fx2_id):
                    raise AssertionError('oracle dispatch resolves to SEND')
                for mode in range(4 if name == 'spectrum' else 3):
                    params = [p.default or 0 for p in mod.params]
                    params[6] = mode
                    for key, value in ({'FREQ': 70, 'RES': 85} if name == 'spectrum'
                                       else {'DRV': 90, 'FOLD': 30, 'COMP': 75, 'MIX': 127}).items():
                        params[mod.knob_map()[key]] = value
                    audio = []
                    for base in (None, 0x2407, 0x3001):
                        mem = baseline
                        entry_init, entry_proc = init, proc
                        if base is not None:
                            mem = out / f'{name}-{payload}-{base:x}.mem'
                            mem.write_bytes(append_p(baseline.read_bytes(), base,
                                                    candidate.relocate({'P': base})['P']))
                            entry_init, entry_proc = base + candidate.init, base + candidate.proc
                        output = out / f'{name}-{payload}-{mode}-{base}.raw'
                        run = subprocess.run([str(host), '-mem', str(mem), '-init', f'{entry_init:x}',
                                              '-proc', f'{entry_proc:x}', '-inst', '1', '-r7', '1',
                                              '-alloc', '0', '-inmask', '1', '-frames', str(frames),
                                              '-blocks', str(blocks), '-in', str(source), '-out', str(output),
                                              '-params', ','.join(map(str, params))],
                                             cwd=ROOT, capture_output=True, text=True, timeout=60)
                        if run.returncode:
                            raise RuntimeError(run.stdout + run.stderr)
                        data = output.read_bytes()
                        if len(data) != len(samples) * 8 or not any(data):
                            raise AssertionError('incomplete or silent render')
                        audio.append(data)
                    dry = struct.pack(f'<{len(samples) * 2}i', *(v for sample in samples for v in (sample, sample)))
                    if audio[0] == dry:
                        raise AssertionError('oracle is dry passthrough')
                    if not audio[0] == audio[1] == audio[2]:
                        raise AssertionError(f'{name}/{payload}/mode {mode}: relocation changed audio')
                    results.append({'module': name, 'payload': payload, 'mode': mode,
                                    'frames': len(samples), 'equal': True})
                    print(f'{name}/{payload}/mode {mode}: stock-build placement == both relocated packages', flush=True)
    finally:
        if saved is not None:
            image.write_bytes(saved)
    (out / 'audio-report.json').write_text(json.dumps(results, indent=2) + '\n')
    print(f'{len(results)} cases, exact stereo audio; offline host only')


if __name__ == '__main__':
    main()
