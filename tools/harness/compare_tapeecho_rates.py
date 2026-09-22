#!/usr/bin/env python3
"""Native fixed-point A/B renders and measurements, at identical gains.

Run the ColdFire oracle gate separately before trusting these renders.
No firmware is included; output lives under out/tapeecho-half.
"""
import array
import ctypes as C
import json
import math
import pathlib
import subprocess
import sys
import wave

ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/verify'))
from verify_tapeecho_cpu import State, Params, params, Q, SR, RING
OUT=ROOT/'out/tapeecho-half'
class HalfState(State):
    _fields_=[('input_history',C.c_int32*10),('wet_history',C.c_int32*5)]
class Engine:
    def __init__(self,lib,state,p):
        self.lib,self.state,self.p=lib,state(),p
        self.ring=(C.c_int32*(2*RING))()
        self.audio,self.record=(C.c_int32*32)(),(C.c_int32*32)()
        self.write=0
    def block(self,source):
        for i,v in enumerate(source): self.audio[i]=v
        self.lib.te_process(C.byref(self.state),C.byref(self.p),self.ring,self.write,self.audio,self.record)
        C.memmove(C.addressof(self.ring)+8*self.write,self.record,128)
        self.write=(self.write+16)%RING
        return list(self.audio)
    def render(self,source,events=None):
        out=array.array('i')
        for n in range(0,len(source),32):
            if events:events(n//32,self.p)
            out.extend(self.block(source[n:n+32]))
        return out

def tone(seconds,hz,amp=.01,burst=False):
    x=array.array('i')
    for n in range(int(seconds*SR)//16*16):
        envelope=min(1,n/64,(1024-n)/64) if burst and n<1024 else (0 if burst else 1)
        v=int(Q*amp*max(0,envelope)*math.sin(2*math.pi*hz*n/SR))
        x.extend((v,v))
    return x

def db(x): return 20*math.log10(max(x,1e-15))
def rms(x,start=0,end=None):
    values=x[2*start:2*end if end is not None else None:2]
    return math.sqrt(sum((v/Q)**2 for v in values)/max(1,len(values)))
def component(x,hz,start):
    values=x[2*start::2];w=2*math.pi*hz/SR
    a=sum(v/Q*math.cos(w*n) for n,v in enumerate(values))
    b=sum(v/Q*math.sin(w*n) for n,v in enumerate(values))
    return 2*math.hypot(a,b)/len(values)
def wav(path,values):
    # Identical 24-bit PCM scale; never normalize the two versions separately.
    with wave.open(str(path),'wb') as f:
        f.setnchannels(2);f.setsampwidth(3);f.setframerate(SR)
        f.writeframes(b''.join((max(-8388608,min(8388607,v>>8))&0xffffff).to_bytes(3,'little') for v in values))
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    libs={}
    for name,module,state in [('full','tapeecho',State),('half','tapeecho_half',HalfState)]:
        path=OUT/f'{name}.so'
        subprocess.run(['cc','-shared','-fPIC','-O2','-DTE_HOST=1',f'modules/{module}/cpu.c','-o',str(path)],cwd=ROOT,check=True)
        lib=C.CDLL(str(path));lib.te_process.argtypes=[C.c_void_p,C.POINTER(Params),C.POINTER(C.c_int32),C.c_uint32,C.POINTER(C.c_int32),C.POINTER(C.c_int32)]
        libs[name]=(lib,state)
    def render(name,p,source,events=None):return Engine(*libs[name],p).render(source,events)
    metrics={'frequency':[],'feedback':[],'buildup':{},'transients':{},'alias':{},'safety':{}}
    for time in (0,65):
        for age in (0,127):
            levels={}
            for hz in (1000,4000,8000,10000,12000):
                source=tone(.8,hz)
                for name in libs:
                    y=render(name,params(time=time,age=age),source)
                    levels[name,hz]=rms(y,SR//2)
            for hz in (4000,8000,10000,12000):
                row={'time':time,'age':age,'hz':hz}
                for name in libs:row[name]=db(levels[name,hz]/levels[name,1000])
                row['delta']=row['half']-row['full'];metrics['frequency'].append(row)
    print('Frequency measurements complete',flush=True)
    for hz in (250,1000,4000):
        source=tone(.7,hz,.003,True)
        for feedback in (64,89,102):
            row={'hz':hz,'feedback':feedback}
            for name in libs:
                y=render(name,params(time=60,feedback=feedback),source)
                row[name]=db(rms(y,2*5888+128,2*5888+896)/rms(y,5888+128,5888+896))
            row['delta']=row['half']-row['full'];metrics['feedback'].append(row)
    for name in libs:
        y=render(name,params(time=60,feedback=102),array.array('i',[0])*(20*SR//16*32))
        metrics['buildup'][name]=db(rms(y,19*SR))
        x=render(name,params(time=0,feedback=127,wow=127,age=127),tone(4,997,.9,True))
        metrics['safety'][name]={'peak':max(map(abs,x))/Q,'dc_last_second':sum(x[-2*SR::2])/SR/Q}
        y=render(name,params(time=0),tone(1,16000))
        metrics['alias'][name]={'6050_hz_dbc':db(component(y,6050,SR//2)/.01)}
    print('Feedback/alias measurements complete',flush=True)
    sources={}
    bright=array.array('i')
    for n in range(6*SR//16*16):
        t=n/SR;u=t%1.5
        v=int(Q*.14*math.exp(-u*35)*sum(math.sin(2*math.pi*f*t)/math.sqrt(i+1) for i,f in enumerate((330,997,2400,4100,6900,8900,12500)))) if t<3.1 else 0
        bright.extend((v,v))
    sources['bright-repeats']=(bright,dict(time=0,feedback=89,age=0,mix=110,wow=25),None)
    sources['feedback-buildup']=(tone(8,997,.08,True),dict(time=60,feedback=102,age=64,mix=127,wow=44),None)
    def free(b,p):
        if b>=1400:p.time=127 if (b//40)%2 else 0
    def beat(b,p):
        if b>=1400:
            p.sync=1;p.time=(b//24*31)%128
    for name,events in [('rapid-free-time',free),('rapid-beat-time',beat)]:
        sources[name]=(tone(4,997,.2),dict(time=65,feedback=64,wow=44,mix=110),events)
    for case,(source,options,events) in sources.items():
        rendered={}
        for name in libs:
            y=render(name,params(**options),source,events);rendered[name]=y
            wav(OUT/f'{case}-{name}.wav',y)
            if case.startswith('rapid'):
                k=2*math.cos(2*math.pi*997/SR);v=y[::2]
                residual=max(abs(v[i]-k*v[i-1]+v[i-2])/Q for i in range(22400,len(v)))
                metrics['transients'][f'{case}-{name}']=residual
        ab=rendered['full']+array.array('i',[0])*(SR//2*2)+rendered['half']
        wav(OUT/f'{case}-AB.wav',ab)
    # Exact stereo dry, dirty entry, and bounded latest-target convergence.
    e=Engine(*libs['half'],params(mix=0,feedback=127,wow=127))
    C.memset(C.addressof(e.state),0xa5,C.sizeof(e.state));e.state.active=0
    C.memset(C.addressof(e.ring),0x7f,C.sizeof(e.ring))
    dry=[0x71234567,-0x72345678]*16
    assert e.block(dry)==dry
    e=Engine(*libs['half'],params());C.memset(C.addressof(e.ring),0x7f,C.sizeof(e.ring))
    assert not any(e.render(array.array('i',[0])*4096))
    e.p.sync=1;e.p.time=127;e.p.tempo=720
    for _ in range(64):e.block([0]*32)
    assert e.state.position==132300*256 and e.state.fade_left==0
    metrics['safety']['half']['exact_dry_dirty_entry_beat_settling']=True
    (OUT/'comparison.json').write_text(json.dumps(metrics,indent=2)+'\n')
    print(json.dumps(metrics,indent=2),flush=True)
if __name__=='__main__':main()
