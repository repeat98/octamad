"""Switching effects and Parts while playing: no dropout, no burst, like stock 1.40C.

Under the port, the dynamic image (no stock DSP effect built in; each loads on
demand) against the user's pristine 1.40C, the same fixture as
verify_stock_load (eight THRU tracks on tones, every Part carrying the same
eleven stock effects; DSP RAM filled with garbage at boot) and the same
script, while the sequencer plays:

  frame 2000   T1 FX1  EQUALIZER -> CHORUS         (core 1, code to load)
  frame 3200   T5 FX2  SPRING REV -> DARK REV      (core 0, reverb to reverb)
  frame 4400   T3 FX1  COMPRESSOR -> FLANGER       (core 1)
  frame 5600   T6 FX1  FILTER -> PHASER            (core 0)
  frame 7000   Part 2: T1 FX1 DJ EQ, T2 FX1 EQUALIZER, T5 FX2 PLATE REV, T6 FX1 CHORUS
  frame 9000   Part 1 again
through the stock setters a user reaches from the FX pages (0x400526e4 FX1,
0x40052474 FX2) and the manual Part selector (0x4004a8a4). Each track's
chain is read back from the host-port blocks (recloop), as verify_stock_load.

  anchors   T4, T7, T8 (LO-FI, SPATIALIZER, COMB) are never switched: sample
            for sample equal to stock over the whole run, every switch
            included, at the one offset they share (nothing a switch does
            reaches another track)
  dropout   around every switch (0.1 s before to 0.6 s after), the switched
            track's quietest 5 ms window is no more than 6 dB below stock's
            quietest in the same span: the old effect plays until the new
            one takes over, never silence in between
  burst     and its loudest 5 ms window no more than 3 dB above stock's
  settle    over the last 0.4 s before the next event, every track's level
            within 1 dB of stock's
  quiet     no message, no transport error, no refusal on the dynamic image
Owned fixture copies only.
"""
from pathlib import Path
import json,math,os,shutil,subprocess,sys
if not __package__:
    sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
    __package__='tools.experimental.dsp_dynload'
from .runtime_catalog import ROOT
OUT=ROOT/'out/dsp-dynload/stock-switch'
FRAMES=11000
FX=[('EQUALIZER','PLATE REV'),('FILTER','DELAY'),('COMPRESSOR','DARK REV'),('LO-FI',None),
    ('DJ EQ','SPRING REV'),('FILTER',None),('SPATIALIZER',None),('COMB FILTER',None)]
SWITCHES=[(2000,0,0,'CHORUS'),(3200,4,1,'DARK REV'),(4400,2,0,'FLANGER'),(5600,5,0,'PHASER')]
PART2={(0,0):'DJ EQ',(1,0):'EQUALIZER',(4,1):'PLATE REV',(5,0):'CHORUS'}
PARTS=[(7000,1),(9000,0)]
ANCHORS=(4,7,8)
COUNTERS=('dl_modal_shown','dl_errors','dl_residency_failures','dl_residency_commits','dl_unguarded',
          'dl_residency_words','dl_selection_refused')
WIN=220                                   # 5 ms

def main():
    if not os.environ.get('OT_PROJECT'):
        print('[SKIP] stock switch: supply OT_PROJECT');return
    sys.path.insert(0,str(ROOT/'tools'));import toolpath  # noqa: F401
    from ab_fixture import prepare
    import ot_project as otp,blockdump as bd,recloop as rl
    from remix import registry
    mods=registry.modules()
    OUT.mkdir(parents=True,exist_ok=True)
    project=prepare(os.environ['OT_PROJECT'],OUT/'fixture')
    def page(key):
        vals=[(v.default or 0) if v.name else 0 for v in mods[key].params]
        names=[v.name for v in mods[key].params]
        if key.endswith('REV') and b'MIX' in names: vals[names.index(b'MIX')]=80
        return vals
    def fx_of(part,t,slot):
        if part==1 and (t,slot) in PART2: return PART2[t,slot]
        return FX[t][slot]
    def mutate(data):
        for p in range(otp.NPARTS_ALL):
            off=otp.PART_BASE+p*otp.PART_STRIDE; base=off+9
            which=1 if p%4==1 else 0                                   # every bank's Part 2
            for t in range(8):
                data[base+0x22+t]=2                                   # THRU
                data[base+0x36+30*t:base+0x3d+30*t]=bytes((1,127,0,0,64,0,0))
                data[base+0x12+2*t]=64
                for slot in (0,1):
                    key=fx_of(which,t,slot)
                    data[off+(otp.FX1_OFF,otp.FX2_OFF)[slot]+t]=mods[key].menu.fx2_id if key else 0
                    vals=page(key) if key else [0]*12
                    at=off+otp.P1_OFF+t*otp.TRACK_STRIDE+6*slot; data[at:at+6]=bytes(v&0x7f for v in vals[:6])
                    at=off+otp.P2_OFF+t*otp.P2_STRIDE+6*slot; data[at:at+6]=bytes(v&0x7f for v in vals[6:12])
        for pat in range(16):
            for t in range(8):
                at=otp.trac_off(pat,t)
                for mask in (0,0x40,0x48): data[at+mask+7]|=1
    for path in project.glob('bank*.work'):
        otp._bank_write(project,int(path.stem[4:]),mutate,guard=False)
    card=OUT/'card.img'
    subprocess.run([sys.executable,'tools/emu/ot_emu/stage_card.py',str(project),'OCTABAM','RIG',
                    '--tree',str(OUT/'tree'),'--out',str(card)],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
    syms={p[2]:int(p[0],16) for p in (l.split() for l in subprocess.check_output(
        ['m68k-elf-nm',str(ROOT/'out/platform/runtime/runtime.elf')],text=True).splitlines()) if len(p)==3}
    images={'stock':ROOT/'out/raw/section_3_MAIN_OS.bin','dynamic':ROOT/'out/mainos_bus.bin'}
    raw_img=images['dynamic'].read_bytes()
    def rd32(a): return int.from_bytes(raw_img[a-0x40000400:a-0x40000400+4],'big')
    def row(table,id):
        for i in range(32):
            ptr=rd32(table+4*i)
            if not ptr: break
            if rd32(ptr)==id: return i
        raise ValueError((hex(table),id))
    def poke(vs): return ';'.join(f'{a+i:#x}={b}' for a,v,n in vs for i,b in enumerate(v.to_bytes(n,'big')))
    # The dynamic image's chooser rows are stock's (the build keeps every
    # listed stock row), so one script drives both images.
    script=[]
    for frame,t,slot,key in SWITCHES:
        fid=mods[key].menu.fx2_id
        chooser=(0x460d5ca8,0x40052474,0x400d6090) if slot else (0x460d5c94,0x400526e4,0x400d6060)
        script+=['--step',f'{frame}:poke:'+poke([(0x80000000,t,1),(chooser[0],row(chooser[2],fid),4)]),
                 '--step',f'{frame}:call:{chooser[1]:#x}']
    for frame,part in PARTS:
        script+=['--step',f'{frame}:call:0x4004a8a4,{part}']
    for img,path in images.items():
        d=OUT/img; d.mkdir(exist_ok=True); shutil.copyfile(path,d/'image.bin')
        cmd=[str(ROOT/'out/emu/ot_emu'),'--image',str(d/'image.bin'),'--card',str(card),'--set','OCTABAM',
             '--project','RIG','--load-ms','20000','--frame','--dsp','--dsp-dirty','--audio-in','tones',
             '--audio-in-from-boot','--pre-roll','8',
             '--sequencer','--internal-clock','--frames',str(FRAMES),'--main-level','64',
             '--block-dump',str(d/'blocks.bin'),'--audio-out',str(d/'main')]
        if img=='dynamic':
            cmd+=['--step',f'-:call:{syms["dl_publication_finish"]:#x}']
        cmd+=script
        if img=='dynamic':
            cmd+=['--mem-dump',';'.join(f'{syms[n]:#x},{8 if n=="dl_residency_words" else 4}={d}/{n}.bin'
                                         for n in COUNTERS)+f';0x80000ec4,16={d}/ids.bin;0x80000003,1={d}/part.bin']
        with (d/'port.log').open('w') as log:
            subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=3600)
    rec={n:bd.classes(bd.read(str(OUT/n/'blocks.bin'))) for n in images}
    audio={n:{(t,r):rl.readback_audio(rec[n],t,r) for t in range(1,9) for r in (False,True)} for n in images}
    fails=[]
    def check(label,ok,detail=''):
        print(f"  [{'ok' if ok else 'FAIL'}] {label}"+(f'  {detail}' if detail else ''),flush=True)
        if not ok: fails.append(label)
    r={}
    for n in COUNTERS:
        b=(OUT/'dynamic'/f'{n}.bin').read_bytes(); r[n]=[int.from_bytes(b[i:i+4],'big') for i in range(0,len(b),4)]
    check('quiet: no message, no transport error, no residency failure, no refusal',
          r['dl_modal_shown']==[0] and r['dl_errors']==[0] and r['dl_residency_failures']==[0]
          and r['dl_selection_refused']==[0],json.dumps(r))
    part=(OUT/'dynamic'/'part.bin').read_bytes()
    check('the run ends on Part 1, as scripted',part==b'\0',part.hex())
    # the offset the anchors share, over their whole length after the load
    def offsets(a,b,span):
        tail=b[-span:]; found=set()
        for s0 in range(len(a)-len(tail),-1,-1):
            if a[s0]==tail[0] and a[s0:s0+len(tail)]==tail: found.add(len(b)-len(tail)-s0)
        return found
    common=None
    for t in ANCHORS:
        for right in (False,True):
            o=offsets(audio['stock'][t,right],audio['dynamic'][t,right],2000*16)
            common=o if common is None else common&o
    if not check('anchors: T4, T7, T8 share one offset against stock',bool(common),str(common)):
        print('FAIL: no common offset'); sys.exit(1)
    d=min(common,key=abs)
    for t in ANCHORS:
        for right in (False,True):
            a,b=audio['stock'][t,right],audio['dynamic'][t,right]
            n=min(len(a),len(b)-d) if d>=0 else min(len(a)+d,len(b))
            lo=4*16*50                                               # past the load's first frames
            diff=[i for i in range(lo,n) if a[i]!=b[i+d]]
            check(f"anchors: T{t}{'R' if right else 'L'} equals stock sample for sample through every switch",
                  not diff,f'{len(diff):,} of {n-lo:,} differ, first at {diff[0] if diff else "-"}')
    def rms(x): return math.sqrt(sum(v*v for v in x)/len(x)) if x else 0.0
    def db(x): return 20*math.log10(x+1)
    def wins(x,s,e): return [rms(x[i:i+WIN]) for i in range(max(0,s),max(0,e-WIN),WIN)]
    # the sample index of a script frame in the chains: `base` samples after the
    # chain's start (calibrated from stock's first switch, printed), 16 a frame;
    # the dynamic run is `d` later
    base=int(os.environ.get('SWITCH_BASE','0'))
    events=[(f,t,'FX') for f,t,_s,_k in SWITCHES]+[(f,None,'PART') for f,_p in PARTS]
    events.sort()
    a=audio['stock'][1,False]; lv=[rms(a[i:i+WIN]) for i in range(0,len(a)-WIN,WIN)]
    print(f'  [info] chain length {len(a):,} samples; FRAMES*16 = {FRAMES*16:,}; offset d = {d}')
    report={'offset':d,'switch':[]}
    for k,(frame,t,kind) in enumerate(events):
        tracks=[t+1] if t is not None else [1,2,5,6]
        s=base+frame*16
        nxt=base+(events[k+1][0]*16 if k+1<len(events) else FRAMES*16)
        for tr in tracks:
            for right in (False,True):
                a,b=audio['stock'][tr,right],audio['dynamic'][tr,right]
                ws=wins(a,s-4410,s+26460); wd=wins(b,s-4410+d,s+26460+d)
                if not ws or not wd: continue
                low=db(min(wd))-db(min(ws)); high=db(max(wd))-db(max(ws))
                side=f"T{tr}{'R' if right else 'L'}"
                check(f'frame {frame} {kind} {side}: no dropout (quietest 5 ms within 6 dB of stock\'s)',low>=-6,
                      f'{low:+.1f} dB')
                check(f'frame {frame} {kind} {side}: no burst (loudest 5 ms within 3 dB of stock\'s)',high<=3,
                      f'{high:+.1f} dB')
                report['switch'].append({'frame':frame,'kind':kind,'chain':side,'low_db':round(low,2),'high_db':round(high,2)})
        for tr in range(1,9):
            for right in (False,True):
                a,b=audio['stock'][tr,right],audio['dynamic'][tr,right]
                e=nxt-16*16; st=e-int(0.4*44100)
                if st<=s: continue
                lv=db(rms(b[st+d:e+d]))-db(rms(a[st:e]))
                check(f"settle before frame {(nxt-base)//16}: T{tr}{'R' if right else 'L'} within 1 dB of stock",abs(lv)<=1,
                      f'{lv:+.2f} dB')
    (OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    if fails:
        print(f'FAIL: {len(fails)} check(s)'); sys.exit(1)
    print('PASS: FX and Part switches while playing -- no dropout, no burst, settled on stock, anchors sample-exact')

if __name__=='__main__': main()
