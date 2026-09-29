"""Real allocation/upload/binding through unchanged stock selectors.

Static originals remain fallback paths. This does not qualify reclaiming them.
"""
from pathlib import Path
import json,os,shutil,subprocess,sys,re
if not __package__:
    sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
    __package__='tools.experimental.dsp_part_loader'
from .runtime_catalog import packages,ROOT
OUT=ROOT/'out/dsp-part-loader/runtime'
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    card=os.environ.get('DL_CARD')
    if not card:
        source=os.environ.get('OT_PROJECT')
        if not source:
            print('[SKIP] runtime: supply OT_PROJECT or DL_CARD');return
        sys.path.insert(0,str(ROOT/'tools/harness'))
        from ab_fixture import prepare
        fixture=prepare(source,OUT/'fixture')
        card=str(OUT/'card.img')
        subprocess.run([sys.executable,'tools/emu/ot_emu/stage_card.py',str(fixture),'OCTABAM','RIG',
                        '--tree',str(OUT/'tree'),'--out',card],cwd=ROOT,check=True)
    syms={p[2]:int(p[0],16) for p in (l.split() for l in subprocess.check_output(
        ['m68k-elf-nm',str(ROOT/'out/platform/runtime/runtime.elf')],text=True).splitlines()) if len(p)==3}
    image=OUT/'image.bin'; shutil.copyfile(ROOT/'out/mainos_bus.bin',image)
    raw=image.read_bytes()
    def rd32(a): return int.from_bytes(raw[a-0x40000400:a-0x40000400+4],'big')
    def row(id):
        for i in range(32):
            ptr=rd32(0x400d6060+4*i)
            if not ptr: break
            if rd32(ptr)==id:return i
        raise ValueError(id)
    def poke(vs): return ';'.join(f'{a+i:#x}={b}' for a,v,n in vs for i,b in enumerate(v.to_bytes(n,'big')))
    names={'dl_residency_commits':4,'dl_residency_rollbacks':4,'dl_residency_failures':4,
           'dl_residency_words':8,'dl_pool_base':8,'dl_selection_completed':4,
           'dl_selection_refused':4,'dl_errors':4,'dl_frames':4,'phase':4,'result':4}
    cases=[('eq-t1',0,12,False),('eq-t5',4,12,False),('character-t1',0,28,False),
           ('cancel-eq',0,12,True),('memory-full',0,0,False),('manual-part',0,0,False),
           ('automatic-apply',0,0,False)]
    cmd=[str(ROOT/'out/emu/ot_emu'),'--image',str(image),'--card',card,'--set','OCTABAM',
         '--project','RIG','--load-ms','20000','--frame','--dsp']
    for name,track,id,cancel in cases:
        d=OUT/name; d.mkdir(exist_ok=True); (d/'events.txt').write_text('1500 quit\n')
        vs=[(0x80000000,track,1)]
        if id: vs.append((0x460d5c94,row(id),4))
        else:
            part=0x40170f60+6322
            ids=[0]*16
            if name=='memory-full': ids[0:3]=[12,16,28]
            else: ids[0]=12;ids[4]=28
            vs += [(part+i,v,1) for i,v in enumerate(ids)]
        args=[str(d/'port.log'),'--step','-:poke:'+poke(vs)]
        args+=['--step','-:call:'+(f'0x400526e4' if id else
                     '0x40009094,0,1' if name=='automatic-apply' else '0x4004a8a4,1')]
        if cancel:args+=['--step','-:poke:'+poke([(0x460d5c94,row(4),4)])]
        spans=';'.join(f'{syms[n]:#x},{size}={d}/{n}.bin' for n,size in names.items())
        spans+=f';0x80000ec4,16={d}/ids.bin;0x80000003,1={d}/part.bin'
        args+=['--live-script',str(d/'events.txt'),'--mem-dump',spans,
               '--dsp-peek','0:X:215,64;1:X:215,64;0:P:1000,1408;1:P:dc0,1408']
        cmd+=['--scenario',' '.join(args)]
    with (OUT/'boot.log').open('w') as log:
        subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=540)
    data=packages(); report=[]
    for name,track,id,cancel in cases:
        d=OUT/name
        def vals(n):
            b=(d/f'{n}.bin').read_bytes()
            return [int.from_bytes(b[i:i+4],'big') for i in range(0,len(b),4)]
        r={n:vals(n) for n in names};r['case']=name
        report.append(r)
        assert r['dl_errors']==[0],r
        assert r['phase']==[0],r
        if name=='memory-full':
            assert r['dl_selection_refused']==[1] and (d/'part.bin').read_bytes()==b'\0',r
        elif cancel: assert r['dl_selection_completed']==[0] and r['dl_residency_rollbacks'][0]>=1,r
        else:
            if name!='automatic-apply': assert r['dl_selection_completed']==[1],r
            if id: assert (d/'ids.bin').read_bytes()[track]==id,r
            expected=([0,282] if track<4 else [282,0]) if id==12 else [0,932] if id==28 else [932,282]
            assert r['dl_residency_words']==expected,r
            log=(d/'port.log').read_text()
            wanted=[(1 if track<4 else 0,id)] if id else [(1,12),(0,28)]
            for core,p in wanted:
                base=r['dl_pool_base'][core]; pkg=data[core,p]
                m=re.search(rf'core {core} P:0x{base:05x}:((?: [0-9a-f]{{6}}){{1408}})',log)
                assert m,(name,'missing P memory')
                actual=[int(w,16) for w in m[1].split()]
                expected_words=list(pkg['words'])
                for reloc in pkg['relocations']:
                    i=reloc&0x7fff
                    expected_words[i]=(expected_words[i]-(base+64) if reloc&0x8000 else expected_words[i]+base+64)&0xffffff
                assert actual[64:64+len(expected_words)]==expected_words,(name,core,'upload differs')
                m=re.search(rf'core {core} X:0x00215:((?: [0-9a-f]{{6}}){{64}})',log)
                assert m,(name,'dispatch dump absent')
                dispatch=[int(w,16) for w in m[1].split()]
                assert (dispatch[p],dispatch[32+p])==(base+64+pkg['init'],base+64+pkg['proc']),(name,'dispatch did not bind')
        print('PASS:',name,flush=True)
    (OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
