#!/usr/bin/env python3
"""ColdFire-produced transfers executed by the real resident DSP loader."""
import array,json,pathlib,subprocess,sys,mmap,copy
ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'modules/analog-bassdrum'),str(ROOT/'tools/harness')]
import dynamic,dsp909,bd909
OUT=ROOT/'out/analog-bassdrum/dynamic'

def host():
    src=ROOT/'tools/harness/bd909_host/bd_loader_host.cpp'; exe=OUT/'loader_host'
    if not exe.exists() or exe.stat().st_mtime<src.stat().st_mtime:
        v=bd909.V
        subprocess.run(['c++','-O3','-DNDEBUG','-std=gnu++17','-DASMJIT_STATIC','-DDSP56300_DEBUGGER=0',f'-I{v}/source',f'-I{v}/source/asmjit/src',str(src),f'{v}/build/source/dsp56kEmu/libdsp56kEmu.a',f'{v}/build/source/dsp56kBase/libdsp56kBase.a',f'{v}/build/source/asmjit/libasmjit.a','-lpthread','-o',str(exe)],check=True)
    return exe

def main():
    exe=host();meta=json.loads((ROOT/'out/analog-bassdrum/image/dynamic.json').read_text())
    cases=json.loads((OUT/'records.json').read_text())
    data=OUT/'common.txt';tab=dsp909.tables()[0]
    data.write_text(''.join(f'{a:x} '+ ' '.join(f'{dsp909.q24(v):x}' for v in tab[k])+'\n' for k,a in dynamic.common_layout().items()))
    raw=(ROOT/'out/analog-bassdrum/image/library.bin').read_bytes();lib=[int.from_bytes(raw[i:i+4],'big') for i in range(0,len(raw),4)]
    for c,tag,org,cont in ((0,'A',0x1252,0x426),(1,'B',0x1012,0x221)):
        stream=[item for case in cases for item in case['streams'][c]]
        path=OUT/f'core{c}.packets';path.write_text(''.join(f'{t:x} '+' '.join(f'{w:x}' for w in words)+'\n' for t,words in stream))
        prefix=OUT/f'core{c}'
        subprocess.run([str(exe),str(ROOT/f'out/analog-bassdrum/image/kernel_{tag}.bin'),f'{org:x}',f'{cont:x}',str(data),str(path),str(prefix)],check=True)
        logs=prefix.with_suffix('.log').read_text().splitlines()
        active=0
        for i,((t,w),line) in enumerate(zip(stream,logs)):
            values=line.split();ready=int(values[6],16);seq=int(values[8],16)
            assert seq!=0xffffff,('DSP rejected packet',c,i,w[4:8],line)
            if w[4]==3:active=0
            elif w[4]==4:active=1
            assert ready==active,('activation barrier',c,i,w[4:8],line)
        # No packet may write outside the allocated overlay or shared tables.
        with prefix.with_suffix('.dump').open('rb') as file:
            mem=mmap.mmap(file.fileno(),0,access=mmap.ACCESS_READ)
            stride=0x8000*4; base=meta['kernels'][c]['base'];end=meta['kernels'][c]['end']
            for i in range(len(stream)):
                start=i*stride
                assert mem[start:start+base*4]==mem[:base*4], ('resident P modified',c,i)
                assert mem[start+end*4:start+0x4000*4]==mem[end*4:0x4000*4], ('stock P modified',c,i)
                common=0x4000*4+dynamic.COMMON_BASE*4;limit=0x4000*4+dynamic.DATA_BASE*4
                assert mem[start+common:start+limit]==mem[common:limit], ('shared tables modified',c,i)
            index=-1
            for case in cases:
                index+=len(case['streams'][c]);start=index*stride
                def read(space,addr,n):
                    blob=mem[start+(space*0x4000+addr)*4:start+(space*0x4000+addr+n)*4]
                    words=array.array('I');words.frombytes(blob);return list(words)
                pc=base;xc=dynamic.DATA_BASE;entries={}
                models=case['models'][(0 if c else 4):(4 if c else 8)]
                for model in dict.fromkeys(models):
                    e=lib[16+12*model:28+12*model];pn,xn=e[1:3]
                    code=lib[e[3+c]:e[3+c]+pn]
                    for at in lib[e[6]:e[6]+e[7]]:code[at]=(code[at]+pc-dynamic.P_ORG)&0xffffff
                    for at in lib[e[8]:e[8]+e[9]]:code[at]=(code[at]+xc-dynamic.X_ORG)&0xffffff
                    assert read(0,pc,pn)==code, ('relocated P bytes',c,model)
                    assert read(1,xc,xn)==lib[e[5]:e[5]+xn], ('table bytes',c,model)
                    entries[model]=pc+e[11];pc+=pn;xc+=xn
                assert read(1,dynamic.META,4)==[entries[m] for m in models], ('shared dispatch',c)
            mem.close()
        print('PASS core',c,len(stream),'packets; barriers, exact relocated code/tables, protected memory, shared dispatch')
        for failure in ('count','sequence','program_bounds','in_range_destination','data_corruption','checksum'):
            broken=copy.deepcopy(cases[0]['streams'][c])
            if failure=='count':broken[1][1][5]=17
            if failure=='sequence':broken[1][1][7]+=1
            if failure=='program_bounds':broken[1][1][6]=org
            if failure=='in_range_destination':broken[1][1][6]+=1
            if failure=='data_corruption':broken[1][1][21]^=1
            if failure=='checksum':next(w for t,w in broken if w[4]==4)[21]^=1
            path.write_text(''.join(f'{t:x} '+' '.join(f'{w:x}' for w in words)+'\n' for t,words in broken))
            subprocess.run([str(exe),str(ROOT/f'out/analog-bassdrum/image/kernel_{tag}.bin'),f'{org:x}',f'{cont:x}',str(data),str(path),str(prefix)+'-bad'],check=True,capture_output=True)
            last=pathlib.Path(str(prefix)+'-bad.log').read_text().splitlines()[-1].split()
            assert int(last[6],16)==0 and int(last[8],16)==0xffffff, (failure,c,last)
        print('PASS core',c,'rejects count, sequence, bounds, payload and commit corruption')
if __name__=='__main__':main()
