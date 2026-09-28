#!/usr/bin/env python3
"""PLATE/DARK must remain bit-identical to stock after harvesting SPRING.

DARK calls a shared routine inside SPRING's region. Exercise both effects on both cores,
with fixed and moving controls, at the hardware audio address X:0.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import benchmark_reverbs as br
import send_probe
from remix import registry, stock


def main():
    root = Path(__file__).resolve().parents[2]
    br.OUT = root/'out/analog-bassdrum/reverb-identity'
    br.OUT.mkdir(parents=True, exist_ok=True)
    mems = {}
    for name, image in [('stock', stock.STOCK_IMAGE), ('patched', root/'out/mainos_bus.bin')]:
        mems[name] = [send_probe.dump_mem(image, br.OUT/f'{name}_{p}.mem', p) for p in 'AB']
    # Stop setup just before the source seam; this gate calls FX directly.
    blocks = 2048
    inputs = [br.source(blocks, k) for k in range(2)]
    for key in ('PLATE REV', 'DARK REV'):
        for moving in (False, True):
            audio = []
            for name in ('stock', 'patched'):
                _, samples = br.run(registry.by_key(key), mems[name], f'{name}-{moving}',
                                    blocks, 2, moving, inputs=inputs, positions=[0, 4],
                                    extra=('-audio', '0', '-ctx', '372,39b,53e',
                                           '-ctxB', '17a,1a1,333'))
                audio.append(samples)
            assert audio[0] == audio[1], (key, moving, 'stock reverb changed')
            assert any(v for track in audio[0] for v in track), (key, moving, 'silent comparison')
            print(f'PASS {key}, moving={moving}: both cores exactly match stock', flush=True)


if __name__ == '__main__':
    main()
