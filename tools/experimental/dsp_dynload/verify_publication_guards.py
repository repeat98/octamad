"""Real pre-publication refusal: stopped pattern requests and LOAD PROJECT.

Owned fixtures only. These checks snapshot state immediately after requesting,
then run the real UI/engine tasks to prove deferred admission or no publication.
"""
from pathlib import Path
import os,sys,subprocess,shutil,json,re
if not __package__:
    sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
    __package__='tools.experimental.dsp_dynload'
from .runtime_catalog import ROOT
OUT=ROOT/'out/dsp-dynload/publication-guards'
def main():
    if not os.environ.get('OT_PROJECT'):
        print('[SKIP] publication guards: supply OT_PROJECT');return
    sys.path.insert(0,str(ROOT/'tools'));import toolpath
    from ab_fixture import prepare
    import ot_project as otp,emu_card
    OUT.mkdir(parents=True,exist_ok=True)
    project=prepare(os.environ['OT_PROJECT'],OUT/'fixture')
    def mutate(data):
        for part in (1,2,5,6):
            at=otp.PART_BASE+part*otp.PART_STRIDE+9
            data[at:at+16]=bytes([12,16]+[0]*14) if part%4==1 else bytes([12,16,28]+[0]*13)
        for pat in (1,2):
            data[otp.PTRN0+(pat+1)*otp.PTRN_FSTRIDE-5]=pat
    otp._bank_write(project,1,mutate,guard=False)
    _,_=emu_card.stage_project(project,'OCTABAM','RIG',tree=str(OUT/'tree'))
    bad=OUT/'bad';shutil.copytree(project,bad,dirs_exist_ok=True)
    def capacity(data):
        for part in (0,4):
            at=otp.PART_BASE+part*otp.PART_STRIDE+9
            data[at:at+16]=bytes([12,16,28]+[0]*13)
    otp._bank_write(bad,1,capacity,guard=False)
    shutil.copytree(bad,OUT/'tree/OCTABAM/BAD',dirs_exist_ok=True)
    card=OUT/'card.img';card.write_bytes(emu_card.build_image(str(OUT/'tree')))
    syms={p[2]:int(p[0],16) for p in (l.split() for l in subprocess.check_output(
        ['m68k-elf-nm',str(ROOT/'out/platform/runtime/runtime.elf')],text=True).splitlines()) if len(p)==3}
    image=OUT/'image.bin';shutil.copyfile(ROOT/'out/mainos_bus.bin',image)
    regions={'active':(0x80000002,3),'running':(0x800065bd,2),'ids':(0x80000ec4,16),
             'bank':(0x400e21e0,635712),'name':(0x100f8378,64)}
    counters=('dl_project_admitted','dl_project_refused','dl_project_completed',
              'dl_publication_prepared','dl_publication_refused','dl_residency_failures','dl_errors')
    def spans(d,label):
        return ';'.join(f'{a:#x},{n}={d}/{label}-{key}.bin' for key,(a,n) in regions.items())
    cmd=[str(ROOT/'out/emu/ot_emu'),'--image',str(image),'--card',str(card),'--set','OCTABAM',
         '--project','RIG','--load-ms','20000','--frame','--dsp']
    for name in ('stopped-static','stopped-ready','stopped-cancel','stopped-full','project-full'):
        d=OUT/name;d.mkdir(exist_ok=True);events=d/'events.txt';events.write_text('2000 quit\n')
        args=[str(d/'port.log'),'--step','-:dump:'+spans(d,'before')]
        if name=='project-full':
            ptr=syms['project_name']
            args+=['--step','-:poke:'+';'.join(f'{ptr+i:#x}={v}' for i,v in enumerate(b'BAD\0')),
                   '--step',f'-:call:0x40023c7c,{ptr:#x}']
        else:
            if name=='stopped-static':
                args+=['--step',f'-:poke:{syms["dl_residency_enabled"]+3:#x}=0']
            pat=1 if name in ('stopped-static','stopped-ready','stopped-cancel') else 2
            args+=['--step',f'-:call:0x400a0570,0,{pat},0,0xffffffff,0']
            if name=='stopped-cancel':
                args+=['--step','-:call:0x400a0570,0,0,0,0xffffffff,0']
        args+=['--step','-:dump:'+spans(d,'immediate'),'--live-script',str(events),
               '--mem-dump',spans(d,'final')+';'+';'.join(f'{syms[n]:#x},4={d}/{n}.bin' for n in counters)]
        args+=['--dsp-peek','1:X:215,64']
        cmd+=['--scenario',' '.join(args)]
    with (OUT/'boot.log').open('w') as log:
        subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=600)
    boot=(OUT/'boot.log').read_text()
    assert 'LOAD PROJECT never entered' not in boot and 'LOAD PROJECT posted: yes' in boot,boot[-3000:]
    results={}
    for name in ('stopped-ready','stopped-cancel','stopped-full','project-full'):
        d=OUT/name
        for key in regions:
            before=(d/f'before-{key}.bin').read_bytes()
            assert (d/f'immediate-{key}.bin').read_bytes()==before,(name,key,'early publication')
            if name!='stopped-ready':
                assert (d/f'final-{key}.bin').read_bytes()==before,(name,key,'refused target published')
        assert (d/'before-ids.bin').read_bytes()==bytes(16),'initial fixture must actually load'
        result={n:int.from_bytes((d/f'{n}.bin').read_bytes(),'big') for n in counters}
        assert result['dl_errors']==0,result
        assert result['dl_residency_failures']==int(name in ('stopped-full','project-full')),result
        if name=='stopped-ready':
            assert (d/'final-active.bin').read_bytes()==bytes((0,1,1))
            # Stock updates the stopped pattern/Part before live FX records.
            # Compare that behavior to the same call with relocation disabled.
            for key in regions:
                assert (d/f'final-{key}.bin').read_bytes()==(OUT/'stopped-static'/f'final-{key}.bin').read_bytes(),key
            def dispatch(where):
                m=re.search(r'core 1 X:0x00215:((?: [0-9a-f]{6}){64})',(OUT/where/'port.log').read_text())
                assert m
                return [int(w,16) for w in m[1].split()]
            original,loaded=dispatch('stopped-static'),dispatch(name)
            for effect in (12,16):
                assert loaded[effect]!=original[effect] and loaded[32+effect]!=original[32+effect]

            assert result['dl_publication_prepared']>0,result
        elif name=='project-full':
            assert result['dl_project_admitted']==1 and result['dl_project_completed']==1,result
            assert result['dl_project_refused']==1,result
        elif name=='stopped-cancel': assert result['dl_publication_prepared']==0,result
        else: assert result['dl_publication_refused']>0,result
        results[name]=result
    (OUT/'report.json').write_text(json.dumps(results,indent=2)+'\n')
    print(json.dumps(results,indent=2))
    print('PASS: stopped-pattern preparation and memory-full pattern/project refusal before any state publication')
if __name__=='__main__':main()
