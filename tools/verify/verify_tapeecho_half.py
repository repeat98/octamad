#!/usr/bin/env python3
"""Opt-in half-rate experiment: compiled CPU oracle, paired cost and audio.

Builds both variants from the current sources, then leaves the requested
half-rate image in out/mainos_bus.bin. Does not change the shipping remix.
"""
import json
import pathlib
import shutil
import subprocess
import sys
ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import toolpath
from remix import registry
OUT=ROOT/'out/tapeecho-half'
def run(args):
    p=subprocess.run([str(x) for x in args],cwd=ROOT,capture_output=True,text=True)
    if p.returncode:raise RuntimeError(f'{args}\n{p.stdout[-4000:]}\n{p.stderr[-4000:]}')
    return p.stdout

def main():
    remix=sys.argv[1] if len(sys.argv)>1 else 'repitch-tapeecho-half'
    if 'TAPE ECHO HALF' not in registry.remix(remix).modules:
        print(f'  [SKIP] half-rate Tape Echo not in {remix}');return
    OUT.mkdir(parents=True,exist_ok=True)
    print(run([sys.executable,'modules/tapeecho_half/generate_cpu.py','--check']),end='',flush=True)
    run(['cmake','-S','tools/emu/ot_emu','-B','out/emu'])
    run(['cmake','--build','out/emu','--target','ot_tapeecho_cpu_test','ot_tapeecho_half_test','-j8'])
    for label,selected,probe,profile in [('reference','repitch-tapeecho','ot_tapeecho_cpu_test',ROOT/'out/tapeecho-cpu'),('half',remix,'ot_tapeecho_half_test',OUT)]:
        run(['make','bus',f'REMIX={selected}'])
        symbols=run(['m68k-elf-nm','-n','out/platform/runtime/runtime.elf'])
        profile.mkdir(parents=True,exist_ok=True);(profile/'profile-symbols.txt').write_text(symbols)
        syms={x[2]:int(x[0],16) for line in symbols.splitlines() if len(x:=line.split())==3}
        layout=json.loads((ROOT/'out/platform/layout.json').read_text())
        args=[ROOT/'out/emu'/probe,ROOT/'out/mainos_bus.bin',ROOT/'out/platform/runtime.raw',f'{layout["base"]:x}',f'{syms["te_states"]:x}']
        for suffix,extra in [('coldfire',[]),('benchmark',['--benchmark'])]:
            result=run(args+extra);(OUT/f'{label}-{suffix}.log').write_text(result)
            print('\n'.join(x for x in result.splitlines() if any(k in x for k in ('[PASS]','[METER]','[BENCH]'))),flush=True)
        shutil.copy2(ROOT/'out/mainos_bus.bin',OUT/f'{label}-mainos.bin')
    run(['cc','-O2','-DTE_HOST=1','-fsanitize=undefined','-fno-sanitize-recover=all',
         '-c','modules/tapeecho_half/cpu.c','-o',OUT/'sanitize.o'])
    run(['c++','-O2','-fsanitize=undefined','-fno-sanitize-recover=all',
         'tools/harness/tapeecho_half_stress.cpp',OUT/'sanitize.o','-o',OUT/'sanitize'])
    sanitized=run([OUT/'sanitize']);(OUT/'sanitize.log').write_text(sanitized)
    print(sanitized,end='',flush=True)
    result=run([sys.executable,'tools/harness/compare_tapeecho_rates.py'])
    (OUT/'comparison.log').write_text(result)
    m=json.loads((OUT/'comparison.json').read_text())
    assert max(m['transients'].values())<.01, m['transients']
    assert abs(m['safety']['half']['dc_last_second'])<.01,m['safety']
    assert m['safety']['half']['peak']<=1,m['safety']
    print('  [PASS] Half-rate exact dry, dirty entry, BEAT settling, bounded stress and rapid TIME residual <0.01 FS')
    print('  [REPORT] '+str(OUT/'comparison.json'))
    print('  [WAV] '+str(OUT/'bright-repeats-AB.wav')+' (full, silence, half; identical gain)')
    print('OK: experimental half-rate correctness gates passed; voicing changes are measurements, not a quality approval.')
if __name__=='__main__':main()
