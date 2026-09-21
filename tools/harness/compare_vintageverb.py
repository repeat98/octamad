#!/usr/bin/env python3
"""Render the installed VintageVerb AU's untouched default and compare Mini Verb.

macOS, C++ compiler and a licensed VintageVerb Audio Unit required. The AU is
used through its public parameter/render API, offline, without opening a DAW.
Only the benchmark itself estimates target DSP cost; host AU time is irrelevant.
Writes normalized wet A/B audio and raw measurements to out/vintage_study.
"""
from __future__ import annotations
import argparse
import array
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import wave

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import toolpath  # noqa: F401,E402
import benchmark_reverbs as bench
from remix import registry

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'out/vintage_study'
SR=44100


def read_wav(path):
    with wave.open(str(path),'rb') as w:
        if (w.getsampwidth(),w.getnchannels(),w.getframerate()) != (3,2,SR):
            raise ValueError('expected stereo 24-bit 44.1 kHz WAV')
        b=w.readframes(w.getnframes())
    return [int.from_bytes(b[i:i+3],'little',signed=True)/8388608 for i in range(0,len(b),3)]


def read_float(path):
    a=array.array('f'); a.frombytes(path.read_bytes())
    if sys.byteorder != 'little': a.byteswap()
    if not all(math.isfinite(v) for v in a): raise ValueError('non-finite AU output')
    return list(a[bench.WARM*bench.FRAMES*2:])


def metrics(audio):
    e=[audio[i]**2+audio[i+1]**2 for i in range(0,len(audio),2)]
    total=sum(e)
    if total <= 0: raise ValueError('silent render')
    energy=total; curve=[]
    for n,power in enumerate(e):
        db=10*math.log10(max(energy,1e-30)/total)
        if -25 < db < -5: curve.append((n/SR,db))
        energy-=power
    n=len(curve); sx=sum(x for x,y in curve); sy=sum(y for x,y in curve)
    slope=(n*sum(x*y for x,y in curve)-sx*sy)/(n*sum(x*x for x,y in curve)-sx*sx)
    def density(start,end):
        # A simple window diagnostic, not a perceptual similarity score.
        a=audio[int(start*SR)*2:int(end*SR)*2:2]
        rms=math.sqrt(sum(v*v for v in a)/len(a))
        return sum(abs(v)>rms for v in a)/len(a)/.3173105
    left=audio[::2];right=audio[1::2]
    corr=sum(l*r for l,r in zip(left,right))/math.sqrt(sum(v*v for v in left)*sum(v*v for v in right))
    return dict(rt60_from_t20_seconds=-60/slope, wet_rms=math.sqrt(total/len(audio)),
                peak=max(map(abs,audio)), stereo_correlation=corr,
                normalized_density_50_100ms=density(.05,.1),
                normalized_density_100_200ms=density(.1,.2),
                normalized_density_200_400ms=density(.2,.4),
                normalized_density_500_1000ms=density(.5,1))


def render():
    OUT.mkdir(parents=True,exist_ok=True)
    host=OUT/'au_reference'
    subprocess.run(['clang++','-std=c++17',str(ROOT/'tools/harness/au_reference.cpp'),
                    '-framework','AudioToolbox','-framework','CoreFoundation','-o',str(host)],check=True)
    mod=registry.by_key('MINIVERB'); mem=bench.prepare()['miniverb']
    impulse=bench.source(22050,impulse=True)
    drums=bench.OUT/'drums.raw'
    if not drums.exists():
        raise RuntimeError('run make verify-miniverb first to generate the deterministic drum source')
    for tag,source in [('ir',impulse),('drums',drums)]:
        command=[str(host),'--in',str(source),'--out',str(OUT/f'default_{tag}.f32')]
        result=subprocess.run(command,capture_output=True,text=True,check=True,timeout=60)
        (OUT/f'default_{tag}_parameters.tsv').write_text(result.stdout)
        (OUT/f'default_{tag}_command.json').write_text(json.dumps(command,indent=2)+'\n')
        _,audio=bench.run(mod,mem,f'default_{tag}',22050,instances=1,inputs=[source])
        bench.wav(OUT/f'miniverb_default_{tag}.wav',audio[0][bench.WARM*bench.FRAMES*2:])


def report():
    ref_ir=read_float(OUT/'default_ir.f32')
    mini_ir=read_wav(OUT/'miniverb_default_ir.wav')
    ref=read_float(OUT/'default_drums.f32')
    mini=read_wav(OUT/'miniverb_default_drums.wav')
    for audio in (ref,mini):
        if max(map(abs,audio)) >= 1: raise ValueError('clipped comparison input')
    # Match stereo RMS over the four seconds of percussion, including the
    # plugin's own predelay. One common reduction keeps BOTH clips below -1 dBFS.
    rms=lambda a:math.sqrt(sum(v*v for v in a[:4*SR*2])/(4*SR*2))
    gains=[.08/rms(mini),.08/rms(ref)]
    ceiling=10**(-1/20)
    common=min(1.0,ceiling/max(max(map(abs,a))*g for a,g in zip([mini,ref],gains)))
    gains=[g*common for g in gains]
    matched=[]
    for name,a,g in zip(['mini','valhalla'],[mini,ref],gains):
        q=[round(v*g*8388607) for v in a]
        assert max(map(abs,q)) < 8388607
        bench.wav(OUT/f'{name}_default_wet_matched.wav',q)
        matched.append(q)
    bench.wav(OUT/'ab_default.wav',matched[0]+[0]*SR+matched[1])
    parameter_text=(OUT/'default_ir_parameters.tsv').read_text()
    version=next(line.split('\t')[1] for line in parameter_text.splitlines()
                 if line.startswith('# component_version\t'))
    results=dict(target=f'Unmodified fresh-instance default of installed VintageVerb AU {version}',
                 reference=metrics(ref_ir), miniverb=metrics(mini_ir),
                 listening_gains=dict(miniverb=gains[0],valhalla=gains[1]),
                 ab_order='A: Mini Verb; 0.5 seconds silence; B: VintageVerb default',
                 matching='Stereo RMS over first four seconds; NOT LUFS matching or a similarity score',
                 source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in [ROOT/'modules/miniverb/miniverb.asm',ROOT/'modules/miniverb/manifest.py']})
    (OUT/'comparison.json').write_text(json.dumps(results,indent=2)+'\n')
    (OUT/'comparison.md').write_text(
        '# VintageVerb default comparison\n\n'
        f'Reference: an unmodified fresh instance of the installed VintageVerb AU {version}. '
        'All 17 normalized parameters are recorded in the parameter TSV. '
        'The same impulse and deterministic percussion drive both reverbs at 44.1 kHz.\n\n'
        '| Metric | Mini Verb | VintageVerb default |\n|---|---:|---:|\n'
        f'| RT60 extrapolated from -5 to -25 dB (s) | {results["miniverb"]["rt60_from_t20_seconds"]:.2f} | {results["reference"]["rt60_from_t20_seconds"]:.2f} |\n'
        f'| Raw impulse peak | {results["miniverb"]["peak"]:.4f} | {results["reference"]["peak"]:.4f} |\n'
        f'| Wet L/R correlation | {results["miniverb"]["stereo_correlation"]:.3f} | {results["reference"]["stereo_correlation"]:.3f} |\n\n'
        'RT60 is an extrapolation from a finite eight-second capture, not a full 60 dB measurement. '
        'Matching decay does not establish perceptual equivalence. Mini Verb still has a different '
        'early-reflection pattern, fixed room geometry and simpler modulation/tone controls. '
        'It folds input to mono and has no separate predelay or color algorithms.\n\n'
        'Listen to `ab_default.wav`: **A = Mini Verb, B = VintageVerb default**, '
        'with 0.5 seconds of silence between. Both are 100% wet. Their stereo RMS over '
        'the first four seconds is matched, with a common safety reduction if needed. '
        'No limiter or peak normalization is used. The matched individual clips are also saved.\n\n'
        'This is an original resource-constrained implementation inspired by the audible reference, '
        'not a port of Valhalla code or a claim to reproduce its algorithms. '
        'Target DSP cost comes from `make benchmark-reverbs`; desktop plugin CPU is not comparable.\n')
    print(json.dumps(results,indent=2))


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--report-only',action='store_true')
    args=ap.parse_args()
    if not args.report_only: render()
    report()

if __name__=='__main__':main()
