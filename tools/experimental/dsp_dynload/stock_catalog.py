"""Recover native-address stock DSP candidates from the user's 1.40C image.

This inventory is an input to the shared residency manager, not permission to
reclaim memory. Stock tables, buffer allocators, shared helpers and dispatch
must remain resident until their adapters are qualified. Never check its output
into git: generated candidate files contain stock firmware words.
"""
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3]

def build():
    sys.path.insert(0,str(ROOT/'tools'))
    import toolpath  # noqa: F401
    import dsp_modmap as dm
    from remix import stock
    image=(ROOT/'out/raw/section_3_MAIN_OS.bin').read_bytes()
    entries=[]
    for payload,va,size in dm.PAYLOADS:
        records,blob=dm.modules(image,va,size)
        memory={space:{} for space in (0,1,2)}
        for space,base,count,offset in records:
            if space not in memory: raise ValueError('unknown stock memory space')
            for i in range(count):
                word=dm.w24(blob,offset+3*i)
                address=base+i
                if address in memory[space]: raise ValueError('overlapping stock records')
                memory[space][address]=word
        spans=stock.p_spans(payload)
        for mod in stock.MODULES:
            fxid=mod.menu.fx2_id
            init,proc=(memory[1][base+fxid] for base in (0x215,0x235))
            row=dict(key=mod.key,payload=payload,core=0 if payload=='A' else 1,
                     fx_id=fxid,init=init,proc=proc,
                     slots=['fx1','fx2'] if fxid in stock.fx1_ids() else ['fx2'],
                     source_sha256=hashlib.sha256(image).hexdigest(),
                     processing_bound=None,eligible_for_dynamic_admission=False)
            if mod.key=='DELAY':
                row.update(execution='ColdFire',p_words=[],p_base=None,
                           adapter_requirements=['Keep ColdFire delay DMA and SDRAM ring ownership'])
            else:
                base,count=spans[mod.key]
                words=[memory[0][a] for a in range(base,base+count)]
                if not all(base<=address<base+count for address in (init,proc)):
                    raise ValueError(f'{payload} {mod.key}: dispatch leaves recorded algorithm span')
                requirements=['Native P addresses; no relocation assumed',
                              'Keep stock X/Y tables and shared system routines resident',
                              'Qualify dispatcher and processing allowance before admission']
                if mod.claims and mod.claims.stock_instance_buffer:
                    requirements.append('Adapt per-instance buffer allocation before releasing buffers')
                # DARK calls into SPRING. Until helper-level dependencies are
                # represented, conservatively retain the complete SPRING span.
                dependencies=['SPRING REV'] if mod.key in ('PLATE REV','DARK REV') else []
                row.update(execution='DSP',p_base=base,p_words=words,
                           code_sha256=hashlib.sha256(b''.join(w.to_bytes(3,'big') for w in words)).hexdigest(),
                           retain_dependencies=dependencies,adapter_requirements=requirements)
            entries.append(row)
    assert len(entries)==28
    assert all(sum(len(e['p_words']) for e in entries if e['core']==c)==6158 for c in (0,1))
    return entries

def main():
    out=ROOT/'out/dsp-dynload/stock-catalog.json'
    out.parent.mkdir(parents=True,exist_ok=True)
    entries=build()
    out.write_text(json.dumps(entries,indent=2)+'\n')
    print('PASS: 13 native-address stock DSP candidates per core; dispatch spans and 6,158 P words/core checked')
    print('Stock DELAY remains ColdFire; dynamic admission disabled until adapters are qualified')
if __name__=='__main__': main()
