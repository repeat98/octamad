#!/usr/bin/env python3
"""PLATE/DARK must remain bit-identical to stock after harvesting SPRING.

DARK calls a shared routine inside SPRING's region. Exercise both effects on both cores,
with fixed and moving controls, at the hardware audio address X:0.

In an image whose stock effects load on demand (build_bus DYNAMIC: PLATE's
dispatch is the null stub) no reverb is resident. The gate then does what the
DSP loader does -- uploads both reverbs into this image's arena and binds their
dispatch -- and compares that against stock.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import struct
import benchmark_reverbs as br
import send_probe
from remix import registry, stock
NULL_STUB = {'A': 0x7c8, 'B': 0x588}


def _record(blob, space, base, words):
    """Append a record before the dump's terminator (later records win)."""
    pos = 0
    while pos + 9 <= len(blob):
        sp, _, count = struct.unpack_from('<BII', blob, pos)
        if sp == 255:
            break
        pos += 9 + 4 * count
    return blob[:pos] + struct.pack('<BII', space, base, len(words)) + \
        struct.pack(f'<{len(words)}I', *words) + blob[pos:]


def load_like_the_loader(mem, payload):
    """Upload PLATE and DARK into the image's arena and bind their dispatch."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.experimental.dsp_dynload.runtime_catalog import dynamic_packages, dynamic_layout
    from tools.experimental.dsp_dynload.stock_catalog import build as stock_rows
    core = 0 if payload == 'A' else 1
    rows = stock_rows()
    start = min(r['p_base'] for r in rows if r['core'] == core and r['p_words'])
    arena = dynamic_layout(rows, core, start)[2] + 64     # PTABLE follows the copies
    pkgs = dynamic_packages()
    blob, at = mem.read_bytes(), arena
    for key in ('PLATE REV', 'DARK REV'):
        fid = registry.by_key(key).menu.fx2_id
        pkg = pkgs[core, fid]
        words = list(pkg['words'])
        for r in pkg['relocations']:
            i = r & 0x7fff
            words[i] = (words[i] - at if r & 0x8000 else words[i] + at) & 0xffffff
        blob = _record(blob, 0, at, words)
        blob = _record(blob, 1, 0x215 + fid, [at + pkg['init']])
        blob = _record(blob, 1, 0x235 + fid, [at + pkg['proc']])
        at += len(words)
    mem.write_bytes(blob)


def main():
    root = Path(__file__).resolve().parents[2]
    br.OUT = root/'out/analog-bassdrum/reverb-identity'
    br.OUT.mkdir(parents=True, exist_ok=True)
    mems = {}
    for name, image in [('stock', stock.STOCK_IMAGE), ('patched', root/'out/mainos_bus.bin')]:
        mems[name] = [send_probe.dump_mem(image, br.OUT/f'{name}_{p}.mem', p) for p in 'AB']
    plate = registry.by_key('PLATE REV').menu.fx2_id
    for p, mem in zip('AB', mems['patched']):
        if send_probe.entry_points(mem, plate)[0] == NULL_STUB[p]:
            load_like_the_loader(mem, p)
            print(f'payload {p}: no reverb resident -- PLATE and DARK loaded into the arena '
                  f'and bound, as the DSP loader does', flush=True)
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
