#!/usr/bin/env python3
"""Real source transport and main output, 808 on T1 and 909 on T5.
No audio sample is staged. Port audio verifies integration, not 808/909 timbre.
"""
import json,math,os,pathlib,re,shutil,subprocess,sys,wave
ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'tools/hw'),str(ROOT/'tools/harness')]
import ot_project as otp
import blockdump as bd
import recloop as rl
import ab_source_probe
from analog_bassdrum import DEFAULTS, wav
SAMPLE808=os.environ.get("AB_SAMPLE808")=="1"
REVERSE=os.environ.get("AB_REVERSE")=="1"
MODELS=((0,1),(4,0)) if REVERSE else ((0,0),(4,1))
OUT=ROOT/("out/analog-bassdrum/port-gate-reverse" if REVERSE else "out/analog-bassdrum/port-gate")
if SAMPLE808: OUT=OUT.with_name(OUT.name+"-808")
def main():
    project=os.environ.get('OT_PROJECT')
    if not project:
        print('[SKIP] Analog Bassdrum port: set OT_PROJECT to a project fixture');return
    OUT.mkdir(parents=True,exist_ok=True)
    fixture=OUT/'project'
    if fixture.exists():shutil.rmtree(fixture)
    shutil.copytree(project,fixture)
    for bank in fixture.glob('bank*.work'):
        def mutate(d):
            for pi in range(8):
                base=otp.PART_BASE+pi*otp.PART_STRIDE+9
                for t,model in MODELS:
                    d[base+0x22+t]=1
                    d[base+60+30*t:base+63+30*t]=b'AB\x01'
                    p=DEFAULTS.copy();p[6]=model
                    for k,v in enumerate(p):d[base+(0x2a if k<6 else 0x1da)+30*t+6+k%6]=v
                    # Both FX off: measure native source through stock AMP.
                    d[base+t]=d[base+8+t]=0
            for pattern in range(16):
                for t in (0,4):
                    at=otp.trac_off(pattern,t)
                    d[at:at+8]=(1).to_bytes(8,'big')
        otp._bank_write(fixture,int(bank.stem[4:]),mutate,guard=False)
    card=OUT/'card.img'
    subprocess.run([sys.executable,str(ROOT/'tools/emu/ot_emu/stage_card.py'),str(fixture),'OCTABAM','RIG','--tree',str(OUT/'tree'),'--out',str(card)],check=True,cwd=ROOT)
    image=OUT/'image.bin';shutil.copy2(os.environ.get('AB_IMAGE',ROOT/'out/mainos_bus.bin'),image)
    symbols={l.split()[-1]:int(l.split()[0],16) for l in subprocess.check_output(['m68k-elf-nm',str(ROOT/'out/platform/runtime/runtime.elf')],text=True).splitlines() if len(l.split())==3}
    if os.environ.get('AB_SYMBOLS'): symbols=json.loads(pathlib.Path(os.environ['AB_SYMBOLS']).read_text())
    (OUT/'symbols.json').write_text(json.dumps(symbols,indent=2))
    dump=OUT/'blocks.bin';basewav=OUT/'audio'
    sampler=OUT/'dsp-source.txt'
    sample_model=0 if SAMPLE808 else 1
    sample_track=next(t for t,m in MODELS if m==sample_model)
    core,cont=(1,0x221) if sample_track==0 else (0,0x426)
    knobbase=0x3630 if SAMPLE808 else 0x3130
    spans=';'.join(f'{symbols[name]:#x},4={OUT}/{name}.bin' for name in ('ab_render_calls','ab_hits'))
    spans+=f';0x40170f60,6322={OUT}/part.bin'
    emu=ab_source_probe.build(OUT/'probe',core,cont,knobbase)
    cmd=[str(emu),'--image',str(image),'--card',str(card),'--set','OCTABAM','--project','RIG','--load-ms','20000','--sequencer','--internal-clock','--bank','1','--frames','450','--dsp','--main-level','64','--audio-out',str(basewav),'--block-dump',str(dump),'--mem-dump',spans]
    cmd+=['--dsp-pcwatch',f'{core}:{cont:x}']
    with open(OUT/'port.log','w') as log:
        log.write(' '.join(cmd)+'\n');log.flush()
        subprocess.run(cmd,env={**os.environ,'AB_SOURCE_TRACE':str(sampler)},
                       stdout=log,stderr=subprocess.STDOUT,cwd=ROOT,check=True,timeout=600)
    log=(OUT/'port.log').read_text()
    assert re.search(r'frames run : 450 .*run ended REACHED',log),log[-2000:]
    hits=int.from_bytes((OUT/'ab_hits.bin').read_bytes(),'big')
    assert hits>=2,('both tracks must trigger',hits)
    c=bd.classes(bd.read(dump));outputs=[]
    for t in (1,5):
        src=rl.track_audio(c,t);out=rl.readback_audio(c,t)
        model=dict(MODELS)[t-1]
        trackcore=1 if t==1 else 0
        if True:
            # The incoming stream is controls, not audio. Check both the
            # transported record and the DSP audio before stock AMP/FX.
            addrs=(0x800021d0,0x80002c50) if trackcore==0 else (0x80001c90,0x80002710)
            records=sorted(sum((c.get(('>',0,trackcore,a),[]) for a in addrs),[]))
            signed=[w for _,w in records if w[0]==0xab09 and w[2]==0x909]
            assert signed and any(w[3]==1 for w in signed), 'no DSP trigger record'
            expected=DEFAULTS.copy();expected[6]=model
            assert all(list(w[8:20])==expected for w in signed), 'knob transport'
        if model==sample_model:
            rows=[line.split('|') for line in sampler.read_text().splitlines()]
            voice=[r for r in rows if int(r[1],16)==0 and
                   [int(v,16) for v in r[3].split()[:12]]==expected]
            assert voice, 'DSP did not receive the knob block'
            source=[int(v,16) for r in voice for v in r[2].split()]
            source=[(v^0x800000)-0x800000 for v in source]
            assert max(map(abs,source))>1000, 'DSP source is silent'
            sys.path.insert(0,str(ROOT/'modules/analog-bassdrum'))
            import dsp909,dsp808
            reference=(dsp909.Voice() if model else dsp808.Voice());actual=[];expected_audio=[]
            for row in voice:
                controls=[int(v,16) for v in row[3].split()]
                trig=controls[12] if controls[12]<16 else None
                expected_audio.extend(reference.block(controls[:12],trig))
                actual.extend(((int(v,16)^0x800000)-0x800000)/8388608
                              for v in row[2].split()[::2])
            err=sum((a-b)**2 for a,b in zip(actual,expected_audio))
            power=sum(b*b for b in expected_audio)
            error_db=10*math.log10(max(err,1e-30)/max(power,1e-30))
            assert error_db < -60, ('DSP source/reference',error_db)
            print(f'PASS core {core}: full-image DSP source vs reference {error_db:.1f} dB')
        assert max(map(abs,out))>100,(t,'silent chain')
        assert out==rl.readback_audio(c,t,True),(t,'stereo mismatch')
        outputs.append(out);wav(OUT/f'track-{t}.wav',out)
        print(f'PASS T{t}: {"DSP 909" if model else "DSP 808"} controls/source and post-FX audio')
    assert outputs[0]!=outputs[1],'MODEL must select different engines'
    part=(OUT/'part.bin').read_bytes()
    for t,model in MODELS:
        assert part[0x22+t]==1 and part[60+30*t:63+30*t]==b'AB\x01'
        assert part[0x1da+30*t+6]==model
    path=pathlib.Path(str(basewav)+'_core0.wav')
    with wave.open(str(path),'rb') as f:
        data=f.readframes(f.getnframes())
    assert any(data),'main output is silent'
    print(f'PASS: both cores, {hits} triggers, stored model selection and main output')
if __name__=='__main__':main()
