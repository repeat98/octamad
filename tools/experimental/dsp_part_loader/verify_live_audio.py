"""Compare continuous eight-track audio during automatic apply and relocation.

Both runs use the same firmware, fixture and stock apply functions. One disables
residency before play, retaining the static placement as an audio oracle. This
qualifies transparency of relocation, not a crossfade between different sounds.
"""
from pathlib import Path
import json,os,re,shutil,subprocess,sys,wave
if not __package__:
    sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
    __package__='tools.experimental.dsp_part_loader'
from .runtime_catalog import ROOT
OUT=ROOT/'out/dsp-part-loader/live-audio'
def main(pattern=False,refuse=False):
    global OUT
    if pattern: OUT=ROOT/'out/dsp-part-loader/pattern-audio'
    if refuse: OUT=ROOT/'out/dsp-part-loader/pattern-refusal-audio'
    frames=8192 if pattern else 4096
    OUT.mkdir(parents=True,exist_ok=True)
    sys.path.insert(0,str(ROOT/'tools')); import toolpath
    from ab_fixture import prepare
    import ot_project as otp,blockdump as bd,recloop as rl
    from remix import registry
    if not os.environ.get('OT_PROJECT'):
        print('[SKIP] live audio: supply OT_PROJECT');return
    source=Path(os.environ['OT_PROJECT'])
    project=prepare(source,OUT/'fixture')
    if pattern:
        for path in (project/'project.work',project/'project.strd'):
            text=path.read_text()
            for key,value in (('MIDI_PROGRAM_CHANGE_RECEIVE',1),('MIDI_PROGRAM_CHANGE_RECEIVE_CH',0),('PATTERN_TEMPO_ENABLED',0),('TEMPOx24',2880)):
                text,n=re.subn(rf'(?m)^{key}=.*$',f'{key}={value}',text)
                assert n==1,(path,key,n)
            path.write_text(text)
    mods=registry.modules()
    names={12:'EQUALIZER',16:'PHASER',24:'COMPRESSOR',28:'CHARACTER'}
    for path in project.glob('bank*.work'):
        def mutate(data):
            for p in range(8):
                off=otp.PART_BASE+p*otp.PART_STRIDE; base=off+9
                for t in range(8):
                    data[base+0x22+t]=2
                    data[base+0x36+30*t:base+0x3d+30*t]=bytes((1,127,0,0,64,0,0))
                    data[base+0x12+2*t]=64
                    id=0 if p%4==0 else (12 if t<4 else 16) if p%4==1 else 28 if p%4==2 else 24
                    if refuse and p%4==1: id=(12,16,28,0,0,0,0,0)[t]
                    data[base+t]=id; data[base+8+t]=0
                    params=[v.default or 0 for v in mods[names[id]].params] if id else [0]*12
                    at=off+otp.P1_OFF+t*otp.TRACK_STRIDE
                    data[at:at+6]=bytes(params[:6])
                    at=off+otp.P2_OFF+t*otp.P2_STRIDE
                    data[at:at+6]=bytes(params[6:12])
            for pat in range(16):
                if pattern:
                    tail=otp.PTRN0+(pat+1)*otp.PTRN_FSTRIDE-11
                    data[tail+2]=16;data[tail+3]=2
                    data[tail+6]=1 if pat==1 else 0
                for t in range(8):
                    at=otp.trac_off(pat,t)
                    for mask in (0,0x40,0x48): data[at+mask+7]|=1
                    if pattern: data[at+0x50:at+0x52]=bytes((16,2))
        otp._bank_write(project,int(path.stem[4:]),mutate,guard=False)
    card=OUT/'card.img'
    subprocess.run([sys.executable,'tools/emu/ot_emu/stage_card.py',str(project),'OCTABAM','RIG',
                    '--tree',str(OUT/'tree'),'--out',str(card)],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
    syms={p[2]:int(p[0],16) for p in (l.split() for l in subprocess.check_output(
        ['m68k-elf-nm',str(ROOT/'out/platform/runtime/runtime.elf')],text=True).splitlines()) if len(p)==3}
    image=OUT/'image.bin';shutil.copyfile(ROOT/'out/mainos_bus.bin',image)
    cmd=[str(ROOT/'out/emu/ot_emu'),'--image',str(image),'--card',str(card),'--set','OCTABAM',
         '--project','RIG','--load-ms','20000','--frame','--dsp','--audio-in','tones']
    counters=('dl_residency_commits','dl_residency_failures','dl_errors','dl_residency_words','dl_publication_prepared','dl_publication_deferred','dl_publication_refused')
    for mode in ('static','dynamic'):
        d=OUT/mode;d.mkdir(exist_ok=True)
        args=[str(d/'port.log'),'--sequencer','--internal-clock','--frames',str(frames),'--main-level','64',
              '--step',f'-:poke:{syms["dl_residency_enabled"]+3:#x}={int(mode=="dynamic")}',
              '--block-dump',str(d/'blocks.bin'),'--audio-out',str(d/'audio'),
              '--mem-dump',';'.join(f'{syms[n]:#x},{8 if n=="dl_residency_words" else 4}={d}/{n}.bin' for n in counters)]
        if pattern:
            midi=d/'pattern.txt';midi.write_text('' if refuse and mode=='static' else '256 C0 01\n')
            args[-1]+=f';0x80000003,2={d}/part-pattern.bin'
            args+=['--midi',str(midi)]
        else:
            for frame,part in ((256,1),(1400,2),(2700,3),(3500,1)):
                args+=['--step',f'{frame}:call:0x40009094,0,{part}']
        cmd+=['--scenario',' '.join(args)]
    with (OUT/'boot.log').open('w') as log:
        subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=720)
    recordings={mode:bd.classes(bd.read(str(OUT/mode/'blocks.bin'))) for mode in ('static','dynamic')}
    report=[]
    for track in range(1,9):
        for right in (False,True):
            original=rl.readback_audio(recordings['static'],track,right)
            loaded=rl.readback_audio(recordings['dynamic'],track,right)
            assert len(original)==len(loaded) and len(original)>=frames*16,(track,'frame coverage')
            assert max(map(abs,original))>1000,(track,'silent oracle')
            different=sum(a!=b for a,b in zip(original,loaded))
            report.append(dict(track=track,right=right,samples=len(original),different=different))
    for core in (0,):
        audio=[]
        for mode in ('static','dynamic'):
            with wave.open(str(OUT/mode/f'audio_core{core}.wav'),'rb') as f: audio.append(f.readframes(f.getnframes()))
        report.append(dict(core=core,main_equal=audio[0]==audio[1]))
    if pattern:
        for mode in ('static','dynamic'):
            assert (OUT/mode/'part-pattern.bin').read_bytes()==bytes((0,0) if refuse else (1,1)),(mode,'queued pattern/Part publication')
    stats={}
    for mode in ('static','dynamic'):
        stats[mode]={}
        for n in counters:
            b=(OUT/mode/(n+'.bin')).read_bytes()
            stats[mode][n]=[int.from_bytes(b[i:i+4],'big') for i in range(0,len(b),4)]
    (OUT/'report.json').write_text(json.dumps(dict(audio=report,stats=stats),indent=2)+'\n')
    print(json.dumps(dict(audio=report,stats=stats),indent=2))
    if refuse:
        assert stats['dynamic']['dl_publication_refused'][0]>0,stats
        assert stats['dynamic']['dl_residency_words']==stats['static']['dl_residency_words'],stats
    else:
        assert stats['dynamic']['dl_residency_commits'][0]>stats['static']['dl_residency_commits'][0]
    assert stats['dynamic']['dl_errors']==[0] and (refuse or stats['dynamic']['dl_residency_failures']==[0])
    assert all(r.get('different',0)==0 and r.get('main_equal',True) for r in report),'audio changed during runtime relocation'
    print('PASS: eight stereo chains and main exactly match static placement through '+('a refused queued pattern with unchanged old audio' if refuse else 'a queued MIDI pattern/Part change' if pattern else 'four automatic apply changes'))
if __name__=='__main__':main(pattern='--pattern' in sys.argv,refuse='--refuse' in sys.argv)
