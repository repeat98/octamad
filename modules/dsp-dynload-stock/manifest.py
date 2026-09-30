"""DSP dynamic loading, stock variant: every stock DSP effect loads on demand.

The same runtime as DSP DYNLOAD (guards, allocator, receiver, dry bypass),
with a catalog of all 13 stock DSP effects (runtime_catalog.include_dynamic)
and an arena sized to the whole effect block less the shared stock routines,
the receiver and, when present, Analog BD. The build harvests the effect
block, keeps every listed stock row and stubs every stock id until bound
(schema.Module.dynamic_stock). The UI tick runs one stock call later than
DSP DYNLOAD's, so ANALOG BD's hook at 0x4005221e can coexist.
"""
from dataclasses import replace
from pathlib import Path
import runpy
from remix.schema import Detour,DspHook,DspSection,Gate,Linked
from experimental.dsp_dynload.runtime_catalog import include_dynamic
H=bytes.fromhex
# Table words: 64 saved dispatch entries + the arena. The build sizes it
# (schema.DspSection.arena): the effect block is 6,158 words per core, less
# 414 shared routines, the receiver and whatever the remix's own modules
# take; the rest is this table. The least it accepts holds the saved entries
# and the largest stock effect (DARK REV, 1,067 words), so every stock effect
# can always load on its own.
ARENA_MIN=64+1067
base=runpy.run_path(str(Path(__file__).parent.parent/'dsp-dynload/manifest.py'))['MODULE']
MODULE=replace(base,name='dsp-dynload-stock',key='DSP DYNLOAD STOCK',
    doc='DSP dynamic loading of every stock DSP effect: no stock effect code is built in.',
    proof_note='Port qualification in progress; a first hardware test pending.',
    dsp=DspSection(asm='modules/dsp-dynload-transport/receiver_runtime.asm',priority=0,
        arena='DLWORDS',arena_min=ARENA_MIN,payloads=frozenset({'A'}),
        hooks=(DspHook(0x8e,(0x667000,0x207),'frame','runtime P transfer and dispatch binding'),)),
    linked=tuple(replace(l,include=include_dynamic) if l.label=='dlcatalog' else l for l in base.linked),
    detours=tuple(d for d in base.detours if d.site!=0x4005221e)+(
        Detour(0x40052228,H('4eb9400316a0'),'dlhooks','dl_tick2',
               'UI tick one stock call after ANALOG BD\'s hook: deferred messages, residency, guards'),),
    requires=('DSP DYNLOAD STOCK B',),
    dynamic_stock=True,
    gates=(Gate('tools/experimental/dsp_dynload/verify_controller.py',remix_arg=False),
           Gate('tools/experimental/dsp_dynload/verify_stock_relocation.py',remix_arg=False),
           Gate('tools/experimental/dsp_dynload/verify_stock_select.py',remix_arg=False,stage='image'),
           Gate('tools/experimental/dsp_dynload/verify_stock_load.py',remix_arg=False,stage='image')))
