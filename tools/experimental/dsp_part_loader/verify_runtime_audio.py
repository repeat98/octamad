"""Exact audio oracle for every real runtime relocation candidate, both cores."""
from pathlib import Path
import json,math,os,struct,subprocess,sys
if not __package__:
    sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
    __package__='tools.experimental.dsp_part_loader'
from .runtime_catalog import packages,ROOT
from .verify_audio import append_p

def main():
    sys.path.insert(0,str(ROOT/'tools')); import toolpath
    import send_probe
    from remix import registry
    out=ROOT/'out/dsp-part-loader/runtime-audio'; out.mkdir(parents=True,exist_ok=True)
    host=ROOT/'vendor/dsp56300/build/source/dsp_host/dsp_host'
    candidates=packages(); report=[]
    for core,payload in enumerate(('A','B')):
        baseline=out/f'{payload}.mem'; send_probe.dump_mem(ROOT/'out/mainos_bus.bin',baseline,payload)
        for id,name in ((12,'EQUALIZER'),(16,'PHASER'),(24,'COMPRESSOR'),(28,'CHARACTER')):
            p=candidates[core,id]; base=(0x1000 if core==0 else 0xdc0)+64
            words=list(p['words'])
            for offset in p['relocations']:
                i=offset&0x7fff
                words[i]=(words[i]-base if offset&0x8000 else words[i]+base)&0xffffff
            relocated=out/f'{payload}-{id}.mem'; relocated.write_bytes(append_p(baseline.read_bytes(),base,words))
            original=send_probe.entry_points(baseline,id)
            mod=registry.modules()[name]
            for frames in (1,7,16):
                blocks=128; n=frames*blocks
                samples=[round(0.3*8388607*(math.sin(2*math.pi*197*i/44100)+0.3*math.sin(2*math.pi*3209*i/44100))) for i in range(n)]
                src=out/'input.raw'; src.write_bytes(struct.pack(f'<{n}i',*samples))
                for seed in (0,1,2):
                    params=[(v.default or 0) if seed==0 else ((i*23+seed*53) % (v.count or 128)) for i,v in enumerate(mod.params)]
                    got=[]
                    for label,mem,init,proc in [('original',baseline,*original),('loaded',relocated,base+p['init'],base+p['proc'])]:
                        dest=out/f'{payload}-{id}-{frames}-{seed}-{label}.raw'
                        cmd=[str(host),'-mem',str(mem),'-init',f'{init:x}','-proc',f'{proc:x}',
                             '-inst','1','-r7','1','-alloc','0','-inmask','1','-audio','0','-frames',str(frames),
                             '-blocks',str(blocks),'-in',str(src),'-out',str(dest),'-params',','.join(map(str,params))]
                        run=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=60)
                        if run.returncode: raise RuntimeError(run.stdout+run.stderr)
                        data=dest.read_bytes(); assert len(data)==n*8 and any(data),(name,payload,'silent/incomplete')
                        got.append(data)
                    assert got[0]==got[1],(name,payload,frames,seed,'relocation changed samples')
                    report.append(dict(module=name,core=core,frames=frames,seed=seed,equal=True))
            print(f'PASS: {name}/{payload}, nine exact stereo comparisons',flush=True)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'PASS: {len(report)} comparisons, three sub-block lengths and parameter sets on both cores')
if __name__=='__main__': main()
