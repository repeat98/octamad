from dataclasses import replace
from pathlib import Path
import runpy
from remix.schema import DspHook,DspSection,Gate,Linked
from experimental.dsp_part_loader.runtime_catalog import include
base=runpy.run_path(str(Path(__file__).parent.parent/'dsp-loader-transfer/manifest.py'))['MODULE']
MODULE=replace(base,name='dsp-loader-runtime',key='DSP LOADER RUNTIME',
    doc='Experimental firmware P residency manager, verified uploads and stock dispatch binding.',
    proof_note='Emulator qualification only; static fallback code remains resident.',
    dsp=DspSection(asm='modules/dsp-loader-transfer/receiver_runtime.asm',priority=0,
        ptable=(0,)*1408,payloads=frozenset({'A'}),
        hooks=(DspHook(0x8e,(0x667000,0x207),'frame','runtime P transfer and dispatch binding'),)),
    linked=base.linked[:-1]+(
        Linked('dlallocator','modules/dsp-loader-transfer/allocator.s',dram=True),
        Linked('dlmanager','modules/dsp-loader-transfer/manager.s',dram=True),
        Linked('dlcatalog','modules/dsp-loader-transfer/catalog.s',dram=True,include=include)),
    requires=('DSP LOADER RUNTIME B',),gates=(
        Gate('tools/experimental/dsp_part_loader/verify_controller.py',remix_arg=False),
        Gate('tools/experimental/dsp_part_loader/verify_runtime_audio.py',remix_arg=False,stage='image'),
        Gate('tools/experimental/dsp_part_loader/verify_runtime.py',remix_arg=False,stage='image'),
        Gate('tools/experimental/dsp_part_loader/verify_project_publication.py',remix_arg=False,stage='image'),
        Gate('tools/experimental/dsp_part_loader/verify_live_audio.py',remix_arg=False,stage='image'),
        Gate('tools/experimental/dsp_part_loader/verify_pattern_audio.py',remix_arg=False,stage='image')))
