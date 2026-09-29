#!/usr/bin/env python3
"""Compare original 909 synthesis with local, initialized Drumazon captures.

No alignment search or level normalization is applied. Both engines receive
one hit at 100 ms; the Octatrack patch is the quantized Drumazon Init setting.
Requires numpy/scipy in the optional reference environment.
"""
import json
import pathlib
import numpy as np
from scipy.io import wavfile
from scipy.signal import find_peaks
from analog_bassdrum import DEFAULTS_909, OUT, library, render, wav

RATE = 44100


def load(path):
    rate, data = wavfile.read(path)
    assert rate == RATE
    if data.ndim == 2:
        assert np.array_equal(data[:, 0], data[:, 1]), 'reference is not centered mono'
        data = data[:, 0]
    scale = 1.0 if np.issubdtype(data.dtype, np.floating) else float(2 ** (8 * data.dtype.itemsize - 1))
    return data.astype(float) / scale


def envelope(audio):
    peaks, _ = find_peaks(audio, distance=60, prominence=.0001)
    troughs, _ = find_peaks(-audio, distance=60, prominence=.0001)
    t = peaks / RATE - .1
    keep = (t > .006) & (t < 2.8)
    peaks, t = peaks[keep], t[keep]
    amp = (audio[peaks] - np.interp(peaks, troughs, audio[troughs])) / 2
    return t, amp


def metrics(reference, candidate):
    tr, er = envelope(reference)
    tc, ec = envelope(candidate)
    # First cycle and low-level noise are excluded from the envelope metric.
    times = np.linspace(.02, .13, 60)
    rr = np.interp(times, tr, er)
    cc = np.interp(times, tc, ec)
    keep = (rr > .002) & (cc > .002)
    error = 20*np.log10(cc[keep]/rr[keep])
    body = slice(round(.106*RATE), round(.3*RATE))
    return {
        'peak_reference': float(max(abs(reference))),
        'peak_candidate': float(max(abs(candidate))),
        'envelope_mean_abs_db_20_130ms': float(np.mean(abs(error))),
        'body_correlation_6_200ms': float(np.corrcoef(reference[body], candidate[body])[0, 1]),
        'body_rms_error': float(np.sqrt(np.mean((reference[body]-candidate[body])**2))),
    }


def main():
    dll = library()
    reference_dir = OUT/'drumazon'
    cases = [('init-reference', None, None)]
    positions = {'pitch': 0, 'decay': 1, 'tune': 2, 'attack': 3, 'tune-depth': 4}
    for name, slot in positions.items():
        for value in (0, .25, .5, .75, 1):
            if (reference_dir/f'{name}-{value:g}.wav').exists():
                knob = round(value*128 if value <= .5 else 64+(value-.5)*126)
                cases.append((f'{name}-{value:g}', slot, knob))
    results = []
    for name, slot, knob in cases:
        p = DEFAULTS_909.copy()
        p[8] = 0  # Reference is captured without our optional output network.
        if slot is not None:
            p[slot] = knob
        ref = load(reference_dir/(name+'.wav'))
        raw = render(dll, p, seconds=3, hits=(4410,))
        candidate = np.asarray(raw)/8388608
        results.append({'case': name, 'parameters': p, **metrics(ref, candidate)})
        if name == 'init-reference':
            wav(OUT/'909-drumazon-calibrated.wav', raw)
            comparison = np.concatenate((ref, np.zeros(RATE//2), candidate))
            wav(OUT/'909-drumazon-then-analog.wav',
                np.clip(np.rint(comparison*8388608), -8388608, 8388607).astype(int))
    (OUT/'drumazon-comparison.json').write_text(json.dumps(results, indent=2)+'\n')
    print(json.dumps(results[0], indent=2))
    print('Compared', len(results), 'patches; no time shift or level matching applied')


if __name__ == '__main__':
    main()
