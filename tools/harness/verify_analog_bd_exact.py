#!/usr/bin/env python3
"""Pin audio AND block-boundary state to the pre-optimization DSP executables.

Deterministic cases exercise all trigger offsets, rapid retriggers, long tails,
control extremes and random block-rate automation. Hashes contain no sample data.
Run from any directory: python3 tools/harness/verify_analog_bd_exact.py
"""
import hashlib
import json
import random
import subprocess
import bd808
import bd909


def cases(module):
    for label, knobs in [('default', module.INIT), ('minimum', [0]*12),
                         ('maximum', [127]*12)]:
        yield label, [(knobs, i % 16 if i < 512 else
                       0 if i % 4096 == 0 and i < 8192 else -1)
                      for i in range(16384)]
    rng = random.Random(808909)
    yield 'automation', [([rng.randrange(128) for _ in range(12)],
                           i % 16 if i % 3 else -1) for i in range(8192)]


def main():
    expected = json.loads((bd909.ROOT/'modules/analog-bassdrum/exact-render.json').read_text())
    out = bd909.ROOT/'out/analog-bassdrum/exact-render'
    out.mkdir(parents=True, exist_ok=True)
    for module, prefix in ((bd808, 'zv'), (bd909, 'zq')):
        symbols = module.build()
        name = module.__name__
        for label, blocks in cases(module):
            stem = out/f'{name}-{label}'
            script, raw, state = [stem.with_suffix(ext) for ext in ('.script', '.raw', '.state')]
            script.write_text(''.join(' '.join(map(str, knobs))+f' {trig}\n'
                                      for knobs, trig in blocks))
            subprocess.run([str(bd909.HOST), '-code', str(module.OUT/f'{name}.bin'),
                            '-org', '2000', '-entry', f'{symbols[prefix+"01"]:x}',
                            '-init', f'{symbols[prefix+"02"]:x}',
                            '-data', str(module.OUT/f'{name}.data'), '-script', str(script),
                            '-out', str(raw), '-state', str(state)], check=True, capture_output=True)
            want = next(r for r in expected if (r['model'], r['case']) == (name, label))
            for path, key in ((raw, 'sha256'), (state, 'state_sha256')):
                assert hashlib.sha256(path.read_bytes()).hexdigest() == want[key], (name, label, key)
            print(f'PASS {name} {label}: {len(blocks)*16} samples and every block state exact', flush=True)


if __name__ == '__main__':
    main()
