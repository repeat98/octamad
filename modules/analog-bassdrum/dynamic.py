"""Part-resident engine packages. No stock code is embedded in this library."""
import re
import dsp808
import dsp909

COMMON = ('T_LPF','T_TIN','T_PAD','T_KHP','T_GB','T_OB')
COMMON_BASE = 0x2840
DATA_BASE = COMMON_BASE + 128*len(COMMON)
VOICE_BASE = 0x3700
META = 0x3800
LIBRARY = 0x40C00000
LIBRARY_STAGE = 0x40D00000
LIBRARY_LIMIT = 0x100000
P_ORG = 0x2000
X_ORG = 0x4000
CHUNK = 16


def common_layout():
    return {k:COMMON_BASE+128*i for i,k in enumerate(COMMON)}


def cut(source, tag):
    return source[source.index(';<' + tag + '>'):source.index(';</' + tag + '>')]


def resident_desk():
    lay=dsp909.default_layout();lay.update(common_layout())
    full=dsp909.source(lay)
    decode=cut(full,'desk-decode')
    desk=cut(full,'desk')
    desk=desk[:desk.index('        move    a,x:(r0)+')]
    return 'zy01:\n'+decode+'        rts\nzy02:\n'+desk+'        rts\n'


def engine_tables(model):
    if model==0: return dsp808.tables()
    tab,_,lists,_=dsp909.tables()
    return {k:v for k,v in dict(tab,**lists).items() if k not in COMMON}


def engine_source(model, desk, decode, xbase=X_ORG):
    lay={};at=xbase
    for k,v in engine_tables(model).items(): lay[k]=at;at+=len(v)
    shared=dsp909.default_layout(); shared.update(common_layout())
    if model==0: source=dsp808.source(lay,shared)
    else: source=dsp909.source(dict(shared,**lay))
    # Generated 808 blocks omit the closing marker; delimit by the following
    # unchanged source instruction, and keep the original output limiter/trim.
    begin=source.index(';<desk-decode>')
    if model==0:
        end=source.index('        move x:(r6+$c),a',begin)
    else: end=source.index(';</desk-decode>',begin)+len(';</desk-decode>')
    source=source[:begin]+f'        move #>${decode:x},r2\n        jsr (r2)\n'+source[end:]
    begin=source.index(';<desk>')
    end=source.index('        move    a,x:(r0)+',begin)
    suffix=source[end:]
    trim=('        move a,x0\n'+f'        move #>${dsp909.q24(dsp808.OUTPUT_TRIM):x},y0\n        mpy y0,x0,a\n') if model==0 else ''
    source=source[:begin]+f'        move #>${desk:x},r2\n        jsr (r2)\n'+trim+suffix
    # Initial state travels with the package; no per-engine init code stays in P.
    source=source[:source.index('zv02:' if model==0 else 'zq02:')]
    source=source.replace('do      a1,','do      a,')
    return source


def initial(model):
    words=[0]*64
    if model==0: words[0x16]=0x7fffff
    else:
        for k,v in [('C',0x7fffff),('KLPF',0x7fffff),('LCG',dsp909.SEED)]: words[dsp909.OFF[k]]=v
    return words


def assemble(src,org,out):
    syms,_=dsp909.assemble(org,{},out,src)
    blob=out.read_bytes()
    return [int.from_bytes(blob[i:i+3],'little') for i in range(0,len(blob),3)],syms


def package(model,desk,decode,out):
    src=engine_source(model,desk,decode)
    code,syms=assemble(src,P_ORG,out)
    shifted,_=assemble(src,P_ORG+0x1000,out.with_name(out.stem+'-p.bin'))
    xshift,_=assemble(engine_source(model,desk,decode,X_ORG+0x1000),P_ORG,out.with_name(out.stem+'-x.bin'))
    def reloc(other):
        assert len(other)==len(code)
        indices=[i for i,(a,b) in enumerate(zip(code,other)) if a!=b]
        assert all(other[i]==code[i]+0x1000 for i in indices), 'non-additive engine relocation'
        return indices
    return dict(code=code,p=reloc(shifted),x=reloc(xshift),
                data=[dsp909.q24(v) for vals in engine_tables(model).values() for v in vals],
                initial=initial(model),entry=syms['zv01' if model==0 else 'zq01']-P_ORG)


def kernel(org,cont,pend,out):
    from pathlib import Path
    template=(Path(__file__).parent/'dynamic_glue.asm').read_text()+resident_desk()
    def src(pbase):
        return template.replace('@CONT@',f'${cont:x}').replace('@PBASE@',f'${pbase:x}').replace('@PEND@',f'${pend:x}')
    words,syms=assemble(src(org),org,out)
    pbase=org+len(words)
    words,syms=assemble(src(pbase),org,out)
    return words,syms,pbase


def library(kernels, out):
    """Big-endian ColdFire catalogue; DSP words are untagged 24-bit values."""
    count=len(ENGINE_BUILDERS)
    words=[0x41424c31,1,0,count]+[v for k in kernels for v in (k['base'],k['end'])]+[0]*8
    words += [0]*(count*12)
    def append(data):
        at=len(words);words.extend(data);return at
    packages=[]
    for model in range(count):
        pair=[ENGINE_BUILDERS[model](k['symbols']['zy02'],k['symbols']['zy01'],out/f'package-{model}-{i}.bin') for i,k in enumerate(kernels)]
        a,b=pair
        assert a['code'] and len(a['initial'])==64
        assert 0 <= a['entry'] < len(a['code'])
        assert not set(a['p']) & set(a['x'])
        assert all(0 <= i < len(a['code']) for i in a['p']+a['x'])
        assert all(0 <= w <= 0xffffff for pack in pair for key in ('code','data','initial') for w in pack[key])
        assert all(a[k]==b[k] for k in ('p','x','data','initial','entry'))
        assert len(a['code'])==len(b['code'])
        entry=[model,len(a['code']),len(a['data']),append(a['code']),append(b['code']),append(a['data']),append(a['p']),len(a['p']),append(a['x']),len(a['x']),append(a['initial']),a['entry']]
        words[16+12*model:28+12*model]=entry
        packages.append({'id':model,'program_words':len(a['code']),'data_words':len(a['data'])})
    words[2]=len(words)*4
    assert words[2]<=LIBRARY_LIMIT
    for k in kernels:
        assert all(p['program_words']<=k['end']-k['base'] for p in packages)
    assert all(p['data_words']<=VOICE_BASE-DATA_BASE for p in packages)
    return b''.join(w.to_bytes(4,'big') for w in words),packages

# Each future builder supplies code, additive P/X relocations, tables, initial
# voice state and an entry offset. Library size is independent of active-set fit.
ENGINE_BUILDERS = (
    lambda desk,decode,out: package(0,desk,decode,out),
    lambda desk,decode,out: package(1,desk,decode,out),
)
