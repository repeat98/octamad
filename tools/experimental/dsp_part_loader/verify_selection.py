"""Port-test stock selector guards with an explicitly diagnostic backend.

This proves before-write refusal and context-safe retry, not resource allocation.
All scenarios fork one loaded fixture and retain the stock UI/setter routines.
"""
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'out/dsp-part-loader/selection'

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    card=os.environ.get('DL_CARD')
    if not card:
        source=os.environ.get('OT_PROJECT')
        if not source:
            print('[SKIP] DSP selection: supply OT_PROJECT or DL_CARD with empty FX fixture'); return
        sys.path.insert(0,str(ROOT/'tools/harness'))
        from ab_fixture import prepare
        fixture=prepare(source,OUT/'fixture')
        card=str(OUT/'card.img')
        subprocess.run([sys.executable,'tools/emu/ot_emu/stage_card.py',str(fixture),
                        'OCTABAM','RIG','--tree',str(OUT/'tree'),'--out',card],cwd=ROOT,check=True)
    sym={p[2]:int(p[0],16) for p in (l.split() for l in subprocess.check_output(
        ['m68k-elf-nm',str(ROOT/'out/platform/runtime/runtime.elf')],text=True).splitlines()) if len(p)==3}
    image=OUT/'image.bin'; shutil.copyfile(ROOT/'out/mainos_bus.bin',image)
    raw=image.read_bytes()
    def rd32(addr): return int.from_bytes(raw[addr-0x40000400:addr-0x40000400+4],'big')
    def row(slot,id):
        for i in range(32):
            ptr=rd32((0x400d6060,0x400d6090)[slot]+4*i)
            if not ptr: break
            if rd32(ptr)==id: return i
        raise ValueError('effect absent from built chooser')
    def pokes(values):
        return ';'.join(f'{a+i:#x}={b}' for a,v,n in values
                        for i,b in enumerate((v&((1<<(8*n))-1)).to_bytes(n,'big')))
    def ranges(directory,tag):
        return ';'.join(f'{a:#x},{n}={directory}/{tag}-{name}.bin' for name,a,n in
                       [('part',0x40170f60,6322),('shadow',0x100a4ece,6322),
                        ('ids',0x80000ec4,16),('lanes',0x80000810,576),
                        ('link',0x400eb037,1),('shadowlink',0x1001efa5,1),('active',0x80000003,1)])
    cases=[('refuse-fx1',0,0,-1,False,False),('refuse-fx2',1,4,-1,False,False),
           ('ready-fx2',1,4,1,False,True),('wait-fx1',0,0,0,False,True),
           ('cancel-fx2',1,4,0,True,False),
           ('refuse-part',2,0,-1,False,False),('ready-part',2,0,1,False,True),
           ('wait-part',2,0,0,False,True),('cancel-part',2,0,0,True,False)]
    cmd=[str(ROOT/'out/emu/ot_emu'),'--image',str(image),'--card',card,
         '--set','OCTABAM','--project','RIG','--load-ms','20000','--frame','--dsp']
    for name,slot,track,policy,cancel,accepted in cases:
        directory=OUT/name; directory.mkdir(exist_ok=True)
        event=directory/'events.txt'; event.write_text('250 quit\n')
        cursor=(0x460d5c94,0x460d5ca8,0x460d5c94)[slot]
        setup=pokes([(0x80000000,track,1),(0x80000003,0,1),(cursor,row(slot if slot<2 else 0,12),4),
                     (sym['dl_probe_selection_result'],policy,4)])
        args=[str(directory/'port.log'),'--step','-:poke:'+setup,
              '--step','-:dump:'+ranges(directory,'before'),
              '--step',f'-:call:{(0x400526e4,0x40052474,0x4004a8a4)[slot]:#x}'+(',1' if slot==2 else ''),
              '--step','-:dump:'+ranges(directory,'immediate')]
        if policy==0:
            updates=[(sym['dl_probe_selection_result'],1,4)]
            if cancel: updates.append((cursor,row(slot,4),4) if slot<2 else (0x80000004,1,1))
            args+=['--step','-:poke:'+pokes(updates)]
        counters=';'.join(f'{sym[n]:#x},4={directory}/{n}.bin' for n in
                         ('dl_selection_completed','dl_selection_cancelled','dl_selection_refused'))
        args+=['--live-script',str(event),'--mem-dump',ranges(directory,'final')+';'+counters,
               '--lcd',str(directory/'lcd.bin')]
        if any(' ' in a for a in args): raise ValueError('scenario parser requires paths without spaces')
        cmd+=['--scenario',' '.join(args)]
    with (OUT/'boot.log').open('w') as log:
        subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=420)
    results=[]
    for name,slot,track,policy,cancel,accepted in cases:
        directory=OUT/name
        before=(directory/'before-part.bin').read_bytes()
        assert before[:16]==bytes(16), 'fixture must start with FX NONE on every track'
        for region in ('part','shadow','ids','lanes','link','shadowlink','active'):
            initial=(directory/f'before-{region}.bin').read_bytes()
            if policy!=1:
                assert (directory/f'immediate-{region}.bin').read_bytes()==initial, (name,region,'mutated before ready')
            if not accepted:
                assert (directory/f'final-{region}.bin').read_bytes()==initial, (name,region,'refusal/cancel mutated state')
        if accepted and slot<2:
            for region in ('part','shadow','ids'):
                data=(directory/f'final-{region}.bin').read_bytes()
                assert data[slot*8+track]==12, (name,region,'stock setter did not apply')
        if accepted and slot==2:
            for region in ('link','shadowlink','active'):
                assert (directory/f'final-{region}.bin').read_bytes()==bytes([1]), (name,region,'Part did not change')
        def count(n): return int.from_bytes((directory/f'dl_selection_{n}.bin').read_bytes(),'big')
        assert count('completed')==int(accepted)
        assert count('cancelled')==int(cancel)
        assert count('refused')==int(policy<0)
        text=(directory/'port.log').read_text()
        assert 'ended on quit' in text and 'ILLEGAL' not in text
        results.append(dict(case=name,accepted=accepted,passed=True))
    (OUT/'report.json').write_text(json.dumps(results,indent=2)+'\n')
    print('PASS: both stock FX setters and manual Part selection, exact Part/shadow/live preservation on refusal, pending replay and cancellation')
if __name__=='__main__': main()
