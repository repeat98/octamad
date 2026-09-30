"""Selecting any stock effect loads it; an over-capacity Part is refused whole.

Under the port on the analog-bd-dynload image (no stock DSP effect built in),
through the stock FX setters a user reaches from the FX pages:
- each of the 13 stock DSP effects on T1 (core 1; the reverbs on FX2, the
  rest on FX1), two on T5 (core 0): the id goes live, its package is uploaded
  into the arena, its dispatch points there, no error, no refusal;
- a Part with eight different large effects on T1-T4 (4,665 words against a
  4,320-word arena) through the manual Part selector: refused, the Part index
  unchanged, nothing loaded, the MEMORY FULL message raised.
The fixture's project has every FX slot NONE (DL_CARD, the ui-gate card).
"""
from pathlib import Path
import json,os,re,shutil,subprocess,sys
if not __package__:
    sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
    __package__='tools.experimental.dsp_dynload'
from .runtime_catalog import ROOT,dynamic_packages
OUT=ROOT/'out/dsp-dynload/stock-select'
REVERBS=('PLATE REV','SPRING REV','DARK REV')
FULL=('FILTER','DJ EQ','CHORUS','FLANGER','DARK REV','SPRING REV','PLATE REV','LO-FI')  # T1-4 FX1, FX2
NAMES=('dl_residency_words','dl_pool_base','dl_pool_words','dl_errors','dl_residency_failures',
       'dl_selection_completed','dl_selection_refused','dl_modal_shown','phase')

def main():
    card=os.environ.get('DL_CARD')
    if not card:
        print('[SKIP] stock select: supply DL_CARD');return
    sys.path.insert(0,str(ROOT/'tools'));import toolpath  # noqa: F401
    from remix import registry,stock
    mods=registry.modules()
    OUT.mkdir(parents=True,exist_ok=True)
    syms={p[2]:int(p[0],16) for p in (l.split() for l in subprocess.check_output(
        ['m68k-elf-nm',str(ROOT/'out/platform/runtime/runtime.elf')],text=True).splitlines()) if len(p)==3}
    image=OUT/'image.bin';shutil.copyfile(ROOT/'out/mainos_bus.bin',image);raw=image.read_bytes()
    def rd32(a): return int.from_bytes(raw[a-0x40000400:a-0x40000400+4],'big')
    def row(table,id):
        for i in range(32):
            ptr=rd32(table+4*i)
            if not ptr: break
            if rd32(ptr)==id: return i
        raise ValueError((hex(table),id))
    def poke(vs): return ';'.join(f'{a+i:#x}={b}' for a,v,n in vs for i,b in enumerate(v.to_bytes(n,'big')))
    keys=[m.key for m in stock.MODULES if m.key!='DELAY']
    cases=[(k,0) for k in keys]+[('EQUALIZER',4),('DARK REV',4),('memory-full',0)]
    cmd=[str(ROOT/'out/emu/ot_emu'),'--image',str(image),'--card',card,'--set','OCTABAM',
         '--project','RIG','--load-ms','20000','--frame','--dsp']
    for name,track in cases:
        d=OUT/f'{name.replace(" ","_")}-t{track+1}';d.mkdir(exist_ok=True);(d/'events.txt').write_text('1500 quit\n')
        args=[str(d/'port.log'),'--step',f'-:call:{syms["dl_publication_finish"]:#x}']
        if name=='memory-full':
            part=0x40170f60+6322                         # bank 1, working Part 2
            ids=[mods[k].menu.fx2_id for k in FULL[:4]]+[0]*4+[mods[k].menu.fx2_id for k in FULL[4:]]+[0]*4
            args+=['--step','-:poke:'+poke([(part+i,v,1) for i,v in enumerate(ids)]),
                   '--step','-:call:0x4004a8a4,1']
        else:
            fx2=name in REVERBS; fid=mods[name].menu.fx2_id
            chooser=(0x460d5ca8,0x40052474,0x400d6090) if fx2 else (0x460d5c94,0x400526e4,0x400d6060)
            args+=['--step','-:poke:'+poke([(0x80000000,track,1),(chooser[0],row(chooser[2],fid),4)]),
                   '--step',f'-:call:{chooser[1]:#x}']
        spans=';'.join(f'{syms[n]:#x},{8 if n in ("dl_residency_words","dl_pool_base","dl_pool_words") else 4}={d}/{n}.bin'
                       for n in NAMES)+f';0x80000ec4,16={d}/ids.bin;0x80000003,1={d}/part.bin'
        args+=['--live-script',str(d/'events.txt'),'--mem-dump',spans,'--dsp-peek','0:X:215,64;1:X:215,64']
        cmd+=['--scenario',' '.join(args)]
    with (OUT/'boot.log').open('w') as log:
        subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=1800)
    pkgs=dynamic_packages(); report=[]
    for name,track in cases:
        d=OUT/f'{name.replace(" ","_")}-t{track+1}'
        def vals(n):
            b=(d/f'{n}.bin').read_bytes(); return [int.from_bytes(b[i:i+4],'big') for i in range(0,len(b),4)]
        r={n:vals(n) for n in NAMES}; r['case']=f'{name} T{track+1}'; report.append(r)
        ids=(d/'ids.bin').read_bytes()
        assert r['dl_errors']==[0] and r['phase']==[0],r
        if name=='memory-full':
            assert r['dl_selection_refused']==[1] and (d/'part.bin').read_bytes()==b'\0',r
            assert r['dl_residency_words']==[0,0] and r['dl_modal_shown'][0]>=1,r
            print('PASS: memory-full Part refused whole, Part 1 kept, message raised',flush=True)
            continue
        fx2=name in REVERBS; fid=mods[name].menu.fx2_id; core=0 if track>=4 else 1
        slot=(8 if fx2 else 0)+track
        assert r['dl_selection_completed']==[1] and r['dl_selection_refused']==[0],r
        assert ids[slot]==fid,(r['case'],ids.hex())
        want=[0,0]; want[core]=len(pkgs[core,fid]['words'])
        assert r['dl_residency_words']==want,(r['case'],r['dl_residency_words'],want)
        m=re.search(rf'core {core} X:0x00215:((?: [0-9a-f]{{6}}){{64}})',(d/'port.log').read_text())
        assert m,(r['case'],'dispatch dump absent')
        dispatch=[int(w,16) for w in m[1].split()]
        base,words=r['dl_pool_base'][core],r['dl_pool_words'][core]
        init,proc=dispatch[fid],dispatch[32+fid]
        assert base+64<=init<base+words and base+64<=proc<base+words,(r['case'],'dispatch not in the arena',
                                                                    hex(init),hex(proc),hex(base))
        assert proc-init==pkgs[core,fid]['proc']-pkgs[core,fid]['init'],(r['case'],'entry offsets differ')
        print(f'PASS: {r["case"]:16s} {"FX2" if fx2 else "FX1"} loaded ({want[core]} words), bound at P:{init:#06x}',flush=True)
    (OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS: every stock DSP effect loads on selection; an over-capacity Part is refused whole')

if __name__=='__main__': main()
