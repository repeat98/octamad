"""Run the real firmware DMA extension and both DSP mailbox receivers."""
from pathlib import Path
import json
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'out/dsp-part-loader/transfer'
OUT.mkdir(parents=True,exist_ok=True)
symbols={p[2]:int(p[0],16) for p in (l.split() for l in subprocess.check_output(
    ['m68k-elf-nm',str(ROOT/'out/platform/runtime/runtime.elf')],text=True).splitlines()) if len(p)==3}
(OUT/'symbols.json').write_text(json.dumps(symbols,indent=2))
names={'dl_frames':4,'dl_accepted':8,'dl_rejected':8,'dl_errors':4,'dl_phase':4,
       'dl_modal_shown':4,'dl_rx':128,'dl_tx':256}
spans=';'.join(f'{symbols[n]:#x},{size}={OUT}/{n}.bin' for n,size in names.items())
(OUT/'events.txt').write_text('250 quit\n')
cmd=[str(ROOT/'out/emu/ot_emu'),'--image',str(ROOT/'out/mainos_bus.bin'),
     '--card',str(ROOT/'out/analog-bassdrum/ui-gate/card.img'),'--set','OCTABAM','--project','RIG',
     '--load-ms','20000','--frame','--dsp','--poke',f'{symbols["dl_request_probe"]+3:#x}=1','--live-script',str(OUT/'events.txt'),
     '--mem-dump',spans,'--dsp-peek','0:X:2360,4;0:X:4360,4;1:X:2360,4;1:X:4360,4',
     '--lcd',str(OUT/'lcd.bin')]
with (OUT/'port.log').open('w') as log:
    subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=240)
def values(name):
    b=(OUT/f'{name}.bin').read_bytes()
    return [int.from_bytes(b[i:i+4],'big') for i in range(0,len(b),4)]
report={n:values(n) for n in names if n not in ('dl_rx','dl_tx')}
(OUT/'report.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
assert report['dl_accepted']==[1,1], 'each core must acknowledge its actual transferred packet'
assert report['dl_errors']==[0], 'no rejected/missing packets'
assert report['dl_frames'][0]>100, 'frame chain did not continue'
print('PASS: both cores received and acknowledged the native firmware DMA packets')
