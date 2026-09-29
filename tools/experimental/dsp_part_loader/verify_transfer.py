"""Exercise the real firmware DMA controller and both DSP staging receivers.

Build REMIX=dsp-loader-transfer first. Supply DL_CARD or OT_PROJECT; generated
cards, firmware snapshots, dumps and logs stay in ignored out/. No hardware
qualification or effect-switching claim follows from this transport gate.
"""
from pathlib import Path
import json
import os
import re
import shutil
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'out/dsp-part-loader/transfer'

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    card=os.environ.get('DL_CARD')
    if not card:
        project=os.environ.get('OT_PROJECT')
        if not project:
            print('[SKIP] DSP transfer: supply OT_PROJECT or DL_CARD')
            return
        card=str(OUT/'card.img')
        subprocess.run([sys.executable,'tools/emu/ot_emu/stage_card.py',project,
                        'OCTABAM','RIG','--tree',str(OUT/'tree'),'--out',card],
                       cwd=ROOT,check=True)
    symbols={p[2]:int(p[0],16) for p in (l.split() for l in subprocess.check_output(
        ['m68k-elf-nm',str(ROOT/'out/platform/runtime/runtime.elf')],text=True).splitlines()) if len(p)==3}
    (OUT/'symbols.json').write_text(json.dumps(symbols,indent=2))
    # Pin the actual build's hook targets and derive the preceding, ledger-owned
    # table. No guessed spare DSP addresses: ptable belongs to this module.
    sys.path.insert(0,str(ROOT/'tools'))
    import toolpath  # noqa: F401
    import send_probe
    image=OUT/'image.bin'
    shutil.copyfile(ROOT/'out/mainos_bus.bin',image)
    pools=[]
    for core,payload,hook in ((0,'A',0x8e),(1,'B',0x76)):
        import struct
        mem=OUT/f'{payload}.mem'
        send_probe.dump_mem(image,mem,payload)
        blob=mem.read_bytes(); pos=0; entry=None
        while pos+9<=len(blob):
            sp,base,count=struct.unpack_from('<BII',blob,pos); pos+=9
            if sp==255: break
            if sp==0 and base<=hook and hook+1<base+count:
                opcode,entry=struct.unpack_from('<II',blob,pos+4*(hook-base))
                assert opcode==0x0bf080, 'built DSP hook is not the loader jsr'
            pos+=4*count
        assert entry is not None
        pools.append(entry-128)
    names={'dl_frames':4,'dl_accepted':8,'dl_rejected':8,'dl_errors':4,
           'dl_phase':4,'dl_modal_shown':4,'dl_rx':128,'dl_tx':256}
    spans=';'.join(f'{symbols[n]:#x},{size}={OUT}/{n}.bin' for n,size in names.items())
    (OUT/'events.txt').write_text('250 quit\n')
    poke=';'.join(f'{symbols[name]+3:#x}={value}' for name,value in
                  [('dl_request_probe',1),('dl_request_stage',1),('dl_modal_pending',2)])
    cmd=[str(ROOT/'out/emu/ot_emu'),'--image',str(image),'--card',card,
         '--set','OCTABAM','--project','RIG','--load-ms','20000','--frame','--dsp',
         '--poke',poke,'--live-script',str(OUT/'events.txt'),'--mem-dump',spans,
         '--dsp-peek',';'.join(f'{c}:P:{base:x},128' for c,base in enumerate(pools)),
         '--lcd',str(OUT/'lcd.bin')]
    with (OUT/'port.log').open('w') as log:
        subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=360)
    def values(name):
        b=(OUT/f'{name}.bin').read_bytes()
        return [int.from_bytes(b[i:i+4],'big') for i in range(0,len(b),4)]
    report={n:values(n) for n in names if n not in ('dl_rx','dl_tx')}
    report['staging_bases']=pools
    (OUT/'report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
    assert report['dl_accepted']==[2,2], 'both cores must acknowledge probe and stage'
    assert report['dl_errors']==[0] and report['dl_rejected']==[0,0]
    assert report['dl_frames'][0]>100, 'frame chain did not continue'
    assert report['dl_modal_shown']==[1], 'deferred UI message did not run'
    log=(OUT/'port.log').read_text()
    assert 'unknown line' not in log and 'ended on quit' in log
    for core,base in enumerate(pools):
        match=re.search(rf'^\s+core {core} P:0x{base:05x}:((?: [0-9a-f]{{6}}){{128}})$',log,re.M)
        assert match, f'core {core}: staging dump missing'
        words=[int(w,16) for w in match[1].split()]
        expected=[(0x123456+0x513579*i+2+core)&0xffffff for i in range(24)]+[0]*104
        assert words==expected, f'core {core}: staged P words or untouched guard differ: {words[:24]}'
    print('PASS: firmware delivery, both DSP acknowledgements, exact bounded P staging, UI task and continued frames')
if __name__=='__main__': main()
