"""A project whose effects all load on demand plays like stock 1.40C.

Under the port, on the analog-bd-dynload image (no stock DSP effect built
in) and on the user's pristine 1.40C as the oracle, the same fixture: eight
THRU tracks on tones, every Part of every bank carrying 11 stock DSP effects
across both cores (the reverbs wet: they default to MIX 0). All runs boot
with DSP X/Y filled with garbage (--dsp-dirty): the port otherwise boots
zeroed RAM, where an effect whose init only clears state sounds right
without it. Each image boots once; the scenarios fork from the loaded machine.

- load: the project load (guarded: its Part is bound before stock publishes
  it). No message, no transport error, no refused load, both cores loaded.
  After the load, the chains without long memory (LO-FI, SPATIALIZER, COMB:
  T4, T7, T8) equal stock sample for sample at one offset; FILTER (T2, T6) is
  within 2 LSB (-132 dB) (stock's never re-inits the project's FILTER: its state carries
  the boot default's); every chain's level is within 1 dB of stock's over the
  last 2 s. Reverbs are compared by level only: a later start leaves a
  different tail, and stock would differ from itself the same way.
- raw: after the load, stock's apply (0x40009094) publishes a Part around
  every guard, so its effects reach the DSP before they are loaded and take
  the dry stub's init. With the init fix (the slot parked at NONE until the
  code is bound) no chain's loudest quarter second exceeds stock's by more
  than 3 dB and every chain's level is within 1 dB of stock's doing the same; without it (negative control, dl_reinit_enabled
  0) some chain is off by more than 6 dB (measured: an uninitialised reverb
  plays garbage, +16.5 dB).
Owned fixture copies only.
"""
from pathlib import Path
import json,math,os,shutil,subprocess,sys
if not __package__:
    sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
    __package__='tools.experimental.dsp_dynload'
from .runtime_catalog import ROOT
OUT=ROOT/'out/dsp-dynload/stock-load'
FRAMES=12000
TAIL=2000
# (FX1, FX2) per track. T1-T4 are core 1, T5-T8 core 0; no LFO effects here
# (a later init shifts an LFO's phase for good, so those never re-align).
FX=[('EQUALIZER','PLATE REV'),('FILTER','DELAY'),('COMPRESSOR','DARK REV'),('LO-FI',None),
    ('DJ EQ','SPRING REV'),('FILTER',None),('SPATIALIZER',None),('COMB FILTER',None)]
COUNTERS=('dl_modal_shown','dl_errors','dl_residency_failures','dl_residency_commits','dl_parked',
          'dl_unguarded','dl_reinit','dl_residency_words')

def main():
    if not os.environ.get('OT_PROJECT'):
        print('[SKIP] stock load: supply OT_PROJECT');return
    sys.path.insert(0,str(ROOT/'tools'));import toolpath  # noqa: F401
    from ab_fixture import prepare
    import ot_project as otp,blockdump as bd,recloop as rl
    from remix import registry
    mods=registry.modules()
    OUT.mkdir(parents=True,exist_ok=True)
    project=prepare(os.environ['OT_PROJECT'],OUT/'fixture')
    def page(key):
        vals=[(v.default or 0) if v.name else 0 for v in mods[key].params]
        names=[v.name for v in mods[key].params]
        if key.endswith('REV') and b'MIX' in names: vals[names.index(b'MIX')]=80
        return vals
    def mutate(data):
        for p in range(otp.NPARTS_ALL):
            off=otp.PART_BASE+p*otp.PART_STRIDE; base=off+9
            for t in range(8):
                data[base+0x22+t]=2                                   # THRU
                data[base+0x36+30*t:base+0x3d+30*t]=bytes((1,127,0,0,64,0,0))
                data[base+0x12+2*t]=64
                for slot,key in enumerate(FX[t]):
                    data[off+(otp.FX1_OFF,otp.FX2_OFF)[slot]+t]=mods[key].menu.fx2_id if key else 0
                    vals=page(key) if key else [0]*12
                    at=off+otp.P1_OFF+t*otp.TRACK_STRIDE+6*slot; data[at:at+6]=bytes(v&0x7f for v in vals[:6])
                    at=off+otp.P2_OFF+t*otp.P2_STRIDE+6*slot; data[at:at+6]=bytes(v&0x7f for v in vals[6:12])
        for pat in range(16):
            for t in range(8):
                at=otp.trac_off(pat,t)
                for mask in (0,0x40,0x48): data[at+mask+7]|=1
    for path in project.glob('bank*.work'):
        otp._bank_write(project,int(path.stem[4:]),mutate,guard=False)
    card=OUT/'card.img'
    subprocess.run([sys.executable,'tools/emu/ot_emu/stage_card.py',str(project),'OCTABAM','RIG',
                    '--tree',str(OUT/'tree'),'--out',str(card)],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
    syms={p[2]:int(p[0],16) for p in (l.split() for l in subprocess.check_output(
        ['m68k-elf-nm',str(ROOT/'out/platform/runtime/runtime.elf')],text=True).splitlines()) if len(p)==3}
    # The raw scenario: Part 2 (bank 1 working copy) gets DARK on T1 FX2, EQ on
    # T3 FX1 and PLATE on T5 FX2, wet, and stock's apply publishes it raw.
    part=0x40170f60+6322
    raw_ids=[0]*16
    raw_ids[2]=mods['EQUALIZER'].menu.fx2_id; raw_ids[8]=mods['DARK REV'].menu.fx2_id
    raw_ids[12]=mods['PLATE REV'].menu.fx2_id
    raw_pages=[]
    for t,slot,key in ((0,1,'DARK REV'),(4,1,'PLATE REV'),(2,0,'EQUALIZER')):
        at=part-9+otp.P1_OFF+t*otp.TRACK_STRIDE+6*slot; raw_pages+=[(at+i,v&0x7f) for i,v in enumerate(page(key)[:6])]
    raw=['--step','400:poke:'+';'.join([f'{part+i:#x}={v}' for i,v in enumerate(raw_ids)]+
                                       [f'{a:#x}={v}' for a,v in raw_pages]),
         '--step','400:call:0x40009094,0,1']
    images={'stock':ROOT/'out/raw/section_3_MAIN_OS.bin','dynamic':ROOT/'out/mainos_bus.bin'}
    runs={'stock':('stock',[]),'stock-raw':('stock',raw),'dynamic':('dynamic',[]),'dynamic-raw':('dynamic',raw),
          'noinit-raw':('dynamic',['--step',f'-:poke:{syms["dl_reinit_enabled"]+3:#x}=0']+raw)}
    for img,path in images.items():
        d0=OUT/img; d0.mkdir(exist_ok=True); shutil.copyfile(path,d0/'image.bin')
        cmd=[str(ROOT/'out/emu/ot_emu'),'--image',str(d0/'image.bin'),'--card',str(card),'--set','OCTABAM',
             '--project','RIG','--load-ms','20000','--frame','--dsp','--dsp-dirty','--audio-in','tones',
             '--audio-in-from-boot','--pre-roll','8']
        for name,(which,extra) in runs.items():
            if which!=img: continue
            d=OUT/name; d.mkdir(exist_ok=True)
            args=[str(d/'port.log'),'--sequencer','--internal-clock','--frames',str(FRAMES),'--main-level','64',
                  '--block-dump',str(d/'blocks.bin')]
            if img=='dynamic':
                args+=['--step',f'-:call:{syms["dl_publication_finish"]:#x}']
            args+=extra
            if img=='dynamic':
                args+=['--mem-dump',';'.join(f'{syms[n]:#x},{8 if n=="dl_residency_words" else 4}={d}/{n}.bin'
                                             for n in COUNTERS)+f';0x80000ec4,16={d}/ids.bin']
            cmd+=['--scenario',' '.join(args)]
        with (d0/'boot.log').open('w') as log:
            subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=3600)
    rec={n:bd.classes(bd.read(str(OUT/n/'blocks.bin'))) for n in runs}
    audio={n:{(t,r):rl.readback_audio(rec[n],t,r) for t in range(1,9) for r in (False,True)} for n in runs}
    def rms(x): return math.sqrt(sum(v*v for v in x)/len(x)) if x else 0.0
    def db(a,b): return 20*math.log10((rms(a)+1)/(rms(b)+1))
    def offsets(a,b):
        """Every offset at which b's tail occurs in a. The input tones are
        periodic, so one chain matches at a whole set (measured: L at 47, R at
        341 in the same run); the run's offset is the one all chains share."""
        tail=b[-TAIL*16:]; found=set()
        for s0 in range(len(a)-len(tail),-1,-1):
            if a[s0]==tail[0] and a[s0:s0+len(tail)]==tail: found.add(len(b)-len(tail)-s0)
        return found
    def aligned(ref,got,d,span):
        """ref's last `span` samples against got at offset d."""
        n=min(len(ref),len(got)-d); return ref[n-span:n],got[n-span+d:n+d]
    report={}
    for name in ('dynamic','dynamic-raw','noinit-raw'):
        r={}
        for n in COUNTERS:
            b=(OUT/name/f'{n}.bin').read_bytes(); r[n]=[int.from_bytes(b[i:i+4],'big') for i in range(0,len(b),4)]
        r['ids']=(OUT/name/'ids.bin').read_bytes().hex(); report[name]=r
    for name in ('dynamic','dynamic-raw','noinit-raw'):
        ref='stock-raw' if name.endswith('raw') else 'stock'
        common=None
        for t in (4,7,8):
            for right in (False,True):
                o=offsets(audio[ref][t,right],audio[name][t,right])
                common=o if common is None else common&o
        d=min(common,key=abs) if common else None
        r=report[name]; r['offset']=d; r['level_db']={}; r['max_diff']={}
        for t in range(1,9):
            for right in (False,True):
                k=f'T{t}{"R" if right else "L"}'
                if d is None: r['level_db'][k]=None; continue
                a,b=aligned(audio[ref][t,right],audio[name][t,right],d,2*44100)
                r['level_db'][k]=round(db(b,a),2); r['max_diff'][k]=max(abs(x-y) for x,y in zip(a,b))
                # The loudest quarter second over the whole scenario, against
                # stock's loudest: a publish that ran an effect uninitialised
                # shows as a burst here, not in the settled level.
                q=44100//4; ra=audio[ref][t,right]; rb=audio[name][t,right]
                r.setdefault('burst_db',{})[k]=round(20*math.log10(
                    (max(rms(rb[i+d:i+d+q]) for i in range(0,len(ra)-q,q))+1)/
                    (max(rms(ra[i:i+q]) for i in range(0,len(ra)-q,q))+1)),2)
    report['peaks']={f'T{t}':max(map(abs,audio['stock'][t,False])) for t in range(1,9)}
    (OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:{n:v for n,v in r.items() if n in ('offset','level_db','max_diff','dl_reinit','dl_modal_shown')}
                      if isinstance(r,dict) and 'offset' in r else r for k,r in report.items()},indent=1))
    assert all(v>1000 for v in report['peaks'].values()),('silent oracle track',report['peaks'])
    for name in ('dynamic','dynamic-raw'):
        r=report[name]
        assert r['dl_modal_shown']==[0] and r['dl_errors']==[0] and r['dl_residency_failures']==[0],(name,r)
        assert all(w>0 for w in r['dl_residency_words']),(name,'nothing loaded on a core',r)
        assert r['offset'] is not None,(name,'no common offset: LO-FI/SPATIALIZER/COMB never matched stock')
        assert all(abs(v)<=1.0 for v in r['level_db'].values()),(name,'a chain is off stock by more than 1 dB',r['level_db'])
    r=report['dynamic']
    for t in (4,7,8):
        assert r['max_diff'][f'T{t}L']==0 and r['max_diff'][f'T{t}R']==0,('load',t,'not sample-exact',r['max_diff'])
    for t in (2,6):
        assert r['max_diff'][f'T{t}L']<=2 and r['max_diff'][f'T{t}R']<=2,('load',t,'FILTER off by more than 2 LSB',r['max_diff'])
    print('PASS: load -- LO-FI/SPATIALIZER/COMB sample-exact, FILTER within 2 LSB, every chain within 1 dB of stock')
    r=report['dynamic-raw']
    assert r['dl_parked'][0]>0 and r['dl_reinit'][0]>0,('raw publish did not exercise the init fix',r)
    assert all(v<=3.0 for v in r['burst_db'].values()),('a burst louder than stock by more than 3 dB',r['burst_db'])
    print('PASS: raw publish around the guards -- slots parked until bound, no burst, every chain within 1 dB of stock')
    n=report['noinit-raw']
    assert n['offset'] is None or any(v is None or abs(v)>6 for v in n['level_db'].values()),\
        ('negative control: without the init fix every chain stayed within 6 dB -- the instrument does not see it',n['level_db'])
    print('PASS: negative control -- without the init fix a chain is off stock by more than 6 dB')
    print('PASS: a project with 11 stock effects loaded on demand plays like stock 1.40C')

if __name__=='__main__': main()
