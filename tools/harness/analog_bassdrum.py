#!/usr/bin/env python3
"""Render the same fixed-point C engine compiled into the firmware."""
import ctypes as ct
import pathlib
import subprocess
import sys
import tempfile
import wave
import struct
ROOT=pathlib.Path(__file__).resolve().parents[2]
OUT=ROOT/'out/analog-bassdrum'
DEFAULTS=[64,80,80,64,64,0,0,64,127,64,64,0]
DEFAULTS_909=[64,32,64,32,64,0,1,64,64,64,64,0]
class Voice(ct.Structure):
    _fields_=[(k,ct.c_int32) for k in ('low','band','env','pitch','tone','dc','click')]+[(k,ct.c_uint32) for k in ('phase','noise','age','noise_clock')]+[(k,ct.c_int32) for k in ('previous','band_remainder','env_remainder','pitch_remainder','click_remainder','tone_remainder','dc_remainder','low_remainder','step_remainder','shaper','shaper_remainder','click_rise','click_edge','noise_lp','rise_remainder','edge_remainder','noise_remainder','output_lp','output_remainder')]+[(k,ct.c_uint) for k in ('model','active','pulse','quiet')]
def library():
    OUT.mkdir(parents=True,exist_ok=True)
    temp=tempfile.TemporaryDirectory(prefix='ab-native-',dir=OUT)
    lib=pathlib.Path(temp.name)/('engine.dylib' if sys.platform=='darwin' else 'engine.so')
    subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-fPIC','-shared',str(ROOT/'modules/analog-bassdrum/engine.c'),'-o',str(lib)],check=True)
    dll=ct.CDLL(str(lib)); dll._temporary_directory=temp; pp=ct.POINTER(ct.c_uint8)
    dll.ab_reset.argtypes=[ct.POINTER(Voice)]
    dll.ab_trigger.argtypes=[ct.POINTER(Voice),pp]
    dll.ab_sample.argtypes=[ct.POINTER(Voice),pp]; dll.ab_sample.restype=ct.c_int32
    return dll

def render(dll,params=None,seconds=3,hits=(0,),changes=None):
    v=Voice(); dll.ab_reset(ct.byref(v))
    p=(ct.c_uint8*12)(*(params or DEFAULTS))
    hits=set(hits); changes=changes or {}; out=[]
    for i in range(round(seconds*44100)):
        if i in changes:
            for k,value in changes[i].items(): p[k]=value
        if i in hits: dll.ab_trigger(ct.byref(v),p)
        out.append(dll.ab_sample(ct.byref(v),p))
    return out

def wav(path,samples):
    with wave.open(str(path),'wb') as f:
        f.setnchannels(1); f.setsampwidth(3); f.setframerate(44100)
        f.writeframes(b''.join((int(x)&0xffffff).to_bytes(3,'little') for x in samples))
def main():
    dll=library()
    for model in (0,1):
        p=(DEFAULTS_909 if model else DEFAULTS).copy()
        samples=render(dll,p,seconds=4,hits=(0,44100,66150,77175))
        path=OUT/f'analog-bassdrum-{808 if model==0 else 909}.wav'
        wav(path,samples);print(path)
if __name__=='__main__':main()
