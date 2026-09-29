#!/usr/bin/env python3
"""Relocated engine packages and resident desk must preserve exact output/state."""
import array,json,pathlib,subprocess,sys
import bd808,bd909
from verify_analog_bd_exact import cases
ROOT=bd909.ROOT
sys.path.insert(0,str(ROOT/'modules/analog-bassdrum'))
import dynamic,dsp909
OUT=ROOT/'out/analog-bassdrum/dynamic/audio'

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    meta=json.loads((ROOT/'out/analog-bassdrum/image/dynamic.json').read_text())
    raw=(ROOT/'out/analog-bassdrum/image/library.bin').read_bytes()
    lib=[int.from_bytes(raw[i:i+4],'big') for i in range(0,len(raw),4)]
    bd909.build_host()
    for model,module,prefix in ((0,bd808,'zv'),(1,bd909,'zq')):
        symbols=module.build();e=lib[16+12*model:28+12*model]
        for c,tag in ((0,'A'),(1,'B')):
            # Opposite ends of the pool cover relocation in both directions.
            pc=meta['kernels'][c]['base'] if c==0 else meta['kernels'][c]['end']-e[1]
            xc=dynamic.DATA_BASE if c==0 else dynamic.VOICE_BASE-e[2]
            code=lib[e[3+c]:e[3+c]+e[1]]
            for at in lib[e[6]:e[6]+e[7]]:code[at]=(code[at]+pc-dynamic.P_ORG)&0xffffff
            for at in lib[e[8]:e[8]+e[9]]:code[at]=(code[at]+xc-dynamic.X_ORG)&0xffffff
            codepath=OUT/f'{model}-{c}.bin';codepath.write_bytes(b''.join(v.to_bytes(3,'little') for v in code))
            kernel=(ROOT/f'out/analog-bassdrum/image/kernel_{tag}.bin').read_bytes()
            kw=[int.from_bytes(kernel[i:i+3],'little') for i in range(0,len(kernel),3)]
            line=lambda space,addr,words:f'{space} {addr:x} '+' '.join(f'{v:x}' for v in words)+'\n'
            data=line('P',0x1252 if c==0 else 0x1012,kw)+line('X',xc,lib[e[5]:e[5]+e[2]])+line('X',0x200,dynamic.initial(model))
            tables=dsp909.tables()[0]
            for k,addr in dynamic.common_layout().items():data+=line('X',addr,[dsp909.q24(v) for v in tables[k]])
            datapath=OUT/f'{model}-{c}.data';datapath.write_text(data)
            for label,blocks in cases(module):
                stem=OUT/f'{model}-{c}-{label}';script=stem.with_suffix('.script')
                script.write_text(''.join(' '.join(map(str,k))+f' {t}\n' for k,t in blocks))
                common=['-script',str(script)]
                for kind,args in [('old',['-code',str(module.OUT/f'bd{808 if model==0 else 909}.bin'),'-org','2000','-entry',f'{symbols[prefix+"01"]:x}','-init',f'{symbols[prefix+"02"]:x}','-data',str(module.OUT/f'bd{808 if model==0 else 909}.data')]),('new',['-code',str(codepath),'-org',f'{pc:x}','-entry',f'{pc+e[11]:x}','-data',str(datapath)])]:
                    subprocess.run([str(bd909.HOST),*args,*common,'-out',str(stem)+f'.{kind}.raw','-state',str(stem)+f'.{kind}.state'],check=True,capture_output=True)
                for ext in ('raw','state'):
                    assert pathlib.Path(str(stem)+f'.old.{ext}').read_bytes()==pathlib.Path(str(stem)+f'.new.{ext}').read_bytes(),(model,c,label,ext)
                print('PASS relocated',model,'core',c,label,len(blocks)*16,'frames: exact audio and state',flush=True)
if __name__=='__main__':main()
