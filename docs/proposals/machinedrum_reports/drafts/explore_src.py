import sys, shutil, subprocess, pathlib
ROOT = pathlib.Path('/Users/jannikassfalg/coding/octamad')
sys.path.insert(0, str(ROOT/'tools/harness')); sys.path.insert(0, str(ROOT/'tools/hw')); sys.path.insert(0, str(ROOT/'tools'))
import toolpath  # noqa
import ot_project as otp
from md_panel import run_scripted, key
OUT = ROOT/'out/mdverify/ui'
proj = OUT/'project'
if proj.exists(): shutil.rmtree(proj)
shutil.copytree(ROOT/'out/machinedrum/testset/OCTABAM/RIG', proj)
for part in range(1,5):
    otp.set_machine_type(proj, 1, part, 1, 6, guard=False)
card = OUT/'card.img'
subprocess.run([sys.executable, str(ROOT/'tools/emu/ot_emu/stage_card.py'), str(proj), 'OCTABAM', 'RIG',
                '--tree', str(OUT/'tree'), '--out', str(card)], check=True, capture_output=True)
shutil.copy2(ROOT/'out/mainos_bus.bin', OUT/'image.bin')
DB = 0x400e21e0
part = DB + 0x8ed80
dumps = [f"{part:#x},{0x18b2}={OUT/'part0.bin'}"]
cmd = [str(ROOT/'out/machinedrum/isolated/emu/ot_emu'), '--image', str(OUT/'image.bin'), '--card', str(card),
       '--set', 'OCTABAM', '--project', 'RIG', '--load-ms', '20000', '--dsp', '--lcd', str(OUT/'lcd.bin')]
for d in dumps: cmd += ['--mem-dump', d]
script = [(1.0, 'key 0x10 down'), (0.5, 'key 0x10 up')] + key(0x22) + [(3, 'enc 0 10'), (3, 'enc 1 5'), (3, 'enc 5 3'), (4, 'quit')]
rc, sent = run_scripted(cmd, script, OUT/'port.txt', cwd=ROOT, timeout=600)
print('rc', rc, 'sent', len(sent))
