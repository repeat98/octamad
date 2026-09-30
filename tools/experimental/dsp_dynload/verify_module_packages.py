"""Every module the build carries as a package runs from the loader's arena.

build_bus._package proves the package's words: relocated to four bases they
equal a fresh assembly there. What that proof cannot see is a module that
reaches stock code by an address that does not move -- a helper in the
effect block, which the loader reclaims. So, per payload, under dsp_host,
from the user's pristine 1.40C:
- the oracle: the module's words at the load address in stock memory;
- the loaded run: the same words (the relocated package) in memory whose
  whole effect block is `illegal` except the shared stock copies, exactly
  what the loader leaves (verify_stock_relocation);
- at the arena's lowest, a middle and its highest address, two sub-block
  lengths, the defaults and two other parameter sets: sample-identical, and
  sound from at least one set.
Run: REMIX=<name> python3 tools/experimental/dsp_dynload/verify_module_packages.py
Stock words stay in out/; nothing here is committed.
"""
from pathlib import Path
import math,os,struct,subprocess,sys
if not __package__:
    sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
    __package__='tools.experimental.dsp_dynload'
from .runtime_catalog import dynamic_layout,ROOT
from .stock_catalog import build as stock_build
from .verify_audio import append_p

ILLEGAL=0x000005

def main():
    if len(sys.argv)>1: os.environ['REMIX']=sys.argv[1]   # before build_bus reads it
    sys.path.insert(0,str(ROOT/'tools')); sys.path.insert(0,str(ROOT/'tools/build'))
    import toolpath  # noqa: F401
    import send_probe
    import build_bus
    from remix import stock
    from experimental.dsp_dynload import runtime_catalog as rc
    loadable=build_bus._loadables()
    if not loadable:
        print(f'PASS: remix {build_bus.REMIX.name!r} carries no module as a package'); return
    out=ROOT/'out/dsp-dynload/module-packages'; out.mkdir(parents=True,exist_ok=True)
    host=ROOT/'vendor/dsp56300/build/source/dsp_host/dsp_host'
    rows=stock_build(); n_ok=0
    def render(mem,init,proc,fx2,frames,blocks,src,params,dest):
        cmd=[str(host),'-mem',str(mem),'-init',f'{init:x}','-proc',f'{proc:x}',
             '-inst','1','-r7','2' if fx2 else '1','-alloc','1' if fx2 else '0','-inmask','1',
             '-audio','0','-frames',str(frames),'-blocks',str(blocks),'-in',str(src),
             '-out',str(dest),'-params',','.join(map(str,params))]
        try: run=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=120)
        except subprocess.TimeoutExpired: return None
        return dest.read_bytes() if run.returncode==0 and dest.exists() else None
    for core,payload in enumerate(('A','B')):
        spans=stock.p_spans(payload)
        start=min(b for b,n in spans.values()); end=max(b+n for b,n in spans.values())
        baseline=send_probe.dump_mem(ROOT/'out/raw/section_3_MAIN_OS.bin',out/f'{payload}.mem',payload)
        _h,copies,arena,_r=dynamic_layout(rows,core,start)
        loaded=append_p(baseline.read_bytes(),start,[ILLEGAL]*(end-start))
        for a,w in copies: loaded=append_p(loaded,a,w)
        for key in loadable:
            m=build_bus._MODS[key]; pkg=rc.MODULE_PACKAGES[core,m.menu.fx2_id]
            n=len(pkg['words']); fx2=True; heard=False
            for place in (arena,(arena+end-n)//2,end-n):
                words=list(pkg['words'])
                for i in pkg['relocations']: words[i]=(words[i]+place)&0xffffff
                ref=out/f'{payload}-{m.menu.fx2_id}-{place:x}-ref.mem'
                ref.write_bytes(append_p(baseline.read_bytes(),place,words))
                mem=out/f'{payload}-{m.menu.fx2_id}-{place:x}.mem'
                mem.write_bytes(append_p(loaded,place,words))
                for frames,blocks in ((1,128),(8,512)):
                    total=frames*blocks
                    samples=[round(0.3*8388607*(math.sin(2*math.pi*197*i/44100)+0.3*math.sin(2*math.pi*3209*i/44100)))
                             for i in range(total)]
                    src=out/'input.raw'; src.write_bytes(struct.pack(f'<{total}i',*samples))
                    for seed in (0,1,2):
                        params=[(v.default or 0) if seed==0 else ((i*23+seed*53)%(v.count or 128))
                                for i,v in enumerate(m.params)]
                        a=render(ref,place+pkg['init'],place+pkg['proc'],fx2,frames,blocks,src,params,out/'ref.raw')
                        b=render(mem,place+pkg['init'],place+pkg['proc'],fx2,frames,blocks,src,params,out/'load.raw')
                        assert a and len(a)==total*8,(payload,key,hex(place),'incomplete reference')
                        heard|=any(a)
                        assert a==b,(payload,key,hex(place),frames,seed,
                                     'differs once the effect block is reclaimed: it reaches stock code')
                        n_ok+=1
            # Some output from some parameter set: a module may be silent at
            # its defaults (CF METER prints two page-2 values, both 0 there).
            assert heard,(payload,key,'silent under every parameter set')
            print(f'PASS: {payload} {key:12s} {n:4d} words, 3 addresses x 6 renders identical '
                  f'with the effect block reclaimed',flush=True)
    print(f'PASS: {n_ok} renders; every package of remix {build_bus.REMIX.name!r} runs from the arena')

if __name__=='__main__': main()
