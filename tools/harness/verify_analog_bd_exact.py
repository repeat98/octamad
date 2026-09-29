#!/usr/bin/env python3
"""Pin the original DSP output/state and verify the deliberate 808 output trim.

Deterministic cases exercise all trigger offsets, rapid retriggers, long tails,
control extremes and random block-rate automation. Hashes contain no sample data.
Run from any directory: python3 tools/harness/verify_analog_bd_exact.py
"""
import array
import shutil
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
        if module is bd808:
            symbols = module.build(output_trim=False)
            legacy = module.OUT/'bd808-untrimmed.bin'
            shutil.copy2(module.OUT/'bd808.bin',legacy)
            trimmed_symbols = module.build()
        else:
            symbols = module.build()
        name = module.__name__
        for label, blocks in cases(module):
            stem = out/f'{name}-{label}'
            script, raw, state = [stem.with_suffix(ext) for ext in ('.script', '.raw', '.state')]
            script.write_text(''.join(' '.join(map(str, knobs))+f' {trig}\n'
                                      for knobs, trig in blocks))
            subprocess.run([str(bd909.HOST), '-code', str(legacy if module is bd808 else module.OUT/f'{name}.bin'),
                            '-org', '2000', '-entry', f'{symbols[prefix+"01"]:x}',
                            '-init', f'{symbols[prefix+"02"]:x}',
                            '-data', str(module.OUT/f'{name}.data'), '-script', str(script),
                            '-out', str(raw), '-state', str(state)], check=True, capture_output=True)
            want = next(r for r in expected if (r['model'], r['case']) == (name, label))
            for path, key in ((raw, 'sha256'), (state, 'state_sha256')):
                assert hashlib.sha256(path.read_bytes()).hexdigest() == want[key], (name, label, key)
            if module is bd808:
                trimmed_raw=stem.with_suffix('.trimmed.raw')
                trimmed_state=stem.with_suffix('.trimmed.state')
                subprocess.run([str(bd909.HOST), '-code', str(module.OUT/'bd808.bin'),
                                '-org', '2000', '-entry', f'{trimmed_symbols["zv01"]:x}',
                                '-init', f'{trimmed_symbols["zv02"]:x}',
                                '-data', str(module.OUT/'bd808.data'), '-script', str(script),
                                '-out', str(trimmed_raw), '-state', str(trimmed_state)],
                               check=True,capture_output=True)
                old=array.array('i');old.frombytes(raw.read_bytes())
                gain=bd808.dsp909.q24(bd808.dsp808.OUTPUT_TRIM)
                scaled=array.array('i',((v*gain)>>23 for v in old))
                assert trimmed_raw.read_bytes()==scaled.tobytes(), (name,label,'post-desk trim')
                assert trimmed_state.read_bytes()==state.read_bytes(), (name,label,'trim changed state')
            print(f'PASS {name} {label}: {len(blocks)*16} samples match original hashes; '
                  + ('808 output is exact fixed-point trim, all states unchanged' if module is bd808
                     else 'audio and every block state unchanged'), flush=True)


if __name__ == '__main__':
    main()
