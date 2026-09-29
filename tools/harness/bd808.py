#!/usr/bin/env python3
"""DSP 808 reference, retrigger, automation and desk stability gates."""
import array,pathlib,subprocess,sys
import bd909
sys.path.insert(0,str(bd909.ROOT/'modules/analog-bassdrum'))
import dsp808,dsp909
OUT=bd909.ROOT/'out/bd808'
INIT=[64,80,80,64,64,0,0,100,127,64,64,0]
def build(*,output_trim=True):
    bd909.build_host();OUT.mkdir(parents=True,exist_ok=True)
    shared=dsp909.default_layout(0x1000);lay=dsp808.layout(0x3200)
    syms,_=dsp909.assemble(0x2000,{},OUT/'bd808.bin',dsp808.source(lay,shared,output_trim=output_trim))
    (OUT/'bd808.data').write_text(dsp909.data_lines(shared)+dsp808.data_lines(lay));return syms

def render(labels,blocks,tag):
    script=OUT/f'{tag}.script';script.write_text(''.join(' '.join(map(str,k))+f' {-1 if t is None else t}\n' for k,t in blocks))
    raw=OUT/f'{tag}.raw';meter=OUT/f'{tag}.meter'
    subprocess.run([str(bd909.HOST),'-code',str(OUT/'bd808.bin'),'-org','2000','-entry',f"{labels['zv01']:x}",'-init',f"{labels['zv02']:x}",'-data',str(OUT/'bd808.data'),'-script',str(script),'-out',str(raw),'-meter',str(meter)],check=True,capture_output=True)
    a=array.array('i');a.frombytes(raw.read_bytes());assert a[::2]==a[1::2],'stereo mismatch'
    peak=max(map(int,meter.read_text().split()))
    # Measured code-growth guard, NOT a hardware timing budget (CPU.md).
    assert peak<=3552,('808 instruction cost grew; re-benchmark full chains',peak)
    return [v/8388608 for v in a[::2]],peak
def reference(blocks):
    v=dsp808.Voice();return [x for k,t in blocks for x in v.block(k,t)]
def main():
    syms=build();worst=-999
    cases=[('default',{},(4410,)),('short',{1:0},(4410,)),('long',{1:127},(4410,)),('dark',{2:0},(4410,)),('bright',{2:127},(4410,)),('low',{0:0},(4410,)),('high',{0:127},(4410,)),('drive',{5:127},(4410,)),('loweq',{9:127},(4410,)),('higheq',{10:127},(4410,)),('sweep',{4:127},(4410,)),('nosweep',{4:0},(4410,)),('retrigger',{},(4410,4451,7001,12345))]
    for name,mods,at in cases:
        k=INIT.copy()
        for slot,value in mods.items():k[slot]=value
        blocks=bd909.hits(k,seconds=2,at=at);y,m=render(syms,blocks,name);ref=reference(blocks);err=bd909.err_db(y,ref);worst=max(worst,err)
        print(name,round(err,1),'dB',m,'instructions/block',flush=True)
        assert err < -45,(name,err)
        assert max(map(abs,y))<=1
        if '--wav' in sys.argv:bd909.wav(OUT/f'{name}.wav',y)
    for offset in range(16):
        blocks=bd909.hits(INIT,seconds=.08,at=(32+offset,));y,_=render(syms,blocks,f'offset{offset}');assert not any(y[:32+offset]);assert bd909.err_db(y,reference(blocks)) < -45
    for sat in (0,127):
        k=INIT.copy();k[1]=0;k[5]=sat
        blocks=bd909.hits(k,seconds=4,at=(0,));y,_=render(syms,blocks,f'tail{sat}')
        assert max(map(abs,y[-4410:]))<.0001,('tail/DC floor',sat)
    k=INIT.copy()
    blocks=bd909.hits(k,seconds=.5,at=(32,4001),changes={100:{0:127,2:0,5:127,8:1,9:0,10:127},300:{0:0,2:127,5:0,8:127,9:127,10:0}})
    y,_=render(syms,blocks,'automation');assert bd909.err_db(y,reference(blocks)) < -45
    print('PASS DSP 808; worst reference residual',worst)
if __name__=='__main__':main()
