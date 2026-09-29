from dataclasses import replace
from pathlib import Path
import runpy
from remix.schema import Detour,DspHook,DspSection,Gate,Linked
from experimental.dsp_dynload.runtime_catalog import include
base=runpy.run_path(str(Path(__file__).parent.parent/'dsp-dynload-transport/manifest.py'))['MODULE']
MODULE=replace(base,name='dsp-dynload',key='DSP DYNLOAD',
    doc='Experimental firmware P residency manager, verified uploads and stock dispatch binding.',
    proof_note='Emulator qualification only; static fallback code remains resident.',
    dsp=DspSection(asm='modules/dsp-dynload-transport/receiver_runtime.asm',priority=0,
        ptable=(0,)*1408,payloads=frozenset({'A'}),
        hooks=(DspHook(0x8e,(0x667000,0x207),'frame','runtime P transfer and dispatch binding'),)),
    linked=base.linked[:-1]+(
        Linked('dlallocator','modules/dsp-dynload-transport/allocator.s',dram=True),
        Linked('dlpublication','modules/dsp-dynload-transport/publication.s',dram=True),
        Linked('dlpublishhooks','modules/dsp-dynload-transport/publication_hooks.s',dram=True),
        Linked('dlpreflight','modules/dsp-dynload-transport/preflight.s',dram=True),
        Linked('dlmanager','modules/dsp-dynload-transport/manager.s',dram=True),
        Linked('dlcatalog','modules/dsp-dynload-transport/catalog.s',dram=True,include=include)),
    detours=base.detours+(
        Detour(0x400a0570,bytes.fromhex('4fefffec48d7007c'),'dlpublishhooks','dl_pattern_post','prepare stopped pattern requests before immediate publication',pad_to=8),
        Detour(0x40023c7c,bytes.fromhex('2f02242f0008'),'dlpublishhooks','dl_project_post','prepare project before posting its load command'),
        Detour(0x40085336,bytes.fromhex('2d4afdca2f2a0108'),'dlpublishhooks','dl_project_engine','refuse unprepared project before any loader side effect',pad_to=8),
        Detour(0x4008540e,bytes.fromhex('2f02206efdca'),'dlpublishhooks','dl_project_end','acknowledge completed project publication'),
        Detour(0x400a11ba,bytes.fromhex('42b98000654a'),'dlpublishhooks','dl_chain_stop','admit a chain restart before STOP stores its first pattern'),
        Detour(0x40029a4c,bytes.fromhex('4fefffec48d7043c'),'dlpublishhooks','dl_paste_guard','prepare a pasted active Part before it is written and applied',pad_to=8),
        Detour(0x4004aab4,bytes.fromhex('4fefffe048d70c3c'),'dlpublishhooks','dl_reload_guard','prepare a reloaded active Part before it is written and applied',pad_to=8),
        Detour(0x4004a9d0,bytes.fromhex('4feffff048d70c0c'),'dlpublishhooks','dl_reset_guard','check a reset active Part before it is written and applied',pad_to=8),
        Detour(0x400a406e,bytes.fromhex('41f9800065be'),'dlpublishhooks','dl_boundary_a','admit stop/next pattern before publication'),
        Detour(0x400a44a0,bytes.fromhex('41f9800065be'),'dlpublishhooks','dl_boundary_b','admit queued pattern before publication')),
    requires=('DSP DYNLOAD B',),gates=(
        Gate('tools/experimental/dsp_dynload/verify_controller.py',remix_arg=False),
        Gate('tools/experimental/dsp_dynload/verify_runtime_audio.py',remix_arg=False,stage='image'),
        Gate('tools/experimental/dsp_dynload/verify_runtime.py',remix_arg=False,stage='image'),
        Gate('tools/experimental/dsp_dynload/verify_publication_guards.py',remix_arg=False,stage='image'),
        Gate('tools/experimental/dsp_dynload/verify_pattern_refusal.py',remix_arg=False,stage='image'),
        Gate('tools/experimental/dsp_dynload/verify_chain_stop.py',remix_arg=False,stage='image'),
        Gate('tools/experimental/dsp_dynload/verify_part_edits.py',remix_arg=False,stage='image'),
        Gate('tools/experimental/dsp_dynload/verify_project_publication.py',remix_arg=False,stage='image'),
        Gate('tools/experimental/dsp_dynload/verify_live_audio.py',remix_arg=False,stage='image'),
        Gate('tools/experimental/dsp_dynload/verify_pattern_audio.py',remix_arg=False,stage='image')))
