"""PASTE, RELOAD and RESET of the active Part are prepared before publication.

The three stock routines rewrite a Part and apply it at once when it is the
active one. Each dynamic case runs beside the same call with residency off
(static placement), which is the oracle for the published state. Owned
fixture copies only.
"""
from pathlib import Path
import json,os,re,shutil,subprocess,sys
if not __package__:
    sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
    __package__='tools.experimental.dsp_dynload'
from .runtime_catalog import ROOT
OUT=ROOT/'out/dsp-dynload/part-edits'
BANK=0x400e21e0                         # bank 1
WORK=lambda part: BANK+0x8ed80+part*6322
SAVED=lambda part: BANK+0x9504a+part*6322
VALID=lambda part: BANK+0x9b312+part
PASTE,RELOAD,RESET=0x40029a4c,0x4004aab4,0x4004a9d0
# Part 1 (active) pinned only; Part 2 Character on T1; Part 3 memory-full on core 1.
IDS={0:[0]*16,1:[28]+[0]*15,2:[12,16,28]+[0]*13,3:[0]*16}
def poke(addr,values): return ';'.join(f'{addr+i:#x}={v}' for i,v in enumerate(values))
CASES={
    'static-paste':(0,[f'-:call:{PASTE:#x},{WORK(1):#x},0',f'-:poke:{poke(WORK(1),[0]*16)}']),
    'paste':(1,[f'-:call:{PASTE:#x},{WORK(1):#x},0',f'-:poke:{poke(WORK(1),[0]*16)}']),
    'paste-refused':(1,[f'-:call:{PASTE:#x},{WORK(2):#x},0']),
    'static-reload':(0,[f'-:poke:{poke(SAVED(0),IDS[1])};{VALID(0):#x}=1',f'-:call:{RELOAD:#x},0']),
    'reload':(1,[f'-:poke:{poke(SAVED(0),IDS[1])};{VALID(0):#x}=1',f'-:call:{RELOAD:#x},0']),
    'static-reset':(0,[f'-:call:{RESET:#x},0']),
    'reset':(1,[f'-:call:{RESET:#x},0']),
    'inactive':(1,[f'-:poke:{poke(SAVED(1),[12]+[0]*15)};{VALID(1):#x}=1',f'-:call:{RELOAD:#x},1']),
}
REGIONS={'part':(WORK(0),0x2a),'other':(WORK(1),0x2a),'ids':(0x80000ec4,16),'active':(0x80000002,3)}
COUNTERS=('dl_selection_requested','dl_selection_completed','dl_selection_refused','dl_selection_cancelled',
          'dl_unguarded','dl_residency_failures','dl_errors')
def main():
    if not os.environ.get('OT_PROJECT'):
        print('[SKIP] part edits: supply OT_PROJECT');return
    sys.path.insert(0,str(ROOT/'tools'));import toolpath
    from ab_fixture import prepare
    import ot_project as otp
    OUT.mkdir(parents=True,exist_ok=True)
    project=prepare(os.environ['OT_PROJECT'],OUT/'fixture')
    def mutate(data):
        for part in range(otp.NPARTS_ALL):
            at=otp.PART_BASE+part*otp.PART_STRIDE+9
            data[at:at+16]=bytes(IDS[part%4])
    otp._bank_write(project,1,mutate,guard=False)
    card=OUT/'card.img'
    subprocess.run([sys.executable,'tools/emu/ot_emu/stage_card.py',str(project),'OCTABAM','RIG',
                    '--tree',str(OUT/'tree'),'--out',str(card)],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
    syms={p[2]:int(p[0],16) for p in (l.split() for l in subprocess.check_output(
        ['m68k-elf-nm',str(ROOT/'out/platform/runtime/runtime.elf')],text=True).splitlines()) if len(p)==3}
    image=OUT/'image.bin';shutil.copyfile(ROOT/'out/mainos_bus.bin',image)
    defaults=[image.read_bytes()[a-0x40000400] for a in (0x400d47ad,0x400d4ad1)]
    def spans(d,label): return ';'.join(f'{a:#x},{n}={d}/{label}-{k}.bin' for k,(a,n) in REGIONS.items())
    cmd=[str(ROOT/'out/emu/ot_emu'),'--image',str(image),'--card',str(card),'--set','OCTABAM',
         '--project','RIG','--load-ms','20000','--frame','--dsp']
    for name,(enabled,steps) in CASES.items():
        d=OUT/name;d.mkdir(exist_ok=True);(d/'events.txt').write_text('2000 quit\n')
        args=[str(d/'port.log'),'--step',f'-:poke:{syms["dl_residency_enabled"]+3:#x}={enabled}',
              '--step','-:dump:'+spans(d,'before')]
        call=next(i for i,s in enumerate(steps) if ':call:' in s)
        for i,s in enumerate(steps):
            args+=['--step',s]
            if i==call: args+=['--step','-:dump:'+spans(d,'immediate')]
        args+=['--live-script',str(d/'events.txt'),
               '--mem-dump',spans(d,'final')+';'+';'.join(f'{syms[n]:#x},4={d}/{n}.bin' for n in COUNTERS),
               '--dsp-peek','1:X:215,64']
        cmd+=['--scenario',' '.join(args)]
    with (OUT/'boot.log').open('w') as log:
        subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=900)
    def region(name,label,key): return (OUT/name/f'{label}-{key}.bin').read_bytes()
    def dispatch(name):
        m=re.search(r'core 1 X:0x00215:((?: [0-9a-f]{6}){64})',(OUT/name/'port.log').read_text())
        assert m,(name,'dispatch dump absent')
        return [int(w,16) for w in m[1].split()]
    report={}
    for name,(enabled,steps) in CASES.items():
        r={n:int.from_bytes((OUT/name/f'{n}.bin').read_bytes(),'big') for n in COUNTERS}
        report[name]=r
        assert region(name,'before','ids')==bytes(16) and region(name,'before','active')[1]==0,(name,'fixture must load pinned Part 1')
        assert r['dl_errors']==0,(name,r)
        if not enabled: continue
        assert r['dl_unguarded']==0,(name,r,'a live set reached the DSP unprepared')
        final={k:region(name,'final',k) for k in REGIONS}
        if name=='paste-refused':
            for k in REGIONS: assert final[k]==region(name,'before',k),(name,k,'refused Part published')
            assert r['dl_selection_refused']==1 and r['dl_residency_failures']==1,(name,r)
        elif name=='inactive':
            # Data only: no transaction, the live set is untouched.
            assert final['other'][:16]==bytes([12]+[0]*15) and final['ids']==bytes(16),(name,final)
            assert r['dl_selection_requested']==0,(name,r)
        else:
            oracle='static-'+name
            for k in REGIONS: assert final[k]==region(oracle,'final',k),(name,k,'differs from static placement')
            if name=='reset':
                # The target the guard predicted is what stock wrote.
                assert final['part'][:16]==bytes([defaults[0]]*8+[defaults[1]]*8),(name,final['part'].hex())
            else:
                for k in ('part','ids'):
                    assert region(name,'immediate',k)==region(name,'before',k),(name,k,'published before preparation')
                assert final['ids'][0]==28 and dispatch(name)[28]!=dispatch(oracle)[28],(name,'Character not relocated')
            assert r['dl_selection_completed']==1,(name,r)
        print('PASS:',name,flush=True)
    (OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    print('PASS: PASTE, RELOAD and RESET of the active Part prepare before publication; refusal writes nothing')
if __name__=='__main__':main()
