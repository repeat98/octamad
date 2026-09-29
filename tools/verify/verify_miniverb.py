#!/usr/bin/env python3
"""Eight-instance Mini Verb isolation and audio gates on assembled DSP code."""
import json
import math
import random
from pathlib import Path
import struct
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import toolpath  # noqa: F401,E402
from benchmark_reverbs import (OUT, WARM, FRAMES, prepare, run, source, knobs,
                               raw, wav)
from remix import registry
import send_probe


def verify(mems):
    mod = registry.by_key('MINIVERB')
    gates = []
    def gate(name, ok, detail=''):
        gates.append(dict(name=name, passed=bool(ok), detail=detail))
        print(f"[{'PASS' if ok else 'FAIL'}] {name} {detail}", flush=True)
        if not ok:
            (OUT/'verification.json').write_text(json.dumps(gates, indent=2))
            raise AssertionError(name)

    blocks = 2048
    inputs = [source(blocks, k) for k in range(8)]
    cost, together = run(mod, mems, 'isolation_all', blocks, automate=True, inputs=inputs,
                      split=[1,3,7,15,15,7,3,1])
    # Pristine OS 1.40C spring's measured maximum over all 16 splits and
    # synchronous/asynchronous control sweeps, 20 Sep 2026. See benchmark.
    gate('eight modulated instances fit the stock spring instruction peak',
         max(c['peak_block'] for c in cost['cores']) <= 20376,
         f"{max(c['peak_block'] for c in cost['cores'])} <= 20376 per core/block")
    for k in range(8):
        _, solo = run(mod, mems, f'isolation_solo{k}', blocks, instances=1,
                      automate=True, inputs=[inputs[k]], positions=[k],
                      split=[[1,3,7,15,15,7,3,1][k]])
        gate(f'slot {k}: eight-instance output == isolated output', together[k] == solo[0])
    # Exercise both schedules, including shared-window slots on both cores.
    _, skewed = run(mod, mems, 'isolation_skew', blocks, automate=True, inputs=inputs,
                    split=[1,3,7,15,15,7,3,1], extra=['-skew','97'])
    gate('interleaved cores == lock-step, every sample', together == skewed)
    for k in range(8):
        _, tracks = run(mod, mems, f'onehot{k}', blocks, automate=True,
                        inputs=inputs, mask=1<<k)
        bleed = max(abs(v) for j,t in enumerate(tracks) if j != k for v in t)
        signal = max(abs(v) for v in tracks[k][WARM*FRAMES*2:])
        gate(f'slot {k} excited: other seven exactly silent', bleed == 0 and signal > 1000,
             f'bleed={bleed} Q23 LSB, active peak={signal}')

    # A constant tone reveals actual modulation, while tracking the phase
    # proves that RATE advances by samples rather than process-call count.
    tone=raw(OUT/'mod_tone.raw',[round(.15*8388607*math.sin(2*math.pi*733*n/44100))
                               if n >= WARM*FRAMES else 0 for n in range(4096*FRAMES)])
    modulation_audio=[]
    for depth in (0,127):
        pv=knobs(mod); pv[3]=depth; pv[4]=2
        auto=OUT/f'mod_depth{depth}.csv';auto.write_text(','.join(map(str,[0,*pv]))+'\n')
        phase=OUT/f'mod_phase{depth}.txt'
        _, audio=run(mod,mems,f'mod_depth{depth}',4096,instances=1,inputs=[tone],
                    split=[7],extra=['-paramfile',str(auto),'-track','37','-trackout',str(phase)])
        steps=[list(map(int,line.split()[1:])) for line in phase.read_text().splitlines()][WARM:]
        for channel,advance in enumerate((48,)):
            values=[row[channel] for row in steps]
            gate(f'MOD {depth}, LFO {channel+1}: bounded sample clock, splits and wrap',
                 all(0 <= phase < 131072 for phase in values)
                 and any(b<a for a,b in zip(values,values[1:]))
                 and all((b-a)%131072 == advance for a,b in zip(values,values[1:])))
        modulation_audio.append(audio[0][44100*2:])
    difference=sum((a-b)**2 for a,b in zip(*modulation_audio))
    energy=sum(a*a for a in modulation_audio[0])
    gate('MOD changes the sustained wet signal', difference > .001*energy,
         f'residual/signal energy {difference/max(energy,1):.3f}')

    # Seed all eight scalar blocks AND all eight delay regions, including
    # shared memory. The old -dirty option covers low Y only.
    dirty = []
    for c, base in enumerate(mems):
        data = base.read_bytes()
        body, term = data[:-9], data[-9:]
        assert term[0] == 255
        for slot, ybase in enumerate([0x4000,0x8000,0x30000+c*0x8000,0x34000+c*0x8000]):
            fill = [0x320080,0x800000,0x7fffff,0x5a5a5a][slot]
            body += struct.pack('<BII',1,0x6200+slot*0x300,0x100)+struct.pack('<I',fill)*0x100
            body += struct.pack('<BII',2,ybase,0x4000)+struct.pack('<I',fill)*0x4000
        path=OUT/f'miniverb_dirty_{c}.mem'
        path.write_bytes(body+term); dirty.append(path)
    _, quiet = run(mod, dirty, 'dirty_silent', 1024, mask=0, automate=True,
                   extra=['-guard','16384','-guard-shared'])
    gate('dirty state + dirty delay memory: all eight silent', not any(v for t in quiet for v in t))
    log=(OUT/'miniverb_dirty_silent.log').read_text()
    gate('bounds including shared Y and loaded program memory',
         log.count('0 stray write regions, 0 CLOBBERING') == 8)

    _, _ = run(mod, mems, 'active_bounds', 1024, automate=True,
               inputs=inputs, split=[1,3,7,15,15,7,3,1],
               extra=['-guard','16384','-guard-shared'])
    log=(OUT/'miniverb_active_bounds.log').read_text()
    gate('active split processing stays within all eight buffers',
         log.count('0 stray write regions, 0 CLOBBERING') == 8)

    # Positive control: a deliberate write into core B's shared buffer must
    # be detected while executing on A. Otherwise a green guard proves nothing.
    asm = OUT/'guard_probe.asm'
    asm.write_text('move #>$123456,a\nmove a,y:>$38001\nrts\n')
    blob = OUT/'guard_probe.bin'
    assembler=Path(__file__).resolve().parents[2]/'vendor/dsp56300/build/source/dsp_host/dsp_asm'
    subprocess.run([str(assembler),'-in',str(asm),'-org','1f000','-out',str(blob)],
                   check=True, capture_output=True)
    code=blob.read_bytes()
    words=[int.from_bytes(code[i:i+3],'little') for i in range(0,len(code),3)]
    base=mems[0].read_bytes()
    probe=OUT/'guard_probe.mem'
    probe.write_bytes(base[:-9]+struct.pack('<BII',0,0x1f000,len(words))+
                      struct.pack('<'+'I'*len(words),*words)+base[-9:])
    command=json.loads((OUT/'miniverb_active_bounds.command.json').read_text())
    # Override the entry point on all instances; one block suffices.
    command += ['-mem',str(probe),'-proc','1f000','-blocks','1',
                '-out',str(OUT/'guard_negative.raw')]
    result=subprocess.run(command,capture_output=True,text=True,timeout=30)
    (OUT/'guard_negative.log').write_text(result.stdout+result.stderr)
    gate('shared-memory guard detects deliberately injected cross-core write',
         'Y:0x38001' in result.stdout and 'stray' in result.stdout)

    # Exact dry endpoint from init, tested against full-range bipolar input.
    ramp = [round(-8388607 + i*16777214/(1024*16-1)) for i in range(1024*16)]
    path=raw(OUT/'bipolar.raw',ramp)
    dry_params = knobs(mod); dry_params[2]=0
    # Explicit one-event automation overrides the default full-wet benchmark setup.
    (OUT/'dry.csv').write_text(','.join(map(str,[0,*dry_params]))+'\n')
    _, audio=run(mod, mems,'dry',1024,instances=1,inputs=[path],
                extra=['-paramfile',str(OUT/'dry.csv')])
    gate('MIX=0 exact bipolar passthrough', list(audio[0][::2]) == ramp and list(audio[0][1::2]) == ramp)

    # Long IRs expose decay, DC, clipping and a stereo tail; WAVs are 24-bit.
    ir_blocks = 22050  # 8 s including warmup, multiple full ring wraps
    ir_input = source(ir_blocks, impulse=True)
    energies = []
    for decay in sorted({0,90,mod.params[0].default,127}):
        pv=knobs(mod); pv[0]=decay
        auto=OUT/f'ir_decay{decay}.csv'; auto.write_text(','.join(map(str,[0,*pv]))+'\n')
        row, tracks=run(mod,mems,f'ir_decay{decay}',ir_blocks,instances=1,inputs=[ir_input],
                       extra=['-paramfile',str(auto)])
        tail=tracks[0][WARM*FRAMES*2:]
        wav(OUT/f'miniverb_ir_decay{decay}.wav', tail)
        if decay == mod.params[0].default:
            early=tail[int(.05*44100)*2:int(.1*44100)*2:2]
            rms=math.sqrt(sum(v*v for v in early)/len(early))
            density=sum(abs(v)>rms for v in early)/len(early)/.3173105
            gate('default early tail retains increased diffusion', density > .6,
                 f'normalized 50–100 ms density={density:.3f}; v2 baseline 0.297')
        first=sum(v*v for v in tail[:44100*2])
        late=sum(v*v for v in tail[-44100*2:])
        energies.append(sum(v*v for v in tail[44100*2:]))
        gate(f'decay {decay}: nonzero stereo tail, no clipping, decays',
             first>0 and row['clipped_samples']==0 and late < first*.001
             and any(l != r for l,r in zip(tail[::2],tail[1::2])),
             f'peak={row["peak_audio"]}, final/first second energy={late/max(first,1):.3g}')
    gate('DECAY increases late-tail energy', energies[0] < energies[1] < energies[2])
    # Audible review artifact plus a held maximum-decay stress case. No
    # normalization: the WAVs preserve the algorithm's actual output gain.
    rng = random.Random(56300)
    drum_blocks = 22050
    drums=[]
    for n in range(drum_blocks*16):
        t=n-WARM*FRAMES
        if 0 <= t < 4*44100:
            beat=t % 22050
            kick=.65*math.sin(2*math.pi*(52*beat/44100 + .12*(1-math.exp(-beat/900))))*math.exp(-beat/2600)
            snare=.20*rng.uniform(-1,1)*math.exp(-beat/1500) if (t//22050)%2 else 0
            hat=.10*rng.uniform(-1,1)*math.exp(-(t%5512)/140)
            value=round((kick+snare+hat)*8388607)
        else:
            value=0
        drums.append(value)
    drum_input=raw(OUT/'drums.raw',drums)
    pv=knobs(mod); pv[0]=127; pv[1]=0; pv[3]=127; pv[4]=7
    auto=OUT/'drums.csv'; auto.write_text(','.join(map(str,[0,*pv]))+'\n')
    row, tracks=run(mod,mems,'drums_max_decay',drum_blocks,instances=1,inputs=[drum_input],
                   extra=['-paramfile',str(auto)])
    late=sum(v*v for v in tracks[0][-44100*2:])
    first_tail=sum(v*v for v in tracks[0][(WARM*FRAMES+4*44100)*2:(WARM*FRAMES+5*44100)*2])
    gate('held maximum decay, brightness, modulation and rate: unclipped and decaying',
         row['clipped_samples']==0 and late < first_tail*.25,
         f'peak={row["peak_audio"]} Q23, late/first-tail energy={late/max(first_tail,1):.4g}')
    # Delay modulation is inside feedback now. Sweep it with feedback and
    # brightness held at their maxima, then allow a stationary silent tail.
    moving=OUT/'drums_modulation.csv'
    events=[]
    for block in range(drum_blocks):
        values=pv.copy()
        if block*FRAMES < WARM*FRAMES+4*44100:
            values[3]=(block*3)%128
            values[4]=(block//67)%8
        events.append(','.join(map(str,[block,*values])))
    moving.write_text('\n'.join(events)+'\n')
    moving_row,moving_tracks=run(mod,mems,'drums_moving_tank',drum_blocks,instances=1,
                                inputs=[drum_input],split=[7],
                                extra=['-paramfile',str(moving)])
    moving_tail=moving_tracks[0]
    late=sum(v*v for v in moving_tail[-44100*2:])
    first_tail=sum(v*v for v in moving_tail[(WARM*FRAMES+4*44100)*2:(WARM*FRAMES+5*44100)*2])
    gate('moving in-loop modulation at maximum feedback: unclipped and decaying',
         moving_row['clipped_samples']==0 and late < first_tail*.25,
         f'peak={moving_row["peak_audio"]} Q23, late/first-tail energy={late/max(first_tail,1):.4g}')
    dry=[v for v in drums[WARM*FRAMES:] for _ in range(2)]
    wet=tracks[0][WARM*FRAMES*2:]
    wav(OUT/'drums_dry.wav',dry)
    wav(OUT/'miniverb_drums_wet.wav',wet)
    wav(OUT/'miniverb_drums_mix.wav',[round(.6*d+.4*w) for d,w in zip(dry,wet)])
    (OUT/'verification.json').write_text(json.dumps(gates,indent=2)+'\n')
    print(f'{len(gates)} Mini Verb gates passed', flush=True)

if __name__ == '__main__':
    name = sys.argv[1] if len(sys.argv) > 1 else 'miniverb'
    if 'MINIVERB' not in registry.remix(name).modules:
        print(f'[N/A] verify_miniverb: {name} does not carry MINIVERB')
    else:
        if len(sys.argv) > 1:
            # make check has just built the selected remix. Exercise its
            # actual relocated code alongside its other modules, rather
            # than silently testing the standalone Mini Verb image.
            image = Path(__file__).resolve().parents[2]/'out/mainos_bus.bin'
            OUT.mkdir(parents=True, exist_ok=True)
            print(f'Verifying Mini Verb in selected image: {name}', flush=True)
            mems = [send_probe.dump_mem(image, OUT/f'selected_{p}.mem', p) for p in 'AB']
        else:
            mems = prepare()['miniverb']
        verify(mems)
