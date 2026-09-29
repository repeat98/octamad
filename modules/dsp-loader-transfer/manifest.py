"""Independent two-core host-port transfer probe; no live P writes."""
from remix.schema import Category, Detour, DspHook, DspSection, Kind, Linked, Module, Proof
H=bytes.fromhex
MODULE=Module(
    name='dsp-loader-transfer', key='DSP LOADER TRANSFER', kind=Kind.HYBRID,
    category=Category.REFERENCE, author='repeat98', author_url='https://github.com/repeat98',
    doc='Experimental two-core DMA mailbox and deferred UI error message; no live code writes.',
    proof=Proof.RENDER, proof_note='Unqualified transfer probe; emulator gates in development.',
    linked=(Linked('dltransfer','modules/dsp-loader-transfer/transfer.s',dram=True),
            Linked('dlhooks','modules/dsp-loader-transfer/hooks.s',dram=True)),
    detours=(Detour(0x40004bc0,H('720113c1fc04801d'),'dlhooks','dl_state7',
                   'append two-core packet writes and status reads',pad_to=8),
             Detour(0x4005221e,H('4ebaff1c4eb94007e940'),'dlhooks','dl_tick',
                   'show deferred transport failures from UI task',pad_to=10)),
    dsp=DspSection(asm='modules/dsp-loader-transfer/receiver.asm',priority=0,
        payloads=frozenset({'A'}),
        hooks=(DspHook(0x8e,(0x667000,0x207),'frame','frame head: service loader mailbox'),)),
    requires=('DSP LOADER TRANSFER B',),
)
