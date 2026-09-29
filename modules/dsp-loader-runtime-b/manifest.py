from remix.schema import Category,DspHook,DspSection,Kind,Module,Proof
MODULE=Module(name='dsp-loader-runtime-b',key='DSP LOADER RUNTIME B',kind=Kind.DSP_EFFECT,
    category=Category.REFERENCE,author='repeat98',author_url='https://github.com/repeat98',
    doc='Core 1 of the experimental residency manager.',proof=Proof.PORT,
    proof_note='Emulator qualification only; not a flash candidate.',
    dsp=DspSection(asm='modules/dsp-loader-transfer/receiver_runtime.asm',priority=0,
        ptable=(0,)*1408,payloads=frozenset({'B'}),
        hooks=(DspHook(0x76,(0x667000,0x207),'frame','runtime P transfer and dispatch binding'),)))
