"""Unbound managed ids dispatch to a dry stub, never their original entries.

Under the port, on the dsp-dynload image:
- armed: after the first managed load, every managed id nothing uses points at
  one stub per core, and the stub is stock's null stub word for word (its
  loop end relocated with it);
- retire: retired code points its id at the stub, not at the original;
- restore: with the bypass off (the unguarded-apply oracle's setting) a retired
  id gets its saved original entry back, not the stub;
- dry vs none: a Part published around every guard and over capacity keeps
  EQ and PHASER unbound on T1/T2; all eight stereo chains and the main output
  must equal the same Part with FX NONE there (stock's null stub).
Owned fixture copies only.
"""
from pathlib import Path
import json,os,re,shutil,subprocess,sys,wave
if not __package__:
    sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
    __package__='tools.experimental.dsp_dynload'
from .runtime_catalog import ROOT
OUT=ROOT/'out/dsp-dynload/bypass'
FRAMES=1200
STOCK_STUB={0:0x7c8,1:0x588}          # payload A serves core 0, B core 1
# Part 1 (loads): Character on T1. Part 2: pinned. Part 3: EQ/PHASER/Character on
# T1-T3, over capacity on core 1 (282+207+932 > 1344). Part 4: the same with NONE.
IDS={0:[28]+[0]*15,1:[0]*16,2:[12,16,28]+[0]*13,3:[0,0,28]+[0]*13}
NAMES={12:'EQUALIZER',16:'PHASER',28:'CHARACTER'}
COUNTERS=('dl_unguarded','dl_residency_failures','dl_errors','dl_residency_words')
def main():
    if not os.environ.get('OT_PROJECT'):
        print('[SKIP] bypass: supply OT_PROJECT');return
    sys.path.insert(0,str(ROOT/'tools'));import toolpath
    from ab_fixture import prepare
    import ot_project as otp,blockdump as bd,recloop as rl
    from remix import registry
    OUT.mkdir(parents=True,exist_ok=True)
    project=prepare(os.environ['OT_PROJECT'],OUT/'fixture')
    mods=registry.modules()
    def mutate(data):
        # verify_live_audio's audible fixture: THRU sources, open amp, a trig.
        for p in range(otp.NPARTS_ALL):
            off=otp.PART_BASE+p*otp.PART_STRIDE; base=off+9
            for t in range(8):
                data[base+0x22+t]=2
                data[base+0x36+30*t:base+0x3d+30*t]=bytes((1,127,0,0,64,0,0))
                data[base+0x12+2*t]=64
                id=IDS[p%4][t]; data[base+t]=id; data[base+8+t]=0
                params=[v.default or 0 for v in mods[NAMES[id]].params] if id else [0]*12
                at=off+otp.P1_OFF+t*otp.TRACK_STRIDE; data[at:at+6]=bytes(params[:6])
                at=off+otp.P2_OFF+t*otp.P2_STRIDE; data[at:at+6]=bytes(params[6:12])
        for pat in range(16):
            for t in range(8):
                at=otp.trac_off(pat,t)
                for mask in (0,0x40,0x48): data[at+mask+7]|=1
    otp._bank_write(project,1,mutate,guard=False)
    card=OUT/'card.img'
    subprocess.run([sys.executable,'tools/emu/ot_emu/stage_card.py',str(project),'OCTABAM','RIG',
                    '--tree',str(OUT/'tree'),'--out',str(card)],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
    syms={p[2]:int(p[0],16) for p in (l.split() for l in subprocess.check_output(
        ['m68k-elf-nm',str(ROOT/'out/platform/runtime/runtime.elf')],text=True).splitlines()) if len(p)==3}
    image=OUT/'image.bin';shutil.copyfile(ROOT/'out/mainos_bus.bin',image)
    cmd=[str(ROOT/'out/emu/ot_emu'),'--image',str(image),'--card',str(card),'--set','OCTABAM',
         '--project','RIG','--load-ms','20000','--frame','--dsp','--audio-in','tones']
    dumps=';'.join(f'{syms[n]:#x},{8 if n=="dl_residency_words" else 4}={{d}}/{n}.bin' for n in COUNTERS)
    dumps+=f';{syms["dl_pool_base"]:#x},8={{d}}/dl_pool_base.bin'
    peek='0:X:215,64;1:X:215,64;0:P:0,8192;1:P:0,8192'
    off=['--step',f'-:poke:{syms["dl_bypass_unbound"]+3:#x}=0']
    cases={'armed':[],'retire':['--step','-:call:0x40009094,0,1'],
           'restore':off+['--step','-:call:0x40009094,0,1'],
           'dry':['--step','100:call:0x40009094,0,2'],'none':['--step','100:call:0x40009094,0,3']}
    for name,steps in cases.items():
        d=OUT/name;d.mkdir(exist_ok=True)
        # Finish the load's own admission first: a raw apply inside its
        # completion window is a partial load, which parks both sets.
        args=[str(d/'port.log'),'--step',f'-:call:{syms["dl_publication_finish"]:#x}']
        if name in ('dry','none'):
            args+=['--sequencer','--internal-clock','--frames',str(FRAMES),'--main-level','64',
                   '--block-dump',str(d/'blocks.bin'),'--audio-out',str(d/'audio')]
        else:
            (d/'events.txt').write_text('1500 quit\n'); args+=['--live-script',str(d/'events.txt')]
        args+=steps+['--mem-dump',dumps.format(d=d),'--dsp-peek',peek]
        cmd+=['--scenario',' '.join(args)]
    with (OUT/'boot.log').open('w') as log:
        subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=900)
    def mem(name):
        log=(OUT/name/'port.log').read_text(); out={}
        for core in (0,1):
            m=re.search(rf'core {core} X:0x00215:((?: [0-9a-f]{{6}}){{64}})',log)
            p=re.search(rf'core {core} P:0000000:((?: [0-9a-f]{{6}}){{8192}})',log)
            assert m and p,(name,core,'dump absent')
            out[core]=([int(w,16) for w in m[1].split()],[int(w,16) for w in p[1].split()])
        return out
    def counters(name):
        r={}
        for n in COUNTERS:
            b=(OUT/name/f'{n}.bin').read_bytes()
            r[n]=[int.from_bytes(b[i:i+4],'big') for i in range(0,len(b),4)]
        return r
    def stub(core,dispatch,words,ids):
        # One stub per core, shared by every armed id, equal to stock's null
        # stub except the loop end, which moves with it.
        entries={(dispatch[p],dispatch[32+p]) for p in ids}
        assert len(entries)==1,(core,'armed ids disagree',entries)
        (si,sp),=entries
        s0=STOCK_STUB[core]
        assert (si,sp)!=(s0,s0+1),(core,'dispatch is stock stub, not the receiver copy')
        assert words[si]==words[s0],(core,'stub init differs')
        mine,stock=words[sp:sp+8],words[s0+1:s0+9]
        assert mine[:2]+mine[3:]==stock[:2]+stock[3:],(core,'stub body differs',mine,stock)
        assert mine[2]-sp==stock[2]-(s0+1),(core,'stub loop end not relocated')
        return si,sp
    report={}
    armed=mem('armed'); report['armed']=counters('armed')
    base=int.from_bytes((OUT/'armed'/'dl_pool_base.bin').read_bytes()[4:],'big')
    d1=armed[1][0]
    assert base+64<=d1[28]<base+1408,('Character not bound on core 1 after the load')
    # Managed and unused: EQ, PHASER, COMPRESSOR everywhere; Character on core 0.
    s0=stub(0,*armed[0],(12,16,24,28)); s1=stub(1,*armed[1],(12,16,24))
    assert report['armed']['dl_errors']==[0] and report['armed']['dl_unguarded']==[0],report['armed']
    print('PASS: armed',flush=True)
    retire=mem('retire'); report['retire']=counters('retire')
    assert (retire[1][0][28],retire[1][0][60])==s1,('retired Character is not on the stub')
    assert report['retire']['dl_residency_words']==[0,0],report['retire']
    assert report['retire']['dl_unguarded']==[0],report['retire']
    print('PASS: retire',flush=True)
    restore=mem('restore'); report['restore']=counters('restore')
    # The receiver keeps each id's original init/proc in the first 64 arena words.
    saved=(restore[1][1][base+56],restore[1][1][base+57])
    assert saved!=(0,0),'no saved original entry for Character on core 1'
    assert (restore[1][0][28],restore[1][0][60])==saved,('unbind did not restore the original entry',
            (restore[1][0][28],restore[1][0][60]),saved,s1)
    assert report['restore']['dl_residency_words']==[0,0] and report['restore']['dl_errors']==[0],report['restore']
    print('PASS: restore (bypass off): a retired id gets its original entry back',flush=True)
    for name in ('dry','none'): report[name]=counters(name)
    assert report['dry']['dl_residency_failures'][0]>0,('over-capacity Part was not refused',report['dry'])
    assert report['dry']['dl_unguarded'][0]>0,('tripwire blind to an unbound live id',report['dry'])
    dry=mem('dry')
    assert (dry[1][0][12],dry[1][0][44])==s1 and (dry[1][0][16],dry[1][0][48])==s1,'T1/T2 not on the stub'
    rec={n:bd.classes(bd.read(str(OUT/n/'blocks.bin'))) for n in ('dry','none')}
    audio=[]
    for track in range(1,9):
        for right in (False,True):
            a=rl.readback_audio(rec['none'],track,right);b=rl.readback_audio(rec['dry'],track,right)
            assert len(a)==len(b) and len(a)>=FRAMES*16,(track,'frame coverage')
            audio.append(dict(track=track,right=right,different=sum(x!=y for x,y in zip(a,b)),
                              peak=max(map(abs,a))))
    mains=[]
    for n in ('none','dry'):
        with wave.open(str(OUT/n/'audio_core0.wav'),'rb') as f:
            mains.append((f.getnframes(),f.getnchannels()*f.getsampwidth(),f.readframes(f.getnframes())))
    # The capture stops on the port's frame count, not a sample count: the dry
    # run's extra ColdFire work (a refused transaction, its modal) ended it one
    # output frame early (19447 vs 19448). Compare the common span; the block
    # dumps above are frame-exact.
    frames=min(mains[0][0],mains[1][0]); width=mains[0][1]
    report['audio']=audio;report['main_frames']=[mains[0][0],mains[1][0]]
    report['main_equal']=abs(mains[0][0]-mains[1][0])<=1 and \
        mains[0][2][:frames*width]==mains[1][2][:frames*width]
    (OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    assert max(r['peak'] for r in audio if r['track'] in (1,2))>1000,'silent T1/T2 oracle'
    assert all(r['different']==0 for r in audio) and report['main_equal'],'a stubbed slot is not NONE'
    print('PASS: dry equals NONE on all eight stereo chains and main')
    print('PASS: unbound managed ids run a dry copy of stock\'s null stub, never their originals')
if __name__=='__main__':main()
