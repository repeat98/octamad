#!/usr/bin/env python3
"""Audition a Part switch through the real resident DSP loader on both cores.

Uses ColdFire-produced packet streams. The WAV is the selected track's dry
source, before stock AMP/FX; it isolates loader silence from FX tails.
"""
import array
import json
import math
import pathlib
import subprocess
import wave

from verify_analog_bd_loader import OUT, ROOT, dynamic, dsp909, host


def signed(word):
    value = word & 0xffffff
    return value - 0x1000000 if value & 0x800000 else value


def write_wav(path, blocks):
    with wave.open(str(path), 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(3)
        wav.setframerate(44100)
        wav.writeframes(b''.join((v & 0xffffff).to_bytes(3, 'little')
                                 for block in blocks for v in block))


def main():
    cases = json.loads((OUT / 'records.json').read_text())
    common = OUT / 'common.txt'
    tables = dsp909.tables()[0]
    common.write_text(''.join(f'{addr:x} ' +
                              ' '.join(f'{dsp909.q24(value):x}' for value in tables[key]) + '\n'
                              for key, addr in dynamic.common_layout().items()))
    result = {}
    for core, tag, org, cont in ((0, 'A', 0x1252, 0x426),
                                 (1, 'B', 0x1012, 0x221)):
        old = cases[0]['streams'][core]  # four 808s
        new = cases[3]['streams'][core]  # four 909s
        before = old[-1][1].copy()
        before[3] = 0
        before[4:8] = [0] * 4
        after = new[-1][1].copy()
        after[3] = 0
        after[4:8] = [0] * 4
        pre = []
        for i in range(4 * 1103):
            word = before.copy()
            # Hit just before switching to expose an abrupt tail cut.
            word[3] = 1 if i in (0, 4 * 1095) else 0
            pre.append((i % 4, word))
        post = []
        for i in range(4 * 1103):
            word = after.copy()
            word[3] = 1 if i == 0 else 0
            post.append((i % 4, word))
        stream = old + pre + new + post
        stem = OUT / f'switch-core{core}'
        packet_file = stem.with_suffix('.packets')
        packet_file.write_text(''.join(f'{slot:x} ' +
                                       ' '.join(f'{v:x}' for v in words) + '\n'
                                       for slot, words in stream))
        audio_file = stem.with_suffix('.raw')
        subprocess.run([str(host()),
                        str(ROOT / f'out/analog-bassdrum/image/kernel_{tag}.bin'),
                        f'{org:x}', f'{cont:x}', str(OUT / 'common.txt'),
                        str(packet_file), str(stem), str(audio_file)], check=True)
        samples = array.array('I')
        samples.frombytes(audio_file.read_bytes())
        assert len(samples) == 32 * len(stream)
        blocks = [[signed(v) for v in samples[i * 32:i * 32 + 32:2]]
                  for i, (slot, _) in enumerate(stream) if slot == 0]
        write_wav(stem.with_suffix('.wav'), blocks)
        log = stem.with_suffix('.log').read_text().splitlines()
        ready = [int(line.split()[6], 16) for line in log]
        begin = len(old) + len(pre)
        commit = next(i for i in range(begin, len(stream)) if ready[i])
        assert ready[begin - 1] == 1 and all(v == 0 for v in ready[begin:commit])
        assert all(signed(v) == 0 for v in samples[begin * 32:commit * 32])
        last = [signed(v) for v in samples[(begin - 1) * 32:begin * 32:2]]
        edge = abs(last[-1]) / 8388608
        # Four selected tracks carry one packet each per 16-sample frame.
        muted_frames = (commit - begin) * 16 / 4
        result[tag] = dict(muted_calls=commit - begin,
                           muted_samples=muted_frames,
                           muted_ms=muted_frames / 44.1,
                           prior_sample=last[-1],
                           prior_level_dbfs=20 * math.log10(max(edge, 1e-12)),
                           wav=str(stem.with_suffix('.wav')))
        print(tag, result[tag])
    (OUT / 'switch-report.json').write_text(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
