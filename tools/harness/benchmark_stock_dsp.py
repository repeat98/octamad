#!/usr/bin/env python3
"""Stock DSP instruction baseline, with the real X:0 audio buffer on BOTH cores.

One independent instance per core. Stock code scratches X:0x20..0xff, so
multi-instance buffers at 0x80/0xc0/... are invalid. Full four-track loads
are measured through firmware by benchmark_analog_bd.py instead.
"""
import argparse,hashlib,json,sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));import toolpath
import benchmark_reverbs as br,send_probe
from remix import registry,stock
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'out/stock_dsp_bench'
KEYS=['FILTER','EQUALIZER','DJ EQ','PHASER','FLANGER','CHORUS','SPATIALIZER','COMB FILTER','COMPRESSOR','LO-FI','PLATE REV','SPRING REV','DARK REV']
NULL=SimpleNamespace(key='NULL STUB',name='null',menu=SimpleNamespace(fx2_id=0),params=[SimpleNamespace(default=0,active=False,name=b'',count=128)]*12)
def peak(row):return max(c['peak_block'] for c in row['cores'])
def mean(row):return max(c['mean_block'] for c in row['cores'])
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--blocks',type=int,default=4096);a=ap.parse_args()
 br.OUT=OUT;OUT.mkdir(exist_ok=True);mems=[send_probe.dump_mem(stock.STOCK_IMAGE,OUT/f'stock_{p}.mem',p) for p in 'AB'];inputs=[br.source(a.blocks,k) for k in range(2)]
 results={}
 for mod in [NULL]+[registry.by_key(k) for k in KEYS]:
  for tag,auto in [('fixed',False),('moving',True)]:
   if mod is NULL and auto:continue
   row,_=br.run(mod,mems,tag,a.blocks,2,auto,inputs=inputs,positions=[0,4],extra=('-audio','0'))
   results[(mod.key,tag)]=row
 null=peak(results[('NULL STUB','fixed')]);table=[]
 for key in KEYS:
  fixed=results[(key,'fixed')];moving=results[(key,'moving')]
  assert moving['peak_audio']>100,(key,'silent moving-knob render')
  table.append(dict(effect=key,words=stock.WORDS[key],fixed=(peak(fixed)-null)/16,moving_mean=(mean(moving)-null)/16,worst=max(peak(fixed),peak(moving))/16-null/16,peak_audio=moving['peak_audio']))
 report=['# Stock DSP effects: corrected X:0 benchmark','',f'{a.blocks} blocks, one independent instance on each DSP core. Null stub subtracted. Executed instructions/sample, NOT hardware cycles.','', '| Effect | Fixed knobs | Moving mean | Worst tested |','|---|---:|---:|---:|']
 for r in sorted(table,key=lambda x:x['worst']):report.append(f"| {r['effect']} | {r['fixed']:.1f} | {r['moving_mean']:.1f} | {r['worst']:.1f} |")
 report+=['','Supersedes the earlier 0x80-buffer report: that buffer overlapped stock scratch. Audio is now at X:0, as in firmware. No hardware utilization or safe instance count follows from these instruction counts. Whole four-track chains are measured separately through the actual firmware.']
 (OUT/'report.md').write_text('\n'.join(report)+'\n');(OUT/'results.json').write_text(json.dumps(dict(units='executed instructions/sample, not cycles',audio_base=0,blocks=a.blocks,null_stub_peak_one=null,stock_sha256=hashlib.sha256(stock.STOCK_IMAGE.read_bytes()).hexdigest(),dsp_host_sha256=hashlib.sha256(br.HOST.read_bytes()).hexdigest(),table=table,raw={f'{k}/{t}':v for (k,t),v in results.items()}),indent=2)+'\n');print('\n'.join(report))
if __name__=='__main__':main()
