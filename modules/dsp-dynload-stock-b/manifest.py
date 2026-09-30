"""Core 1 (payload B) of DSP DYNLOAD STOCK: the receiver and its arena."""
from pathlib import Path
import runpy
from remix.schema import Category,DspHook,DspSection,Kind,Module,Proof
ARENA_MIN=runpy.run_path(str(Path(__file__).parent.parent/'dsp-dynload-stock/manifest.py'))['ARENA_MIN']
MODULE=Module(name='dsp-dynload-stock-b',key='DSP DYNLOAD STOCK B',kind=Kind.DSP_EFFECT,
    category=Category.REFERENCE,author='repeat98',author_url='https://github.com/repeat98',
    doc='Core 1 of DSP DYNLOAD STOCK.',proof=Proof.PORT,
    proof_note='Port qualification in progress; a first hardware test pending.',
    dsp=DspSection(asm='modules/dsp-dynload-transport/receiver_runtime.asm',priority=0,
        arena='DLWORDS',arena_min=ARENA_MIN,payloads=frozenset({'B'}),
        hooks=(DspHook(0x76,(0x667000,0x207),'frame','runtime P transfer and dispatch binding'),)),
    dynamic_stock=True)
