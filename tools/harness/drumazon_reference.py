#!/usr/bin/env python3
"""Headless reference captures from the user's installed Drumazon 2.

Build the companion JUCE host and install scipy in a separate environment. Provide a state
saved after SCENE > Init. Plugin state and renders remain in ignored out/.
This script changes only the capture instance, never the plugin's defaults.
"""
import argparse
import hashlib
import json
import pathlib
import struct
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / 'out/analog-bassdrum/drumazon'
ALPHABET = '.ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+'


def decode_memory(text):
    length, encoded = text.split('.', 1)
    result = bytearray()
    value = bits = 0
    for ch in encoded:
        value |= ALPHABET.index(ch) << bits
        bits += 6
        while bits >= 8:
            result.append(value & 255)
            value >>= 8
            bits -= 8
    return bytes(result[:int(length)])


def encode_memory(data):
    result = []
    value = bits = 0
    for byte in data:
        value |= byte << bits
        bits += 8
        while bits >= 6:
            result.append(ALPHABET[value & 63])
            value >>= 6
            bits -= 6
    if bits:
        result.append(ALPHABET[value & 63])
    return str(len(data)) + '.' + ''.join(result)


def xml_state(data):
    assert data[:4] == b'VC2!'
    size = struct.unpack_from('<I', data, 4)[0]
    return ET.fromstring(data[8:8 + size]), data[8 + size:]


def pack_xml(root, suffix):
    data = ET.tostring(root, encoding='utf-8', xml_declaration=True)
    return b'VC2!' + struct.pack('<I', len(data)) + data + suffix


def initialized_direct_state(data):
    outer, outer_tail = xml_state(data)
    component = outer.find('IComponent')
    inner, inner_tail = xml_state(decode_memory(component.text))
    preset = inner.find('ParametersState/Preset')
    assert preset.get('name') == '- Init -', 'Capture requires SCENE > Init'
    parameters = {p.get('name'): p for p in preset.iter('param')}
    for name, expected in {'BD Attack': '25', 'BD Tune': '50', 'BD Decay': '25',
                           'BD Pitch': '50', 'BD Tune Depth': '50'}.items():
        assert parameters[name].get('value') == expected, (name, 'not initialized')
    # A direct MIDI hit must not start the internal pattern sequencer.
    changes = {'Int Seq': 'Off', 'BD Filter/EQ Active': 'Off',
               'BD Compressor Active': 'Off', 'BD Route': 'Master',
               'BD Send Amount': '-320', 'BD Level': '0'}
    for name, value in changes.items():
        assert name in parameters, name
        parameters[name].set('value', value)
    component.text = encode_memory(pack_xml(inner, inner_tail))
    return pack_xml(outer, outer_tail)


def main():
    import subprocess
    import concurrent.futures
    from scipy.io.wavfile import read
    import numpy as np
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plugin', default='/Library/Audio/Plug-Ins/VST3/Drumazon2.vst3')
    parser.add_argument('--state', type=pathlib.Path, default=OUT / 'initialized.state')
    parser.add_argument('--host', type=pathlib.Path,
                        default=OUT.parent / 'host-build/drumazon_host_artefacts/Release/drumazon_host')
    parser.add_argument('--sweep', action='store_true')
    args = parser.parse_args()
    raw = args.state.read_bytes()
    state = initialized_direct_state(raw)
    OUT.mkdir(parents=True, exist_ok=True)
    state_path = OUT / 'direct-init.state'
    state_path.write_bytes(state)
    cases = [('init-reference', {}), ('repeat', {})]
    if args.sweep:
        for knob in ('Pitch', 'Tune', 'Decay', 'Tune Depth', 'Attack'):
            for value in (0, .25, .5, .75, 1):
                cases.append((knob.lower().replace(' ', '-') + f'-{value:g}', {'BD ' + knob: value}))

    def capture(case):
        name, params = case
        output = OUT / (name + '.wav')
        cmd = [str(args.host.resolve()), str(pathlib.Path(args.plugin).resolve()),
               str(state_path), str(output)]
        for key, value in params.items():
            cmd.extend((key, str(value)))
        with (OUT / (name + '.log')).open('w') as log:
            subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=90)
        rate, audio = read(output)
        assert rate == 44100 and audio.ndim == 2 and audio.shape[1] == 2
        assert audio.dtype == np.float32, "reference must preserve floating-point headroom"
        peak = float(np.max(np.abs(audio.astype(np.float64))))
        assert peak > 1e-5, (name, 'silent reference')
        print('captured', name, 'peak', peak, flush=True)
        return {'name': name, 'normalized_overrides': params, 'peak': peak,
                'wav_sha256': hashlib.sha256(output.read_bytes()).hexdigest()}

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(capture, cases))
    assert results[0]['wav_sha256'] == results[1]['wav_sha256'], 'Init repeat differs'
    (OUT / 'capture.json').write_text(json.dumps({
        'plugin': args.plugin, 'init_sha256': hashlib.sha256(raw).hexdigest(),
        'direct_state_sha256': hashlib.sha256(state).hexdigest(),
        'sample_format': 'float32', 'sample_rate': 44100, 'note': 36, 'velocity': 100, 'trigger_seconds': .1,
        'duration_seconds': 3, 'note_off': False, 'output_channels_buffered': 32,
        'cases': results
    }, indent=2) + '\n')


if __name__ == '__main__':
    main()
