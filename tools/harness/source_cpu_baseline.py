#!/usr/bin/env python3
"""Count ColdFire instructions across real source calls, including their helpers.

Uses the existing PC watch; no timing model, injected renderer, or DSP-cycle
conversion. Fixtures and firmware remain local under out/. Requires a built
Analog Bassdrum image and a stock project to copy.
"""
import argparse
import collections
import hashlib
import json
import math
import pathlib
import re
import statistics
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'tools/verify'), str(ROOT/'tools/hw')]
import verify_repitch as fixture
import ot_project as otp
import blockdump as bd
import recloop as rl
from analog_bassdrum import DEFAULTS, DEFAULTS_909

OUT = ROOT/'out/analog-bassdrum/cpu-baseline'
WATCH = '0x4000d43e,0x4000d440,0x4000d52c,0x4000d52e'
HIT = re.compile(r'\[\s*(\d+)\] at (0x[0-9a-f]+).*?a0=(0x[0-9a-f]+|0).*?\[sp (0x[0-9a-f]+): ([^]]+)\]')
CASES = {
    'flex': ('flex',0,120,64),
    'static': ('static',0,120,64),
    'flex-pitched': ('flex',0,120,88),
    'flex-stretch': ('flex',2,90,64),
    'flex-beat': ('flex',3,90,64),
    'thru': ('flex',0,120,64),
    'neighbor': ('flex',0,120,64),
    'ab808': ('flex',0,120,64),
    'ab909': ('flex',0,120,64),
}

def prepare(src, name):
    work=OUT/name;work.mkdir(parents=True,exist_ok=True)
    machine,tstr,bpm,ptch=CASES[name]
    fixture.build_project(src,work/'project',tstr,2,bpm,ptch,127,machine)
    def mutate(data):
        for part in range(8):
            base=otp.PART_BASE+part*otp.PART_STRIDE+9
            for t in range(8):
                data[base+t]=data[base+8+t]=0  # FX NONE
                data[base+60+30*t:base+63+30*t]=bytes(3)
            if name in ('thru','neighbor'):
                data[base+0x22]=2
                data[base+0x2a+12:base+0x2a+18]=bytes((1,127,0,64,0,0))
                if name=='neighbor':data[base+0x23]=3
            if name.startswith('ab'):
                data[base+0x22]=1;data[base+60:base+63]=b'AB\x01'
                p=DEFAULTS if name=='ab808' else DEFAULTS_909
                for k,v in enumerate(p):data[base+(0x2a if k<6 else 0x1da)+6+k%6]=v
        for t in range(8):
            at=otp.trac_off(0,t)
            data[at:at+8]=(1 if t==0 or name=='neighbor' and t==1 else 0).to_bytes(8,'big')
    otp._bank_write(work/'project',1,mutate,guard=False)
    wav=OUT/'tone.wav'
    if not wav.exists():fixture.make_loop(wav)
    fixture.stage(work/'project',work/'card.img',wav)
    return work

def run(src,name,frames,image):
    raw=image.read_bytes()
    for address,expected in ((0x4000d43e,b'\x4e\x90'),(0x4000d440,b'\x4f\xef\x00\x10'),
                             (0x4000d52c,b'\x4e\x90'),(0x4000d52e,b'\x10\x12')):
        offset=address-0x40000400
        assert raw[offset:offset+len(expected)]==expected,'source ABI changed'
    work=prepare(src,name)
    target=1 if name=='neighbor' else 0
    cmd=[str(ROOT/'out/emu/ot_emu'),'--image',str(image),'--card',str(work/'card.img'),
         '--set','OCTABAM','--project','RIG','--load-ms','20000','--sequencer',
         '--internal-clock','--bank','0','--frames',str(frames),'--dsp','--main-level','64',
         '--audio-in','tones','--block-dump',str(work/'blocks.bin'),'--watch-pc',WATCH,
         '--mem-dump',f'0x800049d8,168={work}/voice.bin;0x80000510,48={work}/lane.bin;0x80004898,40={work}/source-state.bin']
    # The watch also sees project loading. Retain a bounded tail of target
    # calls, rather than save hundreds of thousands of irrelevant log lines.
    calls=collections.deque(maxlen=frames*2+100);pending=None
    with (work/'port.log').open('w') as log:
        log.write(' '.join(cmd)+'\n');log.flush()
        proc=subprocess.Popen(cmd,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        for line in proc.stdout:
            m=HIT.search(line)
            if not m:log.write(line);continue
            tick,pc,a0,sp,stack=m.groups()
            tick=int(tick);pc=int(pc,16);sp=int(sp,16);args=[int(x,0) for x in stack.split()]
            if pc in (0x4000d43e,0x4000d52c):
                assert pending is None,'nested source calls'
                if args[0]==target:
                    pending=dict(tick=tick,pc=pc,sp=sp,args=args[:4],entry=int(a0,0))
            elif pending is not None:
                expected=0x4000d440 if pending['pc']==0x4000d43e else 0x4000d52e
                assert pc==expected and sp==pending['sp'],'unpaired source return'
                pending['instructions']=tick-pending['tick']-1  # exclude caller JSR; include callee RTS
                calls.append(pending);pending=None
        rc=proc.wait()
    text=(work/'port.log').read_text()
    assert rc==0 and f'frames run : {frames} ' in text and 'run ended REACHED' in text,(name,rc)
    assert '2000000 hit(s)' not in text,'watch hit cap reached'
    # Use complete first/second-call pairs. The last frames belong to the
    # measured transport interval, not project loading. Drop first 50 frames.
    pairs=[];first=None
    for call in calls:
        if call['pc']==0x4000d43e:first=call
        elif first is not None:
            assert first['args'][2]==0 and first['args'][3]==call['args'][2] and call['args'][3]==16
            pairs.append((first,call));first=None
    pairs=pairs[-(frames-50):]
    assert len(pairs)==frames-50,(name,len(pairs))
    counts=[sum(c['instructions'] for c in pair) for pair in pairs]
    if not name.startswith('ab'):
        expected=0x4000466c if name=='neighbor' else 0x40004424 if name=='thru' else 0x40004008
        assert {c['entry'] for pair in pairs for c in pair}=={expected},'wrong source dispatch'

    resolved=None
    if name.startswith('flex') or name=='static':
        voice=(work/'voice.bin').read_bytes();lane=(work/'lane.bin').read_bytes()
        resolved=voice[24]
        assert lane[28]==CASES[name][1] and resolved==CASES[name][1],('TSTR not delivered',name,lane[28],resolved)
    classes=bd.classes(bd.read(work/'blocks.bin'))
    audio=rl.readback_audio(classes,target+1)
    assert len(audio)>=(frames-50)*16,(name,'missing output')
    audio=audio[-(frames-50)*16:]
    peak=max(map(abs,audio));assert peak>100,(name,'silent path',peak)
    result=dict(case=name,frames=len(pairs),output_samples=len(pairs)*16,
                mean_instructions_per_sample=statistics.mean(counts)/16,
                median_instructions_per_sample=statistics.median(counts)/16,
                min_frame_instructions=min(counts),max_frame_instructions=max(counts),
                source_entries=sorted({hex(c['entry']) for pair in pairs for c in pair}),
                output_peak=peak,output_rms=math.sqrt(sum(x*x for x in audio)/len(audio)),
                resolved_tstr=resolved,image_sha256=hashlib.sha256(image.read_bytes()).hexdigest())
    (work/'calls.json').write_text(json.dumps(pairs,indent=2)+'\n')
    (work/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)
    return result

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--project',type=pathlib.Path,required=True)
    ap.add_argument('--case',choices=CASES,action='append')
    ap.add_argument('--frames',type=int,default=450)
    ap.add_argument('--ab-image',type=pathlib.Path,default=ROOT/'out/analog-bassdrum/port-gate/image.bin')
    a=ap.parse_args();assert a.frames>=100
    OUT.mkdir(parents=True,exist_ok=True)
    for name in a.case or CASES:
        image=a.ab_image if name.startswith('ab') else ROOT/'out/raw/section_3_MAIN_OS.bin'
        run(a.project,name,a.frames,image)

if __name__=='__main__':main()
