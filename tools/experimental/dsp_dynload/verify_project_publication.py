"""Actual LOAD PROJECT with managed effects already saved in the active Part."""
from pathlib import Path
import os,sys,json,subprocess,shutil,re
if not __package__:
    sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
    __package__='tools.experimental.dsp_dynload'
from .runtime_catalog import ROOT,packages
OUT=ROOT/'out/dsp-dynload/project-publication'
def main():
    source=os.environ.get('OT_PROJECT')
    if not source:
        print('[SKIP] project publication: supply OT_PROJECT');return
    OUT.mkdir(parents=True,exist_ok=True)
    sys.path.insert(0,str(ROOT/'tools'));import toolpath
    from ab_fixture import prepare
    import ot_project as otp
    from remix import registry
    fixture=prepare(source,OUT/'fixture')
    for track,key in ((1,'EQUALIZER'),(5,'CHARACTER')):
        mod=registry.modules()[key];params=[v.default or 0 for v in mod.params]
        otp.set_fx(fixture,'fx1',track,key,page=params[:6],page2=params[6:],guard=False)
    card=OUT/'card.img'
    subprocess.run([sys.executable,'tools/emu/ot_emu/stage_card.py',str(fixture),'OCTABAM','RIG',
                    '--tree',str(OUT/'tree'),'--out',str(card)],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
    syms={p[2]:int(p[0],16) for p in (l.split() for l in subprocess.check_output(
        ['m68k-elf-nm',str(ROOT/'out/platform/runtime/runtime.elf')],text=True).splitlines()) if len(p)==3}
    image=OUT/'image.bin';shutil.copyfile(ROOT/'out/mainos_bus.bin',image)
    (OUT/'events.txt').write_text('1000 quit\n')
    sizes={'dl_residency_words':8,'dl_residency_commits':4,'dl_residency_failures':4,
           'dl_project_admitted':4,'dl_project_completed':4,'dl_project_refused':4,
           'dl_selection_requested':4,'dl_errors':4,'phase':4,'dl_pool_base':8}
    spans=';'.join(f'{syms[n]:#x},{size}={OUT}/{n}.bin' for n,size in sizes.items())
    spans+=f';0x80000ec4,16={OUT}/ids.bin'
    cmd=[str(ROOT/'out/emu/ot_emu'),'--image',str(image),'--card',str(card),'--set','OCTABAM',
         '--project','RIG','--load-ms','20000','--frame','--dsp','--live-script',str(OUT/'events.txt'),
         '--mem-dump',spans,'--dsp-peek','0:X:215,64;1:X:215,64;0:P:1000,1408;1:P:dc0,1408']
    with (OUT/'port.log').open('w') as log:
        subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=420)
    report={}
    for n in sizes:
        b=(OUT/(n+'.bin')).read_bytes();report[n]=[int.from_bytes(b[i:i+4],'big') for i in range(0,len(b),4)]
    (OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
    assert report['dl_residency_words']==[932,282],report
    assert report['dl_residency_failures']==[0] and report['dl_errors']==[0],report
    assert report['dl_selection_requested']==[0] and report['phase']==[0],report
    assert report['dl_project_admitted']==[1] and report['dl_project_completed']==[1] and report['dl_project_refused']==[0],report
    ids=(OUT/'ids.bin').read_bytes();assert ids==bytes([12,0,0,0,28,0,0,0]+[0]*8)
    text=(OUT/'port.log').read_text();assert 'LOAD PROJECT posted: yes' in text and 'ended on quit' in text
    data=packages()
    for c,p in ((0,28),(1,12)):
        base=report['dl_pool_base'][c];pkg=data[c,p]
        m=re.search(rf'core {c} X:0x00215:((?: [0-9a-f]{{6}}){{64}})',text);assert m
        entries=[int(w,16) for w in m[1].split()]
        assert (entries[p],entries[32+p])==(base+64+pkg['init'],base+64+pkg['proc'])
        m=re.search(rf'core {c} P:0x{base:05x}:((?: [0-9a-f]{{6}}){{1408}})',text);assert m
        words=[int(w,16) for w in m[1].split()];expected=list(pkg['words'])
        for reloc in pkg['relocations']:
            i=reloc&0x7fff;expected[i]=(expected[i]-(base+64) if reloc&0x8000 else expected[i]+base+64)&0xffffff
        assert words[64:64+len(expected)]==expected
    print('PASS: actual project load populates both cores without chooser calls; exact P code and dispatch verified')
if __name__=='__main__':main()
