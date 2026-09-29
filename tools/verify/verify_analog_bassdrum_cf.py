#!/usr/bin/env python3
"""Compare the built ColdFire engine with portable C, sample for sample.

Requires the selected firmware's runtime and Unicorn from the repo venv.
Instruction counts are diagnostics, not hardware timing measurements.
"""
import ctypes as ct
import pathlib
import struct
import subprocess
import sys

from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
from unicorn.m68k_const import (UC_CPU_M68K_CFV4E, UC_M68K_REG_A7,
                               UC_M68K_REG_D0, UC_M68K_REG_PC, UC_M68K_REG_SR)

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/harness'))
from analog_bassdrum import library, Voice, DEFAULTS


def main():
    runtime = ROOT / 'out/platform/runtime'
    nm = subprocess.check_output(['m68k-elf-nm', str(runtime / 'runtime.elf')], text=True)
    symbols = {f[2]: int(f[0], 16) for f in (line.split() for line in nm.splitlines())
               if len(f) == 3}
    headers = subprocess.check_output(
        ['m68k-elf-objdump', '-h', str(runtime / 'runtime.elf')], text=True)
    base = int(next(line.split()[3] for line in headers.splitlines()
                    if len(line.split()) > 3 and line.split()[1] == '.text'), 16)
    data = (runtime / 'runtime.bin').read_bytes()
    uc = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)
    uc.ctl_set_cpu_model(UC_CPU_M68K_CFV4E)
    mapped = base & ~4095
    uc.mem_map(mapped, (base - mapped + len(data) + 4095) & ~4095)
    uc.mem_write(base, data)
    uc.mem_map(0x10000, 0x20000)
    stop, voice, params, stack = 0x10000, 0x11000, 0x12000, 0x20000
    uc.reg_write(UC_M68K_REG_SR, 0x2000)
    instructions = [0]

    def count(_uc, _address, _size, _data):
        instructions[0] += 1
    uc.hook_add(UC_HOOK_CODE, count)

    def call(name, *args):
        uc.reg_write(UC_M68K_REG_A7, stack)
        uc.mem_write(stack, struct.pack('>' + 'I' * (1 + len(args)), stop, *args))
        uc.emu_start(symbols[name], stop, count=100000)
        assert uc.reg_read(UC_M68K_REG_PC) == stop, name
        assert uc.reg_read(UC_M68K_REG_A7) == stack + 4, (name, 'stack imbalance')
        return ct.c_int32(uc.reg_read(UC_M68K_REG_D0)).value

    # The same admission function protects both chooser commit paths.
    part = 0x23000
    uc.mem_write(part, bytes(0x400))
    assert call('ab_admit_track', part, 7) == 1
    for track in (0, 4):
        uc.mem_write(part + 0x22 + track, b'\x01')
        uc.mem_write(part + 60 + 30 * track, b'AB\x01')
    assert call('ab_admit_track', part, 7) == 0
    assert call('ab_admit_track', part, 0) == 1
    assert call('ab_admit_track', part, 4) == 1
    print('PASS two-instance admission; existing assignments remain selectable')

    for value,label in ((0,b'OFF'),(1,b'500'),(64,b'ORIG'),(127,b'18000')):
        uc.mem_write(0x24000,bytes(16))
        call('ab_lpf_fmt',0x24000,value)
        assert bytes(uc.mem_read(0x24000,len(label)+1))==label+b'\0'
    print('PASS native LPF formatter: OFF, Hz, ORIG')
    # Exercise the real renderer ABI at every frame split. The final
    # control record must occupy exactly the old two-segment FLEX span.
    for address,size in ((0x100b1000,0x1000),(0x46104000,0x1000),
                         (0x46c82000,0x1000),(0x80000000,0x10000),
                         (0x42000000,0xa0000)):
        uc.mem_map(address,size)
    bank=0x42000000; livepart=bank+0x8ed80; cursor=0x80001c90
    uc.mem_write(0x46c82456,struct.pack('>I',bank))
    uc.mem_write(livepart+0x22,b'\x01')
    uc.mem_write(livepart+60,b'AB\x01')
    uc.mem_write(0x800062a4,struct.pack('>I',0x26000))
    uc.mem_write(0x800062a8,struct.pack('>I',0x27000))
    knobs=[64,32,64,32,64,99,1,100,0,64,127,0]
    for model in (0,1):
        knobs[6]=model
        uc.mem_write(0x27000,b''.join(struct.pack('>H',v<<8) for v in knobs[:6]))
        uc.mem_write(0x80000830,bytes(knobs[6:]))
        for split in range(16):
            uc.mem_write(cursor,bytes([0xa5])*200)
            uc.mem_write(0x80001c80,struct.pack('>I',cursor))
            uc.mem_write(0x46104d0c,b'\x10')
            call('ab_render',0,0,0,split)
            call('ab_render',0,0,split,16)
            expected=struct.pack('>4I12H',0xab090000,0x09090001,0,0,*knobs)
            assert bytes(uc.mem_read(cursor,len(expected)))==expected,split
            assert int.from_bytes(uc.mem_read(0x80001c80,4),'big')==cursor+160
            assert bytes(uc.mem_read(cursor+160,40))==bytes([0xa5])*40
    print('PASS DSP control record: all 16 trigger offsets, knobs and next-record boundary')
    lib = library()
    for model in (0, 1):
        p = DEFAULTS.copy()
        p[6] = model
        array = (ct.c_uint8 * 12)(*p)
        state = Voice()
        uc.mem_write(params, bytes(p))
        call('ab_reset', voice)
        call('ab_trigger', voice, params)
        lib.ab_reset(ct.byref(state))
        lib.ab_trigger(ct.byref(state), array)
        before = instructions[0]
        for i in range(800):
            actual = call('ab_sample', voice, params)
            expected = lib.ab_sample(ct.byref(state), array)
            assert actual == expected, (model, i, actual, expected)
        # Check every state word as well as audio, then exercise model
        # switches and retriggers without resetting the voice.
        def same_state():
            expected = b''.join(struct.pack('>I', int(getattr(state, field)) & 0xffffffff)
                                for field, _ctype in Voice._fields_)
            assert bytes(uc.mem_read(voice, ct.sizeof(Voice))) == expected, 'state mismatch'
        same_state()
        average = (instructions[0] - before) / 800
        print(f'PASS ColdFire/native: model {model}, 800 identical samples; '
              f'{average:.1f} instructions/sample (not chip cycles)')
        for i in range(800):
            if i % 127 == 0:
                array[6] = 1-array[6]
                array[0] = (i*17) & 127
                array[1] = (i*31) & 127
                array[8] = (i*11) & 127
                uc.mem_write(params, bytes(array))
                call('ab_trigger', voice, params)
                lib.ab_trigger(ct.byref(state), array)
            assert call('ab_sample', voice, params) == lib.ab_sample(ct.byref(state), array)
        same_state()
        print('PASS ColdFire/native: retriggers, model changes and complete voice state')


if __name__ == '__main__':
    main()
