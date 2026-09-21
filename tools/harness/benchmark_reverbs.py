#!/usr/bin/env python3
"""Execute pristine stock reverbs and Mini Verb on both DSP cores.

Reports executed instructions, NOT target CPU utilization or hardware cycles.
Eight instances means four FX2 slots per core at the real three-block r7 stride.
All active controls change independently every 16-sample block. Source images,
commands, full meters, automation and audio remain in out/reverb_bench.
"""
from __future__ import annotations
import argparse
import array
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import toolpath  # noqa: F401,E402
import send_probe
from remix import registry, stock

ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / 'vendor/dsp56300/build/source/dsp_host/dsp_host'
OUT = ROOT / 'out/reverb_bench'
FRAMES = 16
WARM = 256


def prepare():
    OUT.mkdir(parents=True, exist_ok=True)
    image = ROOT / 'out/mainos_bus.bin'
    keep = image.read_bytes() if image.exists() else None
    try:
        result = subprocess.run([sys.executable, 'tools/build/build_bus.py'], cwd=ROOT,
                                env={**os.environ, 'REMIX': 'miniverb', 'XBUS': '1', 'SPEC': '1'},
                                capture_output=True, text=True, check=True)
        (OUT / 'build.log').write_text(result.stdout + result.stderr)
        (OUT / 'miniverb.bin').write_bytes(image.read_bytes())
    finally:
        if keep is not None:
            image.write_bytes(keep)
        else:
            image.unlink(missing_ok=True)
    paths = {}
    for name, source in [('stock', stock.STOCK_IMAGE), ('miniverb', OUT / 'miniverb.bin')]:
        paths[name] = [send_probe.dump_mem(source, OUT / f'{name}_{pl}.mem', pl) for pl in 'AB']
    return paths


def knobs(mod, block=None, instance=0):
    vals = [p.default or 0 for p in mod.params]
    for j, p in enumerate(mod.params):
        if not p.active:
            continue
        if block is None:
            if p.name == b'MIX':
                vals[j] = 127
        else:
            count = p.count or 128
            # Settled minima/maxima followed by ramps and abrupt endpoint jumps.
            # Every TYPE and MIXF is reached; each instance has a different phase.
            phase = block + 17 * instance + 11 * j
            vals[j] = (0 if block < 384 else count - 1 if block < 512 else
                       (phase * (2*j+1)) % count if block % 256 < 192 else
                       (count - 1 if phase % 2 else 0))
    return vals


def raw(path, values):
    data = array.array('i', values)
    if sys.byteorder != 'little': data.byteswap()
    path.write_bytes(data.tobytes())
    return path


def read_raw(path):
    data = array.array('i')
    data.frombytes(path.read_bytes())
    if sys.byteorder != 'little': data.byteswap()
    return data


def source(blocks, instance=0, impulse=False):
    path = OUT / f'input_{blocks}_{instance}_{int(impulse)}.raw'
    values = []
    for n in range(blocks * FRAMES):
        t = n - WARM * FRAMES
        if impulse:
            s = .5 if t == 0 else 0
        elif t < 0:
            s = 0
        else:
            # Tone plus repeated short bipolar transients, -12 dBFS peak bound.
            s = .12*math.sin(2*math.pi*(173+instance*79)*t/44100)
            s += .12*math.sin(2*math.pi*1987*t/44100)*math.exp(-(t % 4096)/80)
        values.append(round(s * 8388607))
    return raw(path, values)


def run(mod, mems, tag, blocks, instances=8, automate=False, split=None,
        mask=None, inputs=None, extra=(), positions=None, synchronized=False):
    positions = positions or list(range(instances))
    # Single reference renders can occupy any of the real eight slots.
    cores = [k//4 for k in positions]
    eps = [send_probe.entry_points(mems[c], mod.menu.fx2_id) for c in cores]
    output = OUT / f'{mod.name}_{tag}.raw'
    meter = output.with_suffix('.meter')
    cmd = [str(HOST), '-mem', str(mems[0]), '-memB', str(mems[1]),
           '-init', ','.join(f'{ep[0]:x}' for ep in eps),
           '-proc', ','.join(f'{ep[1]:x}' for ep in eps),
           '-inst', str(instances), '-core', ','.join(map(str, cores)),
           '-alloc', ','.join(str(1+2*(k%4)) for k in positions),
           '-r7', ','.join(str(2+3*(k%4)) for k in positions),
           '-audioidx', ','.join(str(k%4) for k in positions),
           '-allocproc', 'end', '-frames', str(FRAMES), '-blocks', str(blocks),
           '-out', str(output), '-meter', str(meter)]
    if mask is not None: cmd += ['-inmask', str(mask)]
    if inputs: cmd += ['-in', ','.join(map(str, inputs))]
    if split is not None: cmd += ['-split', ','.join(map(str, split))]
    for k in positions:
        cmd += ['-params', ','.join(map(str, knobs(mod, instance=k)))]
        if automate:
            auto = OUT / f'{mod.name}_{tag}_p{k}.csv'
            auto.write_text(''.join(','.join(map(str, [b, *knobs(mod, b, 0 if synchronized else k)]))+'\n'
                                    for b in range(blocks)))
            cmd += ['-paramfile', str(auto)]
    cmd += list(extra)
    output.with_suffix('.command.json').write_text(json.dumps(cmd, indent=2))
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    output.with_suffix('.log').write_text(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError(f'{mod.name}/{tag}: {result.stdout[-1500:]}\n{result.stderr[-1000:]}')
    rows = [[int(v) for v in line.split()] for line in meter.read_text().splitlines()]
    if len(rows) != blocks: raise AssertionError('incomplete meter')
    stats = []
    for c in range(2):
        series = [r[c+1] for r in rows]
        steady = series[WARM:]
        stats.append(dict(core=c, mean_block=sum(steady)/len(steady),
                          peak_block=max(series), peak_at=series.index(max(series)),
                          init_instructions=int(re.search(rf'core {c} meter:.*inits (\d+)', result.stdout)[1])))
    audio = [read_raw(Path(str(output)+(f'.i{k}' if k else ''))) for k in range(instances)]
    row = dict(effect=mod.key, case=tag, instances=instances, blocks=blocks,
               cores=stats, peak_audio=max(abs(v) for track in audio for v in track),
               clipped_samples=sum(abs(v)>=8388607 for track in audio for v in track))
    print(f"{mod.key:12s} {tag:18s} peak/core {[s['peak_block'] for s in stats]} instr/16 samples", flush=True)
    return row, audio


def wav(path, stereo):
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(2); w.setsampwidth(3); w.setframerate(44100)
        w.writeframes(b''.join((int(v)&0xffffff).to_bytes(3,'little') for v in stereo))


def write_report(report):
    results = report["results"]
    blocks = results[0]["blocks"]
    lines = ['# Reverb DSP benchmark', '',
             'Eight instances: four per core, 44.1 kHz, 16-sample blocks. '
             'Executed instructions, **not hardware cycles or CPU utilization**.', '',
             '| Effect | Fixed peak/core/block | Moving controls, unsplit | Worst tested peak/core/block | Worst instr/sample/core | Init, four instances |',
             '|---|---:|---:|---:|---:|---:|']
    for key in ['SPRING REV', 'PLATE REV', 'DARK REV', 'MINIVERB']:
        rows = [r for r in results if r['effect'] == key and r['instances'] == 8]
        peak = lambda r: max(c['peak_block'] for c in r['cores'])
        fixed = next(r for r in rows if r['case'] == 'eight_fixed')
        moving = next(r for r in rows if r['case'] == 'eight_modulated')
        worst = max(rows, key=peak)
        init = max(c['init_instructions'] for c in worst['cores'])
        lines.append(f'| {key} | {peak(fixed):,} | {peak(moving):,} | {peak(worst):,} | {peak(worst)/16:.2f} | {init:,} |')
    lines += ['', f'Each case: {blocks} blocks ({blocks*16/44100:.3f} seconds). '
              'Means exclude the first 256 blocks; maxima include startup. '
              'Initialization is measured separately, outside processing blocks.', '',
              'The sweep covers asynchronous and synchronized control changes, minima/maxima, '
              'ramps, endpoint jumps, every spring TYPE and plate/dark MIXF, and all 16 trigger '
              'split positions. This is the worst observed in this finite sweep, not a proof '
              'over every parameter combination.', '',
              'The meter includes effect parameter decoding and both split calls. It excludes '
              'ColdFire parameter publication/UI, the stock DSP dispatcher, other effects, '
              'voice engines, DMA/cache contention and hardware memory stalls. A hardware '
              'eight-track playback/editing and burn sweep remains required.', '',
              'results.json contains full results and source hashes; *.command.json, *.csv, '
              '*.meter and *.log retain reproducible inputs and raw measurements.', '']
    (OUT/'report.md').write_text('\n'.join(lines))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--blocks', type=int, default=4096)
    ap.add_argument('--verify', action='store_true', help='also run isolation, dirty-state and audio gates')
    args = ap.parse_args()
    if args.blocks < 1024: ap.error('--blocks must be at least 1024')
    mem = prepare()
    results = []
    inputs = [source(args.blocks, k) for k in range(8)]
    for key in ['SPRING REV', 'PLATE REV', 'DARK REV', 'MINIVERB']:
        mod = registry.by_key(key)
        images = mem['miniverb' if key == 'MINIVERB' else 'stock']
        for tag, n, auto, splits in [('one_fixed',1,False,None), ('eight_fixed',8,False,None),
                                      ('eight_modulated',8,True,None),
                                      ('eight_mod_split1',8,True,[1]*8),
                                      ('eight_mod_split15',8,True,[15]*8)]:
            row, _ = run(mod, images, tag, args.blocks, n, auto, splits, inputs=inputs[:n])
            results.append(row)
        # Worst aggregate path can require ALL four slots to select the same
        # expensive spring type; asynchronous sweeps alone dilute that cost.
        for split in range(16):
            row, _ = run(mod, images, f'sync_split{split:02}', args.blocks,
                         automate=True, split=[split]*8, inputs=inputs, synchronized=True)
            results.append(row)
    report = dict(source_sha256={str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                                 for path in [ROOT/'modules/miniverb/miniverb.asm',
                                              ROOT/'tools/harness/dsp_host/dsp_host.cpp',
                                              Path(__file__).resolve()]},
                  units='executed DSP instructions (not hardware cycles or CPU utilization)',
                  sample_rate=44100, frames_per_block=FRAMES, warmup_excluded_from_mean=WARM,
                  stock_sha256=hashlib.sha256(stock.STOCK_IMAGE.read_bytes()).hexdigest(),
                  miniverb_sha256=hashlib.sha256((OUT/'miniverb.bin').read_bytes()).hexdigest(),
                  results=results)
    peaks = {key: max(c['peak_block'] for r in results if r['effect'] == key
                       and r['instances'] == 8 for c in r['cores'])
             for key in ['MINIVERB', 'SPRING REV']}
    report['spring_peak_budget'] = dict(limit=peaks['SPRING REV'], measured=peaks['MINIVERB'],
                                      passed=peaks['MINIVERB'] <= peaks['SPRING REV'])
    (OUT/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    write_report(report)
    if not report['spring_peak_budget']['passed']:
        raise AssertionError(f"Mini Verb exceeds measured spring peak: {peaks}")
    if args.verify:
        from verify_miniverb import verify
        verify(mem['miniverb'])
    print(f'Report: {OUT / "results.json"}')

if __name__ == '__main__': main()
