#!/usr/bin/env python3
"""Engine gates: fixed-point bounds, silence, controls, retrigger and models.
These test numerical behavior; they do not establish hardware authenticity.
"""
import cmath
import ctypes as ct
import math
import pathlib
import subprocess
import sys
ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/harness'))
from analog_bassdrum import DEFAULTS, DEFAULTS_909, Voice, library, render, wav, OUT

def rms(x):return math.sqrt(sum(y*y for y in x)/max(1,len(x)))
def check(name,condition):
    if not condition:raise AssertionError(name)
    print('PASS',name)
def main():
    subprocess.run([sys.executable,str(ROOT/'modules/analog-bassdrum/generate.py'),'--check'],check=True)
    dll=library(); renders=[]
    for model in (0,1):
        p=DEFAULTS.copy();p[6]=model
        sound=render(dll,p);renders.append(sound)
        check(f'{model}: produces bounded audio',1000<max(map(abs,sound))<8388608)
        check(f'{model}: silence before trigger',not any(render(dll,p,seconds=.02,hits=())))
        check(f'{model}: decays',rms(sound[-4410:])<rms(sound[1000:5410])*.15)
        reserved=p.copy();reserved[5]=127
        check(f'{model}: unused source slot has no effect',render(dll,reserved,seconds=.1)==render(dll,p,seconds=.1))
        short=p.copy();short[1]=0;long=p.copy();long[1]=127
        check(f'{model}: DECAY extends tail',rms(render(dll,long,seconds=.3)[-4410:])>rms(render(dll,short,seconds=.3)[-4410:])*2)
        for knob in (0,1,2,3,4,6,7):
            lo=p.copy();lo[knob]=0;hi=p.copy();hi[knob]=1 if knob==6 else 127
            a=render(dll,lo,seconds=.1);b=render(dll,hi,seconds=.1)
            check(f'{model}: knob {knob} changes audio',a!=b)
        # Fast hits must be safe even at every parameter maximum.
        hot=[127]*12;hot[6]=model
        roll=render(dll,hot,seconds=.3,hits=range(0,13000,97))
        check(f'{model}: rapid retrigger bounded',max(map(abs,roll))<8388608)
        # Short hits must settle exactly, rather than leave a DC floor and
        # spend 40 seconds running an inaudible voice. Exercise both ends
        # of the tuning range so a low-frequency zero crossing cannot be
        # mistaken for silence.
        for tune in (0, 127):
            v=Voice();dll.ab_reset(ct.byref(v))
            q=p.copy();q[0]=tune;q[1]=0
            params=(ct.c_uint8*12)(*q)
            dll.ab_trigger(ct.byref(v),params)
            tail=[]
            for i in range(3*44100):
                sample=dll.ab_sample(ct.byref(v),params)
                if i>=3*44100-4000:tail.append(sample)
            check(f'{model}: short tail settles at tune {tune}',
                  not v.active and not any(tail))
        # The longest decay must also retire through the silence detector,
        # before the 40-second fail-safe. Catch quiet resonator limit cycles.
        v=Voice();dll.ab_reset(ct.byref(v))
        q=p.copy();q[1]=127;params=(ct.c_uint8*12)(*q)
        dll.ab_trigger(ct.byref(v),params)
        for i in range(39*44100):
            dll.ab_sample(ct.byref(v),params)
            if not v.active:break
        check(f'{model}: maximum decay retires before fail-safe',not v.active)
        long=p.copy();long[1]=127
        check(f'{model}: long decay preserves body',
              rms(render(dll,long,seconds=2)[-4410:])>1000)
        wav(OUT/f'analog-bassdrum-{808 if model==0 else 909}.wav',render(dll,p,seconds=4,hits=(0,44100,66150,77175)))
    check('models have different attack and body',renders[0]!=renders[1])
    # Model edits latch on a trigger and cannot corrupt a ringing tail.
    check('model edit waits for a hit',render(dll,seconds=.15,changes={100:{6:1}})==render(dll,seconds=.15))
    doubled=render(dll,seconds=.15,hits=(0,1000))
    fresh=render(dll,seconds=.15,hits=(1000,))
    check('808 retrigger retains resonator energy',doubled[1000:2000]!=fresh[1000:2000])
    # The source must evolve during silence, but not emit idle noise or
    # randomize pitch. Offset otherwise identical first hits by 731 samples.
    p=DEFAULTS_909.copy();p[8]=0
    early=render(dll,p,seconds=.1,hits=(0,))
    late=render(dll,p,seconds=.12,hits=(731,))[731:731+4410]
    check('909 idle noise phase changes the next attack',early!=late)
    p[3]=0
    check('909 idle time does not randomize the tonal circuit',
          render(dll,p,seconds=.1,hits=(0,))==render(dll,p,seconds=.12,hits=(731,))[731:731+4410])
    v=Voice();dll.ab_reset(ct.byref(v));params=(ct.c_uint8*12)(*p)
    v.active=0;v.noise=12345;before=v.noise
    for _ in range(1000):check_sample=dll.ab_sample(ct.byref(v),params)
    check('909 inactive clock runs without audible leakage',v.noise!=before and check_sample==0)
    # Actual engine transfer, compared with the analog network independently
    # derived from the service schematic. No isolated mock filter is used.
    p=DEFAULTS_909.copy();p[8]=0
    direct=render(dll,p,seconds=2);p[8]=64
    filtered=render(dll,p,seconds=2)
    def magnitude(signal,f):
        rotation=cmath.exp(-2j*math.pi*f/44100);phase=1;total=0j
        for sample in signal:total+=sample*phase;phase*=rotation
        return abs(total)
    cutoff=1/(2*math.pi*(3200*10000/13200)*10e-9)
    for f in (1000,6500,10000):
        measured=20*math.log10(magnitude(filtered,f)/magnitude(direct,f))
        expected=-10*math.log10(1+(f/cutoff)**2)
        check(f'909 original output RC response at {f} Hz',abs(measured-expected)<.4)
    p[6]=0;p[8]=0;a=render(dll,p,seconds=.1);p[8]=127
    check('808 ignores the 909 output control',a==render(dll,p,seconds=.1))
    print('Analog Bassdrum engine gates PASS; hardware matching unmeasured')
if __name__=='__main__':main()
