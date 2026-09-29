#!/usr/bin/env python3
"""Current Analog BD instruction costs and whole-four-track DSP load.

Instructions are NOT hardware cycles. A local metering executable retains
all stopwatch pairs instead of only the first 4096; engine/emulator sources
are untouched. Requires an existing local out/emu build. Firmware remains
under out/. No hardware-safe percentage is inferred from these measurements.
"""
import argparse,concurrent.futures,hashlib,json,os,re,shlex,statistics,subprocess,sys
from pathlib import Path
import bd808,bd909
ROOT=bd909.ROOT
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tools/hw'),str(ROOT/'tools/verify')]
import toolpath,ot_project as otp,verify_repitch as fixture,blockdump,recloop
from remix import registry
OUT=ROOT/'out/analog-bassdrum/load-benchmark'
IMAGE=ROOT/'out/mainos_bus.bin'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def meter_host():
    """Link two locally instrumented units against the existing port libraries."""
    d=OUT/'meter';d.mkdir(parents=True,exist_ok=True);src=ROOT/'tools/emu/ot_emu'
    s=(src/'dsp.cpp').read_text();old='if(m_sw.last.size() < 4096) m_sw.last.push_back(static_cast<uint32_t>(d));'
    assert s.count(old)==1;s=s.replace(old,'m_sw.last.push_back(static_cast<uint32_t>(d));')
    (d/'dsp.cpp').write_text(s)
    s=(src/'main.cpp').read_text();needle='const auto& w = dspPair->stopwatch();';assert s.count(needle)==1
    s=s.replace(needle,needle+'''
            if(const char* path = std::getenv("AB_STOPWATCH_OUT")) {
                FILE* f = std::fopen(path, "w");
                if(!f) return 4;
                for(auto value : w.last) std::fprintf(f, "%u\\n", value);
                std::fclose(f);
            }
''');(d/'main.cpp').write_text(s)
    build=ROOT/'out/emu';flags=(build/'CMakeFiles/ot_emu.dir/flags.make').read_text()
    args=[]
    for k in ('CXX_DEFINES','CXX_INCLUDES','CXX_FLAGS'):
        args+=shlex.split(re.search(r'^'+k+r' = (.*)$',flags,re.M)[1])
    link=shlex.split((build/'CMakeFiles/ot_emu.dir/link.txt').read_text())
    obj=link.index('CMakeFiles/ot_emu.dir/main.cpp.o');tail=link[obj+1:];tail[tail.index('-o')+1]=str(d/'ot_emu')
    cmd=[link[0],*args,str(d/'main.cpp'),str(d/'dsp.cpp'),*tail]
    (d/'build-command.json').write_text(json.dumps(cmd,indent=2))
    subprocess.run(cmd,cwd=build,check=True,capture_output=True)
    return d/'ot_emu'

def engines():
    rows=[]
    for model,host in ((808,bd808),(909,bd909)):
        syms=host.build()
        for case in ('default','maximum','moving','split-triggers','idle'):
            k=list(host.INIT);k[8]=127
            blocks=[]
            for i in range(4096):
                v=k.copy()
                if case=='maximum':v=[127]*12;v[6]=int(model==909)
                if case=='moving':
                    v=[(i*(j*2+1)+j*17)%128 for j in range(12)];v[6]=int(model==909)
                trig=None if case=='idle' or i%137 else i%16
                if case=='split-triggers':trig=i%16
                blocks.append((v,trig))
            tag='benchmark-'+case;got=host.render(syms,blocks,tag)
            counts=list(map(int,(host.OUT/(tag+'.meter')).read_text().split()))
            assert len(counts)==4096
            rows.append(dict(model=model,case=case,mean=statistics.mean(counts)/16,peak=max(counts)/16,code_sha256=sha(host.OUT/f'bd{model}.bin')))
    (OUT/'engines.json').write_text(json.dumps(rows,indent=2));return rows

def prepare(project,name,models,fx1,fx2):
    work=OUT/name;work.mkdir(exist_ok=True);dest=work/'project'
    flex=name.endswith("-flex")
    fixture.build_project(project,dest,2 if flex else 0,2,300,88 if flex else 64,127)
    def mutate(data):
        for part in range(8):
            b=otp.PART_BASE+part*otp.PART_STRIDE+9
            source1=bytes(data[b+0x2a+6:b+0x2a+12]);source2=bytes(data[b+0x1da+6:b+0x1da+12])
            for t in range(8):
                data[b+0x22+t]=2 # THRU: deterministic live input on every remaining track
                data[b+60+30*t:b+63+30*t]=bytes(3)
                data[b+0x2a+30*t+12:b+0x2a+30*t+18]=bytes((1,127,0,64,0,0))
                if flex:
                    data[b+0x22+t]=1
                    data[b-9+0x2d3+5*t+1]=0
                    data[b+0x2a+30*t+6:b+0x2a+30*t+12]=source1
                    data[b+0x1da+30*t+6:b+0x1da+30*t+12]=source2
                if t in models:
                    model=models[t];data[b+0x22+t]=1;data[b+60+30*t:b+63+30*t]=b'AB\x01'
                    p=list(bd909.INIT if model else bd808.INIT);p[1]=127;p[5]=127;p[7]=100;p[8]=127
                    for k,v in enumerate(p):data[b+(0x2a if k<6 else 0x1da)+30*t+6+k%6]=v
        for t in range(8):
            at=otp.trac_off(0,t);data[at:at+8]=(0xffff).to_bytes(8,'big')
    otp._bank_write(dest,1,mutate,guard=False)
    for t in range(1,9):
        for slot,key in (('fx1',fx1),('fx2',fx2)):
            mod=registry.by_key(key);p=[x.default or 0 for x in mod.params]
            for i,x in enumerate(mod.params):
                if x.name in (b'MIX',b'GVOL'):p[i]=127
            # The fully-wet PLATE fixture is silent even in the stock host;
            # use its active 50% mix path and report this limitation explicitly.
            if key=='PLATE REV':p[5]=64
            otp.set_fx(dest,slot,t,key,p[:6],p[6:],guard=False)
    card=work/'card.img'
    if flex:
        tone=work/'tone.wav';fixture.make_loop(tone);fixture.stage(dest,card,tone)
    else:
        subprocess.run([sys.executable,str(ROOT/'tools/emu/ot_emu/stage_card.py'),str(dest),'OCTABAM','RIG','--tree',str(work/'tree'),'--out',str(card)],check=True,capture_output=True)
    return work,card

def run_case(emu,project,name,models,fx1,fx2,core,frames):
    work,card=prepare(project,name,models,fx1,fx2)
    # Four-track loop: no source or effect lies outside this window. Excludes
    # core-to-core waits and the mixdown/IO work before this loop.
    start,end=(0x372,0x53e) if core==0 else (0x17a,0x333)
    meter=work/'counts.txt';dump=work/'blocks.bin'
    cmd=[str(emu),'--image',str(IMAGE),'--card',str(card),'--set','OCTABAM','--project','RIG','--load-ms','20000','--sequencer','--internal-clock','--bank','0','--frames',str(frames),'--dsp','--main-level','32','--audio-in','tones','--block-dump',str(dump),'--dsp-stopwatch',f'{core}:{start:x}:{end:x}']
    (work/'command.json').write_text(json.dumps(cmd,indent=2))
    with (work/'port.log').open('w') as f:subprocess.run(cmd,env={**os.environ,'AB_STOPWATCH_OUT':str(meter)},stdout=f,stderr=subprocess.STDOUT,check=True,timeout=600)
    log=(work/'port.log').read_text();assert f'frames run : {frames} ' in log and 'run ended REACHED' in log,name
    all_counts=list(map(int,meter.read_text().split()));assert len(all_counts)>=frames,(name,len(all_counts))
    counts=all_counts[-frames:][50:]
    classes=blockdump.classes(blockdump.read(dump));tracks=[]
    for t in range(1,9):
        y=recloop.readback_audio(classes,t);assert y and max(map(abs,y))>100,(name,t,'silent')
        right=recloop.readback_audio(classes,t,True)
        assert len(y)==len(right) and max(map(abs,right))>100,(name,t,'missing right output')
        tracks.append(dict(track=t,peak=max(map(abs,y)),samples=len(y)))
    for t,m in models.items():
        c=1 if t<4 else 0;a=0x80001c90+(0 if c else 1344)
        records=[w[168*(t%4):] for addr in (a,a+0xa80) for _,w in classes.get(('>',0,c,addr),[])]
        assert any(w[0]==0xab09 and w[2]==0x909 and w[14]==m and w[3] in (1,2) for w in records),(name,t,'missing AB trigger')
    row=dict(case=name,models=models,fx1=fx1,fx2=fx2,core=core,frames=len(counts),mean=statistics.mean(counts)/16,peak=max(counts)/16,minimum=min(counts)/16,tracks=tracks,image_sha256=sha(IMAGE))
    (work/'result.json').write_text(json.dumps(row,indent=2));print(json.dumps(row),flush=True);return row

def main():
    global IMAGE, OUT
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--project',type=Path,required=True);ap.add_argument('--frames',type=int,default=900);ap.add_argument('--jobs',type=int,default=2);ap.add_argument('--case',action='append');ap.add_argument('--engines-only',action='store_true');ap.add_argument("--image",type=Path);ap.add_argument("--out",type=Path,default=OUT);a=ap.parse_args()
    if not a.engines_only and a.image is None:
        ap.error('--image must name a frozen Analog BD build copied after make bus finishes')
    if a.image is not None: IMAGE=a.image.resolve()
    OUT=a.out.resolve();OUT.mkdir(parents=True,exist_ok=True)
    if a.engines_only:engines();return
    emu=meter_host()
    cases=[]
    for fx1,fx2,tag in [('FILTER','PLATE REV','plate'),('FILTER','DARK REV','dark'),('DJ EQ','DJ EQ','eq')]:
        for models,suffix in [({},'stock'),({0:1,1:1},'909pair')]:cases.append((tag+'-'+suffix,models,fx1,fx2,1))
    cases += [('eq-stock-core0',{},'DJ EQ','DJ EQ',0),('eq-909pair-core0',{4:1,5:1},'DJ EQ','DJ EQ',0),('dark-808pair',{0:0,1:0},'FILTER','DARK REV',1),('dark-mixedpair',{0:0,1:1},'FILTER','DARK REV',1),('dark-split-core0',{0:0,4:1},'FILTER','DARK REV',0),('dark-split-core1',{0:0,4:1},'FILTER','DARK REV',1)]
    cases += [('eq-stock-flex',{},'DJ EQ','DJ EQ',1),('eq-909pair-flex',{0:1,1:1},'DJ EQ','DJ EQ',1),('dark-909pair-flex',{0:1,1:1},'FILTER','DARK REV',1)]
    for tag, fx1, fx2 in [('dark','FILTER','DARK REV'),('eq','DJ EQ','DJ EQ')]:
        for model, label in [(0,'808eight'),(1,'909eight'),(None,'mixedeight')]:
            models={t:(t%2 if model is None else model) for t in range(8)}
            for core in (0,1):
                cases.append((f'{tag}-{label}-core{core}',models,fx1,fx2,core))
    if a.case:cases=[c for c in cases if c[0] in a.case]
    rows=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.jobs) as pool:
        fs=[pool.submit(run_case,emu,a.project,*c,a.frames) for c in cases]
        errors=[]
        for f in concurrent.futures.as_completed(fs):
            try:rows.append(f.result())
            except Exception as e:
                errors.append(str(e));print('FAIL',e,flush=True)
    (OUT/'chains.json').write_text(json.dumps(dict(emu_sha256=sha(emu),units='executed instructions/sample, four-track processing window, not hardware cycles',rows=rows,errors=errors),indent=2))
    if errors:raise SystemExit('Failed load cases: '+str(errors))
if __name__=='__main__':main()
