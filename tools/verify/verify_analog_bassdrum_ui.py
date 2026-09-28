#!/usr/bin/env python3
"""Choose Analog Bassdrum and edit MODEL using actual stock panel events."""
import json,os,pathlib,shutil,subprocess,sys
ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/harness'))
def key(code, gap=.6, hold=.6):
    return [(gap, f"key {code:#x} down"), (hold, f"key {code:#x} up")]
OUT=ROOT/'out/analog-bassdrum/ui-gate'
def main():
    src=os.environ.get('OT_PROJECT')
    if not src:
        print('[SKIP] Analog Bassdrum panel: set OT_PROJECT to a stock project fixture');return
    OUT.mkdir(parents=True,exist_ok=True)
    card=OUT/'card.img'
    subprocess.run([sys.executable,str(ROOT/'tools/emu/ot_emu/stage_card.py'),src,'OCTABAM','RIG','--tree',str(OUT/'tree'),'--out',str(card)],check=True,cwd=ROOT)
    image=OUT/'image.bin';shutil.copy2(os.environ.get('AB_IMAGE',ROOT/'out/mainos_bus.bin'),image)
    sym={l.split()[-1]:int(l.split()[0],16) for l in subprocess.check_output(['m68k-elf-nm',str(ROOT/'out/platform/runtime/runtime.elf')],text=True).splitlines() if len(l.split())==3}
    if os.environ.get('AB_SYMBOLS'): sym=json.loads(pathlib.Path(os.environ['AB_SYMBOLS']).read_text())
    spans=f'0x40170f60,6322={OUT}/part.bin;{sym["desc"]:#x},916={OUT}/desc.bin;0x400d5f4c,4={OUT}/page.bin;0x460e70e0,4={OUT}/pool.bin;0x400bb7d0,4={OUT}/setup.bin'
    cmd=[os.environ.get('AB_EMU',str(ROOT/'out/emu/ot_emu')),'--image',str(image),'--card',str(card),'--set','OCTABAM','--project','RIG','--load-ms','20000','--dsp','--mem-dump',spans]
    cmd += ["--lcd", str(OUT/"lcd.bin")]
    # T1 -> SRC SETUP -> bottom row -> YES; SETUP stays open for MODEL.
    script=key(0x10)+[(.6,'key 0x2d down'),(.3,'key 0x22 down'),(.3,'key 0x22 up'),(.3,'key 0x2d up')]
    for _ in range(6):script+=key(0x20,.25,.25)
    script+=key(0x31)
    script+=[(.8,'enc 0 16'),(.8,'enc 2 -4')]
    # Close setup, then double-tap T1 with a 210 ms down-to-down gap.
    script+=key(0x32)+[(.6,'key 0x10 down'),(.06,'key 0x10 up'),
                      (.15,'key 0x10 down'),(.06,'key 0x10 up'),(.8,'quit')]
    elapsed=0; events=[]
    for delay,event in script:
        elapsed+=round(delay*1000)
        events.append(f'{elapsed} {event}\n')
    eventfile=OUT/'events.txt';eventfile.write_text(''.join(events))
    with (OUT/'port.log').open('w') as log:
        subprocess.run(cmd+['--live-script',str(eventfile)],cwd=ROOT,
                       stdout=log,stderr=subprocess.STDOUT,timeout=600,check=True)
    assert int.from_bytes((OUT/'pool.bin').read_bytes(),'big')==0, 'sample pool opened'
    assert int.from_bytes((OUT/'setup.bin').read_bytes(),'big')!=0, 'source setup did not open'
    log=(OUT/'port.log').read_text();assert 'ILLEGAL' not in log and 'ended on quit' in log
    part=(OUT/'part.bin').read_bytes();desc=(OUT/'desc.bin').read_bytes()
    assert part[0x22]==1 and part[60:63]==b'AB\x01',('selection',part[0x22],part[60:63])
    assert 64 < part[0x1da+8] < 127, ('LPF encoder',part[0x1da+8])
    assert part[0x1da+6]==1,('MODEL',part[0x1da+6])
    assert list(part[48:54])==[64,80,80,64,64,0],list(part[48:54])
    assert desc[0x4e+6*6:0x4e+6*6+6]==b'MODEL\x00'
    assert int.from_bytes(desc[0xd2+4*6:0xd2+4*7],'big')==2
    assert int.from_bytes((OUT/'page.bin').read_bytes(),'big')==sym['desc']+458+0x38, 'MODEL page did not change'
    for model in (0,1):
        d=desc[model*458:(model+1)*458]
        assert d[0x4e+2*6:0x4e+2*6+6]==(b'TONE\0\0' if model==0 else b'TUNE\0\0')
        assert d[0x4e+8*6:0x4e+8*6+6]==b'LPF\0\0\0'
        assert int.from_bytes(d[0x1c2:0x1c6],'big')==0x111
        assert d[0x96+8]==127
        assert d[0x4e+5*6:0x4e+6*6] == b'SAT\0\0\0'
        assert d[0x96+9:0x96+11] == bytes([64,64])
        assert int.from_bytes(d[0x132+4*6:0x136+4*6],"big")==0x400477d4
        assert int.from_bytes(d[0x162+4*6:0x166+4*6],"big")==0
        if model:
            assert d[0x4e+9*6:0x4e+11*6] == b'LOW\0\0\0HIGH\0\0'
    print('PASS chooser: Analog Bassdrum, defaults, MODEL=909 and LPF edit through stock encoders; double-track opens source setup')
if __name__=='__main__':main()
