"""Build-local stock/new packages. Never persist stock words in tracked files.

Stock EQ, PHASER and COMP use PC-relative branches and full-word DO ends. External PC-relative branches are rebased too.
Read each instruction at its native payload address, relocate DO ends and
external long branches, and reject other absolute control or P-memory operands.
Tables and shared helpers stay native.
"""
from pathlib import Path
import re
import subprocess
import tempfile
from .stock_catalog import build as stock_build
from .build_candidates import build as new_build
ROOT=Path(__file__).resolve().parents[3]
MANAGED=('EQUALIZER','PHASER','COMPRESSOR')

def stock_package(row):
    words=list(row['p_words']); base=row['p_base']; reloc=[]; covered=0
    with tempfile.TemporaryDirectory() as tmp:
        p=Path(tmp)/'code.bin'
        p.write_bytes(b''.join(w.to_bytes(3,'little') for w in words))
        out=subprocess.check_output([str(ROOT/'vendor/dsp56300/build/source/disassemble/dsp56kDisassemble'),
                                     '-in',str(p),'-pc',f'{base:x}','-le'],text=True)
    for line in out.splitlines():
        m=re.match(r'([0-9a-f]{6}):\s*(.*?)\s*;\s*([0-9a-f ]+)$',line)
        if not m: continue
        at=int(m[1],16)-base; code=m[2]; enc=[int(w,16) for w in m[3].split()]
        if at!=covered or words[at:at+len(enc)]!=enc: raise ValueError('disassembly coverage drift')
        covered+=len(enc)
        if re.search(r'\b(?:dc|jmp|jsr)\b|\bp:',code):
            raise ValueError(f"unqualified absolute stock operand: {line}")
        if code.startswith('do '):
            if len(enc)!=2 or not base<=enc[1]<base+len(words): raise ValueError('DO leaves package')
            reloc.append(at+1)
        elif code.startswith('b'):
            target=re.search(r'func_([0-9a-f]{6})',code)
            if target and not base<=int(target[1],16)<base+len(words):
                if len(enc)!=2 or enc[0] not in (0x0d1080,0x0d10c0):
                    raise ValueError('unqualified external relative branch: '+line)
                if (base+at+enc[1])&0xffffff != int(target[1],16): raise ValueError('relative branch origin drift')
                reloc.append((at+1)|0x8000)
    if covered!=len(words): raise ValueError('incomplete stock disassembly')
    for r in reloc:
        i=r&0x7fff
        words[i]=(words[i]+base if r&0x8000 else words[i]-base)&0xffffff
    return dict(words=words,relocations=reloc,init=row['init']-base,proc=row['proc']-base)

def packages(character=True):
    result={}
    for r in stock_build():
        if r['key'] in MANAGED: result[r['core'],r['fx_id']]=stock_package(r)
    if character:
        p=new_build('character')
        for c in (0,1): result[c,28]=dict(words=p.sections[0].words,
            relocations=[r.offset for r in p.relocations],init=p.init,proc=p.proc)
    return result

def include(modules):
    data=packages('CHARACTER' in modules)
    lines=['.section .rodata','.balign 4','.global dl_catalog','dl_catalog:']
    resident={0,4,5,8,12,13,16,17,18,19,24,28}
    for p in range(32):
        pkg=data.get((0,p)); exists=p in resident
        lines += [f'.word {len(pkg["words"]) if pkg else 0},1', '.long 0',
                  f'.byte {1 if p==28 and pkg else 3},{0 if pkg else 1},{int(exists)},0']
    lines+=['.balign 4','.global dl_codes','dl_codes:']
    for c in range(2):
        for p in range(32):
            v=data.get((c,p)); label=f'dl_pkg_{c}_{p}'
            if v: lines += [f'.long {label}_words,{label}_reloc',
                            f'.word {len(v["words"])},{v["init"]},{v["proc"]},{len(v["relocations"])}']
            else: lines += ['.long 0,0','.word 0,0,0,0']
    for (c,p),v in data.items():
        label=f'dl_pkg_{c}_{p}'
        lines+=['.balign 4',label+'_words:']
        for i in range(0,len(v['words']),8): lines+=['.long '+','.join(hex(x) for x in v['words'][i:i+8])]
        lines+=[label+'_reloc:','.word '+','.join(str(x) for x in v['relocations'])]
    return '\n'.join(lines)+'\n'
