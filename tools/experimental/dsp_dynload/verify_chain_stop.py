"""STOP on a playing chain: its restart is admitted before publication.

Stock's STOP handler stores the chain's first pattern as the running pattern
(0x400a11c6) before it requests that pattern. The guard admits the whole
restart first. A real sequencer plays a real chain (the stock chain-add
routine builds it); static placement on the same firmware is the oracle.
Owned fixture copies only.

Scope: with every track's source byte below 4 the restart never rewrites the
live FX arrays (PUBLICATION.md, "a queued Part change does not re-apply FX"),
so `ids` is Character throughout, in the static twins too. This gate covers the
guard's protocol -- delay, replay, refusal, a prepared set passing -- and the
sequencer state it must not publish early. It does not show an FX change under
the guard; the tripwire cannot fire here.
"""
from pathlib import Path
import json,os,re,shutil,subprocess,sys
if not __package__:
    sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
    __package__='tools.experimental.dsp_dynload'
from .runtime_catalog import ROOT
OUT=ROOT/'out/dsp-dynload/chain-stop'
# 8-step patterns at 300 BPM: the first boundary lands near frame 790, which
# leaves the queued prefetch ~400 frames (4 steps gave it ~30, and it missed).
CHAIN,STOP,FRAMES=40,1250,1600
PART0=0x40170f60                   # bank 1, working Part 1: the chain's first Part
# The chain-add routine builds [playing pattern, *added], so the chain's first
# pattern is pattern 0: Part 1, Character, which the load left live. STOP restarts
# it. name: (chain after pattern 1, residency on, STOP presses, Part 1 edit).
# 'swap' makes Part 1 EQ on T1 at STOP (not live: the restart must be prepared
# first), 'full' makes it over capacity (refused), 'early' does the swap in time
# for the manager to prepare it as the queued next pattern before STOP.
EARLY=1000
EDITS={'swap':(STOP,(12,)),'full':(STOP,(12,16,28)),'early':(EARLY,(12,))}
CASES={'static':((1,2),0,1,None),'live':((1,2),1,1,None),
       'static-swap':((1,2),0,1,'swap'),'deferred':((1,2),1,1,'swap'),'refused':((1,2),1,1,'full'),
       'static-pair':((1,),0,1,None),'live-pair':((1,),1,1,None),
       'static-early':((1,),0,1,'early'),'prefetched':((1,),1,1,'early'),
       'static-double':((1,2),0,2,'swap'),'double-stop':((1,2),1,2,'swap')}
ORACLE={'live':'static','deferred':'static-swap','live-pair':'static-pair','prefetched':'static-early',
        'double-stop':'static-double'}
STATE=(('phase',4),('desired',16))     # the manager's own view at STOP
REGIONS={'running':(0x800065bd,6),'chain':(0x80006546,0x4c),'positions':(0x80006628,0x14),
         'active':(0x80000002,3),'ids':(0x80000ec4,16)}
COUNTERS=('dl_chain_deferred','dl_chain_restarted','dl_chain_dropped','dl_unguarded',
          'dl_publication_prepared','dl_publication_refused','dl_residency_failures',
          'dl_residency_commits','dl_errors')
def main():
    if not os.environ.get('OT_PROJECT'):
        print('[SKIP] chain stop: supply OT_PROJECT');return
    sys.path.insert(0,str(ROOT/'tools'));import toolpath
    from ab_fixture import prepare
    import ot_project as otp
    OUT.mkdir(parents=True,exist_ok=True)
    project=prepare(os.environ['OT_PROJECT'],OUT/'fixture')
    for path in (project/'project.work',project/'project.strd'):
        text=path.read_text()
        for key,value in (('PATTERN_TEMPO_ENABLED',0),('TEMPOx24',7200)):
            text,n=re.subn(rf'(?m)^{key}=.*$',f'{key}={value}',text)
            assert n==1,(path,key,n)
        path.write_text(text)
    # Pattern n links Part n. Part 1: Character (core 1); Part 2: EQ on core 1,
    # PHASER on core 0; Part 3: COMPRESSOR on core 1; Part 4: pinned only.
    ids={0:[28]+[0]*15,1:[12]*4+[16]*4+[0]*8,2:[24]+[0]*15,3:[0]*16}
    def mutate(data):
        for part in range(otp.NPARTS_ALL):
            at=otp.PART_BASE+part*otp.PART_STRIDE+9
            data[at:at+16]=bytes(ids[part%4])
        for pat in range(16):
            tail=otp.PTRN0+(pat+1)*otp.PTRN_FSTRIDE-11
            data[tail+2]=8;data[tail+3]=2;data[tail+6]=min(pat,3)
            for t in range(8): data[otp.trac_off(pat,t)+0x50:otp.trac_off(pat,t)+0x52]=bytes((8,2))
    otp._bank_write(project,1,mutate,guard=False)
    card=OUT/'card.img'
    subprocess.run([sys.executable,'tools/emu/ot_emu/stage_card.py',str(project),'OCTABAM','RIG',
                    '--tree',str(OUT/'tree'),'--out',str(card)],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
    syms={p[2]:int(p[0],16) for p in (l.split() for l in subprocess.check_output(
        ['m68k-elf-nm',str(ROOT/'out/platform/runtime/runtime.elf')],text=True).splitlines()) if len(p)==3}
    image=OUT/'image.bin';shutil.copyfile(ROOT/'out/mainos_bus.bin',image)
    def spans(d,label):
        return ';'.join([f'{a:#x},{n}={d}/{label}-{k}.bin' for k,(a,n) in REGIONS.items()]+
                        [f'{syms[k]:#x},{n}={d}/{label}-{k}.bin' for k,n in STATE])
    cmd=[str(ROOT/'out/emu/ot_emu'),'--image',str(image),'--card',str(card),'--set','OCTABAM',
         '--project','RIG','--load-ms','20000','--frame','--dsp']
    for name,(chain,enabled,presses,edit) in CASES.items():
        d=OUT/name;d.mkdir(exist_ok=True)
        args=[str(d/'port.log'),'--sequencer','--internal-clock','--frames',str(FRAMES),
              '--step',f'-:poke:{syms["dl_residency_enabled"]+3:#x}={enabled}']
        for pat in chain: args+=['--step',f'{CHAIN}:call:0x4009c634,{pat}']
        if edit:
            frame,ids=EDITS[edit]
            args+=['--step',f'{frame}:poke:'+';'.join(f'{PART0+i:#x}={v}' for i,v in enumerate(ids))]
        args+=['--step',f'{STOP}:dump:'+spans(d,'before')]
        args+=['--step',f'{STOP}:call:0x400a10c8']*presses
        args+=['--step',f'{STOP}:dump:'+spans(d,'immediate'),
               '--mem-dump',spans(d,'final')+';'+';'.join(f'{syms[n]:#x},4={d}/{n}.bin' for n in COUNTERS)
                            +f';{syms["dl_pool_base"]:#x},8={d}/dl_pool_base.bin',
               '--dsp-peek','1:X:215,64']
        cmd+=['--scenario',' '.join(args)]
    with (OUT/'boot.log').open('w') as log:
        subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=1500)
    def region(name,label,key): return (OUT/name/f'{label}-{key}.bin').read_bytes()
    def dispatch(name):
        m=re.search(r'core 1 X:0x00215:((?: [0-9a-f]{6}){64})',(OUT/name/'port.log').read_text())
        assert m,(name,'dispatch dump absent')
        return [int(w,16) for w in m[1].split()]
    report={}
    def word(name,label,key,at=0): return int.from_bytes(region(name,label,key)[at:at+4],'big')
    for name,(chain,enabled,presses,edit) in CASES.items():
        r={n:int.from_bytes((OUT/name/f'{n}.bin').read_bytes(),'big') for n in COUNTERS}
        report[name]=r
        before=region(name,'before','running')
        # The chain has advanced: pattern 2 runs, and the next pattern is queued.
        assert before[:4]==bytes((0,1,0,2 if len(chain)==2 else 0)),(name,before.hex(),'chain did not advance')
        assert region(name,'before','chain')[:4]==b'\0\0\0\1',(name,'chain inactive')
        assert r['dl_errors']==0,(name,r)
        if not enabled: continue
        assert r['dl_unguarded']==0,(name,r,'a live set reached the DSP unprepared')
        oracle=ORACLE.get(name)
        if name=='refused':
            for key in REGIONS:
                assert region(name,'final',key)==region(name,'before',key),(name,key,'refused restart published')
            assert r['dl_residency_failures']==1 and r['dl_publication_refused']>0,(name,r)
            assert r['dl_chain_deferred']==1 and r['dl_chain_restarted']==0,(name,r)
            print('PASS:',name,flush=True)
            continue
        for key in REGIONS:
            assert region(name,'final',key)==region(oracle,'final',key),(name,key,'final state differs from static')
        # STOP's own effect at the instant of the press, against static placement.
        immediate=lambda: [key for key in REGIONS
                           if region(name,'immediate',key)!=region(oracle,'immediate',key)]
        if name in ('live','live-pair'):
            # The first pattern's Part (Character) is live and stays live: the
            # restart is not delayed by whatever else the manager is preparing.
            assert word(name,'before','ids')>>24==28,(name,'Character is not live at STOP')
            assert not immediate(),(name,immediate(),'STOP was delayed')
            assert (r['dl_chain_deferred'],r['dl_chain_restarted'])==(0,0),(name,r)
        elif name=='deferred':
            # EQ is not live: nothing of the restart is published until it is.
            assert word(name,'before','ids')>>24==28,(name,'Character is not live at STOP')
            for key in ('running','chain','active','ids'):
                assert region(name,'immediate',key)==region(name,'before',key),(name,key,'early publication')
            assert (r['dl_chain_deferred'],r['dl_chain_restarted'],r['dl_chain_dropped'])==(1,1,0),(name,r)
            # The replayed restart applied EQ, from the arena, not from stock.
            base=int.from_bytes((OUT/name/'dl_pool_base.bin').read_bytes()[4:],'big')
            assert base+64<=dispatch(name)[12]<base+1408,(name,'EQ not bound to relocated code')
        elif name=='prefetched':
            # The manager holds exactly the first pattern's set, prepared as the
            # queued next pattern, so STOP publishes it on the spot.
            assert word(name,'before','phase')==5 and region(name,'before','desired')[:2]==bytes((12,0)),\
                (name,region(name,'before','phase').hex(),region(name,'before','desired').hex(),'not prefetched')
            assert word(name,'before','ids')>>24==28,(name,'Character is not live at STOP')
            assert not immediate(),(name,immediate(),'a prepared restart was delayed')
            assert (r['dl_chain_deferred'],r['dl_chain_restarted'])==(0,0),(name,r)
        else:
            # A second STOP clears the chain and requests its first pattern: the
            # newer request supersedes the deferred restart, which never replays.
            assert r['dl_chain_deferred']==1 and r['dl_chain_restarted']==0,(name,r)
        print('PASS:',name,flush=True)
    (OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    print('PASS: chain STOP restarts are prepared before publication, refused whole, and superseded cleanly')
if __name__=='__main__':main()
