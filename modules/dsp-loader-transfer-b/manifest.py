"""Payload B receiver of the isolated loader transport probe."""
from remix.schema import Category, DspHook, DspSection, Kind, Module, Proof
MODULE=Module(
    name='dsp-loader-transfer-b', key='DSP LOADER TRANSFER B', kind=Kind.DSP_EFFECT,
    category=Category.REFERENCE, author='repeat98', author_url='https://github.com/repeat98',
    doc='Core 1 mailbox receiver for DSP LOADER TRANSFER; no live code writes.',
    proof=Proof.RENDER, proof_note='Unqualified transfer probe; emulator gates in development.',
    dsp=DspSection(asm='modules/dsp-loader-transfer/receiver.asm',priority=0,
        payloads=frozenset({'B'}),
        hooks=(DspHook(0x76,(0x667000,0x207),'frame','frame head: service loader mailbox'),)),
)
