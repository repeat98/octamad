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

def stock_package(row,reclaimed=(),helpers=None):
    """`reclaimed`: native P ranges (start, end) that will not stay resident
    besides this package's own span; `helpers`: native routine address ->
    resident copy address, for routines inside reclaimed code it calls.
    Absolute jumps into the package relocate like DO ends (two-word forms
    only: a one-word jump holds 12 bits); jumps to resident code stay; jumps
    into reclaimed code go to a helper copy or the package is refused.
    The disassembler omits zero words, so a skipped run of them is a nop."""
    words=list(row['p_words']); base=row['p_base']; reloc=[]; covered=0; helpers=helpers or {}
    end=base+len(words)
    def gone(a): return any(s<=a<e for s,e in reclaimed)
    with tempfile.TemporaryDirectory() as tmp:
        p=Path(tmp)/'code.bin'
        p.write_bytes(b''.join(w.to_bytes(3,'little') for w in words))
        out=subprocess.check_output([str(ROOT/'vendor/dsp56300/build/source/disassemble/dsp56kDisassemble'),
                                     '-in',str(p),'-pc',f'{base:x}','-le'],text=True)
    for line in out.splitlines():
        m=re.match(r'([0-9a-f]{6}):\s*(.*?)\s*;\s*([0-9a-f ]+)$',line)
        if not m: continue
        at=int(m[1],16)-base; code=m[2]; enc=[int(w,16) for w in m[3].split()]
        if at>covered and not any(words[covered:at]): covered=at
        if at!=covered or words[at:at+len(enc)]!=enc: raise ValueError('disassembly coverage drift')
        covered+=len(enc)
        if re.search(r'\bdc\b|\bp:',code):
            raise ValueError(f"unqualified absolute stock operand: {line}")
        target=re.search(r'func_([0-9a-f]{6})',code)
        target=int(target[1],16) if target else None
        if code.startswith('j'):
            if target is None: raise ValueError('unqualified computed jump: '+line)
            inside=base<=target<end
            if len(enc)==2 and enc[1]==target:
                if inside: reloc.append(at+1)
                elif target in helpers: words[at+1]=helpers[target]
                elif gone(target): raise ValueError('jump into reclaimed code: '+line)
            elif len(enc)==1 and enc[0]&0xfff==target:
                if inside: raise ValueError('one-word jump inside a moving package: '+line)
                if target in helpers:
                    if helpers[target]>=0x1000: raise ValueError('helper copy out of one-word reach: '+line)
                    words[at]=enc[0]&~0xfff|helpers[target]
                elif gone(target): raise ValueError('jump into reclaimed code: '+line)
            else: raise ValueError('unqualified absolute jump form: '+line)
        elif code.startswith('do '):
            if len(enc)!=2 or not base<=enc[1]<end: raise ValueError('DO leaves package')
            reloc.append(at+1)
        elif code.startswith('b'):
            if target is not None and not base<=target<end:
                if len(enc)!=2 or enc[0] not in (0x0d1080,0x0d10c0):
                    raise ValueError('unqualified external relative branch: '+line)
                if (base+at+enc[1])&0xffffff != target: raise ValueError('relative branch origin drift')
                if target in helpers: words[at+1]=(helpers[target]-base-at)&0xffffff
                elif gone(target): raise ValueError('branch into reclaimed code: '+line)
                reloc.append((at+1)|0x8000)
    if covered<len(words) and not any(words[covered:]): covered=len(words)
    if covered!=len(words): raise ValueError('incomplete stock disassembly')
    for r in reloc:
        i=r&0x7fff
        words[i]=(words[i]+base if r&0x8000 else words[i]-base)&0xffffff
    return dict(words=words,relocations=reloc,init=row['init']-base,proc=row['proc']-base)

# Shared stock routines other effects call, as (owner, offset into the owner's
# span, words). FILTER's tail from P:0x98a (A) is a library of filter routines
# that FILTER, DJ EQ, SPATIALIZER and the reverbs call with ONE-word jsr, so its
# copy
# must sit below P:0x1000; the reverbs share a 35-word routine in SPRING and a
# 93-word one at DARK's tail. Same offsets on both payloads (B is 0x240 lower).
SHARED=(('FILTER',0x1b9,286),('SPRING REV',0x334,35),('DARK REV',0x3ce,93))
# The part of an owner that stays a package: FILTER's init/proc and the exit
# tail its proc branches to (P:0x980) precede its library; the reverbs keep
# their whole span (their own calls stay internal).
PACKAGE_WORDS={'FILTER':0x1b9}

def _disassemble(words,base):
    with tempfile.TemporaryDirectory() as tmp:
        p=Path(tmp)/'code.bin'
        p.write_bytes(b''.join(w.to_bytes(3,'little') for w in words))
        return subprocess.check_output([str(ROOT/'vendor/dsp56300/build/source/disassemble/dsp56kDisassemble'),
                                        '-in',str(p),'-pc',f'{base:x}','-le'],text=True)

def shared_copy(row,offset,length,at,reclaimed,helpers=None):
    """A shared stock routine block moved to the fixed address `at`: every
    absolute reference inside it is rebased there once, at build time, and a
    call into an earlier shared block goes to that block's copy (`helpers`).
    One-word jumps stay one word, so every copy must end below P:0x1000."""
    helpers=helpers or {}
    base=row['p_base']+offset; words=list(row['p_words'][offset:offset+length]); covered=0
    end=base+length
    def gone(a): return any(s<=a<e for s,e in reclaimed) and not base<=a<end
    for line in _disassemble(words,base).splitlines():
        m=re.match(r'([0-9a-f]{6}):\s*(.*?)\s*;\s*([0-9a-f ]+)$',line)
        if not m: continue
        i=int(m[1],16)-base; code=m[2]; enc=[int(w,16) for w in m[3].split()]
        if i>covered and not any(words[covered:i]): covered=i
        if i!=covered or words[i:i+len(enc)]!=enc: raise ValueError('shared disassembly coverage drift')
        covered+=len(enc)
        if re.search(r'\bdc\b|\bp:',code): raise ValueError('shared routine reads P: '+line)
        target=re.search(r'func_([0-9a-f]{6})',code); target=int(target[1],16) if target else None
        moved=None if target is None else target-base+at if base<=target<end else helpers.get(target)
        if code.startswith('j'):
            if target is None: raise ValueError('computed jump in shared routine: '+line)
            if gone(target) and moved is None: raise ValueError('shared routine jumps into reclaimed code: '+line)
            if moved is not None:
                if len(enc)==2 and enc[1]==target: words[i+1]=moved
                elif len(enc)==1 and enc[0]&0xfff==target:
                    if moved>=0x1000: raise ValueError('shared copy out of one-word reach: '+line)
                    words[i]=enc[0]&~0xfff|moved
                else: raise ValueError('unqualified jump form in shared routine: '+line)
        elif code.startswith('do '):
            if len(enc)!=2 or not base<=enc[1]<end: raise ValueError('shared DO leaves the block')
            words[i+1]=enc[1]-base+at
        elif code.startswith('b') and target is not None and not base<=target<end:
            raise ValueError('shared routine branches out of its block: '+line)
    if covered<len(words) and not any(words[covered:]): covered=len(words)
    if covered!=len(words): raise ValueError('incomplete shared disassembly')
    if at+length>0x1000: raise ValueError('shared copy ends above P:0x1000')
    return words

def dynamic_layout(rows,core,start):
    """Shared copies from `start` on; returns (native->copy map, [(at, words)], next free)."""
    byname={r['key']:r for r in rows if r['core']==core}
    spans=[(r['p_base'],r['p_base']+len(r['p_words'])) for r in byname.values() if r['p_words']]
    reclaimed=[(min(s for s,_ in spans),max(e for _,e in spans))]
    helpers,copies,at={},[],start
    for owner,offset,length in SHARED:
        row=byname[owner]
        copies.append((at,shared_copy(row,offset,length,at,reclaimed,helpers)))
        for k in range(length): helpers[row['p_base']+offset+k]=at+k
        at+=length
    return helpers,copies,at,reclaimed

def dynamic_package(row,reclaimed,helpers):
    """One stock effect as a movable package against the shared copies."""
    n=PACKAGE_WORDS.get(row['key'])
    if n: row=dict(row,p_words=row['p_words'][:n])
    return stock_package(row,reclaimed,helpers)

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
