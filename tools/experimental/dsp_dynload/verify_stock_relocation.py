"""Every stock DSP effect runs sample-identically from any load address.

The plan for an image with no stock effect built in: the whole effect block
(A P:0x7d1..0x1fdf, B 0x240 lower) is reclaimed. Only shared stock routines
stay resident, as copies at the block's start (runtime_catalog.SHARED): the
filter library at FILTER's tail (296 words, called with one-word jsr, so below
P:0x1000), and the two routines the reverbs share (35 + 93 words). Every
effect, FILTER included, is a movable package loaded into the arena above.

Under dsp_host, per payload, from the user's pristine 1.40C:
- the loaded run's memory has the whole effect block filled with `illegal`
  before the shared copies and the package are written, so any jump into
  reclaimed code shows (it hangs or changes the output);
- each effect at the lowest, a middle and the highest arena address, three
  parameter sets, three sub-block lengths, against the native original.
  Parameter set 0 is the stock defaults; every reverb defaults to MIX 0 (dry),
  which never reaches its wet path, so sets 1 and 2 carry that coverage;
- negative control: DARK without the shared copies, wet, must not match.
Stock words stay in out/; nothing here is committed.
"""
from pathlib import Path
import json,math,struct,subprocess,sys
if not __package__:
    sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
    __package__='tools.experimental.dsp_dynload'
from .runtime_catalog import dynamic_layout,dynamic_package,ROOT
from .stock_catalog import build as stock_build
from .verify_audio import append_p

ILLEGAL=0x000005
RESERVED=321+993+64          # loader receiver, Analog BD, the arena's table

def main():
    sys.path.insert(0,str(ROOT/'tools')); import toolpath  # noqa: F401
    import send_probe
    from remix import registry, stock
    out=ROOT/'out/dsp-dynload/stock-relocation'; out.mkdir(parents=True,exist_ok=True)
    host=ROOT/'vendor/dsp56300/build/source/dsp_host/dsp_host'
    rows=stock_build(); mods=registry.modules(); report=[]
    def render(mem,init,proc,fx2,frames,blocks,src,params,dest,timeout=120):
        cmd=[str(host),'-mem',str(mem),'-init',f'{init:x}','-proc',f'{proc:x}',
             '-inst','1','-r7','2' if fx2 else '1','-alloc','1' if fx2 else '0','-inmask','1',
             '-audio','0','-frames',str(frames),'-blocks',str(blocks),'-in',str(src),
             '-out',str(dest),'-params',','.join(map(str,params))]
        try: run=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=timeout)
        except subprocess.TimeoutExpired: return None
        return dest.read_bytes() if run.returncode==0 and dest.exists() else None
    for core,payload in enumerate(('A','B')):
        spans=stock.p_spans(payload)
        start=min(b for b,n in spans.values()); end=max(b+n for b,n in spans.values())
        baseline=send_probe.dump_mem(ROOT/'out/raw/section_3_MAIN_OS.bin',out/f'{payload}.mem',payload)
        byname={r['key']:r for r in rows if r['core']==core}
        helpers,copies,arena,reclaimed=dynamic_layout(rows,core,start)
        arena+=RESERVED
        fill=append_p(baseline.read_bytes(),start,[ILLEGAL]*(end-start))
        with_helpers=fill
        for a,w in copies: with_helpers=append_p(with_helpers,a,w)
        for name,row in byname.items():
            if name=='DELAY': continue
            pkg=dynamic_package(row,reclaimed,helpers)
            fx2=name.endswith('REV')
            original=send_probe.entry_points(baseline,row['fx_id'])
            n=len(pkg['words'])
            for place in (arena,(arena+end-n)//2,end-n):
                words=list(pkg['words'])
                for r in pkg['relocations']:
                    i=r&0x7fff; words[i]=(words[i]-place if r&0x8000 else words[i]+place)&0xffffff
                mem=out/f'{payload}-{row["fx_id"]}-{place:x}.mem'
                mem.write_bytes(append_p(with_helpers,place,words))
                for frames,blocks in ((1,128),(7,512),(16,2048 if fx2 else 256)):
                    total=frames*blocks
                    samples=[round(0.3*8388607*(math.sin(2*math.pi*197*i/44100)+0.3*math.sin(2*math.pi*3209*i/44100)))
                             for i in range(total)]
                    src=out/'input.raw'; src.write_bytes(struct.pack(f'<{total}i',*samples))
                    for seed in (0,1,2):
                        params=[(v.default or 0) if seed==0 else ((i*23+seed*53)%(v.count or 128))
                                for i,v in enumerate(mods[name].params)]
                        a=render(baseline,*original,fx2,frames,blocks,src,params,out/'orig.raw')
                        b=render(mem,place+pkg['init'],place+pkg['proc'],fx2,frames,blocks,src,params,out/'load.raw')
                        assert a and len(a)==total*8 and any(a),(payload,name,'silent/incomplete original')
                        assert a==b,(payload,name,hex(place),frames,seed,'loaded copy differs from stock')
                        report.append(dict(payload=payload,effect=name,address=place,frames=frames,seed=seed))
            print(f'PASS: {payload} {name:12s} {n:4d} words, 3 addresses x 9 renders identical to stock',flush=True)
        # Negative control: DARK without its helper copies.
        row=byname['DARK REV']; pkg=dynamic_package(row,reclaimed,helpers)
        words=list(pkg['words'])
        for r in pkg['relocations']:
            i=r&0x7fff; words[i]=(words[i]-arena if r&0x8000 else words[i]+arena)&0xffffff
        bad=out/f'{payload}-dark-nohelpers.mem'; bad.write_bytes(append_p(fill,arena,words))
        total=16*2048; src=out/'input.raw'
        src.write_bytes(struct.pack(f'<{total}i',*[round(0.3*8388607*math.sin(2*math.pi*197*i/44100)) for i in range(total)]))
        # Not the defaults: every stock reverb defaults to MIX 0, fully dry,
        # which never reaches the wet path or its helpers (measured: DARK
        # without its helper copies matched stock there, and differed at MIX
        # 40 and 93). Parameter sets 1 and 2 above are wet; set 0 is blind.
        params=[(i*23+53)%(v.count or 128) for i,v in enumerate(mods['DARK REV'].params)]
        a=render(baseline,*send_probe.entry_points(baseline,row['fx_id']),True,16,2048,src,params,out/'orig.raw')
        b=render(bad,arena+pkg['init'],arena+pkg['proc'],True,16,2048,src,params,out/'load.raw',timeout=60)
        assert a!=b,(payload,'negative control: DARK matched without its helpers -- the fill is not seen')
        print(f'PASS: {payload} negative control -- DARK without helper copies does not match',flush=True)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'PASS: {len(report)} renders; all 13 stock DSP effects per core load anywhere in the arena')

if __name__=='__main__': main()
