#!/usr/bin/env python3
"""CPU Tape Echo: native signal tests + actual compiled ColdFire/DMA execution.

No hardware timing claim: the instruction meter excludes real cache, RAM and
DMA contention. Full boot is independently covered by make check.
"""
import argparse
import ctypes as C
import json
import math
import os
import pathlib
import struct
import subprocess
import sys
import wave

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import toolpath  # noqa: E402,F401
from remix import registry, rig  # noqa: E402

OUT = ROOT / 'out/tapeecho-cpu'
SR, RING, Q = 44100, 176400, 2147483648
FAILS = 0

class State(C.Structure):
    _fields_ = ([(k, C.c_uint32) for k in ('active','valid','position','tempo','phase','rng')]
                + [(k, C.c_int32) for k in ('mix','feedback','age','wow','hiss')]
                + [('filters',(C.c_int32*5)*3),('coefficients',(C.c_int32*5)*1)]
                + [('flutter',C.c_uint32),('flutter_rate',C.c_uint32),('flutter_target',C.c_uint32),
                   ('wobble',C.c_int32),('wobble_step',C.c_int32),
                   ('fade_from',C.c_uint32),('fade_left',C.c_uint32),('mode',C.c_uint32)]
                + [(k,C.c_uint32) for k in ('cached_position','cached_age','cached_speed','cached_index','filter_pending')]
                + [('filter_targets',(C.c_int32*5)*1),('control_clock',C.c_uint32)])

class Params(C.Structure):
    _fields_ = [(k, C.c_uint32) for k in ('time','feedback','wow','sync','mix','age','tempo','lane')]

def params(**kw):
    p = Params(time=65, feedback=0, wow=0, sync=0, mix=127, age=0, tempo=2880)
    for k,v in kw.items(): setattr(p,k,v)
    return p

def run(args):
    r = subprocess.run([str(x) for x in args], cwd=ROOT, capture_output=True, text=True)
    if r.returncode: raise RuntimeError(f'{args}\n{r.stdout[-3000:]}\n{r.stderr[-3000:]}')
    return r.stdout

def check(name, ok, detail=''):
    global FAILS
    FAILS += not ok
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f': {detail}' if detail else ''), flush=True)

class Engine:
    def __init__(self, lib, p):
        self.lib, self.p, self.state = lib, p, State()
        self.ring = (C.c_int32*(RING*2))()
        self.audio, self.record = (C.c_int32*32)(), (C.c_int32*32)()
        self.write = 0

    def block(self, samples):
        for i,x in enumerate(samples): self.audio[i] = x
        self.lib.te_process(C.byref(self.state), C.byref(self.p), self.ring,
                            self.write, self.audio, self.record)
        for i,x in enumerate(self.record): self.ring[2*self.write+i] = x
        self.write = (self.write + 16) % RING
        return list(self.audio)

    def render(self, frames, source, events=None):
        out=[]
        for block in range((frames+15)//16):
            if events: events(block,self.p)
            inp=[source(block*16+i,c) for i in range(16) for c in range(2)]
            out.extend(self.block(inp)[::2])
        return out[:frames]

def native_tests(lib, wav):
    clocks = [1.5,2,3,4,6,8,9,12,16,18,24,36]
    good = True
    for bpm in (30,45,120,174,240,300):
        for time in range(128):
            p=params(time=time,sync=1,tempo=bpm*24)
            expected=SR*60*clocks[time*12//128]/(bpm*24)
            got=lib.te_target(C.byref(p),p.tempo)/256
            good &= abs(got-expected)<0.004
    check('All 128 BEAT values x 6 tempos snap to twelve exact musical divisions',good)
    e=Engine(lib,params(time=127,sync=1,tempo=720))
    out=e.render(132450,lambda n,c: Q//4 if n==64 else 0)
    expected=64+132300
    peak=max(range(expected-2,expected+33),key=lambda n: abs(out[n]))
    check('30 BPM dotted quarter arrives at three seconds without wrapping',
          expected-1<=peak<=expected+32 and abs(out[peak])>Q//1000
          and max(map(abs,out[expected-32:expected-2]))<Q//100000,str(peak-64))
    e=Engine(lib,params(mix=0,feedback=127,wow=127))
    dry=[0x71234567,-0x72345678]*16
    check('MIX=0 preserves all 32 bits of asymmetric dry audio',e.block(dry)==dry)
    # Old effect memory is deliberately nonzero. No full-ring clear is used.
    e=Engine(lib,params())
    C.memset(C.addressof(e.ring),0x7f,C.sizeof(e.ring))
    C.memset(C.addressof(e.state),0xa5,C.sizeof(e.state)); e.state.active=0
    out=e.render(2048,lambda n,c:0)
    check('Entering from dirty RAM cannot play the preceding effect\'s history',max(map(abs,out))==0)
    before=e.state.tempo; e.p.sync=1; e.p.tempo=0; e.block([0]*32)
    check('A missing tempo frame retains the last valid tempo',e.state.tempo==before)

    worst=0; where=None
    for wow in (0,44,127):
        e=Engine(lib,params(wow=wow))
        def events(b,p):
            # Interrupt the CPU crossfade at 1/8/16/24/40 blocks. The
            # latest target must queue without restarting a live fade.
            for at,gap in ((1400,1),(1500,8),(1600,16),(1700,24),(1800,40)):
                if b==at:p.sync=1
                if b==at+gap:p.sync=0
        out=e.render(32000,lambda n,c:int(Q*.2*math.sin(2*math.pi*997*n/SR)),events)
        k=2*math.cos(2*math.pi*997/SR)
        residual=max(abs(out[n]-k*out[n-1]+out[n-2])/Q for n in range(22400,len(out)))
        if residual>worst:worst,where=residual,wow
    check('Repeated and interrupted FREE/BEAT switches have no sharp click',worst<0.006,
          f'peak sine-recurrence residual {worst:.6f} FS, WOW={where}')
    good=True
    for time in (0,127,11,64,90,20):
        e.p.time=time; e.p.sync=1; e.p.tempo=720
        for _ in range(64):e.block([0]*32)
        good &= e.state.position==lib.te_target(C.byref(e.p),720) and not e.state.fade_left
    check('BEAT reaches the latest TIME target within 1024 samples, without a seconds-long glide',good)
    e=Engine(lib,params(time=0,mix=0))
    e.block([0]*32)
    good=True
    for time in (127,0,64):
        e.p.time=time
        target=lib.te_target(C.byref(e.p),e.p.tempo)
        for _ in range(5000):
            before=e.state.position
            e.block([0]*32)
            after=e.state.position
            good &= min(before,target)<=after<=max(before,target) and abs(after-before)<=512
        good &= e.state.position==target
    check('Cheap FREE slew is monotonic, bounded to two samples/block, and settles exactly',good)
    e=Engine(lib,params(wow=44))
    out=e.render(48000,lambda n,c:int(Q*.2*math.sin(2*math.pi*997*n/SR)),
                 lambda b,p:setattr(p,'time',127 if (b//40)%2 else 0) if b>=1400 else None)
    k=2*math.cos(2*math.pi*997/SR)
    residual=max(abs(out[n]-k*out[n-1]+out[n-2])/Q for n in range(22400,len(out)))
    check('Fast FREE TIME reversals retain continuous read-head motion',residual<.006,
          f'peak sine-recurrence residual {residual:.6f} FS')
    e=Engine(lib,params(time=0,feedback=127,wow=127,age=127))
    out=e.render(100000,lambda n,c:Q//2 if n==0 else 0)
    check('Maximum feedback/wow stays bounded',max(map(abs,out))<=Q)
    check('Self-oscillation does not settle on a DC rail',abs(sum(out[-44100:])/44100/Q)<0.01)

    e=Engine(lib,params(time=80,feedback=90,wow=40,age=50,mix=100))
    def source(n,c):
        elapsed=n%44100
        return int(Q*.13*math.exp(-elapsed/7000)*sum(math.sin(2*math.pi*f*n/SR)
                   for f in (220,277.18,329.63))) if n<SR*3 else 0
    out=e.render(SR*5,source,lambda b,p:setattr(p,'sync',1) if b==3500 else None)
    with wave.open(str(wav),'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(b''.join(struct.pack('<h',max(-32768,min(32767,x>>16))) for x in out))
    print(f'  [WAV] {wav} (native fixed-point oracle, matched against ColdFire execution)',flush=True)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('remix',nargs='?',default='tapeecho')
    ap.add_argument('--wav',type=pathlib.Path,default=OUT/'audition.wav')
    a=ap.parse_args()
    if 'TAPE ECHO' not in registry.remix(a.remix).modules:
        print(f'  [ -- ] CPU Tape Echo not in {a.remix}'); return 0
    OUT.mkdir(parents=True,exist_ok=True); a.wav.parent.mkdir(parents=True,exist_ok=True)
    print(run([sys.executable,'modules/tapeecho/generate_cpu.py','--check']),end='')
    mod=registry.by_key('TAPE ECHO')
    check('AGE occupies page-1 slot 3; detail page is disabled',
          mod.params[3].name==b'AGE' and mod.params[3].active and
          all(not p.active for p in mod.params[6:]))
    check('Hybrid CPU effect remains an insert selectable on all eight tracks',
          rig.category(mod)==rig.INSERT and list(rig.track_range(mod))==list(range(1,9)))
    r=subprocess.run([sys.executable,'tools/remix/audition.py','tapeecho','unused.wav'],
                     cwd=ROOT,capture_output=True,text=True)
    check('DSP-only audition refuses to mislabel dry passthrough as CPU Tape Echo',
          r.returncode!=0 and 'Tape Echo now runs on the CPU' in r.stderr)
    # make check owns the selected image.  Standalone runs consume the same
    # artifact, so they cannot silently replace what an earlier gate built.
    if not (ROOT/'out/mainos_bus.bin').is_file():
        raise RuntimeError(f'missing out/mainos_bus.bin; run make bus REMIX={a.remix}')
    libpath=OUT/'cpu-native.so'
    run(['cc','-shared','-fPIC','-O2','-DTE_HOST=1','modules/tapeecho/cpu.c','-o',libpath])
    lib=C.CDLL(str(libpath))
    lib.te_process.argtypes=[C.POINTER(State),C.POINTER(Params),C.POINTER(C.c_int32),C.c_uint32,
                            C.POINTER(C.c_int32),C.POINTER(C.c_int32)]
    lib.te_target.argtypes=[C.POINTER(Params),C.c_uint32]; lib.te_target.restype=C.c_uint32
    native_tests(lib,a.wav)
    run(['cc','-O2','-DTE_HOST=1','-c','modules/tapeecho/cpu.c','-o',OUT/'voice-cpu.o'])
    run(['c++','-O2','-std=c++17','tools/harness/tapeecho_voice_probe.cpp',OUT/'voice-cpu.o',
         '-o',OUT/'voice-probe'])
    voice=run([OUT/'voice-probe'])
    (OUT/'voice.log').write_text(voice)
    print(voice, end='', flush=True)
    # Configure only when the shared emulator build tree is absent or belongs
    # to another worktree. The targeted incremental build remains here so
    # probe/source edits cannot be tested against a stale executable.
    cache = ROOT/'out/emu/CMakeCache.txt'
    expected_source = (ROOT/'tools/emu/ot_emu').resolve()
    configured_source = None
    if cache.is_file():
        for line in cache.read_text(errors='replace').splitlines():
            if line.startswith('CMAKE_HOME_DIRECTORY:INTERNAL='):
                configured_source = pathlib.Path(line.partition('=')[2]).resolve()
                break
    if configured_source != expected_source:
        run(['cmake','--fresh','-S','tools/emu/ot_emu','-B','out/emu'])
    run(['cmake','--build','out/emu','--target','ot_tapeecho_cpu_test','-j8'])
    symbols=run(['m68k-elf-nm','-n','out/platform/runtime/runtime.elf'])
    (OUT/'profile-symbols.txt').write_text(symbols)
    syms={s[2]:int(s[0],16) for line in symbols.splitlines()
          if len(s:=line.split())==3}
    layout=json.loads((ROOT/'out/platform/layout.json').read_text())
    result=run(['out/emu/ot_tapeecho_cpu_test','out/mainos_bus.bin','out/platform/runtime.raw',
                f'{layout["base"]:x}',f'{syms["te_states"]:x}'])
    (OUT/'coldfire.log').write_text(result)
    print('\n'.join(line for line in result.splitlines() if '[PASS]' in line or '[METER]' in line))
    result=run(['out/emu/ot_tapeecho_cpu_test','out/mainos_bus.bin','out/platform/runtime.raw',
                f'{layout["base"]:x}',f'{syms["te_states"]:x}','--benchmark'])
    (OUT/'benchmark.log').write_text(result)
    print('\n'.join(line for line in result.splitlines() if any(tag in line for tag in ('[BENCH]','[PROFILE]','[LOAD]'))),flush=True)
    result=run(['out/emu/ot_tapeecho_cpu_test','out/mainos_bus.bin','out/platform/runtime.raw',
                f'{layout["base"]:x}',f'{syms["te_states"]:x}','--stress'])
    (OUT/'parameter-spikes.log').write_text(result)
    print('\n'.join(line for line in result.splitlines() if '[SPIKE]' in line),flush=True)
    print(f'\n{FAILS} failure(s)' if FAILS else '\nOK: CPU Tape Echo gates passed; hardware timing/listening still required')
    return int(bool(FAILS))

if __name__=='__main__':
    raise SystemExit(main())
