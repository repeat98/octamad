#!/usr/bin/env python3
"""Execute the diagnostic hooks and test the capture decoder. No hardware I/O."""
import pathlib, sys, subprocess, struct
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools'))
import toolpath
sys.path.insert(0, str(ROOT/'tools/hw'))
from ot_crashlog import Parser, decode
if len(sys.argv) > 1:
    from remix import registry
    if 'CRASH TRACE' not in registry.remix(sys.argv[1]).modules:
        print('[ -- ] crash trace not selected'); sys.exit(0)
from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, UC_HOOK_MEM_WRITE, UC_HOOK_CODE
from unicorn.m68k_const import *
image = (ROOT/'out/mainos_bus.bin').read_bytes()
elf = ROOT/'out/linked/crash-trace/crashtrace/u.elf'
symbols = {p[2]: int(p[0],16) for line in subprocess.check_output(['m68k-elf-nm',str(elf)],text=True).splitlines() if len(p:=line.split())==3}
base = int.from_bytes(image[0xd56a-0x400:0xd56e-0x400],'big')
assert base == symbols['trace_frame'], 'Build octapitch-euclid-debug first'
regs = [UC_M68K_REG_D0+i for i in range(8)] + [UC_M68K_REG_A0+i for i in range(7)]
stack=0x47100000

def machine():
    u=Uc(UC_ARCH_M68K,UC_MODE_BIG_ENDIAN); u.ctl_set_cpu_model(UC_CPU_M68K_CFV4E)
    for b,n in [(0x40000000,0x8000000),(0x80000000,0x10000),(0xfc000000,0x1000000)]: u.mem_map(b,n)
    u.mem_write(0x40000400,image)
    u.reg_write(UC_M68K_REG_SR,0x231f)
    u.reg_write(UC_M68K_REG_A7,stack)
    for i,r in enumerate(regs): u.reg_write(r,0x12340000+i)
    return u

def w(u,a,v): u.mem_write(a,struct.pack('>I',v & 0xffffffff))
def r(u,a): return int.from_bytes(u.mem_read(a,4),'big')
def sr(u):
    # Read SR with an actual instruction: Unicorn's API exposes stale lazy
    # NZVC bits after MOVE, although executed MOVESR sees the right flags.
    pc=u.reg_read(UC_M68K_REG_PC); d7=u.reg_read(UC_M68K_REG_D7)
    u.mem_write(0x47200000,bytes.fromhex('40c7'))
    u.emu_start(0x47200000,0x47200002,count=1)
    value=u.reg_read(UC_M68K_REG_D7)&65535
    u.reg_write(UC_M68K_REG_D7,d7); u.reg_write(UC_M68K_REG_PC,pc)
    return value

def run(u,start,end,count=100000):
    u.emu_start(start,end,count=count)
    assert u.reg_read(UC_M68K_REG_PC)==end, hex(u.reg_read(UC_M68K_REG_PC))

def ready():
    u=machine(); w(u,0x400b966c,0x47000000); w(u,0x400b9678,12)
    w(u,0x4610757c,0xffff1234); w(u,0x800065b8,1); w(u,0x8000181c,2880)
    for t in range(8):
        u.mem_write(0x80000110+t*64+54,bytes([0,29,0,22]))
    return u

u=ready(); before=[u.reg_read(x) for x in regs]
instructions=[]
u.hook_add(UC_HOOK_CODE,lambda *args:instructions.append(1))
run(u,0x4000d568,0x4000d56e)
print(f'[INFO] checkpoint hook: {len(instructions)} executed instructions')
assert len(instructions)<2000
assert u.reg_read(UC_M68K_REG_A7)==stack
assert [u.reg_read(x) for x in regs[1:]]==before[1:]
assert u.reg_read(UC_M68K_REG_D0)==0x75180000
assert sr(u)==0x2310, hex(sr(u))
packet=bytes(u.mem_read(0x47000000+(12-i)%4096,1)[0] for i in range(90))
e=decode(packet)
assert e['frames']==1 and e['tempo']==120 and e['fx_ids']==[29,22]*8
assert r(u,0x400b967c)==90 and r(u,0x460ba988)==0xfffffff7
assert packet==bytes(u.mem_read(symbols['trace_packet'],90))
p=Parser(); events=[]
for b in packet: events+=p.feed(bytes([b,0xf8]))
assert len(events)==1 and events[0]['event']=='checkpoint' and p.clock==90
corrupt=bytearray(packet); corrupt[10]^=1
assert Parser().feed(corrupt)[0]['event']=='invalid_trace'
assert not Parser().feed(b'\xf0'+bytes(1000)+b'\xf7')
print('[PASS] exact checkpoint, queue wrap, preserved registers/SR, realtime interleaving, corruption and bounded parsing')
for addr,val in [(0x400b967c,4095),(0x400b9688,1),(0x460ba978,1),(0x460ba988,0xfffffff0),(0x400b966c,0),(0x400b9678,4096)]:
    u=ready(); w(u,addr,val); ring=bytes(u.mem_read(0x47000000,4096))
    run(u,0x4000d568,0x4000d56e)
    assert r(u,symbols['trace_dropped'])==1
    assert bytes(u.mem_read(0x47000000,4096))==ring
print('[PASS] busy/disabled/SysEx/uninitialized queues skip without waiting or writing')
u=ready(); run(u,0x4000d568,0x4000d56e); w(u,0x400b967c,0)
for _ in range(2755):
    run(u,0x4000d568,0x4000d56e)
    assert sr(u)==0x2310, hex(sr(u))
assert r(u,0x400b967c)==0
run(u,0x4000d568,0x4000d56e)
assert r(u,0x400b967c)==90 and r(u,symbols['trace_frames'])==2757
print('[PASS] checkpoint cadence is independent of transport')
for status in (4,0):
    u=ready(); w(u,symbols['trace_started'],1)
    u.mem_write(0xfc060004,bytes([status]))
    w(u,stack+4,0x47101000); w(u,0x47101000,0x40102300); w(u,0x47101004,0x40012346)
    sent=[]
    u.hook_add(UC_HOOK_MEM_WRITE,lambda u,a,addr,size,value,data:sent.append(value & 255),begin=0xfc06000c,end=0xfc06000c)
    run(u,0x4003af94,0x4003af9c,count=12000000)
    assert u.reg_read(UC_M68K_REG_A7)==stack-44
    if status:
        e=Parser().feed(bytes(sent))[0]
        assert e['event']=='exception' and e['pc']=='0x40012346' and e['vector']==4
    else: assert not sent
print('[PASS] injected exception reaches host before stock panel printer; stuck MIDI has bounded timeout')
