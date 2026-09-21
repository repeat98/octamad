#!/usr/bin/env python3
"""Measure stock and Euclid DSP responses using the actual firmware routines."""
import argparse
import json
import pathlib
import subprocess
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import toolpath  # noqa: E402,F401
import send_probe  # noqa: E402
from dsp_host_cli import command as dsp_host_command  # noqa: E402

HOST = ROOT / 'vendor/dsp56300/build/source/dsp_host/dsp_host'
RATE = 44100


def parameters(kind, cutoff, resonance):
    if kind == 'stock':
        return [0, cutoff, resonance, 64, 0, 64, 0, 0, 1, 0, 2, 0]
    return [cutoff, resonance, 64, 48, 15, 5, 0, 1, 0, 0, 0, 127]


class Renderer:
    def __init__(self, image, work, payload='A'):
        self.work = pathlib.Path(work)
        self.work.mkdir(parents=True, exist_ok=True)
        self.mem = send_probe.dump_mem(str(image), self.work / f'{payload}.mem', payload)

    def render(self, kind, values, signal, label):
        src, dst = self.work / 'input.raw', self.work / f'{label}.raw'
        np.asarray(signal, dtype='<i4').tofile(src)
        init, proc = send_probe.entry_points(str(self.mem), 4 if kind == 'stock' else 29)
        args = dsp_host_command(HOST, self.mem, init, proc, src, dst, values,
                                len(signal) // 16, audio=0)
        result = subprocess.run(args, capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(result.stdout[-1500:] + result.stderr[-1500:])
        return np.fromfile(dst, dtype='<i4').reshape(-1, 2).astype(float)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--image', default='out/mainos_bus.bin')
    ap.add_argument('--out', default='out/euclid/stock-comparison')
    ap.add_argument('--stock-cutoff', type=int, default=64)
    ap.add_argument('--euclid-cutoff', type=int, default=64)
    a = ap.parse_args()
    render = Renderer(a.image, a.out)
    rows = []
    for kind, cutoff in [('stock', a.stock_cutoff), ('euclid', a.euclid_cutoff)]:
        for resonance in [0, 32, 64, 96, 112, 127]:
            signal = np.zeros(32768, dtype=np.int32)
            signal[8192] = 1000000
            values = parameters(kind, cutoff, resonance)
            out = render.render(kind, values, signal, f'{kind}_q{resonance}')
            response = np.abs(np.fft.rfft(out[8192:, 0])) / signal[8192]
            frequencies = np.fft.rfftfreq(len(out)-8192, 1/RATE)
            # Fixed-point residual DC must not be mistaken for resonance.
            response[frequencies < 50] = 0
            peak = int(np.argmax(response))
            row = dict(kind=kind, cutoff=cutoff, resonance=resonance,
                       peak_hz=float(frequencies[peak]), peak_db=float(20*np.log10(max(response[peak], 1e-12))),
                       tail_offset=float(np.mean(out[-1024:, 0])))
            # Coherent near-resonance tone: residual includes all harmonics,
            # block-rate hash and noise, rather than only a few harmonics.
            freq = max(frequencies[peak], 300)
            n = 16384
            bin_no = max(1, round(freq*n/RATE))
            freq = bin_no*RATE/n
            row['tone_hz'] = freq
            for level in [-36, -18, -6]:
                tone = np.round(8388607*10**(level/20)*np.sin(2*np.pi*freq*np.arange(n*2)/RATE))
                audio = render.render(kind, values, tone, f'{kind}_q{resonance}_{level}')[-n:, 0]
                spec = np.fft.rfft(audio)
                fundamental = abs(spec[bin_no])**2
                other = max(float(np.sum(np.abs(spec[1:-1])**2)) - fundamental, 0)
                row[f'residual_{level}_db'] = float(10*np.log10(max(other, 1e-24)/max(fundamental, 1e-24)))
                row[f'peak_{level}'] = int(np.max(np.abs(audio)))
            rows.append(row)
            print(json.dumps(row), flush=True)
    (pathlib.Path(a.out) / 'measurements.json').write_text(json.dumps(rows, indent=2)+'\n')


if __name__ == '__main__':
    main()
