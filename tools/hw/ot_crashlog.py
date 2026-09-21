#!/usr/bin/env python3
"""Passive macOS MIDI crash capture. No MIDI is transmitted.

  python3 tools/hw/ot_crashlog.py --list
  python3 tools/hw/ot_crashlog.py --port 'interface input' --out out/crash-session.jsonl
  python3 tools/hw/ot_crashlog.py --decode capture.midibytes

Diagnostic protocol v1: F0 7D 'OTD' 01 build type, big-endian nibble words,
XOR of all bytes between F0 and checksum, F7. Realtime bytes may interleave.
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import queue
import sys
import time


def decode(packet):
    if not packet.startswith(b'\xf0\x7dOTD\x01'):
        return None
    kind = packet[7] if len(packet) > 7 else 0
    expected = {1: 90, 2: 42}.get(kind)
    if len(packet) != expected or packet[-1] != 0xf7:
        raise ValueError('invalid diagnostic length/type')
    check = 0
    for b in packet[1:-2]: check ^= b
    if check != packet[-2] or any(b > 15 for b in packet[8:-2]):
        raise ValueError('diagnostic checksum/nibble mismatch')
    words = []
    for i in range(8, len(packet)-2, 8):
        value = 0
        for b in packet[i:i+8]: value = (value << 4) | b
        words.append(value)
    event = {'event': 'checkpoint' if kind == 1 else 'exception',
             'build': packet[6], 'frames': words[0],
             'audio_frame_seconds': round(words[0] * 16 / 44100, 3)}
    if kind == 1:
        event.update(clock=words[1], playing=words[2], tempo=words[3]/24,
                     skipped=words[4], tcb=f'0x{words[5]:08x}',
                     fx_ids=[v for word in words[6:] for v in word.to_bytes(4, 'big')])
    else:
        frame = words[2]
        event.update(stack=f'0x{words[1]:08x}', raw_frame=f'0x{frame:08x}',
                     vector=(frame >> 18) & 255, sr=f'0x{frame & 65535:04x}',
                     pc=f'0x{words[3]:08x}')
    return event


class Parser:
    """Bounded stream parser; system realtime never interrupts SysEx."""
    def __init__(self):
        self.packet = None
        self.clock = 0

    def feed(self, data):
        events = []
        for b in data:
            if b >= 0xf8:
                self.clock += b == 0xf8
                continue
            if b == 0xf0:
                self.packet = bytearray([b])
            elif b == 0xf7 and self.packet is not None:
                self.packet.append(b)
                raw = bytes(self.packet)
                self.packet = None
                try:
                    event = decode(raw)
                    if event: events.append(dict(event, raw=raw.hex()))
                except ValueError as e:
                    events.append({'event': 'invalid_trace', 'reason': str(e), 'raw': raw.hex()})
            elif b >= 0x80:
                self.packet = None
            elif self.packet is not None:
                if len(self.packet) < 256: self.packet.append(b)
                else: self.packet = None
        return events


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--port')
    ap.add_argument('--out', type=Path)
    ap.add_argument('--decode', type=Path)
    ap.add_argument('--seconds', type=float, default=0, help='0: until Ctrl+C')
    a = ap.parse_args()
    if a.decode:
        for event in Parser().feed(a.decode.read_bytes()): print(json.dumps(event))
        return
    if sys.platform != 'darwin': ap.error('Live capture currently uses macOS CoreMIDI')
    import ctypes as C
    import ot_midi as midi
    sources = midi.endpoints('src')
    if a.list:
        for name, _ in sources: print(name)
        return
    if not a.port or not a.out: ap.error('--port and --out are required')
    match = [ep for name, ep in sources if name == a.port]
    if len(match) != 1: ap.error('Choose one exact, unambiguous input name from --list')
    a.out.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation protects earlier crash evidence.
    log = a.out.open('x', buffering=1)
    incoming = queue.Queue(maxsize=4096)
    lost = [0]
    start = time.monotonic()

    def record(event):
        event = dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                     elapsed=round(time.monotonic()-start, 6), **event)
        log.write(json.dumps(event)+'\n')
        if event['event'] != 'midi_raw': print(json.dumps(event), flush=True)

    def callback(ptr, _a, _b):
        try:
            n = C.cast(ptr, C.POINTER(C.c_uint32))[0]
            p = ptr + 4
            for _ in range(n):
                length = C.c_uint16.from_address(p+8).value
                data = C.string_at(p+10, length)
                stamp = C.c_uint64.from_address(p).value
                try: incoming.put_nowait((stamp, data))
                except queue.Full: lost[0] += 1
                p += (10+length+3) & ~3
        except Exception:
            lost[0] += 1

    proc = midi.READPROC(callback)
    client, port = C.c_uint32(), C.c_uint32()
    def checked(code):
        if code: raise RuntimeError(f'CoreMIDI error {code}')
    checked(midi.cm.MIDIClientCreate(midi.cfstr('OT crash capture'), None, None, C.byref(client)))
    checked(midi.cm.MIDIInputPortCreate(client, midi.cfstr('capture'), proc, None, C.byref(port)))
    checked(midi.cm.MIDIPortConnectSource(port, match[0], None))
    midi.cf.CFRunLoopRunInMode.argtypes = [C.c_void_p, C.c_double, C.c_bool]
    mode = midi.cfstr('kCFRunLoopDefaultMode')
    parser = Parser()
    last, warned, sync, clock, overflow = None, False, start, 0, 0
    record({'event': 'capture_start', 'port': a.port,
            'note': 'Missing checkpoints alone do not establish a hardware or firmware cause.'})
    try:
        while not a.seconds or time.monotonic()-start < a.seconds:
            midi.cf.CFRunLoopRunInMode(mode, .05, False)
            for _ in range(4096):
                try: stamp, data = incoming.get_nowait()
                except queue.Empty: break
                record({'event': 'midi_raw', 'host_timestamp': stamp, 'hex': data.hex()})
                for event in parser.feed(data):
                    record(event)
                    if event['event'] == 'checkpoint':
                        last, warned = time.monotonic(), False
            now = time.monotonic()
            if last is not None and now-last > 6 and not warned:
                record({'event': 'checkpoint_gap', 'seconds': round(now-last, 2),
                        'note': 'May be OT stall, busy MIDI, cable/interface loss or host delay.'})
                warned = True
            if now-sync >= 1:
                if parser.clock != clock:
                    record({'event': 'midi_clock', 'ticks': parser.clock-clock})
                    clock = parser.clock
                if lost[0] != overflow:
                    record({'event': 'capture_overflow', 'lost_packets': lost[0]})
                    overflow = lost[0]
                log.flush(); os.fsync(log.fileno()); sync = now
    except KeyboardInterrupt:
        pass
    finally:
        record({'event': 'capture_stop'})
        log.flush(); os.fsync(log.fileno()); log.close()
        midi.cm.MIDIPortDispose(port)
        midi.cm.MIDIClientDispose(client)


if __name__ == '__main__': main()
